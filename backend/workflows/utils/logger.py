import os
import json
from typing import Any

def is_debug_verbose() -> bool:
    return os.environ.get("DEBUG_VERBOSE", "false").lower() == "true"

def log_section(title: str):
    print(f"============================================================")
    print(title.upper())
    print(f"============================================================")
    print()

def log_step(name: str, value: str):
    print(f"{name}:")
    print(value)
    print()

def log_key_value(key: str, value: Any):
    print(f"{key}:")
    if isinstance(value, list) and value:
        for i, item in enumerate(value):
            if hasattr(item, "capability_name"):
                print(f"{i+1}. {item.capability_name}")
            else:
                print(f"- {item}")
    elif isinstance(value, dict) and value:
        for k, v in value.items():
            print(f"{k}={v}")
    else:
        print(value)
    print()

def log_trace(title: str, large_data: Any):
    if is_debug_verbose():
        print(f"--- TRACE: {title} ---")
        if isinstance(large_data, (dict, list)):
            print(json.dumps(large_data, indent=2, default=str))
        else:
            print(large_data)
        print("-----------------------")
        print()

def log_success(msg: str):
    print(f"SUCCESS: {msg}\n")

def log_warning(msg: str):
    print(f"WARNING: {msg}\n")

def log_error(msg: str):
    print(f"ERROR: {msg}\n")

def format_duration(ms: float) -> str:
    return f"{int(ms)} ms"
