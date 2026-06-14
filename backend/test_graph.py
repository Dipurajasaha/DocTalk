import asyncio
import os
import sys

from langchain_core.messages import HumanMessage
from backend.workflows.unified_chat_graph import unified_chat_graph
from backend.workflows.state import WorkflowState
from backend.core.database import prisma

async def run_test():
    await prisma.connect()
    try:
        state: WorkflowState = {
        "messages": [HumanMessage(content="show my medical history")],
        "user_id": "test_patient",
        "target_patient_id": "test_patient",
        "ai_session_id": "test_session",
        "role": "patient",
        "mode": "general",
        "context_payload": {},
        "final_response": "",
        "workflow_version": "1.0",
        "execution_plan": [],
        "evidence": [],
        "action_results": [],
        "retrieval_strategy": None,
        "planner_metadata": {},
        "patient_history_context": [],
        "doctor_availability_context": [],
        "appointment_context": {},
        "consultation_context": [],
        "rag_scope": {},
        "asset_selection_context": {},
        "memory_context": [],
        "shadow_execution_completed": False,
        "shadow_response": "",
        "need_more_actions": False,
        "execution_iteration": 0,
        "pending_tasks": [],
        "response_sections": []
    }
    
        result = await unified_chat_graph.ainvoke(
            state,
            config={"configurable": {"thread_id": "test_thread_1"}}
        )
    
        print("\n--- FINAL OUTPUT ---")
        print(result.get("final_response"))
    finally:
        await prisma.disconnect()

if __name__ == "__main__":
    asyncio.run(run_test())
