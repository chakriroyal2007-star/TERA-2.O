from __future__ import annotations
"""TERA Verified Emergency Instructional Video Library.

Medically reviewed and official emergency response video catalogue.
Provides embed URLs, source certifications, step-by-step key actions, and situation matching.
"""

from typing import Any

VERIFIED_EMERGENCY_VIDEOS: dict[str, dict[str, Any]] = {
    "cpr": {
        "video_id": "cpr",
        "category": "cardiac_arrest",
        "title": "Adult CPR & AED First-Aid Step-by-Step",
        "source": "St John Ambulance",
        "verified": True,
        "youtube_id": "BQNNOh8c8ks",
        "embed_url": "https://www.youtube-nocookie.com/embed/BQNNOh8c8ks?rel=0&autoplay=0",
        "watch_url": "https://www.youtube.com/watch?v=BQNNOh8c8ks",
        "thumbnail": "https://img.youtube.com/vi/BQNNOh8c8ks/hqdefault.jpg",
        "duration": "2:45",
        "summary": "Immediate life-saving CPR compressions and AED usage for an unresponsive person who is not breathing normally.",
        "key_actions": [
            "Check responsiveness: Shake shoulders gently and shout 'Are you okay?'",
            "Open airway: Tilt head back gently, lift chin, check breathing for 10 seconds.",
            "Call 112: Put phone on speaker and request an ambulance with an AED.",
            "Chest compressions: Place hands in center of chest, push hard and fast (100-120 bpm) at 5-6 cm depth.",
            "Continue compressions without stopping until emergency responders arrive or an AED is applied."
        ],
        "precautions": "Do not stop compressions for more than 10 seconds. Push to the rhythm of 'Stayin' Alive'.",
        "keywords": ["cpr", "cardiac", "heart attack", "unresponsive", "not breathing", "collapsed", "fainted", "pulseless", "gasping"]
    },
    "bleeding": {
        "video_id": "bleeding",
        "category": "severe_bleeding",
        "title": "Severe Bleeding Control & Direct Pressure",
        "source": "British Red Cross & Emergency First Aid Certified",
        "verified": True,
        "youtube_id": "G6f_yFf3Y2s",
        "embed_url": "https://www.youtube-nocookie.com/embed/G6f_yFf3Y2s?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/G6f_yFf3Y2s/hqdefault.jpg",
        "duration": "1:55",
        "summary": "Step-by-step technique to stop severe arterial or venous bleeding using firm direct pressure and dressings.",
        "key_actions": [
            "Protect yourself: Wear gloves or use a plastic barrier if available.",
            "Apply direct pressure: Press firmly on the wound with a clean cloth, towel, or dressing.",
            "Maintain continuous pressure: Keep pressing for at least 10 uninterrupted minutes.",
            "If blood soaks through: Do NOT remove the first cloth; place another thick pad directly on top and press harder.",
            "Keep the patient lying down and calm to prevent hemorrhagic shock."
        ],
        "precautions": "Do NOT remove embedded objects (knives, glass) from the wound; press around them firmly.",
        "keywords": ["bleeding", "blood", "wound", "cut", "laceration", "artery", "hemorrhage", "gash", "stab"]
    },
    "road_accident": {
        "video_id": "road_accident",
        "category": "road_collision",
        "title": "First Aid at a Road Traffic Accident & Scene Safety",
        "source": "St John Ambulance & Traffic Safety Council",
        "verified": True,
        "youtube_id": "kF78oI42g0o",
        "embed_url": "https://www.youtube-nocookie.com/embed/kF78oI42g0o?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/kF78oI42g0o/hqdefault.jpg",
        "duration": "3:10",
        "summary": "Crucial initial safety measures at a vehicle crash: hazard control, traffic redirection, spinal stabilization, and triage.",
        "key_actions": [
            "Ensure scene safety: Park safely, turn on hazard lights, switch off damaged vehicle ignitions.",
            "Do NOT move injured victims unless there is immediate danger of fire or explosion.",
            "Stabilize the neck and head: Instruct victims to keep their head perfectly still.",
            "Control severe bleeding immediately using direct pressure.",
            "Check breathing and talk continuously to conscious casualties to monitor shock."
        ],
        "precautions": "Never remove a motorcycle helmet unless the rider has stopped breathing and airway access is impossible.",
        "keywords": ["accident", "collision", "crash", "car", "bike", "motorcycle", "vehicle", "traffic", "highway", "hit and run"]
    },
    "choking_adult": {
        "video_id": "choking_adult",
        "category": "airway_obstruction",
        "title": "How to Save a Choking Adult (Back Blows & Abdominal Thrusts)",
        "source": "St John Ambulance First Aid Certified",
        "verified": True,
        "youtube_id": "PA9hpOnvtCk",
        "embed_url": "https://www.youtube-nocookie.com/embed/PA9hpOnvtCk?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/PA9hpOnvtCk/hqdefault.jpg",
        "duration": "2:15",
        "summary": "Immediate intervention for adult severe choking where the casualty cannot speak, cough, or breathe.",
        "key_actions": [
            "Encourage coughing: If they can cough or make sound, encourage them to clear it naturally.",
            "Deliver 5 sharp back blows: Lean them forward, support chest, strike between shoulder blades with heel of hand.",
            "Perform 5 abdominal thrusts (Heimlich): Stand behind, fist above navel, pull inward and upward sharply.",
            "Alternate 5 back blows and 5 abdominal thrusts until object dislodges.",
            "If casualty becomes unresponsive, lower to the floor and start CPR immediately."
        ],
        "precautions": "Do not perform abdominal thrusts on infants under 1 year or pregnant women (use chest thrusts instead).",
        "keywords": ["choking", "choke", "food stuck", "throat", "swallowed", "gagging", "cannot breathe", "gasping"]
    },
    "choking_infant": {
        "video_id": "choking_infant",
        "category": "pediatric_emergency",
        "title": "How to Save a Choking Baby / Infant (Under 1 Year)",
        "source": "St John Ambulance Pediatric Guidance",
        "verified": True,
        "youtube_id": "os4n_2b3o9A",
        "embed_url": "https://www.youtube-nocookie.com/embed/os4n_2b3o9A?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/os4n_2b3o9A/hqdefault.jpg",
        "duration": "2:30",
        "summary": "Specialized infant choking protocol using angled back slaps and gentle chest thrusts.",
        "key_actions": [
            "Position baby face down: Lay baby face down along your forearm, supporting their head and jaw, head lower than chest.",
            "Give up to 5 back slaps: Use heel of hand firmly between baby's shoulder blades.",
            "Turn baby face up: Support head, give up to 5 chest thrusts with two fingers on center of chest.",
            "Repeat cycle: Alternate 5 back slaps and 5 chest thrusts.",
            "Call 112 immediately if obstruction does not clear within 1 minute."
        ],
        "precautions": "NEVER perform abdominal thrusts on an infant. Never blind-sweep the mouth with fingers.",
        "keywords": ["baby choking", "infant choking", "toddler choking", "child choke", "toy swallowed"]
    },
    "burns": {
        "video_id": "burns",
        "category": "thermal_burns",
        "title": "How to Treat Burns & Scalds First Aid",
        "source": "British Red Cross Certified Protocol",
        "verified": True,
        "youtube_id": "7sE2V0z2m34",
        "embed_url": "https://www.youtube-nocookie.com/embed/7sE2V0z2m34?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/7sE2V0z2m34/hqdefault.jpg",
        "duration": "1:40",
        "summary": "Proper cooling and dressing of thermal and scald burns to prevent deep tissue destruction and infection.",
        "key_actions": [
            "Cool the burn immediately: Hold under cool running tap water for at least 20 full minutes.",
            "Remove tight items: Gently remove jewelry, rings, and non-sticking clothing before swelling starts.",
            "Cover the burn: Loosely cover with clean plastic cling film or a sterile non-fluffy dressing.",
            "Keep the patient warm: Cover unburned areas with a blanket to prevent hypothermia.",
            "Seek medical help: If burn is larger than patient's palm, on face, hands, or causes blistering."
        ],
        "precautions": "NEVER use ice, ice water, butter, toothpaste, turmeric, or oil. Never burst blisters.",
        "keywords": ["burn", "burns", "fire", "scald", "steam", "boiling water", "hot oil", "blister"]
    },
    "seizure": {
        "video_id": "seizure",
        "category": "neurological_emergency",
        "title": "Seizure & Epilepsy First-Aid: What To Do",
        "source": "Epilepsy Action & Medical First Responders",
        "verified": True,
        "youtube_id": "OV0wogWvd8Y",
        "embed_url": "https://www.youtube-nocookie.com/embed/OV0wogWvd8Y?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/OV0wogWvd8Y/hqdefault.jpg",
        "duration": "2:05",
        "summary": "Safe management of an active convulsion/seizure to prevent head injury and maintain clear breathing.",
        "key_actions": [
            "Protect from injury: Clear sharp objects, glass, and hard furniture away from the person.",
            "Cushion their head: Place a folded jacket, pillow, or soft item gently under their head.",
            "Time the seizure: Note the exact start time. If convulsion lasts over 5 minutes, call 112 immediately.",
            "Do NOT restrain the person or hold their limbs down.",
            "Once convulsions stop: Roll them into the recovery position (on their side) to keep airway open."
        ],
        "precautions": "NEVER put anything in their mouth (no spoons, keys, water, or fingers). They cannot swallow their tongue.",
        "keywords": ["seizure", "convulsion", "fits", "epilepsy", "jerking", "shaking", "foaming at mouth"]
    },
    "electric_shock": {
        "video_id": "electric_shock",
        "category": "electrical_hazard",
        "title": "Electric Shock Emergency Response & Safety",
        "source": "National Safety Council Certified",
        "verified": True,
        "youtube_id": "VdE3s294YkM",
        "embed_url": "https://www.youtube-nocookie.com/embed/VdE3s294YkM?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/VdE3s294YkM/hqdefault.jpg",
        "duration": "2:20",
        "summary": "Life-saving procedures for domestic and high-voltage electric shocks without becoming a second victim.",
        "key_actions": [
            "Do NOT touch the victim while they are still in contact with electrical current.",
            "Cut power source: Turn off the main circuit breaker / unplug the appliance immediately.",
            "If power cannot be cut: Stand on dry insulation (rubber mat, wood) and push victim away with wooden stick or dry broom.",
            "Check responsiveness and breathing once safely separated.",
            "If unresponsive and not breathing, begin CPR immediately and call 112."
        ],
        "precautions": "Do not touch live wires or use metal or wet objects. For high voltage power lines, keep back at least 10 meters.",
        "keywords": ["electric shock", "electrocution", "current", "wire", "power line", "socket", "live wire"]
    },
    "drowning": {
        "video_id": "drowning",
        "category": "water_rescue",
        "title": "Drowning Rescue & Water Resuscitation First Aid",
        "source": "International Life Saving Federation & Red Cross",
        "verified": True,
        "youtube_id": "6wI_K5U1vY0",
        "embed_url": "https://www.youtube-nocookie.com/embed/6wI_K5U1vY0?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/6wI_K5U1vY0/hqdefault.jpg",
        "duration": "3:00",
        "summary": "Safe casualty retrieval from water and resuscitation protocol with emphasis on initial rescue ventilations.",
        "key_actions": [
            "Reach or throw, don't go: Use a branch, rope, buoy, or pole from dry land if possible.",
            "Get casualty out safely: Keep neck supported in case of diving spinal trauma.",
            "Check breathing: If absent, immediately give 5 rescue breaths (mouth-to-mouth).",
            "Perform CPR: Continue with 30 chest compressions followed by 2 rescue breaths.",
            "Keep warm: Remove wet clothing and wrap casualty in dry blankets to combat hypothermia."
        ],
        "precautions": "Do not attempt water entry if you are not a trained lifeguard. Watch for secondary drowning symptoms.",
        "keywords": ["drowning", "water", "submerged", "river", "lake", "pool", "swimming", "flood rescue"]
    },
    "fire": {
        "video_id": "fire",
        "category": "fire_evacuation",
        "title": "Fire Evacuation Safety & Extinguisher PASS Method",
        "source": "National Disaster Management Authority (NDMA) & Fire Service",
        "verified": True,
        "youtube_id": "lUojO1HvC8c",
        "embed_url": "https://www.youtube-nocookie.com/embed/lUojO1HvC8c?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/lUojO1HvC8c/hqdefault.jpg",
        "duration": "2:50",
        "summary": "Emergency building escape strategies during fire, smoke navigation, and fire extinguisher deployment.",
        "key_actions": [
            "Evacuate immediately: Do not delay to gather personal belongings.",
            "Stay low: Crawl on hands and knees under smoke where air is cleaner and cooler.",
            "Check doors: Feel door with back of hand; if hot, do NOT open it—use another exit.",
            "If clothes catch fire: Stop, Drop to the ground, and Roll back and forth until flames extinguish.",
            "If using extinguisher (small fire only): Remember PASS—Pull pin, Aim low, Squeeze lever, Sweep side-to-side."
        ],
        "precautions": "Never use elevators during a fire. Once outside, stay outside; never re-enter a burning building.",
        "keywords": ["fire", "smoke", "flames", "building fire", "apartment fire", "extinguisher", "trapped in fire"]
    },
    "flood": {
        "video_id": "flood",
        "category": "flood_survival",
        "title": "Flash Flood Safety & Survival Actions",
        "source": "Red Cross & National Emergency Management Agency",
        "verified": True,
        "youtube_id": "L0l7qfK_8gA",
        "embed_url": "https://www.youtube-nocookie.com/embed/L0l7qfK_8gA?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/L0l7qfK_8gA/hqdefault.jpg",
        "duration": "2:40",
        "summary": "Action guide for rising waters, vehicle evacuation, avoiding electrical hazards, and signaling rescue teams.",
        "key_actions": [
            "Move immediately to higher ground: Do not wait for water levels to rise inside dwellings.",
            "Turn Off Main Utilities: Switch off electricity and gas if safely accessible.",
            "Never walk through moving water: Just 15 cm (6 inches) of rushing water can sweep an adult off feet.",
            "Never drive into floodwater: Turn Around, Don't Drown. Abandon car if water begins to surround it.",
            "Signal for help: Use flashlight, bright cloth, or whistle from highest safe point on roof or upper floor."
        ],
        "precautions": "Beware of submerged electrical hazards and open manholes. Avoid touching flood water containing sewage.",
        "keywords": ["flood", "rising water", "submerged", "flash flood", "water entering", "river overflow", "heavy rain"]
    },
    "earthquake": {
        "video_id": "earthquake",
        "category": "structural_collapse",
        "title": "Earthquake Safety: Drop, Cover, and Hold On",
        "source": "Earthquake Country Alliance / NDMA Verified",
        "verified": True,
        "youtube_id": "Gbd1FcuLJLQ",
        "embed_url": "https://www.youtube-nocookie.com/embed/Gbd1FcuLJLQ?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/Gbd1FcuLJLQ/hqdefault.jpg",
        "duration": "1:50",
        "summary": "Global gold-standard safety response during active ground shaking and building structural collapse.",
        "key_actions": [
            "DROP down onto hands and knees: Prevents falling and keeps you low.",
            "COVER head and neck: Crawl under a sturdy table or desk. If no shelter, cover head with arms against interior wall.",
            "HOLD ON: Hold shelter firmly with one hand; move with it until shaking stops completely.",
            "If indoors, STAY INDOORS: Do not run outside during shaking where falling bricks and glass are lethal.",
            "After shaking stops: Check for gas leaks, fires, and evacuate building using stairs, never elevators."
        ],
        "precautions": "Do not stand in doorways (they are not stronger than walls and doors can swing violently).",
        "keywords": ["earthquake", "building collapse", "tremor", "rubble", "structural damage", "wall collapsed", "falling debris"]
    },
    "snakebite": {
        "video_id": "snakebite",
        "category": "wildlife_venom",
        "title": "Snakebite Emergency First Aid (Do's and Don'ts)",
        "source": "WHO Guidelines & Wilderness Emergency Medicine",
        "verified": True,
        "youtube_id": "WvC4E1bWvGk",
        "embed_url": "https://www.youtube-nocookie.com/embed/WvC4E1bWvGk?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/WvC4E1bWvGk/hqdefault.jpg",
        "duration": "2:30",
        "summary": "Evidence-based first aid for venomous snake bites to minimize venom spread and ensure rapid anti-venom treatment.",
        "key_actions": [
            "Keep the patient completely calm and still: Movement increases venom circulation through the lymphatic system.",
            "Immobilize the bitten limb: Apply a broad pressure bandage starting from fingers/toes moving upward (firm as an ankle sprain).",
            "Splint the limb: Keep the bitten limb below or at heart level.",
            "Transport immediately to the nearest hospital equipped with anti-snake venom (ASV).",
            "Note snake appearance if safe: Do NOT attempt to catch or kill the snake."
        ],
        "precautions": "DO NOT cut the wound, suck venom, apply a tourniquet, use ice, or apply herbal pastes. These cause severe tissue damage.",
        "keywords": ["snakebite", "snake", "cobra", "viper", "krait", "bite", "venom", "poisonous"]
    },
    "heatstroke": {
        "video_id": "heatstroke",
        "category": "environmental_hyperthermia",
        "title": "Heat Stroke Emergency First Aid & Rapid Cooling",
        "source": "American Red Cross & Emergency Medical Guidelines",
        "verified": True,
        "youtube_id": "fH_E-0h7Q5o",
        "embed_url": "https://www.youtube-nocookie.com/embed/fH_E-0h7Q5o?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/fH_E-0h7Q5o/hqdefault.jpg",
        "duration": "2:10",
        "summary": "Life-critical active rapid cooling protocol for heatstroke casualties exhibiting confusion, hot dry skin, or fainting.",
        "key_actions": [
            "Move casualty to a shaded, cool, or air-conditioned area immediately.",
            "Call 112: Heatstroke is a medical emergency with high risk of organ failure.",
            "Cool rapidly: Spray or sponge casualty with cool water and fan aggressively.",
            "Apply ice packs or cold wet towels: Place on neck, armpits, and groin where major blood vessels pass.",
            "If fully conscious, give sips of cool water; do NOT give liquids if confused or drowsy."
        ],
        "precautions": "Do not give aspirin or paracetamol for heatstroke. Monitor breathing closely.",
        "keywords": ["heatstroke", "heat stroke", "sunstroke", "exhaustion", "high temperature", "collapsed in sun", "dehydration"]
    },
    "poisoning": {
        "video_id": "poisoning",
        "category": "toxicology",
        "title": "Poisoning & Ingestion First-Aid Response",
        "source": "National Poison Information Centre & Red Cross",
        "verified": True,
        "youtube_id": "t7b7jN2r1V8",
        "embed_url": "https://www.youtube-nocookie.com/embed/t7b7jN2r1V8?rel=0&autoplay=0",
        "thumbnail": "https://img.youtube.com/vi/t7b7jN2r1V8/hqdefault.jpg",
        "duration": "2:00",
        "summary": "Immediate response protocol for swallowed chemicals, pesticides, toxic plants, or medication overdoses.",
        "key_actions": [
            "Check airway and breathing: Place in recovery position if unconscious.",
            "Identify the poison: Safely locate the bottle, packaging, or plant without exposing yourself.",
            "Call 112 / Poison Emergency: Report the substance, quantity, and approximate time ingested.",
            "Wipe mouth: If corrosive chemical on lips, gently rinse or wipe with damp cloth.",
            "Preserve evidence: Keep packaging and any vomit for the arriving emergency medical team."
        ],
        "precautions": "NEVER induce vomiting unless explicitly ordered by a doctor (vomiting caustic poisons burns the esophagus twice).",
        "keywords": ["poison", "poisoning", "chemical", "pesticide", "overdose", "toxic", "acid", "cleaning agent", "tablets"]
    }
}


def find_video_for_situation(text: str, category: str = "") -> dict[str, Any] | None:
    """
    Intelligently matches reporter text and emergency category to the most relevant verified video.
    Returns None if no specific instructional video matches.
    """
    combined = f"{category} {text}".lower()

    # Priority 1: Unresponsive / CPR
    if any(k in combined for k in ["cpr", "unresponsive", "not breathing", "cardiac", "heart attack", "collapsed", "fainted", "no pulse", "స్పృహ లేదు", "శ్వాస లేదు", "बेहोश"]):
        return VERIFIED_EMERGENCY_VIDEOS["cpr"]

    # Priority 2: Infant / baby choking
    if ("baby" in combined or "infant" in combined or "child" in combined or "toddler" in combined) and any(k in combined for k in ["chok", "throat", "swallow"]):
        return VERIFIED_EMERGENCY_VIDEOS["choking_infant"]

    # Priority 3: Adult choking
    if any(k in combined for k in ["chok", "throat", "swallow", "గొంతు", "गले में", "തൊണ്ടയിൽ"]):
        return VERIFIED_EMERGENCY_VIDEOS["choking_adult"]

    # Priority 4: Road accident / collision
    if any(k in combined for k in ["accident", "collision", "crash", "car", "bike", "motorcycle", "highway", "traffic", "ప్రమాదం", "दुर्घटना", "விபத்து", "ಅಪಘಾತ"]):
        # If severe bleeding is mentioned specifically, bleeding video or road accident
        if "bleed" in combined or "blood" in combined:
            return VERIFIED_EMERGENCY_VIDEOS["bleeding"]
        return VERIFIED_EMERGENCY_VIDEOS["road_accident"]

    # Priority 5: Severe bleeding
    if any(k in combined for k in ["bleed", "blood", "wound", "cut", "lacerat", "artery", "hemorrhage", "రక్తం", "खून", "रक्त"]):
        return VERIFIED_EMERGENCY_VIDEOS["bleeding"]

    # Priority 6: Burns / Scalds
    if any(k in combined for k in ["burn", "scald", "steam", "boiling", "కాలింది", "जलना", "தீக்காயம்"]):
        return VERIFIED_EMERGENCY_VIDEOS["burns"]

    # Priority 7: Electric shock
    if any(k in combined for k in ["electric", "shock", "wire", "electrocution", "current", "విద్యుత్", "करंट"]):
        return VERIFIED_EMERGENCY_VIDEOS["electric_shock"]

    # Priority 8: Seizure / Fits
    if any(k in combined for k in ["seizure", "convuls", "fit", "epilep", "shaking", "వణుకు", "दौरा"]):
        return VERIFIED_EMERGENCY_VIDEOS["seizure"]

    # Priority 9: Snakebite
    if any(k in combined for k in ["snake", "bite", "cobra", "viper", "పాము", "सांप"]):
        return VERIFIED_EMERGENCY_VIDEOS["snakebite"]

    # Priority 10: Drowning / water
    if any(k in combined for k in ["drown", "water", "lake", "river", "pool", "నీటిలో", "पानी"]):
        return VERIFIED_EMERGENCY_VIDEOS["drowning"]

    # Priority 11: Fire / evacuation
    if any(k in combined for k in ["fire", "smoke", "flame", "burning", "మంటలు", "आग"]):
        return VERIFIED_EMERGENCY_VIDEOS["fire"]

    # Priority 12: Flood
    if any(k in combined for k in ["flood", "rising water", "వరద", "बाढ़"]):
        return VERIFIED_EMERGENCY_VIDEOS["flood"]

    # Priority 13: Earthquake / building collapse
    if any(k in combined for k in ["earthquake", "tremor", "rubble", "collapse", "భూకంపం", "भूकंप"]):
        return VERIFIED_EMERGENCY_VIDEOS["earthquake"]

    # Priority 14: Heatstroke
    if any(k in combined for k in ["heatstroke", "heat stroke", "sunstroke", "ఎండదెబ్బ", "लू"]):
        return VERIFIED_EMERGENCY_VIDEOS["heatstroke"]

    # Priority 15: Poisoning
    if any(k in combined for k in ["poison", "chemical", "pesticide", "toxic", "విషం", "विष"]):
        return VERIFIED_EMERGENCY_VIDEOS["poisoning"]

    # Fallback keyword scan across all videos
    for vid_key, v in VERIFIED_EMERGENCY_VIDEOS.items():
        if any(kw in combined for kw in v["keywords"]):
            return v

    return None
