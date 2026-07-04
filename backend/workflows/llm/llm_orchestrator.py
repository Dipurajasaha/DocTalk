import logging
from typing import Any

from .patient.patient_nodes import patient_assistant_llm, patient_general_llm, triage_evaluator
from .doctor.doctor_nodes import doctor_general_llm, doctor_scoped_llm
from .patient.routing import classify_intent
from ..graph.state import WorkflowState

logger = logging.getLogger(__name__)

async def llm_orchestrator_node(state: WorkflowState) -> dict[str, Any]:
    role = str(state.get("role") or "patient").lower()
    
    if role == "doctor":
        mode = str(state.get("mode") or "").strip()
        if mode == "patient_scoped":
            return await doctor_scoped_llm(state)
        else:
            return await doctor_general_llm(state)
    else:
        # Patient logic
        
        # 1. Evaluate triage
        triage_result = await triage_evaluator(state)
        
        # We need to temporarily update state so classify_intent and subsequent LLMs see triage_level
        temp_state = dict(state)
        temp_state.update(triage_result)
        
        # 2. Classify intent
        intent = classify_intent(temp_state)
        
        # 3. Route to specific LLM
        if intent in ("emergency", "patient_rag"):
            llm_result = await patient_assistant_llm(temp_state)
        else:
            llm_result = await patient_general_llm(temp_state)
            
        # Combine the triage updates and the LLM result
        final_result = dict(triage_result)
        
        # If the LLM result has context_payload, merge it carefully
        if "context_payload" in llm_result and "context_payload" in triage_result:
            merged_payload = dict(triage_result["context_payload"])
            merged_payload.update(llm_result["context_payload"])
            final_result.update(llm_result)
            final_result["context_payload"] = merged_payload
        else:
            final_result.update(llm_result)
            
        return final_result
