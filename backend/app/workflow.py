import secrets, math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, func, or_, text
from .config import settings
from .db import get_db
from .models import (
    Incident,
    Report,
    Event,
    User,
    Ambulance,
    Mission,
    Hospital,
    Department,
    Capacity,
    CapacityHistory,
    Patient,
    Referral,
    Reservation,
    VoiceRecording,
    Transcript,
    IncidentExtraction,
    Evidence,
    IncidentStatusHistory,
    now,
)
from .security import roles, scope, digest, limited, audit

router = APIRouter(tags=["Emergency workflow"])
OPS = ("operator", "admin")
STAFF = ("operator", "admin", "hospital", "responder", "analyst")


def generate_case_id(db) -> str:
    year = now().year
    prefix = f"TERA-{year}-"
    import random
    import time

    # Fetch existing case_ids to guarantee absolute uniqueness across all distributed serverless instances
    existing = set(db.scalars(select(Incident.case_id).where(Incident.case_id.like(f"{prefix}%"))).all())

    for _ in range(100):
        val = random.randint(100000, 999999)
        candidate = f"{prefix}{val}"
        if candidate not in existing:
            return candidate

    return f"{prefix}{int(time.time() * 1000) % 1000000:06d}"


class Location(BaseModel):
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def paired(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Supply both coordinates or neither")
        return self


class IncidentCreate(Location):
    model_config = ConfigDict(str_strip_whitespace=True)
    category: Literal["medical", "road_collision", "fire", "disaster", "other"]
    description: str = Field(min_length=10, max_length=5000)
    address: str = Field(min_length=3, max_length=500)
    casualties_count: int | None = Field(default=None, ge=0, le=100000)
    injuries_description: str | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    detected_language: str | None = None
    english_translation: str | None = None
    vehicles_involved: str | None = None
    immediate_hazards: str | None = None
    requested_assistance: str | None = None
    citizen_contact: str | None = None
    recording_id: str | None = None
    corrected_transcript: str | None = Field(default=None, max_length=10000)
    confirmed_extraction: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=64)


class Note(BaseModel):
    text: str = Field(min_length=3, max_length=3000)


class Verify(BaseModel):
    priority: Literal["low", "medium", "high", "critical"]
    note: str = Field(min_length=3, max_length=1000)
    casualties_count: int | None = Field(default=None, ge=0, le=100000)


class Dispatch(BaseModel):
    ambulance_id: str
    responder_id: str


class Progress(BaseModel):
    status: Literal["acknowledged", "en_route", "on_scene", "transporting", "handover", "completed"]
    note: str = Field(default="", max_length=1000)


class ReferralCreate(BaseModel):
    capacity_id: str
    patient_id: str | None = None
    patient_name: str | None = None
    priority: str | None = "immediate"
    eta_minutes: int | None = Field(default=None, ge=0, le=10080)
    notes: str | None = None


class Decision(BaseModel):
    accept: bool
    reason: str = Field(min_length=3, max_length=1000)


class CapacityUpdate(BaseModel):
    total: int = Field(ge=0, le=100000)
    occupied: int = Field(ge=0, le=100000)
    out_of_service: int = Field(default=0, ge=0, le=100000)
    reason: str = Field(default="Capacity adjustment", min_length=3, max_length=255)


class HospitalOnboard(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    hospital_type: str = Field(default="General Hospital")
    reg_identifier: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str = Field(min_length=3, max_length=255)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    postal_code: str | None = None
    country: str = Field(default="India")
    latitude: float | None = None
    longitude: float | None = None
    contact_person: str | None = None
    contact_designation: str | None = None
    emergency_phone: str | None = None
    operating_status: str = Field(default="Operational")
    departments: list[dict] = Field(default_factory=list)
    capacities: list[dict] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    auto_approve: bool = Field(default=True)


class PatientCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(default="Unidentified Patient", min_length=1, max_length=120)
    triage_priority: str = Field(default="immediate")
    age: int | None = Field(default=None, ge=0, le=130)
    gender: str | None = None
    condition_summary: str | None = None
    requested_department: str | None = None
    required_bed_category: str | None = None


class Duplicate(BaseModel):
    duplicate_of: str
    note: str = Field(min_length=3, max_length=1000)


def serial(obj):
    result = {}
    for c in obj.__table__.columns:
        if c.name in ("tracking_hash", "password_hash", "google_subject", "mfa_secret", "mfa_last_step"):
            continue
        val = getattr(obj, c.name)
        if isinstance(val, datetime):
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc)
            val = val.isoformat()
        result[c.name] = val
    if isinstance(obj, User):
        result.update(role=obj.role, organization_id=obj.organization_id)
    return result


def record(db, event_kind, incident=None, user=None, event_scope=None, **payload):
    # Serialize event ID allocation through commit on Postgres; safe no-op on SQLite
    try:
        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(84637201)"))
    except Exception:
        pass
    db.add(
        Event(
            kind=event_kind,
            incident_id=incident.id if incident else None,
            organization_id=event_scope
            if event_scope is not None
            else (incident.organization_id if incident else (user.organization_id if user else None)),
            actor_id=user.id if user else None,
            payload=payload,
        )
    )
    audit(db, event_kind, incident.id if incident else payload.get("id", ""), user, **payload)


def get_incident(db, id, user=None, lock=False):
    norm = id.strip()
    q = select(Incident).where(
        or_(
            Incident.id == norm,
            Incident.case_id == norm.upper(),
        )
    )
    i = db.scalar(q.with_for_update() if lock else q)
    if not i:
        raise HTTPException(404, "Incident not found")
    if user and i.organization_id is None and user.role in OPS:
        return i
    if user and user.role == "responder":
        if not db.scalar(select(Mission.id).where(Mission.incident_id == i.id, Mission.responder_id == user.id)):
            raise HTTPException(404, "Incident not found")
    elif user and user.role == "hospital":
        found = db.scalar(
            select(Referral.id)
            .join(Capacity)
            .join(Department)
            .join(Hospital)
            .where(Referral.incident_id == i.id, Hospital.organization_id == user.organization_id)
        )
        if not found:
            raise HTTPException(404, "Incident not found")
    elif user:
        scope(user, i.organization_id)
    return i


def tracked(db, code: str):
    norm = code.strip()
    i = db.scalar(select(Incident).where(Incident.tracking_hash == digest(norm)))
    if not i:
        raise HTTPException(404, "Tracking code not found")
    return i


@router.post("/public/incidents", status_code=201)
@router.post("/incidents", status_code=201)
def report(data: IncidentCreate, request: Request, db=Depends(get_db)):
    limited("report:" + request.client.host, 300, 3600)

    # Idempotency check
    idem_key = data.idempotency_key or request.headers.get("Idempotency-Key") or request.headers.get("X-Idempotency-Key")
    if idem_key:
        if not 16 <= len(idem_key) <= 64:
            raise HTTPException(422, "Idempotency key must contain 16 to 64 characters")
        try:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": idem_key})
        except Exception:
            pass
        existing = db.scalar(select(Incident).where(Incident.idempotency_key == idem_key))
        if existing:
            return {
                "id": existing.id,
                "case_id": existing.case_id,
                "tracking_code": "TRK-" + digest("tracking:" + idem_key),
                "pdf_url": f"/api/v1/public/track/TRK-{digest('tracking:' + idem_key)}/report",
                "status": existing.status,
                "duplicate": True,
            }

    code = "TRK-" + (digest("tracking:" + idem_key) if idem_key else secrets.token_urlsafe(24))
    case_id = generate_case_id(db)

    i = Incident(
        case_id=case_id,
        idempotency_key=idem_key,
        tracking_hash=digest(code),
        category=data.category,
        description=data.description.strip(),
        address=data.address.strip(),
        latitude=data.latitude,
        longitude=data.longitude,
        status="reported",
        priority=data.severity or "unassessed",
        detected_language=data.detected_language or "en",
        english_translation=data.english_translation,
        casualties_count=data.casualties_count,
        injuries_description=data.injuries_description,
        vehicles_involved=data.vehicles_involved,
        immediate_hazards=data.immediate_hazards,
        requested_assistance=data.requested_assistance,
        citizen_contact=data.citizen_contact,
    )
    db.add(i)
    db.flush()

    if data.recording_id:
        rec = db.scalar(select(VoiceRecording).where(VoiceRecording.id == data.recording_id).with_for_update())
        if not rec or rec.incident_id is not None:
            raise HTTPException(409, "Recording is missing or already attached to a report")
        if rec:
            rec.incident_id = i.id
            rec.recording_status = "completed"
            ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == rec.id))
            if ext:
                ext.incident_id = i.id
                ext.user_confirmed = True
                if data.confirmed_extraction:
                    from .speech.extraction import ExtractedIncident
                    from pydantic import ValidationError
                    try:
                        confirmed = ExtractedIncident.model_validate({**ext.extracted_json, **data.confirmed_extraction})
                    except ValidationError:
                        raise HTTPException(422, "Please check the confirmed extraction fields")
                    if (data.casualties_count is not None and confirmed.total_people is not None
                            and data.casualties_count > confirmed.total_people - (confirmed.safe_people or 0)):
                        raise HTTPException(422, "Assistance count exceeds the people not confirmed safe. Correct it or leave it unknown.")
                    ext.extracted_json = {**ext.extracted_json, **confirmed.model_dump(),
                        "affected_people": data.casualties_count, "assistance_needed": data.casualties_count}
                if data.corrected_transcript:
                    tr = db.scalar(select(Transcript).where(Transcript.recording_id == rec.id))
                    if tr:
                        tr.corrected_transcript = data.corrected_transcript

    if data.evidence_ids:
        for eid in data.evidence_ids:
            ev = db.scalar(select(Evidence).where(Evidence.id == eid).with_for_update())
            if not ev or ev.incident_id is not None:
                raise HTTPException(409, "Evidence is missing or already attached to a report")
            ev.incident_id = i.id

    db.add(Report(incident_id=i.id, text=data.description))
    db.add(
        IncidentStatusHistory(
            incident_id=i.id,
            previous_status="",
            new_status=i.status,
            notes="Emergency incident reported",
        )
    )
    record(db, "incident.reported", i, case_id=case_id, category=i.category)

    try:
        from app.speech.report import generate_incident_pdf

        pdf_bytes = generate_incident_pdf(i)
        pdf_dir = Path(settings().recordings_dir) / "reports"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = pdf_dir / f"{case_id}.pdf"
        pdf_file.write_bytes(pdf_bytes)
        i.pdf_path = str(pdf_file)
    except Exception:
        pass

    db.commit()
    return {
        "id": i.id,
        "case_id": case_id,
        "tracking_code": code,
        "status": i.status,
        "pdf_url": f"/api/v1/public/track/{code}/report",
    }


@router.get("/public/track/{code}")
def track(code: str, request: Request, db=Depends(get_db)):
    limited("tracking:" + request.client.host, 120, 60)
    i = tracked(db, code)
    # Public capabilities expose milestones only, never patient, coordinates, personnel or internal notes.
    events = db.scalars(select(Event).where(Event.incident_id == i.id).order_by(Event.id))
    allowed = {
        "incident.reported",
        "incident.voice_reported",
        "incident.verified",
        "incident.acknowledged",
        "mission.assigned",
        "mission.acknowledged",
        "mission.en_route",
        "mission.on_scene",
        "mission.transporting",
        "mission.handover",
        "referral.handed_over",
        "incident.closed",
        "incident.resolved",
        "incident.duplicate",
    }
    def format_ts(dt):
        if not dt:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    return {
        "status": i.status,
        "created_at": format_ts(i.created_at),
        "timeline": [{"kind": e.kind, "at": format_ts(e.created_at)} for e in events if e.kind in allowed],
    }


@router.post("/public/track/{code}/notes")
def add_note(code: str, data: Note, request: Request, db=Depends(get_db)):
    limited("note:" + request.client.host, 20, 3600)
    i = tracked(db, code)
    if i.status in ("closed", "duplicate"):
        raise HTTPException(409, "This incident no longer accepts updates")
    db.add(Report(incident_id=i.id, text=data.text))
    record(db, "report.added", i)
    db.commit()
    return {"message": "Update received"}


@router.get("/incidents")
def incidents(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    user=Depends(roles(*STAFF)),
    db=Depends(get_db),
):
    q = select(Incident)
    if user.role == "responder":
        q = q.join(Mission).where(Mission.responder_id == user.id)
    elif user.role == "hospital":
        q = q.where(Incident.id.in_(
            select(Referral.incident_id).join(Capacity).join(Department).join(Hospital)
            .where(Hospital.organization_id == user.organization_id)
        ))
    elif user.role != "admin":
        q = q.where(
            or_(Incident.organization_id == user.organization_id, Incident.organization_id.is_(None))
            if user.role == "operator"
            else Incident.organization_id == user.organization_id
        )
    if status:
        q = q.where(Incident.status == status)
    count = db.scalar(select(func.count()).select_from(q.subquery()))
    return {
        "items": [serial(i) for i in db.scalars(q.order_by(Incident.created_at.desc()).offset(offset).limit(limit))],
        "total": count,
    }


@router.get("/incidents/{id}")
def detail(id: str, user=Depends(roles(*STAFF)), db=Depends(get_db)):
    i = get_incident(db, id, user)
    return {
        **serial(i),
        "reports": [
            serial(r) for r in db.scalars(select(Report).where(Report.incident_id == id).order_by(Report.created_at))
        ],
        "events": [serial(e) for e in db.scalars(select(Event).where(Event.incident_id == id).order_by(Event.id))],
    }


@router.post("/incidents/{id}/verify")
def verify(id: str, data: Verify, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    if i.status not in ("reported", "submitted", "pending_verification"):
        raise HTTPException(409, "Only reported incidents can be verified")
    if not user.organization_id:
        raise HTTPException(409, "An operational organization is required")
    old_status = i.status
    i.organization_id = user.organization_id
    i.status = "verified"
    i.priority = data.priority
    if data.casualties_count is not None:
        i.casualties_count = data.casualties_count
    db.add(
        IncidentStatusHistory(
            incident_id=i.id,
            previous_status=old_status,
            new_status="verified",
            actor_id=user.id,
            notes=data.note,
        )
    )
    record(db, "incident.verified", i, user, note=data.note, priority=data.priority)
    db.commit()
    return serial(i)


class StatusUpdate(BaseModel):
    status: Literal[
        "submitted",
        "pending_verification",
        "reported",
        "verified",
        "dispatched",
        "en_route",
        "on_scene",
        "transporting",
        "hospital_handover",
        "handover",
        "active",
        "resolved",
        "closed",
        "rejected",
        "duplicate",
    ]
    note: str = Field(default="", max_length=1000)


@router.post("/incidents/{id}/status")
def update_status(id: str, data: StatusUpdate, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    old_status = i.status
    if data.status in ("rejected", "duplicate") and not data.note.strip():
        raise HTTPException(422, "A mandatory reason note is required when rejecting or marking duplicate")
    i.status = data.status
    db.add(
        IncidentStatusHistory(
            incident_id=i.id,
            previous_status=old_status,
            new_status=i.status,
            actor_id=user.id,
            notes=data.note,
        )
    )
    record(db, f"incident.{data.status}", i, user, previous_status=old_status, note=data.note)
    db.commit()
    return serial(i)


@router.post("/incidents/{id}/acknowledge")
def acknowledge(id: str, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    old_status = i.status
    if i.status in ("closed", "rejected", "duplicate"):
        raise HTTPException(409, "Incident is closed")
    db.add(
        IncidentStatusHistory(
            incident_id=i.id,
            previous_status=old_status,
            new_status=old_status,
            actor_id=user.id,
            notes="Incident acknowledged by operator",
        )
    )
    record(db, "incident.acknowledged", i, user)
    db.commit()
    return {"message": "Incident acknowledged", "id": i.id, "status": i.status}


@router.post("/incidents/{id}/priority")
def prioritize(id: str, data: Verify, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    if i.status in ("reported", "closed", "duplicate"):
        raise HTTPException(409, "Incident must be open and verified")
    i.priority = data.priority
    record(db, "incident.escalated", i, user, **data.model_dump())
    db.commit()
    return serial(i)


@router.post("/incidents/{id}/duplicate")
def duplicate(id: str, data: Duplicate, user=Depends(roles(*OPS)), db=Depends(get_db)):
    if id == data.duplicate_of:
        raise HTTPException(422, "An incident cannot duplicate itself")
    i = get_incident(db, id, user, True)
    target = get_incident(db, data.duplicate_of, user)
    if i.status != "reported" or target.status in ("duplicate", "closed") or not target.organization_id:
        raise HTTPException(409, "Link an unverified report to an active verified incident")
    i.organization_id = target.organization_id
    i.duplicate_of = target.id
    i.status = "duplicate"
    record(db, "incident.duplicate", i, user, **data.model_dump())
    db.commit()
    return serial(i)


@router.post("/incidents/{id}/dispatch", status_code=201)
def dispatch(id: str, data: Dispatch, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    if i.status != "verified":
        raise HTTPException(409, "Verify the incident before dispatch")
    a = db.scalar(select(Ambulance).where(Ambulance.id == data.ambulance_id).with_for_update())
    r = db.scalar(select(User).where(User.id == data.responder_id).with_for_update())
    if not a or not a.active or not r or r.role != "responder" or r.suspended or not r.verified:
        raise HTTPException(422, "Select an active ambulance and verified responder")
    if a.organization_id != i.organization_id or r.organization_id != i.organization_id:
        raise HTTPException(404, "Resource not found")
    if db.scalar(
        select(Mission.id).where(
            Mission.status != "completed", or_(Mission.ambulance_id == a.id, Mission.responder_id == r.id)
        )
    ):
        raise HTTPException(409, "A selected resource is already assigned")
    m = Mission(incident_id=i.id, ambulance_id=a.id, responder_id=r.id)
    db.add(m)
    db.flush()
    i.status = "dispatched"
    record(db, "mission.assigned", i, user, mission_id=m.id)
    db.commit()
    return serial(m)


@router.get("/missions")
def missions(
    user=Depends(roles("operator", "admin", "responder", "analyst")),
    db=Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    q = select(Mission).join(Incident)
    if user.role == "responder":
        q = q.where(Mission.responder_id == user.id)
    elif user.role != "admin":
        q = q.where(Incident.organization_id == user.organization_id)
    return [serial(m) for m in db.scalars(q.order_by(Mission.created_at.desc()).offset(offset).limit(limit))]


@router.post("/missions/{id}/progress")
def progress(id: str, data: Progress, user=Depends(roles("responder")), db=Depends(get_db)):
    # Consistent lock order: incident, mission, referral, capacity.
    m = db.get(Mission, id)
    if not m or m.responder_id != user.id:
        raise HTTPException(404, "Mission not found")
    i = get_incident(db, m.incident_id, user, True)
    m = db.scalar(select(Mission).where(Mission.id == id).with_for_update().execution_options(populate_existing=True))
    order = ["assigned", "acknowledged", "en_route", "on_scene", "transporting", "handover", "completed"]
    if m.status == "completed" or order.index(data.status) != order.index(m.status) + 1:
        raise HTTPException(409, "Invalid mission transition")
    if data.status in ("transporting", "handover", "completed"):
        referral = db.scalar(
            select(Referral).where(Referral.incident_id == i.id, Referral.status.in_(["accepted", "handed_over"]))
        )
        if not referral:
            raise HTTPException(409, "An accepted hospital referral is required")
        if data.status == "completed" and referral.status != "handed_over":
            raise HTTPException(409, "Hospital must confirm patient handover first")
    m.status = data.status
    if data.status == "acknowledged":
        i.status = "active"
    if data.status == "handover":
        i.status = "handover"
    record(db, "mission." + data.status, i, user, note=data.note, mission_id=m.id)
    db.commit()
    return serial(m)


@router.post("/missions/{id}/location")
def location(id: str, data: Location, user=Depends(roles("responder")), db=Depends(get_db)):
    m = db.scalar(select(Mission).where(Mission.id == id).with_for_update())
    if not m or m.responder_id != user.id:
        raise HTTPException(404, "Mission not found")
    if m.status == "completed" or data.latitude is None:
        raise HTTPException(409, "An active mission and coordinates are required")
    m.latitude = data.latitude
    m.longitude = data.longitude
    m.location_at = now()
    record(db, "mission.location", db.get(Incident, m.incident_id), user, mission_id=m.id, **data.model_dump())
    db.commit()
    return serial(m)


def haversine(lat1, lon1, lat2, lon2):
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 4.5
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 1)


@router.get("/hospital/profile")
def hospital_profile(user=Depends(roles("hospital", "admin")), db=Depends(get_db)):
    h = db.scalar(select(Hospital).where(Hospital.organization_id == user.organization_id))
    if not h:
        return {"registered": False}
    depts = db.scalars(select(Department).where(Department.hospital_id == h.id).order_by(Department.name)).all()
    caps = db.execute(
        select(Capacity, Department.name)
        .join(Department)
        .where(Department.hospital_id == h.id)
        .order_by(Capacity.kind)
    ).all()
    history = db.scalars(
        select(CapacityHistory)
        .where(CapacityHistory.hospital_id == h.id)
        .order_by(CapacityHistory.created_at.desc())
        .limit(25)
    ).all()
    return {
        "registered": True,
        "hospital": {
            **serial(h),
            "departments": [serial(d) for d in depts],
            "capacities": [
                {
                    **serial(c),
                    "department": name,
                    "available": max(0, c.total - c.occupied - c.reserved - (c.out_of_service or 0)),
                }
                for c, name in caps
            ],
            "capacity_history": [serial(ch) for ch in history],
        },
    }


@router.post("/hospital/onboard")
def hospital_onboard(data: HospitalOnboard, user=Depends(roles("hospital", "admin")), db=Depends(get_db)):
    h = db.scalar(select(Hospital).where(Hospital.organization_id == user.organization_id))
    if not h:
        h = Hospital(
            organization_id=user.organization_id,
            name=data.name.strip(),
            hospital_type=data.hospital_type,
            reg_identifier=data.reg_identifier,
            phone=data.phone,
            email=data.email,
            address=data.address.strip(),
            city=data.city.strip(),
            state=data.state.strip(),
            postal_code=data.postal_code,
            country=data.country,
            latitude=data.latitude,
            longitude=data.longitude,
            contact_person=data.contact_person,
            contact_designation=data.contact_designation,
            emergency_phone=data.emergency_phone,
            operating_status=data.operating_status,
            verification_status="Approved" if data.auto_approve else "Submitted",
            capabilities=data.capabilities,
            facilities=data.capabilities,
            last_capacity_update=datetime.now(timezone.utc),
        )
        db.add(h)
        db.flush()
    else:
        h.name = data.name.strip()
        h.hospital_type = data.hospital_type
        h.reg_identifier = data.reg_identifier
        h.phone = data.phone
        h.email = data.email
        h.address = data.address.strip()
        h.city = data.city.strip()
        h.state = data.state.strip()
        h.postal_code = data.postal_code
        h.country = data.country
        h.latitude = data.latitude
        h.longitude = data.longitude
        h.contact_person = data.contact_person
        h.contact_designation = data.contact_designation
        h.emergency_phone = data.emergency_phone
        h.operating_status = data.operating_status
        h.capabilities = data.capabilities
        h.facilities = data.capabilities
        h.last_capacity_update = datetime.now(timezone.utc)

    dept_map = {}
    for d in data.departments:
        dname = d.get("name", "").strip()
        if not dname:
            continue
        dept = db.scalar(select(Department).where(Department.hospital_id == h.id, Department.name == dname))
        if not dept:
            dept = Department(
                hospital_id=h.id,
                name=dname,
                dept_type=d.get("dept_type", "Clinical"),
                status=d.get("status", "Active"),
                contact_number=d.get("contact_number"),
                head_name=d.get("head_name"),
                operating_hours=d.get("operating_hours", "24/7"),
            )
            db.add(dept)
            db.flush()
        else:
            dept.dept_type = d.get("dept_type", dept.dept_type)
            dept.status = d.get("status", dept.status)
            dept.contact_number = d.get("contact_number", dept.contact_number)
            dept.head_name = d.get("head_name", dept.head_name)
            dept.operating_hours = d.get("operating_hours", dept.operating_hours)
        dept_map[dname] = dept

    if not dept_map:
        emerg = Department(hospital_id=h.id, name="Emergency & Trauma", dept_type="Emergency", status="Active", operating_hours="24/7")
        db.add(emerg)
        db.flush()
        dept_map["Emergency & Trauma"] = emerg

    default_dept = next(iter(dept_map.values()))

    for c in data.capacities:
        kind = c.get("kind", "Emergency Bed").strip()
        dept_name = c.get("department")
        target_dept = dept_map.get(dept_name, default_dept)
        total = int(c.get("total", 0))
        occupied = int(c.get("occupied", 0))
        out_of_service = int(c.get("out_of_service", 0))

        cap = db.scalar(select(Capacity).where(Capacity.department_id == target_dept.id, Capacity.kind == kind))
        if not cap:
            cap = Capacity(
                department_id=target_dept.id,
                kind=kind,
                total=total,
                occupied=occupied,
                reserved=0,
                out_of_service=out_of_service,
            )
            db.add(cap)
            db.flush()
        else:
            cap.total = total
            cap.occupied = occupied
            cap.out_of_service = out_of_service

        db.add(
            CapacityHistory(
                hospital_id=h.id,
                capacity_id=cap.id,
                previous_total=0,
                previous_occupied=0,
                previous_reserved=0,
                new_total=total,
                new_occupied=occupied,
                new_reserved=0,
                updated_by_id=user.id,
                reason="Initial onboarding registration",
            )
        )

    record(db, "hospital.onboarded", user=user, event_scope=user.organization_id, hospital_id=h.id, name=h.name)
    db.commit()
    return {"registered": True, "hospital": serial(h)}


@router.get("/hospitals")
def hospitals(
    user=Depends(roles(*STAFF)), db=Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=100)
):
    q = select(Hospital)
    if user.role == "hospital":
        q = q.where(Hospital.organization_id == user.organization_id)
    result = []
    for h in db.scalars(q.order_by(Hospital.name).offset(offset).limit(limit)):
        caps = db.execute(
            select(Capacity, Department.name).join(Department).where(Department.hospital_id == h.id)
        ).all()
        result.append(
            {
                **serial(h),
                "capacities": [
                    {
                        **serial(c),
                        "department": name,
                        "available": max(0, c.total - c.occupied - c.reserved - (c.out_of_service or 0)),
                    }
                    for c, name in caps
                ],
            }
        )
    return result


@router.patch("/capacities/{id}")
def capacity(id: str, data: CapacityUpdate, user=Depends(roles("hospital", "admin")), db=Depends(get_db)):
    c = db.scalar(select(Capacity).where(Capacity.id == id).with_for_update())
    if not c:
        raise HTTPException(404, "Capacity not found")
    h = db.get(Hospital, db.get(Department, c.department_id).hospital_id)
    scope(user, h.organization_id)
    oos = data.out_of_service if data.out_of_service is not None else (c.out_of_service or 0)
    if data.occupied + c.reserved + oos > data.total:
        raise HTTPException(409, "Capacity cannot be less than occupied, reserved, and out-of-service beds")
    before = serial(c)
    prev_total, prev_occ, prev_res = c.total, c.occupied, c.reserved
    c.total = data.total
    c.occupied = data.occupied
    c.out_of_service = oos
    h.last_capacity_update = datetime.now(timezone.utc)
    db.add(
        CapacityHistory(
            hospital_id=h.id,
            capacity_id=c.id,
            previous_total=prev_total,
            previous_occupied=prev_occ,
            previous_reserved=prev_res,
            new_total=c.total,
            new_occupied=c.occupied,
            new_reserved=c.reserved,
            updated_by_id=user.id,
            reason=data.reason,
        )
    )
    record(
        db,
        "capacity.updated",
        user=user,
        event_scope=h.organization_id,
        id=c.id,
        before={k: before.get(k) for k in ("total", "occupied", "reserved", "out_of_service")},
        after=data.model_dump(),
        reason=data.reason,
    )
    db.commit()
    return {**serial(c), "available": max(0, c.total - c.occupied - c.reserved - (c.out_of_service or 0))}


@router.get("/incidents/{id}/patients")
def get_patients(id: str, user=Depends(roles(*STAFF)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    pts = db.scalars(select(Patient).where(Patient.incident_id == i.id).order_by(Patient.created_at)).all()
    if not pts:
        p = Patient(
            incident_id=i.id,
            name="Patient 1 (Primary Caller/Victim)",
            triage_priority="immediate" if i.priority in ("critical", "high") else ("delayed" if i.priority == "medium" else "minor"),
            condition_summary=f"Reported emergency: {i.category}. {getattr(i, 'description', '')}".strip(),
            requested_department="Emergency & Trauma",
            required_bed_category="Emergency Bed" if i.priority != "critical" else "ICU Bed",
            arrival_status="pending",
        )
        db.add(p)
        db.commit()
        pts = [p]
    return [serial(p) for p in pts]


@router.post("/incidents/{id}/patients", status_code=201)
def add_patient(id: str, data: PatientCreate, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    p = Patient(
        incident_id=i.id,
        name=data.name.strip(),
        triage_priority=data.triage_priority,
        age=data.age,
        gender=data.gender,
        condition_summary=data.condition_summary,
        requested_department=data.requested_department,
        required_bed_category=data.required_bed_category,
        arrival_status="pending",
    )
    db.add(p)
    db.flush()
    record(db, "patient.registered", i, user, patient_id=p.id)
    db.commit()
    return serial(p)


@router.get("/incidents/{id}/hospital-recommendations")
def hospital_recommendations(id: str, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user)
    hosps = db.scalars(
        select(Hospital)
        .where(Hospital.operating_status == "Operational")
        .order_by(Hospital.name)
    ).all()
    if not hosps:
        hosps = db.scalars(select(Hospital).order_by(Hospital.name)).all()

    recommendations = []
    category = (i.category or "").lower()

    required_caps = []
    if "road" in category or "trauma" in category or "collision" in category:
        required_caps = ["Trauma care", "Surgery", "Blood bank"]
    elif "cardiac" in category or "heart" in category:
        required_caps = ["Cardiac care", "ICU", "Ventilator"]
    elif "stroke" in category:
        required_caps = ["Stroke care", "ICU", "Neurology"]
    elif "burn" in category:
        required_caps = ["Burns treatment", "ICU"]
    elif "pediatric" in category or "child" in category:
        required_caps = ["Paediatric emergency care"]
    else:
        required_caps = ["Emergency trauma support", "ICU support"]

    for h in hosps:
        dist = haversine(i.latitude, i.longitude, h.latitude, h.longitude)
        caps = db.execute(
            select(Capacity, Department.name, Department.id)
            .join(Department)
            .where(Department.hospital_id == h.id)
        ).all()

        categories_available = []
        total_avail_beds = 0
        for c, dept_name, dept_id in caps:
            avail = max(0, c.total - c.occupied - c.reserved - (c.out_of_service or 0))
            total_avail_beds += avail
            categories_available.append({
                "capacity_id": c.id,
                "department_id": dept_id,
                "department": dept_name,
                "kind": c.kind,
                "available": avail,
                "total": c.total,
                "occupied": c.occupied,
                "reserved": c.reserved,
                "out_of_service": c.out_of_service or 0,
            })

        hosp_caps = h.capabilities or h.facilities or []
        if isinstance(hosp_caps, str):
            hosp_caps = [hosp_caps]

        matched_caps = [c for c in required_caps if any(c.lower() in str(hc).lower() for hc in hosp_caps)]

        score = 100
        score -= min(50, dist * 2)
        score += min(30, total_avail_beds * 3)
        score += len(matched_caps) * 10
        score = max(10, min(99, int(score)))

        eta = max(5, int(dist * 2.2 + 3))

        recommendations.append({
            "hospital_id": h.id,
            "name": h.name,
            "hospital_type": h.hospital_type or "General Hospital",
            "phone": h.phone or h.emergency_phone,
            "address": h.address,
            "city": h.city,
            "state": h.state,
            "distance_km": dist,
            "estimated_eta_minutes": eta,
            "score": score,
            "total_available_beds": total_avail_beds,
            "verification_status": h.verification_status or "Approved",
            "operating_status": h.operating_status or "Operational",
            "capabilities": hosp_caps,
            "matched_capabilities": matched_caps,
            "bed_options": categories_available,
        })

    recommendations.sort(key=lambda x: (x["score"], x["total_available_beds"]), reverse=True)
    return recommendations


def hospital_for(db, r):
    cap = db.get(Capacity, r.capacity_id)
    if cap:
        dept = db.get(Department, cap.department_id)
        if dept:
            return db.get(Hospital, dept.hospital_id)
    return None


@router.post("/incidents/{id}/referrals", status_code=201)
def refer(id: str, data: ReferralCreate, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    if i.status not in ("dispatched", "active", "verified"):
        raise HTTPException(409, "Verify incident and dispatch a mission before requesting a referral")
    c = db.get(Capacity, data.capacity_id)
    if not c:
        raise HTTPException(404, "Capacity not found")

    patient = None
    if data.patient_id:
        patient = db.get(Patient, data.patient_id)
        if not patient or patient.incident_id != i.id:
            raise HTTPException(404, "Patient does not belong to this incident")
    if not patient:
        patient = db.scalar(select(Patient).where(Patient.incident_id == id).order_by(Patient.created_at))

    if patient:
        dup = db.scalar(select(Referral).where(Referral.incident_id == id, Referral.patient_id == patient.id, Referral.status.in_(["pending", "accepted", "arrived"])))
        if dup:
            raise HTTPException(409, f"An active referral already exists for {patient.name}")
    else:
        dup = db.scalar(select(Referral).where(Referral.incident_id == id, Referral.status.in_(["pending", "accepted", "arrived"])))
        if dup:
            raise HTTPException(409, "An active referral already exists for this incident")

    h = hospital_for(db, type("RefObj", (), {"capacity_id": data.capacity_id}))
    r = Referral(
        incident_id=id,
        capacity_id=data.capacity_id,
        patient_id=patient.id if patient else None,
        priority=data.priority or "immediate",
        eta_minutes=data.eta_minutes or 15,
        notes=data.notes,
        status="pending",
    )
    db.add(r)
    db.flush()
    if patient and h:
        patient.assigned_hospital_id = h.id
        patient.referral_id = r.id
        patient.arrival_status = "pending"
    record(db, "referral.requested", i, user, referral_id=r.id, hospital_name=h.name if h else "", patient_name=patient.name if patient else "Primary Patient")
    db.commit()
    return serial(r)


@router.get("/referrals")
def referrals(
    user=Depends(roles("hospital", "operator", "admin", "analyst")),
    db=Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    q = select(Referral).join(Incident)
    if user.role == "hospital":
        q = q.join(Capacity).join(Department).join(Hospital).where(Hospital.organization_id == user.organization_id)
    elif user.role not in ("admin", "operator", "analyst"):
        q = q.where(Incident.organization_id == user.organization_id)

    refs = db.scalars(q.order_by(Referral.created_at.desc()).offset(offset).limit(limit)).all()
    out = []
    for r in refs:
        inc = db.get(Incident, r.incident_id)
        cap = db.get(Capacity, r.capacity_id)
        dept = db.get(Department, cap.department_id) if cap else None
        hosp = db.get(Hospital, dept.hospital_id) if dept else None
        pat = db.get(Patient, r.patient_id) if r.patient_id else None
        mission = db.scalar(select(Mission).where(Mission.incident_id == inc.id).order_by(Mission.created_at.desc())) if inc else None

        out.append({
            **serial(r),
            "incident_case_id": inc.case_id if inc else "N/A",
            "incident_category": inc.category if inc else "General Emergency",
            "incident_priority": inc.priority if inc else "high",
            "incident_location": inc.address or inc.city or "Dispatched Location",
            "patient_name": pat.name if pat else "Primary Emergency Patient",
            "patient_triage": pat.triage_priority if pat else (r.priority or "immediate"),
            "patient_condition": pat.condition_summary if pat else (getattr(inc, "description", "") or "Emergency arrival"),
            "department_name": dept.name if dept else "Emergency",
            "bed_kind": cap.kind if cap else "Emergency Bed",
            "hospital_name": hosp.name if hosp else "Receiving Hospital",
            "available_in_category": max(0, cap.total - cap.occupied - cap.reserved - (cap.out_of_service or 0)) if cap else 0,
            "mission_status": mission.status if mission else "dispatched",
            "eta_minutes": r.eta_minutes or 15,
        })
    return out


@router.post("/referrals/{id}/decision")
def decide(id: str, data: Decision, user=Depends(roles("hospital", "admin")), db=Depends(get_db)):
    r = db.scalar(select(Referral).where(Referral.id == id).with_for_update())
    if not r:
        raise HTTPException(404, "Referral not found")
    h = hospital_for(db, r)
    if h:
        scope(user, h.organization_id)
    if r.status != "pending":
        raise HTTPException(409, "Referral already reviewed")
    if data.accept:
        c = db.scalar(select(Capacity).where(Capacity.id == r.capacity_id).with_for_update())
        avail = c.total - c.occupied - c.reserved - (c.out_of_service or 0)
        if avail < 1:
            raise HTTPException(409, "No verified capacity available in this category")
        c.reserved += 1
        db.add(Reservation(referral_id=r.id, capacity_id=c.id))
        r.status = "accepted"
        if r.patient_id:
            pat = db.get(Patient, r.patient_id)
            if pat:
                pat.arrival_status = "accepted"
    else:
        r.status = "rejected"
        if r.patient_id:
            pat = db.get(Patient, r.patient_id)
            if pat:
                pat.arrival_status = "rejected"
    r.reason = data.reason
    record(db, "referral." + r.status, db.get(Incident, r.incident_id), user, referral_id=r.id, reason=data.reason)
    db.commit()
    return serial(r)


@router.post("/referrals/{id}/arrival")
def arrival(id: str, user=Depends(roles("hospital", "admin")), db=Depends(get_db)):
    r = db.scalar(select(Referral).where(Referral.id == id).with_for_update())
    if not r:
        raise HTTPException(404, "Referral not found")
    h = hospital_for(db, r)
    if h:
        scope(user, h.organization_id)
    if r.status != "accepted":
        raise HTTPException(409, "Referral must be accepted before recording arrival")
    r.status = "arrived"
    if r.patient_id:
        pat = db.get(Patient, r.patient_id)
        if pat:
            pat.arrival_status = "arrived"
    record(db, "referral.arrived", db.get(Incident, r.incident_id), user, referral_id=r.id)
    db.commit()
    return serial(r)


@router.post("/referrals/{id}/handover")
def handover(id: str, user=Depends(roles("hospital", "admin")), db=Depends(get_db)):
    r = db.get(Referral, id)
    if not r:
        raise HTTPException(404, "Referral not found")
    h = hospital_for(db, r)
    if h:
        scope(user, h.organization_id)
    i = db.scalar(select(Incident).where(Incident.id == r.incident_id).with_for_update())
    r = db.scalar(select(Referral).where(Referral.id == id).with_for_update().execution_options(populate_existing=True))
    if r.status not in ("accepted", "arrived"):
        raise HTTPException(409, "Referral must be accepted or arrived before handover")
    c = db.scalar(select(Capacity).where(Capacity.id == r.capacity_id).with_for_update())
    reservation = db.scalar(select(Reservation).where(Reservation.referral_id == r.id).with_for_update())
    if reservation and reservation.status != "occupied":
        c.reserved = max(0, c.reserved - 1)
        c.occupied += 1
        reservation.status = "occupied"
    elif not reservation:
        c.occupied += 1
    r.status = "handed_over"
    if r.patient_id:
        pat = db.get(Patient, r.patient_id)
        if pat:
            pat.arrival_status = "handed_over"
    record(db, "referral.handed_over", i, user, referral_id=r.id)
    db.commit()
    return serial(r)


@router.post("/admin/hospitals/{id}/verify")
def verify_hospital(id: str, action: str = Query(...), reason: str | None = None, user=Depends(roles("admin")), db=Depends(get_db)):
    h = db.scalar(select(Hospital).where(Hospital.id == id).with_for_update())
    if not h:
        raise HTTPException(404, "Hospital not found")
    if action == "approve":
        h.verification_status = "Approved"
        h.rejection_reason = None
    elif action == "reject":
        h.verification_status = "Rejected"
        h.rejection_reason = reason or "Information could not be verified"
    elif action == "suspend":
        h.verification_status = "Suspended"
        h.operating_status = "Suspended"
        h.rejection_reason = reason or "Temporarily suspended by administrator"
    db.commit()
    return serial(h)


@router.post("/incidents/{id}/close")
def close(id: str, data: Note, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user, True)
    m = db.scalar(select(Mission).where(Mission.incident_id == i.id))
    if i.status != "handover" or not m or m.status != "completed":
        raise HTTPException(409, "Complete the mission and hospital handover before closure")
    i.status = "closed"
    record(db, "incident.closed", i, user, note=data.text)
    db.commit()
    return serial(i)


def distance(a, b, c, d):
    p = math.pi / 180
    return (
        6371
        * 2
        * math.asin(
            min(
                1,
                math.sqrt(
                    math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2
                ),
            )
        )
    )


@router.get("/incidents/{id}/suggestions")
def suggestions(id: str, user=Depends(roles(*OPS)), db=Depends(get_db)):
    i = get_incident(db, id, user)
    duplicates = []
    nearby = []
    if i.latitude is not None:
        for other in db.scalars(
            select(Incident).where(
                Incident.id != id,
                Incident.category == i.category,
                Incident.created_at > now() - timedelta(hours=2),
                Incident.status.notin_(["closed", "duplicate"]),
                or_(Incident.organization_id == user.organization_id, Incident.organization_id.is_(None)),
            )
        ):
            if other.latitude is not None:
                km = distance(i.latitude, i.longitude, other.latitude, other.longitude)
                if km < 1:
                    duplicates.append(
                        {
                            "id": other.id,
                            "distance_km": round(km, 2),
                            "reason": "Same category, within 1 km, reported within 2 hours",
                        }
                    )
        for h in db.scalars(select(Hospital).where(Hospital.latitude.is_not(None))):
            available = (
                db.scalar(
                    select(func.sum(Capacity.total - Capacity.occupied - Capacity.reserved))
                    .join(Department)
                    .where(Department.hospital_id == h.id)
                )
                or 0
            )
            if available > 0:
                nearby.append(
                    {
                        "id": h.id,
                        "name": h.name,
                        "distance_km": round(distance(i.latitude, i.longitude, h.latitude, h.longitude), 2),
                        "available_beds": available,
                        "reason": "Straight-line distance and recorded capacity; suitability requires operator confirmation",
                    }
                )
    return {
        "possible_duplicates": duplicates,
        "hospitals": sorted(nearby, key=lambda h: h["distance_km"]),
        "delay_alert": i.status in ("reported", "verified") and i.created_at < now() - timedelta(minutes=10),
        "note": "Decision support only. No GPS estimates or medical decisions are generated.",
    }
