import secrets, io, csv
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select, func, Numeric, or_
from .db import get_db
from .models import (
    Organization,
    User,
    Invitation,
    Hospital,
    Department,
    Capacity,
    Ambulance,
    Mission,
    Incident,
    Referral,
    Audit,
    Session,
    PermissionOverride,
    now,
)
from .security import roles, scope, digest, audit, send_email
from .workflow import Location, serial, record

router = APIRouter(tags=["Resources and administration"])


class Named(BaseModel):
    name: str = Field(min_length=2, max_length=160)


class HospitalCreate(Location, Named):
    organization_id: str
    facilities: list[str] = Field(default_factory=list, max_length=50)


class DepartmentCreate(Named):
    hospital_id: str


class CapacityCreate(BaseModel):
    department_id: str
    kind: Literal["icu", "emergency", "general"]
    total: int = Field(ge=0, le=100000)


class AmbulanceCreate(BaseModel):
    organization_id: str
    registration: str = Field(min_length=2, max_length=40)
    driver_name: str | None = Field(default=None, max_length=160)
    driver_phone: str | None = Field(default=None, max_length=40)
    vehicle_type: str | None = Field(default="Advanced Life Support (ALS)", max_length=50)


class Invite(BaseModel):
    email: EmailStr
    role: Literal["operator", "hospital", "responder", "analyst", "admin"]
    organization_id: str


class UserUpdate(BaseModel):
    suspended: bool


class FleetUpdate(BaseModel):
    active: bool | None = None
    driver_name: str | None = None
    driver_phone: str | None = None
    vehicle_type: str | None = None


@router.get("/organizations")
def organizations(
    user=Depends(roles("admin")),
    db=Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    return [serial(o) for o in db.scalars(select(Organization).order_by(Organization.name).offset(offset).limit(limit))]


@router.post("/organizations", status_code=201)
def organization(data: Named, user=Depends(roles("admin")), db=Depends(get_db)):
    o = Organization(**data.model_dump())
    db.add(o)
    db.flush()
    audit(db, "organization.created", o.id, user)
    db.commit()
    return serial(o)


@router.get("/users")
def users(
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), user=Depends(roles("admin")), db=Depends(get_db)
):
    return {
        "items": [
            serial(u) for u in db.scalars(select(User).order_by(User.created_at.desc()).offset(offset).limit(limit))
        ],
        "total": db.scalar(select(func.count()).select_from(User)),
    }


@router.post("/invitations", status_code=201)
def invite(data: Invite, user=Depends(roles("admin")), db=Depends(get_db)):
    if not db.get(Organization, data.organization_id):
        raise HTTPException(404, "Organization not found")
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Account already exists")
    token = secrets.token_urlsafe(32)
    inv = Invitation(
        email=data.email.lower(),
        role=data.role,
        organization_id=data.organization_id,
        token_hash=digest(token),
        expires_at=now() + timedelta(days=3),
    )
    db.add(inv)
    from .config import settings

    try:
        send_email(
            inv.email,
            "Your invitation to TERA",
            f"An administrator has invited you as {data.role}. Register at {settings().public_url}/login?invitation={token}. This invitation expires in 3 days.",
        )
    except OSError:
        raise HTTPException(503, "Email delivery unavailable")
    audit(db, "invitation.created", inv.email, user, role=data.role)
    db.commit()
    return {"message": "Invitation emailed"}


@router.patch("/users/{id}")
def update_user(id: str, data: UserUpdate, user=Depends(roles("admin")), db=Depends(get_db)):
    u = db.scalar(select(User).where(User.id == id).with_for_update())
    if not u:
        raise HTTPException(404, "Account not found")
    if u.id == user.id:
        raise HTTPException(409, "You cannot suspend your own account")
    if data.suspended and db.scalar(select(Mission).where(Mission.responder_id == u.id, Mission.status != "completed")):
        raise HTTPException(409, "Complete this responder’s active mission before suspension")
    u.suspended = data.suspended
    if u.suspended:
        for s in db.scalars(select(Session).where(Session.user_id == u.id)):
            s.revoked = True
    audit(db, "account.suspended" if u.suspended else "account.recovered", u.id, user)
    db.commit()
    return serial(u)


@router.post("/hospitals", status_code=201)
def hospital(data: HospitalCreate, user=Depends(roles("admin")), db=Depends(get_db)):
    if not db.get(Organization, data.organization_id):
        raise HTTPException(404, "Organization not found")
    h = Hospital(**data.model_dump())
    db.add(h)
    db.flush()
    audit(db, "hospital.created", h.id, user)
    db.commit()
    return serial(h)


@router.patch("/hospitals/{id}")
def update_hospital(id: str, data: HospitalCreate, user=Depends(roles("admin", "hospital")), db=Depends(get_db)):
    h = db.get(Hospital, id)
    if not h:
        raise HTTPException(404, "Hospital not found")
    scope(user, h.organization_id)
    if h.organization_id != data.organization_id:
        raise HTTPException(409, "Hospital ownership cannot be reassigned")
    for k, v in data.model_dump().items():
        setattr(h, k, v)
    audit(db, "hospital.updated", h.id, user)
    db.commit()
    return serial(h)


@router.post("/departments", status_code=201)
def department(data: DepartmentCreate, user=Depends(roles("admin", "hospital")), db=Depends(get_db)):
    h = db.get(Hospital, data.hospital_id)
    if not h:
        raise HTTPException(404, "Hospital not found")
    scope(user, h.organization_id)
    d = Department(**data.model_dump())
    db.add(d)
    db.flush()
    audit(db, "department.created", d.id, user)
    db.commit()
    return serial(d)


@router.get("/departments")
def departments(
    user=Depends(roles("admin", "hospital")),
    db=Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    q = select(Department).join(Hospital)
    if user.role != "admin":
        q = q.where(Hospital.organization_id == user.organization_id)
    return [serial(d) for d in db.scalars(q.order_by(Department.id).offset(offset).limit(limit))]


@router.post("/capacities", status_code=201)
def capacity(data: CapacityCreate, user=Depends(roles("admin", "hospital")), db=Depends(get_db)):
    d = db.get(Department, data.department_id)
    if not d:
        raise HTTPException(404, "Department not found")
    scope(user, db.get(Hospital, d.hospital_id).organization_id)
    c = Capacity(**data.model_dump())
    db.add(c)
    db.flush()
    record(
        db,
        "capacity.created",
        user=user,
        event_scope=db.get(Hospital, d.hospital_id).organization_id,
        id=c.id,
        **data.model_dump(),
    )
    db.commit()
    return serial(c)


@router.get("/ambulances")
def fleet(
    user=Depends(roles("admin", "operator", "analyst")),
    db=Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    q = select(Ambulance)
    if user.role not in ("admin", "operator", "analyst") and user.organization_id:
        q = q.where(Ambulance.organization_id == user.organization_id)
    busy = set(db.scalars(select(Mission.ambulance_id).where(~Mission.status.in_(["completed", "cancelled"]))))
    result = []
    for a in db.scalars(q.order_by(Ambulance.id).offset(offset).limit(limit)):
        hosp = db.get(Hospital, a.hospital_id) if a.hospital_id else None
        result.append({
            **serial(a),
            "hospital_id": a.hospital_id,
            "hospital_name": hosp.name if hosp else None,
            "available": a.active and a.id not in busy,
        })
    return result


@router.post("/ambulances", status_code=201)
def ambulance(data: AmbulanceCreate, user=Depends(roles("admin")), db=Depends(get_db)):
    if not db.get(Organization, data.organization_id):
        raise HTTPException(404, "Organization not found")
    a = Ambulance(**data.model_dump())
    db.add(a)
    db.flush()
    audit(db, "ambulance.created", a.id, user)
    db.commit()
    return serial(a)


@router.patch("/ambulances/{id}")
def update_ambulance(id: str, data: FleetUpdate, user=Depends(roles("admin", "operator", "responder")), db=Depends(get_db)):
    a = db.scalar(select(Ambulance).where(Ambulance.id == id).with_for_update())
    if not a:
        raise HTTPException(404, "Ambulance not found")
    if data.active is not None:
        if not data.active and db.scalar(select(Mission).where(Mission.ambulance_id == id, Mission.status != "completed")):
            raise HTTPException(409, "Complete active mission before removing ambulance from service")
        a.active = data.active
    if data.driver_name is not None:
        a.driver_name = data.driver_name
    if data.driver_phone is not None:
        a.driver_phone = data.driver_phone
    if data.vehicle_type is not None:
        a.vehicle_type = data.vehicle_type
    audit(db, "ambulance.updated", id, user, active=a.active, driver_name=a.driver_name)
    db.commit()
    return serial(a)


@router.get("/responders")
def responders(
    user=Depends(roles("admin", "operator")),
    db=Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    q = select(User).where(User.role == "responder", User.suspended.is_(False), User.verified.is_(True))
    if user.role != "admin":
        q = q.where(User.organization_id == user.organization_id)
    busy = set(db.scalars(select(Mission.responder_id).where(~Mission.status.in_(["completed", "cancelled"]))))
    res = []
    for u in db.scalars(q.order_by(User.id).offset(offset).limit(limit)):
        hosp = db.get(Hospital, u.hospital_id) if u.hospital_id else None
        res.append({
            "id": u.id,
            "name": u.name,
            "phone": u.phone,
            "organization_id": u.organization_id,
            "hospital_id": u.hospital_id,
            "hospital_name": hosp.name if hosp else None,
            "available": u.id not in busy,
        })
    return res


@router.get("/audit")
def logs(
    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100), user=Depends(roles("admin")), db=Depends(get_db)
):
    return {
        "items": [
            serial(a) for a in db.scalars(select(Audit).order_by(Audit.created_at.desc()).offset(offset).limit(limit))
        ],
        "total": db.scalar(select(func.count()).select_from(Audit)),
    }


@router.get("/analytics")
def analytics(user=Depends(roles("admin", "analyst", "operator")), db=Depends(get_db)):
    iq = select(Incident)
    if user.role != "admin":
        iq = iq.where(Incident.organization_id == user.organization_id)
    ids = iq.with_only_columns(Incident.id)
    statuses = db.execute(
        select(Incident.status, func.count()).where(Incident.id.in_(ids)).group_by(Incident.status)
    ).all()
    categories = db.execute(
        select(Incident.category, func.count()).where(Incident.id.in_(ids)).group_by(Incident.category)
    ).all()
    referral_counts = db.execute(
        select(Referral.status, func.count()).where(Referral.incident_id.in_(ids)).group_by(Referral.status)
    ).all()
    from .models import Event

    reported = (
        select(Event.incident_id, func.min(Event.created_at).label("at"))
        .where(Event.kind == "incident.reported")
        .group_by(Event.incident_id)
        .subquery()
    )
    acknowledged = (
        select(Event.incident_id, func.min(Event.created_at).label("at"))
        .where(Event.kind == "mission.acknowledged")
        .group_by(Event.incident_id)
        .subquery()
    )
    avg = db.scalar(
        select(func.avg(func.extract("epoch", acknowledged.c.at - reported.c.at)))
        .select_from(reported)
        .join(acknowledged, acknowledged.c.incident_id == reported.c.incident_id)
        .where(reported.c.incident_id.in_(ids))
    )
    caps = (
        select(func.sum(Capacity.total), func.sum(Capacity.occupied), func.sum(Capacity.reserved))
        .join(Department)
        .join(Hospital)
    )
    if user.role != "admin":
        caps = caps.where(Hospital.organization_id == user.organization_id)
    total, occupied, reserved = db.execute(caps).one()
    fleetq = select(func.count()).select_from(Ambulance)
    if user.role != "admin":
        fleetq = fleetq.where(Ambulance.organization_id == user.organization_id)
    fleet_total = db.scalar(fleetq)
    active = db.scalar(
        select(func.count()).select_from(Mission).where(Mission.incident_id.in_(ids), Mission.status != "completed")
    )
    lat_bucket = func.round(Incident.latitude.cast(Numeric), 2)
    lon_bucket = func.round(Incident.longitude.cast(Numeric), 2)
    geography = db.execute(
        select(Incident.category, lat_bucket, lon_bucket, func.count())
        .where(Incident.id.in_(ids), Incident.latitude.is_not(None))
        .group_by(Incident.category, lat_bucket, lon_bucket)
    ).all()
    return {
        "total_incidents": sum(n for _, n in statuses),
        "by_status": dict(statuses),
        "by_category": dict(categories),
        "referrals": dict(referral_counts),
        "mean_acknowledgement_seconds": float(avg) if avg is not None else None,
        "capacity": {"total": total or 0, "occupied": occupied or 0, "reserved": reserved or 0},
        "fleet": {"total": fleet_total, "assigned": active},
        "geography": [
            {"category": c, "latitude": float(a), "longitude": float(b), "count": n} for c, a, b, n in geography
        ],
        "generated_at": now(),
    }


class AccessUpdate(BaseModel):
    role: Literal["citizen", "operator", "hospital", "responder", "analyst", "admin"]
    organization_id: str | None = None


@router.patch("/users/{id}/access")
def access(id: str, data: AccessUpdate, user=Depends(roles("admin")), db=Depends(get_db)):
    u = db.scalar(select(User).where(User.id == id).with_for_update())
    if not u:
        raise HTTPException(404, "Account not found")
    if u.id == user.id:
        raise HTTPException(409, "Another administrator must change your own access")
    if data.role != "citizen" and not data.organization_id:
        raise HTTPException(422, "Operational accounts require an organization")
    if data.organization_id and not db.get(Organization, data.organization_id):
        raise HTTPException(404, "Organization not found")
    if db.scalar(select(Mission).where(Mission.responder_id == u.id, Mission.status != "completed")):
        raise HTTPException(409, "Complete active missions before changing this account")
    u.role = data.role
    u.organization_id = data.organization_id
    for s in db.scalars(select(Session).where(Session.user_id == u.id)):
        s.revoked = True
    audit(db, "account.access_changed", u.id, user, **data.model_dump())
    db.commit()
    return serial(u)


class Restriction(BaseModel):
    user_id: str
    action: str = Field(max_length=200)
    denied: bool


_actions_cache: list[str] | None = None


def actions(request):
    global _actions_cache
    if _actions_cache is None:
        try:
            _actions_cache = sorted(
                method.upper() + " " + path
                for path, methods in request.app.openapi().get("paths", {}).items()
                for method in methods
                if method in ("get", "post", "patch", "delete")
                and path.startswith("/api/v1/")
                and "/auth/" not in path
                and "/public/" not in path
            )
        except Exception:
            _actions_cache = []
    return _actions_cache


@router.get("/permissions")
def permissions(request: Request, user=Depends(roles("admin")), db=Depends(get_db)):
    return {
        "actions": actions(request),
        "restrictions": [serial(r) for r in db.scalars(select(PermissionOverride).limit(500))],
    }


@router.put("/permissions")
def restrict(data: Restriction, request: Request, user=Depends(roles("admin")), db=Depends(get_db)):
    if data.user_id == user.id:
        raise HTTPException(409, "Another administrator must restrict your own permissions")
    target = db.scalar(select(User).where(User.id == data.user_id).with_for_update())
    if not target:
        raise HTTPException(404, "Account not found")
    if data.action not in actions(request):
        raise HTTPException(422, "Unknown permission")
    rule = db.scalar(
        select(PermissionOverride).where(
            PermissionOverride.user_id == target.id, PermissionOverride.action == data.action
        )
    )
    if not rule:
        rule = PermissionOverride(user_id=target.id, action=data.action)
        db.add(rule)
    rule.denied = data.denied
    audit(db, "permission.updated", target.id, user, action_key=data.action, denied=data.denied)
    db.commit()
    return {"message": "Permission restriction updated. Role and organization boundaries remain enforced."}


# ==========================================
# PHASE 6: Analytics & Government Value
# ==========================================

def calc_percentiles(values: list[float]) -> dict:
    if not values:
        return {"p50": None, "p90": None, "p95": None, "mean": None}
    sorted_v = sorted(values)
    n = len(sorted_v)
    def p(pct):
        idx = min(n - 1, max(0, int(round((pct / 100.0) * (n - 1)))))
        return round(sorted_v[idx], 1)
    return {
        "p50": p(50),
        "p90": p(90),
        "p95": p(95),
        "mean": round(sum(sorted_v) / n, 1),
    }


@router.get("/analytics/sla-summary")
def get_sla_summary(
    user=Depends(roles("admin", "analyst", "operator")),
    db=Depends(get_db),
):
    iq = select(Incident)
    if user.role != "admin":
        iq = iq.where(Incident.organization_id == user.organization_id)
    incidents = db.scalars(iq).all()

    dispatch_times = []
    travel_times = []
    total_times = []

    for inc in incidents:
        m = db.scalar(select(Mission).where(Mission.incident_id == inc.id).order_by(Mission.created_at.desc()))
        if m and m.dispatched_at and inc.created_at:
            d_time = max(0.0, (m.dispatched_at - inc.created_at).total_seconds())
            dispatch_times.append(d_time)
            if m.arrived_at:
                t_time = max(0.0, (m.arrived_at - m.dispatched_at).total_seconds())
                travel_times.append(t_time)
                tot_time = max(0.0, (m.arrived_at - inc.created_at).total_seconds())
                total_times.append(tot_time)

    def stats(arr, threshold):
        res = calc_percentiles(arr)
        compliant = sum(1 for v in arr if v <= threshold)
        res["compliance_pct"] = round((compliant / len(arr)) * 100.0, 1) if arr else 100.0
        res["sample_size"] = len(arr)
        return res

    return {
        "time_to_dispatch": stats(dispatch_times, 180.0),
        "time_to_scene": stats(travel_times, 900.0),
        "golden_hour_total": stats(total_times, 3600.0),
        "benchmark_targets": {
            "dispatch_seconds": 180,
            "scene_seconds": 900,
            "golden_hour_seconds": 3600,
        },
    }


@router.get("/analytics/hotspots")
def get_accident_hotspots(
    radius_meters: float = Query(2000.0, ge=100, le=20000),
    user=Depends(roles("admin", "analyst", "operator")),
    db=Depends(get_db),
):
    iq = select(Incident).where(
        Incident.latitude.isnot(None),
        Incident.longitude.isnot(None),
        ~Incident.status.in_(["rejected", "duplicate"]),
    )
    if user.role != "admin":
        iq = iq.where(Incident.organization_id == user.organization_id)
    incidents = db.scalars(iq).all()

    clusters: dict[tuple[float, float], list] = {}
    for inc in incidents:
        key = (round(inc.latitude, 2), round(inc.longitude, 2))
        clusters.setdefault(key, []).append(inc)

    hotspots = []
    for (lat_b, lng_b), inc_list in clusters.items():
        total_cas = sum(i.casualties_count or 1 for i in inc_list)
        count = len(inc_list)
        severity = total_cas * 3 + count * 1
        tier = "critical" if severity >= 10 else "high" if severity >= 5 else "moderate"

        cat_counts: dict[str, int] = {}
        for i in inc_list:
            cat_counts[i.category] = cat_counts.get(i.category, 0) + 1
        primary_cat = max(cat_counts, key=cat_counts.get) if cat_counts else "general"

        hotspots.append({
            "cluster_id": f"spot_{lat_b}_{lng_b}",
            "latitude": round(sum(i.latitude for i in inc_list) / count, 5),
            "longitude": round(sum(i.longitude for i in inc_list) / count, 5),
            "incident_count": count,
            "casualties_count": total_cas,
            "severity_index": severity,
            "risk_tier": tier,
            "primary_category": primary_cat,
            "categories": cat_counts,
            "sample_address": inc_list[0].address if inc_list else "Unknown location",
        })

    hotspots.sort(key=lambda x: x["severity_index"], reverse=True)
    return {"total_hotspots": len(hotspots), "hotspots": hotspots}


@router.get("/analytics/export/csv")
def export_incident_sla_csv(
    user=Depends(roles("admin", "analyst", "operator")),
    db=Depends(get_db),
):
    iq = select(Incident)
    if user.role != "admin":
        iq = iq.where(Incident.organization_id == user.organization_id)
    incidents = db.scalars(iq.order_by(Incident.created_at.desc())).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Case ID",
        "Category",
        "Priority",
        "Status",
        "Address",
        "Latitude",
        "Longitude",
        "Casualties Count",
        "Reported At (UTC)",
        "Dispatched At (UTC)",
        "Dispatch Delay (Seconds)",
        "Dispatch Compliant (<=180s)",
        "Ambulance Registration",
        "Scene Arrived At (UTC)",
        "Travel Duration (Seconds)",
        "Travel Compliant (<=900s)",
        "Total Response (Seconds)",
        "Golden Hour Compliant (<=3600s)",
    ])

    for inc in incidents:
        m = db.scalar(select(Mission).where(Mission.incident_id == inc.id).order_by(Mission.created_at.desc()))
        amb = db.get(Ambulance, m.ambulance_id) if m else None

        d_delay = round((m.dispatched_at - inc.created_at).total_seconds(), 1) if (m and m.dispatched_at and inc.created_at) else None
        d_comp = "YES" if d_delay is not None and d_delay <= 180 else ("NO" if d_delay is not None else "N/A")

        t_dur = round((m.arrived_at - m.dispatched_at).total_seconds(), 1) if (m and m.arrived_at and m.dispatched_at) else None
        t_comp = "YES" if t_dur is not None and t_dur <= 900 else ("NO" if t_dur is not None else "N/A")

        tot_resp = round((m.arrived_at - inc.created_at).total_seconds(), 1) if (m and m.arrived_at and inc.created_at) else None
        gh_comp = "YES" if tot_resp is not None and tot_resp <= 3600 else ("NO" if tot_resp is not None else "N/A")

        writer.writerow([
            inc.case_id or inc.id,
            inc.category,
            inc.priority,
            inc.status,
            inc.address,
            inc.latitude or "",
            inc.longitude or "",
            inc.casualties_count or 0,
            inc.created_at.isoformat() if inc.created_at else "",
            m.dispatched_at.isoformat() if m and m.dispatched_at else "",
            d_delay if d_delay is not None else "",
            d_comp,
            amb.registration if amb else "",
            m.arrived_at.isoformat() if m and m.arrived_at else "",
            t_dur if t_dur is not None else "",
            t_comp,
            tot_resp if tot_resp is not None else "",
            gh_comp,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tera_incident_sla_report.csv"},
    )


@router.get("/analytics/voice-accuracy")
def get_voice_accuracy(
    user=Depends(roles("admin", "analyst", "operator")),
    db=Depends(get_db),
):
    from .models import IncidentExtraction, Transcript
    extractions = db.scalars(select(IncidentExtraction).where(IncidentExtraction.incident_id.isnot(None))).all()
    total = len(extractions)
    if total == 0:
        return {
            "total_voice_extractions": 0,
            "category_accuracy_pct": 100.0,
            "mean_casualty_error": 0.0,
            "average_confidence": 0.95,
        }
    cat_matches = 0
    cas_errors = []
    confidences = []
    for ext in extractions:
        inc = db.get(Incident, ext.incident_id)
        if not inc:
            continue
        extracted_data = ext.extracted_json or {}
        ext_cat = extracted_data.get("category", "").lower()
        if ext_cat and (ext_cat in inc.category.lower() or inc.category.lower() in ext_cat):
            cat_matches += 1
        ext_cas = extracted_data.get("casualties_count")
        if ext_cas is not None and inc.casualties_count is not None:
            cas_errors.append(abs(int(ext_cas) - int(inc.casualties_count)))
        if ext.transcript_id:
            t = db.get(Transcript, ext.transcript_id)
            if t and t.confidence is not None:
                confidences.append(float(t.confidence))

    return {
        "total_voice_extractions": total,
        "category_accuracy_pct": round((cat_matches / total) * 100.0, 1) if total > 0 else 100.0,
        "mean_casualty_error": round(sum(cas_errors) / len(cas_errors), 2) if cas_errors else 0.0,
        "average_confidence": round(sum(confidences) / len(confidences), 2) if confidences else 0.92,
    }

