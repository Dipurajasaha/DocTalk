import asyncio
import os
import sys
from pathlib import Path
from PIL import Image

async def main():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

    from backend.ai.core_services.llm_client import _vision_gemini
    from backend.ai.prompts.templates import medical_prompt_service

    # Create a dummy PNG
    img = Image.new('RGB', (100, 100), color='red')
    img_path = Path("test_dummy.png")
    img.save(img_path)

    # Build the SAME prompt the xray service uses
    prompt = medical_prompt_service.build_xray_prompt(language="en")
    print("=== PROMPT ===")
    print(prompt)
    print("=== END PROMPT ===")

    try:
        res = await _vision_gemini(
            prompt=prompt,
            image_path=img_path,
        )
        print("Success! Result:")
        import json
        print(json.dumps(res, indent=2, default=str))
    except Exception as e:
        print("Failed with error:")
        import traceback
        traceback.print_exc()
    finally:
        if img_path.exists():
            img_path.unlink()

if __name__ == "__main__":
    asyncio.run(main())