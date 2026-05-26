import streamlit as st
import time
from streamlit_app.services.api_client import ApiClient


def run():
    st.title("Chat Workflow Testing")
    client = ApiClient()
    token = st.text_input("Dev token (optional)", value=st.session_state.get('dev_token', ''))
    consultation = st.text_input("Consultation ID (optional)")
    message = st.text_area("Patient message", value="Patient reports cough and fever for two days.")
    if st.button("Send Message"):
        start = time.time()
        resp = client.send_message(token, consultation, message)
        latency = time.time() - start
        st.write("Status:", resp.status_code)
        try:
            st.json(resp.json())
        except Exception:
            st.text(resp.text)
        st.write(f"Latency: {latency:.2f}s")
        st.write("Prompt preview:")
        st.code(message)

if __name__ == '__main__':
    run()
