-- Migration 010: Add publication_status column to cases table
-- This stores the publication status from metadata (Published, Published in Part, etc.)

-- Add publication_status column
ALTER TABLE cases ADD COLUMN IF NOT EXISTS publication_status CITEXT;

-- Add index for filtering by publication status
CREATE INDEX IF NOT EXISTS idx_cases_publication_status ON cases(publication_status);

-- Verify the changes
DO $$
DECLARE
    cols TEXT[];
BEGIN
    SELECT array_agg(column_name::TEXT) INTO cols
    FROM information_schema.columns 
    WHERE table_name = 'cases' 
    AND column_name = 'publication_status';
    
    RAISE NOTICE 'publication_status column added: %', cols;
END $$;
