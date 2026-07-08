APPOINTMENT_RULE_CONFIG = {
    "entities": ["cardiologist", "slot", "appointment"],
    "appointment_actions": {
        "book": ["book", "schedule", "reserve", "confirm"],
        "cancel": ["cancel"],
        "reschedule": ["reschedule"],
        "list": ["show", "list", "all"],
        "upcoming": ["upcoming", "next"]
    }
}

DOCTOR_AVAILABILITY_RULE_CONFIG = {
    "entities": ["cardiologist"],
    "actions": {
        "check": ["open slots", "available", "slot"]
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
