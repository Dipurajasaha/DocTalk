from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..ai.core_services.llm_client import complete_json
from ..schemas.patient_history import CreatePatientHistoryRecord

logger = logging.getLogger(__name__)


class PatientHistoryRecordExtractor:
    async def extract_record(
        self,
        *,
        asset_id: str,
        patient_id: str,
        file_name: str,
        document_type: str,
        report_type: str,
        extracted_text: str,
        created_at: datetime,
    ) -> CreatePatientHistoryRecord | None:
        """Extract a structured patient history record (vitals + conditions /
        medications / allergies) from a processed document.

        Returns a ``CreatePatientHistoryRecord`` containing only the fields that
        were confidently found in the document, or ``None`` when nothing usable
        was extracted.
        """

        if not extracted_text or not extracted_text.strip():
            return None

        text = extracted_text[:4000]

        prompt = (
            "You are a clinical data extraction assistant.\n"
            "Extract structured patient history information from the medical document below.\n"
            "Only extract values that are EXPLICITLY stated in the text. Do not guess or infer.\n"
            "Return ONLY a JSON object with the following keys (omit or use empty arrays/strings when not present):\n"
            "{\n"
            '  "bloodGroup": "e.g. O+, A-, AB+ (or empty string)",\n'
            '  "weight": "e.g. 72 kg (or empty string)",\n'
            '  "bmi": "e.g. 24.1 (or empty string)",\n'
            '  "bloodPressure": "e.g. 120/80 mmHg (or empty string)",\n'
            '  "heartRate": "e.g. 78 bpm (or empty string)",\n'
            '  "spo2": "e.g. 98% (or empty string)",\n'
            '  "temperature": "e.g. 98.6 F (or empty string)",\n'
            '  "bloodSugarFasting": "e.g. 110 mg/dL (or empty string)",\n'
            '  "bloodSugarPP": "e.g. 140 mg/dL (or empty string)",\n'
            '  "conditions": [{"condition": "name", "status": "active|chronic|resolved", "severity": "mild|moderate|severe"}],\n'
            '  "medications": [{"name": "drug", "dosage": "e.g. 500 mg", "frequency": "e.g. twice daily", "is_ongoing": true}],\n'
            '  "allergies": [{"allergen": "substance", "reaction": "description", "severity": "mild|moderate|severe"}]\n'
            "}\n\n"
            "Notes:\n"
            "- Vitals must include their unit when present.\n"
            "- Only include conditions/medications/allergies clearly mentioned in the document.\n"
            "- If no structured data is found, return {}.\n"
        )

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Filename: {file_name}\n"
                    f"Document type: {document_type}\n"
                    f"Report type: {report_type}\n\n"
                    f"Document text:\n{text}"
                ),
            },
        ]

        try:
            response = await complete_json(
                messages,
                temperature=0.1,
                max_output_tokens=2048,
            )
        except Exception as exc:
            logger.exception(
                "PatientHistoryRecordExtractor LLM call failed",
                extra={"asset_id": asset_id, "error": str(exc)},
            )
            return None

        if not isinstance(response, dict):
            return None

        parsed = {
            "bloodGroup": _as_str(response.get("bloodGroup")),
            "weight": _as_str(response.get("weight")),
            "bmi": _as_str(response.get("bmi")),
            "bloodPressure": _as_str(response.get("bloodPressure")),
            "heartRate": _as_str(response.get("heartRate")),
            "spo2": _as_str(response.get("spo2")),
            "temperature": _as_str(response.get("temperature")),
            "bloodSugarFasting": _as_str(response.get("bloodSugarFasting")),
            "bloodSugarPP": _as_str(response.get("bloodSugarPP")),
            "conditions": _as_list_of_dicts(response.get("conditions")),
            "medications": _as_list_of_dicts(response.get("medications")),
            "allergies": _as_list_of_dicts(response.get("allergies")),
        }

        has_vitals = any(
            parsed[k]
            for k in (
                "bloodGroup",
                "weight",
                "bmi",
                "bloodPressure",
                "heartRate",
                "spo2",
                "temperature",
                "bloodSugarFasting",
                "bloodSugarPP",
            )
        )
        has_lists = bool(parsed["conditions"] or parsed["medications"] or parsed["allergies"])

        if not has_vitals and not has_lists:
            return None

        try:
            return CreatePatientHistoryRecord(**parsed)
        except Exception as exc:
            logger.exception(
                "PatientHistoryRecordExtractor validation failed",
                extra={"asset_id": asset_id, "error": str(exc)},
            )
            return None


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(item)
        elif item is not None:
            result.append({"value": str(item)})
    return result


patient_history_record_extractor = PatientHistoryRecordExtractor()
