import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

async def test_llm():
    # Load variables from .env
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL")
    
    if not api_key or not model:
        print("Error: OPENAI_API_KEY or OPENAI_MODEL is not set in .env")
        return
        
    print(f"Testing with Model: {model}")
    print(f"Base URL: {base_url}")
    print("Sending test request to the AI model...")
    
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello! Please reply with a short message confirming that you are working."}],
            max_tokens=100
        )
        print("\nSuccess! Response received:")
        print("-" * 40)
        print(response.choices[0].message.content)
        print("-" * 40)
    except Exception as e:
        print("\nFailed to get a response!")
        print(f"Error details: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_llm())
