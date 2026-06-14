from typing import Any, Callable, TypedDict, Awaitable
from .state import UnifiedChatState

class ActionDefinition(TypedDict):
    name: str
    handler: Callable[[UnifiedChatState, dict[str, Any]], Awaitable[dict[str, Any]]]
    requires_patient: bool
    requires_doctor: bool

async def handle_appointment_search(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_results": [{"type": "appointment_context", "action": "search"}],
        "pending_tasks": [{"task": "action", "action_handler": "APPOINTMENT_SEARCH_SLOTS", "parameters": {}}]
    }

async def handle_appointment_book(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_results": [{"type": "appointment_context", "action": "book"}],
        "pending_tasks": [{"task": "action", "action_handler": "APPOINTMENT_SEARCH_SLOTS", "parameters": {}}]
    }

async def handle_appointment_cancel(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {"action_results": [{"type": "appointment_context", "action": "cancel"}], "pending_tasks": []}

async def handle_appointment_reschedule(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {"action_results": [{"type": "appointment_context", "action": "reschedule"}], "pending_tasks": []}

async def handle_appointment_list(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {"action_results": [{"type": "appointment_context", "action": "list"}], "pending_tasks": []}

async def handle_appointment_search_slots(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {"action_results": [], "pending_tasks": []}

async def handle_doctor_search(state: UnifiedChatState, task_info: dict[str, Any]) -> dict[str, Any]:
    return {"action_results": [], "pending_tasks": []}

ACTION_REGISTRY: dict[str, ActionDefinition] = {
    "APPOINTMENT_SEARCH": {
        "name": "APPOINTMENT_SEARCH",
        "handler": handle_appointment_search,
        "requires_patient": False,
        "requires_doctor": False
    },
    "APPOINTMENT_BOOK": {
        "name": "APPOINTMENT_BOOK",
        "handler": handle_appointment_book,
        "requires_patient": False,
        "requires_doctor": False
    },
    "APPOINTMENT_CANCEL": {
        "name": "APPOINTMENT_CANCEL",
        "handler": handle_appointment_cancel,
        "requires_patient": False,
        "requires_doctor": False
    },
    "APPOINTMENT_RESCHEDULE": {
        "name": "APPOINTMENT_RESCHEDULE",
        "handler": handle_appointment_reschedule,
        "requires_patient": False,
        "requires_doctor": False
    },
    "APPOINTMENT_LIST": {
        "name": "APPOINTMENT_LIST",
        "handler": handle_appointment_list,
        "requires_patient": False,
        "requires_doctor": False
    },
    "APPOINTMENT_SEARCH_SLOTS": {
        "name": "APPOINTMENT_SEARCH_SLOTS",
        "handler": handle_appointment_search_slots,
        "requires_patient": False,
        "requires_doctor": False
    },
    "DOCTOR_SEARCH": {
        "name": "DOCTOR_SEARCH",
        "handler": handle_doctor_search,
        "requires_patient": False,
        "requires_doctor": False
    }
}

def get_action_handler(name: str) -> ActionDefinition | None:
    return ACTION_REGISTRY.get(name)
