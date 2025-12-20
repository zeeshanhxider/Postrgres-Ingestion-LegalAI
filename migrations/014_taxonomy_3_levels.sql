-- Migration 014: Restructure Legal Taxonomy to 3 Levels
-- 
-- PROBLEM: Current 2-level hierarchy is too shallow for legal analytics
-- 
-- CURRENT (2 levels):
--   Category (e.g., "Family Law") → Subcategory (e.g., "Parenting Plan")
-- 
-- REQUIRED (3 levels):
--   area_of_law (e.g., "Family") → category (e.g., "Parenting Plan") → subcategory (e.g., "Residential Schedules")
-- 
-- This matches how lawyers actually think:
--   - Area of Law = Criminal, Civil, Family, Administrative (the broad umbrella)
--   - Category = Major topic bucket within that area (Parenting Plan, Property Division, Sentencing)
--   - Subcategory = Specific detail (Residential Schedules, Decision Making, Exceptional Sentence)

-- Step 1: Add new level_type value
-- We need to update the enum to include 'area_of_law'
DO $$
BEGIN
    -- Check if value already exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum 
        WHERE enumlabel = 'area_of_law' 
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'taxonomy_level_type')
    ) THEN
        ALTER TYPE taxonomy_level_type ADD VALUE 'area_of_law' BEFORE 'category';
    END IF;
END $$;

-- Step 2: Create temporary table to map old taxonomy to new structure
-- This preserves the relationships while restructuring
CREATE TABLE IF NOT EXISTS taxonomy_migration_map (
    old_taxonomy_id BIGINT,
    new_area_id BIGINT,
    new_category_id BIGINT,
    new_subcategory_id BIGINT
);

-- Step 3: Create the new area_of_law entries
-- These are the top-level umbrellas
INSERT INTO legal_taxonomy (parent_id, name, level_type) VALUES
    (NULL, 'Criminal', 'area_of_law'),
    (NULL, 'Civil', 'area_of_law'),
    (NULL, 'Family', 'area_of_law'),
    (NULL, 'Administrative', 'area_of_law'),
    (NULL, 'Constitutional', 'area_of_law'),
    (NULL, 'Juvenile', 'area_of_law'),
    (NULL, 'Probate', 'area_of_law'),
    (NULL, 'Real Property', 'area_of_law'),
    (NULL, 'Other', 'area_of_law')
ON CONFLICT (COALESCE(parent_id, -1), name, level_type) DO NOTHING;

-- Step 4: Update the unique index to support 3 levels
-- Drop and recreate with level_type included
DROP INDEX IF EXISTS idx_legal_taxonomy_unique;
CREATE UNIQUE INDEX idx_legal_taxonomy_unique 
    ON legal_taxonomy (COALESCE(parent_id, -1), name, level_type);

-- Step 5: Migration mapping for existing categories
-- Map old "category" entries to become new categories under appropriate areas
-- This is a best-effort mapping - some may need manual review

-- Criminal Law related categories -> Criminal area
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Criminal' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL
AND lt.name IN (
    'Criminal Law', 'Sentencing', 'Evidence', 'Search and Seizure', 
    'Prosecutorial Misconduct', 'Jury Instructions', 'DUI', 'Homicide',
    'Drug Offenses', 'Sex Crimes', 'Assault', 'Theft', 'Robbery',
    'Burglary', 'Weapons', 'White Collar Crime'
);

-- Family related categories -> Family area  
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Family' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL
AND lt.name IN (
    'Family Law', 'Parenting Plan', 'Child Support', 'Child Custody',
    'Divorce', 'Property Division', 'Spousal Maintenance', 'Adoption',
    'Guardianship', 'Domestic Violence', 'Paternity', 'Termination of Parental Rights'
);

-- Civil related categories -> Civil area
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Civil' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL
AND lt.name IN (
    'Civil Procedure', 'Contract', 'Tort Law', 'Property', 'Insurance',
    'Employment', 'Personal Injury', 'Medical Malpractice', 'Negligence',
    'Breach of Contract', 'Professional Liability', 'Products Liability',
    'Premises Liability', 'Defamation', 'Privacy'
);

-- Constitutional -> Constitutional area
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Constitutional' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL
AND lt.name IN (
    'Constitutional Law', 'Due Process', 'Equal Protection', 
    'First Amendment', 'Fourth Amendment', 'Fifth Amendment',
    'Sixth Amendment', 'Eighth Amendment', 'Fourteenth Amendment'
);

-- Administrative -> Administrative area
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Administrative' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL
AND lt.name IN (
    'Administrative', 'Regulatory', 'Licensing', 'Public Records',
    'Government Liability', 'Environmental', 'Tax', 'Workers Compensation',
    'Unemployment', 'Social Security', 'Immigration'
);

-- Juvenile -> Juvenile area
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Juvenile' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL
AND lt.name IN (
    'Juvenile', 'Juvenile Offender', 'Dependency', 'CHINS',
    'Juvenile Rehabilitation', 'Juvenile Transfer'
);

-- Probate -> Probate area
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Probate' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL
AND lt.name IN (
    'Probate', 'Estate', 'Trust', 'Will', 'Inheritance',
    'Guardianship', 'Conservatorship'
);

-- Real Property -> Real Property area
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Real Property' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL
AND lt.name IN (
    'Real Property', 'Land Use', 'Zoning', 'Easements', 'Boundaries',
    'Title', 'Foreclosure', 'Landlord-Tenant', 'Quiet Title'
);

-- Remaining unmapped categories -> Other area
UPDATE legal_taxonomy lt
SET parent_id = (SELECT taxonomy_id FROM legal_taxonomy WHERE name = 'Other' AND level_type = 'area_of_law'),
    level_type = 'category'
WHERE lt.level_type = 'category'
AND lt.parent_id IS NULL;

-- Step 6: Clean up orphaned old category entries that are now under areas
-- (Nothing to do here - the UPDATEs above moved them)

-- Step 7: Drop the temporary migration table
DROP TABLE IF EXISTS taxonomy_migration_map;

-- Step 8: Create a view for easy querying of the 3-level hierarchy
CREATE OR REPLACE VIEW v_legal_taxonomy_hierarchy AS
SELECT 
    area.taxonomy_id as area_id,
    area.name as area_of_law,
    cat.taxonomy_id as category_id,
    cat.name as category,
    subcat.taxonomy_id as subcategory_id,
    subcat.name as subcategory
FROM legal_taxonomy area
LEFT JOIN legal_taxonomy cat ON cat.parent_id = area.taxonomy_id AND cat.level_type = 'category'
LEFT JOIN legal_taxonomy subcat ON subcat.parent_id = cat.taxonomy_id AND subcat.level_type = 'subcategory'
WHERE area.level_type = 'area_of_law'
ORDER BY area.name, cat.name, subcat.name;

-- Step 9: Add comment explaining the new structure
COMMENT ON TABLE legal_taxonomy IS 
'3-level legal taxonomy hierarchy:
 - area_of_law: Criminal, Civil, Family, Administrative, etc. (top level umbrella)
 - category: Major topic bucket (Parenting Plan, Sentencing, Contract, etc.)
 - subcategory: Specific detail (Residential Schedules, Exceptional Sentence, etc.)
 
Use parent_id to traverse hierarchy. Use level_type to filter by level.';

-- Migration complete
