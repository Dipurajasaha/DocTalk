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

async def main():
    print("Tracing: hello\n")
    
    # 1. Setup matching _run_ai_websocket
    user_text = 'hello'
    ai_session_id = 'patient_ai'
    user_id = 'test_user'
    role = 'patient'
    namespace = f"{ai_session_id}:{user_id}"
    
    messages = [HumanMessage(content=user_text)]
    
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
    
    print("--- 1. Raw workflow result returned from graph ---")
    raw_results = []
    
    # Mocking the streaming loop exactly as in _run_ai_websocket
    final_response = ""
    streamed_token = False
    
    async for event in unified_chat_graph.astream_events(workflow_state, config=ai_config, version="v2"):
        event_name = str(event.get("event") or "")
        node_name = str(event.get("name") or "")
        data = dict(event.get("data") or {})
        
        if event_name == "on_chain_end" and node_name == "patient_general_llm":
            output = data.get("output")
            raw_results.append(output)
            chunk = _extract_message_text(output)
            if chunk:
                final_response = _sanitize_ai_message(chunk)
                streamed_token = True
                
    # Since streaming is not enabled on standard invoke, we rely on the final state
    full_state = unified_chat_graph.get_state(ai_config).values
    print("Raw output from patient_general_llm node:")
    for r in raw_results:
        print(repr(r))
        
    print("\n--- 2. Value of final_response immediately after graph completes ---")
    print(repr(full_state.get('final_response')))
    
    print("\n--- 3. Value passed into API response model ---")
    print("(No response model used; it is sent directly via websocket)")
    
    print("\n--- 4. Value passed into websocket payload ---")
    
    # Re-evaluating the fallback logic exactly
    final_resp_after_graph = str(full_state.get("final_response") or "").strip()
    
    if not final_resp_after_graph:
        fallback = _role_scaffold_message(role)
        print(f"Fallback triggered! -> {repr(fallback)}")
    else:
        print(f"Normal response -> {repr(_sanitize_ai_message(final_resp_after_graph))}")
        
    print("\n--- 5. Exact condition that triggers the error string ---")
    print("Condition in ackend/api/chat/router.py: _run_ai_websocket loop:")
    print("if not final_response: final_response = str(workflow_state.get('final_response') or '').strip()")
    print("if not final_response: final_response = _role_scaffold_message(current_user.role)")
    print("\nWhere _role_scaffold_message('patient') returns: \"I'm sorry, I was unable to generate a response. Please try again.\"")

if __name__ == '__main__':
    asyncio.run(main())
