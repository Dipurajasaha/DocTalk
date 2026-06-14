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
    return "My name is Raj.\nMy favorite color is blue.\nWBC count is 7600."

async def fake_classify(*args, **kwargs):
    return "REPORT"

asset_svc._extract_asset_text = fake_extract
asset_svc._classify_pdf_text = fake_classify

async def main():
    await prisma.connect()
    
    user_id = 'test_rag_patient_1'
    
    # 1. Create Patient (needed for RagDocument)
    await prisma.patient.upsert(
        where={'username': user_id},
        data={
            'create': {'username': user_id, 'name': 'Test RAG Patient', 'password': 'pass'},
            'update': {}
        }
    )
    # 2. Create User (needed for MedicalAsset)
    await prisma.user.upsert(
        where={'id': user_id},
        data={
            'create': {'id': user_id},
            'update': {}
        }
    )
    
    print("\n--- A. Upload Flow ---")
    service = AssetService(AssetConfig(storage_folder="unclassified"))
    
    asset_id = "test_rag_asset_1"
    stored_path = service.upload_root / "test_doc.pdf"
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    stored_path.write_text("fake pdf")
    
    # Clean up prior
    await pgvector_service.delete_document_embeddings(asset_id=asset_id)
    await prisma.medicalasset.delete_many(where={"id": asset_id})
    
    await prisma.medicalasset.create(
        data={
            "id": asset_id,
            "userId": user_id,
            "fileName": "test_doc.pdf",
            "fileType": "application/pdf",
            "folderPath": "/my_documents/unclassified/",
            "assetCategory": "UNCLASSIFIED",
            "processingStatus": "PENDING",
        }
    )
    print("Asset record created.")
    
    print("\n--- B. Wait for Processing ---")
    try:
        await process_asset_background(asset_id, str(stored_path), "application/pdf", prisma)
    except Exception as e:
        print(f"Error in processing: {e}")
    
    asset = await prisma.medicalasset.find_unique(where={"id": asset_id})
    print(f"Extracted text: {repr(asset.extractedText)}")
    print(f"Status: {asset.processingStatus}")
    
    # Verify embeddings
    docs = await prisma.ragdocument.find_many(where={"patientId": user_id})
    docs = [d for d in docs if (d.metadata or {}).get("asset_id") == asset_id]
    print(f"Number of embeddings generated/inserted: {len(docs)}")
    if len(docs) > 0:
        print(f"Chunks created: {[d.content for d in docs]}")
    
    print(f"Embedding model used: {embedding_service.model_name}")
    print(f"Embedding dimensions: {embedding_service.dimension}")
    
    print("\n--- C. Query 1: What is my favorite color? ---")
    res1 = await pgvector_service.search_documents(
        patient_id=user_id,
        query="What is my favorite color?",
        top_k=5,
        asset_ids=[asset_id]
    )
    for item in res1['items']:
        print(f"Score: {item['similarity']:.4f} | Content: {item['content']}")
        
    print("\n--- D. Query 2: What was my WBC count? ---")
    res2 = await pgvector_service.search_documents(
        patient_id=user_id,
        query="What was my WBC count?",
        top_k=5,
        asset_ids=[asset_id]
    )
    for item in res2['items']:
        print(f"Score: {item['similarity']:.4f} | Content: {item['content']}")
        
    # Cleanup
    await pgvector_service.delete_document_embeddings(asset_id=asset_id)
    await prisma.medicalasset.delete(where={"id": asset_id})
    await prisma.patient.delete(where={"username": user_id})
    await prisma.user.delete(where={"id": user_id})
    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
