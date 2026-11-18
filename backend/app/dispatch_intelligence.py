"""Dispatch Intelligence & Advisory Smart-Matching Engine.

Calculates multi-factor transparent rankings for available ambulances and hospitals,
with human-readable explanation breakdowns, admin-tunable scoring weights,
and audited human operator override logging.
"""
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func, and_, or_
from app.models import (
    Incident,
    Ambulance,
    Hospital,
    Department,
    Capacity,
    Mission,
    Referral,
    User,
    DispatchRankingWeights,
)
from app.routing.service import RoutingService

logger = logging.getLogger(__name__)

# Category to required hospital specialties mapping
CATEGORY_SPECIALTY_MAP = {
    "road_traffic_accident": ["trauma", "emergency", "orthopedics"],
    "cardiac": ["cardiac", "icu", "emergency"],
    "stroke": ["neurology", "icu", "emergency"],
    "burns": ["burns", "trauma", "icu"],
    "neonatal": ["neonatal", "pediatrics", "icu"],
    "maternal": ["obstetrics", "gynecology", "emergency"],
    "toxicology": ["toxicology", "icu", "emergency"],
    "medical_emergency": ["emergency", "general"],
}


def get_active_weights(db, organization_id: Optional[str] = None) -> DispatchRankingWeights:
    """Returns the custom weights for the organization or standard default weights."""
    if organization_id:
        w = db.scalar(
            select(DispatchRankingWeights).where(DispatchRankingWeights.organization_id == organization_id)
        )
        if w:
            return w
    default_w = db.scalar(select(DispatchRankingWeights).where(DispatchRankingWeights.organization_id.is_(None)))
    if default_w:
        return default_w
    return DispatchRankingWeights(
        eta_weight=0.40,
        capability_weight=0.30,
        readiness_weight=0.20,
        workload_fairness_weight=0.10,
    )


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


async def rank_ambulances_for_incident(
    db,
    incident: Incident,
    available_ambulances: List[Ambulance],
    weights: Optional[DispatchRankingWeights] = None,
) -> List[Dict[str, Any]]:
    """Computes transparent advisory ranking for available ambulances."""
    if not weights:
        weights = get_active_weights(db, incident.organization_id)

    w_eta = weights.eta_weight
    w_cap = weights.capability_weight
    w_readiness = weights.readiness_weight
    w_fairness = weights.workload_fairness_weight

    inc_lat = incident.latitude or 12.8828
    inc_lng = incident.longitude or 77.6757
    is_high_acuity = incident.priority in ("critical", "high") or incident.category in ("cardiac", "stroke", "burns")

    routing_svc = RoutingService()
    now_dt = datetime.now(timezone.utc)
    results = []

    for amb in available_ambulances:
        # 1. Determine vehicle coordinates (from last active telemetry or mission, fallback to city hub)
        last_m = db.scalar(
            select(Mission)
            .where(Mission.ambulance_id == amb.id)
            .order_by(Mission.created_at.desc())
            .limit(1)
        )
        amb_lat = last_m.latitude if (last_m and last_m.latitude is not None) else 12.9716
        amb_lng = last_m.longitude if (last_m and last_m.longitude is not None) else 77.5946

        # 2. ETA Calculation
        try:
            route_res = await routing_svc.get_directions((amb_lat, amb_lng), (inc_lat, inc_lng))
            eta_seconds = route_res.duration_seconds
            distance_meters = route_res.distance_meters
            routing_provider = route_res.provider
        except Exception:
            dist_km = haversine_km(amb_lat, amb_lng, inc_lat, inc_lng)
            eta_seconds = int((dist_km / 40.0) * 3600)  # estimated 40 km/h in urban India
            distance_meters = dist_km * 1000.0
            routing_provider = "fallback_estimate"

        eta_minutes = round(eta_seconds / 60.0, 1)

        # ETA score: 0 to 100 (100 for immediate <2m, 0 for >35m)
        eta_score = max(0.0, min(100.0, 100.0 - (eta_minutes * 2.8)))

        # 3. Capability Match Score:
        # ALS ambulances preferred for high acuity; BLS fine for low/medium
        v_type = (amb.vehicle_type or "").lower()
        if is_high_acuity:
            if "advanced" in v_type or "als" in v_type or "icu" in v_type:
                cap_score = 100.0
                cap_reason = "Advanced Life Support (ALS) fully matches high-acuity incident"
            else:
                cap_score = 65.0
                cap_reason = "Basic Life Support (BLS) unit available (ALS preferred for high severity)"
        else:
            cap_score = 95.0
            cap_reason = "Vehicle classification satisfies triage requirements"

        # 4. Readiness & Shift Status:
        readiness_score = 100.0 if amb.active else 40.0

        # 5. Workload Fairness (time since last mission)
        fairness_score = 80.0
        if last_m and last_m.created_at:
            hours_since = (now_dt - last_m.created_at).total_seconds() / 3600.0
            fairness_score = min(100.0, 50.0 + (hours_since * 10.0))

        # Composite Score (0 - 100)
        total_score = round(
            (eta_score * w_eta)
            + (cap_score * w_cap)
            + (readiness_score * w_readiness)
            + (fairness_score * w_fairness),
            1,
        )

        results.append({
            "ambulance_id": amb.id,
            "registration": amb.registration,
            "driver_name": amb.driver_name,
            "driver_phone": amb.driver_phone,
            "vehicle_type": amb.vehicle_type or "Advanced Life Support (ALS)",
            "score": total_score,
            "eta_minutes": eta_minutes,
            "distance_km": round(distance_meters / 1000.0, 1),
            "routing_provider": routing_provider,
            "breakdown": {
                "eta_score": round(eta_score, 1),
                "capability_score": cap_score,
                "readiness_score": readiness_score,
                "fairness_score": round(fairness_score, 1),
            },
            "reasons": [
                f"Estimated arrival in ~{eta_minutes} min ({round(distance_meters / 1000.0, 1)} km)",
                cap_reason,
                f"Fleet pilot: {amb.driver_name or 'Assigned Crew'}",
            ],
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank

    return results


async def rank_hospitals_for_incident(
    db,
    incident: Incident,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Computes advisory ranking for destination hospitals matching specialty & beds."""
    inc_lat = incident.latitude or 12.8828
    inc_lng = incident.longitude or 77.6757
    req_specialties = CATEGORY_SPECIALTY_MAP.get(incident.category or "", ["emergency", "trauma"])
    routing_svc = RoutingService()

    # Query hospitals with coordinates
    hospitals = db.scalars(
        select(Hospital)
        .where(Hospital.latitude.is_not(None), Hospital.longitude.is_not(None))
    ).all()

    ranked = []
    for h in hospitals:
        # Check diversion status
        if h.diversion_status:
            continue

        # 1. Total available emergency and ICU capacity
        cap_records = db.execute(
            select(Capacity.kind, Capacity.total, Capacity.occupied, Capacity.reserved)
            .join(Department)
            .where(Department.hospital_id == h.id)
        ).all()

        total_avail_icu = 0
        total_avail_er = 0
        total_avail_gen = 0
        for kind, total, occ, res in cap_records:
            free = max(0, total - occ - res)
            if kind == "icu":
                total_avail_icu += free
            elif kind == "emergency":
                total_avail_er += free
            else:
                total_avail_gen += free

        total_free_beds = total_avail_icu + total_avail_er + total_avail_gen

        # 2. Specialty match score
        h_specs = [s.lower() for s in (h.specialties or [])]
        h_caps = [c.lower() for c in (h.capabilities or [])]
        all_specs = set(h_specs + h_caps)

        matched_specs = [s for s in req_specialties if s.lower() in all_specs]
        spec_match_ratio = len(matched_specs) / max(1, len(req_specialties))
        spec_score = spec_match_ratio * 100.0

        # 3. Travel distance / ETA
        dist_km = haversine_km(inc_lat, inc_lng, h.latitude, h.longitude)
        eta_minutes = round((dist_km / 45.0) * 60.0, 1)  # urban transport avg
        eta_score = max(0.0, min(100.0, 100.0 - (eta_minutes * 2.5)))

        # 4. Bed capacity score
        bed_score = min(100.0, total_free_beds * 15.0)

        # 5. Historical acceptance rate
        total_refs = db.scalar(
            select(func.count(Referral.id))
            .join(Capacity)
            .join(Department)
            .where(Department.hospital_id == h.id)
        ) or 0
        acc_refs = db.scalar(
            select(func.count(Referral.id))
            .join(Capacity)
            .join(Department)
            .where(Department.hospital_id == h.id, Referral.status.in_(["accepted", "handed_over"]))
        ) or 0
        acc_rate = (acc_refs / total_refs) if total_refs > 0 else 0.95
        acceptance_score = acc_rate * 100.0

        # Composite Hospital Score
        final_score = round(
            (spec_score * 0.35)
            + (eta_score * 0.35)
            + (bed_score * 0.20)
            + (acceptance_score * 0.10),
            1,
        )

        reasons = [
            f"~{eta_minutes} min transport ({dist_km} km)",
            f"{total_avail_icu} ICU / {total_avail_er} Emergency beds open",
        ]
        if matched_specs:
            reasons.append(f"Specialty capability: {', '.join(matched_specs)}")

        ranked.append({
            "hospital_id": h.id,
            "name": h.name,
            "hospital_type": h.hospital_type,
            "address": h.address,
            "city": h.city,
            "emergency_phone": h.emergency_phone,
            "latitude": h.latitude,
            "longitude": h.longitude,
            "score": final_score,
            "eta_minutes": eta_minutes,
            "distance_km": dist_km,
            "available_beds": {
                "icu": total_avail_icu,
                "emergency": total_avail_er,
                "general": total_avail_gen,
                "total": total_free_beds,
            },
            "specialties": h.specialties or [],
            "reasons": reasons,
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank

    return ranked[:limit]
