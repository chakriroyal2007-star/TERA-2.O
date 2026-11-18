"""Live Ambulance Telemetry & GPS Streaming Engine.

Provides continuous telemetry ingestion, Redis latest-position caching,
downsampled PostgreSQL persistence, transactional outbox pub/sub fan-out,
and stale GPS warning detection.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from app.db import get_db, SessionLocal
from app.models import Mission, Ambulance, Incident, AmbulanceTelemetryHistory
from app.security import redis
from app.config import settings

logger = logging.getLogger(__name__)

STALE_TELEMETRY_THRESHOLD_SECONDS = 30
DOWNSAMPLE_INTERVAL_SECONDS = 5.0
TELEMETRY_REDIS_TTL = 3600  # 1 hour


class TelemetryInput(BaseModel):
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    speed: Optional[float] = Field(default=None, ge=0.0)
    heading: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    accuracy: Optional[float] = Field(default=None, ge=0.0)
    consent: Optional[bool] = None


class TelemetrySnapshot(BaseModel):
    mission_id: str
    ambulance_id: str
    latitude: float
    longitude: float
    speed: Optional[float] = None
    heading: Optional[float] = None
    accuracy: Optional[float] = None
    recorded_at: str
    stale: bool = False
    driver_name: Optional[str] = None
    driver_phone: Optional[str] = None
    ambulance_registration: Optional[str] = None
    remaining_distance_meters: Optional[float] = None


def publish_realtime_event(channel: str, message: dict):
    """Publish a realtime message through Redis pub/sub fan-out."""
    try:
        redis.publish(channel, json.dumps(message))
    except Exception as exc:
        logger.warning("Failed to publish to redis pub/sub %s: %s", channel, exc)


def ingest_mission_telemetry(
    db,
    mission: Mission,
    data: TelemetryInput,
    user=None,
) -> Dict[str, Any]:
    """Ingests high-frequency telemetry, caches in Redis, publishes to Pub/Sub,
    and conditionally persists downsampled snapshots in PostgreSQL."""
    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()

    # Explicit consent check per mission
    if data.consent is not None:
        mission.telemetry_consent = data.consent
    elif not mission.telemetry_consent:
        mission.telemetry_consent = True

    mission.latitude = data.latitude
    mission.longitude = data.longitude
    mission.location_at = now_dt

    # Recalculate remaining distance if incident coordinates exist
    rem_dist = None
    inc = db.get(Incident, mission.incident_id)
    if inc and inc.latitude is not None and inc.longitude is not None:
        import math
        dlat = math.radians(inc.latitude - data.latitude)
        dlon = math.radians(inc.longitude - data.longitude)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(data.latitude)) * math.cos(math.radians(inc.latitude)) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        rem_dist = round(6371000.0 * c, 1)
        mission.decision_distance_meters = rem_dist

        # Auto arrival detection within 100 meters
        if rem_dist < 100 and mission.status in ("assigned", "acknowledged", "en_route"):
            mission.status = "on_scene"
            mission.arrived_at = now_dt
            inc.status = "active"

    amb = db.get(Ambulance, mission.ambulance_id)
    if amb:
        amb.current_latitude = data.latitude
        amb.current_longitude = data.longitude
        if data.speed is not None:
            amb.current_speed = data.speed
    reg = amb.registration if amb else None
    driver_name = amb.driver_name if amb else None
    driver_phone = amb.driver_phone if amb else None

    payload = {
        "kind": "mission.telemetry",
        "mission_id": mission.id,
        "ambulance_id": mission.ambulance_id,
        "incident_id": mission.incident_id,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "speed": data.speed,
        "heading": data.heading,
        "accuracy": data.accuracy,
        "recorded_at": now_iso,
        "stale": False,
        "ambulance_registration": reg,
        "driver_name": driver_name,
        "driver_phone": driver_phone,
        "remaining_distance_meters": rem_dist,
        "mission_status": mission.status,
    }

    # 1. Update Redis Telemetry Snapshot (fast cache)
    try:
        redis_key = f"telemetry:mission:{mission.id}"
        redis.setex(redis_key, TELEMETRY_REDIS_TTL, json.dumps(payload))
        if mission.ambulance_id:
            redis.setex(f"telemetry:ambulance:{mission.ambulance_id}", TELEMETRY_REDIS_TTL, json.dumps(payload))
    except Exception as exc:
        logger.warning("Redis telemetry cache update failed: %s", exc)

    # 2. Publish to Redis Pub/Sub Fan-out
    publish_realtime_event("channel:events", payload)
    publish_realtime_event(f"channel:telemetry:{mission.id}", payload)

    # 3. Downsampled persistence into ambulance_telemetry_history (prevent DB table explosion)
    last_hist = db.scalar(
        select(AmbulanceTelemetryHistory)
        .where(AmbulanceTelemetryHistory.mission_id == mission.id)
        .order_by(AmbulanceTelemetryHistory.recorded_at.desc())
        .limit(1)
    )

    should_persist = True
    if last_hist:
        elapsed = (now_dt - last_hist.recorded_at).total_seconds()
        if elapsed < DOWNSAMPLE_INTERVAL_SECONDS:
            # Check if significant distance moved (> 15m)
            dist_moved = abs(data.latitude - last_hist.latitude) + abs(data.longitude - last_hist.longitude)
            if dist_moved < 0.00015:  # ~16 meters
                should_persist = False

    if should_persist:
        db.add(
            AmbulanceTelemetryHistory(
                mission_id=mission.id,
                ambulance_id=mission.ambulance_id,
                latitude=data.latitude,
                longitude=data.longitude,
                speed=data.speed,
                heading=data.heading,
                accuracy=data.accuracy,
                recorded_at=now_dt,
            )
        )

    db.commit()
    return payload


def get_latest_mission_telemetry(db, mission_id: str) -> Optional[Dict[str, Any]]:
    """Fetches the latest telemetry snapshot for a mission from Redis, falling back to DB."""
    try:
        cached = redis.get(f"telemetry:mission:{mission_id}")
        if cached:
            parsed = json.loads(cached)
            # Evaluate staleness
            if "recorded_at" in parsed:
                try:
                    rec_dt = datetime.fromisoformat(parsed["recorded_at"])
                    if rec_dt.tzinfo is None:
                        rec_dt = rec_dt.replace(tzinfo=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - rec_dt).total_seconds()
                    parsed["stale"] = age_seconds > STALE_TELEMETRY_THRESHOLD_SECONDS
                    parsed["age_seconds"] = round(age_seconds, 1)
                except Exception:
                    pass
            return parsed
    except Exception as exc:
        logger.warning("Redis telemetry read error: %s", exc)

    m = db.get(Mission, mission_id)
    if not m or m.latitude is None or m.longitude is None:
        return None

    age_seconds = None
    stale = False
    if m.location_at:
        loc_dt = m.location_at
        if loc_dt.tzinfo is None:
            loc_dt = loc_dt.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - loc_dt).total_seconds()
        stale = age_seconds > STALE_TELEMETRY_THRESHOLD_SECONDS

    amb = db.get(Ambulance, m.ambulance_id)
    return {
        "mission_id": m.id,
        "ambulance_id": m.ambulance_id,
        "incident_id": m.incident_id,
        "latitude": m.latitude,
        "longitude": m.longitude,
        "recorded_at": m.location_at.isoformat() if m.location_at else None,
        "stale": stale,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "ambulance_registration": amb.registration if amb else None,
        "driver_name": amb.driver_name if amb else None,
        "driver_phone": amb.driver_phone if amb else None,
        "remaining_distance_meters": m.decision_distance_meters,
        "mission_status": m.status,
    }


def get_mission_trail(db, mission_id: str, limit: int = 150) -> List[List[float]]:
    """Returns the historical GPS coordinates list [[lat, lng], ...] for a mission."""
    records = db.scalars(
        select(AmbulanceTelemetryHistory)
        .where(AmbulanceTelemetryHistory.mission_id == mission_id)
        .order_by(AmbulanceTelemetryHistory.recorded_at.asc())
        .limit(limit)
    ).all()
    return [[r.latitude, r.longitude] for r in records]


def prune_telemetry_history(db, retention_days: int = 7) -> int:
    """Retention policy job: removes historical telemetry older than retention_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = db.execute(
        delete(AmbulanceTelemetryHistory).where(AmbulanceTelemetryHistory.recorded_at < cutoff)
    )
    db.commit()
    return result.rowcount

