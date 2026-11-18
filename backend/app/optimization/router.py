"""TERA 2.0 Optimization, Routing & Emergency Simulation API Router."""
import time
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, and_, or_, delete
from app.db import get_db
from app.security import current, roles
from app.models import (
    Incident,
    Ambulance,
    Hospital,
    Department,
    Capacity,
    Mission,
    Referral,
    User,
    Organization,
    DispatchRankingWeights,
    OptimizationExecution,
)
from .priority import calculate_incident_priority, PriorityWeights
from .dijkstra import calculate_shortest_road_route, haversine_distance_meters, _DEMO_GRAPH
from .allocation import allocate_ambulances_to_incidents
from .hospital_ranking import rank_hospitals_for_transfer
from .evaluation import run_baseline_vs_optimized_evaluation

router = APIRouter(prefix="/optimization", tags=["Research Optimization & Simulation"])


class WeightsUpdateRequest(BaseModel):
    severity_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    waiting_time_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    patient_count_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    resource_urgency_weight: Optional[float] = Field(None, ge=0.0, le=1.0)


class RouteRequest(BaseModel):
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float


# In-memory storage for custom admin weights if DB record not persisted
_CURRENT_WEIGHTS = PriorityWeights()


@router.get("/priority-ranking")
async def get_priority_ranking(
    db=Depends(get_db),
    user=Depends(roles("operator", "admin", "analyst", "responder", "hospital")),
):
    """Calculates research priority scores and ranks all active/pending incidents."""
    t_start = time.perf_counter()

    incidents = db.scalars(
        select(Incident)
        .where(
            Incident.status.in_(["reported", "verified", "active", "dispatched", "en_route", "on_scene"]),
            Incident.is_hoax.is_(False),
        )
        .order_by(Incident.created_at.desc())
    ).all()

    now_dt = datetime.now(timezone.utc)
    ranked = []
    for inc in incidents:
        res = calculate_incident_priority(inc, _CURRENT_WEIGHTS, now_dt)
        # Update incident record in db with calculated priority score
        inc.priority_score = res["priority_score"]
        inc.priority_breakdown = res["contributions"]
        ranked.append(res)

    db.commit()
    ranked.sort(key=lambda x: x["priority_score"], reverse=True)

    execution_time = round((time.perf_counter() - t_start) * 1000, 2)
    return {
        "status": "success",
        "total_active": len(ranked),
        "execution_time_ms": execution_time,
        "weights": _CURRENT_WEIGHTS.normalize().__dict__,
        "ranked_queue": ranked,
    }


@router.get("/weights")
def get_weights():
    """Retrieves current priority scoring weights."""
    return {
        "weights": _CURRENT_WEIGHTS.normalize().__dict__,
        "formula": "Priority = 0.40*Severity + 0.25*WaitingTime + 0.20*PatientCount + 0.15*ResourceUrgency",
    }


@router.patch("/weights")
def update_weights(
    data: WeightsUpdateRequest,
    user=Depends(roles("admin")),
):
    """Allows administrators to tune priority scoring weights."""
    global _CURRENT_WEIGHTS
    if data.severity_weight is not None:
        _CURRENT_WEIGHTS.severity_weight = data.severity_weight
    if data.waiting_time_weight is not None:
        _CURRENT_WEIGHTS.waiting_time_weight = data.waiting_time_weight
    if data.patient_count_weight is not None:
        _CURRENT_WEIGHTS.patient_count_weight = data.patient_count_weight
    if data.resource_urgency_weight is not None:
        _CURRENT_WEIGHTS.resource_urgency_weight = data.resource_urgency_weight

    _CURRENT_WEIGHTS = _CURRENT_WEIGHTS.normalize()
    return {
        "status": "updated",
        "weights": _CURRENT_WEIGHTS.__dict__,
    }


@router.post("/allocate-ambulances")
async def run_ambulance_allocation(
    db=Depends(get_db),
    user=Depends(roles("operator", "admin", "analyst")),
):
    """Executes capacity-constrained multi-patient ambulance allocation for all pending incidents."""
    t_start = time.perf_counter()

    pending_incidents = db.scalars(
        select(Incident)
        .where(
            Incident.status.in_(["reported", "verified", "active"]),
            Incident.is_hoax.is_(False),
        )
    ).all()

    # Query currently unassigned active ambulances
    busy_ambulance_ids = db.scalars(
        select(Mission.ambulance_id).where(
            Mission.status.in_(["assigned", "acknowledged", "en_route", "on_scene", "transporting", "handover"])
        )
    ).all()

    available_ambulances = db.scalars(
        select(Ambulance).where(
            Ambulance.active.is_(True),
            Ambulance.id.not_in(busy_ambulance_ids) if busy_ambulance_ids else True,
        )
    ).all()

    result = await allocate_ambulances_to_incidents(
        incidents=pending_incidents,
        ambulances=available_ambulances,
        weights=_CURRENT_WEIGHTS,
    )

    exec_ms = round((time.perf_counter() - t_start) * 1000, 2)
    result["execution_time_ms"] = exec_ms

    # Log optimization execution record in DB
    try:
        opt_log = OptimizationExecution(
            algorithm="capacity_constrained_allocation",
            status="completed",
            input_summary={
                "pending_incidents": len(pending_incidents),
                "available_ambulances": len(available_ambulances),
            },
            output_summary={
                "total_assignments": len(result.get("assignments", [])),
                "allocation_efficiency_pct": result.get("allocation_efficiency_pct"),
            },
            execution_time_ms=exec_ms,
            created_by_id=user.id,
        )
        db.add(opt_log)
        db.commit()
    except Exception:
        pass

    return result


@router.get("/hospital-ranking/{incident_id}")
async def get_hospital_recommendations(
    incident_id: str,
    limit: int = Query(3, ge=1, le=10),
    db=Depends(get_db),
    user=Depends(roles("operator", "admin", "analyst", "responder", "hospital")),
):
    """Calculates multi-factor hospital cost ranking for patient transfer."""
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")

    recommendations = await rank_hospitals_for_transfer(db, incident, limit=limit)
    return {
        "incident_id": incident.id,
        "case_id": incident.case_id or incident.id[:8].upper(),
        "category": incident.category,
        "priority": incident.priority,
        "recommendations": recommendations,
    }


@router.post("/dijkstra-route")
async def get_dijkstra_route(
    data: RouteRequest,
    user=Depends(roles("operator", "admin", "analyst", "responder", "hospital")),
):
    """Computes shortest road route using Dijkstra on weighted road network."""
    res = await calculate_shortest_road_route(
        origin=(data.origin_lat, data.origin_lng),
        destination=(data.dest_lat, data.dest_lng),
    )
    return res.model_dump()


@router.get("/baseline-vs-optimized")
async def get_baseline_vs_optimized(
    db=Depends(get_db),
    user=Depends(roles("operator", "admin", "analyst")),
):
    """Runs empirical comparative evaluation between Baseline and TERA 2.0 Optimized systems."""
    incidents = db.scalars(select(Incident).where(Incident.is_hoax.is_(False)).limit(30)).all()
    ambulances = db.scalars(select(Ambulance)).all()
    hospitals = db.scalars(select(Hospital)).all()

    if not incidents:
        return {
            "status": "no_data",
            "message": "Click 'Load Emergency Simulation' to run comparative evaluation on benchmark scenarios.",
        }

    comparison = await run_baseline_vs_optimized_evaluation(incidents, ambulances, hospitals)
    return comparison


# =============================================================================
# PHASE 11: DEMONSTRATION SIMULATION LOADER
# =============================================================================

DEMO_TAG = "DEMO SIMULATION"

# Reproducible Demonstration Coordinates (Tirupati Medical Corridor)
DEMO_SCENARIO_INCIDENTS = [
    {
        "code_suffix": "A",
        "category": "road_traffic_accident",
        "priority": "critical",
        "description": "[DEMO DATA] Incident A: Multiple vehicle collision on Alipiri Bypass; 3 casualties requiring trauma care.",
        "address": "Alipiri Bypass Road, Near Toll Gate, Tirupati",
        "latitude": 13.6495,
        "longitude": 79.4085,
        "casualties_count": 3,
        "reported_offset_min": 0,
    },
    {
        "code_suffix": "B",
        "category": "medical_emergency",
        "priority": "medium",
        "description": "[DEMO DATA] Incident B: Elderly citizen experiencing acute asthma attack and dizziness; stable vitals.",
        "address": "Bhavani Nagar Circle, Tirupati",
        "latitude": 13.6335,
        "longitude": 79.4168,
        "casualties_count": 1,
        "reported_offset_min": 2,
    },
    {
        "code_suffix": "C",
        "category": "cardiac",
        "priority": "critical",
        "description": "[DEMO DATA] Incident C: Severe chest pain radiating to left arm with diaphoresis; suspected acute MI.",
        "address": "Korlagunta Main Road Intersection, Tirupati",
        "latitude": 13.6235,
        "longitude": 79.4285,
        "casualties_count": 2,
        "reported_offset_min": 3,
    },
    {
        "code_suffix": "D",
        "category": "burns",
        "priority": "high",
        "description": "[DEMO DATA] Incident D: Industrial steam burn injury in commercial kitchen; conscious with localized burns.",
        "address": "Tirupati Railway Station South Gate, Tirupati",
        "latitude": 13.6180,
        "longitude": 79.4365,
        "casualties_count": 1,
        "reported_offset_min": 4,
    },
    {
        "code_suffix": "E",
        "category": "road_traffic_accident",
        "priority": "critical",
        "description": "[DEMO DATA] Incident E: Bus rollover near highway flyover; 4 casualties requiring mass-casualty triage.",
        "address": "Renigunta Highway Bypass Flyover, Tirupati",
        "latitude": 13.6310,
        "longitude": 79.4450,
        "casualties_count": 4,
        "reported_offset_min": 5,
    },
]

DEMO_AMBULANCES = [
    {"reg": "AP-03-EMG-1001", "type": "Advanced Life Support (ALS)", "cap": 2, "eq": "ALS", "lat": 13.6288, "lng": 79.4192, "driver": "K. Srinivas", "phone": "+91 94401 22001"},
    {"reg": "AP-03-EMG-1002", "type": "Advanced Life Support (ALS)", "cap": 2, "eq": "ALS", "lat": 13.6420, "lng": 79.4130, "driver": "M. Ramesh", "phone": "+91 94401 22002"},
    {"reg": "AP-03-EMG-1003", "type": "Mobile Intensive Care Unit (MICU)", "cap": 2, "eq": "ICU", "lat": 13.6405, "lng": 79.4350, "driver": "P. Venkatesh", "phone": "+91 94401 22003"},
    {"reg": "AP-03-EMG-1004", "type": "Basic Life Support (BLS)", "cap": 1, "eq": "BLS", "lat": 13.6210, "lng": 79.4120, "driver": "S. Rajesh", "phone": "+91 94401 22004"},
    {"reg": "AP-03-EMG-1005", "type": "Advanced Life Support (ALS)", "cap": 4, "eq": "ALS", "lat": 13.6350, "lng": 79.4270, "driver": "T. Naresh", "phone": "+91 94401 22005"},
    {"reg": "AP-03-EMG-1006", "type": "Basic Life Support (BLS)", "cap": 2, "eq": "BLS", "lat": 13.6120, "lng": 79.4050, "driver": "B. Suresh", "phone": "+91 94401 22006"},
]

DEMO_HOSPITALS = [
    {
        "name": "SVIMS Super Specialty Hospital & Medical Institute",
        "type": "Government Apex Hospital",
        "lat": 13.6420,
        "lng": 79.4130,
        "address": "Alipiri Road, Tirupati, Andhra Pradesh",
        "phone": "+91 877 2287777",
        "specialties": ["cardiac", "stroke", "trauma", "icu", "emergency", "neurosurgery"],
        "icu_beds": 14,
        "er_beds": 28,
        "gen_beds": 120,
    },
    {
        "name": "BIRRD Orthopedic Trauma & Rehabilitation Hospital",
        "type": "Specialized Trauma Center",
        "lat": 13.6405,
        "lng": 79.4350,
        "address": "Near Balaji Colony, Tirupati",
        "phone": "+91 877 2286666",
        "specialties": ["trauma", "orthopedics", "emergency", "burns"],
        "icu_beds": 8,
        "er_beds": 18,
        "gen_beds": 85,
    },
    {
        "name": "Sri Padmavathi Multi-Specialty Medical Center",
        "type": "Regional Emergency Care",
        "lat": 13.6550,
        "lng": 79.4220,
        "address": "Bypass Road, Tirupati",
        "phone": "+91 877 2285555",
        "specialties": ["emergency", "general", "pediatrics", "toxicology"],
        "icu_beds": 6,
        "er_beds": 12,
        "gen_beds": 60,
    },
]


@router.post("/demo-simulation/load")
async def load_emergency_simulation(
    db=Depends(get_db),
    user=Depends(roles("operator", "admin")),
):
    """Seeds the reproducible 5-incident research demonstration scenario into database."""
    now_dt = datetime.now(timezone.utc)
    org = db.scalar(select(Organization).order_by(Organization.created_at).limit(1))
    if not org:
        org = Organization(name="Andhra Emergency Response 112")
        db.add(org)
        db.flush()

    # 1. Upsert Demonstration Hospitals
    created_hospitals = []
    for h_data in DEMO_HOSPITALS:
        h = db.scalar(select(Hospital).where(Hospital.name == h_data["name"]))
        if not h:
            h = Hospital(
                organization_id=org.id,
                name=h_data["name"],
                hospital_type=h_data["type"],
                latitude=h_data["lat"],
                longitude=h_data["lng"],
                address=h_data["address"],
                city="Tirupati",
                state="Andhra Pradesh",
                emergency_phone=h_data["phone"],
                specialties=h_data["specialties"],
                operating_status="Operational",
                verification_status="approved",
                diversion_status=False,
            )
            db.add(h)
            db.flush()

            # Create default Emergency Department
            dept = Department(hospital_id=h.id, name="Emergency & Trauma Unit", dept_type="emergency")
            db.add(dept)
            db.flush()

            # Add Capacities
            db.add(Capacity(department_id=dept.id, kind="icu", total=h_data["icu_beds"], occupied=3, reserved=1))
            db.add(Capacity(department_id=dept.id, kind="emergency", total=h_data["er_beds"], occupied=5, reserved=2))
            db.add(Capacity(department_id=dept.id, kind="general", total=h_data["gen_beds"], occupied=40, reserved=5))
            db.flush()
        created_hospitals.append(h)

    # 2. Upsert Demonstration Ambulances
    created_ambs = []
    for amb_data in DEMO_AMBULANCES:
        amb = db.scalar(select(Ambulance).where(Ambulance.registration == amb_data["reg"]))
        if not amb:
            amb = Ambulance(
                organization_id=org.id,
                registration=amb_data["reg"],
                driver_name=amb_data["driver"],
                driver_phone=amb_data["phone"],
                vehicle_type=amb_data["type"],
                patient_capacity=amb_data["cap"],
                equipment_level=amb_data["eq"],
                current_latitude=amb_data["lat"],
                current_longitude=amb_data["lng"],
                current_speed=0.0,
                active=True,
            )
            db.add(amb)
            db.flush()
        else:
            # Reset demo ambulance position and status
            amb.current_latitude = amb_data["lat"]
            amb.current_longitude = amb_data["lng"]
            amb.patient_capacity = amb_data["cap"]
            amb.active = True
        created_ambs.append(amb)

    # 3. Create Demonstration Incidents (A through E)
    created_incidents = []
    base_case_prefix = f"DEMO-{now_dt.strftime('%H%M')}"

    for inc_data in DEMO_SCENARIO_INCIDENTS:
        case_id = f"{base_case_prefix}-{inc_data['code_suffix']}"
        existing = db.scalar(select(Incident).where(Incident.case_id == case_id))
        if existing:
            created_incidents.append(existing)
            continue

        created_time = now_dt - timedelta(minutes=inc_data["reported_offset_min"])
        inc = Incident(
            case_id=case_id,
            tracking_hash=uuid.uuid4().hex,
            organization_id=org.id,
            category=inc_data["category"],
            description=inc_data["description"],
            address=inc_data["address"],
            latitude=inc_data["latitude"],
            longitude=inc_data["longitude"],
            status="reported",
            priority=inc_data["priority"],
            casualties_count=inc_data["casualties_count"],
            citizen_contact="+91 91211 08108",
            created_at=created_time,
            is_hoax=False,
        )
        db.add(inc)
        db.flush()

        # Calculate Priority Score dynamically
        p_res = calculate_incident_priority(inc, _CURRENT_WEIGHTS, now_dt)
        inc.priority_score = p_res["priority_score"]
        inc.priority_breakdown = p_res["contributions"]
        created_incidents.append(inc)

    db.commit()

    # 4. Run Optimization Engine on the newly seeded scenario
    allocation_res = await allocate_ambulances_to_incidents(
        incidents=created_incidents,
        ambulances=created_ambs,
        weights=_CURRENT_WEIGHTS,
        now_dt=now_dt,
    )

    return {
        "status": "success",
        "scenario_label": DEMO_TAG,
        "message": "Reproducible 5-incident demonstration scenario loaded successfully.",
        "incidents_count": len(created_incidents),
        "ambulances_count": len(created_ambs),
        "hospitals_count": len(created_hospitals),
        "ranked_queue": allocation_res["ranked_incident_queue"],
        "recommended_allocations": allocation_res["assignments"],
        "unallocated_count": allocation_res["unallocated_incidents_count"],
        "objective_cost_Z": allocation_res["objective_cost_Z"],
        "allocation_efficiency_pct": allocation_res["allocation_efficiency_pct"],
    }


@router.post("/demo-simulation/reset")
async def reset_emergency_simulation(
    db=Depends(get_db),
    user=Depends(roles("operator", "admin")),
):
    """Safely resets demonstration records (tagged with DEMO-) without modifying production data."""
    # Find demo incidents
    demo_incidents = db.scalars(select(Incident).where(Incident.case_id.like("DEMO-%"))).all()
    demo_ids = [i.id for i in demo_incidents]

    if demo_ids:
        # Delete dependent missions, referrals, events
        db.execute(delete(Referral).where(Referral.incident_id.in_(demo_ids)))
        db.execute(delete(Mission).where(Mission.incident_id.in_(demo_ids)))
        db.execute(delete(Incident).where(Incident.id.in_(demo_ids)))
        db.commit()

    return {
        "status": "success",
        "message": f"Cleared {len(demo_ids)} demonstration incident records successfully.",
    }
