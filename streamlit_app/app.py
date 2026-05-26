import sys
from pathlib import Path
import streamlit as st
from importlib import import_module
import pkgutil

# Ensure repo root is on sys.path so the package imports work when Streamlit runs this file
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# import ApiClient after ensuring repo root is on sys.path
from streamlit_app.services.api_client import ApiClient

st.set_page_config(layout="wide", page_title="DocTalk Dev AI Debugger")

st.sidebar.title("DocTalk Developer Debugger")
st.sidebar.markdown('---')
st.sidebar.header('Dev Auth (local only)')

pages = {
    'Chat Workflow': 'streamlit_app.pages.chat_workflow',
    'RAG Testing': 'streamlit_app.pages.rag_testing',
    'Doctor Copilot': 'streamlit_app.pages.doctor_copilot',
    'X-ray Testing': 'streamlit_app.pages.xray_testing',
    'OCR / Prescription': 'streamlit_app.pages.ocr_prescription',
    'Visualization': 'streamlit_app.pages.visualization',
    'Health & Logs': 'streamlit_app.pages.health_and_logs',
}

choice = st.sidebar.radio('Select page', list(pages.keys()))
module_name = pages[choice]
try:
    module = import_module(module_name)
except Exception as exc:
    st.error(f"Failed to import page module '{module_name}': {exc}")
    st.exception(exc)
else:
    if hasattr(module, 'run'):
        module.run()
    else:
        st.write('Page not implemented correctly')
    
    # --- Dev auth helper (local development only) ---
    if 'dev_token' not in st.session_state:
        st.session_state['dev_token'] = ''

    with st.sidebar.expander('Auto-login / Create test user'):
        da_client = ApiClient()
        dev_user = st.text_input('Username / Doctor ID', value='dev_user')
        dev_name = st.text_input('Name', value='Dev User')
        dev_pass = st.text_input('Password', value='DevPass123!', type='password')
        col1, col2 = st.columns(2)
        if col1.button('Signup patient'):
            try:
                r = da_client.signup_patient(dev_user, dev_name, dev_pass)
                if r.ok:
                    body = r.json()
                    token = body.get('access_token')
                    user_id = body.get('user_id')
                    role = body.get('role')
                    st.session_state['dev_token'] = token or ''
                    if user_id:
                        st.session_state['dev_user_id'] = user_id
                    if role:
                        st.session_state['dev_role'] = role
                    st.success('Patient created and token set')
                else:
                    st.error(f'Signup failed: {r.status_code} {r.text}')
            except Exception as e:
                st.exception(e)
        if col2.button('Login patient'):
            try:
                r = da_client.login_patient(dev_user, dev_pass)
                if r.ok:
                    body = r.json()
                    token = body.get('access_token')
                    user_id = body.get('user_id')
                    role = body.get('role')
                    st.session_state['dev_token'] = token or ''
                    if user_id:
                        st.session_state['dev_user_id'] = user_id
                    if role:
                        st.session_state['dev_role'] = role
                    st.success('Patient logged in and token set')
                else:
                    st.error(f'Login failed: {r.status_code} {r.text}')
            except Exception as e:
                st.exception(e)
        st.markdown('---')
        st.write('Doctor accounts (local only)')
        dcol1, dcol2 = st.columns(2)
        if dcol1.button('Signup doctor'):
            try:
                r = da_client.signup_doctor(dev_user, dev_name, dev_pass)
                if r.ok:
                    body = r.json()
                    token = body.get('access_token')
                    user_id = body.get('user_id')
                    role = body.get('role')
                    st.session_state['dev_token'] = token or ''
                    if user_id:
                        st.session_state['dev_user_id'] = user_id
                    if role:
                        st.session_state['dev_role'] = role
                    st.success('Doctor created and token set')
                else:
                    st.error(f'Signup failed: {r.status_code} {r.text}')
            except Exception as e:
                st.exception(e)
        if dcol2.button('Login doctor'):
            try:
                r = da_client.login_doctor(dev_user, dev_pass)
                if r.ok:
                    body = r.json()
                    token = body.get('access_token')
                    user_id = body.get('user_id')
                    role = body.get('role')
                    st.session_state['dev_token'] = token or ''
                    if user_id:
                        st.session_state['dev_user_id'] = user_id
                    if role:
                        st.session_state['dev_role'] = role
                    st.success('Doctor logged in and token set')
                else:
                    st.error(f'Login failed: {r.status_code} {r.text}')
            except Exception as e:
                st.exception(e)
        st.write('Or use an existing token:')
        token_input = st.text_area('Dev token (overrides)', value=st.session_state.get('dev_token',''))
        if st.button('Use token'):
            st.session_state['dev_token'] = token_input.strip()
            st.success('Token stored in session')
        if st.button('Clear token'):
            st.session_state['dev_token'] = ''
            st.info('Token cleared')
