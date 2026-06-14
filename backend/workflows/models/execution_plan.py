from dataclasses import dataclass, field
from .planner_task import PlannerTask

@dataclass
class ExecutionPlan:
    tasks: list[PlannerTask] = field(default_factory=list)
    
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
        
    def to_list(self) -> list[PlannerTask]:
        return self.tasks
