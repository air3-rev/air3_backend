-- Migration: Add key_topics and search_input columns to reviews table
BEGIN;

-- Add key_topics column as TEXT to store key topics as a string
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS key_topics TEXT;

-- Add search_input column as TEXT
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS search_input TEXT;

-- Add comments for documentation
COMMENT ON COLUMN reviews.key_topics IS 'Key topics for the review, stored as a string';
COMMENT ON COLUMN reviews.search_input IS 'Search input string for the review';

COMMIT;