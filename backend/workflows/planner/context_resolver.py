from __future__ import annotations

import re
from typing import Any

from ..graph.state import UnifiedChatState
from ..models.resolved_context import ResolvedContext


# ---------------------------------------------------------------------------
# Generic Linguistic Rules (Domain-Agnostic)
# ---------------------------------------------------------------------------
_ORDINAL_INDEX_MAP: dict[str, int] = {
    "first": 0, "1st": 0,
    "second": 1, "2nd": 1,
    "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3,
    "fifth": 4, "5th": 4,
    "last": -1, "latest": 0, "previous": 0, "recent": 0,
}

_AFFIRMATION_PATTERNS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright",
    "yes please", "confirm", "go ahead", "do it", "sounds good",
    "perfect", "great", "that works", "please do",
}

_ANAPHORA_PATTERNS = [
    r"\b(it|that|this|that one|this one|the one|those|them)\b",
    r"\b(that|this|the|latest|last|previous)\s+(slot|appointment|report|document|consultation|record|test|result|one|option)\b",
]

_CONTEXT_BUFFER_KEYS = [
    ("doctor_availability_context", "doctor_availability"),
    ("asset_selection_context", "asset_selection"),
    ("consultation_context", "consultation"),
    ("patient_history_context", "patient_history"),
]


class ContextResolver:
    """
    Generic, domain-agnostic context resolver stage.

    Responsibility:
    Inspects UnifiedChatState context buffers, planner_metadata, and the latest user message
    to resolve conversational references (ordinals, demonstratives, confirmations) into a
    structured ResolvedContext model.

    Contains ZERO domain business logic, capability registries, or database schemas.
    """

    def __init__(self, state: UnifiedChatState, raw_text: str):
        self.state = state
        self.raw_text = raw_text.strip()
        self.text_lower = self.raw_text.lower()

    def resolve(self) -> ResolvedContext:
        """
        Main entry point. Inspects state context buffers and raw user text to produce a
        ResolvedContext object.
        """
        # 1. Locate active context buffer from state
        active_buffer, source_name = self._find_active_context_buffer()

        # 2. Extract linguistic patterns from user text
        ordinal_word, ordinal_idx = self._detect_ordinal()
        is_affirmation = self._detect_affirmation()
        anaphora_match = self._detect_anaphora()

        # If no linguistic reference and no active context buffer, return empty context
        if not active_buffer and not ordinal_word and not is_affirmation and not anaphora_match:
            return ResolvedContext(has_reference=False, confidence=0.0)

        # Build ResolvedContext
        res = ResolvedContext()
        res.resolved_source = source_name

        # 3. Resolve reference type & selection
        if ordinal_word:
            res.has_reference = True
            res.reference_type = "ordinal"
            res.resolved_selection = ordinal_word
            res.metadata["ordinal_index"] = ordinal_idx
            res.confidence = 0.90
        elif is_affirmation:
            res.has_reference = True
            res.reference_type = "affirmation"
            res.resolved_selection = "confirm"
            res.confidence = 0.85
        elif anaphora_match:
            res.has_reference = True
            res.reference_type = "anaphora"
            res.resolved_selection = anaphora_match
            res.confidence = 0.80
        elif active_buffer:
            # Active buffer present without explicit pronoun/ordinal
            res.has_reference = False
            res.confidence = 0.50

        # 4. Resolve entity payload generically from active buffer or previous metadata
        if active_buffer:
            res.resolved_entity = self._extract_generic_entity(active_buffer, ordinal_idx)

        # Also merge previous planner_metadata attributes into metadata dictionary if available
        prev_meta = self.state.get("planner_metadata") or {}
        if prev_meta:
            for k, v in prev_meta.items():
                if v is not None and k not in res.resolved_entity:
                    res.metadata[f"prev_{k}"] = v

        print(f"[DEBUG][CONTEXT_RESOLVER] Resolved Context:")
        print(f"[DEBUG][CONTEXT_RESOLVER]   has_reference     = {res.has_reference}")
        print(f"[DEBUG][CONTEXT_RESOLVER]   reference_type    = {res.reference_type}")
        print(f"[DEBUG][CONTEXT_RESOLVER]   resolved_source   = {res.resolved_source}")
        print(f"[DEBUG][CONTEXT_RESOLVER]   resolved_selection= {res.resolved_selection}")
        print(f"[DEBUG][CONTEXT_RESOLVER]   resolved_entity   = {res.resolved_entity}")
        print(f"[DEBUG][CONTEXT_RESOLVER]   confidence        = {res.confidence}")

        return res

    # ------------------------------------------------------------------
    # Private Helper Methods
    # ------------------------------------------------------------------

    def _find_active_context_buffer(self) -> tuple[Any, str | None]:
        """
        Iterates over state context buffers to find the primary non-empty context payload.
        Also inspects pending_booking_candidate in planner_metadata if available.
        """
        for state_key, source_name in _CONTEXT_BUFFER_KEYS:
            buf = self.state.get(state_key)
            if buf:
                return buf, source_name

        # Fallback to preserved active_workflow in planner_metadata
        prev_meta = self.state.get("planner_metadata") or {}
        workflow = prev_meta.get("active_workflow")
        if workflow and isinstance(workflow, dict) and workflow.get("status") != "cancelled":
            ctx = workflow.get("context") or {}
            if ctx:
                return [ctx], "doctor_availability"

        return None, None

    def _detect_ordinal(self) -> tuple[str | None, int | None]:
        """Detects ordinal words/numbers in user text."""
        for word, idx in _ORDINAL_INDEX_MAP.items():
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, self.text_lower):
                return word, idx
        return None, None

    def _detect_affirmation(self) -> bool:
        """Detects affirmation/confirmation phrases."""
        clean = self.text_lower.strip("!.,")
        if clean in _AFFIRMATION_PATTERNS:
            return True
        for aff in _AFFIRMATION_PATTERNS:
            if clean.startswith(aff) or f" {aff}" in clean:
                return True
        return False

    def _detect_anaphora(self) -> str | None:
        """Detects demonstrative pronouns or nominal references."""
        for pat in _ANAPHORA_PATTERNS:
            m = re.search(pat, self.text_lower)
            if m:
                return m.group(0)
        return None

    def _extract_generic_entity(self, buffer_data: Any, ordinal_idx: int | None) -> dict[str, Any]:
        """
        Generically extracts key-value attributes from the target item in the active buffer.
        Does NOT rely on any specific schema.
        """
        extracted: dict[str, Any] = {}

        selected_item: Any = None
        if isinstance(buffer_data, list) and len(buffer_data) > 0:
            idx = ordinal_idx if (ordinal_idx is not None and abs(ordinal_idx) < len(buffer_data)) else 0
            selected_item = buffer_data[idx]
        elif isinstance(buffer_data, dict):
            selected_item = buffer_data

        if isinstance(selected_item, dict):
            for k, v in selected_item.items():
                if v is not None:
                    extracted[k] = v
            slots = selected_item.get("available_slots")
            if isinstance(slots, list) and slots and ordinal_idx is not None and abs(ordinal_idx) < len(slots):
                extracted["booking_datetime"] = slots[ordinal_idx]
            if "booking_datetime" not in extracted:
                b_dt = extracted.get("appointment_time") or extracted.get("selected_slot")
                if b_dt:
                    extracted["booking_datetime"] = b_dt
        elif selected_item is not None:
            extracted["raw_value"] = selected_item

        return extracted
