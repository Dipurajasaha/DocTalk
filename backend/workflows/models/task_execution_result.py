from dataclasses import dataclass, field
from .planner_task import PlannerTask

@dataclass
class TaskExecutionResult:
    pending_tasks: list[PlannerTask] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    memory_context: list | None = None
    consultation_context: list | None = None
    patient_history_context: list | None = None
    appointment_context: dict | None = None
    doctor_availability_context: list | None = None
    asset_selection_context: dict | None = None
    rag_scope: dict | None = None

    def merge(self, result: dict) -> None:
        if "memory_context" in result:
            if self.memory_context is None: self.memory_context = []
            self.memory_context.extend(result["memory_context"])
        if "consultation_context" in result:
            if self.consultation_context is None: self.consultation_context = []
            self.consultation_context.extend(result["consultation_context"])
        if "patient_history_context" in result:
            if self.patient_history_context is None: self.patient_history_context = []
            self.patient_history_context.extend(result["patient_history_context"])
        if "appointment_context" in result:
            if self.appointment_context is None: self.appointment_context = {}
            self.appointment_context.update(result["appointment_context"])
        if "doctor_availability_context" in result:
            if self.doctor_availability_context is None: self.doctor_availability_context = []
            self.doctor_availability_context.extend(result["doctor_availability_context"])
        if "asset_selection_context" in result:
            if self.asset_selection_context is None: self.asset_selection_context = {}
            self.asset_selection_context.update(result["asset_selection_context"])
        if "rag_scope" in result:
            if self.rag_scope is None: self.rag_scope = {}
            self.rag_scope.update(result["rag_scope"])
        if "evidence" in result:
            self.evidence.extend(result["evidence"])

    def add_pending_tasks(self, tasks: list[dict]) -> None:
        for t in tasks:
            self.pending_tasks.append(PlannerTask(
                task_type=t.get("task", ""),
                retriever=t.get("retriever"),
                action_handler=t.get("action_handler"),
                action=t.get("action"),
                parameters=t.get("parameters", {})
            ))
