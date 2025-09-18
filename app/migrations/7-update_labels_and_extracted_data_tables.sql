-- MIGRATION: drop-and-recreate-labels-and-extracted_data (fixed view duplicate column)
BEGIN;

-- Drop dependent view(s) first
DROP VIEW IF EXISTS extracted_data_with_labels;

-- Drop the two tables and all dependent objects
DROP TABLE IF EXISTS extracted_data CASCADE;
DROP TABLE IF EXISTS labels CASCADE;

-- Ensure pgcrypto exists for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ensure papers has review_id (nullable; you must populate appropriately)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'papers' AND column_name = 'review_id'
  ) THEN
    ALTER TABLE papers ADD COLUMN review_id UUID;
  END IF;
END$$;

-- Recreate labels table
CREATE TABLE labels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  prompt TEXT,
  review_id UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  display_order INTEGER DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Recreate extracted_data table
CREATE TABLE extracted_data (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  label_id UUID NOT NULL REFERENCES labels(id) ON DELETE CASCADE,
  paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  review_id UUID NOT NULL, -- populated/validated by trigger
  data JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Indexes
CREATE INDEX idx_labels_review_id ON labels (review_id);
CREATE INDEX idx_labels_display_order ON labels (review_id, display_order);
CREATE INDEX idx_extracted_data_paper_id ON extracted_data (paper_id);
CREATE INDEX idx_extracted_data_label_paper ON extracted_data (label_id, paper_id);
CREATE INDEX idx_extracted_data_review_id ON extracted_data (review_id);

-- Trigger function to validate that paper.review_id == label.review_id and populate extracted_data.review_id
CREATE OR REPLACE FUNCTION validate_and_set_extracted_data_review()
RETURNS TRIGGER LANGUAGE plpgsql AS
$$
DECLARE
  lbl_review uuid;
  pap_review uuid;
BEGIN
  SELECT review_id INTO lbl_review FROM labels WHERE id = NEW.label_id;
  IF lbl_review IS NULL THEN
    RAISE EXCEPTION 'invalid label_id: % (no review_id found)', NEW.label_id;
  END IF;

  SELECT review_id INTO pap_review FROM papers WHERE id = NEW.paper_id;
  IF pap_review IS NULL THEN
    RAISE EXCEPTION 'invalid paper_id: % (no review_id found)', NEW.paper_id;
  END IF;

  IF lbl_review IS DISTINCT FROM pap_review THEN
    RAISE EXCEPTION 'mismatched review: label % belongs to review %, but paper % belongs to review %',
      NEW.label_id, lbl_review, NEW.paper_id, pap_review;
  END IF;

  NEW.review_id := lbl_review;
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

-- Attach trigger on extracted_data
DROP TRIGGER IF EXISTS trg_validate_extracted_data_review ON extracted_data;
CREATE TRIGGER trg_validate_extracted_data_review
  BEFORE INSERT OR UPDATE ON extracted_data
  FOR EACH ROW EXECUTE FUNCTION validate_and_set_extracted_data_review();

-- Enable RLS and policies
ALTER TABLE labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY labels_policy ON labels
  FOR ALL
  USING (
    review_id IN (SELECT id FROM reviews WHERE user_id = auth.uid())
  );

CREATE POLICY extracted_data_policy ON extracted_data
  FOR ALL
  USING (
    review_id IN (SELECT id FROM reviews WHERE user_id = auth.uid())
  );

-- Recreate view WITHOUT duplicating review_id
DROP VIEW IF EXISTS extracted_data_with_labels;
CREATE VIEW extracted_data_with_labels AS
SELECT
  ed.*,
  l.name    AS label_name,
  l.prompt  AS label_prompt,
  l.display_order
  -- note: do NOT select l.review_id here because ed.* already contains review_id
FROM extracted_data ed
JOIN labels l ON ed.label_id = l.id;


COMMIT;
