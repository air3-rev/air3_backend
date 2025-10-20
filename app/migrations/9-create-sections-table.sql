-- MIGRATION: Create sections table for storing generated literature review content
BEGIN;

-- Create the sections table
CREATE TABLE sections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  parent_section_id UUID NULL REFERENCES sections(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT NULL,
  summary TEXT NULL,
  content TEXT NULL,
  context JSONB DEFAULT '{}'::jsonb,
  order_index INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create indexes for better query performance
CREATE INDEX idx_sections_review_id ON sections(review_id);
CREATE INDEX idx_sections_parent_section_id ON sections(parent_section_id);
CREATE INDEX idx_sections_order_index ON sections(review_id, order_index);

-- Create trigger to update the updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_sections_updated_at
    BEFORE UPDATE ON sections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enable RLS
ALTER TABLE sections ENABLE ROW LEVEL SECURITY;

-- Create RLS policy - users can only access sections from reviews they own
CREATE POLICY sections_policy ON sections
  FOR ALL
  USING (
    review_id IN (SELECT id FROM reviews WHERE user_id = auth.uid())
  );

COMMIT;
