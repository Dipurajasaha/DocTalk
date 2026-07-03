from typing import Any
from abc import ABC, abstractmethod
from .parsers.document_query_parser import parse_document_query
from .parsers.intent_parser import ParsedIntent
from .retrieval_strategy import RetrievalStrategy
from ..models.task_template import TaskTemplate
from .planner_rule_config import APPOINTMENT_RULE_CONFIG, CONSULTATION_RULE_CONFIG, PATIENT_HISTORY_RULE_CONFIG, DOCTOR_AVAILABILITY_RULE_CONFIG

class PlannerRule(ABC):
    @abstractmethod
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        pass
        
    @abstractmethod
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[TaskTemplate]:
        pass

class AppointmentRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        if parsed_intent.is_appointment:
            return True
        return strategy == RetrievalStrategy.APPOINTMENT_QUERY.value
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[TaskTemplate]:
        action_handler = "APPOINTMENT"
        action = "all"
        
        if parsed_intent.is_appointment:
            metadata["query_type"] = "appointment"
            for entity in APPOINTMENT_RULE_CONFIG["entities"]:
                if entity in parsed_intent.entities:
                    metadata["detected_entities"].append(entity)
                    
        if "cancel" in parsed_intent.actions:
            action_handler = "APPOINTMENT_CANCEL"
            metadata["detected_actions"].append("cancel")
        elif "reschedule" in parsed_intent.actions:
            action_handler = "APPOINTMENT_RESCHEDULE"
            metadata["detected_actions"].append("reschedule")
        elif "book" in parsed_intent.actions:
            action_handler = "APPOINTMENT_BOOK"
            metadata["detected_actions"].append("book")
        elif "upcoming" in parsed_intent.actions:
            action = "upcoming"
            metadata["detected_actions"].append("upcoming")
        elif "list" in parsed_intent.actions:
            action = "all"
            metadata["detected_actions"].append("list")
            
        params = {"retrieval_strategy": strategy, "action": action}
        if action_handler == "APPOINTMENT_BOOK":
            if parsed_intent.booking_datetime:
                params["booking_datetime"] = parsed_intent.booking_datetime
            if parsed_intent.booking_ordinal:
                params["booking_ordinal"] = parsed_intent.booking_ordinal
                
        return [TaskTemplate(action_handler, params)]

class DoctorAvailabilityRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        return strategy == RetrievalStrategy.DOCTOR_AVAILABILITY_QUERY.value
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[TaskTemplate]:
        metadata["query_type"] = "doctor_availability"
        
        params = {"retrieval_strategy": strategy}
        if parsed_intent.doctor_name:
            metadata["doctor_name"] = parsed_intent.doctor_name
            params["doctor_name"] = parsed_intent.doctor_name
            
        return [TaskTemplate("DOCTOR_AVAILABILITY", params)]

class ConsultationRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        if parsed_intent.is_consultation:
            return True
        return strategy == RetrievalStrategy.CONSULTATION_QUERY.value
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[TaskTemplate]:
        if parsed_intent.intent_type == "symptom":
            metadata["query_type"] = "symptom"
            for entity in CONSULTATION_RULE_CONFIG["entities"]:
                if entity in parsed_intent.entities:
                    metadata["detected_entities"].append(entity)
            return [TaskTemplate("MEMORY"), TaskTemplate("CONSULTATION")]
            
        elif parsed_intent.intent_type == "consultation":
            metadata["query_type"] = "consultation"
            if "last_time" in parsed_intent.actions:
                return [TaskTemplate("MEMORY"), TaskTemplate("CONSULTATION")]
            return [TaskTemplate("CONSULTATION")]
                
        action = "retrieve"
        if "history" in parsed_intent.actions:
            action = "history"
        return [TaskTemplate("CONSULTATION", {"action": action, "retrieval_strategy": strategy})]

class PatientHistoryRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        return parsed_intent.is_history
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[TaskTemplate]:
        metadata["query_type"] = "patient_history"
        if parsed_intent.history_type:
            metadata["history_type"] = parsed_intent.history_type
            
        return [TaskTemplate("PATIENT_HISTORY")]

class DocumentRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        return parse_document_query(parsed_intent.original_text) is not None
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[TaskTemplate]:
        doc_intent = parse_document_query(parsed_intent.original_text)
        if doc_intent:
            if metadata.get("query_type") == "general":
                metadata["query_type"] = "document"
            metadata["document_type"] = doc_intent.document_type
            metadata["report_type"] = doc_intent.report_type
            metadata["comparison_requested"] = doc_intent.comparison_requested
            if doc_intent.detected_entities:
                metadata["detected_entities"].extend(doc_intent.detected_entities)
                
            return [TaskTemplate("ASSET_INDEX", {"action": doc_intent.action})]
        return []

class MemoryRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        return strategy == RetrievalStrategy.MEMORY_QUERY.value
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[TaskTemplate]:
        return [TaskTemplate("MEMORY", {"retrieval_strategy": strategy})]
