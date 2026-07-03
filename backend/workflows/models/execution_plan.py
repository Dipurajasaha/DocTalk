from dataclasses import dataclass, field
from typing import Any
from .planner_task import PlannerTask

@dataclass
class ExecutionPlan:
    goal: str = "general_chat"
    required_information: list[str] = field(default_factory=list)
    tasks: list[PlannerTask] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def add_task(self, task: PlannerTask) -> None:
        self.tasks.append(task)
        
    def add_tasks(self, tasks: list[PlannerTask]) -> None:
        self.tasks.extend(tasks)
        
    def deduplicate(self) -> None:
        final_tasks = []
        seen = set()
        for task in self.tasks:
            task_id = f"{task.task_type}_{task.action}_{task.action_handler}_{task.retriever}"
            if task_id not in seen:
                seen.add(task_id)
                final_tasks.append(task)
        self.tasks = final_tasks
