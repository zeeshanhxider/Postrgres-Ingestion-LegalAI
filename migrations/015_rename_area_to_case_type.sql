-- Migration 015: Rename area_of_law to case_type
-- 
-- The term "case_type" is more consistent with existing terminology
-- and better represents the top-level classification.

-- Step 1: Update all existing records from 'area_of_law' to 'case_type'
UPDATE legal_taxonomy 
SET level_type = 'case_type'
WHERE level_type = 'area_of_law';

-- Step 2: Update the enum type by renaming the value
-- PostgreSQL doesn't support renaming enum values directly, so we need to:
-- 1. Add the new value
-- 2. Update all usages
-- 3. Remove the old value (can't be done in same transaction)

-- Add new enum value
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum 
        WHERE enumlabel = 'case_type' 
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'taxonomy_level_type')
    ) THEN
        ALTER TYPE taxonomy_level_type ADD VALUE 'case_type' BEFORE 'category';
    END IF;
END $$;

-- Note: The old 'area_of_law' enum value cannot be dropped in the same transaction
-- It will remain in the enum type but won't be used

-- Step 3: Update the view to use case_type
CREATE OR REPLACE VIEW v_legal_taxonomy_hierarchy AS
SELECT 
    ct.taxonomy_id as case_type_id,
    ct.name as case_type,
    cat.taxonomy_id as category_id,
    cat.name as category,
    subcat.taxonomy_id as subcategory_id,
    subcat.name as subcategory
FROM legal_taxonomy ct
LEFT JOIN legal_taxonomy cat ON cat.parent_id = ct.taxonomy_id AND cat.level_type = 'category'
LEFT JOIN legal_taxonomy subcat ON subcat.parent_id = cat.taxonomy_id AND subcat.level_type = 'subcategory'
WHERE ct.level_type = 'case_type'
ORDER BY ct.name, cat.name, subcat.name;

-- Step 4: Update table comment
COMMENT ON TABLE legal_taxonomy IS 
'3-level legal taxonomy hierarchy:
 - case_type: Criminal, Civil, Family, Administrative, etc. (top level umbrella)
 - category: Major topic bucket (Parenting Plan, Sentencing, Contract, etc.)
 - subcategory: Specific detail (Residential Schedules, Exceptional Sentence, etc.)
 
Use parent_id to traverse hierarchy. Use level_type to filter by level.';

-- Migration complete
