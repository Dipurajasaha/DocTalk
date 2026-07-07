from typing import Any
import re

from ..graph.state import UnifiedChatState
from ..graph.common import latest_message_text
from ..utils.logger import log_section, log_key_value

def _determine_specialty(evidence_text: str) -> str | None:
    text = evidence_text.lower()
    
    # Priority 1: Endocrinologist
    if any(k in text for k in ["hba1c", "fbs", "ppbs", "diabetes", "fasting blood sugar", "post prandial"]):
        return "Endocrinologist"
        
    # Priority 2: Cardiologist
    if any(k in text for k in ["ecg", "chest pain", "troponin", "heart"]):
        return "Cardiologist"
        
    # Priority 3: Nephrologist
    if any(k in text for k in ["creatinine", "egfr", "urea", "kidney"]):
        return "Nephrologist"
        
    # Priority 4: Gastroenterologist
    if any(k in text for k in ["sgpt", "sgot", "alt", "ast", "bilirubin", "liver"]):
        return "Gastroenterologist"
        
    # Priority 5: Pulmonologist
    if any(k in text for k in ["respiratory", "asthma", "copd", "lungs", "breathing"]):
        return "Pulmonologist"
        
    # Priority 6: Dermatologist
    if any(k in text for k in ["skin", "rash", "dermatitis"]):
        return "Dermatologist"
        
    # Priority 7: Ophthalmologist
    if any(k in text for k in ["eye", "vision"]):
        return "Ophthalmologist"
        
    # Priority 8: Neurologist
    if any(k in text for k in ["neurological", "nerve", "seizure", "stroke", "brain"]):
        return "Neurologist"
        
    # Priority 9: Orthopedic Surgeon
    if any(k in text for k in ["orthopedic", "bone", "fracture", "joint"]):
        return "Orthopedic Surgeon"
        
    # Priority 10: Urologist
    if any(k in text for k in ["urinary", "urine", "bladder"]):
        return "Urologist"
        
    # Priority 11: Hematologist
    if ("severe" in text or "leukemia" in text or "lymphoma" in text) and any(k in text for k in ["anemia", "hematology", "blood"]):
        return "Hematologist"
        
    # Priority 12: General Physician
    if any(k in text for k in ["hemoglobin", "cbc", "rbc", "wbc", "platelet", "anemia"]):
        return "General Physician"
        
    return None

async def recommendation_engine_node(state: UnifiedChatState) -> dict[str, Any]:
    # 1. Skip if there's an active workflow or if we already have a recommendation in context
    planner_metadata = state.get("planner_metadata") or {}
    if "active_workflow" in planner_metadata:
        return {} # Don't interrupt active workflows like booking
        
    query_type = planner_metadata.get("query_type", "general")
    if query_type not in ["rag", "knowledge", "general"]:
        return {}

    evidence = state.get("evidence") or []
    
    # 2. Only execute when current execution contains fresh medical evidence
    has_medical_evidence = False
    for e in evidence:
        if isinstance(e, dict):
            # "rag" evidence comes from asset (report/prescription) analysis
            # Uploaded documents and medical interpretation populate this.
            if e.get("type") in ["rag", "symptom_analysis", "medical_analysis"]:
                has_medical_evidence = True
                break
                
    if not has_medical_evidence:
        return {}

    messages = state.get("messages") or []
    latest_msg = latest_message_text(messages)
    if not latest_msg:
        return {}
        
    evidence = state.get("evidence") or []
    evidence_text = "\n\n".join([str(e.get("content")) for e in evidence if isinstance(e, dict)])
    
    # 2. Determine specialty deterministically
    specialty = _determine_specialty(evidence_text)
    if not specialty:
        return {}
        
    # 3. Search for previous Platform Doctors (avoiding patient_history Document Doctors)
    prev_doctor_id = None
    prev_doctor_name = None
    
    consultations = state.get("consultation_context") or []
    for cons in consultations:
        doc = cons.get("doctor")
        if doc and isinstance(doc, dict):
            if doc.get("specialization") and specialty.lower() in doc.get("specialization").lower():
                prev_doctor_id = doc.get("id")
                prev_doctor_name = doc.get("name")
                break
                
    if not prev_doctor_id:
        appointments = state.get("appointment_context", {}).get("upcoming", []) + state.get("appointment_context", {}).get("past", [])
        for appt in appointments:
            doc = appt.get("doctor")
            if doc and isinstance(doc, dict):
                if doc.get("specialization") and specialty.lower() in doc.get("specialization").lower():
                    prev_doctor_id = doc.get("id")
                    prev_doctor_name = doc.get("name")
                    break

    # 4. Construct response and context
    article = "an" if specialty.lower()[0] in ['a', 'e', 'i', 'o', 'u'] else "a"

    recommendation_context = {
        "recommended_specialty": specialty,
        "recommendation_confidence": 1.0,
        "recommendation_source": "RecommendationEngineRuleBased"
    }
    
    if prev_doctor_id and prev_doctor_name:
        recommendation_context["recommended_doctor_id"] = prev_doctor_id
        recommendation_context["recommended_doctor_name"] = prev_doctor_name
        rec_text = (
            f"Based on the available information, you may consider consulting {article} {specialty}.\n\n"
            f"You previously consulted Dr. {prev_doctor_name} on this platform.\n"
            f"Would you like me to check Dr. {prev_doctor_name}'s availability?"
        )
    else:
        rec_text = (
            f"Based on the available information, you may consider consulting {article} {specialty}.\n\n"
            "If you'd like, I can help you find an appropriate specialist available on this platform."
        )
        
    log_section("RECOMMENDATION ENGINE")
    log_key_value("Source", "RecommendationEngineRuleBased")
    log_key_value("Recommended Specialty", specialty)
    log_key_value("Recommended Doctor", prev_doctor_name if prev_doctor_name else "None")
    log_key_value("Previous Match", "Yes" if prev_doctor_id else "No")
    
    new_evidence = list(evidence)
    new_evidence.append({
        "source": "RECOMMENDATION",
        "type": "care_recommendation",
        "content": rec_text,
        "metadata": recommendation_context
    })
    
    return {
        "evidence": new_evidence,
        "recommendation_context": recommendation_context
    }
