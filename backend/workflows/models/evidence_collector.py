from dataclasses import dataclass, field
from typing import Any

@dataclass
class EvidenceCollector:
    items: list[dict[str, Any]] = field(default_factory=list)
    
    def add(self, evidence: dict[str, Any]) -> None:
        self.items.append(evidence)
        
    def extend(self, evidence: list[dict[str, Any]]) -> None:
        self.items.extend(evidence)
        
    def build(self) -> list[dict[str, Any]]:
        return self.items
