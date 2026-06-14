APPOINTMENT_RULE_CONFIG = {
    "entities": ["cardiologist"],
    "appointment_actions": {
        "book": ["book", "schedule"],
        "cancel": ["cancel"],
        "reschedule": ["reschedule"],
        "list": ["upcoming", "show", "list"]
    }
}

CONSULTATION_RULE_CONFIG = {
    "entities": ["chest pain"],
    "consultation_triggers": ["recommend"],
    "consultation_actions": {
        "last_time": ["last time"],
        "history": ["previous", "history", "last"]
    }
}

PATIENT_HISTORY_RULE_CONFIG = {
    "trigger_phrases": [
        "do i have", "medical history", "history", "medications", "medication", 
        "surgery", "surgeries", "allergy", "allergies", "diagnosed with", "conditions"
    ],
    "history_types": ["medication", "surgery", "allergy", "condition"]
}
