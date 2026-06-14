import asyncio
import sys
import io
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
load_dotenv('d:/DocTalk/.env')

from backend.workflows.unified_chat_graph import unified_chat_graph
from backend.workflows.state import create_workflow_state
from langchain_core.messages import HumanMessage
from backend.api.chat.router import _extract_message_text, _sanitize_ai_message, _role_scaffold_message

async def validate_query(query: str):
    print(f"\n--- Validating Query: '{query}' ---")
    
    ai_session_id = 'patient_ai'
    user_id = 'test_user'
    role = 'patient'
    namespace = f"{ai_session_id}:{user_id}:debug"
    
    messages = [HumanMessage(content=query)]
    workflow_state = create_workflow_state(
        messages=messages,
        role=role,
        user_id=user_id,
        ai_session_id=ai_session_id,
        context_payload={
            "ai_session_id": ai_session_id,
            "user_id": user_id,
            "role": role,
        },
    )
    
    ai_config = {"configurable": {"thread_id": namespace}}
    
    final_response = ""
    streamed_token = False
    
    async for event in unified_chat_graph.astream_events(workflow_state, config=ai_config, version="v2"):
        event_name = str(event.get("event") or "")
        node_name = str(event.get("name") or "")
        data = dict(event.get("data") or {})
        
        if event_name == "on_chain_end" and node_name in {
            "patient_assistant_llm",
            "patient_general_llm",
            "doctor_general_llm",
            "doctor_scoped_llm",
        }:
            output = data.get("output")
            chunk = _extract_message_text(output)
            if chunk:
                final_response = _sanitize_ai_message(chunk)
                streamed_token = True
                print(f"[Streamed] Captured from node '{node_name}'")
                
    if not final_response:
        final_state = unified_chat_graph.get_state(ai_config).values
        final_response = str(final_state.get("final_response") or "").strip()
        if final_response:
            print("[Fallback] Retrieved successfully from graph state!")
            
    if not final_response:
        final_response = _role_scaffold_message(role)
        print("[Error] Failed to extract response, hit _role_scaffold_message!")
        
    print(f"Final websocket payload sent: {repr(final_response)}")

async def validate_doctor(query: str):
    print(f"\n--- Validating Doctor Route: '{query}' ---")
    
    ai_session_id = 'doctor_ai'
    user_id = 'test_user'
    role = 'doctor'
    namespace = f"{ai_session_id}:{user_id}:debug"
    
    messages = [HumanMessage(content=query)]
    workflow_state = create_workflow_state(
        messages=messages,
        role=role,
        user_id=user_id,
        ai_session_id=ai_session_id,
        context_payload={
            "ai_session_id": ai_session_id,
            "user_id": user_id,
            "role": role,
        },
    )
    
    ai_config = {"configurable": {"thread_id": namespace}}
    
    final_response = ""
    streamed_token = False
    
    async for event in unified_chat_graph.astream_events(workflow_state, config=ai_config, version="v2"):
        event_name = str(event.get("event") or "")
        node_name = str(event.get("name") or "")
        data = dict(event.get("data") or {})
        
        if event_name == "on_chain_end" and node_name in {
            "patient_assistant_llm",
            "patient_general_llm",
            "doctor_general_llm",
            "doctor_scoped_llm",
        }:
            output = data.get("output")
            chunk = _extract_message_text(output)
            if chunk:
                final_response = _sanitize_ai_message(chunk)
                streamed_token = True
                print(f"[Streamed] Captured from node '{node_name}'")
                
    if not final_response:
        final_state = unified_chat_graph.get_state(ai_config).values
        final_response = str(final_state.get("final_response") or "").strip()
        if final_response:
            print("[Fallback] Retrieved successfully from graph state!")
            
    if not final_response:
        final_response = _role_scaffold_message(role)
        print("[Error] Failed to extract response, hit _role_scaffold_message!")
        
    print(f"Final websocket payload sent: {repr(final_response)}")

async def main():
    await validate_query("hello")
    await validate_query("What is hypertension?")
    await validate_doctor("hello")

if __name__ == '__main__':
    asyncio.run(main())
