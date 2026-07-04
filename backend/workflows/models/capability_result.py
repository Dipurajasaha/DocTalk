from dataclasses import dataclass, field
from typing import Any

@dataclass
class CapabilityResult:
    capability_name: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    pending_tasks: list[dict[str, Any]] = field(default_factory=list)
    # Generic bucket for whatever data the capability retrieved/acted upon
    data: Any = None
    # Additional generic flags or execution info
    metadata: dict[str, Any] = field(default_factory=dict)
