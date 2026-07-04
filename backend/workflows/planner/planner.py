from __future__ import annotations
from typing import Any

from ..graph.common import latest_message_text
from ..graph.state import UnifiedChatState
from .parsers.intent_parser import parse_intent, ParsedIntent
from .parsers.document_query_parser import parse_document_query
from ..models.planner_task import PlannerTask
from ..models.execution_plan import ExecutionPlan
from .planner_rule_config import APPOINTMENT_RULE_CONFIG, CONSULTATION_RULE_CONFIG, PATIENT_HISTORY_RULE_CONFIG

class PlanningEngine:
    def __init__(self, state: UnifiedChatState):
        self.state = state
        self.text = latest_message_text(state.get("messages") or []).lower()
        self.plan = ExecutionPlan()
        self.plan.metadata = {
            "query_type": "general",
            "detected_entities": [],
            "detected_actions": []
        }
        self.intent: ParsedIntent | None = None
        
    def determine_goal(self):
        self.intent = parse_intent(self.text)
        
        if self.intent.is_appointment or any(k in self.text for k in [
            "appointment", "reschedule", "cancel", "upcoming", "schedule",
            "cardiologist", "book this", "reserve this", "book slot",
            "confirm this", "book", "reserve",
        ]):
            self.plan.goals.append("manage_appointment")
            
        if any(k in self.text for k in [
            "doctor available", "available doctor", "doctor slot", "open slots",
            "open appointments", "slots open", "is dr", "is dr.", "is doctor",
            "available on", "availability", "when is", "free slots", "any slots",
            "check slots", "show slots", "available slots",
        ]):
            self.plan.goals.append("check_doctor_availability")
            
        if self.intent.is_consultation or any(k in self.text for k in [
            "previous consultation", "doctor recommend", "last consultation",
            "what did doctor say", "last visit", "follow up", "recommend",
        ]):
            self.plan.goals.append("review_consultation")
            
        if self.intent.is_history:
            self.plan.goals.append("review_patient_history")
            
        if parse_document_query(self.intent.original_text) is not None or any(k in self.text for k in [
            "latest report", "last report", "compare reports", "blood report",
            "analyze my report", "analyze my blood", "summarize my report",
            "review my report", "what does my report", "cbc report",
            "hemoglobin", "hb level", "pcv level", "rbc count", "wbc count",
            "platelet", "blood test", "prescription",
        ]):
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
                elif "book" in self.intent.actions: meta["detected_actions"].append("book")
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
        
        for goal in self.plan.goals:
            if goal == "manage_appointment":
                action_handler = "APPOINTMENT"
                action = "all"
                if "cancel" in self.intent.actions:
                    action_handler = "APPOINTMENT_CANCEL"
                elif "reschedule" in self.intent.actions:
                    action_handler = "APPOINTMENT_RESCHEDULE"
                elif "book" in self.intent.actions:
                    action_handler = "APPOINTMENT_BOOK"
                elif "upcoming" in self.intent.actions:
                    action = "upcoming"
                elif "list" in self.intent.actions:
                    action = "all"
                    
                params = {"action": action}
                if action_handler == "APPOINTMENT_BOOK":
                    if self.intent.booking_datetime: params["booking_datetime"] = self.intent.booking_datetime
                    if self.intent.booking_ordinal: params["booking_ordinal"] = self.intent.booking_ordinal
                    
                if action_handler == "APPOINTMENT":
                    tasks.append(PlannerTask.create_retrieve("APPOINTMENT", parameters=params))
                else:
                    tasks.append(PlannerTask.create_action(action_handler, parameters=params))
                    
            elif goal == "check_doctor_availability":
                params = {}
                if self.intent.doctor_name:
                    params["doctor_name"] = self.intent.doctor_name
                tasks.append(PlannerTask.create_retrieve("DOCTOR_AVAILABILITY", parameters=params))
                
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
            return "DOCTOR_AVAILABILITY_QUERY"
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
        print(f"[DEBUG][INTENT_TYPE] {self.intent.intent_type or 'general'}")
        print(f"[DEBUG][ENTITY_TYPE] {self.intent.entities}")
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
