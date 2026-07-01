from __future__ import annotations

from typing import Any

from ..common import latest_message_text
from ..retrieval_strategy import RetrievalStrategy
from ..state import UnifiedChatState


async def retrieval_strategy_node(state: UnifiedChatState) -> dict[str, Any]:
    text = latest_message_text(state.get("messages") or []).lower()
    
    # Doctor availability – check FIRST since availability queries may also
    # contain words like "appointment" which would match the appointment branch.
    if any(k in text for k in [
        "doctor available", "available doctor", "doctor slot", "open slots",
        "open appointments", "slots open", "is dr", "is dr.", "is doctor",
        "available on", "availability", "when is", "free slots", "any slots",
        "check slots", "show slots", "available slots",
    ]):
        strategy = RetrievalStrategy.DOCTOR_AVAILABILITY_QUERY.value
    elif any(k in text for k in [
        "latest report", "last report", "compare reports", "blood report",
        "analyze my report", "analyze my blood", "summarize my report",
        "review my report", "what does my report", "cbc report",
        "hemoglobin", "hb level", "pcv level", "rbc count", "wbc count",
        "platelet", "blood test",
    ]):
        strategy = RetrievalStrategy.DOCUMENT_QUERY.value
    elif any(k in text for k in [
        "appointment", "reschedule", "cancel", "upcoming", "schedule",
        "cardiologist", "book this", "reserve this", "book slot",
        "confirm this", "book", "reserve",
    ]):
        strategy = RetrievalStrategy.APPOINTMENT_QUERY.value
    elif any(k in text for k in [
        "previous consultation", "doctor recommend", "last consultation",
        "what did doctor say", "last visit", "follow up", "recommend",
    ]):
        strategy = RetrievalStrategy.CONSULTATION_QUERY.value
    else:
        strategy = RetrievalStrategy.GENERAL_CHAT.value

    return {"retrieval_strategy": strategy}
