import re
from dataclasses import dataclass, field
from ..planner_rule_config import APPOINTMENT_RULE_CONFIG, CONSULTATION_RULE_CONFIG, PATIENT_HISTORY_RULE_CONFIG

@dataclass
class ParsedIntent:
    original_text: str = ""
    intent_type: str | None = None
    entities: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    report_type: str | None = None
    history_type: str | None = None
    comparison_requested: bool = False
    latest_requested: bool = False
    is_appointment: bool = False
    is_consultation: bool = False
    is_history: bool = False
    doctor_name: str | None = None
    booking_datetime: str | None = None
    booking_ordinal: str | None = None

def parse_intent(text: str) -> ParsedIntent:
    intent = ParsedIntent(original_text=text)
    
    # Appointment extraction
    has_appointment_entity = any(entity in text for entity in APPOINTMENT_RULE_CONFIG["entities"])
    has_appointment_action = False
    
    for action_key, action_aliases in APPOINTMENT_RULE_CONFIG["appointment_actions"].items():
        if any(a in text for a in action_aliases):
            has_appointment_action = True
            if action_key not in intent.actions:
                intent.actions.append(action_key)
                
    if has_appointment_entity and has_appointment_action:
        intent.is_appointment = True
        intent.intent_type = "appointment"
        intent.entities.extend([e for e in APPOINTMENT_RULE_CONFIG["entities"] if e in text])
        
    # Consultation extraction
    if any(entity in text for entity in CONSULTATION_RULE_CONFIG["entities"]):
        intent.is_consultation = True
        intent.intent_type = "symptom"
        intent.entities.extend([e for e in CONSULTATION_RULE_CONFIG["entities"] if e in text])
    elif any(trigger in text for trigger in CONSULTATION_RULE_CONFIG["consultation_triggers"]):
        intent.is_consultation = True
        intent.intent_type = "consultation"
        
    for action_key, action_aliases in CONSULTATION_RULE_CONFIG.get("consultation_actions", {}).items():
        if any(a in text for a in action_aliases):
            if action_key not in intent.actions:
                intent.actions.append(action_key)

    # Patient History extraction
    if any(kw in text for kw in PATIENT_HISTORY_RULE_CONFIG["trigger_phrases"]):
        intent.is_history = True
        intent.intent_type = "patient_history"
        
        for htype in PATIENT_HISTORY_RULE_CONFIG["history_types"]:
            if htype in text or htype + "s" in text or (htype == "condition" and "diagnosed" in text):
                intent.history_type = htype
                break

    # Extract doctor name using regex – try multiple common patterns
    lowered = text.lower()
    doc_match = None

    # Pattern 1: "doctor X" / "dr. X" followed by availability keywords
    doc_match = re.search(
        r"(?:doctor|dr\.?)\s+([a-z][a-z0-9]*(?:\s+[a-z]+)*?)(?:\s+(?:have|has|is|are|slot|available|open|any|on|for))",
        lowered,
    )

    # Pattern 2: "with X" (covers "book an appointment with DocDipu for …")
    if not doc_match:
        doc_match = re.search(
            r"\bwith\s+([a-z][a-z0-9]*(?:\s+[a-z]+)*?)(?:\s+(?:for|on|at|today|tomorrow|slot|please|thanks|$))",
            lowered,
        )

    # Pattern 3: standalone "X available/slots/open" without a prefix
    if not doc_match:
        doc_match = re.search(
            r"\b([a-z][a-z0-9]{2,}(?:\s+[a-z]+)*?)\s+(?:available|availability|slots?|open|schedule)",
            lowered,
        )

    if doc_match:
        intent.doctor_name = doc_match.group(1).strip()
        print(f"[DEBUG][DOCTOR_NAME_EXTRACTED] {intent.doctor_name}")

    # Extract booking slots if booking intent is detected
    if "book" in intent.actions:
        print("[DEBUG][BOOKING_INTENT_DETECTED] True")
        ordinal_match = re.search(r"(first|second|third|fourth|fifth|last)\s+(?:slot|appointment|one)", text.lower())
        if ordinal_match:
            intent.booking_ordinal = ordinal_match.group(1)
            print(f"[DEBUG][BOOKING_ORDINAL] {intent.booking_ordinal}")
        else:
            # Extract whatever comes after 'slot ' or 'appointment ' if any
            slot_match = re.search(r"(?:slot|appointment)\s+(?:on\s+|for\s+)?([a-z0-9\s,:]+?)(?:$|please|thanks)", text.lower())
            if slot_match:
                extracted = slot_match.group(1).strip()
                if extracted and extracted not in ["this", "that"]:
                    intent.booking_datetime = extracted
                    print(f"[DEBUG][BOOKING_DATETIME] {intent.booking_datetime}")

    return intent
