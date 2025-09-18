-- =====================================
-- LABELS TABLE
-- Labels are specific to papers (which are linked to reviews)
-- =====================================
CREATE TABLE labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID NOT NULL, -- References papers table
    name VARCHAR(100) NOT NULL, -- Display name like "Method", "Sample", etc.
    prompt TEXT NOT NULL, -- The actual extraction question
    display_order INTEGER DEFAULT 0, -- For UI ordering
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX idx_labels_paper_id ON labels (paper_id);
CREATE INDEX idx_labels_display_order ON labels (paper_id, display_order);

-- =====================================
-- EXTRACTED_DATA TABLE
-- Store extraction results linked to labels
-- =====================================
CREATE TABLE extracted_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label_id UUID NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
    
    -- Core extraction data (from your existing function)
    summary TEXT,
    key_points JSONB DEFAULT '[]'::jsonb,
    extracted_items JSONB DEFAULT '{}'::jsonb,
    sources JSONB DEFAULT '[]'::jsonb,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for performance
CREATE INDEX idx_extracted_data_label_id ON extracted_data (label_id);

-- JSONB indexes for efficient queries
CREATE INDEX idx_extracted_data_key_points ON extracted_data USING GIN (key_points);
CREATE INDEX idx_extracted_data_extracted_items ON extracted_data USING GIN (extracted_items);

-- =====================================
-- TRIGGERS FOR updated_at
-- =====================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER labels_updated_at BEFORE UPDATE ON labels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER extracted_data_updated_at BEFORE UPDATE ON extracted_data
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =====================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================
ALTER TABLE labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_data ENABLE ROW LEVEL SECURITY;

-- Users can access labels for papers that belong to reviews they own
CREATE POLICY "labels_policy" ON labels
    FOR ALL USING (
        paper_id IN (
            SELECT p.id FROM papers p
            JOIN reviews r ON p.review_id = r.id
            WHERE r.user_id = auth.uid()
        )
    );

-- Users can access extracted_data through labels for papers in reviews they own
CREATE POLICY "extracted_data_policy" ON extracted_data
    FOR ALL USING (
        label_id IN (
            SELECT l.id FROM labels l
            JOIN papers p ON l.paper_id = p.id
            JOIN reviews r ON p.review_id = r.id
            WHERE r.user_id = auth.uid()
        )
    );

-- =====================================
-- USEFUL VIEW
-- =====================================
CREATE VIEW extracted_data_with_labels AS
SELECT 
    ed.*,
    l.name as label_name,
    l.prompt as label_prompt,
    l.paper_id,
    l.display_order
FROM extracted_data ed
JOIN labels l ON ed.label_id = l.id;