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
    
class TFIDFValidator:
    """
    A deterministic, math-based domain validator using TF-IDF and Cosine Similarity.
    Replaces brittle regex and keyword lists.
    """
    def __init__(self):
        from ..executor.capability_registry import REGISTRY
        
        self.documents = {
            "CORE_CONVERSATION": "hello hi greetings good morning afternoon evening thank thanks bye goodbye",
            "CORE_MEDICAL_KNOWLEDGE": (
                "medical knowledge health queries query disease diseases symptom symptoms "
                "medicine medicines treatment treatments prescription prescriptions "
                "diabetes anemia fever cough cold headache nausea dizziness pain fatigue "
                "blood report reports scan scans mri xray x-ray lab result results "
                "allergy allergies medication medications doctor physician hospital clinic "
                "surgery lab test tests cbc hemoglobin platelet pcv hematocrit rbc wbc"
            )
        }
        
        # Dynamically inject capabilities from the platform's registry
        for cap_name, cap_def in REGISTRY.items():
            self.documents[cap_name] = cap_def["metadata"].description + " " + cap_name.replace("_", " ").lower()
            
        self.doc_ids = list(self.documents.keys())
        self.corpus = [self._tokenize(doc) for doc in self.documents.values()]
        
        # Build TF-IDF model
        import math
        from collections import Counter
        
        self.df = Counter()
        for doc in self.corpus:
            self.df.update(set(doc))
            
        self.idf = {}
        N = len(self.corpus)
        for term, count in self.df.items():
            self.idf[term] = math.log((N + 1) / (count + 1)) + 1
            
        self.doc_vectors = [self._vectorize(doc) for doc in self.corpus]

    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r'\b[a-z0-9]+\b', text.lower())
        stopwords = {"explain", "analyze", "show", "tell", "me", "about", "what", "is", "how", "does", "the", "for", "to", "or", "and", "my", "this", "a", "an", "of", "in", "write", "create", "generate", "solve"}
        return [w for w in words if w not in stopwords]

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        import math
        from collections import Counter
        tf = Counter(tokens)
        vec = {}
        norm = 0.0
        for term, count in tf.items():
            val = count * self.idf.get(term, math.log((len(self.corpus) + 1) / 1) + 1)
            vec[term] = val
            norm += val * val
        
        norm = math.sqrt(norm)
        if norm > 0:
            for term in vec:
                vec[term] /= norm
        return vec

    def classify(self, text: str) -> str:
        q_tokens = self._tokenize(text)
        if not q_tokens:
            return "UNSUPPORTED"

        medical_hint_terms = {
            "anemia", "fever", "cough", "cold", "headache", "nausea", "dizziness", "pain",
            "fatigue", "allergy", "allergies", "medication", "medications", "prescription",
            "prescriptions", "blood", "report", "reports", "cbc", "hemoglobin", "platelet",
            "pcv", "hematocrit", "rbc", "wbc", "xray", "x-ray", "scan", "scans", "symptom",
            "symptoms", "treatment", "treatments", "doctor", "clinic", "hospital", "medicine",
            "medicines", "diabetes",
        }

        if any(term in q_tokens for term in medical_hint_terms):
            return "MEDICAL"
            
        q_vec = self._vectorize(q_tokens)
        
        best_doc = None
        best_score = -1.0
        
        for doc_id, doc_vec in zip(self.doc_ids, self.doc_vectors):
            score = sum(q_vec.get(term, 0.0) * doc_vec.get(term, 0.0) for term in q_vec)
            if score > best_score:
                best_score = score
                best_doc = doc_id
                
        # Threshold to ensure we don't accidentally match irrelevant text
        if best_score < 0.05:
            return "UNSUPPORTED"
            
        if best_doc == "CORE_CONVERSATION":
            return "CONVERSATION"
            
        # Any other match (registered capabilities or CORE_MEDICAL)
        return "MEDICAL"

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
        session_risk_delta = len(triggered_rules) * 2 # Increase risk significantly on input violation
        
    new_risk_score = current_risk_score + session_risk_delta
    
    # Domain Validation
    domain_validator = TFIDFValidator()
    domain = domain_validator.classify(text)
    
    if domain == "UNSUPPORTED" and decision != "BLOCK":
        decision = "BLOCK"
        
    # Structured Logging
    security_status = "FAIL" if triggered_rules else "PASS"
    log_lines = [
        "==========================",
        "INPUT GUARDRAIL",
        "==========================",
        f"Security: {security_status}",
        f"Domain: {domain}",
        f"Decision: {decision}"
    ]
    if decision == "BLOCK":
        log_lines.append("Planner Invoked: NO")
        
    logger.info("\n" + "\n".join(log_lines) + "\n")
    
    if triggered_rules:
        logger.info(f"Risk Level: {risk_level}\nTriggered Rules:\n" + "\n".join(f"- {r}" for r in triggered_rules))
        if session_risk_delta > 0:
            logger.info(f"Risk Score\n{current_risk_score} -> {new_risk_score}")
    
    status = "blocked" if decision == "BLOCK" else "allowed"
    
    updates: dict[str, Any] = {
        "session_risk_score": new_risk_score,
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
