import json
import logging
from datetime import datetime
from typing import Any

from ..ai.core_services.llm_client import complete_json
from ..schemas.patient_history import CreatePatientHistory

logger = logging.getLogger(__name__)

class LabResultExtractor:
    async def extract_lab_results(
        self,
        asset_id: str,
        patient_id: str,
        file_name: str,
        extracted_text: str,
        created_at: datetime
    ) -> list[CreatePatientHistory]:
        
        prompt = """
        You are a clinical data extraction assistant.
        Extract all quantitative lab biomarkers from the provided text report.
        Return ONLY a JSON array of objects. Each object must have these keys:
        - "biomarker": (string) the name of the test, e.g., "Hemoglobin", "WBC", "PCV".
        - "value": (string or number) the measured result.
        - "unit": (string) the unit of measurement, if available, else "".
        - "reference_range": (string) the normal range, if available, else "".
        - "flag": (string) "HIGH", "LOW", "NORMAL", or "" if unknown.
        
        If no biomarkers are found, return an empty array [].
        """
        
        payload = extracted_text[:4000] # truncate just in case
        
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": str(payload)},
        ]
        
        try:
            response = await complete_json(messages, temperature=0.1, max_output_tokens=1024)
        except Exception as exc:
            logger.exception("LabResultExtractor LLM call failed", extra={"error": str(exc)})
            return []
            
        entries = []
        
        # LLM might wrap in an object e.g. {"results": [...]} or just return the list
        results = []
        if isinstance(response, list):
            results = response
        elif isinstance(response, dict):
            for v in response.values():
                if isinstance(v, list):
                    results = v
                    break
                    
        for r in results:
            if not isinstance(r, dict):
                continue
                
            biomarker = r.get("biomarker", "")
            if not biomarker:
                continue
                
            val = r.get("value", "")
            unit = r.get("unit", "")
            ref = r.get("reference_range", "")
            flag = r.get("flag", "")
            
            val_str = f"Value: {val}"
            if unit: val_str += f" {unit}"
            if ref: val_str += f" (Range: {ref})"
            if flag: val_str += f" [{flag}]"
            
            entries.append(
                CreatePatientHistory(
                    patientId=patient_id,
                    historyType="lab_result",
                    title=str(biomarker).capitalize(),
                    value=val_str,
                    source="asset",
                    sourceId=asset_id,
                    recordDate=created_at
                )
            )
            
        return entries

lab_result_extractor = LabResultExtractor()
