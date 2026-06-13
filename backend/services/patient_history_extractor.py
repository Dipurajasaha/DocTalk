import re
from datetime import datetime
from ..schemas.patient_history import CreatePatientHistory

class PatientHistoryExtractor:
    def __init__(self):
        self.rules = {
            "diagnosis": ["diagnosis", "diagnosed with", "impression"],
            "condition": ["diabetes", "hypertension", "asthma", "thyroid"],
            "allergy": ["allergy", "allergic to"],
            "medication": ["tablet", "capsule", "mg", "medicine"],
            "surgery": ["surgery", "operation", "procedure"]
        }
        self.negation_prefixes = [
            "no", "denies", "without", "negative for", "not", "absence of"
        ]

    def _is_negated(self, text: str, keyword: str) -> bool:
        kw_escaped = re.escape(keyword)
        for neg in self.negation_prefixes:
            neg_escaped = re.escape(neg)
            pattern = rf"\b{neg_escaped}\b(?:\W+\w+){{0,5}}\W+{kw_escaped}\b"
            if re.search(pattern, text):
                return True
        return False

    def extract_history_entries(
        self,
        asset_id: str,
        patient_id: str,
        file_name: str,
        document_type: str,
        report_type: str,
        extracted_text: str,
        created_at: datetime
    ) -> list[CreatePatientHistory]:
        entries = []
        text_lower = (extracted_text or "").lower()
        
        seen = set()
        for h_type, keywords in self.rules.items():
            for kw in keywords:
                # Use word boundaries to avoid partial substring matches
                if re.search(rf"\b{re.escape(kw)}\b", text_lower):
                    if self._is_negated(text_lower, kw):
                        continue
                    
                    title = kw.capitalize()
                    key = f"{h_type}:{title}"
                    if key not in seen:
                        seen.add(key)
                        entries.append(
                            CreatePatientHistory(
                                patientId=patient_id,
                                historyType=h_type,
                                title=title,
                                value="Detected in uploaded report",
                                source="asset",
                                sourceId=asset_id,
                                recordDate=created_at
                            )
                        )
        return entries

patient_history_extractor = PatientHistoryExtractor()
