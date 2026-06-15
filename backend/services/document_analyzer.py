from __future__ import annotations

from datetime import datetime
from typing import Any


class DocumentAnalyzer:
    @staticmethod
    async def analyze_document(
        asset_id: str,
        patient_id: str,
        file_name: str,
        category: str,
        extracted_text: str,
        created_at: datetime | None = None
    ) -> dict[str, Any]:
        text_lower = extracted_text.lower()
        name_lower = file_name.lower()
        
        # 1. Determine Source Type
        source_type = "report"
        if category == "PRESCRIPTION":
            source_type = "prescription"
        elif category == "XRAY":
            source_type = "xray"
            
        # 2. Heuristic Classification
        document_type = "medical_record"
        report_type = "general"
        
        if "blood" in name_lower or "blood" in text_lower or "cbc" in text_lower:
            document_type = "lab_report"
            report_type = "blood_test"
        elif "mri" in name_lower or "mri" in text_lower:
            document_type = "imaging"
            report_type = "mri"
        elif "xray" in name_lower or "x-ray" in text_lower or category == "XRAY":
            document_type = "imaging"
            report_type = "xray"
        elif category == "PRESCRIPTION":
            document_type = "prescription"
            report_type = "medication"
            
        # 3. Text Generation
        title = file_name
        summary = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")
        if not summary.strip():
            summary = f"Automatically generated summary for {file_name}"
            
        # 4. Keyword Extraction
        keywords = []
        target_keywords = ["blood", "mri", "xray", "prescription", "heart", "glucose", "lipid", "cholesterol", "pain"]
        for kw in target_keywords:
            if kw in text_lower or kw in name_lower:
                keywords.append(kw)
                
        return {
            "assetId": asset_id,
            "patientId": patient_id,
            "fileName": file_name,
            "fileCategory": category,
            "sourceType": source_type,
            "documentType": document_type,
            "reportType": report_type,
            "documentDate": created_at or datetime.now(),
            "title": title,
            "summary": summary,
            "keywords": keywords,
        }

document_analyzer = DocumentAnalyzer()
