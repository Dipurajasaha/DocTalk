from typing import Any

def sanitize_for_llm(data: Any) -> Any:
    """
    Recursively removes internal IDs and backend-specific fields from data structures
    before they are passed to the LLM to prevent leaking UUIDs, primary keys, or system IDs.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = k.lower()
            if k_lower == "id" or k_lower == "_id" or k_lower.endswith("_id") or k_lower.endswith("id"):
                continue
            if k_lower in ["uuid", "metadata"]:
                continue
            sanitized[k] = sanitize_for_llm(v)
        return sanitized
    elif isinstance(data, list) or isinstance(data, tuple):
        return [sanitize_for_llm(item) for item in data]
    return data
