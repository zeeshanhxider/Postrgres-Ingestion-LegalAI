-- Migration: Fix legal_taxonomy duplicates and remove description column
-- Date: 2025-12-18
-- Description: 
--   1. Consolidate duplicate taxonomy entries
--   2. Update issues_decisions to point to canonical entries
--   3. Delete duplicates
--   4. Drop unnecessary description column
--   5. Fix unique constraint to handle NULL parent_id
--
-- This migration is IDEMPOTENT - safe to run multiple times

BEGIN;

-- ============================================================================
-- STEP 1: Identify and keep the lowest taxonomy_id for each (parent_id, name, level_type)
-- ============================================================================

-- Create temp table with canonical (first) taxonomy_id for each unique combo
CREATE TEMP TABLE canonical_taxonomy AS
SELECT 
    COALESCE(parent_id, -1) AS parent_key,  -- Use -1 for NULL parent
    name,
    level_type,
    MIN(taxonomy_id) AS canonical_id
FROM legal_taxonomy
GROUP BY COALESCE(parent_id, -1), name, level_type;

DO $$ 
DECLARE
    dup_count INTEGER;
BEGIN
    SELECT COUNT(*) - COUNT(DISTINCT (COALESCE(parent_id, -1), name, level_type)) 
    INTO dup_count FROM legal_taxonomy;
    RAISE NOTICE 'Found % duplicate taxonomy entries to consolidate', dup_count;
END $$;

-- ============================================================================
-- STEP 2: Update issues_decisions to point to canonical taxonomy_id
-- ============================================================================

UPDATE issues_decisions id
SET taxonomy_id = ct.canonical_id
FROM legal_taxonomy lt
JOIN canonical_taxonomy ct 
    ON COALESCE(lt.parent_id, -1) = ct.parent_key 
    AND lt.name = ct.name 
    AND lt.level_type = ct.level_type
WHERE id.taxonomy_id = lt.taxonomy_id
  AND id.taxonomy_id != ct.canonical_id;

DO $$ 
DECLARE
    updated_count INTEGER;
BEGIN
    GET DIAGNOSTICS updated_count = ROW_COUNT;
    RAISE NOTICE 'Updated % issues_decisions rows to canonical taxonomy_id', updated_count;
END $$;

-- ============================================================================
-- STEP 3: Update subcategory parent_id references to canonical category IDs
-- ============================================================================

-- For subcategories pointing to duplicate category parents, update to canonical
UPDATE legal_taxonomy sub
SET parent_id = ct.canonical_id
FROM legal_taxonomy parent
JOIN canonical_taxonomy ct 
    ON COALESCE(parent.parent_id, -1) = ct.parent_key 
    AND parent.name = ct.name 
    AND parent.level_type = ct.level_type
WHERE sub.parent_id = parent.taxonomy_id
  AND sub.parent_id != ct.canonical_id;

-- ============================================================================
-- STEP 4: Delete duplicate taxonomy entries (keep only canonical ones)
-- ============================================================================

DELETE FROM legal_taxonomy lt
WHERE lt.taxonomy_id NOT IN (
    SELECT canonical_id FROM canonical_taxonomy
);

DO $$ 
DECLARE
    remaining_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining_count FROM legal_taxonomy;
    RAISE NOTICE 'Remaining taxonomy entries after dedup: %', remaining_count;
END $$;

DROP TABLE canonical_taxonomy;

-- ============================================================================
-- STEP 5: Drop the description column (not needed)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'legal_taxonomy' AND column_name = 'description'
    ) THEN
        ALTER TABLE legal_taxonomy DROP COLUMN description;
        RAISE NOTICE 'Dropped column: description';
    ELSE
        RAISE NOTICE 'Column description already dropped, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 6: Drop old unique constraint and create a new one that handles NULLs
-- ============================================================================

-- Drop existing constraint
ALTER TABLE legal_taxonomy 
DROP CONSTRAINT IF EXISTS legal_taxonomy_unique_name_parent;

-- Create unique index that treats NULL parent_id as equal
-- Using COALESCE to convert NULL to a sentinel value for uniqueness
CREATE UNIQUE INDEX IF NOT EXISTS idx_legal_taxonomy_unique 
ON legal_taxonomy (COALESCE(parent_id, -1), name, level_type);

DO $$ BEGIN RAISE NOTICE 'Created unique index with NULL handling'; END $$;

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    cat_count INTEGER;
    subcat_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO cat_count FROM legal_taxonomy WHERE level_type = 'category';
    SELECT COUNT(*) INTO subcat_count FROM legal_taxonomy WHERE level_type = 'subcategory';
    RAISE NOTICE 'Final counts - Categories: %, Subcategories: %', cat_count, subcat_count;
END $$;

COMMIT;
