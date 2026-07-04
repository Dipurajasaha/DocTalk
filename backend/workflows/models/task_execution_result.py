from dataclasses import dataclass, field
from .planner_task import PlannerTask
from .capability_result import CapabilityResult

@dataclass
class TaskExecutionResult:
    pending_tasks: list[PlannerTask] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    results: list[CapabilityResult] = field(default_factory=list)

    def merge(self, result: CapabilityResult) -> None:
        self.results.append(result)
        self.evidence.extend(result.evidence)
        self.add_pending_tasks(result.pending_tasks)

    def add_pending_tasks(self, tasks: list[dict]) -> None:
        for t in tasks:
            self.pending_tasks.append(PlannerTask(
                task_type=t.get("task", ""),
                retriever=t.get("retriever"),
                action_handler=t.get("action_handler"),
                action=t.get("action"),
                parameters=t.get("parameters", {})
            ))
