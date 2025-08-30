-- Enable pgvector extension (if not already enabled)
create extension if not exists vector;

-- Create the z_documents table LangChain expects
create table if not exists public.z_documents (
    id uuid primary key default gen_random_uuid (),
    content text,
    embedding vector (1536), -- IMPORTANT: 3072 for text-embedding-3-large, 1536 for small
    metadata jsonb
);

-- Index for fast similarity search
create index if not exists idx_documents_embedding_hnsw on public.z_documents using hnsw (embedding vector_cosine_ops);

-- RPC for similarity search (LangChain SupabaseVectorStore calls this by default)
create or replace function public.match_documents(
  query_embedding vector(3072),
  match_count int,
  filter jsonb default null
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language plpgsql
security definer
set search_path = public
as $$
begin
  return query
  select d.id, d.content, d.metadata,
         1 - (d.embedding <=> query_embedding) as similarity
  from public.z_documents d
  where (filter is null)
     or (filter ? 'doc_id' and (d.metadata->>'doc_id') = (filter->>'doc_id'))
  order by d.embedding <=> query_embedding
  limit match_count;
end;
$$;