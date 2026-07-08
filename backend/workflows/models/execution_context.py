import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from .planner_task import PlannerTask
from .capability_result import CapabilityResult


@dataclass
class ExecutionStatistics:
    tasks_executed: int = 0
    tasks_skipped: int = 0
    dependency_waits: int = 0
    failed_tasks: int = 0
    total_duration_ms: float = 0.0


@dataclass
class ExecutionContext:
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    completed_task_ids: set[str] = field(default_factory=set)
    produced_data: dict[str, Any] = field(default_factory=dict)
    consumed_data: dict[str, Any] = field(default_factory=dict)
    shared_context: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    stats: ExecutionStatistics = field(default_factory=ExecutionStatistics)
    pending_tasks: list[PlannerTask] = field(default_factory=list)
    
    _start_time: float = field(default_factory=time.time)

    def merge_result(self, task: PlannerTask, result: CapabilityResult) -> None:
        """Merges the execution output of a single capability into the centralized context."""
        
        # 1. Track Statistics
        if result.status == "SUCCESS":
            self.stats.tasks_executed += 1
            if getattr(task, "task_id", None):
                self.completed_task_ids.add(task.task_id)
        else:
            self.stats.failed_tasks += 1
            
        # 2. Merge Metadata (both arbitrary metadata and target contexts)
        if result.metadata:
            self.metadata.update(result.metadata)
            
        # 3. Handle data output routing
        # Either map via explicit `produces` from the task...
        if getattr(task, "produces", None) and result.data is not None:
            if isinstance(result.data, dict):
                for k in task.produces:
                    if k in result.data:
                        self.produced_data[k] = result.data[k]
                        self.shared_context[k] = result.data[k]
            elif len(task.produces) == 1:
                self.produced_data[task.produces[0]] = result.data
                self.shared_context[task.produces[0]] = result.data
                
        # Or map via implicit metadata rules from the capability
        from ..executor.capability_registry import get_capability
        capability = get_capability(result.capability_name)
        if capability and "metadata" in capability:
            for target_key in getattr(capability["metadata"], "target_context_keys", []):
                if result.data is None:
                    continue
                if isinstance(result.data, dict) and target_key in result.data:
                    self.shared_context[target_key] = result.data[target_key]
                else:
                    if isinstance(result.data, dict) and isinstance(self.shared_context.get(target_key), dict):
                        self.shared_context[target_key].update(result.data)
                    else:
                        self.shared_context[target_key] = result.data
                        
        # 4. Handle consumed data tracking
        if getattr(task, "consumes", None):
            for k in task.consumes:
                if k in self.shared_context:
                    self.consumed_data[k] = self.shared_context[k]

        # 5. Handle evidence collection & deduplication
        if result.evidence:
            for ev in result.evidence:
                if ev not in self.evidence:
                    self.evidence.append(ev)
                    
        # 6. Track warnings/errors
        if getattr(result, "warnings", None):
            self.warnings.extend(result.warnings)
        if getattr(result, "errors", None):
            self.warnings.extend(result.errors)
            
        # 7. Add pending tasks dynamically discovered
        if getattr(result, "pending_tasks", None):
            for pt in result.pending_tasks:
                if isinstance(pt, dict):
                    self.pending_tasks.append(PlannerTask(
                        task_type=pt.get("task_type", pt.get("task", "")),
                        retriever=pt.get("retriever"),
                        action_handler=pt.get("action_handler"),
                        action=pt.get("action"),
                        parameters=pt.get("parameters", {})
                    ))
                else:
                    self.pending_tasks.append(pt)
                    
    def finalize(self) -> None:
        """Called at the end of the execution cycle to finalize timing."""
        self.stats.total_duration_ms = (time.time() - self._start_time) * 1000
