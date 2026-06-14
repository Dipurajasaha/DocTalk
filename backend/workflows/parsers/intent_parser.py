from dataclasses import dataclass, field

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

def parse_intent(text: str) -> ParsedIntent:
    intent = ParsedIntent(original_text=text)
    
    # Appointment extraction
    if "cardiologist" in text and "book" in text:
        intent.is_appointment = True
        intent.intent_type = "appointment"
        intent.entities.append("cardiologist")
        intent.actions.append("book")
        
    if "cancel" in text:
        intent.actions.append("cancel")
    elif "reschedule" in text:
        intent.actions.append("reschedule")
    elif "book" in text or "schedule" in text:
        intent.actions.append("book")
    elif "upcoming" in text or "show" in text or "list" in text:
        intent.actions.append("list")
        
    # Consultation extraction
    if "chest pain" in text:
        intent.is_consultation = True
        intent.intent_type = "symptom"
        intent.entities.append("chest pain")
    elif "recommend" in text:
        intent.is_consultation = True
        intent.intent_type = "consultation"
        
    if "last time" in text:
        intent.actions.append("last_time")
    if "previous" in text or "history" in text or "last" in text:
        intent.actions.append("history")

    # Patient History extraction
    history_keywords = [
        "do i have", "medical history", "history", "medications", "medication", 
        "surgery", "surgeries", "allergy", "allergies", "diagnosed with", "conditions"
    ]
    if any(kw in text for kw in history_keywords):
        intent.is_history = True
        intent.intent_type = "patient_history"
        if "medication" in text or "medications" in text:
            intent.history_type = "medication"
        elif "surgery" in text or "surgeries" in text:
            intent.history_type = "surgery"
        elif "allergy" in text or "allergies" in text:
            intent.history_type = "allergy"
        elif "condition" in text or "conditions" in text or "diagnosed with" in text:
            intent.history_type = "condition"

    return intent
