from typing import Any
from abc import ABC, abstractmethod
from .parsers.document_query_parser import parse_document_query
from .parsers.intent_parser import ParsedIntent
from .retrieval_strategy import RetrievalStrategy
from .models.planner_task import PlannerTask

class PlannerRule(ABC):
    @abstractmethod
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        pass
        
    @abstractmethod
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[PlannerTask]:
        pass

class AppointmentRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        if parsed_intent.is_appointment:
            return True
        return strategy == RetrievalStrategy.APPOINTMENT_QUERY.value
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[PlannerTask]:
        if parsed_intent.is_appointment:
            metadata["query_type"] = "appointment"
            if "cardiologist" in parsed_intent.entities:
                metadata["detected_entities"].append("cardiologist")
            if "book" in parsed_intent.actions:
                metadata["detected_actions"].append("book")
            return [
                PlannerTask.create_action("APPOINTMENT_SEARCH"),
                PlannerTask.create_action("DOCTOR_SEARCH")
            ]
            
        action_handler = "APPOINTMENT_SEARCH"
        if "cancel" in parsed_intent.actions:
            action_handler = "APPOINTMENT_CANCEL"
        elif "reschedule" in parsed_intent.actions:
            action_handler = "APPOINTMENT_RESCHEDULE"
        elif "book" in parsed_intent.actions:
            action_handler = "APPOINTMENT_BOOK"
        elif "list" in parsed_intent.actions:
            action_handler = "APPOINTMENT_LIST"
            
        return [PlannerTask.create_action(action_handler, {"retrieval_strategy": strategy})]

class ConsultationRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        if parsed_intent.is_consultation:
            return True
        return strategy == RetrievalStrategy.CONSULTATION_QUERY.value
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[PlannerTask]:
        if parsed_intent.intent_type == "symptom":
            metadata["query_type"] = "symptom"
            if "chest pain" in parsed_intent.entities:
                metadata["detected_entities"].append("chest pain")
            return [PlannerTask.create_retrieve("MEMORY"), PlannerTask.create_retrieve("CONSULTATION")]
            
        elif parsed_intent.intent_type == "consultation":
            metadata["query_type"] = "consultation"
            if "last_time" in parsed_intent.actions:
                return [PlannerTask.create_retrieve("MEMORY"), PlannerTask.create_retrieve("CONSULTATION")]
            return [PlannerTask.create_retrieve("CONSULTATION")]
                
        action = "retrieve"
        if "history" in parsed_intent.actions:
            action = "history"
        return [PlannerTask.create_retrieve("CONSULTATION", action, {"retrieval_strategy": strategy})]

class PatientHistoryRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        return parsed_intent.is_history
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[PlannerTask]:
        metadata["query_type"] = "patient_history"
        if parsed_intent.history_type:
            metadata["history_type"] = parsed_intent.history_type
            
        return [PlannerTask.create_retrieve("PATIENT_HISTORY")]

class DocumentRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        return parse_document_query(parsed_intent.original_text) is not None
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[PlannerTask]:
        doc_intent = parse_document_query(parsed_intent.original_text)
        if doc_intent:
            if metadata.get("query_type") == "general":
                metadata["query_type"] = "document"
            metadata["document_type"] = doc_intent.document_type
            metadata["report_type"] = doc_intent.report_type
            metadata["comparison_requested"] = doc_intent.comparison_requested
            if doc_intent.detected_entities:
                metadata["detected_entities"].extend(doc_intent.detected_entities)
                
            return [PlannerTask.create_retrieve("ASSET_INDEX", doc_intent.action)]
        return []

class MemoryRule(PlannerRule):
    def matches(self, parsed_intent: ParsedIntent, strategy: str | None = None) -> bool:
        return strategy == RetrievalStrategy.MEMORY_QUERY.value
        
    def build_tasks(self, parsed_intent: ParsedIntent, metadata: dict[str, Any], strategy: str | None = None) -> list[PlannerTask]:
        return [PlannerTask.create_retrieve("MEMORY", None, {"retrieval_strategy": strategy})]

PLANNER_RULES = [
    PatientHistoryRule(),
    DocumentRule(),
    AppointmentRule(),
    ConsultationRule(),
    MemoryRule()
]
