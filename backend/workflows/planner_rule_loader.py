from .planner_rule_registry import (
    PatientHistoryRule,
    DocumentRule,
    AppointmentRule,
    ConsultationRule,
    MemoryRule,
    PlannerRule
)

RULE_REGISTRY: dict[str, type[PlannerRule]] = {
    "PATIENT_HISTORY": PatientHistoryRule,
    "DOCUMENT": DocumentRule,
    "APPOINTMENT": AppointmentRule,
    "CONSULTATION": ConsultationRule,
    "MEMORY": MemoryRule
}

def load_planner_rules() -> list[PlannerRule]:
    return [rule_class() for rule_class in RULE_REGISTRY.values()]
