"""AI chat service implementation.

Provides the `AIChatService` with async methods used by routes. Heavy/IO-bound
operations are offloaded with ``asyncio.to_thread`` where needed.
"""
from __future__ import annotations

import os
import json
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Any, Tuple
import asyncio

import google.generativeai as genai
from ...utils.logger import logger
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_core.outputs.chat_generation import ChatGeneration
from langchain_core.outputs.llm_result import LLMResult


# Token estimation (rough approximation: ~4 chars per token for English)
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    if estimate_tokens(text) <= max_tokens:
        return text
    low, high = 0, len(text)
    result = ""
    while low <= high:
        mid = (low + high) // 2
        truncated = text[:mid]
        if estimate_tokens(truncated) <= max_tokens:
            result = truncated
            low = mid + 1
        else:
            high = mid - 1
    return result


def _load_root_env() -> None:
    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.is_file():
        return

    try:
        with env_path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        return


_load_root_env()
_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if _API_KEY:
    genai.configure(api_key=_API_KEY)

TEXT_MODEL_CANDIDATES = [
    os.getenv("GEMINI_TEXT_MODEL", "gemini-3.5-flash"),
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
]


class GeminiChatModel(BaseChatModel):
    model_name: str = "gemini-3.5-flash"

    class Config:
        arbitrary_types_allowed = True

    def _generate(self, messages: List[BaseMessage], stop: List[str] | None = None, **kwargs: Any) -> LLMResult:
        prompt_text = self._format_messages_to_text(messages)

        last_err = None
        for model_name in TEXT_MODEL_CANDIDATES:
            try:
                response = genai.GenerativeModel(model_name).generate_content(prompt_text)
                text_response = response.text if hasattr(response, "text") else str(response)
                generation = ChatGeneration(message=AIMessage(content=text_response))
                return LLMResult(generations=[[generation]])
            except Exception as e:
                last_err = e
                msg_lower = str(e).lower()
                if "404" in msg_lower or "not found" in msg_lower:
                    continue
                raise
        raise RuntimeError(f"No available Gemini model. Last error: {last_err}")

    def _format_messages_to_text(self, messages: List[BaseMessage]) -> str:
        parts = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                parts.append(f"System: {msg.content}")
            elif isinstance(msg, HumanMessage):
                parts.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                parts.append(f"Assistant: {msg.content}")
            else:
                parts.append(str(msg.content))
        return "\n".join(parts)

    @property
    def _llm_type(self) -> str:
        return "gemini-chat"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"model_name": self.model_name, "model_type": "gemini-chat"}


class AIChatService:
    """Full chat implementation.

    This class preserves the public async API used by routes: `chat`,
    `explain_document`, `analyze_xray`.
    """

    RECENT_MESSAGE_WINDOW = 10
    SUMMARIZATION_THRESHOLD = 20
    MAX_CONTEXT_TOKENS = 2000
    SUMMARY_UPDATE_INTERVAL = 5
    MAX_SESSIONS_PER_USER = 10

    def __init__(self, data_root: str | None = None) -> None:
        self.data_root = data_root or "data"
        self.patients_root = os.path.join(self.data_root, "patients")
        self.llm = GeminiChatModel()

    def _chat_sessions_path(self, username: str) -> str:
        return os.path.join(self.patients_root, username, "chat_sessions.json")

    def _load_sessions(self, username: str) -> List[Dict[str, Any]]:
        path = self._chat_sessions_path(username)
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_sessions(self, username: str, sessions: List[Dict[str, Any]]) -> None:
        if len(sessions) > self.MAX_SESSIONS_PER_USER:
            sessions = sessions[-self.MAX_SESSIONS_PER_USER:]
        path = self._chat_sessions_path(username)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            pass

    def _summarize_messages(self, messages: List[Dict[str, str]]) -> str:
        if not messages:
            return ""
        summary_parts = []
        for msg in messages:
            sender = msg.get("sender", "").capitalize()
            text = msg.get("text", "")[:200]
            summary_parts.append(f"{sender}: {text}")
        full_text = "\n".join(summary_parts)
        system_prompt = (
            "Create a 1-2 sentence summary of the conversation history. "
            "Capture key medical topics and user intent, but be very brief. "
            "Do NOT include specific patient details or diagnoses."
        )
        llm_messages = [SystemMessage(content=system_prompt), HumanMessage(content=f"Summarize this conversation:\n{full_text}")]
        try:
            summary = self._call_llm_with_messages(llm_messages)
            return summary.strip()
        except Exception:
            return f"[Previous {len(messages)} messages about medical topics]"

    def _build_efficient_context(self, active_session: Dict[str, Any]) -> Tuple[List[Dict[str, str]], str]:
        all_messages = active_session.get("messages", [])
        summary = active_session.get("summary", "")
        summary_timestamp = active_session.get("summary_timestamp", 0)
        if len(all_messages) <= self.RECENT_MESSAGE_WINDOW:
            context = "\n".join([f"{m.get('sender').capitalize()}: {m.get('text', '')}" for m in all_messages[-self.RECENT_MESSAGE_WINDOW :]])
            return all_messages, context
        recent_messages = all_messages[-self.RECENT_MESSAGE_WINDOW :]
        old_messages = all_messages[: -self.RECENT_MESSAGE_WINDOW]
        current_time = time.time()
        needs_resummary = (not summary or (current_time - summary_timestamp) > 300 or len(all_messages) > self.SUMMARIZATION_THRESHOLD)
        if needs_resummary and old_messages:
            summary = self._summarize_messages(old_messages)
            active_session["summary"] = summary
            active_session["summary_timestamp"] = current_time
        context_parts = []
        if summary:
            context_parts.append(f"[Context Summary]\n{summary}\n")
        context_parts.append("[Recent Messages]")
        for msg in recent_messages:
            sender = msg.get("sender", "").capitalize()
            text = msg.get("text", "")
            context_parts.append(f"{sender}: {text}")
        context = "\n".join(context_parts)
        context = truncate_to_token_limit(context, self.MAX_CONTEXT_TOKENS)
        return recent_messages, context

    def _call_llm_with_messages(self, messages: List[BaseMessage]) -> str:
        if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
            raise RuntimeError(
                "No LLM API key configured. Set the GOOGLE_API_KEY or GEMINI_API_KEY "
                "environment variable, or call genai.configure(api_key=...) before making LLM requests. "
            )
        if isinstance(self.llm, GeminiChatModel) or hasattr(self.llm, "_format_messages_to_text"):
            prompt_text = None
            try:
                if isinstance(self.llm, GeminiChatModel):
                    prompt_text = self.llm._format_messages_to_text(messages)
                else:
                    parts = []
                    for m in messages:
                        try:
                            parts.append(f"{type(m).__name__}: {m.content}")
                        except Exception:
                            parts.append(str(m))
                    prompt_text = "\n".join(parts)
                last_err = None
                for model_name in TEXT_MODEL_CANDIDATES:
                    try:
                        resp = genai.GenerativeModel(model_name).generate_content(prompt_text)
                        result = resp
                        break
                    except Exception as e:
                        last_err = e
                        error_str = str(e).lower()
                        if "quota" in error_str or "resource_exhausted" in error_str or "429" in error_str:
                            retry_after = self._extract_retry_after(str(e))
                            return (
                                f"⏱️ API quota exceeded. The free tier allows 20 requests/day. "
                                f"Please try again in {retry_after} seconds, or upgrade your Gemini API plan at "
                                f"https://ai.google.dev/pricing"
                            )
                        if "404" in error_str or "not found" in error_str:
                            continue
                        raise
                else:
                    raise RuntimeError(f"No available Gemini model. Last error: {last_err}")
            except Exception as e:
                logger.exception("LLM invocation raised an exception (direct genai call)")
                raise RuntimeError(f"LLM call failed: {e}")
        else:
            try:
                result = self.llm.invoke(messages)
            except Exception as e:
                logger.exception("LLM invocation raised an exception")
                raise RuntimeError(f"LLM call failed: {e}")
        try:
            try:
                raw_repr = repr(result)
            except Exception:
                raw_repr = "<unrepresentable>"
            logger.debug("Raw LLM result type=%s repr=%s", type(result), raw_repr)
            if isinstance(result, str):
                return result
            if hasattr(result, "text") and isinstance(result.text, str):
                return result.text
            generations = None
            if hasattr(result, "generations"):
                generations = result.generations
            if generations is None and isinstance(result, list):
                generations = result
            if generations:
                first = None
                if isinstance(generations, list) and generations:
                    first = generations[0]
                    if isinstance(first, list) and first:
                        first = first[0]
                if first is not None:
                    if hasattr(first, "message"):
                        msg = first.message
                        if hasattr(msg, "content"):
                            return msg.content
                        if hasattr(msg, "text"):
                            return msg.text
                        return str(msg)
                    if hasattr(first, "text"):
                        return first.text
                    if hasattr(first, "content"):
                        return first.content
            if isinstance(result, dict):
                for key in ("text", "content", "message"):
                    if key in result and isinstance(result[key], str):
                        return result[key]
            return str(result)
        except Exception as e:
            logger.exception("Failed to parse LLM result: %s", e)
            try:
                logger.debug("Raw LLM result for diagnostics: %s", repr(result))
            except Exception:
                logger.debug("Raw LLM result unrepresentable")
            raise RuntimeError(f"LLM result parsing failed: {e}")

    async def chat(self, username: str, messages: List[Dict[str, str]], language: str = "en") -> Any:
        # Run the synchronous heavy logic in a thread to avoid blocking
        return await asyncio.to_thread(self._chat_impl, username, messages, language)

    def _chat_impl(self, username: str, messages: List[Dict[str, str]], language: str = "en") -> Any:
        sessions = self._load_sessions(username)
        if not sessions:
            sessions = [{
                "id": f"s_{int(time.time()*1000)}",
                "title": "",
                "messages": [],
                "summary": "",
                "summary_timestamp": 0,
                "created": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }]
        active_session = sessions[0]
        user_input = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_input += msg.get("content", "") + " "
        user_input = user_input.strip() or (messages[-1].get("content", "") if messages else "")
        recent_messages, context_str = self._build_efficient_context(active_session)
        llm_messages = [SystemMessage(content=(
            "You are a concise medical knowledge assistant. "
            "Be educational, non-prescriptive, and avoid diagnosis. "
            "Keep responses clear and brief unless asked to expand. "
            "Always respond in the user's language when identifiable. "
            "Vary your phrasing and focus—avoid repeating the same structure across responses. "
            "Use natural, conversational wording."
        ))]
        if context_str:
            llm_messages.append(HumanMessage(content=f"[Context from conversation history]\n{context_str}"))
        llm_messages.append(HumanMessage(content=user_input))
        try:
            raw_response = self._call_llm_with_messages(llm_messages)
        except Exception as e:
            raw_response = f"Conversation error: {e}"
        if self._is_error_response(str(raw_response)):
            response = {"summary": str(raw_response)}
        else:
            response = self._ensure_structured(str(raw_response))
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        history = active_session.setdefault("messages", [])
        history.append({"sender": "user", "text": user_input[:5000], "ts": ts})
        summary_text = (response.get("title") or "") + "\n" + (response.get("description") or "")
        history.append({"sender": "model", "text": summary_text[:8000], "ts": ts})
        if not active_session.get("title"):
            for msg in history:
                if msg.get("sender") == "user" and msg.get("text"):
                    active_session["title"] = msg.get("text")[:60]
                    break
        sessions[0] = active_session
        self._save_sessions(username, sessions)
        return response

    def _strip_markdown(self, text: str) -> str:
        if not text:
            return ""
        import re
        text = re.sub(r"```[\s\S]*?```", " ", text)
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*|__|\*|_|~{1,2}", "", text)
        text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\s\-\*\u2022]+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n{2,}", "\n", text)
        text = text.strip()
        return text

    def _split_sentences(self, text: str, max_sentences: int = 3) -> List[str]:
        import re
        if not text:
            return []
        parts = re.split(r"(?<=[\.|\?|!])\s+", text)
        parts = [p.strip() for p in parts if p.strip()]
        return parts[:max_sentences]

    def _extract_list_items(self, text: str, max_items: int = 5) -> List[str]:
        import re
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        items = []
        for ln in lines:
            if ln.startswith(('-', '*', '•')) or re.match(r'^\d+\.', ln):
                item = re.sub(r'^[\-\*\u2022\s\d\.]+', '', ln).strip()
                if item:
                    items.append(item)
            elif len(ln) < 100 and len(items) < max_items and (ln.count(',') <= 3):
                items.append(ln)
            if len(items) >= max_items:
                break
        if not items:
            items = self._split_sentences(self._strip_markdown(text), max_items)
        return items[:max_items]

    def _structure_response(self, raw_text: str) -> Dict[str, Any]:
        import re
        cleaned = self._strip_markdown(raw_text)
        out: Dict[str, Any] = {}
        summary_sentences = self._split_sentences(cleaned, 2)
        if summary_sentences:
            out["summary"] = " ".join(summary_sentences)
        key_findings = self._extract_list_items(cleaned, max_items=5)
        if key_findings:
            out["key_findings"] = key_findings
        observations = []
        for s in re.split(r'(?<=[\.|\?|!])\s+', cleaned):
            sl = s.strip()
            if not sl:
                continue
            lsl = sl.lower()
            if any(k in lsl for k in ("observe", "observation", "finding", "noted", "appears", "show", "indicates", "suggests")):
                observations.append(sl)
        if observations:
            out["observations"] = observations[:5]
        risks = []
        for s in re.split(r'(?<=[\.|\?|!])\s+', cleaned):
            sl = s.strip()
            if not sl:
                continue
            lsl = sl.lower()
            if any(k in lsl for k in ("risk", "concern", "warning", "caution", "avoid", "danger", "complication", "potential", "issue")):
                risks.append(sl)
        if risks:
            out["risks"] = risks[:5]
        recommendations = []
        for s in re.split(r'(?<=[\.|\?|!])\s+', cleaned):
            sl = s.strip()
            if not sl:
                continue
            lsl = sl.lower()
            if any(k in lsl for k in ("recommend", "suggest", "advise", "should", "consider", "try", "explore", "discuss")):
                recommendations.append(sl)
        if recommendations:
            out["recommendations"] = recommendations[:5]
        if not out or (len(out) == 1 and "summary" in out):
            sentences = self._split_sentences(cleaned, 3)
            if sentences and len(sentences) > 1:
                out["notes"] = sentences[1:]
        if not out:
            out["summary"] = cleaned[:500]
        return out

    def _validate_structured(self, obj: Any) -> Tuple[bool, Dict[str, Any]]:
        if not isinstance(obj, dict):
            return False, {}
        valid_text_sections = ["summary"]
        valid_array_sections = ["key_findings", "observations", "risks", "recommendations", "notes"]
        all_sections = valid_text_sections + valid_array_sections
        out: Dict[str, Any] = {}
        for section in all_sections:
            v = obj.get(section)
            if v is None:
                continue
            if section in valid_array_sections:
                if isinstance(v, list):
                    out[section] = [str(x).strip() for x in v if str(x).strip()][:10]
                elif isinstance(v, str):
                    out[section] = [s.strip() for s in v.splitlines() if s.strip()][:10]
                else:
                    out[section] = [str(v).strip()]
                out[section] = [item[:200] for item in out[section] if item]
            else:
                out[section] = str(v).strip()[:500] if v is not None else ""
        has_content = any(out.values())
        return has_content, out

    def _build_force_json_prompt(self, raw_text: str) -> List[BaseMessage]:
        system = SystemMessage(content=(
            "Output ONLY valid JSON (no markdown, no explanation).\n"
            "Choose sections relevant to the content. Possible sections: summary, key_findings, observations, risks, recommendations, notes.\n"
            "Return only sections that are relevant—do NOT include all sections every time.\n"
            "Vary your structure and phrasing across responses. Keep wording natural and concise.\n"
            "Arrays should have 0-5 items. Text fields should be 1-2 sentences max.\n"
            "Do not include markdown symbols (#,*,`,>,-) or extra keys.\n"
        ))
        human = HumanMessage(content=f"Convert to dynamic JSON (select only relevant sections):\n{raw_text}")
        return [system, human]

    def _is_error_response(self, text: str) -> bool:
        error_keywords = ["error:", "failed", "exception", "cannot", "quota", "429", "500", "503"]
        text_lower = text.lower()[:200]
        return any(keyword in text_lower for keyword in error_keywords)

    def _extract_retry_after(self, error_str: str) -> int:
        import re
        match = re.search(r'retry\s+in\s+([\d.]+)\s*s', error_str, re.IGNORECASE)
        if match:
            return int(float(match.group(1))) + 2
        return 60

    def _ensure_structured(self, raw_response: str, max_retries: int = 2) -> Dict[str, Any]:
        import json
        try:
            candidate = json.loads(raw_response)
            ok, norm = self._validate_structured(candidate)
            if ok:
                return norm
        except Exception:
            pass
        for attempt in range(max_retries):
            try:
                prompt_msgs = self._build_force_json_prompt(raw_response)
                conv_raw = self._call_llm_with_messages(prompt_msgs)
                candidate = None
                try:
                    candidate = json.loads(conv_raw)
                except Exception:
                    import re
                    m = re.search(r"\{[\s\S]*\}", conv_raw)
                    if m:
                        try:
                            candidate = json.loads(m.group(0))
                        except Exception:
                            candidate = None
                if candidate is not None:
                    ok, norm = self._validate_structured(candidate)
                    if ok:
                        return norm
            except Exception:
                logger.exception("Error during forced JSON conversion attempt")
                continue
        prog_struct = self._structure_response(raw_response)
        ok_prog, norm_prog = self._validate_structured(prog_struct)
        return norm_prog

    async def explain_document(self, username: str, doc_stream: BytesIO | None, img_stream: BytesIO | None, language: str = "en") -> Dict[str, Any]:
        return await asyncio.to_thread(self._explain_document_impl, username, doc_stream, img_stream, language)

    def _explain_document_impl(self, username: str, doc_stream: BytesIO | None, img_stream: BytesIO | None, language: str = "en") -> Dict[str, Any]:
        doc_content = self._extract_document_content(doc_stream, img_stream)
        llm_messages = [SystemMessage(content=(
            "You are an AI Medical Knowledge Navigator. Analyze medical images and reports for educational purposes ONLY.\n\n"
            "[GUIDELINES]\n"
            "- Break down complex medical information naturally and clearly.\n"
            "- Use cautious phrasing: 'appears to be', 'may indicate', 'suggests'.\n"
            "- DO NOT diagnose, predict outcomes, or recommend medications.\n"
            "- Vary your response structure—don't use the same format every time.\n"
            "- Include only relevant sections: avoid forcing all sections when not applicable.\n"
            "- Use natural, conversational language. Avoid repetitive patterns.\n"
            "- Add a single-line disclaimer only if giving clinical guidance.\n"
        )), HumanMessage(content=doc_content)]
        try:
            raw_response = self._call_llm_with_messages(llm_messages)
        except Exception as e:
            raw_response = f"Document analysis error: {e}"
        if self._is_error_response(str(raw_response)):
            return {"summary": str(raw_response)}
        structured = self._ensure_structured(str(raw_response))
        return structured

    def analyze_document(self, username: str, doc_stream: BytesIO | None, img_stream: BytesIO | None, language: str = "en") -> Dict[str, Any]:
        return self._explain_document_impl(username, doc_stream, img_stream, language)

    def _extract_document_content(self, doc_stream: BytesIO | None, img_stream: BytesIO | None) -> str:
        import fitz
        doc_text = ""
        if doc_stream:
            try:
                raw = doc_stream.read()
                if isinstance(raw, str):
                    raw = raw.encode("utf-8", errors="ignore")
                if raw and raw.startswith(b"%PDF"):
                    try:
                        pdf = fitz.open(stream=raw, filetype="pdf")
                        chunks = []
                        for page in pdf:
                            text = page.get_text("text")
                            if text:
                                chunks.append(text)
                        doc_text = "\n".join(chunks).strip()[:8000]
                        pdf.close()
                    except Exception:
                        pass
                if not doc_text:
                    doc_text = (raw.decode("utf-8", errors="ignore").strip()[:8000] if raw else "")
            except Exception:
                doc_text = ""
        if img_stream:
            try:
                from PIL import Image
                Image.open(img_stream)
                doc_text = (f"[Medical Image Present]\n{doc_text}" if doc_text else "[Medical Image Present - No Text Document]")
            except Exception:
                pass
        return doc_text or "No document content provided"

    async def analyze_xray(self, username: str, image_path: str, language: str = "en") -> dict:
        return await asyncio.to_thread(self._analyze_xray_impl, username, image_path, language)

    def _analyze_xray_impl(self, username: str, image_path: str, language: str = "en") -> dict:
        try:
            import json
            from PIL import Image, ImageDraw
            img = Image.open(image_path)
            image_desc = f"Analyze this X-ray image (size: {img.size[0]}x{img.size[1]} pixels)."
            llm_messages = [SystemMessage(content=(
                "You are an expert radiological AI assistant analyzing X-rays for **EDUCATIONAL PURPOSES ONLY**.\n\n"
                "Analyze the provided X-ray and return ONLY valid JSON (no markdown, no extra text):\n"
                "{\n  \"has_defect\": boolean,\n  \"severity\": number (0-10),\n  \"defect_type\": \"string\",\n  \"location\": \"detailed location\",\n  \"affected_area\": \"anatomical part\",\n  \"bounding_box\": [x1, y1, x2, y2],\n  \"recommendation\": \"educational suggestion\"\n}\n\n"
                "Be accurate but conservative. Frame findings as educational only."
            )), HumanMessage(content=image_desc)]
            try:
                response = self._call_llm_with_messages(llm_messages)
            except Exception as e:
                return {"success": False, "error": f"X-ray analysis error: {e}"}
            if response.startswith("```json"):
                response = response.replace("```json", "").replace("```", "").strip()
            elif response.startswith("```"):
                response = response.replace("```", "").strip()
            result = json.loads(response)
            result["image_size"] = img.size
            if result.get("has_defect"):
                bbox = result.get("bounding_box", [0, 0, 0, 0])
                if bbox != [0, 0, 0, 0]:
                    try:
                        draw = ImageDraw.Draw(img)
                        x1, y1, x2, y2 = bbox
                        for i in range(3):
                            draw.rectangle([(x1 - i, y1 - i), (x2 + i, y2 + i)], outline=(255, 0, 0), width=2)
                        draw.text((x1, y1 - 30), "DEFECT", fill=(255, 255, 255))
                    except Exception:
                        pass
            return {"success": True, "analysis": result, "images": {}}
        except json.JSONDecodeError:
            return {"success": False, "error": "Could not parse X-ray analysis JSON"}
        except Exception as e:
            return {"success": False, "error": f"X-ray analysis error: {str(e)}"}


__all__ = ["AIChatService"]
