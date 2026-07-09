from dataclasses import dataclass, field
from typing import Any

@dataclass
class ComposedResponse:
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        response_sections = []
        text_parts = []
        
        for ev in self.evidence:
            if ev.get("content"):
                response_sections.append({"type": ev.get("type"), "content": ev.get("content")})
                text_parts.append(ev.get("content"))
                if ev.get("metadata", {}).get("action") == "confirmed":
                    print("[DEBUG][BOOKING_CONFIRMATION_RENDERED] True")
            
        if not text_parts:
            text_parts.append("I am processing your request using general knowledge.")
            response_sections.append({"type": "general", "content": text_parts[-1]})
            
        shadow_response = "\n\n".join(text_parts)

        return {
            "response_sections": response_sections,
            "shadow_response": shadow_response,
            "shadow_execution_completed": True
        }
