import secrets
from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select, func, Numeric
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


class Invite(BaseModel):
    email: EmailStr
    role: Literal["operator", "hospital", "responder", "analyst", "admin"]
    organization_id: str


class UserUpdate(BaseModel):
    suspended: bool


class FleetUpdate(BaseModel):
    active: bool


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
    if user.role != "admin":
        q = q.where(Ambulance.organization_id == user.organization_id)
    busy = set(db.scalars(select(Mission.ambulance_id).where(Mission.status != "completed")))
    return [
        {**serial(a), "available": a.active and a.id not in busy}
        for a in db.scalars(q.order_by(Ambulance.id).offset(offset).limit(limit))
    ]


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
def update_ambulance(id: str, data: FleetUpdate, user=Depends(roles("admin")), db=Depends(get_db)):
    a = db.scalar(select(Ambulance).where(Ambulance.id == id).with_for_update())
    if not a:
        raise HTTPException(404, "Ambulance not found")
    if not data.active and db.scalar(select(Mission).where(Mission.ambulance_id == id, Mission.status != "completed")):
        raise HTTPException(409, "Complete active mission before removing ambulance from service")
    a.active = data.active
    audit(db, "ambulance.updated", id, user, active=data.active)
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
    busy = set(db.scalars(select(Mission.responder_id).where(Mission.status != "completed")))
    return [
        {"id": u.id, "name": u.name, "organization_id": u.organization_id, "available": u.id not in busy}
        for u in db.scalars(q.order_by(User.id).offset(offset).limit(limit))
    ]


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
