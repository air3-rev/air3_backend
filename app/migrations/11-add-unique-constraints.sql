-- MIGRATION: Add unique constraints to labels and extracted_data tables
-- This fixes the "there is no unique or exclusion constraint matching the ON CONFLICT specification" error

BEGIN;

-- Add unique constraint on labels(review_id, name) to prevent duplicate label names within a review
ALTER TABLE labels ADD CONSTRAINT unique_labels_review_name UNIQUE (review_id, name);

-- Add unique constraint on extracted_data(label_id, paper_id) to prevent duplicate extractions
ALTER TABLE extracted_data ADD CONSTRAINT unique_extracted_data_label_paper UNIQUE (label_id, paper_id);

COMMIT;