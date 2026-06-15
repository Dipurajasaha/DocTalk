from dataclasses import dataclass, field
from typing import Any

@dataclass
class ComposedResponse:
    memory_context: list[Any] | None = None
    consultation_context: list[Any] | None = None
    patient_history_context: list[Any] | None = None
    doctor_availability_context: list[Any] | None = None
    appointment_context: dict[str, Any] | None = None
    asset_selection_context: dict[str, Any] = field(default_factory=dict)
    rag_scope: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        response_sections = []
        text_parts = []
        
        # Asset Selection Context
        asset_ids = self.asset_selection_context.get("asset_ids", []) if self.asset_selection_context else []
        rag_evidence = [e for e in self.evidence if e.get("type") == "rag"]
        
        if asset_ids:
            reason = self.asset_selection_context.get("selection_reason", "relevant") if self.asset_selection_context else "relevant"
            rtype = self.asset_selection_context.get("report_type", "document").replace("_", " ") if self.asset_selection_context else "document"
            
            if rag_evidence:
                msg = f"Your {reason} {rtype} was located.\\nRetrieved Findings:"
                for e in rag_evidence:
                    msg += f"\\n* {e.get('content')}"
            else:
                msg = f"Your {reason} {rtype} was located.\\nSelected documents:"
                for aid in asset_ids:
                    msg += f"\\n* {rtype.title()} ({aid})"
                    
            response_sections.append({"type": "asset_selection", "content": msg})
            text_parts.append(msg)
            
        # Appointment Context
        if self.appointment_context:
            action = self.appointment_context.get("action", "processing") if self.appointment_context else "processing"
            if self.appointment_context.get("message"):
                msg = self.appointment_context.get("message")
                if action == "confirmed":
                    print("[DEBUG][BOOKING_CONFIRMATION_RENDERED] True")
            else:
                msg = f"Appointment status: {action}."
            response_sections.append({"type": "appointment", "content": msg})
            text_parts.append(msg)
            
        # Doctor Availability Context
        if self.doctor_availability_context:
            msg = f"Found {len(self.doctor_availability_context)} available doctors."
            response_sections.append({"type": "doctor_availability", "content": msg})
            text_parts.append(msg)
            
        # Memory Context
        if self.memory_context is not None:
            msg = f"Retrieved {len(self.memory_context)} previous conversation messages."
            response_sections.append({"type": "memory", "content": msg})
            text_parts.append(msg)
            
        # Consultation Context
        if self.consultation_context is not None:
            msg = f"Retrieved {len(self.consultation_context)} past consultations."
            response_sections.append({"type": "consultation", "content": msg})
            text_parts.append(msg)
            
        # Medical History Context
        if self.patient_history_context is not None:
            msg = f"Medical history shows {len(self.patient_history_context)} active conditions or records."
            response_sections.append({"type": "patient_history", "content": msg})
            text_parts.append(msg)
        if not text_parts:
            text_parts.append("I am processing your request using general knowledge.")
            response_sections.append({"type": "general", "content": text_parts[-1]})
            
        shadow_response = "\\n\\n".join(text_parts)

        return {
            "memory_context": self.memory_context,
            "consultation_context": self.consultation_context,
            "patient_history_context": self.patient_history_context,
            "doctor_availability_context": self.doctor_availability_context,
            "appointment_context": self.appointment_context,
            "asset_selection_context": self.asset_selection_context,
            "rag_scope": self.rag_scope,
            "evidence": self.evidence,
            "response_sections": response_sections,
            "shadow_response": shadow_response,
            "shadow_execution_completed": True
        }
