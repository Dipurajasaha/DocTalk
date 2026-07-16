from typing import Any
import re

from pydantic import BaseModel, Field, model_validator
from ...core.database import get_prisma
from ..graph.state import UnifiedChatState
from ..graph.common import latest_message_text, get_workflow_model
from ..utils.logger import log_section, log_key_value

class RecommendationPrediction(BaseModel):
    needs_doctor: bool = Field(default=False, description="True if the patient is describing a symptom, condition, or need that requires a doctor's consultation.")
    recommended_specialty: str | None = Field(default=None, description="The specific type of doctor needed (e.g., 'Cardiologist', 'General Physician', 'Pulmonologist', 'Dermatologist'). Null if no doctor is needed.")
    reasoning: str = Field(default="", description="Brief explanation of why this specialty is recommended.")

    @model_validator(mode='before')
    @classmethod
    def parse_flexible_fields(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        
        data = dict(values)
        if "needs_doctor" not in data:
            data["needs_doctor"] = False
        if "recommended_specialty" not in data:
            data["recommended_specialty"] = None
        if "reasoning" not in data:
            data["reasoning"] = ""
            
        return data

async def recommendation_engine_node(state: UnifiedChatState) -> dict[str, Any]:
    # 0. Skip recommendation engine entirely for doctors
    if state.get("mode") in ["DOCTOR_GENERAL", "DOCTOR_PATIENT"]:
        return {}

    # 1. Skip if there's an active workflow
    planner_metadata = state.get("planner_metadata") or {}
    if "active_workflow" in planner_metadata:
        return {} # Don't interrupt active workflows like booking
        
    query_type = planner_metadata.get("query_type", "general")
    if query_type not in ["rag", "knowledge", "general"]:
        return {}

    messages = state.get("messages") or []
    latest_msg = latest_message_text(messages)
    if not latest_msg:
        return {}
        
    # 2. Use LLM to predict if a doctor is needed based on recent context
    model = get_workflow_model(temperature=0.0)
    evaluator = model.with_structured_output(RecommendationPrediction)
    
    chat_history = []
    for m in messages[-4:]:
        role = "USER" if getattr(m, "type", "") == "human" else "ASSISTANT"
        content = str(getattr(m, "content", "")).replace('\n', ' ')
        chat_history.append(f"{role}: {content}")
        
    prompt = f"""
You are a medical triage assistant. Analyze the recent conversation to determine if the patient needs to consult a doctor.
If they are reporting a symptom (e.g., cough, headache, chest pain), asking for a doctor, or seeking medical advice, set needs_doctor=true and provide the most appropriate medical specialty (e.g., 'General Physician', 'Pulmonologist', 'Cardiologist').
If they are just greeting, asking general platform questions, or following up on a non-medical topic, set needs_doctor=false.

You MUST respond with a strictly formatted JSON object matching the following schema:
{{
  "needs_doctor": boolean,
  "recommended_specialty": "string" or null,
  "reasoning": "string"
}}

Recent conversation:
{chr(10).join(chat_history)}
"""
    
    try:
        prediction = await evaluator.ainvoke([{"role": "user", "content": prompt}])
    except Exception as e:
        log_section("RECOMMENDATION ENGINE")
        log_key_value("Error", str(e))
        return {}

    needs_doctor = getattr(prediction, "needs_doctor", False)
    specialty = getattr(prediction, "recommended_specialty", None)
    
    if not needs_doctor or not specialty:
        return {}
        
    # 3. Query Prisma database to find available doctors of this specialty
    prisma = await get_prisma()
    
    # We do a basic search for the specialty in the DB (case-insensitive substring)
    doctors = await prisma.doctor.find_many(
        where={
            "specialization": {
                "contains": specialty,
                "mode": "insensitive"
            }
        },
        take=2
    )
    
    # If exact specialty not found, fallback to 'General Physician'
    if not doctors and specialty.lower() != "general physician":
        doctors = await prisma.doctor.find_many(
            where={
                "specialization": {
                    "contains": "General Physician",
                    "mode": "insensitive"
                }
            },
            take=2
        )
        if doctors:
            specialty = "General Physician"

    recommendation_context = {
        "recommended_specialty": specialty,
        "recommendation_confidence": 0.9,
        "recommendation_source": "RecommendationEngineLLM",
        "reasoning": getattr(prediction, "reasoning", "")
    }
    
    article = "an" if specialty.lower()[0] in ['a', 'e', 'i', 'o', 'u'] else "a"
    rec_text = f"Based on your symptoms, consulting {article} {specialty} would be recommended.\n"
    
    if doctors:
        doc_names_list = []
        for d in doctors:
            name_prefix = "" if d.name.startswith("Dr.") else "Dr. "
            doc_names_list.append(f"{name_prefix}{d.name} ({d.specialization})")
        doc_names = ", ".join(doc_names_list)
        recommendation_context["suggested_doctors"] = [{"id": d.doctorId, "name": d.name, "specialization": d.specialization} for d in doctors]
        rec_text += f"\nWe have the following doctors available on our platform who can help you:\n{doc_names}\n\nWould you like me to help you book an appointment with them?"
    else:
        rec_text += "\nIf you'd like, I can help you find an appropriate specialist available on this platform."
        
    log_section("RECOMMENDATION ENGINE")
    log_key_value("Source", "RecommendationEngineLLM")
    log_key_value("Recommended Specialty", specialty)
    log_key_value("Doctors Found", str(len(doctors)))
    
    evidence = state.get("evidence") or []
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
