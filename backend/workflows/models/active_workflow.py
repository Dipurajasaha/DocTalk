from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class ActiveWorkflow:
    """
    Generic Active Workflow dataclass.
    Tracks state for multi-turn transactional workflows (booking, cancellation, reschedule, payments, etc.).
    """
    type: str  # e.g., "appointment_booking", "appointment_cancellation", "appointment_reschedule"
    status: str  # e.g., "waiting_selection", "waiting_confirmation", "executing", "completed", "cancelled"
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "status": self.status,
            "context": self.context,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Optional["ActiveWorkflow"]:
        if not data or not isinstance(data, dict) or "type" not in data:
            return None
        return cls(
            type=data["type"],
            status=data.get("status", "in_progress"),
            context=dict(data.get("context") or {}),
            created_at=data.get("created_at") or datetime.now(timezone.utc).isoformat(),
        )
