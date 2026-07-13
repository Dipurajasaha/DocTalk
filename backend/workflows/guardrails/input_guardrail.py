from __future__ import annotations
import logging
import re
from typing import Any
from ..graph.common import message_content_text
from ..graph.state import UnifiedChatState

logger = logging.getLogger(__name__)

# Deterministic patterns
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"new\s+instructions", re.IGNORECASE),
]

JAILBREAK_PATTERNS = [
    re.compile(r"\bdan\b", re.IGNORECASE), # Do Anything Now
    re.compile(r"developer\s+mode", re.IGNORECASE),
    re.compile(r"you\s+are\s+(now\s+)?(unrestricted|free|an\s+unconstrained)", re.IGNORECASE),
]

ROLE_MANIPULATION_PATTERNS = [
    re.compile(r"you\s+are\s+(now\s+)?(a\s+human|my\s+doctor|my\s+physician)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a\s+human|my\s+doctor|my\s+physician)", re.IGNORECASE),
]

OUT_OF_SCOPE_PATTERNS = [
    re.compile(r"write\s+(a\s+)?(python|javascript|java|c\+\+|code)\s+(script|function|program)", re.IGNORECASE),
    re.compile(r"how\s+to\s+build\s+(a\s+)?bomb", re.IGNORECASE),
]

# Strict patterns (only active on HIGH or STRICT risk levels)
STRICT_PATTERNS = [
    re.compile(r"translate\s+this", re.IGNORECASE),
    re.compile(r"summarize\s+this\s+url", re.IGNORECASE),
    re.compile(r"forget", re.IGNORECASE),
    re.compile(r"bypass", re.IGNORECASE),
]

def _evaluate_risk_level(score: int) -> str:
    if score >= 5:
        return "STRICT"
    if score >= 3:
        return "HIGH"
    if score >= 1:
        return "MEDIUM"
    return "LOW"

def _detect_rules(text: str, risk_level: str) -> list[str]:
    triggered_rules = []
    
    if any(p.search(text) for p in PROMPT_INJECTION_PATTERNS):
        triggered_rules.append("Prompt Injection")
    
    if any(p.search(text) for p in JAILBREAK_PATTERNS):
        triggered_rules.append("Jailbreak")
        
    if any(p.search(text) for p in ROLE_MANIPULATION_PATTERNS):
        triggered_rules.append("Role Manipulation")
        
    if any(p.search(text) for p in OUT_OF_SCOPE_PATTERNS):
        triggered_rules.append("Unsupported Capability")
        
    if risk_level in ["HIGH", "STRICT"]:
        if any(p.search(text) for p in STRICT_PATTERNS):
            triggered_rules.append("Strict Block")
            
    return triggered_rules
    
from .semantic_cache import cache_manager
from backend.ai.core_services.llm_client import complete_text, _extract_json

async def input_guardrail_node(state: UnifiedChatState) -> dict[str, Any]:
    messages = list(state.get("messages") or [])
    if not messages:
        return {}
        
    last_message = messages[-1]
    if last_message.type != "human":
        return {}
        
    text = message_content_text(last_message)
    if not text:
        return {}
        
    current_risk_score = state.get("session_risk_score", 0)
    risk_level = _evaluate_risk_level(current_risk_score)
    
    triggered_rules = _detect_rules(text, risk_level)
    
    session_risk_delta = 0
    decision = "ALLOW"
    
    if triggered_rules:
        decision = "BLOCK"
        session_risk_delta = len(triggered_rules) * 2
        
    domain = "UNKNOWN"
    
    # 2. Semantic Cache Domain Validation
    if decision != "BLOCK":
        words = re.findall(r'\b[a-z0-9]+\b', text.lower())
        stopwords = {"explain", "analyze", "show", "tell", "me", "about", "what", "is", "how", "does", "the", "for", "to", "or", "and", "my", "this", "a", "an", "of", "in", "write", "create", "generate", "solve", "can", "you", "i", "want"}
        tokens = [w for w in words if w not in stopwords]
        
        if not tokens and words:
            # If the user only typed stopwords (e.g. "what is this"), don't blindly block.
            # Revert to the original words so the LLM fallback can evaluate the context!
            tokens = words
            
        if not tokens:
            domain = "UNSUPPORTED"
            decision = "BLOCK"
        else:
            logger.info(f"\n[DEBUG] Guardrail checking tokens against Semantic Cache: {tokens}")
            cache_result = await cache_manager.check_tokens(tokens)
            
            if cache_result == "BLOCKED":
                domain = "UNSUPPORTED"
                decision = "BLOCK"
                logger.info(f"Blocked by Semantic Cache. Tokens: {tokens}")
            elif cache_result == "ALLOWED":
                domain = "MEDICAL"
            else:
                logger.info(f"Semantic Cache MISS. Triggering LLM Fallback for: '{text}'")
                history_text = ""
                if len(messages) > 1:
                    recent_messages = messages[-4:-1]
                    history_lines = []
                    for m in recent_messages:
                        role = "USER" if m.type == "human" else "ASSISTANT"
                        content = str(getattr(m, "content", "")).replace('\n', ' ')
                        if len(content) > 150:
                            content = content[:147] + "..."
                        history_lines.append(f"{role}: {content}")
                    history_text = "\n".join(history_lines)

                from langchain_core.messages import HumanMessage
                prompt = f"""You are a security domain classifier for a healthcare app.

Recent Conversation Context (for reference):
{history_text if history_text else "None"}

Analyze this new user query: "{text}"

1. Is this query related to healthcare/medical topics, or is it a normal friendly greeting or a valid conversational follow-up to the context? (If yes, it is ALLOWED).
2. Is this query completely irrelevant to the context (e.g. coding, cars, cooking, finance) or malicious? (If yes, it is REJECTED).

Extract 1-3 highly specific ROOT NOUNS or core topical words from the query that define its domain. 
CRITICAL: If the query is a vague follow-up (like "explain it", "yes", "elaborate") and has no specific nouns, just return an empty array [] for extracted_keywords. Do NOT extract common verbs.

Return ONLY a JSON object with this exact structure:
{{
  "classification": "ALLOWED", // or "REJECTED"
  "extracted_keywords": ["word1", "word2"] // or [] if none
}}"""
                try:
                    response_text = await complete_text([HumanMessage(content=prompt)], temperature=0.0)
                    response_json = _extract_json(response_text)
                    
                    classification = response_json.get("classification", "REJECTED")
                    keywords = response_json.get("extracted_keywords", [])
                    logger.info(f"[Guardrail] LLM Fallback: {classification} (Keywords: {keywords})")
                    
                    if classification == "ALLOWED":
                        domain = "MEDICAL"
                        for kw in keywords:
                            await cache_manager.add_allowed(kw)
                    else:
                        domain = "UNSUPPORTED"
                        decision = "BLOCK"
                        for kw in keywords:
                            await cache_manager.add_blocked(kw)
                except Exception as e:
                    logger.error(f"[Guardrail] LLM Fallback failed: {e}")
                    domain = "UNSUPPORTED"
                    decision = "BLOCK"
        
    logger.info(f"[Guardrail] Result: {decision} | Domain: {domain} | Risk: {current_risk_score}->{current_risk_score + session_risk_delta} | Rules: {triggered_rules}")
    
    status = "blocked" if decision == "BLOCK" else "allowed"
    
    updates: dict[str, Any] = {
        "session_risk_score": session_risk_delta,
        "input_guardrail_context": {
            "status": status,
            "triggered_rules": triggered_rules,
            "session_risk_delta": session_risk_delta,
            "risk_level": risk_level,
            "domain": domain
        }
    }
    
    if status == "blocked":
        if triggered_rules:
            updates["final_response"] = "Your request was blocked due to safety policies."
        else:
            updates["final_response"] = "I'm sorry, but DocTalk only supports healthcare-related conversations. How can I help you with your health today?"
        
    return updates
