from __future__ import annotations

from typing import Any

from ..common import latest_message_text
from ..retrieval_strategy import RetrievalStrategy
from ..state import UnifiedChatState


async def retrieval_strategy_node(state: UnifiedChatState) -> dict[str, Any]:
    text = latest_message_text(state.get("messages") or []).lower()
    
    if any(k in text for k in ["latest report", "last report", "compare reports", "blood report"]):
        strategy = RetrievalStrategy.DOCUMENT_QUERY.value
    elif any(k in text for k in ["appointment", "reschedule", "cancel", "upcoming", "schedule", "doctor available", "available doctor", "doctor slot", "cardiologist"]):
        strategy = RetrievalStrategy.APPOINTMENT_QUERY.value
    elif any(k in text for k in ["previous consultation", "doctor recommend", "last consultation", "what did doctor say", "last visit", "follow up", "recommend"]):
        strategy = RetrievalStrategy.CONSULTATION_QUERY.value
    else:
        strategy = RetrievalStrategy.GENERAL_CHAT.value

    return {"retrieval_strategy": strategy}
