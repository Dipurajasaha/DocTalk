import asyncio
from dotenv import load_dotenv

load_dotenv('d:/DocTalk/.env')

from backend.core.config import settings

print(f"Loaded config GEMINI_EMBED_MODEL = {settings.gemini_embed_model}")
