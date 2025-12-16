-- Migration: Drop redundant category/subcategory text columns from issues_decisions
-- Date: 2025-12-16
-- Description: Completes taxonomy normalization by removing denormalized text columns
-- 
-- PREREQUISITE: Run 011_normalize_issues_taxonomy.sql first
-- This migration is IDEMPOTENT - safe to run multiple times

BEGIN;

-- ============================================================================
-- STEP 1: Verify all rows have taxonomy_id populated before dropping columns
-- ============================================================================
DO $$
DECLARE
    unlinked_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO unlinked_count 
    FROM issues_decisions 
    WHERE taxonomy_id IS NULL;
    
    IF unlinked_count > 0 THEN
        RAISE EXCEPTION 'Cannot drop columns: % rows have NULL taxonomy_id. Run 011_normalize_issues_taxonomy.sql first.', unlinked_count;
    END IF;
    
    RAISE NOTICE 'All issues_decisions rows have taxonomy_id populated. Safe to proceed.';
END $$;

-- ============================================================================
-- STEP 2: Make taxonomy_id NOT NULL (now that all rows are populated)
-- ============================================================================
DO $$
BEGIN
    -- Check if column is already NOT NULL
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'issues_decisions' 
          AND column_name = 'taxonomy_id'
          AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE issues_decisions ALTER COLUMN taxonomy_id SET NOT NULL;
        RAISE NOTICE 'Set taxonomy_id to NOT NULL';
    ELSE
        RAISE NOTICE 'taxonomy_id is already NOT NULL, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 3: Drop the category column (if exists)
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'issues_decisions' AND column_name = 'category'
    ) THEN
        ALTER TABLE issues_decisions DROP COLUMN category;
        RAISE NOTICE 'Dropped column: category';
    ELSE
        RAISE NOTICE 'Column category already dropped, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 4: Drop the subcategory column (if exists)
-- ============================================================================
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'issues_decisions' AND column_name = 'subcategory'
    ) THEN
        ALTER TABLE issues_decisions DROP COLUMN subcategory;
        RAISE NOTICE 'Dropped column: subcategory';
    ELSE
        RAISE NOTICE 'Column subcategory already dropped, skipping';
    END IF;
END $$;

-- ============================================================================
-- VERIFICATION: Show final table structure
-- ============================================================================
DO $$
DECLARE
    col_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO col_count 
    FROM information_schema.columns 
    WHERE table_name = 'issues_decisions';
    
    RAISE NOTICE 'issues_decisions now has % columns', col_count;
END $$;

COMMIT;

-- ============================================================================
-- POST-MIGRATION: Useful query to verify data via taxonomy join
-- ============================================================================
-- SELECT 
--     id.issue_id,
--     cat.name AS category,
--     subcat.name AS subcategory,
--     id.issue_summary
-- FROM issues_decisions id
-- JOIN legal_taxonomy subcat ON id.taxonomy_id = subcat.taxonomy_id
-- LEFT JOIN legal_taxonomy cat ON subcat.parent_id = cat.taxonomy_id
-- LIMIT 10;
