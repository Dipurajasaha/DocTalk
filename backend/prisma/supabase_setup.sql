-- Run once on your Supabase project (SQL Editor) before `prisma db push`.
-- Supabase usually has the vector extension enabled already.

CREATE EXTENSION IF NOT EXISTS vector;

-- After prisma db push, optionally add an HNSW index for faster similarity search:
-- CREATE INDEX IF NOT EXISTS rag_documents_embedding_idx
--   ON rag_documents USING hnsw (embedding vector_cosine_ops);
