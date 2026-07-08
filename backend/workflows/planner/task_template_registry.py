from typing import Callable
from ..models.planner_task import PlannerTask
from ..models.task_template import TaskTemplate

def build_patient_history(template: TaskTemplate) -> list[PlannerTask]:
    return [PlannerTask.create_retrieve("PATIENT_HISTORY", parameters=template.parameters)]

def build_consultation(template: TaskTemplate) -> list[PlannerTask]:
    action = template.parameters.pop("action", None)
    return [PlannerTask.create_retrieve("CONSULTATION", action, template.parameters)]

def build_memory(template: TaskTemplate) -> list[PlannerTask]:
    return [PlannerTask.create_retrieve("MEMORY", parameters=template.parameters)]

def build_asset_index(template: TaskTemplate) -> list[PlannerTask]:
    action = template.parameters.pop("action", None)
    return [PlannerTask.create_retrieve("ASSET_INDEX", action, template.parameters)]

def build_appointment(template: TaskTemplate) -> list[PlannerTask]:
    return [PlannerTask.create_retrieve("APPOINTMENT", parameters=template.parameters)]

def build_appointment_book(template: TaskTemplate) -> list[PlannerTask]:
    return [PlannerTask.create_action("APPOINTMENT_BOOK", template.parameters)]

def build_appointment_cancel(template: TaskTemplate) -> list[PlannerTask]:
    return [PlannerTask.create_action("APPOINTMENT_CANCEL", template.parameters)]

def build_appointment_reschedule(template: TaskTemplate) -> list[PlannerTask]:
    return [PlannerTask.create_action("APPOINTMENT_RESCHEDULE", template.parameters)]

def build_doctor_availability(template: TaskTemplate) -> list[PlannerTask]:
    return [PlannerTask.create_retrieve("DOCTOR_AVAILABILITY", parameters=template.parameters)]

TASK_TEMPLATE_REGISTRY: dict[str, Callable[[TaskTemplate], list[PlannerTask]]] = {
    "PATIENT_HISTORY": build_patient_history,
    "CONSULTATION": build_consultation,
    "MEMORY": build_memory,
    "ASSET_INDEX": build_asset_index,
    "APPOINTMENT": build_appointment,
    "APPOINTMENT_BOOK": build_appointment_book,
    "APPOINTMENT_CANCEL": build_appointment_cancel,
    "APPOINTMENT_RESCHEDULE": build_appointment_reschedule,
    "DOCTOR_AVAILABILITY": build_doctor_availability
}

def build_task_from_template(template: TaskTemplate) -> list[PlannerTask]:
    builder = TASK_TEMPLATE_REGISTRY.get(template.template_name)
    if builder:
        return builder(template)
    return []
