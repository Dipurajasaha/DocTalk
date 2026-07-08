from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from dateutil import parser as date_parser

from ..ai.core_services.llm_client import complete_json

_DATE_PATTERNS = [
    re.compile(
        r"\b(?:0?[1-9]|[12]\d|3[01])[/.-](?:0?[1-9]|1[0-2])[/.-](?:\d{4}|\d{2})\b"
    ),
    re.compile(
        r"\b(?:0?[1-9]|[12]\d|3[01])[-/\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[-/\s]\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{4}[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b"),
]

_MEDICAL_KEYWORD_HINTS = [
    "prescription",
    "report",
    "xray",
    "mri",
    "ct",
    "ultrasound",
    "lab",
    "blood",
    "cbc",
    "hba1c",
    "glucose",
    "creatinine",
    "cholesterol",
    "lipid",
    "urine",
    "tablet",
    "capsule",
    "syrup",
    "injection",
    "dosage",
    "frequency",
    "hospital",
    "clinic",
    "diagnosis",
    "medicine",
    "follow-up",
    "followup",
    "radiology",
]


def _extract_document_date(text: str) -> datetime | None:
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            return date_parser.parse(match.group(0), dayfirst=True, fuzzy=True)
        except Exception:
            continue
    return None


def _extract_fallback_keywords(
    text: str, document_type: str, report_type: str
) -> list[str]:
    text_lower = text.lower()
    keywords: list[str] = []

    for term in _MEDICAL_KEYWORD_HINTS:
        if term in text_lower and term not in keywords:
            keywords.append(term)
        if len(keywords) >= 5:
            return keywords

    for candidate in [document_type, report_type]:
        normalized = str(candidate or "").strip().lower()
        if normalized and normalized not in keywords and normalized != "general":
            keywords.append(normalized)
        if len(keywords) >= 5:
            return keywords

    words = re.findall(r"\b[a-z]{4,}\b", text_lower)
    stop_words = {
        "patient",
        "doctor",
        "hospital",
        "report",
        "prescription",
        "medical",
        "sample",
        "signed",
        "dated",
        "follow",
        "followup",
        "name",
        "date",
        "results",
        "normal",
        "advice",
        "tablets",
        "tablet",
        "capsules",
        "capsule",
        "syrup",
        "injection",
    }
    for word in words:
        if word in stop_words or word in keywords:
            continue
        keywords.append(word)
        if len(keywords) >= 5:
            break

    return keywords


class DocumentAnalyzer:
    @staticmethod
    async def analyze_document(
        asset_id: str,
        patient_id: str,
        file_name: str,
        category: str,
        extracted_text: str,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:

        system_prompt = (
            "You are an expert medical document metadata extractor.\n"
            "Analyze the following document filename and extracted OCR text.\n"
            "Extract structured metadata and return ONLY a JSON object with these exact keys:\n"
            "{\n"
            '  "asset_category": "...",\n'
            '  "document_type": "...",\n'
            '  "report_type": "...",\n'
            '  "document_date": "YYYY-MM-DD (MUST extract the date the document was issued/created from the text. If absolutely none, return null)",\n'
            '  "doctor_name": "...",\n'
            '  "hospital_name": "...",\n'
            '  "title": "...",\n'
            '  "summary": "...",\n'
            '  "keywords": ["Max 5 concise medical terms (e.g. diabetes, hba1c, xray)"],\n'
            '  "confidence": 0.00,\n'
            '  "reason": "One short sentence explaining the classification."\n'
            "}\n\n"
            "==========================\n"
            "1. STRICT CATEGORY RULES\n"
            "==========================\n"
            "asset_category MUST be one of: [REPORT, PRESCRIPTION, XRAY]\n"
            "document_type MUST be one of: [lab_report, prescription, imaging, medical_record]\n"
            "report_type MUST be one of: [blood_test, lipid_profile, liver_function, kidney_function, thyroid, hba1c, urine_test, mri, ct_scan, xray, prescription, general]\n\n"
            "==========================\n"
            "2. PRIORITY RULES\n"
            "==========================\n"
            "Rule 1 (Highest Priority): If the document contains ANY of these strong prescription indicators:\n"
            "Rx, Prescription, Medicine list, Drug names, Dosage, Frequency, Duration, Tablet, Capsule, Syrup, Injection, Follow-up, Advice, Doctor Signature, Registration Number, 'Take once daily', 'Twice daily', 'Before food', 'After food'\n"
            "-> YOU MUST classify as asset_category = PRESCRIPTION.\n"
            "EVEN IF the document also contains laboratory values (HbA1c, FBS, PPBS, Blood Sugar, CBC, Creatinine, Cholesterol, Lipid Profile, Blood Pressure). Laboratory values DO NOT override a prescription.\n\n"
            "Rule 2: Only classify as REPORT if there is NO medicine list, NO prescription section, AND the document is primarily a diagnostic or laboratory report.\n"
            "Rule 3: Only classify as XRAY if the document is clearly an imaging report or X-ray.\n"
            "Rule 4: 'keywords' MUST be an array of maximum 5 concise medical terms or short phrases. Do NOT include full sentences or vague words."
        )

        user_content = f"Filename: {file_name}\n\nDocument Text (truncated):\n{extracted_text[:2000]}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Default fallbacks
        asset_category_val = (
            category if category in ["REPORT", "PRESCRIPTION", "XRAY"] else "REPORT"
        )
        document_type = "medical_record"
        report_type = "general"
        document_date_val = created_at or datetime.now()
        title = file_name
        summary = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")
        if not summary.strip():
            summary = f"Automatically generated summary for {file_name}"
        keywords = []
        document_date_from_llm = False
        llm_result = None

        try:
            llm_result = await complete_json(
                messages,
                temperature=0.1,
                max_output_tokens=1024,
            )

            if llm_result:
                # Validation
                ac = llm_result.get("asset_category")
                if ac in ["REPORT", "PRESCRIPTION", "XRAY"]:
                    asset_category_val = ac
                else:
                    print(f"[WARNING] Invalid asset_category returned by LLM: {ac}")

                dt = llm_result.get("document_type")
                if dt in ["lab_report", "prescription", "imaging", "medical_record"]:
                    document_type = dt
                else:
                    print(f"[WARNING] Invalid document_type returned by LLM: {dt}")

                rt = llm_result.get("report_type")
                if rt in [
                    "blood_test",
                    "lipid_profile",
                    "liver_function",
                    "kidney_function",
                    "thyroid",
                    "hba1c",
                    "urine_test",
                    "mri",
                    "ct_scan",
                    "xray",
                    "prescription",
                    "general",
                ]:
                    report_type = rt
                else:
                    print(f"[WARNING] Invalid report_type returned by LLM: {rt}")

                title = llm_result.get("title") or title
                summary = llm_result.get("summary") or summary

                kw = llm_result.get("keywords")
                if isinstance(kw, list):
                    keywords = [str(k) for k in kw][:5]

                date_str = llm_result.get("document_date")
                if (
                    date_str
                    and isinstance(date_str, str)
                    and date_str.lower() != "null"
                ):
                    try:
                        parsed_date = date_parser.parse(date_str, fuzzy=True)
                        document_date_val = parsed_date
                        document_date_from_llm = True
                    except Exception:
                        pass
        except Exception as exc:
            print(f"[DEBUG][DOCUMENT_ANALYZER] LLM extraction failed: {exc}")

        fallback_document_date = _extract_document_date(extracted_text)
        if not document_date_from_llm and fallback_document_date is not None:
            document_date_val = fallback_document_date

        # ── Deterministic fallback when LLM returns nothing ──
        # If the LLM did not produce a valid classification, use keyword matching on the OCR text.
        if not llm_result and asset_category_val == "REPORT" and category not in [
            "REPORT",
            "PRESCRIPTION",
            "XRAY",
        ]:
            text_lower = extracted_text.lower()
            name_lower = file_name.lower()

            # Prescription indicators (same list as the LLM prompt)
            rx_keywords = [
                "rx",
                "prescription",
                "tablet",
                "capsule",
                "syrup",
                "injection",
                "dosage",
                "frequency",
                "duration",
                "take once daily",
                "twice daily",
                "before food",
                "after food",
                "once daily",
                "after breakfast",
                "after lunch",
                "after dinner",
                "before meals",
            ]
            if (
                any(kw in text_lower for kw in rx_keywords)
                or "prescription" in name_lower
            ):
                asset_category_val = "PRESCRIPTION"
                document_type = "prescription"
                report_type = "prescription"
                print("[DEBUG][DOCUMENT_ANALYZER] Fallback classifier -> PRESCRIPTION")
            else:
                # Check for lab report indicators
                lab_keywords = [
                    "blood test",
                    "cbc",
                    "hba1c",
                    "fbs",
                    "ppbs",
                    "cholesterol",
                    "lipid profile",
                    "creatinine",
                    "urine test",
                    "thyroid",
                    "hemoglobin",
                    "lab report",
                    "pathology",
                    "diagnostic",
                ]
                if any(kw in text_lower for kw in lab_keywords):
                    document_type = "lab_report"
                    report_type = "blood_test"
                    print(
                        "[DEBUG][DOCUMENT_ANALYZER] Fallback classifier -> REPORT (lab_report)"
                    )
                else:
                    print(
                        "[DEBUG][DOCUMENT_ANALYZER] Fallback classifier -> REPORT (general)"
                    )

        if not keywords:
            keywords = _extract_fallback_keywords(
                extracted_text, document_type, report_type
            )

        # 1. Determine Source Type from validated asset_category_val
        source_type = "report"
        if asset_category_val == "PRESCRIPTION":
            source_type = "prescription"
        elif asset_category_val == "XRAY":
            source_type = "xray"

        # Note: doctor_name and hospital_name are extracted by the LLM
        # but purposefully omitted from this dictionary to maintain schema compatibility.

        return {
            "assetId": asset_id,
            "patientId": patient_id,
            "fileName": file_name,
            "_fileCategory": asset_category_val,
            "_sourceType": source_type,
            "documentType": document_type,
            "reportType": report_type,
            "documentDate": document_date_val,
            "title": title,
            "summary": summary,
            "keywords": keywords,
        }


document_analyzer = DocumentAnalyzer()
