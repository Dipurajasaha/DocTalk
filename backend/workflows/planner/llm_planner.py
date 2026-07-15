import copy
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
- PATIENT_HISTORY: Fetch structured patient medical history including medications, prescriptions, vitals, conditions, symptoms, and diagnoses
- CONSULTATION: Fetch previous doctor-patient consultation sessions and their messages
- MEMORY: Fetch patient summary
- ASSET_INDEX: Fetch uploaded documents including prescriptions, clinical notes, symptoms, lab reports, and medical records via RAG search
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
6. If the user selects a slot (e.g. "Book the first available slot"), use APPOINTMENT_BOOK directly and set "booking_ordinal" or "booking_datetime" in metadata.
7. If the user confirms a booking (e.g. "Yes, please book it"), use APPOINTMENT_BOOK.
8. If the user asks to cancel an appointment (e.g. "Cancel my appointment"), use APPOINTMENT_CANCEL.
9. For general greetings (e.g. "Hello", "Hi"), return NO tasks and "query_type": "general". DO NOT include workflow or appointment metadata.
10. For general medical knowledge (e.g. "Tell me about anemia", "What is diabetes?"), return NO tasks and "query_type": "knowledge". DO NOT include workflow or appointment metadata.
11. Always preserve the active_workflow if we are in the middle of a booking, UNLESS the query is unrelated (general or knowledge) or cancelled. For unrelated queries, omit workflow metadata entirely to prevent context pollution.
11a. If the user says payment was successful, paid, or completed while a booking is waiting for payment confirmation, treat it as confirmation of the existing appointment. Do NOT search slots again, do NOT reserve a new slot, and do NOT create a fresh booking.
12. If PREVIOUS PLANNER METADATA contains `recommended_specialty` and the user accepts it (e.g. "Yes", "Find one", "Book it"), use APPOINTMENT_SEARCH_SLOTS. If there is a `recommended_doctor_name`, set "doctor_name" in metadata. Otherwise set "specialty" in metadata to the `recommended_specialty`.
13. CONTEXT-AWARE FOLLOW-UPS: If the user's message is a follow-up or ambiguous (e.g., "what are the symptoms?", "what did they say?"), look at PREVIOUS PLANNER METADATA. If the previous `query_type` was "rag" or related to a document/prescription, use ASSET_INDEX. If the previous `query_type` was "consultation" or related to a doctor visit, use CONSULTATION.

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
          "action": "latest|compare (only for ASSET_INDEX if explicitly requested latest or comparison)",
          "depends_on": []
      }
  ],
  "workflow": {
      "type": "appointment_booking",
      "status": "waiting_selection|waiting_confirmation|cancelled"
  },
  "metadata": {
      "doctor_name": "Doctor name if detected",
      "specialty": "Specialty if detected",
      "booking_datetime": "Slot time if detected",
      "booking_ordinal": "e.g. 'first' if detected",
      "document_type": "e.g. lab_report, prescription, imaging, medical_record (use medical_record if unsure)",
      "report_type": "e.g. blood_test, xray, mri, ct, prescription, general (use general if unsure)",
      "limit": "Integer e.g. 2, 5, 10 if explicitly requested",
      "time_range": "e.g. '2_months', '1_year', '6_months' if explicitly requested"
  }
}

Examples:
USER: "Hello!"
OUTPUT: {"confidence":1.0,"reasoning":"Greeting detected","query_type":"general","tasks":[],"metadata":{}}

USER: "Tell me about anemia."
OUTPUT: {"confidence":0.98,"reasoning":"Medical knowledge query","query_type":"knowledge","tasks":[],"metadata":{}}

USER: "Explain my latest blood report."
OUTPUT: {"confidence":0.95,"reasoning":"Needs asset and memory","query_type":"rag","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"ASSET_INDEX","action":"latest","depends_on":[]},{"task_id":"t2","task_type":"retrieve","retriever":"MEMORY","depends_on":[]}],"metadata":{"document_type":"lab_report","report_type":"blood_test"}}

USER: "Compare my last two blood reports."
OUTPUT: {"confidence":0.95,"reasoning":"Needs multiple assets for comparison","query_type":"rag","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"ASSET_INDEX","action":"compare","depends_on":[]},{"task_id":"t2","task_type":"retrieve","retriever":"MEMORY","depends_on":[]}],"metadata":{"document_type":"lab_report","report_type":"blood_test","limit":2}}

USER: "What were my blood test results over the last 6 months?"
OUTPUT: {"confidence":0.95,"reasoning":"Needs assets within a time range","query_type":"rag","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"ASSET_INDEX","action":"compare","depends_on":[]},{"task_id":"t2","task_type":"retrieve","retriever":"MEMORY","depends_on":[]}],"metadata":{"document_type":"lab_report","report_type":"blood_test","time_range":"6_months"}}

USER: "Summarize my previous consultations."
OUTPUT: {"confidence":0.95,"reasoning":"Needs consultation history","query_type":"rag","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"CONSULTATION","depends_on":[]}],"metadata":{}}

USER: "Is there any appointment slots available for Dr. DocDipu?"
OUTPUT: {"confidence":0.92,"reasoning":"Search slots for specific doctor","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"APPOINTMENT_SEARCH_SLOTS","depends_on":[]}],"metadata":{"doctor_name":"DocDipu"}}

USER: "Book the first available slot." (Context: Waiting for selection)
OUTPUT: {"confidence":0.90,"reasoning":"Selecting first ordinal slot","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"action","action_handler":"APPOINTMENT_BOOK","depends_on":[]}],"workflow":{"type":"appointment_booking","status":"confirmed"},"metadata":{"booking_ordinal":"first"}}

USER: "Yes, please book it." (Context: Waiting for confirmation)
OUTPUT: {"confidence":0.95,"reasoning":"Confirming booking","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"action","action_handler":"APPOINTMENT_BOOK","depends_on":[]}],"workflow":{"type":"appointment_booking","status":"confirmed"},"metadata":{}}

USER: "Payment successful." (Context: Waiting for payment confirmation)
OUTPUT: {"confidence":1.0,"reasoning":"Payment completed for the pending appointment","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"action","action_handler":"APPOINTMENT_BOOK","depends_on":[]}],"workflow":{"type":"appointment_booking","status":"confirmed"},"metadata":{"payment_successful":true}}

USER: "Cancel my appointment."
OUTPUT: {"confidence":0.98,"reasoning":"Canceling appointment","query_type":"workflow","tasks":[{"task_id":"t1","task_type":"action","action_handler":"APPOINTMENT_CANCEL","depends_on":[]}],"metadata":{}}

USER: "What medicines did the doctor prescribe?"
OUTPUT: {"confidence":0.95,"reasoning":"Needs patient medication history and prescription documents","query_type":"rag","tasks":[{"task_id":"t1","task_type":"retrieve","retriever":"PATIENT_HISTORY","depends_on":[]},{"task_id":"t2","task_type":"retrieve","retriever":"ASSET_INDEX","depends_on":[]}],"metadata":{}}
"""

class LLMPlanningEngine:
    def __init__(self, state: UnifiedChatState):
        self.state = state
        self.text = latest_message_text(state.get("messages") or [])
        self.previous_metadata = copy.deepcopy(state.get("planner_metadata") or {})
        incoming_active_workflow = state.get("active_workflow")
        if isinstance(incoming_active_workflow, dict):
            self.previous_metadata["active_workflow"] = copy.deepcopy(incoming_active_workflow)
        incoming_payment_order = state.get("payment_order")
        if isinstance(incoming_payment_order, dict):
            self.previous_metadata["payment_order"] = copy.deepcopy(incoming_payment_order)
        self.previous_metadata.pop("payment_successful", None)
        self.current_payment_successful = bool(
            (state.get("context_payload") or {}).get("payment_successful")
            or "payment successful" in self.text.lower()
            or "payment complete" in self.text.lower()
            or "payment completed" in self.text.lower()
            or "paid successfully" in self.text.lower()
        )

    def _is_payment_confirmation_turn(self) -> bool:
        text = self.text.lower()
        active_wf = ActiveWorkflow.from_dict(self.previous_metadata.get("active_workflow") or {})
        if not active_wf or active_wf.status not in ("waiting_confirmation", "waiting_payment_confirmation"):
            return False

        return self.current_payment_successful and any(
            phrase in text
            for phrase in (
                "payment successful",
                "payment complete",
                "payment completed",
                "paid successfully",
                "payment is successful",
                "paid",
            )
        )

    def _build_payment_confirmation_plan(self) -> ExecutionPlan:
        plan = ExecutionPlan()
        plan.reasoning = "Payment completed for the pending appointment"
        plan.confidence = 1.0

        task = PlannerTask.create_action(
            action_handler="APPOINTMENT_BOOK",
            task_id="t1",
            depends_on=[],
        )

        active_wf = ActiveWorkflow.from_dict(self.previous_metadata.get("active_workflow") or {})
        wf_ctx = active_wf.context if active_wf else {}
        payment_order = self.previous_metadata.get("payment_order") or {}

        if self.previous_metadata.get("doctor_name") or wf_ctx.get("doctor_name"):
            task.parameters["doctor_name"] = self.previous_metadata.get("doctor_name") or wf_ctx.get("doctor_name")
        if self.previous_metadata.get("booking_datetime") or wf_ctx.get("appointment_time") or wf_ctx.get("selected_slot"):
            task.parameters["booking_datetime"] = (
                self.previous_metadata.get("booking_datetime")
                or wf_ctx.get("appointment_time")
                or wf_ctx.get("selected_slot")
            )
        if self.previous_metadata.get("booking_ordinal") or wf_ctx.get("selection_type") or wf_ctx.get("booking_ordinal"):
            task.parameters["booking_ordinal"] = (
                self.previous_metadata.get("booking_ordinal")
                or wf_ctx.get("selection_type")
                or wf_ctx.get("booking_ordinal")
            )
        if wf_ctx.get("appointment_id") or payment_order.get("appointment_id"):
            task.parameters["appointment_id"] = wf_ctx.get("appointment_id") or payment_order.get("appointment_id")
        if wf_ctx.get("slot_id") or payment_order.get("slot_id"):
            task.parameters["slot_id"] = wf_ctx.get("slot_id") or payment_order.get("slot_id")
        task.parameters["payment_successful"] = True

        plan.tasks.append(task)
        plan.metadata = copy.deepcopy(self.previous_metadata)
        plan.metadata["query_type"] = "workflow"
        plan.metadata["payment_successful"] = True
        plan.metadata["active_workflow"] = {
            "type": "appointment_booking",
            "status": "confirmed",
            "context": {
                **dict(wf_ctx or {}),
                "appointment_id": wf_ctx.get("appointment_id") or payment_order.get("appointment_id"),
                "slot_id": wf_ctx.get("slot_id") or payment_order.get("slot_id"),
                "doctor_id": wf_ctx.get("doctor_id") or payment_order.get("doctor_id"),
                "amount": wf_ctx.get("amount") or payment_order.get("amount"),
                "currency": wf_ctx.get("currency") or payment_order.get("currency"),
                "payment_stage": "confirmed",
            },
        }
        plan.metadata["retrieval_strategy"] = "APPOINTMENT_SEARCH_SLOTS"
        return plan

    async def execute(self) -> ExecutionPlan:
        if self._is_payment_confirmation_turn():
            return self._build_payment_confirmation_plan()

        prompt = LLM_PLANNER_PROMPT + f"\n\nUSER MESSAGE: {self.text}\nPREVIOUS PLANNER METADATA: {json.dumps(self.previous_metadata)}\n\nOUTPUT:"
        
        response_text = await complete_text([{"role": "system", "content": prompt}], max_output_tokens=1000)
        
        parsed = _extract_json(response_text)
        if not parsed:
            from backend.utils.logger import log_error
            log_error(f"LLM Planner JSON extraction failed. Raw output:\n{response_text}")
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
