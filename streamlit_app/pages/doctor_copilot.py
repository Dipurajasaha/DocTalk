import streamlit as st
from streamlit_app.services.api_client import ApiClient


def run():
    st.title("Doctor Copilot Testing")
    client = ApiClient()
    token = st.text_input("Dev token (optional)", value=st.session_state.get('dev_token', ''))
    patient_id = st.text_input("Patient ID", value=st.session_state.get('dev_user_id',''))
    if st.button("Fetch Overview"):
        # lightweight calls: use existing endpoints the backend exposes
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = client.session.get(f"{client.base_url}/api/doctor/copilot/patients/{patient_id}", headers=headers)
        st.write("Status:", resp.status_code)
        try:
            st.json(resp.json())
        except Exception:
            st.text(resp.text)

if __name__ == '__main__':
    run()
