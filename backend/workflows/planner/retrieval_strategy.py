from enum import Enum
from typing import Any
from ..graph.state import UnifiedChatState

class RetrievalStrategy(str, Enum):
    DOCUMENT_QUERY = "DOCUMENT_QUERY"
    CONSULTATION_QUERY = "CONSULTATION_QUERY"
    APPOINTMENT_QUERY = "APPOINTMENT_QUERY"
    ASSET_INDEX_QUERY = "ASSET_INDEX_QUERY"
    PATIENT_HISTORY_QUERY = "PATIENT_HISTORY_QUERY"
    MEMORY_QUERY = "MEMORY_QUERY"
    DEEP_REASONING = "DEEP_REASONING"
    GENERAL_CHAT = "GENERAL_CHAT"
    DOCTOR_AVAILABILITY_QUERY = "DOCTOR_AVAILABILITY_QUERY"

async def retrieval_strategy_node(state: UnifiedChatState) -> dict[str, Any]:
    """
    Deprecated: Strategy is now determined inside the main planner node.
    This node is kept as a no-op to avoid modifying unified_chat_graph.py topology.
    """
    return {}
