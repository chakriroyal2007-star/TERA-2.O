import secrets
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import Response as FastApiResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from app.config import settings
from app.db import get_db
from app.models import (
    Incident,
    Event,
    Report,
    VoiceRecording,
    TranscriptionJob,
    Transcript,
    IncidentExtraction,
    Evidence,
    IncidentStatusHistory,
    now,
)
from app.security import roles, limited, digest
from app.workflow import tracked, get_incident, record, generate_case_id
from .provider import get_speech_provider, ProviderHealth
from .storage import save_audio, load_audio, stream_audio
from .extraction import ExtractedIncident
from .report import generate_incident_pdf
from .intelligence import extract_context

router = APIRouter(tags=["Speech and Voice Operations"])


class CorrectTranscriptRequest(BaseModel):
    corrected_transcript: str = Field(min_length=1, max_length=10000)


class TranscribeRequest(BaseModel):
    language: str | None = Field(default=None, max_length=10)


class VoiceExtractRequest(BaseModel):
    recording_id: str | None = None
    transcript: str | None = Field(default=None, max_length=10000)
    language: str | None = None


class VoiceFollowUp(BaseModel):
    message: str = Field(min_length=1, max_length=3000)


@router.post("/voice/recordings/{recording_id}/follow-up")
async def voice_follow_up(recording_id: str, data: VoiceFollowUp, request: Request, db=Depends(get_db)):
    limited("voice-follow-up:" + request.client.host, 60, 3600)
    rec = db.get(VoiceRecording, recording_id)
    if not rec or rec.incident_id:
        raise HTTPException(409, "This draft is unavailable or already submitted")
    tr = db.scalar(select(Transcript).where(Transcript.recording_id == recording_id))
    ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == recording_id))
    if not tr or not ext:
        raise HTTPException(404, "Transcript not found")
    history = list(ext.extracted_json.get("conversation", []))
    if len(history) >= 40:
        raise HTTPException(422, "Please review and submit the report before adding more messages")
    history.append({"speaker": "citizen", "content": data.message, "created_at": now().isoformat()})
    context = (tr.corrected_transcript or tr.original_transcript) + "\n" + "\n".join(m["content"] for m in history if m["speaker"] == "citizen")
    result = await extract_context(context, tr.detected_language)
    reply = " ".join(result.follow_up_questions) or "The report has been updated. Review the fields and submit when ready."
    history.append({"speaker": "assistant", "content": reply, "created_at": now().isoformat()})
    ext.extracted_json = {**result.model_dump(), "conversation": history}
    db.commit()
    return {"extraction": ext.extracted_json, "reply": reply}


class VoiceIncidentSubmit(BaseModel):
    recording_id: str
    category: Literal["medical", "road_collision", "fire", "disaster", "other"]
    description: str = Field(min_length=10, max_length=5000)
    address: str = Field(min_length=3, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    corrected_transcript: str | None = None
    confirmed_extraction: dict = Field(default_factory=dict)
    casualties_count: int | None = Field(default=None, ge=0, le=100000)
    injuries_description: str | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    detected_language: str | None = None
    english_translation: str | None = None
    vehicles_involved: str | None = None
    immediate_hazards: str | None = None
    requested_assistance: str | None = None
    citizen_contact: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, min_length=16, max_length=64)


@router.get("/speech/health", response_model=ProviderHealth)
@router.get("/voice/health", response_model=ProviderHealth)
async def speech_health():
    """
    Check speech provider configuration, connectivity, and dependencies truthfully.
    Never reports ONLINE if API keys or provider dependencies are missing.
    """
    provider = get_speech_provider()
    return await provider.get_health()


@router.post("/voice/extract", response_model=ExtractedIncident)
async def voice_extract(data: VoiceExtractRequest, request: Request, db=Depends(get_db)):
    """Extract structured emergency fields from spoken transcript."""
    limited("voice-extract:" + request.client.host, 60, 3600)
    text = data.transcript or ""
    rec_id = data.recording_id
    lang = data.language
    if rec_id and not text:
        tr = db.scalar(select(Transcript).where(Transcript.recording_id == rec_id))
        if tr:
            text = tr.corrected_transcript or tr.original_transcript
            lang = lang or tr.detected_language
    if not text:
        raise HTTPException(422, "Please provide recording_id or transcript")

    extracted = await extract_context(text, lang)
    if rec_id:
        existing = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == rec_id))
        if existing:
            existing.extracted_json = extracted.model_dump()
        else:
            db.add(
                IncidentExtraction(
                    recording_id=rec_id,
                    extracted_json=extracted.model_dump(),
                    extraction_status="extracted",
                )
            )
        db.commit()
    return extracted


@router.post("/voice/transcribe")
async def voice_transcribe(
    request: Request,
    file: UploadFile = File(...),
    language: str = Form("auto"),
    db=Depends(get_db),
):
    """Persist, transcribe, and extract one browser voice report.

    The provider credential is intentionally used only on this server.  A
    failed provider call leaves a visible failed recording for support rather
    than a fake client-side recording id that cannot be submitted later.
    """
    limited("voice-transcribe:" + request.client.host, 300, 3600)
    data = await file.read()
    mime = file.content_type or "audio/webm"
    storage_ref, filename, file_size, checksum = save_audio(data, mime)
    rec = VoiceRecording(
        storage_reference=storage_ref,
        original_filename=filename,
        mime_type=mime,
        file_size=file_size,
        duration=0.0,
        checksum=checksum,
        recording_status="uploaded",
    )
    db.add(rec)
    db.flush()

    provider = get_speech_provider()
    try:
        trans_res = await provider.transcribe(data, mime, language if language != "auto" else None)
    except HTTPException:
        rec.recording_status = "failed"
        db.commit()
        raise
    except ValueError as exc:
        rec.recording_status = "failed"
        db.commit()
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        rec.recording_status = "failed"
        db.commit()
        err_msg = str(exc)
        if "No clear speech" in err_msg or "too short" in err_msg or "Failed to read" in err_msg or "Invalid file" in err_msg:
            raise HTTPException(422, "Audio could not be transcribed. Speak clearly into the microphone and try again.") from exc
        raise HTTPException(
            503,
            "Voice transcription is temporarily unavailable. Please re-record, try again shortly, or use the text report.",
        ) from exc

    if not trans_res.text.strip():
        rec.recording_status = "failed"
        db.commit()
        raise HTTPException(
            422,
            "No speech could be recognized. Speak closer to the microphone and try again.",
        )

    tr = Transcript(
        recording_id=rec.id,
        original_transcript=trans_res.text,
        detected_language=trans_res.detected_language,
        confidence=trans_res.confidence,
        provider=trans_res.provider,
        provider_metadata=trans_res.metadata,
    )
    db.add(tr)

    db.flush()
    extracted = await extract_context(trans_res.text, trans_res.detected_language)
    ext = IncidentExtraction(
        recording_id=rec.id,
        transcript_id=tr.id,
        extracted_json=extracted.model_dump(),
        extraction_status="extracted",
    )
    db.add(ext)
    rec.recording_status = "transcribed"
    db.commit()

    return {
        "recording_id": rec.id,
        "transcript": tr.original_transcript,
        "detected_language": tr.detected_language,
        "confidence": tr.confidence,
        "provider": tr.provider,
        "extraction": extracted.model_dump(),
    }


@router.post("/speech/recordings", status_code=201)
async def upload_recording(
    request: Request,
    file: UploadFile = File(...),
    duration: float = Form(0.0),
    db=Depends(get_db),
):
    """
    Accepts raw audio recorded via browser microphone, validates format and size,
    computes SHA-256 checksum, and persists to durable storage and PostgreSQL.
    """
    limited("speech-record:" + request.client.host, 300, 3600)
    data = await file.read()
    mime = file.content_type or "audio/webm"

    storage_ref, filename, file_size, checksum = save_audio(data, mime)

    recording = VoiceRecording(
        storage_reference=storage_ref,
        original_filename=filename,
        mime_type=mime,
        file_size=file_size,
        duration=max(duration, 0.0),
        checksum=checksum,
        recording_status="uploaded",
    )
    db.add(recording)
    db.commit()

    return {
        "id": recording.id,
        "duration": recording.duration,
        "mime_type": recording.mime_type,
        "file_size": recording.file_size,
        "checksum": recording.checksum,
        "recording_status": recording.recording_status,
        "created_at": recording.created_at,
    }


@router.get("/speech/recordings/{recording_id}")
def get_recording_metadata(recording_id: str, db=Depends(get_db)):
    rec = db.get(VoiceRecording, recording_id)
    if not rec:
        raise HTTPException(404, "Recording not found")
    return {
        "id": rec.id,
        "incident_id": rec.incident_id,
        "duration": rec.duration,
        "mime_type": rec.mime_type,
        "file_size": rec.file_size,
        "checksum": rec.checksum,
        "recording_status": rec.recording_status,
        "created_at": rec.created_at,
    }


@router.get("/speech/recordings/{recording_id}/audio")
def stream_recording_audio(recording_id: str, request: Request, db=Depends(get_db)):
    """Streams the recorded audio for HTML5 audio playback with Range request support."""
    rec = db.get(VoiceRecording, recording_id)
    if not rec:
        raise HTTPException(404, "Recording not found")
    range_header = request.headers.get("range")
    return stream_audio(rec.storage_reference, rec.mime_type, range_header)


@router.post("/speech/recordings/{recording_id}/transcribe")
async def transcribe_recording(
    recording_id: str,
    payload: TranscribeRequest | None = None,
    db=Depends(get_db),
):
    """
    Executes speech-to-text transcription via the configured SpeechProvider,
    persists original transcript, and triggers structured incident extraction.
    """
    rec = db.get(VoiceRecording, recording_id)
    if not rec:
        raise HTTPException(404, "Recording not found")

    provider = get_speech_provider()
    lang = payload.language if payload else None

    # Track transcription job
    job = TranscriptionJob(
        recording_id=rec.id,
        provider=getattr(provider, "provider", settings().speech_provider or "speech"),
        language=lang or settings().speech_provider_language or "en",
        status="processing",
    )
    db.add(job)
    db.commit()

    try:
        audio_bytes, mime = load_audio(rec.storage_reference)
        res = await provider.transcribe(audio_bytes, mime, lang)

        rec.recording_status = "transcribed"
        job.status = "completed"
        job.completed_at = now()

        # Persist or update transcript
        existing_transcript = db.scalar(select(Transcript).where(Transcript.recording_id == rec.id))
        if existing_transcript:
            existing_transcript.original_transcript = res.text
            existing_transcript.detected_language = res.detected_language
            existing_transcript.confidence = res.confidence
            existing_transcript.provider = res.provider
            existing_transcript.provider_metadata = res.metadata
            tr = existing_transcript
        else:
            tr = Transcript(
                recording_id=rec.id,
                original_transcript=res.text,
                detected_language=res.detected_language,
                confidence=res.confidence,
                provider=res.provider,
                provider_metadata=res.metadata,
            )
            db.add(tr)
        db.flush()

        # Run extraction pipeline
        extraction_data = await extract_context(res.text, res.detected_language)
        existing_extraction = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == rec.id))
        if existing_extraction:
            existing_extraction.extracted_json = extraction_data.model_dump()
            ext = existing_extraction
        else:
            ext = IncidentExtraction(
                recording_id=rec.id,
                transcript_id=tr.id,
                extracted_json=extraction_data.model_dump(),
                extraction_status="extracted",
                user_confirmed=False,
            )
            db.add(ext)

        db.commit()

        return {
            "recording_id": rec.id,
            "job_id": job.id,
            "status": "completed",
            "original_transcript": tr.original_transcript,
            "corrected_transcript": tr.corrected_transcript,
            "detected_language": tr.detected_language,
            "confidence": tr.confidence,
            "provider": tr.provider,
            "extraction": ext.extracted_json,
        }
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        rec.recording_status = "failed"
        db.commit()
        raise HTTPException(502, f"Speech transcription failed: {str(exc)}")


@router.get("/speech/jobs/{job_id}")
def get_transcription_job(job_id: str, db=Depends(get_db)):
    job = db.get(TranscriptionJob, job_id)
    if not job:
        raise HTTPException(404, "Transcription job not found")
    return {
        "id": job.id,
        "recording_id": job.recording_id,
        "provider": job.provider,
        "status": job.status,
        "error_message": job.error_message,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }


@router.get("/speech/transcripts/{recording_id}")
def get_transcript(recording_id: str, db=Depends(get_db)):
    tr = db.scalar(select(Transcript).where(Transcript.recording_id == recording_id))
    if not tr:
        raise HTTPException(404, "Transcript not found for this recording")
    ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == recording_id))
    return {
        "id": tr.id,
        "recording_id": tr.recording_id,
        "original_transcript": tr.original_transcript,
        "corrected_transcript": tr.corrected_transcript,
        "detected_language": tr.detected_language,
        "confidence": tr.confidence,
        "provider": tr.provider,
        "created_at": tr.created_at,
        "extraction": ext.extracted_json if ext else None,
        "user_confirmed": ext.user_confirmed if ext else False,
    }


@router.post("/speech/transcripts/{recording_id}/correct")
async def correct_transcript(recording_id: str, data: CorrectTranscriptRequest, db=Depends(get_db)):
    """Allows user to correct errors in the transcript before final submission."""
    tr = db.scalar(select(Transcript).where(Transcript.recording_id == recording_id))
    if not tr:
        raise HTTPException(404, "Transcript not found")
    tr.corrected_transcript = data.corrected_transcript.strip()

    # Re-extract the corrected original together with later citizen clarifications.
    ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == recording_id))
    history = ext.extracted_json.get("conversation", []) if ext else []
    context = tr.corrected_transcript + "\n" + "\n".join(m["content"] for m in history if m["speaker"] == "citizen")
    ext_data = await extract_context(context, tr.detected_language)
    if ext:
        ext.extracted_json = {**ext_data.model_dump(), "conversation": history}

    db.commit()
    return {
        "recording_id": recording_id,
        "original_transcript": tr.original_transcript,
        "corrected_transcript": tr.corrected_transcript,
        "extraction": ext.extracted_json if ext else ext_data.model_dump(),
    }


@router.post("/speech/transcripts/{recording_id}/extract")
async def extract_from_transcript(recording_id: str, db=Depends(get_db)):
    """Re-runs incident field extraction."""
    tr = db.scalar(select(Transcript).where(Transcript.recording_id == recording_id))
    if not tr:
        raise HTTPException(404, "Transcript not found")
    text = tr.corrected_transcript or tr.original_transcript
    ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == recording_id))
    history = ext.extracted_json.get("conversation", []) if ext else []
    text += "\n" + "\n".join(m["content"] for m in history if m["speaker"] == "citizen")
    ext_data = await extract_context(text, tr.detected_language)
    if ext:
        ext.extracted_json = {**ext_data.model_dump(), "conversation": history}
    else:
        ext = IncidentExtraction(
            recording_id=recording_id,
            transcript_id=tr.id,
            extracted_json=ext_data.model_dump(),
        )
        db.add(ext)
    db.commit()
    return ext.extracted_json


@router.post("/public/voice-incidents", status_code=201)
def submit_voice_incident(data: VoiceIncidentSubmit, request: Request, db=Depends(get_db)):
    """
    Finalizes the voice incident submission:
    Creates PostgreSQL Incident, links voice recording, transcript, extraction,
    records timeline event, and issues private tracking code.
    """
    limited("incident:" + request.client.host, 300, 3600)
    rec = db.get(VoiceRecording, data.recording_id)
    if not rec:
        raise HTTPException(404, "Voice recording not found")

    # Idempotency check
    if data.idempotency_key:
        try:
            if db.bind and db.bind.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": data.idempotency_key})
        except Exception:
            pass
        existing = db.scalar(select(Incident).where(Incident.idempotency_key == data.idempotency_key))
        if existing:
            return {
                "id": existing.id,
                "case_id": existing.case_id,
                "tracking_code": "TRK-" + digest("tracking:" + data.idempotency_key),
                "status": existing.status,
                "category": existing.category,
                "duplicate": True,
            }

    tracking_code = "TRK-" + (digest("tracking:" + data.idempotency_key) if data.idempotency_key else secrets.token_urlsafe(24))
    case_id = generate_case_id(db)

    incident = Incident(
        case_id=case_id,
        idempotency_key=data.idempotency_key,
        tracking_hash=digest(tracking_code),
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
    db.add(incident)
    db.flush()

    # Link voice recording
    rec.incident_id = incident.id
    rec.recording_status = "completed"

    # Link transcript
    tr = db.scalar(select(Transcript).where(Transcript.recording_id == rec.id))
    if tr:
        if data.corrected_transcript:
            tr.corrected_transcript = data.corrected_transcript.strip()
        if data.detected_language:
            tr.detected_language = data.detected_language

    # Link extraction
    ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == rec.id))
    if ext:
        ext.incident_id = incident.id
        ext.user_confirmed = True
        if data.confirmed_extraction:
            ext.extracted_json = {**ext.extracted_json, **data.confirmed_extraction}

    # Link any evidence uploaded
    if data.evidence_ids:
        for eid in data.evidence_ids:
            ev = db.scalar(select(Evidence).where(Evidence.id == eid).with_for_update())
            if not ev or ev.incident_id is not None:
                raise HTTPException(409, "Evidence is missing or already attached to a report")
            ev.incident_id = incident.id

    db.add(Report(incident_id=incident.id, text=data.description))
    db.add(
        IncidentStatusHistory(
            incident_id=incident.id,
            previous_status="",
            new_status="reported",
            notes="Citizen voice report submitted",
        )
    )

    # Record operational event & audit
    record(
        db,
        "incident.voice_reported",
        incident,
        case_id=case_id,
        tracking_code=tracking_code,
        has_voice=True,
        recording_id=rec.id,
        duration=rec.duration,
        category=incident.category,
    )

    # Generate PDF
    try:
        pdf_bytes = generate_incident_pdf(
            incident=incident,
            voice_recording=rec,
            transcript=tr,
            extraction=ext,
        )
        pdf_dir = Path(settings().recordings_dir) / "reports"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = pdf_dir / f"{case_id}.pdf"
        pdf_file.write_bytes(pdf_bytes)
        incident.pdf_path = str(pdf_file)
    except Exception:
        pass

    db.commit()

    return {
        "id": incident.id,
        "case_id": case_id,
        "tracking_code": tracking_code,
        "status": incident.status,
        "category": incident.category,
        "recording_id": rec.id,
        "pdf_url": f"/api/v1/incidents/{incident.id}/report",
        "message": "Emergency voice report successfully created and queued for dispatch.",
    }


@router.get("/incidents/{id}/voice")
def get_incident_voice(
    id: str,
    user=Depends(roles("admin", "operator", "responder", "hospital", "analyst")),
    db=Depends(get_db),
):
    """Fetches voice recording, transcript, and extraction details for operators."""
    get_incident(db, id, user)
    rec = db.scalar(select(VoiceRecording).where(VoiceRecording.incident_id == id))
    if not rec:
        return {"has_voice": False}

    tr = db.scalar(select(Transcript).where(Transcript.recording_id == rec.id))
    ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.recording_id == rec.id))

    return {
        "has_voice": True,
        "recording": {
            "id": rec.id,
            "duration": rec.duration,
            "mime_type": rec.mime_type,
            "file_size": rec.file_size,
            "checksum": rec.checksum,
            "created_at": rec.created_at,
            "audio_url": f"/api/v1/speech/recordings/{rec.id}/audio",
        },
        "transcript": {
            "original": tr.original_transcript if tr else None,
            "corrected": tr.corrected_transcript if tr else None,
            "language": tr.detected_language if tr else None,
            "confidence": tr.confidence if tr else None,
            "provider": tr.provider if tr else None,
        }
        if tr
        else None,
        "extraction": ext.extracted_json if ext else None,
        "user_confirmed": ext.user_confirmed if ext else False,
    }


@router.get("/incidents/{id}/audio")
def get_incident_audio_stream(
    id: str,
    request: Request,
    user=Depends(roles("admin", "operator", "responder", "hospital", "analyst")),
    db=Depends(get_db),
):
    """Authorized audio stream for an incident."""
    get_incident(db, id, user)
    rec = db.scalar(select(VoiceRecording).where(VoiceRecording.incident_id == id))
    if not rec:
        raise HTTPException(404, "No voice recording found for this incident")
    range_header = request.headers.get("range")
    return stream_audio(rec.storage_reference, rec.mime_type, range_header)


@router.get("/incidents/{id}/report")
def get_incident_pdf_report(
    id: str,
    request: Request,
    user=Depends(roles("admin", "operator", "responder", "hospital", "analyst")),
    db=Depends(get_db),
):
    """Generates and downloads a formal PDF report for the incident."""
    inc = get_incident(db, id, user)

    rec = db.scalar(select(VoiceRecording).where(VoiceRecording.incident_id == inc.id))
    tr = db.scalar(select(Transcript).where(Transcript.recording_id == rec.id)) if rec else None
    ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.incident_id == inc.id))
    events = list(db.scalars(select(Event).where(Event.incident_id == inc.id).order_by(Event.created_at.asc())))
    reports = list(db.scalars(select(Report).where(Report.incident_id == inc.id).order_by(Report.created_at.asc())))

    pdf_bytes = generate_incident_pdf(
        incident=inc,
        voice_recording=rec,
        transcript=tr,
        extraction=ext,
        events=events,
        reports=reports,
    )

    filename = f"{inc.case_id or inc.id[:8].upper()}.pdf"
    return FastApiResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/public/track/{code}/report")
def get_public_tracking_pdf_report(code: str, db=Depends(get_db)):
    """Allows a citizen to download their official PDF report using their tracking code or case ID."""
    inc = tracked(db, code)
    rec = db.scalar(select(VoiceRecording).where(VoiceRecording.incident_id == inc.id))
    tr = db.scalar(select(Transcript).where(Transcript.recording_id == rec.id)) if rec else None
    ext = db.scalar(select(IncidentExtraction).where(IncidentExtraction.incident_id == inc.id))
    events = list(db.scalars(select(Event).where(Event.incident_id == inc.id).order_by(Event.created_at.asc())))
    reports = list(db.scalars(select(Report).where(Report.incident_id == inc.id).order_by(Report.created_at.asc())))

    pdf_bytes = generate_incident_pdf(
        incident=inc,
        voice_recording=rec,
        transcript=tr,
        extraction=ext,
        events=events,
        reports=reports,
    )

    filename = f"{inc.case_id or inc.id[:8].upper()}.pdf"
    return FastApiResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

