from __future__ import annotations
"""TERA AI Multilingual Emergency Companion Service.

Orchestrates:
1. OpenRouter Intelligent Emergency Conversation Engine (multilingual, structured JSON, dynamic assessment)
2. Sarvam Speech-to-Text (STT) for natural citizen voice input in 6 languages
3. Sarvam Text-to-Speech (TTS) for lifelike emergency guidance voice synthesis
4. Dynamic matching of verified instructional safety videos
"""

import json
import logging
import httpx
from typing import Any
from app.config import settings
from .videos import find_video_for_situation, VERIFIED_EMERGENCY_VIDEOS

logger = logging.getLogger("tera.companion.ai")

# 6 Supported Indian & English Languages
LANGUAGE_MAP = {
    "en": {"code": "en-IN", "name": "English", "speaker": "kavya"},
    "te": {"code": "te-IN", "name": "Telugu (తెలుగు)", "speaker": "kavitha"},
    "hi": {"code": "hi-IN", "name": "Hindi (हिन्दी)", "speaker": "priya"},
    "ta": {"code": "ta-IN", "name": "Tamil (தமிழ்)", "speaker": "gokul"},
    "kn": {"code": "kn-IN", "name": "Kannada (ಕನ್ನಡ)", "speaker": "tarun"},
    "ml": {"code": "ml-IN", "name": "Malayalam (മലയാളം)", "speaker": "kavya"},
}

FALLBACK_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "openai/gpt-4o-mini",
    "openai/gpt-4.1-mini",
]


class AICompanionService:
    """Core intelligence engine for the TERA Multilingual AI Emergency Companion."""

    @staticmethod
    def get_system_prompt(language: str = "en") -> str:
        lang_name = LANGUAGE_MAP.get(language, LANGUAGE_MAP["en"])["name"]
        return f"""You are TERA's AI Multilingual Emergency Assistance Companion.
Your role is to act as an intelligent, calm, highly empathetic, and decisive emergency guidance operator.
You assist citizens during acute crises while emergency responders (ambulance, police, fire) are en route.

PRIMARY GOALS:
1. Understand the incident already reported. Never ask questions that were already answered in the report.
2. Determine immediate dangers and prioritize life-safety over everything else.
3. Provide clear, simple, step-by-step instructions (1 or 2 steps at a time).
4. Verify whether the citizen has completed the step or is safe before moving to the next.
5. If immediate danger exists, give urgent life-saving directives immediately.
6. Identify whether instructional video guidance is required (e.g. CPR, bleeding control, choking, burns, seizure, road accident safety, fire evacuation, flood survival, electric shock, snakebite, heatstroke, poisoning).
7. Communicate FLUENTLY in {lang_name}.

OUTPUT FORMAT:
You MUST respond with a strictly valid JSON object matching this schema:
{{
  "message": "Clear, concise, calming message and immediate instruction in {lang_name}. (2-4 sentences max)",
  "follow_up_question": "One focused question to assess status, safety, or confirmation in {lang_name}.",
  "urgency": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
  "risk_assessment": "Brief assessment of active dangers in English (1 sentence).",
  "immediate_actions": [
    "Action step 1 (actionable verb)",
    "Action step 2",
    "Action step 3"
  ],
  "video_category": "cpr" | "bleeding" | "road_accident" | "choking_adult" | "choking_infant" | "burns" | "seizure" | "electric_shock" | "drowning" | "fire" | "flood" | "earthquake" | "snakebite" | "heatstroke" | "poisoning" | "none",
  "requires_human_escalation": boolean (true if severe danger, worsening unconsciousness, active fire, trapped persons, or reporter panicking)
}}

IMPORTANT RULES:
- Never hallucinate non-standard medical procedures.
- Do NOT output markdown code blocks or text outside the JSON object.
- If the situation is choking, road accident, cardiac arrest, or severe bleeding, prioritize immediate action before lengthy explanations.
"""

    @classmethod
    async def generate_response(
        cls,
        incident_context: dict[str, Any],
        conversation_history: list[dict[str, str]],
        user_message: str | None = None,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Calls OpenRouter LLM with incident context and conversation history.
        Returns validated structured emergency response with video recommendations.
        """
        s = settings()
        api_key = s.openrouter_api_key or s.openai_api_key
        base_url = s.openai_base_url.rstrip("/")
        selected_model = s.openrouter_model or s.openai_model or FALLBACK_MODELS[0]

        # Clean language
        lang = language if language in LANGUAGE_MAP else "en"

        # Construct prompt
        system_prompt = cls.get_system_prompt(lang)

        # Context summary
        incident_summary = (
            f"INCIDENT REPORT SUMMARY:\n"
            f"- Case ID: {incident_context.get('case_id', 'Unknown')}\n"
            f"- Category: {incident_context.get('category', 'Emergency')}\n"
            f"- Description: {incident_context.get('description', 'Emergency reported')}\n"
            f"- Location: {incident_context.get('address', 'Current Location')}\n"
            f"- Severity: {incident_context.get('severity', 'High')}\n"
            f"- Affected Count: {incident_context.get('people_affected', 'Unknown')}\n"
            f"- Status: Responders alerted / in dispatch queue.\n"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{incident_summary}\nInitiate emergency assessment and initial guidance."}
        ]

        # Add history
        for msg in conversation_history[-8:]:
            role = "assistant" if msg.get("speaker") in ("ai", "assistant", "system") else "user"
            messages.append({"role": role, "content": msg.get("content", "")})

        if user_message:
            messages.append({"role": "user", "content": user_message})

        # Do not call a third party without an explicitly configured key. The
        # deterministic safety engine below remains available during outages.
        if not api_key:
            parsed_result = cls._build_rule_based_response(incident_context, user_message, lang)
            parsed_result["provider_status"] = "OpenRouter is not configured; verified safety fallback is active."
            parsed_result["video"] = find_video_for_situation(
                f"{incident_context.get('category', '')} {incident_context.get('description', '')} {user_message or ''}",
                incident_context.get("category", ""),
            )
            parsed_result["language"] = lang
            return parsed_result

        # Try configured model with documented fallbacks.
        models_to_try = [selected_model] + [m for m in FALLBACK_MODELS if m != selected_model]
        parsed_result = None
        last_error = ""

        async with httpx.AsyncClient(timeout=25.0) as client:
            for model_name in models_to_try:
                try:
                    payload = {
                        "model": model_name,
                        "messages": messages,
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                        "max_tokens": 800,
                    }
                    res = await client.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://tera.app",
                            "X-Title": "TERA Emergency Companion",
                        },
                        json=payload,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        raw_content = data["choices"][0]["message"]["content"].strip()
                        # Clean potential backticks
                        if raw_content.startswith("```json"):
                            raw_content = raw_content[7:]
                        if raw_content.startswith("```"):
                            raw_content = raw_content[3:]
                        if raw_content.endswith("```"):
                            raw_content = raw_content[:-3]
                        raw_content = raw_content.strip()

                        parsed = json.loads(raw_content)
                        if isinstance(parsed, dict) and "message" in parsed:
                            parsed_result = parsed
                            break
                    else:
                        last_error = f"Model {model_name} HTTP {res.status_code}: {res.text[:100]}"
                except Exception as e:
                    last_error = f"Model {model_name} error: {str(e)}"
                    continue

        # If LLM failed, construct graceful rule-based fallback
        if not parsed_result:
            logger.warning(f"AI LLM generation fallback triggered: {last_error}")
            parsed_result = cls._build_rule_based_response(incident_context, user_message, lang)

        # The most recent citizen message takes precedence over the initial
        # category: a road collision can become a CPR emergency.
        video_info = find_video_for_situation(
            f"{user_message or ''} {parsed_result.get('message', '')}", ""
        )
        vid_cat = parsed_result.get("video_category", "")
        if not video_info and vid_cat and vid_cat != "none" and vid_cat in VERIFIED_EMERGENCY_VIDEOS:
            video_info = VERIFIED_EMERGENCY_VIDEOS[vid_cat]
        elif not video_info:
            # Automatic heuristic detection based on combined context
            context_text = f"{incident_context.get('category', '')} {incident_context.get('description', '')} {user_message or ''} {parsed_result.get('message', '')}"
            video_info = find_video_for_situation(context_text, incident_context.get("category", ""))

        parsed_result["video"] = video_info
        parsed_result["language"] = lang
        return parsed_result

    @classmethod
    def _build_rule_based_response(
        cls, incident_context: dict[str, Any], user_message: str | None, language: str
    ) -> dict[str, Any]:
        """Ensures the companion NEVER crashes even if external network/LLM is down."""
        cat = (incident_context.get("category") or "medical").lower()
        desc = (incident_context.get("description") or "").lower()
        combined = f"{cat} {desc} {user_message or ''}"

        # Default English messages
        msg = "If there is immediate danger, call 112 now. Stay calm and keep yourself and the affected persons safe."
        question = "Are you in a safe position right now away from moving vehicles or hazards?"
        actions = [
            "Ensure the immediate area is safe before approaching.",
            "Do not move the injured person unless there is danger of fire or collapse.",
            "Stay on the line and follow instructions."
        ]
        urgency = "HIGH"
        vid_key = "none"

        if any(k in combined for k in ["cardiac", "unresponsive", "not breathing", "cpr", "collapsed"]):
            urgency = "CRITICAL"
            vid_key = "cpr"
            msg = "Call 112 immediately. Check if the person responds or is breathing. If they are not breathing, begin chest compressions immediately in the center of the chest."
            question = "Is the person breathing or responding when you shout?"
            actions = [
                "Check breathing for 10 seconds.",
                "Begin firm, fast chest compressions (100-120 bpm) in center of chest.",
                "Send someone nearby to find an Automated External Defibrillator (AED)."
            ]
        elif any(k in combined for k in ["bleed", "blood", "artery", "cut"]):
            urgency = "CRITICAL"
            vid_key = "bleeding"
            msg = "Apply firm, continuous direct pressure to the wound with a clean cloth or towel. Do not release pressure to check."
            question = "Is the bleeding slowing down with direct pressure?"
            actions = [
                "Press firmly on the wound with a clean cloth or pad.",
                "Keep the person lying down and warm.",
                "If blood soaks through, place another pad on top and press harder."
            ]
        elif any(k in combined for k in ["accident", "collision", "crash", "car", "bike"]):
            urgency = "HIGH"
            vid_key = "road_accident"
            msg = "Make sure you are safe from oncoming traffic. Turn on hazard lights. Do not move injured victims unless there is immediate danger of fire."
            question = "Are any victims trapped inside the vehicle or lying on the road?"
            actions = [
                "Turn off vehicle ignitions if safely accessible.",
                "Keep casualty's head and neck still.",
                "Direct traffic away from the crash site."
            ]
        elif any(k in combined for k in ["fire", "smoke"]):
            urgency = "CRITICAL"
            vid_key = "fire"
            msg = "Evacuate the building immediately. Stay low under the smoke where air is cleaner. Do not use elevators."
            question = "Are you and others completely outside the building?"
            actions = [
                "Evacuate via stairs immediately.",
                "Feel doors before opening; do not open hot doors.",
                "Assemble at a safe distance outside."
            ]

        # Multi-language translations for fallback
        if language == "te":
            msg = "తక్షణ ప్రమాదం ఉంటే ఇప్పుడు 112 కు కాల్ చేయండి. ప్రశాంతంగా ఉండండి మరియు బాధితులను సురక్షితంగా ఉంచండి."
            question = "మీరు ప్రస్తుతం సురక్షితమైన ప్రదేశంలో ఉన్నారా?"
        elif language == "hi":
            msg = "तत्काल खतरा हो तो अभी 112 पर कॉल करें। शांत रहें और स्वयं को तथा प्रभावित लोगों को सुरक्षित रखें।"
            question = "क्या आप अभी सुरक्षित स्थान पर हैं?"
        elif language == "ta":
            msg = "உடனடி ஆபத்து இருந்தால் இப்போது 112-ஐ அழைக்கவும். அமைதியாக இருந்து அனைவரையும் பாதுகாப்பாக வைத்திருங்கள்."
            question = "நீங்கள் இப்போது பாதுகாப்பான இடத்தில் இருக்கிறீர்களா?"
        elif language == "kn":
            msg = "ತಕ್ಷಣದ ಅಪಾಯವಿದ್ದರೆ ಈಗ 112 ಗೆ ಕರೆ ಮಾಡಿ. ಶಾಂತರಾಗಿರಿ ಮತ್ತು ಸಂತ್ರಸ್ತರನ್ನು ಸುರಕ್ಷಿತವಾಗಿಡಿ."
            question = "ನೀವು ಈಗ ಸುರಕ್ಷಿತವಾಗಿದ್ದೀರಾ?"
        elif language == "ml":
            msg = "ഉടൻ അപകടമുണ്ടെങ്കിൽ ഇപ്പോൾ 112-ലേക്ക് വിളിക്കുക. ശാന്തരായി എല്ലാവരെയും സുരക്ഷിതരാക്കുക."
            question = "നിങ്ങൾ ഇപ്പോൾ സുരക്ഷിതമായ സ്ഥാനത്താണോ?"

        return {
            "message": msg,
            "follow_up_question": question,
            "urgency": urgency,
            "risk_assessment": f"Emergency assessment for {cat}: active triage.",
            "immediate_actions": actions,
            "video_category": vid_key,
            "requires_human_escalation": urgency == "CRITICAL",
        }

    # =========================================================================
    # Sarvam AI Voice: Speech-to-Text (STT)
    # =========================================================================

    @classmethod
    async def transcribe_audio(
        cls, audio_bytes: bytes, filename: str = "recording.webm", language: str = "en"
    ) -> dict[str, Any]:
        """
        Transcribes speech audio using Sarvam AI Speech-to-Text API.
        Supports Indian English and regional languages (te, hi, ta, kn, ml).
        """
        s = settings()
        api_key = s.sarvam_api_key
        if not api_key:
            return {"transcript": "", "error": "SARVAM_API_KEY is not configured"}

        lang_code = LANGUAGE_MAP.get(language, LANGUAGE_MAP["en"])["code"]

        try:
            # Sarvam STT expects multipart form data with file and model
            files = {
                "file": (filename, audio_bytes, "audio/webm")
            }
            data = {
                "model": "saaras:v3",
                "language_code": lang_code,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    "https://api.sarvam.ai/speech-to-text",
                    headers={"api-subscription-key": api_key},
                    files=files,
                    data=data,
                )

                if res.status_code == 200:
                    payload = res.json()
                    transcript = payload.get("transcript", "").strip()
                    return {
                        "transcript": transcript,
                        "language_code": payload.get("language_code", lang_code),
                    }
                else:
                    logger.warning(f"Sarvam STT returned status {res.status_code}: {res.text}")
                    return {"transcript": "", "error": f"STT failed with code {res.status_code}"}
        except Exception as e:
            logger.error(f"Sarvam STT exception: {e}")
            return {"transcript": "", "error": str(e)}

    # =========================================================================
    # Sarvam AI Voice: Text-to-Speech (TTS)
    # =========================================================================

    @classmethod
    async def synthesize_speech(
        cls, text: str, language: str = "en"
    ) -> dict[str, Any]:
        """
        Synthesizes emergency operator speech using Sarvam AI Bulbul TTS API.
        Returns base64 encoded audio string ready for browser HTML5 audio element.
        """
        s = settings()
        api_key = s.sarvam_api_key
        if not api_key or not text.strip():
            return {"audio_base64": None, "error": "TTS unavailable or empty text"}

        cfg = LANGUAGE_MAP.get(language, LANGUAGE_MAP["en"])
        lang_code = cfg["code"]
        speaker = cfg["speaker"]

        # Truncate clean text for fast TTS generation (up to 500 chars)
        clean_text = text[:480].strip()

        try:
            payload = {
                "inputs": [clean_text],
                "target_language_code": lang_code,
                "speaker": speaker,
                "model": "bulbul:v3",
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    "https://api.sarvam.ai/text-to-speech",
                    headers={
                        "api-subscription-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

                if res.status_code == 200:
                    data = res.json()
                    audios = data.get("audios", [])
                    if audios and len(audios) > 0:
                        return {
                            "audio_base64": audios[0],
                            "format": "audio/wav",
                            "language": lang_code,
                            "speaker": speaker,
                        }
                logger.warning(f"Sarvam TTS failed {res.status_code}: {res.text[:120]}")
                return {"audio_base64": None, "error": f"TTS status {res.status_code}"}
        except Exception as e:
            logger.error(f"Sarvam TTS exception: {e}")
            return {"audio_base64": None, "error": str(e)}
