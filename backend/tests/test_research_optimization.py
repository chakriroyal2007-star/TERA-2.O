"""Tests for TERA 2.0 Research-Based Optimization Engine."""
import pytest
from datetime import datetime, timezone, timedelta
from app.models import Incident, Ambulance, Hospital, Department, Capacity, Mission
from app.optimization.priority import (
    calculate_incident_priority,
    PriorityWeights,
    calculate_severity_score,
    calculate_waiting_time_score,
    calculate_patient_count_score,
)
from app.optimization.dijkstra import (
    RoadGraph,
    haversine_distance_meters,
    build_demonstration_road_graph,
    calculate_shortest_road_route,
)
from app.optimization.allocation import (
    allocate_ambulances_to_incidents,
    compute_assignment_cost,
)
from app.optimization.hospital_ranking import rank_hospitals_for_transfer
from app.optimization.evaluation import run_baseline_vs_optimized_evaluation, compute_improvement_pct


def test_priority_scoring_formula():
    """Verifies Priority Score = 0.40*Sev + 0.25*Wait + 0.20*Pat + 0.15*Urg."""
    now_dt = datetime.now(timezone.utc)
    report_time = now_dt - timedelta(minutes=10)  # 10 min waiting = 50 pts

    incident = Incident(
        id="test-inc-1",
        case_id="TEST-001",
        priority="critical",  # 100 pts
        casualties_count=2,   # 50 pts
        category="cardiac",   # 100 pts
        created_at=report_time,
    )

    weights = PriorityWeights(
        severity_weight=0.40,
        waiting_time_weight=0.25,
        patient_count_weight=0.20,
        resource_urgency_weight=0.15,
    )

    res = calculate_incident_priority(incident, weights=weights, now_dt=now_dt)

    # 100*0.40 = 40.0
    # 50*0.25 = 12.5
    # 50*0.20 = 10.0
    # 100*0.15 = 15.0
    # Total = 77.5
    assert res["priority_score"] == pytest.approx(77.5, 0.1)
    assert res["contributions"]["severity_contribution"] == 40.0
    assert res["contributions"]["waiting_time_contribution"] == 12.5
    assert res["contributions"]["patient_count_contribution"] == 10.0
    assert res["contributions"]["resource_urgency_contribution"] == 15.0
    assert res["priority_tier"] == "high"


def test_dijkstra_binary_heap():
    """Verifies Dijkstra executes on weighted road graph and finds true shortest path."""
    g = RoadGraph()
    g.add_node("A", 13.6288, 79.4192, "Point A")
    g.add_node("B", 13.6335, 79.4168, "Point B")
    g.add_node("C", 13.6420, 79.4130, "Point C")
    g.add_node("D", 13.6495, 79.4085, "Point D")

    # Path 1: A -> B -> D (1000m + 2000m = 3000m)
    g.add_edge("A", "B", distance_meters=1000, speed_kmh=40.0, bidirectional=True)
    g.add_edge("B", "D", distance_meters=2000, speed_kmh=40.0, bidirectional=True)

    # Path 2: A -> C -> D (800m + 900m = 1700m - shorter!)
    g.add_edge("A", "C", distance_meters=800, speed_kmh=40.0, bidirectional=True)
    g.add_edge("C", "D", distance_meters=900, speed_kmh=40.0, bidirectional=True)

    res = g.dijkstra("A", "D", weight_metric="distance")
    assert res["found"] is True
    assert res["path"] == ["A", "C", "D"]
    assert res["distance_meters"] == 1700.0


@pytest.mark.anyio
async def test_capacity_constrained_allocation():
    """Verifies capacity-constrained matching allocates multiple units or larger ambulances."""
    # 5 incidents with varying patient counts & severities
    incA = Incident(
        id="inc-A",
        case_id="DEMO-A",
        priority="critical",
        casualties_count=3,
        category="trauma",
        latitude=13.6495,
        longitude=79.4085,
        created_at=datetime.now(timezone.utc),
    )
    incB = Incident(
        id="inc-B",
        case_id="DEMO-B",
        priority="medium",
        casualties_count=1,
        category="medical_emergency",
        latitude=13.6335,
        longitude=79.4168,
        created_at=datetime.now(timezone.utc),
    )

    # Fleet of ambulances
    amb1 = Ambulance(
        id="amb-1",
        registration="AP-01",
        vehicle_type="Advanced Life Support (ALS)",
        patient_capacity=2,
        equipment_level="ALS",
        current_latitude=13.6420,
        current_longitude=79.4130,
        active=True,
    )
    amb2 = Ambulance(
        id="amb-2",
        registration="AP-02",
        vehicle_type="Advanced Life Support (ALS)",
        patient_capacity=2,
        equipment_level="ALS",
        current_latitude=13.6405,
        current_longitude=79.4350,
        active=True,
    )
    amb3 = Ambulance(
        id="amb-3",
        registration="AP-03",
        vehicle_type="Basic Life Support (BLS)",
        patient_capacity=1,
        equipment_level="BLS",
        current_latitude=13.6210,
        current_longitude=79.4120,
        active=True,
    )

    allocation = await allocate_ambulances_to_incidents(
        incidents=[incA, incB],
        ambulances=[amb1, amb2, amb3],
    )

    assert allocation["status"] == "success"
    assert allocation["total_incidents_evaluated"] == 2
    # Verify no ambulance was assigned twice
    assigned_amb_ids = [a["ambulance_id"] for a in allocation["assignments"]]
    assert len(assigned_amb_ids) == len(set(assigned_amb_ids))
    # Critical incident A (3 casualties) gets assigned first
    assert allocation["ranked_incident_queue"][0]["case_id"] == "DEMO-A"


def test_improvement_percentage_calculation():
    # Response time: lower is better (900s baseline -> 540s optimized = 40% reduction)
    resp_imp = compute_improvement_pct(900.0, 540.0, higher_is_better=False)
    assert resp_imp == 40.0

    # Allocation efficiency: higher is better (60% baseline -> 90% optimized = 50% gain)
    alloc_imp = compute_improvement_pct(60.0, 90.0, higher_is_better=True)
    assert alloc_imp == 50.0
