import json
import traceback
from typing import Any

from backend.ai.core_services.llm_client import complete_text, _extract_json
from backend.workflows.graph.state import UnifiedChatState
from backend.workflows.graph.common import latest_message_text
from backend.workflows.models.planner_task import PlannerTask
from backend.workflows.models.execution_plan import ExecutionPlan
from backend.workflows.models.active_workflow import ActiveWorkflow

LLM_PLANNER_PROMPT = """You are the central Planning Engine for DocTalk, a patient healthcare assistant.
Your job is to analyze the user's message, conversation history, and current context to output a JSON execution plan.

AVAILABLE CAPABILITIES:
- PATIENT_HISTORY: Fetch medical history
- CONSULTATION: Fetch previous consultations
- MEMORY: Fetch patient summary
- ASSET_INDEX: Fetch assets/documents
- APPOINTMENT: List patient's existing appointments
- APPOINTMENT_SEARCH_SLOTS: Search for available doctor slots
- APPOINTMENT_BOOK: Confirm and book an appointment
- APPOINTMENT_CANCEL: Cancel an appointment
- APPOINTMENT_RESCHEDULE: Reschedule an appointment

RULES:
1. Always return valid JSON.
2. PREFER RETRIEVAL: If the user asks a question, retrieve data first before answering. Do not attempt to guess or hallucinate.
3. AVOID HALLUCINATION: ONLY output capabilities that exactly match the list above. Never make up capability names.
4. MULTI-CAPABILITY: For queries spanning multiple topics (e.g. "Summarize my previous consultations and latest blood report"), output multiple tasks. Do NOT create unnecessary tasks.
5. If the user asks for appointment slots (e.g. "Is there any appointment slots available for Dr. X?"), use APPOINTMENT_SEARCH_SLOTS.
6. If the user selects a slot (e.g. "Book the first available slot"), use APPOINTMENT_SEARCH_SLOTS again to retrieve the context, but update the workflow status to "waiting_confirmation" and set "booking_ordinal" in metadata.
7. If the user confirms a booking (e.g. "Yes, please book it"), use APPOINTMENT_BOOK.
8. If the user asks to cancel an appointment (e.g. "Cancel my appointment"), use APPOINTMENT_CANCEL.
9. For general greetings (e.g. "Hello", "Hi"), return NO tasks and "query_type": "general". DO NOT include workflow or appointment metadata.
10. For general medical knowledge (e.g. "Tell me about anemia", "What is diabetes?"), return NO tasks and "query_type": "knowledge". DO NOT include workflow or appointment metadata.
11. Always preserve the active_workflow if we are in the middle of a booking, UNLESS the query is unrelated (general or knowledge) or cancelled. For unrelated queries, omit workflow metadata entirely to prevent context pollution.

OUTPUT SCHEMA (JSON ONLY):
{
  "confidence": 0.95,
  "reasoning": "Short explanation of why this plan was chosen.",
  "query_type": "general|knowledge|rag|workflow",
  "tasks": [
      {
          "task_id": "unique_string",
          "task_type": "retrieve|action",
          "retriever": "CAPABILITY_NAME (only if retrieve)",
          "action_handler": "CAPABILITY_NAME (only if action)",
          "action": "latest (only for ASSET_INDEX if explicitly requested latest)",
          "depends_on": []
      }
  ],
  "workflow": {
      "type": "appointment_booking",
      "status": "waiting_selection|waiting_confirmation|cancelled"
  },
  "metadata": {
      "doctor_name": "Doctor name if detected",
      "booking_datetime": "Slot time if detected",
      "booking_ordinal": "e.g. 'first' if detected"
  }
}

Examples:
USER: "Hello!"
OUTPUT: {"confidence":1.0,"reasoning":"Greeting detected","query_type":"general","tasks":[],"metadata":{}}

USER: "Tell me about anemia."
OUTPUT: {"confidence":0.98,"reasoning":"Medical knowledge query","query_type":"knowledge","tasks":[],"metadata":{}}

USER: "Explain my latest blood report."
OUTPUT: {"confidence":0.95,"reasoning":"Needs asset and memory","query_type":"rag","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"ASSET_INDEX","action":"latest","depends_on":[]},{"task_id":"t2","task_type":"retrieve","retriever":"MEMORY","depends_on":[]}],"metadata":{}}

USER: "Summarize my previous consultations."
OUTPUT: {"confidence":0.95,"reasoning":"Needs consultation history","query_type":"rag","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"CONSULTATION","depends_on":[]}],"metadata":{}}

USER: "Is there any appointment slots available for Dr. DocDipu?"
OUTPUT: {"confidence":0.92,"reasoning":"Search slots for specific doctor","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"APPOINTMENT_SEARCH_SLOTS","depends_on":[]}],"metadata":{"doctor_name":"DocDipu"}}

USER: "Book the first available slot." (Context: Waiting for selection)
OUTPUT: {"confidence":0.90,"reasoning":"Selecting first ordinal slot","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"APPOINTMENT_SEARCH_SLOTS","depends_on":[]}],"workflow":{"type":"appointment_booking","status":"waiting_confirmation"},"metadata":{"booking_ordinal":"first"}}

USER: "Yes, please book it." (Context: Waiting for confirmation)
OUTPUT: {"confidence":0.95,"reasoning":"Confirming booking","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"action","action_handler":"APPOINTMENT_BOOK","depends_on":[]}],"workflow":{"type":"appointment_booking","status":"confirmed"},"metadata":{}}

USER: "Cancel my appointment."
OUTPUT: {"confidence":0.98,"reasoning":"Canceling appointment","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"action","action_handler":"APPOINTMENT_CANCEL","depends_on":[]}],"metadata":{}}
"""

class LLMPlanningEngine:
    def __init__(self, state: UnifiedChatState):
        self.state = state
        self.text = latest_message_text(state.get("messages") or [])
        self.previous_metadata = state.get("planner_metadata") or {}
        
    async def execute(self) -> ExecutionPlan:
        prompt = LLM_PLANNER_PROMPT + f"\n\nUSER MESSAGE: {self.text}\nPREVIOUS PLANNER METADATA: {json.dumps(self.previous_metadata)}\n\nOUTPUT:"
        
        response_text = await complete_text([{"role": "system", "content": prompt}], max_output_tokens=1000)
        
        parsed = _extract_json(response_text)
        if not parsed:
            raise ValueError("LLM returned invalid or empty JSON")
            
        confidence = parsed.get("confidence", 1.0)
        if confidence < 0.65:
            raise ValueError(f"LLM planner confidence ({confidence}) is below threshold 0.65")
            
        plan = ExecutionPlan()
        plan.reasoning = parsed.get("reasoning", "")
        plan.confidence = confidence
        
        for t_dict in parsed.get("tasks", []):
            task_type = t_dict.get("task_type")
            if task_type == "retrieve":
                plan.tasks.append(PlannerTask.create_retrieve(
                    retriever=t_dict.get("retriever"),
                    action=t_dict.get("action"),
                    task_id=t_dict.get("task_id"),
                    depends_on=t_dict.get("depends_on") or []
                ))
            elif task_type == "action":
                plan.tasks.append(PlannerTask.create_action(
                    action_handler=t_dict.get("action_handler"),
                    task_id=t_dict.get("task_id"),
                    depends_on=t_dict.get("depends_on") or []
                ))
                
        # Parse metadata and workflow (deep merge)
        import copy
        plan.metadata = copy.deepcopy(self.previous_metadata)
        
        # Only overwrite with fields explicitly returned by planner
        returned_meta = parsed.get("metadata", {})
        for k, v in returned_meta.items():
            if isinstance(v, dict) and isinstance(plan.metadata.get(k), dict):
                plan.metadata[k].update(v)
            else:
                plan.metadata[k] = v
                
        plan.metadata["query_type"] = parsed.get("query_type", "general")
        
        wf_dict = parsed.get("workflow")
        if wf_dict:
            plan.metadata["active_workflow"] = wf_dict
            
        # Manually populate task parameters from metadata for appointment capabilities
        # (replicating legacy planner logic)
        for task in plan.tasks:
            cap = task.capability_name
            if cap in ["APPOINTMENT_SEARCH_SLOTS", "APPOINTMENT_BOOK", "APPOINTMENT_CANCEL", "APPOINTMENT_RESCHEDULE"]:
                if plan.metadata.get("doctor_name"):
                    task.parameters["doctor_name"] = plan.metadata["doctor_name"]
                if plan.metadata.get("booking_datetime"):
                    task.parameters["booking_datetime"] = plan.metadata["booking_datetime"]
                if plan.metadata.get("booking_ordinal"):
                    task.parameters["booking_ordinal"] = plan.metadata["booking_ordinal"]
            
        # Ensure fallback legacy strategy is set (since executor expects it)
        plan.metadata["retrieval_strategy"] = "multi" if len(plan.tasks) > 1 else plan.tasks[0].capability_name if plan.tasks else "general"
        if plan.tasks and plan.tasks[0].capability_name in ["APPOINTMENT_SEARCH_SLOTS", "APPOINTMENT_BOOK", "APPOINTMENT_CANCEL"]:
            plan.metadata["retrieval_strategy"] = "APPOINTMENT_SEARCH_SLOTS"

        # Apply legacy strategy to parameters as well, to mimic rule-based planner behavior
        legacy_strategy = plan.metadata["retrieval_strategy"]
        for task in plan.tasks:
            if not task.parameters:
                task.parameters = {}
            task.parameters["retrieval_strategy"] = legacy_strategy

        return plan
