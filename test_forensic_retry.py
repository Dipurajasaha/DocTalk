import asyncio
import io
import time
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
load_dotenv('d:/DocTalk/.env')

from backend.core.database import prisma
from backend.services.asset_service import process_asset_background, AssetService, AssetConfig
import backend.services.asset_service as asset_svc
from backend.ai.vectorstore.pgvector_service import pgvector_service
from backend.ai.core_services.embeddings import embedding_service

# Mock extraction for testing without creating a valid PDF
async def fake_extract(*args, **kwargs):
    return "My favorite color is blue."

async def fake_classify(*args, **kwargs):
    return "REPORT"

asset_svc._extract_asset_text = fake_extract
asset_svc._classify_pdf_text = fake_classify

async def main():
    await prisma.connect()
    
    user_id = 'test_forensic_user'
    
    print("\n--- 5. RUNTIME PROOF ---")
    db_rows = await prisma.query_raw(
        f"SELECT id, patient_id, metadata::text as meta_text, length(content) as content_len FROM rag_documents WHERE patient_id = '{user_id}' ORDER BY created_at DESC LIMIT 5"
    )
    for r in db_rows:
        print(f"ID: {r['id']}")
        print(f"Patient ID: {r['patient_id']}")
        print(f"Metadata: {r['meta_text']}")
        print(f"Content Length: {r['content_len']}")

    print("\n--- 6. EMBEDDING PROOF ---")
    embed_rows = await prisma.query_raw(
        f"SELECT content, array_length(embedding::real[], 1) as embed_len FROM rag_documents WHERE patient_id = '{user_id}' ORDER BY created_at DESC LIMIT 1"
    )
    for r in embed_rows:
        print(f"chunk:\n\"{r['content']}\"")
        print(f"embedding_length:\n{r['embed_len']}")

    print("\n--- 7. RETRIEVAL PROOF ---")
    res1 = await pgvector_service.search_documents(
        patient_id=user_id,
        query="What is my favorite color?",
        top_k=1
    )
    for item in res1['items']:
        print(f"similarity score: {item['similarity']:.4f}")
        print(f"retrieved chunk: {item['content']}")
        print(f"asset_id metadata: {item.get('metadata', {}).get('asset_id')}")

    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
