from dataclasses import dataclass, field
from typing import Any

@dataclass
class PlannerTask:
    task_type: str
    retriever: str | None = None
    action_handler: str | None = None
    action: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create_retrieve(cls, retriever: str, action: str | None = None, parameters: dict[str, Any] | None = None) -> "PlannerTask":
        return cls(
            task_type="retrieve",
            retriever=retriever,
            action=action,
            parameters=parameters or {}
        )
        
    @classmethod
    def create_action(cls, action_handler: str, parameters: dict[str, Any] | None = None) -> "PlannerTask":
        return cls(
            task_type="action",
            action_handler=action_handler,
            parameters=parameters or {}
        )
        
    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task_type,
            "retriever": self.retriever,
            "action_handler": self.action_handler,
            "action": self.action,
            "parameters": self.parameters
        }
        
    @property
    def capability_name(self) -> str | None:
        if self.task_type == "retrieve":
            return self.retriever
        elif self.task_type == "action":
            return self.action_handler
        return self.task_type

