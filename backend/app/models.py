import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    String,
    Text,
    ForeignKey,
    DateTime,
    Integer,
    Float,
    Boolean,
    JSON,
    CheckConstraint,
    UniqueConstraint,
    Index,
    text,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from .db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc)


class Identity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Organization(Identity, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(160), unique=True)


class User(Identity, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    google_subject: Mapped[str | None] = mapped_column(String(255), unique=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    mfa_secret: Mapped[str | None] = mapped_column(Text)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_last_step: Mapped[int] = mapped_column(Integer, default=0)
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)

    membership: Mapped["Membership"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.membership is None:
            self.membership = Membership(role_id="citizen")

    @hybrid_property
    def role(self):
        return self.membership.role_id if self.membership else "citizen"

    @role.setter
    def role(self, value):
        if self.membership is None:
            self.membership = Membership(role_id=value)
        else:
            self.membership.role_id = value

    @role.expression
    def role(cls):
        return select(Membership.role_id).where(Membership.user_id == cls.id).scalar_subquery()

    @hybrid_property
    def organization_id(self):
        return self.membership.organization_id if self.membership else None

    @organization_id.setter
    def organization_id(self, value):
        if self.membership is None:
            self.membership = Membership(role_id="citizen", organization_id=value)
        else:
            self.membership.organization_id = value

    @organization_id.expression
    def organization_id(cls):
        return select(Membership.organization_id).where(Membership.user_id == cls.id).scalar_subquery()


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class Membership(Identity, Base):
    __tablename__ = "memberships"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    user: Mapped[User] = relationship(back_populates="membership")
    __table_args__ = (CheckConstraint("role_id = 'citizen' OR organization_id IS NOT NULL"),)


class Permission(Base):
    __tablename__ = "permissions"
    action: Mapped[str] = mapped_column(String(200), primary_key=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    action: Mapped[str] = mapped_column(ForeignKey("permissions.action"), primary_key=True)


class Session(Identity, Base):
    __tablename__ = "sessions"
    family_id: Mapped[str] = mapped_column(String(36), default=uid, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent: Mapped[str] = mapped_column(String(256), default="")


class Challenge(Identity, Base):
    __tablename__ = "challenges"
    email: Mapped[str] = mapped_column(String(254), index=True)
    purpose: Mapped[str] = mapped_column(String(20))
    secret_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class Invitation(Identity, Base):
    __tablename__ = "invitations"
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(24))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class Incident(Identity, Base):
    __tablename__ = "incidents"
    case_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    tracking_hash: Mapped[str] = mapped_column(String(64), unique=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(32))
    description: Mapped[str] = mapped_column(Text)
    address: Mapped[str] = mapped_column(String(500))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="reported", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="unassessed")
    duplicate_of: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"))
    detected_language: Mapped[str | None] = mapped_column(String(10), default="en", nullable=True)
    english_translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    casualties_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    injuries_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    vehicles_involved: Mapped[str | None] = mapped_column(String(255), nullable=True)
    immediate_hazards: Mapped[str | None] = mapped_column(String(255), nullable=True)
    requested_assistance: Mapped[str | None] = mapped_column(String(255), nullable=True)
    citizen_contact: Mapped[str | None] = mapped_column(String(160), nullable=True)
    ai_extraction: Mapped[dict] = mapped_column(JSON, default=dict)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    triage_summary: Mapped[dict | None] = mapped_column(JSON, default=dict)
    is_hoax: Mapped[bool] = mapped_column(Boolean, default=False)
    hoax_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    hoax_flagged_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority_breakdown: Mapped[dict | None] = mapped_column(JSON, default=dict)

    __table_args__ = (
        CheckConstraint("casualties_count >= 0", name="incident_casualties_nonnegative"),
        CheckConstraint("latitude BETWEEN -90 AND 90"),
        CheckConstraint("longitude BETWEEN -180 AND 180"),
        CheckConstraint(
            "status IN ('submitted','pending_verification','reported','verified','dispatched','en_route','on_scene','transporting','hospital_handover','handover','active','resolved','closed','rejected','duplicate')"
        ),
        CheckConstraint("priority IN ('unassessed','low','medium','high','critical')"),
    )


class IncidentStatusHistory(Identity, Base):
    __tablename__ = "incident_status_history"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    previous_status: Mapped[str] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Report(Identity, Base):
    __tablename__ = "reports"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text)


class Evidence(Identity, Base):
    __tablename__ = "evidence"
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), index=True)
    object_key: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)


class VoiceRecording(Identity, Base):
    __tablename__ = "voice_recordings"
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), index=True, nullable=True)
    reporter_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    storage_reference: Mapped[str] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255), default="recording.webm")
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    checksum: Mapped[str] = mapped_column(String(64))
    recording_status: Mapped[str] = mapped_column(String(24), default="uploaded")


class TranscriptionJob(Identity, Base):
    __tablename__ = "transcription_jobs"
    recording_id: Mapped[str] = mapped_column(ForeignKey("voice_recordings.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[str] = mapped_column(String(24), default="queued")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Transcript(Identity, Base):
    __tablename__ = "transcripts"
    recording_id: Mapped[str] = mapped_column(ForeignKey("voice_recordings.id"), unique=True)
    original_transcript: Mapped[str] = mapped_column(Text)
    corrected_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_language: Mapped[str] = mapped_column(String(10), default="en")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider: Mapped[str] = mapped_column(String(50))
    provider_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class IncidentExtraction(Identity, Base):
    __tablename__ = "incident_extractions"
    recording_id: Mapped[str | None] = mapped_column(ForeignKey("voice_recordings.id"), index=True, nullable=True)
    transcript_id: Mapped[str | None] = mapped_column(ForeignKey("transcripts.id"), index=True, nullable=True)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), index=True, nullable=True)
    extracted_json: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_status: Mapped[str] = mapped_column(String(24), default="extracted")
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Hospital(Identity, Base):
    __tablename__ = "hospitals"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    facilities: Mapped[list] = mapped_column(JSON, default=list)
    hospital_type: Mapped[str] = mapped_column(String(80), default="General Hospital")
    reg_identifier: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(100), default="India")
    contact_person: Mapped[str | None] = mapped_column(String(120))
    contact_designation: Mapped[str | None] = mapped_column(String(120))
    emergency_phone: Mapped[str | None] = mapped_column(String(40))
    operating_status: Mapped[str] = mapped_column(String(40), default="Operational")
    verification_status: Mapped[str] = mapped_column(String(40), default="approved")
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    capabilities: Mapped[list] = mapped_column(JSON, default=list)
    specialties: Mapped[list | None] = mapped_column(JSON, default=list)
    diversion_status: Mapped[bool] = mapped_column(Boolean, default=False)
    operating_hours: Mapped[str | None] = mapped_column(String(100), default="24/7 Emergency")
    last_capacity_update: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("latitude BETWEEN -90 AND 90"), CheckConstraint("longitude BETWEEN -180 AND 180"))


class Department(Identity, Base):
    __tablename__ = "departments"
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    dept_type: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="active")
    contact_number: Mapped[str | None] = mapped_column(String(40))
    head_name: Mapped[str | None] = mapped_column(String(120))
    operating_hours: Mapped[str | None] = mapped_column(String(80), default="24/7")
    __table_args__ = (UniqueConstraint("hospital_id", "name"),)


class Capacity(Identity, Base):
    __tablename__ = "capacities"
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"))
    kind: Mapped[str] = mapped_column(String(24))
    total: Mapped[int] = mapped_column(Integer, default=0)
    occupied: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)
    out_of_service: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("department_id", "kind"),
        CheckConstraint("total >= 0 AND occupied >= 0 AND reserved >= 0 AND out_of_service >= 0"),
    )


class CapacityHistory(Identity, Base):
    __tablename__ = "capacity_history"
    hospital_id: Mapped[str] = mapped_column(ForeignKey("hospitals.id"), index=True)
    capacity_id: Mapped[str] = mapped_column(ForeignKey("capacities.id"), index=True)
    previous_total: Mapped[int] = mapped_column(Integer, default=0)
    previous_occupied: Mapped[int] = mapped_column(Integer, default=0)
    previous_reserved: Mapped[int] = mapped_column(Integer, default=0)
    new_total: Mapped[int] = mapped_column(Integer, default=0)
    new_occupied: Mapped[int] = mapped_column(Integer, default=0)
    new_reserved: Mapped[int] = mapped_column(Integer, default=0)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(String(255))


class Patient(Identity, Base):
    __tablename__ = "patients"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="Unidentified Patient")
    triage_priority: Mapped[str] = mapped_column(String(24), default="immediate")
    age: Mapped[int | None] = mapped_column(Integer)
    gender: Mapped[str | None] = mapped_column(String(20))
    condition_summary: Mapped[str | None] = mapped_column(Text)
    requested_department: Mapped[str | None] = mapped_column(String(100))
    required_bed_category: Mapped[str | None] = mapped_column(String(40))
    assigned_hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id"))
    referral_id: Mapped[str | None] = mapped_column(ForeignKey("referrals.id"))
    arrival_status: Mapped[str] = mapped_column(String(40), default="pending")
    start_triage_color: Mapped[str | None] = mapped_column(String(20), default="red")


class Ambulance(Identity, Base):
    __tablename__ = "ambulances"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    hospital_id: Mapped[str | None] = mapped_column(ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    registration: Mapped[str] = mapped_column(String(40), unique=True)
    driver_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    vehicle_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default="Advanced Life Support (ALS)")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    patient_capacity: Mapped[int] = mapped_column(Integer, default=2)
    equipment_level: Mapped[str | None] = mapped_column(String(50), default="ALS")
    current_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_speed: Mapped[float | None] = mapped_column(Float, nullable=True)


class Mission(Identity, Base):
    __tablename__ = "missions"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    ambulance_id: Mapped[str] = mapped_column(ForeignKey("ambulances.id"))
    responder_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(24), default="assigned")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_eta_seconds: Mapped[int | None] = mapped_column(Integer)
    decision_distance_meters: Mapped[float | None] = mapped_column(Float)
    decision_route_polyline: Mapped[str | None] = mapped_column(Text)
    decision_routing_provider: Mapped[str | None] = mapped_column(String(50))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    telemetry_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    ranking_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ranking_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint(
            "status IN ('assigned','acknowledged','en_route','on_scene','transporting','handover','completed','cancelled')"
        ),
        Index("one_active_ambulance", "ambulance_id", unique=True, postgresql_where=text("status NOT IN ('completed', 'cancelled')")),
        Index("one_active_responder", "responder_id", unique=True, postgresql_where=text("status NOT IN ('completed', 'cancelled')")),
    )


class AmbulanceTelemetryHistory(Identity, Base):
    __tablename__ = "ambulance_telemetry_history"
    mission_id: Mapped[str] = mapped_column(ForeignKey("missions.id", ondelete="CASCADE"), index=True)
    ambulance_id: Mapped[str] = mapped_column(ForeignKey("ambulances.id", ondelete="CASCADE"), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (
        Index("ix_telemetry_mission_recorded", "mission_id", "recorded_at"),
    )


class DispatchRankingWeights(Identity, Base):
    __tablename__ = "dispatch_ranking_weights"
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    eta_weight: Mapped[float] = mapped_column(Float, default=0.40)
    capability_weight: Mapped[float] = mapped_column(Float, default=0.30)
    readiness_weight: Mapped[float] = mapped_column(Float, default=0.20)
    workload_fairness_weight: Mapped[float] = mapped_column(Float, default=0.10)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    updated_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class Referral(Identity, Base):
    __tablename__ = "referrals"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"))
    capacity_id: Mapped[str] = mapped_column(ForeignKey("capacities.id"))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    reason: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str | None] = mapped_column(String(24), default="immediate")
    eta_minutes: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    decision_eta_seconds: Mapped[int | None] = mapped_column(Integer)
    decision_distance_meters: Mapped[float | None] = mapped_column(Float)
    decision_route_polyline: Mapped[str | None] = mapped_column(Text)
    decision_routing_provider: Mapped[str | None] = mapped_column(String(50))
    referred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted','rejected','arrived','handed_over')"),
    )


class ETAPredictionRecord(Identity, Base):
    __tablename__ = "eta_prediction_records"
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    target_type: Mapped[str] = mapped_column(String(20))  # mission, referral
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    origin_lat: Mapped[float] = mapped_column(Float)
    origin_lng: Mapped[float] = mapped_column(Float)
    dest_lat: Mapped[float] = mapped_column(Float)
    dest_lng: Mapped[float] = mapped_column(Float)
    predicted_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    predicted_distance_meters: Mapped[float] = mapped_column(Float)
    straight_line: Mapped[bool] = mapped_column(Boolean, default=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actual_arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    error_seconds: Mapped[int | None] = mapped_column(Integer)


class Reservation(Identity, Base):
    __tablename__ = "reservations"
    referral_id: Mapped[str] = mapped_column(ForeignKey("referrals.id"), unique=True)
    capacity_id: Mapped[str] = mapped_column(ForeignKey("capacities.id"))
    status: Mapped[str] = mapped_column(String(24), default="reserved")
    __table_args__ = (CheckConstraint("status IN ('reserved','occupied')"),)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Audit(Identity, Base):
    __tablename__ = "audit_logs"
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"))
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str] = mapped_column(String(254))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class PermissionOverride(Identity, Base):
    __tablename__ = "permission_overrides"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(ForeignKey("permissions.action"))
    denied: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("user_id", "action"),)


# ==============================================================================
# TERA AI EMERGENCY FIRST-AID COMPANION & MEDICALLY REVIEWED KNOWLEDGE BASE
# ==============================================================================

class EmergencyKnowledgeSource(Identity, Base):
    __tablename__ = "emergency_knowledge_sources"
    name: Mapped[str] = mapped_column(String(200), unique=True)
    organization: Mapped[str] = mapped_column(String(200))
    citation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)


class EmergencyProtocol(Base):
    __tablename__ = "emergency_protocols"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    subtype: Mapped[str] = mapped_column(String(80))
    applicable_patient_group: Mapped[str] = mapped_column(String(40), default="all")
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    recognition_criteria: Mapped[dict] = mapped_column(JSON, default=list)
    immediate_danger_indicators: Mapped[dict] = mapped_column(JSON, default=list)
    assessment_questions: Mapped[dict] = mapped_column(JSON, default=list)
    contraindications: Mapped[dict] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    trusted_source_id: Mapped[str | None] = mapped_column(ForeignKey("emergency_knowledge_sources.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'in_review', 'approved', 'retired')"),
    )


class EmergencyProtocolVersion(Identity, Base):
    __tablename__ = "emergency_protocol_versions"
    protocol_id: Mapped[str] = mapped_column(ForeignKey("emergency_protocols.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    change_summary: Mapped[str] = mapped_column(Text, default="Initial version")
    medical_approval_status: Mapped[str] = mapped_column(String(24), default="draft")
    approved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("protocol_id", "version_number"),
        CheckConstraint("medical_approval_status IN ('draft', 'in_review', 'approved', 'rejected', 'retired')"),
    )


class EmergencyProtocolStep(Identity, Base):
    __tablename__ = "emergency_protocol_steps"
    version_id: Mapped[str] = mapped_column(ForeignKey("emergency_protocol_versions.id", ondelete="CASCADE"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    instruction_title: Mapped[str] = mapped_column(String(200))
    instruction_text: Mapped[str] = mapped_column(Text)
    expected_action: Mapped[str] = mapped_column(Text)
    danger_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_trigger: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("version_id", "step_number"),
    )


class EmergencyProtocolTranslation(Identity, Base):
    __tablename__ = "emergency_protocol_translations"
    version_id: Mapped[str] = mapped_column(ForeignKey("emergency_protocol_versions.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("emergency_protocol_steps.id", ondelete="CASCADE"), nullable=True)
    language: Mapped[str] = mapped_column(String(10), index=True)  # en, te, hi, ta, kn, ml
    translated_title: Mapped[str] = mapped_column(String(200))
    translated_instruction: Mapped[str] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    medical_review_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("version_id", "step_id", "language"),
        CheckConstraint("language IN ('en', 'te', 'hi', 'ta', 'kn', 'ml')"),
    )


class EmergencyProtocolReview(Identity, Base):
    __tablename__ = "emergency_protocol_reviews"
    version_id: Mapped[str] = mapped_column(ForeignKey("emergency_protocol_versions.id", ondelete="CASCADE"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    reviewer_medical_qualification: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(String(32))
    comments: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("decision IN ('approved', 'rejected', 'revisions_requested')"),
    )


class EmergencyAssistanceSession(Identity, Base):
    __tablename__ = "emergency_assistance_sessions"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    citizen_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="connecting", index=True)
    channel: Mapped[str] = mapped_column(String(24), default="web_voice")
    selected_language: Mapped[str] = mapped_column(String(10), default="en")
    current_protocol_id: Mapped[str | None] = mapped_column(ForeignKey("emergency_protocols.id"), nullable=True)
    current_version_id: Mapped[str | None] = mapped_column(ForeignKey("emergency_protocol_versions.id"), nullable=True)
    current_step_id: Mapped[str | None] = mapped_column(ForeignKey("emergency_protocol_steps.id"), nullable=True)
    current_step_number: Mapped[int] = mapped_column(Integer, default=0)
    sarvam_session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sarvam_call_attempt_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    human_operator_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('idle', 'connecting', 'initial_assessment', 'guidance_active', "
            "'awaiting_citizen_response', 'reassessment', 'escalation_required', "
            "'human_assistance_pending', 'human_takeover', 'professional_handover', "
            "'completed', 'disconnected', 'error')"
        ),
        CheckConstraint("channel IN ('web_voice', 'phone_call', 'web_text')"),
        CheckConstraint("selected_language IN ('en', 'te', 'hi', 'ta', 'kn', 'ml')"),
    )


class EmergencyConversationMessage(Identity, Base):
    __tablename__ = "emergency_conversation_messages"
    session_id: Mapped[str] = mapped_column(ForeignKey("emergency_assistance_sessions.id", ondelete="CASCADE"), index=True)
    speaker: Mapped[str] = mapped_column(String(20))  # ai, citizen, operator, system
    language: Mapped[str] = mapped_column(String(10), default="en")
    content: Mapped[str] = mapped_column(Text)
    audio_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("speaker IN ('ai', 'citizen', 'operator', 'system')"),
    )


class EmergencyAssistanceAction(Identity, Base):
    __tablename__ = "emergency_assistance_actions"
    session_id: Mapped[str] = mapped_column(ForeignKey("emergency_assistance_sessions.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str | None] = mapped_column(ForeignKey("emergency_protocol_steps.id"), nullable=True)
    step_number: Mapped[int] = mapped_column(Integer)
    instruction_delivered: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[str] = mapped_column(String(32), default="delivered", index=True)
    citizen_confirmation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivered', 'acknowledged', 'completed_by_citizen', "
            "'not_completed', 'uncertain', 'escalated')"
        ),
    )


class EmergencyConditionUpdate(Identity, Base):
    __tablename__ = "emergency_condition_updates"
    session_id: Mapped[str] = mapped_column(ForeignKey("emergency_assistance_sessions.id", ondelete="CASCADE"), index=True)
    reported_by: Mapped[str] = mapped_column(String(20))  # citizen, ai, operator
    condition_type: Mapped[str] = mapped_column(String(40))  # consciousness, breathing, bleeding, pain, movement
    description: Mapped[str] = mapped_column(Text)
    severity_change: Mapped[str | None] = mapped_column(String(20), nullable=True)  # worsened, stable, improved


class AIEscalationEvent(Identity, Base):
    __tablename__ = "ai_escalation_events"
    session_id: Mapped[str] = mapped_column(ForeignKey("emergency_assistance_sessions.id", ondelete="CASCADE"), index=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(Text)
    escalation_level: Mapped[str] = mapped_column(String(32), default="operator_alert")
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("escalation_level IN ('operator_alert', 'urgent_dispatch', 'human_takeover')"),
    )


class AIAssistanceConsent(Identity, Base):
    __tablename__ = "ai_assistance_consents"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    phone_number: Mapped[str] = mapped_column(String(32), index=True)
    callback_consented: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_disclosure_acknowledged: Mapped[bool] = mapped_column(Boolean, default=True)
    recording_consented: Mapped[bool] = mapped_column(Boolean, default=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AICallbackAttempt(Identity, Base):
    __tablename__ = "ai_callback_attempts"
    session_id: Mapped[str] = mapped_column(ForeignKey("emergency_assistance_sessions.id", ondelete="CASCADE"), index=True)
    consent_id: Mapped[str] = mapped_column(ForeignKey("ai_assistance_consents.id", ondelete="CASCADE"), index=True)
    phone_number: Mapped[str] = mapped_column(String(32))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    provider: Mapped[str] = mapped_column(String(50), default="sarvam")
    provider_attempt_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'dialing', 'connected', 'no_answer', 'busy', 'failed', 'cancelled', 'completed')"
        ),
    )


class EmergencyHandover(Identity, Base):
    __tablename__ = "emergency_handovers"
    session_id: Mapped[str] = mapped_column(ForeignKey("emergency_assistance_sessions.id", ondelete="CASCADE"), unique=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    responder_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    summary_markdown: Mapped[str] = mapped_column(Text)
    actions_completed_count: Mapped[int] = mapped_column(Integer, default=0)
    actions_uncompleted_count: Mapped[int] = mapped_column(Integer, default=0)
    condition_at_handover: Mapped[str] = mapped_column(Text)
    protocols_used: Mapped[list] = mapped_column(JSON, default=list)
    verified_by_responder: Mapped[bool] = mapped_column(Boolean, default=False)
    handover_completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)



class RoleRequest(Identity, Base):
    __tablename__ = "role_requests"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    requested_role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="pending")


class OptimizationExecution(Identity, Base):
    __tablename__ = "optimization_executions"
    algorithm: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="completed")
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    output_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

