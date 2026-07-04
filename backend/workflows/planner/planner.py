from __future__ import annotations
from typing import Any

from ..graph.common import latest_message_text
from ..graph.state import UnifiedChatState
from .parsers.intent_parser import parse_intent, ParsedIntent
from .parsers.document_query_parser import parse_document_query
from ..models.planner_task import PlannerTask
from ..models.execution_plan import ExecutionPlan
from ..models.resolved_context import ResolvedContext
from ..models.active_workflow import ActiveWorkflow
from .planner_rule_config import APPOINTMENT_RULE_CONFIG, CONSULTATION_RULE_CONFIG, PATIENT_HISTORY_RULE_CONFIG
from .context_resolver import ContextResolver

class PlanningEngine:
    def __init__(self, state: UnifiedChatState):
        self.state = state
        self.text = latest_message_text(state.get("messages") or []).lower()
        self.plan = ExecutionPlan()
        
        previous_metadata = state.get("planner_metadata") or {}
        prev_wf_dict = previous_metadata.get("active_workflow")
        active_wf = ActiveWorkflow.from_dict(prev_wf_dict)
        wf_ctx = active_wf.context if (active_wf and active_wf.status != "cancelled") else {}
        
        doc_name_from_avail = None
        avail_context = state.get("doctor_availability_context") or []
        for avail in avail_context:
            if isinstance(avail, dict) and avail.get("doctor_name"):
                doc_name_from_avail = avail["doctor_name"]
                break
                
        self.plan.metadata = {
            "query_type": "general",
            "detected_entities": previous_metadata.get("detected_entities", []),
            "detected_actions": [],
            "doctor_name": wf_ctx.get("doctor_name") or previous_metadata.get("doctor_name") or doc_name_from_avail,
            "booking_datetime": wf_ctx.get("appointment_time") or wf_ctx.get("selected_slot") or previous_metadata.get("booking_datetime"),
            "booking_ordinal": wf_ctx.get("selection_type") or previous_metadata.get("booking_ordinal"),
            "active_workflow": active_wf.to_dict() if (active_wf and active_wf.status != "cancelled") else None,
        }
        # filter out Nones
        self.plan.metadata = {k: v for k, v in self.plan.metadata.items() if v is not None}
        self.intent: ParsedIntent | None = None
        self.resolved_context: ResolvedContext | None = None
        
    def determine_goal(self):
        self.intent = parse_intent(self.text)
        res_ctx = self.resolved_context

        # Check cancellation patterns ("never mind", "cancel this", "abort", "forget it", "don't book", "stop")
        is_workflow_cancellation = any(k in self.text for k in [
            "never mind", "nevermind", "cancel this", "abort", "forget it", "don't book", "stop booking"
        ])
        if is_workflow_cancellation:
            self.plan.metadata["active_workflow"] = None
            self.resolved_context = ResolvedContext(has_reference=False)
            res_ctx = self.resolved_context
        
        # Explicit patient appointment requests
        is_explicit_patient_appointment = any(k in self.text for k in [
            "my appointment", "my appointments", "list my", "show my", "my upcoming",
            "cancel my", "reschedule my"
        ]) or (
            any(a in self.intent.actions for a in ["cancel", "reschedule", "list", "upcoming"]) and 
            ("my" in self.text or "appointment" in self.text or self.intent.is_appointment)
            and not any(k in self.text for k in ["availability", "available", "doctor", "dr.", "dr "])
        )
        
        # Booking confirmation via active_workflow or resolved context
        active_wf_dict = self.plan.metadata.get("active_workflow")
        active_wf = ActiveWorkflow.from_dict(active_wf_dict) if active_wf_dict else None

        is_booking_confirmation = False
        if is_workflow_cancellation:
            is_booking_confirmation = False
        elif res_ctx and res_ctx.has_reference and res_ctx.reference_type == "ordinal":
            # Ordinal selection ("book the first available slot") proposes candidate, does NOT confirm yet
            is_booking_confirmation = False
        elif active_wf and active_wf.status == "waiting_confirmation":
            if res_ctx and (res_ctx.reference_type == "affirmation" or "yes" in self.text or "confirm" in self.text or "proceed" in self.text):
                is_booking_confirmation = True
            elif any(p in self.text for p in ["book it", "book this", "book this slot", "book now", "please book it"]):
                is_booking_confirmation = True
        elif res_ctx and res_ctx.has_reference and res_ctx.resolved_source == "doctor_availability" and res_ctx.reference_type == "affirmation":
            is_booking_confirmation = True
        elif "book" in self.intent.actions and (
            (self.plan.metadata.get("doctor_name") or self.intent.doctor_name) and
            (self.plan.metadata.get("booking_datetime") or self.intent.booking_datetime)
        ):
            if not (res_ctx and res_ctx.reference_type == "ordinal"):
                is_booking_confirmation = True

        is_availability = any(k in self.text for k in [
            "doctor available", "available doctor", "doctor slot", "open slots",
            "open appointments", "slots open", "is dr", "is dr.", "is doctor",
            "available on", "availability", "when is", "free slots", "any slots",
            "check slots", "show slots", "available slots", "appointment slots",
            "book", "reserve", "schedule"
        ]) or ("book" in self.intent.actions) or (res_ctx and res_ctx.reference_type == "ordinal")

        if is_explicit_patient_appointment or is_booking_confirmation:
            self.plan.goals.append("manage_appointment")
        elif is_availability:
            self.plan.goals.append("check_doctor_availability")
        elif self.intent.is_appointment or "appointment" in self.text:
            if "my" in self.text:
                self.plan.goals.append("manage_appointment")
            else:
                self.plan.goals.append("check_doctor_availability")
            
        if self.intent.is_consultation or any(k in self.text for k in [
            "previous consultation", "doctor recommend", "last consultation",
            "what did doctor say", "last visit", "follow up", "recommend",
        ]) or (res_ctx and res_ctx.has_reference and res_ctx.resolved_source == "consultation"):
            self.plan.goals.append("review_consultation")
            
        if self.intent.is_history or (res_ctx and res_ctx.has_reference and res_ctx.resolved_source == "patient_history"):
            self.plan.goals.append("review_patient_history")
            
        if parse_document_query(self.intent.original_text) is not None or any(k in self.text for k in [
            "latest report", "last report", "compare reports", "blood report",
            "analyze my report", "analyze my blood", "summarize my report",
            "review my report", "what does my report", "cbc report",
            "hemoglobin", "hb level", "pcv level", "rbc count", "wbc count",
            "platelet", "blood test", "prescription",
        ]) or (res_ctx and res_ctx.has_reference and res_ctx.resolved_source == "asset_selection"):
            self.plan.goals.append("review_document")
            
        if any(k in self.text for k in ["memory", "remember", "recall"]):
            self.plan.goals.append("access_memory")
            
        if not self.plan.goals:
            self.plan.goals.append("general_chat")
            
    def determine_required_information(self):
        meta = self.plan.metadata
        
        for goal in self.plan.goals:
            if goal == "manage_appointment":
                meta["query_type"] = "appointment"
                if self.intent.is_appointment:
                    for entity in APPOINTMENT_RULE_CONFIG["entities"]:
                        if entity in self.intent.entities:
                            meta["detected_entities"].append(entity)
                if "cancel" in self.intent.actions: meta["detected_actions"].append("cancel")
                elif "reschedule" in self.intent.actions: meta["detected_actions"].append("reschedule")
                elif "book" in self.intent.actions or (self.resolved_context and self.resolved_context.has_reference):
                    if "book" not in meta["detected_actions"]:
                        meta["detected_actions"].append("book")
                elif "upcoming" in self.intent.actions: meta["detected_actions"].append("upcoming")
                elif "list" in self.intent.actions: meta["detected_actions"].append("list")
                
            elif goal == "check_doctor_availability":
                meta["query_type"] = "doctor_availability"
                if self.intent.doctor_name:
                    meta["doctor_name"] = self.intent.doctor_name
                    
            elif goal == "review_consultation":
                if self.intent.intent_type == "symptom":
                    meta["query_type"] = "symptom"
                    for entity in CONSULTATION_RULE_CONFIG["entities"]:
                        if entity in self.intent.entities:
                            meta["detected_entities"].append(entity)
                elif self.intent.intent_type == "consultation":
                    meta["query_type"] = "consultation"
                    
            elif goal == "review_patient_history":
                meta["query_type"] = "patient_history"
                if self.intent.history_type:
                    meta["history_type"] = self.intent.history_type
                    
            elif goal == "review_document":
                doc_intent = parse_document_query(self.intent.original_text)
                if doc_intent:
                    meta["query_type"] = "document"
                    meta["document_type"] = doc_intent.document_type
                    meta["report_type"] = doc_intent.report_type
                    meta["comparison_requested"] = doc_intent.comparison_requested
                    if doc_intent.detected_entities:
                        meta["detected_entities"].extend(doc_intent.detected_entities)
                    
    def build_execution_plan(self):
        tasks = []
        res_ctx = self.resolved_context
        
        for goal in self.plan.goals:
            if goal == "manage_appointment":
                action_handler = "APPOINTMENT"
                action = "all"
                if "cancel" in self.intent.actions:
                    action_handler = "APPOINTMENT_CANCEL"
                elif "reschedule" in self.intent.actions:
                    action_handler = "APPOINTMENT_RESCHEDULE"
                elif "book" in self.intent.actions or (res_ctx and res_ctx.has_reference and res_ctx.resolved_source == "doctor_availability") or self.plan.metadata.get("active_workflow"):
                    action_handler = "APPOINTMENT_BOOK"
                elif "upcoming" in self.intent.actions:
                    action = "upcoming"
                elif "list" in self.intent.actions:
                    action = "all"
                    
                params = {"action": action}
                if action_handler == "APPOINTMENT_BOOK":
                    active_wf_dict = self.plan.metadata.get("active_workflow")
                    active_wf = ActiveWorkflow.from_dict(active_wf_dict) if active_wf_dict else None
                    wf_ctx = active_wf.context if active_wf else {}

                    booking_datetime = (
                        self.intent.booking_datetime or
                        self.plan.metadata.get("booking_datetime") or
                        wf_ctx.get("appointment_time") or
                        wf_ctx.get("selected_slot")
                    )
                    booking_ordinal = (
                        self.intent.booking_ordinal or
                        self.plan.metadata.get("booking_ordinal") or
                        wf_ctx.get("selection_type")
                    )

                    if res_ctx and res_ctx.has_reference:
                        if res_ctx.reference_type == "ordinal" and not booking_ordinal:
                            booking_ordinal = str(res_ctx.resolved_selection)
                        if res_ctx.resolved_entity.get("available_slots") and not booking_datetime:
                            slots = res_ctx.resolved_entity["available_slots"]
                            idx = res_ctx.metadata.get("ordinal_index", 0)
                            if isinstance(slots, list) and slots and abs(idx) < len(slots):
                                booking_datetime = slots[idx]

                    if booking_datetime:
                        params["booking_datetime"] = booking_datetime
                        self.plan.metadata["booking_datetime"] = booking_datetime
                    if booking_ordinal:
                        params["booking_ordinal"] = booking_ordinal
                        self.plan.metadata["booking_ordinal"] = booking_ordinal
                        
                    doc_name = (
                        params.get("doctor_name") or
                        self.plan.metadata.get("doctor_name") or
                        (res_ctx.resolved_entity.get("doctor_name") if res_ctx else None) or
                        wf_ctx.get("doctor_name")
                    )
                    if doc_name:
                        params["doctor_name"] = doc_name
                        self.plan.metadata["doctor_name"] = doc_name

                    # Update active_workflow state to executing
                    if active_wf:
                        active_wf.status = "executing"
                        self.plan.metadata["active_workflow"] = active_wf.to_dict()
                    
                if action_handler == "APPOINTMENT":
                    tasks.append(PlannerTask.create_retrieve("APPOINTMENT", parameters=params))
                else:
                    tasks.append(PlannerTask.create_action(action_handler, parameters=params))
                    
            elif goal == "check_doctor_availability":
                params = {}
                doc_name = self.intent.doctor_name or self.plan.metadata.get("doctor_name")
                if doc_name:
                    params["doctor_name"] = doc_name

                # Check if this is a new search replacing a previous doctor's workflow
                prev_wf_dict = self.plan.metadata.get("active_workflow")
                prev_wf = ActiveWorkflow.from_dict(prev_wf_dict) if prev_wf_dict else None
                if prev_wf and doc_name and prev_wf.context.get("doctor_name") and prev_wf.context.get("doctor_name").lower() != doc_name.lower():
                    prev_wf = None
                
                if res_ctx and res_ctx.has_reference and res_ctx.reference_type == "ordinal":
                    booking_ordinal = str(res_ctx.resolved_selection)
                    booking_datetime = None
                    slots = res_ctx.resolved_entity.get("available_slots") or []
                    idx = res_ctx.metadata.get("ordinal_index", 0)
                    if isinstance(slots, list) and slots and abs(idx) < len(slots):
                        booking_datetime = slots[idx]
                    
                    self.plan.metadata["booking_ordinal"] = booking_ordinal
                    if booking_datetime:
                        self.plan.metadata["booking_datetime"] = booking_datetime

                    # Fallback to existing contexts if missing from resolved entity
                    avail_ctx = self.state.get("doctor_availability_context") or []
                    avail_dict = avail_ctx[0] if isinstance(avail_ctx, list) and len(avail_ctx) > 0 else {}
                    prev_wf_dict = self.plan.metadata.get("active_workflow") or {}
                    prev_ctx = prev_wf_dict.get("context", {}) if isinstance(prev_wf_dict, dict) else {}

                    wf_context = {
                        "doctor_name": doc_name or res_ctx.resolved_entity.get("doctor_name") or avail_dict.get("doctor_name") or prev_ctx.get("doctor_name"),
                        "doctor_id": doc_name or res_ctx.resolved_entity.get("doctor_id") or avail_dict.get("doctor_id") or prev_ctx.get("doctor_id"),
                        "selected_slot": booking_datetime,
                        "appointment_time": booking_datetime,
                        "selection_type": booking_ordinal,
                        "available_slots": slots or avail_dict.get("available_slots") or prev_ctx.get("available_slots", []),
                    }
                    new_wf = ActiveWorkflow(
                        type="appointment_booking",
                        status="waiting_confirmation",
                        context=wf_context
                    )
                    self.plan.metadata["active_workflow"] = new_wf.to_dict()
                    tasks.append(PlannerTask.create_retrieve("APPOINTMENT_SEARCH_SLOTS", parameters=params))
                elif doc_name or ("book" in self.intent.actions):
                    wf_context = {
                        "doctor_name": doc_name,
                        "doctor_id": doc_name,
                        "available_slots": res_ctx.resolved_entity.get("available_slots") if res_ctx else []
                    }
                    new_wf = ActiveWorkflow(
                        type="appointment_booking",
                        status="waiting_selection",
                        context=wf_context
                    )
                    self.plan.metadata["active_workflow"] = new_wf.to_dict()
                    tasks.append(PlannerTask.create_retrieve("APPOINTMENT_SEARCH_SLOTS", parameters=params))
                else:
                    tasks.append(PlannerTask.create_retrieve("APPOINTMENT_SEARCH_SLOTS", parameters=params))
                
            elif goal == "review_consultation":
                if self.intent.intent_type == "symptom":
                    tasks.append(PlannerTask.create_retrieve("MEMORY"))
                    tasks.append(PlannerTask.create_retrieve("CONSULTATION"))
                elif self.intent.intent_type == "consultation":
                    if "last_time" in self.intent.actions:
                        tasks.append(PlannerTask.create_retrieve("MEMORY"))
                    tasks.append(PlannerTask.create_retrieve("CONSULTATION"))
                else:
                    action = "retrieve"
                    if "history" in self.intent.actions:
                        action = "history"
                    tasks.append(PlannerTask.create_retrieve("CONSULTATION", action=action))
                    
            elif goal == "review_patient_history":
                tasks.append(PlannerTask.create_retrieve("PATIENT_HISTORY"))
                
            elif goal == "review_document":
                doc_intent = parse_document_query(self.intent.original_text)
                if doc_intent:
                    tasks.append(PlannerTask.create_retrieve("ASSET_INDEX", action=doc_intent.action))
                else:
                    tasks.append(PlannerTask.create_retrieve("ASSET_INDEX", action="latest"))
                    
            elif goal == "access_memory":
                tasks.append(PlannerTask.create_retrieve("MEMORY"))
                
        self.plan.add_tasks(tasks)
        
    def order_tasks(self):
        self.plan.deduplicate()
        if not self.plan.tasks:
            self.plan.add_tasks([PlannerTask(task_type="general_response")])
            
    def derive_legacy_strategy(self) -> str:
        primary_goal = self.plan.goals[0] if self.plan.goals else "general_chat"
        if primary_goal == "manage_appointment":
            return "APPOINTMENT_QUERY"
        elif primary_goal == "check_doctor_availability":
            return "APPOINTMENT_SEARCH_SLOTS"
        elif primary_goal == "review_consultation":
            return "CONSULTATION_QUERY"
        elif primary_goal == "review_patient_history":
            return "PATIENT_HISTORY_QUERY"
        elif primary_goal == "review_document":
            return "DOCUMENT_QUERY"
        elif primary_goal == "access_memory":
            return "MEMORY_QUERY"
        return "GENERAL_CHAT"
            
    def execute(self) -> ExecutionPlan:
        print(f"[DEBUG][PLANNER] text = {self.text}")

        # ── 1. Run generic ContextResolver ────────────────────────────────
        self.resolved_context = ContextResolver(self.state, self.text).resolve()

        # Merge generic entity attributes from resolved_context into plan metadata
        if self.resolved_context and self.resolved_context.resolved_entity:
            res_ent = self.resolved_context.resolved_entity
            
            # If a new ordinal/selection is resolved, override previous selection metadata
            if self.resolved_context.reference_type == "ordinal":
                if res_ent.get("booking_datetime"):
                    self.plan.metadata["booking_datetime"] = res_ent["booking_datetime"]
                if self.resolved_context.resolved_selection:
                    self.plan.metadata["booking_ordinal"] = str(self.resolved_context.resolved_selection)

            for k, v in res_ent.items():
                if v is not None and (k not in self.plan.metadata or self.resolved_context.reference_type == "ordinal"):
                    self.plan.metadata[k] = v

            # Maintain active_workflow in planner_metadata
            if res_ent.get("doctor_name") or res_ent.get("available_slots") or res_ent.get("booking_datetime") or res_ent.get("selected_slot") or res_ent.get("appointment_time"):
                current_wf_dict = self.plan.metadata.get("active_workflow")
                current_wf = ActiveWorkflow.from_dict(current_wf_dict) if current_wf_dict else None
                wf_ctx = current_wf.context if current_wf else {}
                b_dt = (
                    res_ent.get("booking_datetime") or 
                    res_ent.get("appointment_time") or 
                    res_ent.get("selected_slot") or 
                    (self.intent.booking_datetime if self.intent else None) or 
                    self.plan.metadata.get("booking_datetime")
                )
                b_ord = self.plan.metadata.get("booking_ordinal") or res_ent.get("selection_type") or wf_ctx.get("selection_type")

                updated_ctx = {
                    **wf_ctx,
                    "doctor_name": res_ent.get("doctor_name") or wf_ctx.get("doctor_name") or self.plan.metadata.get("doctor_name"),
                    "doctor_id": res_ent.get("doctor_id") or wf_ctx.get("doctor_id") or res_ent.get("doctor_name"),
                    "selected_slot": b_dt,
                    "appointment_time": b_dt,
                    "selection_type": b_ord,
                    "available_slots": res_ent.get("available_slots") or wf_ctx.get("available_slots", []),
                }
                status = "waiting_confirmation" if updated_ctx.get("selected_slot") else "waiting_selection"
                new_wf = ActiveWorkflow(
                    type="appointment_booking",
                    status=status,
                    context=updated_ctx
                )
                self.plan.metadata["active_workflow"] = new_wf.to_dict()

        # ── 2. Standard Planner Pipeline ──────────────────────────────────
        self.determine_goal()
        self.determine_required_information()
        self.build_execution_plan()
        self.order_tasks()
        
        legacy_strategy = self.derive_legacy_strategy()
        for task in self.plan.tasks:
            if not task.parameters:
                task.parameters = {}
            task.parameters["retrieval_strategy"] = legacy_strategy

        print(f"[DEBUG][PLANNER] goals = {self.plan.goals}")
        print(f"[DEBUG][PLANNER] strategy = {legacy_strategy}")
        print("[DEBUG][PLANNER] execution_plan =", self.plan.tasks)
        print("[DEBUG][PLANNER_CLASSIFICATION]", self.plan.metadata)
        print(f"[DEBUG][PLANNER_DOCTOR_NAME] {self.plan.metadata.get('doctor_name')}")
        print(f"[DEBUG][INTENT_TYPE] {self.intent.intent_type or 'general' if self.intent else 'general'}")
        print(f"[DEBUG][RETRIEVER_SELECTED] {legacy_strategy}")
        
        return self.plan


async def planner_node(state: UnifiedChatState) -> dict[str, Any]:
    engine = PlanningEngine(state)
    plan = engine.execute()
    
    return {
        "execution_plan": plan.tasks,
        "planner_metadata": plan.metadata,
        "retrieval_strategy": engine.derive_legacy_strategy()
    }

