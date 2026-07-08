from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ResolvedContext:
    """
    Domain-agnostic structured representation of resolved conversational context.

    Produced by the ContextResolver and consumed by the PlanningEngine.
    Contains zero capability-specific business logic.
    """
    has_reference: bool = False
    reference_type: str | None = None       # e.g., "ordinal", "affirmation", "anaphora", "action_ref"
    resolved_selection: Any = None          # Index, ordinal string, or selected item identifier
    resolved_entity: dict[str, Any] = field(default_factory=dict)  # Key-value payload extracted from active state
    resolved_source: str | None = None      # Source context key (e.g., "doctor_availability", "asset_selection")
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
