from .planner_rule_registry import (
    PatientHistoryRule,
    DocumentRule,
    AppointmentRule,
    DoctorAvailabilityRule,
    ConsultationRule,
    MemoryRule,
    PlannerRule
)
from .planner_rule_order import RULE_EXECUTION_ORDER

RULE_REGISTRY: dict[str, type[PlannerRule]] = {
    "PATIENT_HISTORY": PatientHistoryRule,
    "DOCUMENT": DocumentRule,
    "APPOINTMENT": AppointmentRule,
    "DOCTOR_AVAILABILITY": DoctorAvailabilityRule,
    "CONSULTATION": ConsultationRule,
    "MEMORY": MemoryRule
}

def load_planner_rules() -> list[PlannerRule]:
    rules = []
    for rule_name in RULE_EXECUTION_ORDER:
        if rule_name not in RULE_REGISTRY:
            raise ValueError(f"Rule '{rule_name}' in RULE_EXECUTION_ORDER not found in RULE_REGISTRY.")
        rules.append(RULE_REGISTRY[rule_name]())
    return rules
