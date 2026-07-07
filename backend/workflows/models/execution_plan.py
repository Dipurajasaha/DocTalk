from dataclasses import dataclass, field
from typing import Any
from .planner_task import PlannerTask

@dataclass
class ExecutionPlan:
    goals: list[str] = field(default_factory=list)
    required_information: list[str] = field(default_factory=list)
    tasks: list[PlannerTask] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    reasoning: str = ""
    
    def add_task(self, task: PlannerTask) -> None:
        self.tasks.append(task)
        
    def add_tasks(self, tasks: list[PlannerTask]) -> None:
        self.tasks.extend(tasks)
        
    def deduplicate(self) -> None:
        # Deprecated: Deduplication is now handled by PlanOptimizer
        pass
