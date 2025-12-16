-- Migration: Normalize issues_decisions category/subcategory into legal_taxonomy
-- Date: 2025-12-16
-- Description: Creates hierarchical legal_taxonomy table and links issues_decisions via FK
-- 
-- This migration is IDEMPOTENT - safe to run multiple times

BEGIN;

-- ============================================================================
-- STEP 1: Create the level_type enum (if not exists)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taxonomy_level_type') THEN
        CREATE TYPE taxonomy_level_type AS ENUM ('case_type', 'category', 'subcategory');
        RAISE NOTICE 'Created enum type: taxonomy_level_type';
    ELSE
        RAISE NOTICE 'Enum type taxonomy_level_type already exists, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 2: Create the legal_taxonomy table
-- ============================================================================
CREATE TABLE IF NOT EXISTS legal_taxonomy (
    taxonomy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id BIGINT REFERENCES legal_taxonomy(taxonomy_id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    level_type taxonomy_level_type NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Ensure unique name within same parent (allows same subcategory name under different categories)
    CONSTRAINT legal_taxonomy_unique_name_parent UNIQUE (parent_id, name, level_type)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_legal_taxonomy_parent ON legal_taxonomy(parent_id);
CREATE INDEX IF NOT EXISTS idx_legal_taxonomy_level ON legal_taxonomy(level_type);
CREATE INDEX IF NOT EXISTS idx_legal_taxonomy_name ON legal_taxonomy(name);

DO $$ BEGIN RAISE NOTICE 'Created legal_taxonomy table (if not existed)'; END $$;

-- ============================================================================
-- STEP 3: Seed Categories (level_type = 'category', parent_id = NULL)
-- ============================================================================
-- Insert distinct categories from issues_decisions that don't already exist
INSERT INTO legal_taxonomy (parent_id, name, level_type, description)
SELECT DISTINCT
    NULL::BIGINT AS parent_id,
    category AS name,
    'category'::taxonomy_level_type AS level_type,
    'Legal issue category extracted from case opinions' AS description
FROM issues_decisions
WHERE category IS NOT NULL 
  AND category != ''
  AND NOT EXISTS (
      SELECT 1 FROM legal_taxonomy lt 
      WHERE lt.name = issues_decisions.category 
        AND lt.level_type = 'category'
        AND lt.parent_id IS NULL
  )
ON CONFLICT (parent_id, name, level_type) DO NOTHING;

-- Log count
DO $$
DECLARE
    cat_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO cat_count FROM legal_taxonomy WHERE level_type = 'category';
    RAISE NOTICE 'Total categories in legal_taxonomy: %', cat_count;
END $$;

-- ============================================================================
-- STEP 4: Seed Subcategories (level_type = 'subcategory', parent_id = category)
-- ============================================================================
-- Insert distinct subcategories linked to their parent categories
INSERT INTO legal_taxonomy (parent_id, name, level_type, description)
SELECT DISTINCT
    cat.taxonomy_id AS parent_id,
    id.subcategory AS name,
    'subcategory'::taxonomy_level_type AS level_type,
    'Legal issue subcategory extracted from case opinions' AS description
FROM issues_decisions id
JOIN legal_taxonomy cat 
    ON cat.name = id.category 
    AND cat.level_type = 'category'
    AND cat.parent_id IS NULL
WHERE id.subcategory IS NOT NULL 
  AND id.subcategory != ''
  AND NOT EXISTS (
      SELECT 1 FROM legal_taxonomy lt 
      WHERE lt.name = id.subcategory 
        AND lt.level_type = 'subcategory'
        AND lt.parent_id = cat.taxonomy_id
  )
ON CONFLICT (parent_id, name, level_type) DO NOTHING;

-- Log count
DO $$
DECLARE
    subcat_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO subcat_count FROM legal_taxonomy WHERE level_type = 'subcategory';
    RAISE NOTICE 'Total subcategories in legal_taxonomy: %', subcat_count;
END $$;

-- ============================================================================
-- STEP 5: Add taxonomy_id column to issues_decisions (if not exists)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'issues_decisions' AND column_name = 'taxonomy_id'
    ) THEN
        ALTER TABLE issues_decisions ADD COLUMN taxonomy_id BIGINT;
        RAISE NOTICE 'Added taxonomy_id column to issues_decisions';
    ELSE
        RAISE NOTICE 'Column taxonomy_id already exists in issues_decisions, skipping';
    END IF;
END $$;

-- ============================================================================
-- STEP 6: Add Foreign Key constraint (if not exists)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_issues_decisions_taxonomy'
          AND table_name = 'issues_decisions'
    ) THEN
        ALTER TABLE issues_decisions 
        ADD CONSTRAINT fk_issues_decisions_taxonomy 
        FOREIGN KEY (taxonomy_id) REFERENCES legal_taxonomy(taxonomy_id);
        RAISE NOTICE 'Added FK constraint fk_issues_decisions_taxonomy';
    ELSE
        RAISE NOTICE 'FK constraint fk_issues_decisions_taxonomy already exists, skipping';
    END IF;
END $$;

-- Create index for faster joins
CREATE INDEX IF NOT EXISTS idx_issues_decisions_taxonomy ON issues_decisions(taxonomy_id);

-- ============================================================================
-- STEP 7: Populate taxonomy_id in issues_decisions
-- ============================================================================
-- Update issues_decisions to link to the correct subcategory taxonomy entry
-- Match: subcategory name AND parent category name
UPDATE issues_decisions id
SET taxonomy_id = subcat.taxonomy_id
FROM legal_taxonomy subcat
JOIN legal_taxonomy cat ON subcat.parent_id = cat.taxonomy_id
WHERE id.subcategory IS NOT NULL
  AND id.subcategory != ''
  AND id.category IS NOT NULL
  AND id.category != ''
  AND subcat.name = id.subcategory
  AND subcat.level_type = 'subcategory'
  AND cat.name = id.category
  AND cat.level_type = 'category'
  AND id.taxonomy_id IS NULL;  -- Only update rows not yet linked

-- For issues with category but no subcategory, link to the category level
UPDATE issues_decisions id
SET taxonomy_id = cat.taxonomy_id
FROM legal_taxonomy cat
WHERE (id.subcategory IS NULL OR id.subcategory = '')
  AND id.category IS NOT NULL
  AND id.category != ''
  AND cat.name = id.category
  AND cat.level_type = 'category'
  AND cat.parent_id IS NULL
  AND id.taxonomy_id IS NULL;

-- Log results
DO $$
DECLARE
    linked_count INTEGER;
    unlinked_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO linked_count FROM issues_decisions WHERE taxonomy_id IS NOT NULL;
    SELECT COUNT(*) INTO unlinked_count FROM issues_decisions WHERE taxonomy_id IS NULL;
    RAISE NOTICE 'Issues linked to taxonomy: %', linked_count;
    RAISE NOTICE 'Issues not yet linked (NULL taxonomy_id): %', unlinked_count;
END $$;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration to verify)
-- ============================================================================

-- Show taxonomy hierarchy
-- SELECT 
--     cat.taxonomy_id AS category_id,
--     cat.name AS category_name,
--     subcat.taxonomy_id AS subcategory_id,
--     subcat.name AS subcategory_name
-- FROM legal_taxonomy cat
-- LEFT JOIN legal_taxonomy subcat ON subcat.parent_id = cat.taxonomy_id
-- WHERE cat.level_type = 'category'
-- ORDER BY cat.name, subcat.name;

-- Show unlinked issues (if any)
-- SELECT issue_id, category, subcategory, taxonomy_id 
-- FROM issues_decisions 
-- WHERE taxonomy_id IS NULL 
-- LIMIT 20;

-- Verify data integrity
-- SELECT 
--     id.issue_id,
--     id.category AS old_category,
--     id.subcategory AS old_subcategory,
--     cat.name AS new_category,
--     subcat.name AS new_subcategory
-- FROM issues_decisions id
-- JOIN legal_taxonomy subcat ON id.taxonomy_id = subcat.taxonomy_id
-- LEFT JOIN legal_taxonomy cat ON subcat.parent_id = cat.taxonomy_id
-- LIMIT 20;

COMMIT;

-- ============================================================================
-- NOTES:
-- ============================================================================
-- 1. Old columns (category, subcategory) are preserved for verification
-- 2. Run verification queries above before dropping old columns
-- 3. To drop old columns after verification:
--    ALTER TABLE issues_decisions DROP COLUMN category;
--    ALTER TABLE issues_decisions DROP COLUMN subcategory;
-- 4. The legal_taxonomy table supports 3 levels: case_type, category, subcategory
--    - Future: can add case_types as parents of categories for deeper hierarchy
