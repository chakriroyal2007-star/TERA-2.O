"""Capacity-Constrained Multi-Patient Ambulance Allocation Engine.

Mathematical Formulation:
Minimize Z = Σ (C_ij * X_ij)
Subject to:
1. Σ_i X_ij <= 1, for all j (Each ambulance assigned to at most one incident)
2. Σ_j (Capacity_j * X_ij) >= PatientCount_i, for each fully assigned incident i
   (or partial assignment with remaining pending)
3. Type suitability: ALS/ICU ambulances prioritized for critical/trauma/cardiac; BLS for minor.
4. X_ij ∈ {0, 1}
"""
import math
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.models import Incident, Ambulance, Mission
from .priority import calculate_incident_priority, PriorityWeights
from .dijkstra import calculate_shortest_road_route, haversine_distance_meters


def calculate_travel_estimate(
    amb_lat: float,
    amb_lng: float,
    inc_lat: float,
    inc_lng: float,
) -> tuple[float, float]:
    """Returns estimated distance in km and ETA in minutes."""
    dist_m = haversine_distance_meters(amb_lat, amb_lng, inc_lat, inc_lng)
    dist_km = round(dist_m / 1000.0, 2)
    # Average urban response speed 38 km/h + 1.5 min turnout time
    eta_mins = round((dist_km / 38.0) * 60.0 + 1.5, 1)
    return dist_km, eta_mins


def compute_assignment_cost(
    incident_priority_score: float,
    incident_category: str,
    incident_severity: str,
    eta_minutes: float,
    ambulance_type: str,
    ambulance_capacity: int,
    patient_count: int,
) -> tuple[float, str]:
    """Computes C_ij assignment cost (lower cost = optimal match) and reason."""
    v_type = (ambulance_type or "").lower()
    is_high_acuity = incident_severity in ("critical", "high") or incident_category in (
        "cardiac", "stroke", "burns", "trauma", "neonatal"
    )

    # 1. Base travel time cost (2.0 per minute)
    travel_cost = eta_minutes * 2.0

    # 2. Priority inverse cost (urgent incidents get matched to closer resources first)
    priority_discount = (incident_priority_score / 100.0) * 15.0

    # 3. Medical Capability / Equipment Suitability Penalty
    acuity_penalty = 0.0
    reason_notes = []

    if is_high_acuity:
        if "advanced" in v_type or "als" in v_type or "icu" in v_type:
            acuity_penalty = 0.0
            reason_notes.append("ALS/ICU capability matches high-acuity incident")
        else:
            acuity_penalty = 25.0  # Penalty for dispatching BLS to critical when ALS might be required
            reason_notes.append("BLS unit assigned under emergency capacity strain")
    else:
        if "basic" in v_type or "bls" in v_type:
            acuity_penalty = 0.0
            reason_notes.append("BLS unit correctly matched for standard emergency")
        else:
            acuity_penalty = 5.0  # Minor penalty for using ALS on low-acuity (preserves ALS for critical)
            reason_notes.append("ALS unit deployed for basic triage requirement")

    # 4. Capacity Efficiency: prefer matching vehicle capacity to patient count
    cap_diff = ambulance_capacity - patient_count
    if cap_diff < 0:
        cap_penalty = 30.0  # Under-capacity requires secondary vehicle
    else:
        cap_penalty = cap_diff * 2.0  # Mild penalty for excessive empty beds

    total_cost = round(max(1.0, travel_cost - priority_discount + acuity_penalty + cap_penalty), 2)
    reason_notes.append(f"ETA: ~{eta_minutes}m ({round(travel_cost, 1)} cost units)")

    return total_cost, "; ".join(reason_notes)


async def allocate_ambulances_to_incidents(
    incidents: List[Incident],
    ambulances: List[Ambulance],
    weights: Optional[PriorityWeights] = None,
    now_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Executes capacity-constrained multi-patient ambulance allocation.
    
    Evaluates all pending incidents simultaneously, ranks them dynamically,
    and assigns available ambulances without capacity or double-assignment violations.
    """
    if not now_dt:
        now_dt = datetime.now(timezone.utc)

    # Step 1: Dynamic Emergency Priority Ranking
    prioritized_incidents = []
    for inc in incidents:
        p_res = calculate_incident_priority(inc, weights, now_dt)
        prioritized_incidents.append({
            "incident": inc,
            "priority_score": p_res["priority_score"],
            "priority_tier": p_res["priority_tier"],
            "patient_count": p_res["patient_count"],
            "breakdown": p_res,
        })

    # Sort descending by priority score (Critical/High-demand incidents prioritized first)
    prioritized_incidents.sort(key=lambda x: x["priority_score"], reverse=True)

    # Step 2: Available Ambulances Pool
    available_pool = []
    for amb in ambulances:
        if not amb.active:
            continue
        lat = amb.current_latitude if amb.current_latitude is not None else 13.6288
        lng = amb.current_longitude if amb.current_longitude is not None else 79.4192
        cap = getattr(amb, "patient_capacity", 2) or 2
        eq = getattr(amb, "equipment_level", "ALS") or "ALS"
        available_pool.append({
            "ambulance": amb,
            "id": amb.id,
            "registration": amb.registration,
            "vehicle_type": amb.vehicle_type or "Advanced Life Support (ALS)",
            "patient_capacity": cap,
            "equipment_level": eq,
            "latitude": lat,
            "longitude": lng,
            "driver_name": amb.driver_name or "Fleet Crew",
            "driver_phone": amb.driver_phone or "+91 91211 08108",
        })

    assigned_ambulance_ids = set()
    assignments: List[Dict[str, Any]] = []
    unallocated: List[Dict[str, Any]] = []
    total_objective_Z = 0.0

    # Step 3: Match Ambulances to Ranked Incidents
    for item in prioritized_incidents:
        inc = item["incident"]
        p_score = item["priority_score"]
        p_count = item["patient_count"]
        inc_lat = inc.latitude if inc.latitude is not None else 13.6288
        inc_lng = inc.longitude if inc.longitude is not None else 79.4192

        needed_patients = p_count
        incident_assigned_ambs = []

        while needed_patients > 0:
            # Find best candidate ambulance from remaining unassigned pool
            best_cand = None
            best_cost = float("inf")
            best_reason = ""
            best_eta = 0.0
            best_dist_km = 0.0

            for cand in available_pool:
                if cand["id"] in assigned_ambulance_ids:
                    continue

                dist_km, eta_mins = calculate_travel_estimate(
                    cand["latitude"], cand["longitude"], inc_lat, inc_lng
                )

                cost, reason = compute_assignment_cost(
                    incident_priority_score=p_score,
                    incident_category=inc.category,
                    incident_severity=inc.priority,
                    eta_minutes=eta_mins,
                    ambulance_type=cand["vehicle_type"],
                    ambulance_capacity=cand["patient_capacity"],
                    patient_count=needed_patients,
                )

                if cost < best_cost:
                    best_cost = cost
                    best_cand = cand
                    best_reason = reason
                    best_eta = eta_mins
                    best_dist_km = dist_km

            if best_cand is not None:
                # Assign ambulance to incident
                assigned_ambulance_ids.add(best_cand["id"])
                total_objective_Z += best_cost

                # Capacity reduction
                cap_provided = min(needed_patients, best_cand["patient_capacity"])
                needed_patients -= cap_provided

                assignment_rec = {
                    "incident_id": inc.id,
                    "case_id": inc.case_id or inc.id[:8].upper(),
                    "incident_category": inc.category,
                    "incident_priority": inc.priority,
                    "incident_priority_score": p_score,
                    "patient_count_total": p_count,
                    "patients_allocated_this_unit": cap_provided,
                    "ambulance_id": best_cand["id"],
                    "ambulance_registration": best_cand["registration"],
                    "vehicle_type": best_cand["vehicle_type"],
                    "patient_capacity": best_cand["patient_capacity"],
                    "driver_name": best_cand["driver_name"],
                    "driver_phone": best_cand["driver_phone"],
                    "eta_minutes": best_eta,
                    "distance_km": best_dist_km,
                    "cost_Cij": best_cost,
                    "match_reason": best_reason,
                    "status": "recommended",
                }
                assignments.append(assignment_rec)
                incident_assigned_ambs.append(assignment_rec)
            else:
                # No more available ambulances in fleet
                break

        if needed_patients > 0:
            unallocated.append({
                "incident_id": inc.id,
                "case_id": inc.case_id or inc.id[:8].upper(),
                "priority_score": p_score,
                "priority": inc.priority,
                "unserved_patients": needed_patients,
                "total_patients": p_count,
                "reason": "Insufficient available ambulance fleet capacity in service area",
            })

    total_patients_req = sum(item["patient_count"] for item in prioritized_incidents)
    allocated_patients = sum(a["patients_allocated_this_unit"] for a in assignments)
    allocation_efficiency = round((allocated_patients / max(1, total_patients_req)) * 100.0, 1)

    return {
        "status": "success",
        "objective_cost_Z": round(total_objective_Z, 2),
        "total_incidents_evaluated": len(incidents),
        "fully_allocated_incidents": len(incidents) - len(unallocated),
        "unallocated_incidents_count": len(unallocated),
        "total_patients": total_patients_req,
        "allocated_patients": allocated_patients,
        "allocation_efficiency_pct": allocation_efficiency,
        "total_ambulances_assigned": len(assignments),
        "remaining_free_ambulances": len(available_pool) - len(assigned_ambulance_ids),
        "ranked_incident_queue": [item["breakdown"] for item in prioritized_incidents],
        "assignments": assignments,
        "unallocated": unallocated,
    }
