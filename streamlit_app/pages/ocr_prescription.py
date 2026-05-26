import streamlit as st
import io
from streamlit_app.services.api_client import ApiClient


def run():
    st.title("OCR / Prescription Testing")
    client = ApiClient()
    token = st.text_input("Dev token (optional)", value=st.session_state.get('dev_token', ''))
    uploaded = st.file_uploader("Upload PDF or image", type=["pdf", "png", "jpg", "jpeg"])
    patient_id = st.text_input("Patient ID (required for upload)", value=st.session_state.get('dev_user_id',''))
    # Consultation helper
    with st.expander("Consultation helper (list / create)", expanded=False):
        if not token:
            st.info("Provide a Dev token to list or create consultations")
        else:
            try:
                if st.button("List consultations"):
                    res = client.list_consultations(token)
                    if res.ok:
                        items = res.json()
                        options = {f"{it.get('id')} (appt:{it.get('appointment_id')})": it.get('id') for it in items}
                        sel = st.selectbox("Select consultation", options=list(options.keys()))
                        if sel:
                            st.session_state['consultation_id'] = options[sel]
                            st.success(f"Selected consultation {st.session_state['consultation_id']}")
                    else:
                        st.error(f"Failed to list consultations: {res.status_code}")
                if 'items' in locals() and len(items) == 0:
                    st.info("No consultations found for this user.")
                    try:
                        p = client.get_my_patient_profile(token)
                        if p.ok:
                            st.success(f"Authenticated as patient: {p.json().get('patient_id')}")
                        else:
                            d = client.get_my_doctor_profile(token)
                            if d.ok:
                                st.success(f"Authenticated as doctor: {d.json().get('doctor_id')}")
                            else:
                                st.warning("Token didn't match a patient or doctor profile (401/403). Check token and permissions.")
                    except Exception:
                        st.write("Could not fetch profile info; backend may be unreachable or token invalid.")
                st.markdown("---")
                st.write("Create new consultation")
                if st.button("List appointments"):
                    try:
                        ap_res = client.list_appointments(token)
                        if ap_res.ok:
                            appts = ap_res.json()
                            if appts:
                                st.write("Found appointments:")
                                st.table([{"id": a.get("id"), "status": a.get("status"), "doctor_id": a.get("doctor_id") if a.get("doctor_id") else a.get("doctorId"), "date": a.get("date")} for a in appts])
                            else:
                                st.info("No appointments returned for this user.")
                            ap_options = {f"{a.get('id')} (status:{a.get('status')})": a.get('id') for a in appts}
                            if ap_options:
                                sel_ap = st.selectbox("Select appointment", options=list(ap_options.keys()))
                                if sel_ap:
                                    appt_id = ap_options[sel_ap]
                                    st.session_state['_selected_appointment_id'] = appt_id
                                    st.success(f"Selected appointment {appt_id}")
                        else:
                            st.error(f"Failed to list appointments: {ap_res.status_code}")
                    except Exception as exc:
                        st.exception(exc)

                st.markdown("**Create test appointment (patient token required)**")
                st.markdown("**Create test doctor (for appointments)**")
                test_doc_id = st.text_input("Doctor ID (create if needed)", value="test_doctor_1")
                test_doc_name = st.text_input("Doctor name", value="Dr Test")
                test_doc_pw = st.text_input("Doctor password", value="password", type="password")
                if st.button("Create test doctor"):
                    try:
                        rdoc = client.signup_doctor(test_doc_id, test_doc_name, test_doc_pw)
                        if rdoc.ok:
                            st.success(f"Created doctor {test_doc_id}")
                        else:
                            try:
                                st.error(f"Doctor create failed: {rdoc.status_code} - {rdoc.json()}")
                            except Exception:
                                st.error(f"Doctor create failed: {rdoc.status_code} - {rdoc.text}")
                    except Exception as exc:
                        st.exception(exc)

                test_doctor = st.text_input("Doctor ID (required to create appointment)", value=test_doc_id)
                test_date = st.text_input("Date (YYYY-MM-DD)", value="2026-06-01")
                test_time = st.text_input("Time (HH:MM)", value="09:00")
                test_reason = st.text_input("Reason", value="Dev test")
                if st.button("Create test appointment"):
                    if not test_doctor:
                        st.error("Doctor ID is required to create a test appointment")
                    else:
                        try:
                            payload = {"doctor_id": test_doctor, "date": test_date, "time": test_time, "reason": test_reason}
                            apc = client.create_appointment(token, payload)
                            if apc.ok:
                                apdata = apc.json()
                                st.success(f"Created appointment {apdata.get('id')}")
                                st.session_state['_selected_appointment_id'] = apdata.get('id')
                            else:
                                try:
                                    st.error(f"Create appointment failed: {apc.status_code} - {apc.json()}")
                                except Exception:
                                    st.error(f"Create appointment failed: {apc.status_code} - {apc.text}")
                        except Exception as exc:
                            st.exception(exc)

                appt_default = st.session_state.get('_selected_appointment_id', '')
                appt_id = st.text_input("Appointment ID (required to create)", value=appt_default)
                if st.button("Create consultation"):
                    if not appt_id:
                        st.error("Appointment ID is required to create a consultation")
                    else:
                        r = client.create_consultation(token, {"appointment_id": appt_id})
                        if r.ok:
                            data = r.json()
                            cid = data.get('id')
                            st.session_state['consultation_id'] = cid
                            st.success(f"Created consultation {cid}")
                        else:
                            try:
                                err = r.json()
                                st.error(f"Create failed: {r.status_code} - {err}")
                            except Exception:
                                st.error(f"Create failed: {r.status_code} - {r.text}")
            except Exception as exc:
                st.exception(exc)
    if uploaded and st.button("Analyze Document"):
        if not patient_id:
            st.error('Patient ID is required to upload the document')
        else:
            try:
                files = {"file": (uploaded.name, uploaded.getvalue())}
                url_upload = f"{client.base_url}/api/prescriptions/upload"
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                data = {"patient_id": patient_id}
                if st.session_state.get('consultation_id'):
                    data['consultation_id'] = st.session_state.get('consultation_id')
                up = client.session.post(url_upload, files=files, data=data, headers=headers, timeout=60)
                st.write("Upload status:", up.status_code)
                if not up.ok:
                    st.error(f"Upload failed: {up.status_code}")
                    try:
                        st.text(up.text)
                    except Exception:
                        pass
                else:
                    asset = up.json()
                    asset_id = asset.get('id')
                    if not asset_id:
                        st.error('Upload succeeded but no asset id returned')
                    else:
                        st.info(f'Uploaded asset id: {asset_id} — invoking analyzer')
                        url = f"{client.base_url}/api/processing/analyze-prescription"
                        payload = {"asset_id": asset_id, "language": "en"}
                        with st.spinner('Analyzing document (this may take a while)...'):
                            resp = client.session.post(url, json=payload, headers=headers, timeout=180)
                        st.write("Analyzer status:", resp.status_code)
                        if resp.ok:
                            try:
                                st.json(resp.json())
                            except Exception:
                                st.text(resp.text)
                        else:
                            st.error(f"Analyzer failed: {resp.status_code}")
                            try:
                                st.text(resp.text)
                            except Exception:
                                pass
            except Exception as exc:
                st.exception(exc)

if __name__ == '__main__':
    run()
