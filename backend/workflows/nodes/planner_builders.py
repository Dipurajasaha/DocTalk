from typing import Any
from ..parsers.document_query_parser import parse_document_query
from ..retrieval_strategy import RetrievalStrategy

def build_patient_history_tasks(text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    history_keywords = [
        "do i have", "medical history", "history", "medications", "medication", 
        "surgery", "surgeries", "allergy", "allergies", "diagnosed with", "conditions"
    ]
    if any(kw in text for kw in history_keywords):
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
    return []

def build_document_tasks(text: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
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

def build_appointment_tasks(text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
    if "cardiologist" in text and "book" in text:
        metadata["query_type"] = "appointment"
        metadata["detected_entities"].append("cardiologist")
        metadata["detected_actions"].append("book")
        return [
            {"task": "retrieve", "retriever": "APPOINTMENT", "action": "search", "parameters": {}}, 
            {"task": "retrieve", "retriever": "DOCTOR_SEARCH", "action": None, "parameters": {}}
        ]
        
    if strategy == RetrievalStrategy.APPOINTMENT_QUERY.value:
        action = "search"
        if "cancel" in text:
            action = "cancel"
        elif "reschedule" in text:
            action = "reschedule"
        elif "book" in text or "schedule" in text:
            action = "book"
        elif "upcoming" in text or "show" in text or "list" in text:
            action = "list"
            
        return [{"task": "retrieve", "retriever": "APPOINTMENT", "action": action, "parameters": {"retrieval_strategy": strategy}}]
    return []

def build_consultation_tasks(text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
    if "chest pain" in text:
        metadata["query_type"] = "symptom"
        metadata["detected_entities"].append("chest pain")
        return [{"task": "retrieve", "retriever": "MEMORY", "action": None, "parameters": {}}, {"task": "retrieve", "retriever": "CONSULTATION", "action": None, "parameters": {}}]
        
    elif "recommend" in text:
        metadata["query_type"] = "consultation"
        if "last time" in text:
            return [{"task": "retrieve", "retriever": "MEMORY", "action": None, "parameters": {}}, {"task": "retrieve", "retriever": "CONSULTATION", "action": None, "parameters": {}}]
        return [{"task": "retrieve", "retriever": "CONSULTATION", "action": None, "parameters": {}}]
            
    if strategy == RetrievalStrategy.CONSULTATION_QUERY.value:
        action = "retrieve"
        if "previous" in text or "history" in text or "last" in text:
            action = "history"
        return [{"task": "retrieve", "retriever": "CONSULTATION", "action": action, "parameters": {"retrieval_strategy": strategy}}]
        
    return []

def build_memory_tasks(text: str, metadata: dict[str, Any], strategy: str | None = None) -> list[dict[str, Any]]:
    if strategy == RetrievalStrategy.MEMORY_QUERY.value:
        return [{"task": "retrieve", "retriever": "MEMORY", "action": None, "parameters": {"retrieval_strategy": strategy}}]
    return []
