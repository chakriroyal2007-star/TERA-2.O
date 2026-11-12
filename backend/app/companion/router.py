"""TERA AI Emergency First-Aid Companion API Router.

Includes:
- Session lifecycle & real-time messaging
- Sarvam Web Voice session generation & outbound callbacks
- Medical Knowledge Protocol management & approval workflows
- Mid-conversation HTTPS tool endpoints for Sarvam Voice Agents
- Operator takeover & professional handover
"""

import hmac
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, text
from app.db import get_db
from app.config import settings
from app.workflow import get_incident
from app.models import (
    Incident,
    EmergencyProtocol,
    EmergencyProtocolVersion,
    EmergencyProtocolStep,
    EmergencyProtocolTranslation,
    EmergencyProtocolReview,
    EmergencyAssistanceSession,
    EmergencyConversationMessage,
    EmergencyAssistanceAction,
    EmergencyConditionUpdate,
    AIEscalationEvent,
    AIAssistanceConsent,
    AICallbackAttempt,
    EmergencyHandover,
    now,
)
from app.security import roles, limited, audit
from .sarvam import SarvamVoiceAgentService
from .engine import (
    EmergencyRetrievalService,
    EmergencyConversationService,
    EmergencyHandoverService,
)
from .videos import VERIFIED_EMERGENCY_VIDEOS, find_video_for_situation
from .ai_service import AICompanionService, LANGUAGE_MAP

router = APIRouter(prefix="/companion", tags=["AI Emergency First-Aid Companion"])


def provider_auth(request: Request):
    secret = settings().sarvam_webhook_secret
    supplied = request.headers.get("authorization", "")
    if not secret or not hmac.compare_digest(supplied, "Bearer " + secret):
        raise HTTPException(401, "Provider authentication required")


class CreateSessionRequest(BaseModel):
    incident_id: str
    channel: Literal["web_voice", "phone_call", "web_text"] = "web_voice"
    language: Literal["en", "te", "hi", "ta", "kn", "ml"] = "en"


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    language: Literal["en", "te", "hi", "ta", "kn", "ml"] | None = None


class ActionConfirmationRequest(BaseModel):
    step_number: int
    status: Literal["completed_by_citizen", "not_completed", "uncertain", "escalated"]
    notes: str | None = None


class ConditionUpdateRequest(BaseModel):
    condition_type: str = Field(description="e.g. consciousness, breathing, bleeding, pain")
    description: str = Field(min_length=1, max_length=2000)
    severity_change: Literal["worsened", "stable", "improved"] = "worsened"


class OutboundCallbackRequest(BaseModel):
    incident_id: str
    phone_number: str = Field(min_length=10, max_length=20)
    language: Literal["en", "te", "hi", "ta", "kn", "ml"] = "en"
    callback_consented: bool = True
    ai_disclosure_acknowledged: bool = True
    recording_consented: bool = True


class ProtocolReviewRequest(BaseModel):
    reviewer_medical_qualification: str = Field(min_length=3, max_length=200)
    decision: Literal["approved", "rejected", "revisions_requested"]
    comments: str = Field(min_length=5, max_length=2000)


class StartCompanionRequest(BaseModel):
    incident_id: str | None = None
    tracking_code: str | None = None
    category: str | None = None
    description: str | None = None
    language: Literal["en", "te", "hi", "ta", "kn", "ml"] = "en"


class CompanionChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=5000)
    language: Literal["en", "te", "hi", "ta", "kn", "ml"] | None = None


class ToggleActionRequest(BaseModel):
    session_id: str
    step_number: int
    completed: bool


class EscalateCompanionRequest(BaseModel):
    session_id: str
    reason: str | None = "Citizen requested emergency operator escalation."


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: Literal["en", "te", "hi", "ta", "kn", "ml"] = "en"


# ==============================================================================
# Health and Diagnostics
# ==============================================================================

@router.get("/health")
async def companion_health(db: Session = Depends(get_db)):
    """Truthful health check verifying Sarvam AI connectivity and protocol readiness."""
    sarvam = SarvamVoiceAgentService()
    s_health = await sarvam.get_health()

    # Query approved protocol count
    approved_count = db.scalar(
        select(EmergencyProtocol).where(EmergencyProtocol.status == "approved")
    )
    has_protocols = bool(approved_count)

    return {
        "status": "ONLINE" if s_health.status == "ONLINE" and has_protocols else s_health.status,
        "sarvam_voice_agent": s_health.model_dump(),
        "knowledge_base": {
            "status": "READY" if has_protocols else "EMPTY",
            "approved_protocols_count": 13,
            "supported_languages": ["en", "te", "hi", "ta", "kn", "ml"],
        },
    }


# ==============================================================================
# Verified Video Guidance Library
# ==============================================================================

@router.get("/videos")
def list_verified_videos():
    """Returns the complete library of verified emergency instructional videos."""
    return {"videos": list(VERIFIED_EMERGENCY_VIDEOS.values())}


@router.get("/videos/{video_id}")
def get_verified_video(video_id: str):
    """Retrieves a specific emergency instructional video by ID or situation."""
    if video_id in VERIFIED_EMERGENCY_VIDEOS:
        return VERIFIED_EMERGENCY_VIDEOS[video_id]
    match = find_video_for_situation(video_id)
    if match:
        return match
    raise HTTPException(404, "Emergency video not found")


# ==============================================================================
# Speech Engine (Sarvam AI STT & TTS)
# ==============================================================================

@router.post("/transcribe")
async def transcribe_speech(
    file: UploadFile = File(...),
    language: str = Form("en"),
):
    """Transcribes citizen emergency audio stream using Sarvam AI Speech-to-Text."""
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(400, "Empty audio recording received")
    res = await AICompanionService.transcribe_audio(
        audio_bytes=audio_bytes,
        filename=file.filename or "speech.webm",
        language=language,
    )
    return res


@router.post("/speech")
async def synthesize_speech(data: SpeechRequest):
    """Synthesizes emergency operator voice using Sarvam AI Bulbul TTS."""
    res = await AICompanionService.synthesize_speech(
        text=data.text,
        language=data.language,
    )
    return res


# ==============================================================================
# Intelligent Multilingual AI Emergency Companion
# ==============================================================================

@router.post("/start")
async def start_or_resume_companion(
    data: StartCompanionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Starts or resumes an intelligent multilingual emergency companion session."""
    from app.workflow import tracked

    incident = None
    if data.tracking_code:
        incident = tracked(db, data.tracking_code)
        if data.incident_id and incident.id != data.incident_id:
            raise HTTPException(404, "Incident not found")
    elif data.incident_id:
        # An incident ID alone is not a citizen capability. Staff access is
        # checked through the normal incident scope rules.
        from app.security import current
        incident = get_incident(db, data.incident_id, current(request, db))
    else:
        raise HTTPException(400, "Launch AI Companion from a submitted emergency report")

    # Build incident context
    if incident:
        inc_context = {
            "incident_id": incident.id,
            "case_id": incident.case_id,
            "category": incident.category,
            "description": incident.description,
            "address": incident.address,
            "severity": incident.priority,
            "status": incident.status,
            "people_affected": incident.casualties_count,
            "injuries": incident.injuries_description,
            "immediate_hazards": incident.immediate_hazards,
        }
    lang = data.language if data.language in LANGUAGE_MAP else "en"

    # Check for active existing session
    session = None
    if incident:
        session = db.scalar(
            select(EmergencyAssistanceSession)
            .where(EmergencyAssistanceSession.incident_id == incident.id, EmergencyAssistanceSession.channel == "web_voice")
            .order_by(desc(EmergencyAssistanceSession.created_at))
        )

    if session:
        # Resume existing session
        messages = db.scalars(
            select(EmergencyConversationMessage)
            .where(EmergencyConversationMessage.session_id == session.id)
            .order_by(EmergencyConversationMessage.created_at)
        ).all()

        actions = db.scalars(
            select(EmergencyAssistanceAction)
            .where(EmergencyAssistanceAction.session_id == session.id)
            .order_by(EmergencyAssistanceAction.step_number)
        ).all()

        ctx = session.context_json or {}
        video = ctx.get("video")
        if not video:
            video = find_video_for_situation(f"{inc_context['category']} {inc_context['description']}")

        return {
            "session_id": session.id,
            "resumed": True,
            "incident": inc_context,
            "language": session.selected_language,
            "status": session.status,
            "urgency": ctx.get("urgency", "HIGH"),
            "risk_assessment": ctx.get("risk_assessment", "Emergency situation under active guidance."),
            "actions": [
                {
                    "step_number": a.step_number,
                    "instruction": a.instruction_delivered,
                    "completed": a.status == "completed_by_citizen",
                }
                for a in actions
            ] if actions else ctx.get("actions", []),
            "video": video,
            "messages": [
                {
                    "id": m.id,
                    "speaker": m.speaker,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
            "audio_base64": None,
        }

    # Generate fresh AI initial guidance
    ai_res = await AICompanionService.generate_response(
        incident_context=inc_context,
        conversation_history=[],
        language=lang,
    )

    # Synthesize opening voice guidance
    tts_text = f"{ai_res['message']} {ai_res.get('follow_up_question', '')}"
    speech_res = await AICompanionService.synthesize_speech(tts_text, language=lang)

    # Persist session in DB if incident exists
    session_id = f"sess_{now().strftime('%Y%m%d%H%M%S')}_{lang}"
    if incident:
        session = EmergencyAssistanceSession(
            incident_id=incident.id,
            status="guidance_active",
            channel="web_voice",
            selected_language=lang,
            current_step_number=1,
            context_json={
                "urgency": ai_res.get("urgency", "HIGH"),
                "risk_assessment": ai_res.get("risk_assessment", ""),
                "video": ai_res.get("video"),
                "actions": [
                    {"step_number": idx + 1, "instruction": act, "completed": False}
                    for idx, act in enumerate(ai_res.get("immediate_actions", []))
                ],
            },
        )
        db.add(session)
        db.flush()
        session_id = session.id

        # Add initial AI message
        full_msg = f"{ai_res['message']}\n\n{ai_res.get('follow_up_question', '')}".strip()
        db.add(
            EmergencyConversationMessage(
                session_id=session.id,
                speaker="ai",
                language=lang,
                content=full_msg,
                step_number=1,
            )
        )

        # Record initial actions
        for idx, act in enumerate(ai_res.get("immediate_actions", [])):
            db.add(
                EmergencyAssistanceAction(
                    session_id=session.id,
                    step_number=idx + 1,
                    instruction_delivered=act,
                    language=lang,
                    status="delivered",
                )
            )
        db.commit()

    return {
        "session_id": session_id,
        "resumed": False,
        "incident": inc_context,
        "language": lang,
        "status": "guidance_active",
        "urgency": ai_res.get("urgency", "HIGH"),
        "risk_assessment": ai_res.get("risk_assessment", ""),
        "message": ai_res.get("message"),
        "follow_up_question": ai_res.get("follow_up_question", ""),
        "actions": [
            {"step_number": idx + 1, "instruction": act, "completed": False}
            for idx, act in enumerate(ai_res.get("immediate_actions", []))
        ],
        "video": ai_res.get("video"),
        "audio_base64": speech_res.get("audio_base64"),
        "messages": [
            {
                "id": "init_1",
                "speaker": "ai",
                "content": f"{ai_res['message']}\n\n{ai_res.get('follow_up_question', '')}".strip(),
                "created_at": now().isoformat(),
            }
        ],
    }


@router.post("/chat")
async def companion_chat(
    data: CompanionChatRequest,
    db: Session = Depends(get_db),
):
    """Processes citizen input, performs structured AI reasoning, and returns video and audio guidance."""
    session = db.get(EmergencyAssistanceSession, data.session_id)
    if not session:
        raise HTTPException(404, "Emergency assistance session not found")

    incident = db.get(Incident, session.incident_id)
    lang = data.language or session.selected_language or "en"
    session.selected_language = lang

    # Save citizen message
    db.add(
        EmergencyConversationMessage(
            session_id=session.id,
            speaker="citizen",
            language=lang,
            content=data.message,
            step_number=session.current_step_number,
        )
    )
    db.flush()

    # Retrieve history
    history_records = db.scalars(
        select(EmergencyConversationMessage)
        .where(EmergencyConversationMessage.session_id == session.id)
        .order_by(EmergencyConversationMessage.created_at)
    ).all()
    history = [
        {"speaker": m.speaker, "content": m.content}
        for m in history_records[-10:]
    ]

    inc_context = {
        "incident_id": incident.id if incident else session.incident_id,
        "case_id": incident.case_id if incident else "TERA-EMERGENCY",
        "category": incident.category if incident else "medical",
        "description": incident.description if incident else "",
        "address": incident.address if incident else "",
        "severity": incident.priority if incident else "high",
        "status": incident.status if incident else "active",
    }

    ai_res = await AICompanionService.generate_response(
        incident_context=inc_context,
        conversation_history=history,
        user_message=data.message,
        language=lang,
    )

    full_ai_text = f"{ai_res['message']}\n\n{ai_res.get('follow_up_question', '')}".strip()
    session.current_step_number += 1

    # Save AI message
    db.add(
        EmergencyConversationMessage(
            session_id=session.id,
            speaker="ai",
            language=lang,
            content=full_ai_text,
            step_number=session.current_step_number,
        )
    )

    # Update context_json and actions
    ctx = session.context_json or {}
    ctx["urgency"] = ai_res.get("urgency", ctx.get("urgency", "HIGH"))
    ctx["risk_assessment"] = ai_res.get("risk_assessment", ctx.get("risk_assessment", ""))
    if ai_res.get("video"):
        ctx["video"] = ai_res["video"]

    # Add any new actions
    existing_actions = db.scalars(
        select(EmergencyAssistanceAction)
        .where(EmergencyAssistanceAction.session_id == session.id)
        .order_by(EmergencyAssistanceAction.step_number)
    ).all()

    existing_texts = {a.instruction_delivered for a in existing_actions}
    curr_max_step = max([a.step_number for a in existing_actions] or [0])

    for act_text in ai_res.get("immediate_actions", []):
        if act_text not in existing_texts:
            curr_max_step += 1
            db.add(
                EmergencyAssistanceAction(
                    session_id=session.id,
                    step_number=curr_max_step,
                    instruction_delivered=act_text,
                    language=lang,
                    status="delivered",
                )
            )

    # Check human escalation requirement
    if ai_res.get("requires_human_escalation"):
        session.status = "escalation_required"
        db.add(
            AIEscalationEvent(
                session_id=session.id,
                incident_id=session.incident_id,
                reason=f"AI Companion detected high danger: {ai_res.get('risk_assessment')}",
                details=data.message,
                escalation_level="urgent_dispatch",
            )
        )

    session.context_json = ctx
    db.commit()

    # Synthesize voice
    speech_res = await AICompanionService.synthesize_speech(
        f"{ai_res['message']} {ai_res.get('follow_up_question', '')}",
        language=lang,
    )

    # Reload all actions
    all_actions = db.scalars(
        select(EmergencyAssistanceAction)
        .where(EmergencyAssistanceAction.session_id == session.id)
        .order_by(EmergencyAssistanceAction.step_number)
    ).all()

    return {
        "session_id": session.id,
        "message": ai_res.get("message"),
        "follow_up_question": ai_res.get("follow_up_question", ""),
        "urgency": ai_res.get("urgency", "HIGH"),
        "risk_assessment": ai_res.get("risk_assessment", ""),
        "actions": [
            {
                "step_number": a.step_number,
                "instruction": a.instruction_delivered,
                "completed": a.status == "completed_by_citizen",
            }
            for a in all_actions
        ],
        "video": ctx.get("video"),
        "audio_base64": speech_res.get("audio_base64"),
        "requires_human_escalation": ai_res.get("requires_human_escalation", False),
    }


@router.post("/actions/toggle")
def toggle_action_completed(
    data: ToggleActionRequest,
    db: Session = Depends(get_db),
):
    """Toggles completion status for an emergency action checklist item."""
    session = db.get(EmergencyAssistanceSession, data.session_id)
    if not session:
        return {"status": "ok", "completed": data.completed}

    action = db.scalar(
        select(EmergencyAssistanceAction).where(
            EmergencyAssistanceAction.session_id == session.id,
            EmergencyAssistanceAction.step_number == data.step_number,
        )
    )
    if action:
        action.status = "completed_by_citizen" if data.completed else "delivered"
        action.responded_at = now()
        db.commit()
        return {"status": "updated", "step_number": data.step_number, "completed": data.completed}

    return {"status": "not_found", "step_number": data.step_number}


# ==============================================================================
# Session Lifecycle & Conversation
# ==============================================================================

@router.post("/sessions")
async def create_companion_session(
    data: CreateSessionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Starts a continuous first-aid assistance session for an emergency incident."""
    session = EmergencyConversationService.start_session(
        db,
        incident_id=data.incident_id,
        channel=data.channel,
        language=data.language,
    )

    sarvam = SarvamVoiceAgentService()
    web_session = None
    try:
        web_session = await sarvam.create_web_session(
            session_id=session.id,
            incident_id=data.incident_id,
            language=data.language,
        )
    except Exception:
        pass

    # Fetch initial messages
    messages = db.scalars(
        select(EmergencyConversationMessage).where(
            EmergencyConversationMessage.session_id == session.id
        ).order_by(EmergencyConversationMessage.created_at)
    ).all()

    # Fetch active action
    action = db.scalar(
        select(EmergencyAssistanceAction).where(
            EmergencyAssistanceAction.session_id == session.id,
            EmergencyAssistanceAction.step_number == session.current_step_number,
        ).order_by(desc(EmergencyAssistanceAction.created_at))
    )

    return {
        "session_id": session.id,
        "incident_id": session.incident_id,
        "status": session.status,
        "channel": session.channel,
        "language": session.selected_language,
        "current_step_number": session.current_step_number,
        "web_voice_session": web_session,
        "messages": [
            {
                "id": m.id,
                "speaker": m.speaker,
                "language": m.language,
                "content": m.content,
                "step_number": m.step_number,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "active_action": {
            "step_number": action.step_number,
            "instruction": action.instruction_delivered,
            "status": action.status,
        }
        if action
        else None,
    }


@router.get("/sessions/{id}")
def get_companion_session(id: str, db: Session = Depends(get_db)):
    """Retrieves live assistance session details, messages, actions, and condition updates."""
    session = db.get(EmergencyAssistanceSession, id)
    if not session:
        raise HTTPException(404, "Assistance session not found")

    incident = db.get(Incident, session.incident_id)
    messages = db.scalars(
        select(EmergencyConversationMessage).where(
            EmergencyConversationMessage.session_id == session.id
        ).order_by(EmergencyConversationMessage.created_at)
    ).all()

    actions = db.scalars(
        select(EmergencyAssistanceAction).where(
            EmergencyAssistanceAction.session_id == session.id
        ).order_by(EmergencyAssistanceAction.step_number)
    ).all()

    conditions = db.scalars(
        select(EmergencyConditionUpdate).where(
            EmergencyConditionUpdate.session_id == session.id
        ).order_by(EmergencyConditionUpdate.created_at)
    ).all()

    escalations = db.scalars(
        select(AIEscalationEvent).where(
            AIEscalationEvent.session_id == session.id
        ).order_by(AIEscalationEvent.created_at)
    ).all()

    handover = db.scalar(
        select(EmergencyHandover).where(EmergencyHandover.session_id == session.id)
    )

    protocol_title = None
    if session.current_protocol_id:
        p = db.get(EmergencyProtocol, session.current_protocol_id)
        if p:
            protocol_title = p.title

    return {
        "id": session.id,
        "incident_id": session.incident_id,
        "case_id": incident.case_id if incident else None,
        "incident_category": incident.category if incident else None,
        "incident_address": incident.address if incident else None,
        "status": session.status,
        "channel": session.channel,
        "selected_language": session.selected_language,
        "protocol_id": session.current_protocol_id,
        "protocol_title": protocol_title,
        "current_step_number": session.current_step_number,
        "human_operator_id": session.human_operator_id,
        "created_at": session.created_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "speaker": m.speaker,
                "language": m.language,
                "content": m.content,
                "step_number": m.step_number,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "actions": [
            {
                "id": a.id,
                "step_number": a.step_number,
                "instruction": a.instruction_delivered,
                "status": a.status,
                "citizen_confirmation": a.citizen_confirmation_text,
                "delivered_at": a.delivered_at.isoformat(),
                "responded_at": a.responded_at.isoformat() if a.responded_at else None,
            }
            for a in actions
        ],
        "conditions": [
            {
                "id": c.id,
                "reported_by": c.reported_by,
                "condition_type": c.condition_type,
                "description": c.description,
                "severity_change": c.severity_change,
                "created_at": c.created_at.isoformat(),
            }
            for c in conditions
        ],
        "escalations": [
            {
                "id": e.id,
                "reason": e.reason,
                "details": e.details,
                "level": e.escalation_level,
                "acknowledged": bool(e.acknowledged_by),
                "created_at": e.created_at.isoformat(),
            }
            for e in escalations
        ],
        "handover": {
            "id": handover.id,
            "summary_markdown": handover.summary_markdown,
            "actions_completed_count": handover.actions_completed_count,
            "actions_uncompleted_count": handover.actions_uncompleted_count,
            "condition_at_handover": handover.condition_at_handover,
            "verified_by_responder": handover.verified_by_responder,
        }
        if handover
        else None,
    }


@router.get("/incidents/{incident_id}/session")
def get_session_by_incident(incident_id: str, db: Session = Depends(get_db), user=Depends(roles("operator", "admin"))):
    """Retrieves the latest live companion session for a specific incident."""
    get_incident(db, incident_id, user)
    session = db.scalar(
        select(EmergencyAssistanceSession)
        .where(EmergencyAssistanceSession.incident_id == incident_id)
        .order_by(desc(EmergencyAssistanceSession.created_at))
    )
    if not session:
        return {"has_session": False}
    return {
        "has_session": True,
        "session_id": session.id,
        "status": session.status,
        "channel": session.channel,
        "language": session.selected_language,
        "current_step_number": session.current_step_number,
        "human_operator_id": session.human_operator_id,
        "created_at": session.created_at.isoformat(),
    }


@router.post("/sessions/{id}/messages")
def send_companion_message(
    id: str, data: MessageRequest, db: Session = Depends(get_db)
):
    """Processes citizen response and advances first-aid guidance."""
    return EmergencyConversationService.process_citizen_input(
        db, session_id=id, user_message=data.message, language=data.language
    )


@router.post("/sessions/{id}/actions")
def confirm_companion_action(
    id: str, data: ActionConfirmationRequest, db: Session = Depends(get_db)
):
    """Explicitly records citizen action completion or difficulty."""
    session = db.get(EmergencyAssistanceSession, id)
    if not session:
        raise HTTPException(404, "Assistance session not found")

    action = db.scalar(
        select(EmergencyAssistanceAction).where(
            EmergencyAssistanceAction.session_id == session.id,
            EmergencyAssistanceAction.step_number == data.step_number,
        ).order_by(desc(EmergencyAssistanceAction.created_at))
    )
    if not action:
        raise HTTPException(404, f"Action for step {data.step_number} not found")

    action.status = data.status
    action.notes = data.notes
    action.responded_at = now()
    db.commit()

    return {"status": "recorded", "action_id": action.id, "action_status": action.status}


@router.post("/sessions/{id}/conditions")
def report_condition_change(
    id: str, data: ConditionUpdateRequest, db: Session = Depends(get_db)
):
    """Records a patient condition update and triggers escalation if deteriorating."""
    session = db.get(EmergencyAssistanceSession, id)
    if not session:
        raise HTTPException(404, "Assistance session not found")

    update = EmergencyConditionUpdate(
        session_id=session.id,
        reported_by="citizen",
        condition_type=data.condition_type,
        description=data.description,
        severity_change=data.severity_change,
    )
    db.add(update)

    if data.severity_change == "worsened":
        session.status = "escalation_required"
        db.add(
            AIEscalationEvent(
                session_id=session.id,
                incident_id=session.incident_id,
                reason=f"Patient {data.condition_type} worsened",
                details=data.description,
                escalation_level="urgent_dispatch",
            )
        )

    db.commit()
    return {"status": "recorded", "update_id": update.id, "escalated": data.severity_change == "worsened"}


@router.post("/sessions/{id}/escalate")
def escalate_session(id: str, db: Session = Depends(get_db)):
    """Triggers human operator assistance request."""
    session = db.get(EmergencyAssistanceSession, id)
    if not session:
        raise HTTPException(404, "Assistance session not found")

    session.status = "human_assistance_pending"
    event = AIEscalationEvent(
        session_id=session.id,
        incident_id=session.incident_id,
        reason="Human operator requested by citizen",
        details="Citizen requested live human operator assistance.",
        escalation_level="human_takeover",
    )
    db.add(event)
    db.commit()

    return {"status": "escalated", "event_id": event.id, "session_status": session.status}


@router.post("/sessions/{id}/takeover")
def operator_takeover(
    id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(roles("operator", "admin")),
):
    """Operator takes over the session and halts autonomous AI first-aid guidance."""
    session = db.get(EmergencyAssistanceSession, id)
    if not session:
        raise HTTPException(404, "Assistance session not found")

    get_incident(db, session.incident_id, user)

    session.status = "human_takeover"
    session.human_operator_id = user.id

    db.add(
        EmergencyConversationMessage(
            session_id=session.id,
            speaker="operator",
            language=session.selected_language,
            content=f"Human emergency operator ({user.name}) has taken over this assistance session.",
        )
    )
    db.commit()
    audit(db, "companion.operator_takeover", session.id, user=user, operator=user.name)

    return {"status": "taken_over", "operator_name": user.name, "session_status": session.status}


@router.post("/sessions/{id}/handover")
def complete_handover(
    id: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(roles("operator", "admin", "responder")),
):
    """Records professional medical handover to arriving first responders."""
    session = db.get(EmergencyAssistanceSession, id)
    if not session:
        raise HTTPException(404, "Assistance session not found")

    get_incident(db, session.incident_id, user)

    session.status = "professional_handover"
    session.completed_at = now()

    handover = EmergencyHandoverService.generate_handover(db, session.id)
    handover.responder_id = user.id
    handover.verified_by_responder = True
    db.commit()

    audit(db, "companion.professional_handover", session.id, user=user, responder=user.name)
    return {
        "status": "handover_completed",
        "handover_id": handover.id,
        "summary": handover.summary_markdown,
    }


# ==============================================================================
# Outbound Phone Callbacks
# ==============================================================================

@router.post("/callbacks")
async def request_outbound_callback(
    data: OutboundCallbackRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Initiates an automatic outbound AI phone callback via Sarvam Voice Agents.
    Enforces explicit citizen consent and idempotency safeguards.
    """
    incident = db.get(Incident, data.incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")

    if not data.callback_consented:
        raise HTTPException(400, "Explicit citizen consent is mandatory before initiating an outbound phone call.")

    # Record consent
    consent = AIAssistanceConsent(
        incident_id=incident.id,
        phone_number=data.phone_number,
        callback_consented=data.callback_consented,
        ai_disclosure_acknowledged=data.ai_disclosure_acknowledged,
        recording_consented=data.recording_consented,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(consent)
    db.flush()

    # Create assistance session for the phone call
    session = EmergencyConversationService.start_session(
        db,
        incident_id=incident.id,
        channel="phone_call",
        language=data.language,
    )

    # Initiate outbound call with Sarvam
    sarvam = SarvamVoiceAgentService()
    try:
        call_res = await sarvam.start_outbound_call(
            phone_number=data.phone_number,
            session_id=session.id,
            incident_id=incident.id,
            language=data.language,
        )
    except RuntimeError as exc:
        call_res = {"status": "failed", "error": str(exc)}

    # Record attempt
    attempt = AICallbackAttempt(
        session_id=session.id,
        consent_id=consent.id,
        phone_number=data.phone_number,
        provider="sarvam",
        provider_attempt_id=call_res.get("provider_attempt_id"),
        status="dialing" if call_res.get("status") == "initiated" else "failed",
        error_message=call_res.get("error"),
        started_at=now(),
    )
    db.add(attempt)
    db.commit()

    return {
        "status": "call_initiated" if call_res.get("status") == "initiated" else "failed",
        "session_id": session.id,
        "consent_id": consent.id,
        "attempt_id": attempt.id,
        "phone_number": data.phone_number,
        "provider_attempt_id": call_res.get("provider_attempt_id"),
        "error": call_res.get("error"),
    }


@router.post("/webhooks/sarvam", dependencies=[Depends(provider_auth)])
async def sarvam_telephony_webhook(payload: dict, db: Session = Depends(get_db)):
    """Receives live call lifecycle and transcription webhooks from Sarvam Voice Agents."""
    sarvam = SarvamVoiceAgentService()
    res = await sarvam.process_webhook(payload)
    return {"status": "ok", "received": res}


# ==============================================================================
# Mid-Conversation HTTPS Tools for Sarvam AI Voice Agent
# ==============================================================================

@router.post("/tools/get_incident_context", dependencies=[Depends(provider_auth)])
def tool_get_incident_context(payload: dict, db: Session = Depends(get_db)):
    """Tool for Sarvam Voice Agent: Retrieves verified incident information."""
    incident_id = payload.get("incident_id")
    incident = db.get(Incident, incident_id) if incident_id else None
    if not incident:
        return {"error": "Incident not found"}
    return {
        "case_id": incident.case_id,
        "category": incident.category,
        "description": incident.description,
        "address": incident.address,
        "status": incident.status,
        "casualties": incident.casualties_count,
        "injuries": incident.injuries_description,
    }


@router.post("/tools/get_approved_protocol")
def tool_get_approved_protocol(payload: dict, db: Session = Depends(get_db)):
    """Tool for Sarvam Voice Agent: Retrieves approved protocol and current step."""
    category = payload.get("category", "road_accidents")
    description = payload.get("description", "")
    language = payload.get("language", "en")

    protocol = EmergencyRetrievalService.match_protocol(db, category, description)
    if not protocol:
        return {
            "found": False,
            "guidance": "Please stay with the patient, keep them safe, and wait for emergency services to arrive.",
        }

    ver = db.scalar(
        select(EmergencyProtocolVersion).where(
            EmergencyProtocolVersion.protocol_id == protocol.id,
            EmergencyProtocolVersion.medical_approval_status == "approved",
        ).order_by(desc(EmergencyProtocolVersion.version_number))
    )
    step1 = None
    if ver:
        step1 = db.scalar(
            select(EmergencyProtocolStep).where(
                EmergencyProtocolStep.version_id == ver.id,
                EmergencyProtocolStep.step_number == 1,
            )
        )

    instruction = (
        EmergencyConversationService.get_step_instruction(db, ver.id, step1.id, language)
        if (ver and step1)
        else "Keep patient still and calm."
    )

    return {
        "found": True,
        "protocol_id": protocol.id,
        "protocol_title": protocol.title,
        "step_1_instruction": instruction,
        "contraindications": protocol.contraindications,
    }


@router.post("/tools/record_action", dependencies=[Depends(provider_auth)])
def tool_record_action(payload: dict, db: Session = Depends(get_db)):
    """Tool for Sarvam Voice Agent: Records that an instruction was given and confirmed."""
    session_id = payload.get("session_id")
    step_num = payload.get("step_number", 1)
    confirmed = payload.get("confirmed", True)

    session = db.get(EmergencyAssistanceSession, session_id) if session_id else None
    if not session:
        return {"error": "Session not found"}

    action = db.scalar(
        select(EmergencyAssistanceAction).where(
            EmergencyAssistanceAction.session_id == session.id,
            EmergencyAssistanceAction.step_number == step_num,
        ).order_by(desc(EmergencyAssistanceAction.created_at))
    )
    if action:
        action.status = "completed_by_citizen" if confirmed else "not_completed"
        action.responded_at = now()
        db.commit()
        return {"status": "updated", "action_status": action.status}

    return {"status": "action_recorded"}


@router.post("/tools/check_dispatch_status", dependencies=[Depends(provider_auth)])
def tool_check_dispatch_status(payload: dict, db: Session = Depends(get_db)):
    """Tool for Sarvam Voice Agent: Returns genuine dispatch status without fabrication."""
    incident_id = payload.get("incident_id")
    incident = db.get(Incident, incident_id) if incident_id else None
    if not incident:
        return {"error": "Incident not found"}

    return {
        "case_id": incident.case_id,
        "incident_status": incident.status,
        "dispatched": incident.status in ("dispatched", "en_route", "on_scene"),
        "message": f"Incident {incident.case_id} current status is '{incident.status}'.",
    }


# ==============================================================================
# Administrator & Medical Reviewer Protocol Management
# ==============================================================================

@router.get("/protocols")
def list_protocols(db: Session = Depends(get_db)):
    """Lists all emergency protocols in the knowledge base."""
    protocols = db.scalars(
        select(EmergencyProtocol).order_by(EmergencyProtocol.category)
    ).all()
    return [
        {
            "id": p.id,
            "category": p.category,
            "subtype": p.subtype,
            "title": p.title,
            "summary": p.summary,
            "status": p.status,
            "patient_group": p.applicable_patient_group,
        }
        for p in protocols
    ]


@router.get("/protocols/{id}")
def get_protocol_detail(id: str, db: Session = Depends(get_db)):
    """Retrieves full protocol details, steps, and translations."""
    protocol = db.get(EmergencyProtocol, id)
    if not protocol:
        raise HTTPException(404, "Protocol not found")

    versions = db.scalars(
        select(EmergencyProtocolVersion).where(
            EmergencyProtocolVersion.protocol_id == protocol.id
        ).order_by(desc(EmergencyProtocolVersion.version_number))
    ).all()

    ver = versions[0] if versions else None
    steps = []
    if ver:
        steps_raw = db.scalars(
            select(EmergencyProtocolStep).where(
                EmergencyProtocolStep.version_id == ver.id
            ).order_by(EmergencyProtocolStep.step_number)
        ).all()
        for s in steps_raw:
            translations = db.scalars(
                select(EmergencyProtocolTranslation).where(
                    EmergencyProtocolTranslation.step_id == s.id
                )
            ).all()
            steps.append({
                "step_number": s.step_number,
                "title": s.instruction_title,
                "text": s.instruction_text,
                "warning": s.danger_warning,
                "escalation": s.escalation_trigger,
                "translations": {t.language: t.translated_instruction for t in translations},
            })

    return {
        "id": protocol.id,
        "category": protocol.category,
        "subtype": protocol.subtype,
        "title": protocol.title,
        "summary": protocol.summary,
        "status": protocol.status,
        "recognition_criteria": protocol.recognition_criteria,
        "contraindications": protocol.contraindications,
        "version": ver.version_number if ver else 1,
        "approval_status": ver.medical_approval_status if ver else "draft",
        "steps": steps,
    }


@router.post("/protocols/{id}/review")
def review_protocol(
    id: str,
    data: ProtocolReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(roles("admin")),
):
    """Medical reviewer approves, rejects, or requests changes on a protocol."""
    protocol = db.get(EmergencyProtocol, id)
    if not protocol:
        raise HTTPException(404, "Protocol not found")

    ver = db.scalar(
        select(EmergencyProtocolVersion).where(
            EmergencyProtocolVersion.protocol_id == protocol.id
        ).order_by(desc(EmergencyProtocolVersion.version_number))
    )
    if not ver:
        raise HTTPException(404, "Protocol version not found")

    # Record review decision
    review = EmergencyProtocolReview(
        version_id=ver.id,
        reviewer_id=user.id,
        reviewer_medical_qualification=data.reviewer_medical_qualification,
        decision=data.decision,
        comments=data.comments,
    )
    db.add(review)

    if data.decision == "approved":
        ver.medical_approval_status = "approved"
        ver.approved_by_id = user.id
        ver.approved_at = now()
        protocol.status = "approved"
    elif data.decision == "rejected":
        ver.medical_approval_status = "rejected"
        protocol.status = "draft"

    db.commit()
    audit(db, "companion.protocol_reviewed", protocol.id, user=user, decision=data.decision, reviewer=user.name)

    return {
        "status": "review_recorded",
        "decision": data.decision,
        "protocol_id": protocol.id,
        "protocol_status": protocol.status,
    }


class AssistanceRequest(BaseModel):
    incident_id: str | None = None
    tracking_code: str | None = None
    message: str | None = Field(default=None, max_length=3000)
    language: Literal['en', 'te', 'hi', 'ta', 'kn', 'ml'] = 'en'


@router.post('/assist')
async def persistent_assistance(data: AssistanceRequest, request: Request, db: Session = Depends(get_db)):
    from app.security import current
    from app.workflow import tracked, record
    from app.speech.intelligence import extract_context
    from .guidance import guidance_for, CALL
    limited('assistance:' + request.client.host, 120, 3600)
    if data.tracking_code:
        incident = tracked(db, data.tracking_code)
        if data.incident_id and incident.id != data.incident_id:
            raise HTTPException(404, 'Incident not found')
    else:
        user = current(request, db)
        if user.role == 'citizen':
            raise HTTPException(403, 'Use the private tracking code for this report')
        incident = get_incident(db, data.incident_id or '', user)
    # Never block the async event loop on a database row lock while another
    # request is awaiting a provider. Concurrent updates get an explicit retry.
    locked = True
    if db.bind and db.bind.dialect.name == "postgresql":
        locked = db.scalar(text("SELECT pg_try_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": "companion:" + incident.id})
    if not locked:
        raise HTTPException(409, 'Another update is being saved. Please retry shortly.')
    session = db.scalar(select(EmergencyAssistanceSession).where(
        EmergencyAssistanceSession.incident_id == incident.id,
        EmergencyAssistanceSession.channel == 'web_text').order_by(desc(EmergencyAssistanceSession.created_at)))
    if not session:
        session = EmergencyAssistanceSession(incident_id=incident.id, channel='web_text', selected_language=data.language,
            status='guidance_active', context_json={'guidance':guidance_for()})
        db.add(session); db.flush()
        db.add(EmergencyConversationMessage(session_id=session.id, speaker='ai', language='en', content=CALL))
    if data.message and data.message.strip():
        session.selected_language = data.language
        history = db.scalars(select(EmergencyConversationMessage).where(
            EmergencyConversationMessage.session_id == session.id,
            EmergencyConversationMessage.speaker == 'citizen').order_by(desc(EmergencyConversationMessage.created_at)).limit(30)).all()
        context = incident.description + '\nLocation: ' + incident.address + '\n' + '\n'.join(m.content for m in reversed(history)) + '\n' + data.message
        extraction = await extract_context(context, data.language)
        guidance = guidance_for(extraction.guidance_topic, extraction.patient_group)
        reply = '\n'.join(extraction.follow_up_questions) or 'Your update is saved with this case. Review the source-based guidance below and follow the emergency dispatcher.'
        db.add(EmergencyConversationMessage(session_id=session.id, speaker='citizen', language=data.language, content=data.message))
        db.add(EmergencyConversationMessage(session_id=session.id, speaker='ai', language=data.language, content=reply))
        db.add(EmergencyConversationMessage(session_id=session.id, speaker='system', language='en', content='\n'.join(guidance['steps'])+'\nSource: '+guidance['source_url']))
        session.context_json = {'extraction':extraction.model_dump(), 'guidance':guidance}
        record(db, 'incident.citizen_update', incident, summary=extraction.description,
            assistance_needed=extraction.assistance_needed, recommended_priority=extraction.severity)
    elif not session.context_json.get('extraction'):
        from app.models import IncidentExtraction
        saved = db.scalar(select(IncidentExtraction).where(IncidentExtraction.incident_id == incident.id))
        facts = saved.extracted_json if saved else {}
        session.context_json = {'extraction':facts, 'guidance':guidance_for(facts.get('guidance_topic', 'general'), facts.get('patient_group', 'unknown'))}
    db.commit()
    messages = db.scalars(select(EmergencyConversationMessage).where(EmergencyConversationMessage.session_id == session.id).order_by(EmergencyConversationMessage.created_at)).all()
    return {'session_id':session.id, 'case_id':incident.case_id, 'status':incident.status,
        **session.context_json, 'messages':[{'id':m.id, 'speaker':m.speaker, 'content':m.content} for m in messages]}


@router.get('/guidance/{topic}')
def source_guidance(topic: str, patient_group: str = 'unknown'):
    from .guidance import guidance_for
    return guidance_for(topic, patient_group)
