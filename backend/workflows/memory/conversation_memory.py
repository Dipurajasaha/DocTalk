import copy
from typing import Any
from ..graph.state import UnifiedChatState
from ..utils.logger import log_section, log_key_value

class ConversationMemoryManager:
    def __init__(self, state: dict[str, Any]):
        self.state = state
        self.memory = copy.deepcopy(state.get("conversation_memory") or {})
        
        # Ensure base structure
        if "workflow" not in self.memory:
            self.memory["workflow"] = {}
        if "semantic" not in self.memory:
            self.memory["semantic"] = {}
        if "short_term" not in self.memory:
            self.memory["short_term"] = {}
            
    def hydrate_planner_metadata(self) -> dict[str, Any]:
        """Reads from conversation_memory to populate planner_metadata for the next turn."""
        metadata = dict(self.state.get("planner_metadata") or {})
        
        hydrated = []
        
        # Hydrate workflow state
        workflow = self.memory.get("workflow", {})
        if "active_workflow" in workflow:
            metadata["active_workflow"] = workflow["active_workflow"]
            hydrated.append("active_workflow")
            
        if "doctor_name" in workflow:
            metadata["doctor_name"] = workflow["doctor_name"]
            hydrated.append("doctor_name")
            
        if "booking_datetime" in workflow:
            metadata["booking_datetime"] = workflow["booking_datetime"]
            hydrated.append("booking_datetime")
            
        if "booking_ordinal" in workflow:
            metadata["booking_ordinal"] = workflow["booking_ordinal"]
            hydrated.append("booking_ordinal")
            
        # Hydrate semantic state
        semantic = self.memory.get("semantic", {})
        # Note: we don't stuff doctor_availability_context into planner_metadata, 
        # but the executor might need it later. For now, just hydrate metadata.

        if hydrated:
            log_section("MEMORY")
            log_key_value("Hydrated", hydrated)
            
        return metadata

    def update(self, result_dict: dict[str, Any]) -> dict[str, Any]:
        """Updates memory based on executor results and applies expiration."""
        updated = []
        expired = []
        
        workflow = self.memory.setdefault("workflow", {})
        semantic = self.memory.setdefault("semantic", {})
        
        # 1. Update Workflow memory from planner_metadata (if Executor preserved it)
        pmeta = result_dict.get("planner_metadata", self.state.get("planner_metadata", {}))
        is_workflow_query = pmeta.get("query_type") in ("workflow", "appointment")
        
        # If executor explicitly cleared active_workflow, or it's a workflow query and it's gone
        if "active_workflow" not in pmeta and "active_workflow" in workflow:
            if is_workflow_query:
                workflow.pop("active_workflow", None)
                workflow.pop("doctor_name", None)
                workflow.pop("booking_datetime", None)
                workflow.pop("booking_ordinal", None)
                expired.append("active_workflow")
                expired.append("workflow_context")
            else:
                pass # Preserve workflow memory for unrelated tangents
        elif "active_workflow" in pmeta:
            workflow["active_workflow"] = pmeta["active_workflow"]
            updated.append("active_workflow")
            
            # Extract items from active_workflow context
            ctx = pmeta["active_workflow"].get("context", {})
            if "doctor_name" in ctx and ctx["doctor_name"]:
                workflow["doctor_name"] = ctx["doctor_name"]
                if "doctor_name" not in updated: updated.append("doctor_name")
            if "appointment_time" in ctx and ctx["appointment_time"]:
                workflow["booking_datetime"] = ctx["appointment_time"]
                if "booking_datetime" not in updated: updated.append("booking_datetime")
            if "selection_type" in ctx and ctx["selection_type"]:
                workflow["booking_ordinal"] = ctx["selection_type"]
                if "booking_ordinal" not in updated: updated.append("booking_ordinal")
                
        # 2. Update Semantic memory (e.g., doctor_availability_context)
        if "doctor_availability_context" in result_dict:
            avail = result_dict["doctor_availability_context"]
            if avail:
                semantic["doctor_availability_context"] = avail
                updated.append("doctor_availability_context")
            elif "doctor_availability_context" in semantic:
                semantic.pop("doctor_availability_context", None)
                expired.append("doctor_availability_context")
                
        if updated or expired:
            log_section("MEMORY")
            log_key_value("Updated", updated if updated else "none")
            log_key_value("Expired", expired if expired else "none")
            
        return self.memory
