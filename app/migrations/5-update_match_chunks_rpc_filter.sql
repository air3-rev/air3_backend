CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1536), 
    match_count int, 
    filter jsonb DEFAULT NULL
)
RETURNS TABLE(
    id uuid,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT c.id, c.content, c.metadata,
           1 - (c.embedding <=> query_embedding) AS similarity
    FROM public.paper_chunks c
    WHERE (filter IS NULL)
       OR (filter ? 'paper_id' AND c.metadata->>'paper_id' = filter->>'paper_id')
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;