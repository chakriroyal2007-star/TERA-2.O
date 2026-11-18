"""Hospital Selection Optimization Engine.

Mathematical Formulation:
Hospital Cost = (w_time * Travel Time Score)
              + (w_bed  * Bed Availability Score)
              + (w_dept * Department Suitability Score)
              + (w_dem  * Incoming Demand Score)

Default decision-support weights:
- w_time: 0.35 (Travel Time / ETA)
- w_bed:  0.30 (Emergency & ICU Bed Availability)
- w_dept: 0.20 (Department / Specialty Suitability)
- w_dem:  0.15 (Incoming Referral Load / Occupancy Strain)
Lower Hospital Cost indicates an optimal patient transfer destination.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func
from app.models import Hospital, Department, Capacity, Referral, Incident
from .dijkstra import haversine_distance_meters

CATEGORY_DEPARTMENT_REQUIREMENTS = {
    "cardiac": {"specialties": ["cardiac", "cardiology", "icu"], "dept": "Cardiology"},
    "stroke": {"specialties": ["neurology", "neuro", "icu"], "dept": "Neurology"},
    "burns": {"specialties": ["burns", "plastic surgery", "icu"], "dept": "Burns & Trauma"},
    "trauma": {"specialties": ["trauma", "orthopedics", "emergency"], "dept": "Trauma & Ortho"},
    "road_traffic_accident": {"specialties": ["trauma", "emergency", "orthopedics"], "dept": "Emergency"},
    "neonatal": {"specialties": ["neonatal", "pediatrics", "nicu"], "dept": "Pediatrics"},
    "maternal": {"specialties": ["obstetrics", "gynecology"], "dept": "Obstetrics"},
    "toxicology": {"specialties": ["toxicology", "emergency", "icu"], "dept": "Critical Care"},
    "medical_emergency": {"specialties": ["emergency", "general"], "dept": "General Medicine"},
    "general": {"specialties": ["emergency", "general"], "dept": "Emergency"},
}


async def rank_hospitals_for_transfer(
    db,
    incident: Incident,
    limit: int = 3,
    custom_weights: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Calculates multi-factor hospital cost ranking for patient transfer."""
    w_time = (custom_weights or {}).get("travel_time_weight", 0.35)
    w_bed = (custom_weights or {}).get("bed_availability_weight", 0.30)
    w_dept = (custom_weights or {}).get("department_suitability_weight", 0.20)
    w_dem = (custom_weights or {}).get("incoming_demand_weight", 0.15)

    inc_lat = incident.latitude if incident.latitude is not None else 13.6288
    inc_lng = incident.longitude if incident.longitude is not None else 79.4192
    cat = (incident.category or "general").lower().strip()
    req_info = CATEGORY_DEPARTMENT_REQUIREMENTS.get(cat, CATEGORY_DEPARTMENT_REQUIREMENTS["general"])
    req_specs = [s.lower() for s in req_info["specialties"]]

    # Query operational registered hospitals
    hospitals = db.scalars(
        select(Hospital).where(
            Hospital.operating_status == "Operational",
            Hospital.latitude.isnot(None),
            Hospital.longitude.isnot(None),
        )
    ).all()

    eligible_ranked = []

    for h in hospitals:
        # Exclude hospitals currently on complete diversion
        if h.diversion_status:
            continue

        # 1. Available Beds & Occupancy
        cap_records = db.execute(
            select(Capacity.kind, Capacity.total, Capacity.occupied, Capacity.reserved)
            .join(Department, Department.id == Capacity.department_id)
            .where(Department.hospital_id == h.id)
        ).all()

        icu_free = 0
        er_free = 0
        gen_free = 0
        total_capacity = 0
        total_occupied = 0

        for kind, tot, occ, res in cap_records:
            free = max(0, tot - occ - res)
            total_capacity += tot
            total_occupied += occ + res
            if kind == "icu":
                icu_free += free
            elif kind == "emergency":
                er_free += free
            else:
                gen_free += free

        total_free_beds = icu_free + er_free + gen_free

        # Exclude hospital if zero emergency or ICU beds are available for critical patient
        if incident.priority in ("critical", "high") and (icu_free + er_free) <= 0:
            continue
        elif total_free_beds <= 0:
            continue

        # Bed Availability Score (Normalized 0 to 100, where 0 = abundant beds, 100 = 0 beds)
        # More available beds => lower cost
        bed_score = max(0.0, min(100.0, 100.0 - (total_free_beds * 10.0)))

        # 2. Travel Time / ETA Score
        dist_m = haversine_distance_meters(inc_lat, inc_lng, h.latitude, h.longitude)
        dist_km = round(dist_m / 1000.0, 2)
        eta_mins = round((dist_km / 42.0) * 60.0 + 1.0, 1)  # urban ambulance transit
        # 0 mins = 0, 40+ mins = 100
        travel_score = min(100.0, eta_mins * 2.5)

        # 3. Department Suitability Score (0 = perfect match, 50 = partial, 100 = missing)
        h_specs = [s.lower() for s in (h.specialties or [])]
        h_caps = [c.lower() for c in (h.capabilities or [])]
        combined_specs = set(h_specs + h_caps)

        matched = [s for s in req_specs if s in combined_specs]
        if matched:
            dept_score = round(max(0.0, 100.0 - (len(matched) / len(req_specs)) * 100.0), 1)
        else:
            dept_score = 65.0  # general emergency backup

        # 4. Incoming Referral Demand / Workload Score
        active_referrals = db.scalar(
            select(func.count(Referral.id))
            .join(Capacity, Capacity.id == Referral.capacity_id)
            .join(Department, Department.id == Capacity.department_id)
            .where(
                Department.hospital_id == h.id,
                Referral.status.in_(["pending", "accepted"]),
            )
        ) or 0
        # 0 referrals = 0 pts; +20 pts per incoming pending referral
        demand_score = min(100.0, active_referrals * 20.0)

        # Composite Hospital Cost (Lower Cost = Higher Recommendation)
        cost_time = round(travel_score * w_time, 2)
        cost_bed = round(bed_score * w_bed, 2)
        cost_dept = round(dept_score * w_dept, 2)
        cost_dem = round(demand_score * w_dem, 2)
        hospital_cost = round(cost_time + cost_bed + cost_dept + cost_dem, 2)

        # Recommendation confidence score (100 - cost)
        confidence_pct = round(max(10.0, min(99.0, 100.0 - hospital_cost)), 1)

        eligible_ranked.append({
            "hospital_id": h.id,
            "hospital_name": h.name,
            "hospital_type": h.hospital_type,
            "address": h.address,
            "city": h.city,
            "emergency_phone": h.emergency_phone or h.phone or "+91 877 2287777",
            "latitude": h.latitude,
            "longitude": h.longitude,
            "hospital_cost": hospital_cost,
            "recommendation_score": confidence_pct,
            "distance_km": dist_km,
            "eta_minutes": eta_mins,
            "available_beds": {
                "icu": icu_free,
                "emergency": er_free,
                "general": gen_free,
                "total": total_free_beds,
            },
            "incoming_referrals": active_referrals,
            "matched_specialties": matched,
            "score_breakdown": {
                "travel_time_score": travel_score,
                "travel_time_cost": cost_time,
                "bed_availability_score": bed_score,
                "bed_availability_cost": cost_bed,
                "department_suitability_score": dept_score,
                "department_suitability_cost": cost_dept,
                "incoming_demand_score": demand_score,
                "incoming_demand_cost": cost_dem,
            },
            "reasons": [
                f"Transport ETA: ~{eta_mins} mins ({dist_km} km)",
                f"{icu_free} ICU / {er_free} Emergency beds immediately ready",
                f"Specialty match: {', '.join(matched) if matched else 'General Trauma Coverage'}",
            ],
        })

    # Sort ascending by hospital cost (lowest cost = rank 1)
    eligible_ranked.sort(key=lambda x: x["hospital_cost"])

    for rank, item in enumerate(eligible_ranked, start=1):
        item["rank"] = rank

    return eligible_ranked[:limit]
