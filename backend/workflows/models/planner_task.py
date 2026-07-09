from dataclasses import dataclass, field
from typing import Any

@dataclass
class PlannerTask:
    task_type: str
    retriever: str | None = None
    action_handler: str | None = None
    action: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    
    # Stage 3C: Dependency metadata
    task_id: str | None = None
    depends_on: list[str] | None = None
    produces: list[str] | None = None
    consumes: list[str] | None = None
    
    @classmethod
    def create_retrieve(cls, retriever: str, action: str | None = None, parameters: dict[str, Any] | None = None,
                        task_id: str | None = None, depends_on: list[str] | None = None,
                        produces: list[str] | None = None, consumes: list[str] | None = None) -> "PlannerTask":
        return cls(
            task_type="retrieve",
            retriever=retriever,
            action=action,
            parameters=parameters or {},
            task_id=task_id,
            depends_on=depends_on,
            produces=produces,
            consumes=consumes
        )
        
    @classmethod
    def create_action(cls, action_handler: str, parameters: dict[str, Any] | None = None,
                      task_id: str | None = None, depends_on: list[str] | None = None,
                      produces: list[str] | None = None, consumes: list[str] | None = None) -> "PlannerTask":
        return cls(
            task_type="action",
            action_handler=action_handler,
            parameters=parameters or {},
            task_id=task_id,
            depends_on=depends_on,
            produces=produces,
            consumes=consumes
        )
        
    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task_type,
            "retriever": self.retriever,
            "action_handler": self.action_handler,
            "action": self.action,
            "parameters": self.parameters,
            "task_id": self.task_id,
            "depends_on": self.depends_on,
            "produces": self.produces,
            "consumes": self.consumes
        }
        
    @property
    def capability_name(self) -> str | None:
        if self.task_type == "retrieve":
            return self.retriever
        elif self.task_type == "action":
            return self.action_handler
        return self.task_type

