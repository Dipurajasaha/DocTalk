import streamlit as st
import time
from streamlit_app.services.api_client import ApiClient


def run():
    st.title("RAG Testing")
    client = ApiClient()
    token = st.text_input("Dev token (optional)", value=st.session_state.get('dev_token', ''))
    pid = st.text_input("Patient ID")
    query = st.text_input("Query", value="diabetes")
    top_k = st.number_input("top_k", min_value=1, max_value=50, value=3)
    if st.button("Search"):
        payload = {"patient_id": pid, "query": query, "top_k": top_k}
        start = time.time()
        resp = client.rag_search(token, payload)
        latency = time.time() - start
        st.write("Status:", resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            st.write(f"Latency: {latency:.2f}s")
            st.write("Top results:")
            for item in data.get("items", []):
                st.markdown("---")
                st.write("Similarity:", item.get("similarity"))
                st.write("Source:", item.get("metadata", {}).get("source"))
                st.write(item.get("summary") or item.get("content") or item)
        else:
            st.text(resp.text)

if __name__ == '__main__':
    run()
