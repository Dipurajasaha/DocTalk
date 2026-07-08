import asyncio
from backend.ai.core_services.llm_client import complete_text
import os

async def main():
    try:
        res = await complete_text([{'role':'user', 'content':'Return {"test": 1}'}], response_format={'type':'json_object'})
        print('WITH FORMAT:', repr(res))
    except Exception as e:
        print('WITH FORMAT FAILED:', e)
    
    try:
        res2 = await complete_text([{'role':'user', 'content':'Return {"test": 1}'}])
        print('WITHOUT FORMAT:', repr(res2))
    except Exception as e:
        print('WITHOUT FORMAT FAILED:', e)

if __name__ == "__main__":
    asyncio.run(main())
