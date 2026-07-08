from dataclasses import dataclass, field
from typing import Any

@dataclass
class Evidence:
    source: str
    type: str
    content: str
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "type": self.type,
            "content": self.content,
            "confidence": self.confidence,
            "metadata": self.metadata
        }
