import asyncio
from dotenv import load_dotenv

load_dotenv('d:/DocTalk/.env')

from backend.core.database import prisma

async def main():
    await prisma.connect()
    
    # Try to find the dimension constraint
    rows = await prisma.query_raw(
        "SELECT pg_get_expr(adbin, adrelid) AS default_val FROM pg_attrdef WHERE adrelid = 'rag_documents'::regclass AND adnum = (SELECT attnum FROM pg_attribute WHERE attrelid = 'rag_documents'::regclass AND attname = 'embedding');"
    )
    print("Default expr:", rows)
    
    rows2 = await prisma.query_raw(
        "SELECT atttypmod FROM pg_attribute WHERE attrelid = 'rag_documents'::regclass AND attname = 'embedding';"
    )
    print("Typmod:", rows2)
    
    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
