-- MIGRATION: Create sections table for storing generated literature review content
BEGIN;

-- 1. Create or replace helper trigger function (shared by multiple tables)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. Create the sections table (linked to reviews and structures)
CREATE TABLE IF NOT EXISTS public.sections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Link to the review (main entity)
  review_id UUID NOT NULL REFERENCES public.reviews(id) ON DELETE CASCADE,

  -- Link to the structural blueprint (section/subsection design)
  structure_id UUID NOT NULL REFERENCES public.structures(id) ON DELETE CASCADE,

  -- Self-referencing for subsections
  parent_section_id UUID NULL REFERENCES public.sections(id) ON DELETE CASCADE,

  -- Actual content
  title TEXT NOT NULL,
  description TEXT NULL,
  summary TEXT NULL,
  content TEXT NULL,
  context JSONB DEFAULT '{}'::jsonb,

  -- Metadata
  order_index INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sections_review_id ON public.sections(review_id);
CREATE INDEX IF NOT EXISTS idx_sections_structure_id ON public.sections(structure_id);
CREATE INDEX IF NOT EXISTS idx_sections_parent_section_id ON public.sections(parent_section_id);
CREATE INDEX IF NOT EXISTS idx_sections_order_index ON public.sections(review_id, order_index);

-- 4. Trigger for updated_at
DROP TRIGGER IF EXISTS update_sections_updated_at ON public.sections;
CREATE TRIGGER update_sections_updated_at
    BEFORE UPDATE ON public.sections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 5. Enable Row Level Security
ALTER TABLE public.sections ENABLE ROW LEVEL SECURITY;

-- 6. Policy: only allow users to access their own review sections
DROP POLICY IF EXISTS sections_policy ON public.sections;
CREATE POLICY sections_policy ON public.sections
  FOR ALL
  USING (
    review_id IN (
      SELECT id FROM public.reviews WHERE user_id = auth.uid()
    )
  );

COMMIT;
