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
    
    print("\n--- 3. DATABASE SCHEMA ---")
    rows = await prisma.query_raw(
        "SELECT a.attname, t.typname, a.atttypmod FROM pg_attribute a JOIN pg_class c ON a.attrelid = c.oid JOIN pg_type t ON a.atttypid = t.oid WHERE c.relname = 'rag_documents' AND a.attname = 'embedding';"
    )
    for r in rows:
        dim = r['atttypmod']
        dim_str = f"({dim})" if dim > 0 else ""
        print(f"Table: rag_documents\nColumn: {r['attname']}\nType: {r['typname']}{dim_str}")

    user_id = 'test_forensic_user'
    
    # 1. Create Patient
    await prisma.patient.upsert(
        where={'username': user_id},
        data={
            'create': {'username': user_id, 'name': 'Forensic Test', 'password': 'pass'},
            'update': {}
        }
    )
    # 2. Create User
    await prisma.user.upsert(
        where={'id': user_id},
        data={'create': {'id': user_id}, 'update': {}}
    )
    
    print("\n--- 5. RUNTIME PROOF ---")
    service = AssetService(AssetConfig(storage_folder="unclassified"))
    asset_id = "forensic_asset_1"
    stored_path = service.upload_root / "forensic_doc.pdf"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_text("fake pdf")
    
    await pgvector_service.delete_document_embeddings(asset_id=asset_id)
    await prisma.medicalasset.delete_many(where={"id": asset_id})
    
    await prisma.medicalasset.create(
        data={
            "id": asset_id,
            "userId": user_id,
            "fileName": "forensic_doc.pdf",
            "fileType": "application/pdf",
            "folderPath": "/my_documents/unclassified/",
            "assetCategory": "UNCLASSIFIED",
            "processingStatus": "PENDING",
        }
    )
    
    try:
        await process_asset_background(asset_id, str(stored_path), "application/pdf", prisma)
    except Exception:
        pass
        
    db_rows = await prisma.query_raw(
        "SELECT id, patient_id, metadata, length(content) as content_len FROM rag_documents WHERE patient_id =  ORDER BY created_at DESC LIMIT 5;",
        user_id
    )
    for r in db_rows:
        print(f"ID: {r['id']}")
        print(f"Patient ID: {r['patient_id']}")
        print(f"Metadata: {r['metadata']}")
        print(f"Content Length: {r['content_len']}")

    print("\n--- 6. EMBEDDING PROOF ---")
    embed_rows = await prisma.query_raw(
        "SELECT content, array_length(embedding::real[], 1) as embed_len FROM rag_documents WHERE patient_id =  ORDER BY created_at DESC LIMIT 1;",
        user_id
    )
    for r in embed_rows:
        print(f"chunk:\n\"{r['content']}\"")
        print(f"embedding_length:\n{r['embed_len']}")

    print("\n--- 7. RETRIEVAL PROOF ---")
    res1 = await pgvector_service.search_documents(
        patient_id=user_id,
        query="What is my favorite color?",
        top_k=1,
        asset_ids=[asset_id]
    )
    for item in res1['items']:
        print(f"similarity score: {item['similarity']:.4f}")
        print(f"retrieved chunk: {item['content']}")
        print(f"asset_id metadata: {item['metadata'].get('asset_id')}")

    # Cleanup
    await pgvector_service.delete_document_embeddings(asset_id=asset_id)
    await prisma.medicalasset.delete_many(where={"id": asset_id})
    await prisma.patient.delete_many(where={"username": user_id})
    await prisma.user.delete_many(where={"id": user_id})
    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
