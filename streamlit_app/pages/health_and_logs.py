import os
from pathlib import Path
from collections import deque

import streamlit as st
from streamlit_app.services.api_client import ApiClient


def tail_file(path: Path, lines: int = 200) -> str:
    if not path.exists():
        return f"Log file not found: {path}"
    dq = deque(maxlen=lines)
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                dq.append(line.rstrip("\n"))
    except Exception as e:
        return f"Error reading log file: {e}"
    return "\n".join(dq)


def find_log_file() -> Path | None:
    # Try common locations relative to repo root
    this = Path(__file__).resolve()
    repo_root = this.parents[2]
    candidates = [
        repo_root / "backend" / "backend.log",
        repo_root / "backend.log",
        repo_root / "logs" / "backend.log",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def run():
    st.title("Runtime Health & Logs")
    client = ApiClient()
    col1, col2 = st.columns(2)
    with col1:
        st.header("Backend Health")
        try:
            r = client.health()
            st.write(r.status_code)
            st.json(r.json())
        except Exception as e:
            st.error(str(e))
    with col2:
        st.header("Database Health")
        try:
            r = client.db_health()
            st.write(r.status_code)
            st.json(r.json())
        except Exception as e:
            st.error(str(e))

    st.markdown("**Recent logs (tail)**")
    log_path = find_log_file()
    if log_path is None:
        st.info(
            "No local backend log file found. Start the backend with stdout/stderr redirected to 'backend/backend.log' or 'backend.log'."
        )
        st.caption("Example (PowerShell): `python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 > backend\\backend.log 2>&1`")
    else:
        st.write(f"Reading: {log_path}")
        num_lines = st.number_input("Lines to show", min_value=20, max_value=2000, value=200)
        if st.button("Refresh logs"):
            pass
        txt = tail_file(log_path, int(num_lines))
        st.code(txt, language="json")


if __name__ == '__main__':
    run()
