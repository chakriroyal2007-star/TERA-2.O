"""Dynamic Emergency Incident Priority Scoring Engine.

Mathematical formulation:
Priority Score = (w_sev * Severity Score) + (w_wait * Waiting Time Score)
                 + (w_pat * Patient Count Score) + (w_urg * Resource Urgency Score)

Default decision-support weights:
- w_sev:  0.40 (Severity)
- w_wait: 0.25 (Waiting Time)
- w_pat:  0.20 (Patient Count)
- w_urg:  0.15 (Resource Urgency)
Total = 1.00
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from app.models import Incident


@dataclass
class PriorityWeights:
    severity_weight: float = 0.40
    waiting_time_weight: float = 0.25
    patient_count_weight: float = 0.20
    resource_urgency_weight: float = 0.15

    def normalize(self) -> "PriorityWeights":
        total = (
            self.severity_weight
            + self.waiting_time_weight
            + self.patient_count_weight
            + self.resource_urgency_weight
        )
        if total <= 0:
            return PriorityWeights()
        return PriorityWeights(
            severity_weight=round(self.severity_weight / total, 3),
            waiting_time_weight=round(self.waiting_time_weight / total, 3),
            patient_count_weight=round(self.patient_count_weight / total, 3),
            resource_urgency_weight=round(self.resource_urgency_weight / total, 3),
        )


SEVERITY_SCALE: Dict[str, float] = {
    "critical": 100.0,
    "high": 75.0,
    "medium": 50.0,
    "moderate": 50.0,
    "low": 25.0,
    "minor": 25.0,
    "unassessed": 35.0,
}

URGENCY_SCALE: Dict[str, float] = {
    "cardiac": 100.0,
    "stroke": 100.0,
    "burns": 100.0,
    "trauma": 100.0,
    "neonatal": 95.0,
    "respiratory": 95.0,
    "road_traffic_accident": 85.0,
    "maternal": 85.0,
    "toxicology": 80.0,
    "medical_emergency": 60.0,
    "other": 40.0,
    "general": 40.0,
}


def calculate_severity_score(priority: Optional[str]) -> float:
    key = (priority or "unassessed").lower().strip()
    return SEVERITY_SCALE.get(key, 35.0)


def calculate_waiting_time_score(created_at: Optional[datetime], now_dt: Optional[datetime] = None) -> tuple[float, float]:
    """Computes waiting time in minutes and normalized waiting score (0 to 100)."""
    if not created_at:
        return 0.0, 0.0

    if not now_dt:
        now_dt = datetime.now(timezone.utc)

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    diff_seconds = max(0.0, (now_dt - created_at).total_seconds())
    waiting_minutes = round(diff_seconds / 60.0, 1)

    # 0 mins = 0 pts; linear increase +5 pts per min up to 20 mins (100 pts)
    score = min(100.0, round(waiting_minutes * 5.0, 1))
    return waiting_minutes, score


def calculate_patient_count_score(casualties_count: Optional[int]) -> tuple[int, float]:
    """Computes patient count and normalized patient score (0 to 100)."""
    patients = max(1, casualties_count or 1)
    # 1 patient = 25 pts, 2 = 50 pts, 3 = 75 pts, 4+ = 100 pts
    score = min(100.0, round(patients * 25.0, 1))
    return patients, score


def calculate_resource_urgency_score(category: Optional[str]) -> float:
    key = (category or "general").lower().strip()
    return URGENCY_SCALE.get(key, 50.0)


def calculate_incident_priority(
    incident: Incident,
    weights: Optional[PriorityWeights] = None,
    now_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Calculates research-based dynamic emergency priority score and transparent breakdown."""
    w = (weights or PriorityWeights()).normalize()

    # Raw normalized input scores (0 - 100)
    sev_score = calculate_severity_score(incident.priority)
    wait_minutes, wait_score = calculate_waiting_time_score(incident.created_at, now_dt)
    patients, pat_score = calculate_patient_count_score(incident.casualties_count)
    urg_score = calculate_resource_urgency_score(incident.category)

    # Weighted contributions
    sev_contrib = round(sev_score * w.severity_weight, 2)
    wait_contrib = round(wait_score * w.waiting_time_weight, 2)
    pat_contrib = round(pat_score * w.patient_count_weight, 2)
    urg_contrib = round(urg_score * w.resource_urgency_weight, 2)

    final_score = round(sev_contrib + wait_contrib + pat_contrib + urg_contrib, 2)

    tier = "critical" if final_score >= 80.0 else "high" if final_score >= 60.0 else "medium" if final_score >= 40.0 else "low"

    return {
        "incident_id": incident.id,
        "case_id": incident.case_id or incident.id[:8].upper(),
        "priority_score": final_score,
        "priority_tier": tier,
        "waiting_time_minutes": wait_minutes,
        "patient_count": patients,
        "severity": incident.priority or "unassessed",
        "category": incident.category,
        "contributions": {
            "severity_contribution": sev_contrib,
            "waiting_time_contribution": wait_contrib,
            "patient_count_contribution": pat_contrib,
            "resource_urgency_contribution": urg_contrib,
        },
        "raw_scores": {
            "severity_score": sev_score,
            "waiting_time_score": wait_score,
            "patient_count_score": pat_score,
            "resource_urgency_score": urg_score,
        },
        "weights": asdict(w),
    }
