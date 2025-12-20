-- Migration 017: Remove case_types table and use legal_taxonomy instead
-- 
-- The case_types table is redundant - legal_taxonomy already has case_type level entries
-- This consolidates everything into the unified taxonomy hierarchy

-- Step 1: Drop the FK constraint from cases.case_type_id to case_types
ALTER TABLE cases DROP CONSTRAINT IF EXISTS cases_case_type_id_fkey;

-- Step 2: Migrate existing case_type_id values to point to legal_taxonomy
-- Map cases.case_type_id (from case_types) to legal_taxonomy.taxonomy_id (where level_type = 'case_type')
UPDATE cases c
SET case_type_id = lt.taxonomy_id
FROM case_types ct
JOIN legal_taxonomy lt ON LOWER(ct.case_type) = LOWER(lt.name) AND lt.level_type = 'case_type'
WHERE c.case_type_id = ct.case_type_id;

-- Step 3: For any case_type_id values that couldn't be mapped, set to NULL
-- (These would be case_types that don't exist in legal_taxonomy)
UPDATE cases 
SET case_type_id = NULL 
WHERE case_type_id NOT IN (SELECT taxonomy_id FROM legal_taxonomy WHERE level_type = 'case_type')
  AND case_type_id IS NOT NULL;

-- Step 4: Add new FK constraint to legal_taxonomy
ALTER TABLE cases 
ADD CONSTRAINT cases_case_type_id_fkey 
FOREIGN KEY (case_type_id) REFERENCES legal_taxonomy(taxonomy_id) ON DELETE SET NULL;

-- Step 5: Drop the case_types table and its sequence
DROP TABLE IF EXISTS case_types CASCADE;

-- Verification comment:
-- After this migration:
-- - cases.case_type_id now references legal_taxonomy.taxonomy_id (where level_type = 'case_type')
-- - The legal_taxonomy table is the single source of truth for case_type, category, subcategory hierarchy
