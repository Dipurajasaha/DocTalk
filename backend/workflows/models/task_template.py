from dataclasses import dataclass, field
from typing import Any

@dataclass
class TaskTemplate:
    template_name: str
    parameters: dict[str, Any] = field(default_factory=dict)
