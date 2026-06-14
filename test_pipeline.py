import asyncio
import sys
import traceback
import os
from dotenv import load_dotenv

# Load env vars
load_dotenv('d:/DocTalk/.env')

from backend.workflows.unified_chat_graph import build_unified_chat_graph
from langchain_core.messages import HumanMessage

async def main():
    print('Creating workflow...')
    graph = build_unified_chat_graph()
    
    config = {'configurable': {'thread_id': 'test_thread'}}
    
    print('\n--- Test 1: hello ---')
    state = {
        'messages': [HumanMessage(content='hello')],
        'session_id': 'test_patient',
        'role': 'patient',
        'metadata': {'test': True}
    }
    
    try:
        async for event in graph.astream(state, config):
            print('Event from:', list(event.keys())[0] if event else 'unknown')
    except Exception as e:
        print(f'\nEXCEPTION in Test 1: {type(e).__name__}')
        print(f'Message: {str(e)}')
        traceback.print_exc(file=sys.stdout)
        
    print('\n--- Test 2: What is hypertension? ---')
    state = {
        'messages': [HumanMessage(content='What is hypertension?')],
        'session_id': 'test_patient',
        'role': 'patient',
        'metadata': {'test': True}
    }
    
    try:
        async for event in graph.astream(state, config):
            print('Event from:', list(event.keys())[0] if event else 'unknown')
    except Exception as e:
        print(f'\nEXCEPTION in Test 2: {type(e).__name__}')
        print(f'Message: {str(e)}')
        traceback.print_exc(file=sys.stdout)

if __name__ == '__main__':
    asyncio.run(main())
