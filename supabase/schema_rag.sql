-- Enable pgvector for semantic search
create extension if not exists vector;

-- Embeddings table for units rows extracted from CSV
-- Uses 1536 dimensions for text-embedding-3-small
create table if not exists public.units_embeddings (
  row_id bigint primary key,
  content text,
  metadata jsonb,
  embedding vector(1536)
);

-- Similarity search RPC over the embeddings
create or replace function public.match_units(
  query_embedding vector(1536),
  match_count int default 5,
  min_similarity float default 0
)
returns table (
  row_id bigint,
  content text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    ue.row_id,
    ue.content,
    ue.metadata,
    1 - (ue.embedding <=> query_embedding) as similarity
  from public.units_embeddings as ue
  where 1 - (ue.embedding <=> query_embedding) >= min_similarity
  order by ue.embedding <=> query_embedding
  limit match_count;
$$;

-- Optional: allow anon to call search (adjust to your RLS needs)
-- grant execute on function public.match_units(vector(1536), int, float) to anon;

