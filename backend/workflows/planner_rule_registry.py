from typing import Any
from abc import ABC, abstractmethod
from .parsers.document_query_parser import parse_document_query
from .retrieval_strategy import RetrievalStrategy

class PlannerRule(ABC):
    @abstractmethod
    def matches(self, text: str, strategy: str | None = None) -> bool:
        pass
        
    @abstractmethod
    def build_tasks(self, text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
        pass

class AppointmentRule(PlannerRule):
    def matches(self, text: str, strategy: str | None = None) -> bool:
        if "cardiologist" in text and "book" in text:
            return True
        return strategy == RetrievalStrategy.APPOINTMENT_QUERY.value
        
    def build_tasks(self, text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
        if "cardiologist" in text and "book" in text:
            metadata["query_type"] = "appointment"
            metadata["detected_entities"].append("cardiologist")
            metadata["detected_actions"].append("book")
            return [
                {"task": "action", "action_handler": "APPOINTMENT_SEARCH", "parameters": {}}, 
                {"task": "action", "action_handler": "DOCTOR_SEARCH", "parameters": {}}
            ]
            
        action_handler = "APPOINTMENT_SEARCH"
        if "cancel" in text:
            action_handler = "APPOINTMENT_CANCEL"
        elif "reschedule" in text:
            action_handler = "APPOINTMENT_RESCHEDULE"
        elif "book" in text or "schedule" in text:
            action_handler = "APPOINTMENT_BOOK"
        elif "upcoming" in text or "show" in text or "list" in text:
            action_handler = "APPOINTMENT_LIST"
            
        return [{"task": "action", "action_handler": action_handler, "parameters": {"retrieval_strategy": strategy}}]

class ConsultationRule(PlannerRule):
    def matches(self, text: str, strategy: str | None = None) -> bool:
        if "chest pain" in text or "recommend" in text:
            return True
        return strategy == RetrievalStrategy.CONSULTATION_QUERY.value
        
    def build_tasks(self, text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
        if "chest pain" in text:
            metadata["query_type"] = "symptom"
            metadata["detected_entities"].append("chest pain")
            return [{"task": "retrieve", "retriever": "MEMORY", "action": None, "parameters": {}}, {"task": "retrieve", "retriever": "CONSULTATION", "action": None, "parameters": {}}]
            
        elif "recommend" in text:
            metadata["query_type"] = "consultation"
            if "last time" in text:
                return [{"task": "retrieve", "retriever": "MEMORY", "action": None, "parameters": {}}, {"task": "retrieve", "retriever": "CONSULTATION", "action": None, "parameters": {}}]
            return [{"task": "retrieve", "retriever": "CONSULTATION", "action": None, "parameters": {}}]
                
        action = "retrieve"
        if "previous" in text or "history" in text or "last" in text:
            action = "history"
        return [{"task": "retrieve", "retriever": "CONSULTATION", "action": action, "parameters": {"retrieval_strategy": strategy}}]

class PatientHistoryRule(PlannerRule):
    def __init__(self):
        self.history_keywords = [
            "do i have", "medical history", "history", "medications", "medication", 
            "surgery", "surgeries", "allergy", "allergies", "diagnosed with", "conditions"
        ]

    def matches(self, text: str, strategy: str | None = None) -> bool:
        return any(kw in text for kw in self.history_keywords)
        
    def build_tasks(self, text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
        metadata["query_type"] = "patient_history"
        history_type = None
        if "medication" in text or "medications" in text:
            history_type = "medication"
        elif "surgery" in text or "surgeries" in text:
            history_type = "surgery"
        elif "allergy" in text or "allergies" in text:
            history_type = "allergy"
        elif "condition" in text or "conditions" in text or "diagnosed with" in text:
            history_type = "condition"
            
        if history_type:
            metadata["history_type"] = history_type
            
        return [{"task": "retrieve", "retriever": "PATIENT_HISTORY", "action": None, "parameters": {}}]

class DocumentRule(PlannerRule):
    def matches(self, text: str, strategy: str | None = None) -> bool:
        return parse_document_query(text) is not None
        
    def build_tasks(self, text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
        doc_intent = parse_document_query(text)
        if doc_intent:
            if metadata.get("query_type") == "general":
                metadata["query_type"] = "document"
            metadata["document_type"] = doc_intent.document_type
            metadata["report_type"] = doc_intent.report_type
            metadata["comparison_requested"] = doc_intent.comparison_requested
            if doc_intent.detected_entities:
                metadata["detected_entities"].extend(doc_intent.detected_entities)
                
            return [{"task": "retrieve", "retriever": "ASSET_INDEX", "action": doc_intent.action, "parameters": {}}]
        return []

class MemoryRule(PlannerRule):
    def matches(self, text: str, strategy: str | None = None) -> bool:
        return strategy == RetrievalStrategy.MEMORY_QUERY.value
        
    def build_tasks(self, text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
        return [{"task": "retrieve", "retriever": "MEMORY", "action": None, "parameters": {"retrieval_strategy": strategy}}]

PLANNER_RULES = [
    PatientHistoryRule(),
    DocumentRule(),
    AppointmentRule(),
    ConsultationRule(),
    MemoryRule()
]
