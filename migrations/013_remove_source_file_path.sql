-- Migration 013: Remove source_file_path column
-- The source_file_path column is redundant since we can derive the path from source_file
-- This simplifies the schema and reduces data redundancy

-- Drop from briefs table
ALTER TABLE briefs DROP COLUMN IF EXISTS source_file_path;

-- Drop from cases table
ALTER TABLE cases DROP COLUMN IF EXISTS source_file_path;

-- Migration complete
