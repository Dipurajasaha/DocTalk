from dataclasses import dataclass, field

@dataclass
class DocumentQueryIntent:
    action: str | None = None
    document_type: str | None = None
    report_type: str | None = None
    comparison_requested: bool = False
    latest_requested: bool = False
    detected_entities: list[str] = field(default_factory=list)

def parse_document_query(text: str) -> DocumentQueryIntent | None:
    text = text.lower()
    
    intent = DocumentQueryIntent()
    matched = False
    
    if "compare" in text:
        intent.action = "compare"
        intent.comparison_requested = True
        matched = True
    elif "latest" in text or "last" in text:
        intent.action = "latest"
        intent.latest_requested = True
        matched = True
    elif any(k in text for k in ["analyze", "summarize", "review", "what does my"]):
        intent.action = "analyze"
        matched = True
        
    if not matched:
        return None

    if "blood" in text:
        intent.document_type = "lab_report"
        intent.report_type = "blood_test"
        intent.detected_entities.append("blood report")
    elif "mri" in text:
        intent.document_type = "imaging"
        intent.report_type = "mri"
        intent.detected_entities.append("mri")
    elif "prescription" in text:
        intent.document_type = "prescription"
        intent.report_type = "medication"
        intent.detected_entities.append("prescription")
    elif "report" in text:
        intent.document_type = "medical_record"
        intent.report_type = "general"
    else:
        return None
        
    return intent
