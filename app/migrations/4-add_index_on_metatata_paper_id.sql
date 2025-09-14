CREATE INDEX idx_paper_chunks_metadata_paper_id 
ON paper_chunks USING GIN ((metadata->'paper_id'));