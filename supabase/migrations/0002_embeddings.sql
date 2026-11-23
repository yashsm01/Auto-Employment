-- Embeddings for the resume pre-filter. Needs the pgvector extension (built in on Supabase).
-- Gemini embeddings default to 3072 dimensions, above pgvector's 2000 limit for an HNSW
-- index on vector columns, so request output_dimensionality=768 and normalise the result.

create extension if not exists vector;

alter table resume_profiles add column embedding vector(768);
alter table jobs add column embedding vector(768);

create index jobs_embedding_idx on jobs using hnsw (embedding vector_cosine_ops);
