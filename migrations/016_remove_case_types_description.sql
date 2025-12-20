-- Migration 016: Remove description column from case_types table
-- 
-- The description column is unused and adds unnecessary complexity

-- Drop the description column
ALTER TABLE case_types DROP COLUMN IF EXISTS description;
