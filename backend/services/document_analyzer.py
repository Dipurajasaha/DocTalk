from __future__ import annotations

from datetime import datetime
from typing import Any

from ..ai.core_services.llm_client import complete_json


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
        
        system_prompt = (
            "You are an expert medical document metadata extractor.\n"
            "Analyze the following document filename and extracted OCR text.\n"
            "Extract structured metadata and return ONLY a JSON object with these exact keys:\n"
            "{\n"
            "  \"asset_category\": \"...\",\n"
            "  \"document_type\": \"...\",\n"
            "  \"report_type\": \"...\",\n"
            "  \"document_date\": \"...\",\n"
            "  \"doctor_name\": \"...\",\n"
            "  \"hospital_name\": \"...\",\n"
            "  \"title\": \"...\",\n"
            "  \"summary\": \"...\",\n"
            "  \"keywords\": [\"...\"],\n"
            "  \"confidence\": 0.00,\n"
            "  \"reason\": \"One short sentence explaining the classification.\"\n"
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
        )

        user_content = f"Filename: {file_name}\n\nDocument Text (truncated):\n{extracted_text[:2000]}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Default fallbacks
        asset_category_val = category if category in ["REPORT", "PRESCRIPTION", "XRAY"] else "REPORT"
        document_type = "medical_record"
        report_type = "general"
        document_date_val = created_at or datetime.now()
        title = file_name
        summary = extracted_text[:200] + ("..." if len(extracted_text) > 200 else "")
        if not summary.strip():
            summary = f"Automatically generated summary for {file_name}"
        keywords = []

        try:
            llm_result = await complete_json(messages, temperature=0.1, max_output_tokens=512)
            
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
                if rt in ["blood_test", "lipid_profile", "liver_function", "kidney_function", "thyroid", "hba1c", "urine_test", "mri", "ct_scan", "xray", "prescription", "general"]:
                    report_type = rt
                else:
                    print(f"[WARNING] Invalid report_type returned by LLM: {rt}")

                title = llm_result.get("title") or title
                summary = llm_result.get("summary") or summary
                
                kw = llm_result.get("keywords")
                if isinstance(kw, list):
                    keywords = [str(k) for k in kw]
                
                date_str = llm_result.get("document_date")
                if date_str and isinstance(date_str, str):
                    try:
                        parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                        document_date_val = parsed_date
                    except ValueError:
                        pass
        except Exception as exc:
            print(f"[DEBUG][DOCUMENT_ANALYZER] LLM extraction failed: {exc}")

        # ── Deterministic fallback when LLM returns nothing ──
        # If the LLM did not produce a valid classification (asset_category_val
        # is still the input default), use keyword matching on the OCR text.
        if asset_category_val == "REPORT" and category not in ["REPORT", "PRESCRIPTION", "XRAY"]:
            text_lower = extracted_text.lower()
            name_lower = file_name.lower()

            # Prescription indicators (same list as the LLM prompt)
            rx_keywords = [
                "rx", "prescription", "tablet", "capsule", "syrup",
                "injection", "dosage", "frequency", "duration",
                "take once daily", "twice daily", "before food",
                "after food", "once daily", "after breakfast",
                "after lunch", "after dinner", "before meals",
                "mg ", " mg\n", "mcg", "ml ",
            ]
            if any(kw in text_lower for kw in rx_keywords) or "prescription" in name_lower:
                asset_category_val = "PRESCRIPTION"
                document_type = "prescription"
                report_type = "prescription"
                print("[DEBUG][DOCUMENT_ANALYZER] Fallback classifier -> PRESCRIPTION")
            else:
                # Check for lab report indicators
                lab_keywords = [
                    "blood test", "cbc", "hba1c", "fbs", "ppbs",
                    "cholesterol", "lipid profile", "creatinine",
                    "urine test", "thyroid", "hemoglobin",
                    "lab report", "pathology", "diagnostic",
                ]
                if any(kw in text_lower for kw in lab_keywords):
                    document_type = "lab_report"
                    report_type = "blood_test"
                    print("[DEBUG][DOCUMENT_ANALYZER] Fallback classifier -> REPORT (lab_report)")
                else:
                    print("[DEBUG][DOCUMENT_ANALYZER] Fallback classifier -> REPORT (general)")

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
