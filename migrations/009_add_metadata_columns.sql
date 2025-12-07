-- Migration: 009_add_metadata_columns.sql
-- Purpose: Add columns for metadata fields that were not being stored
-- This migration is idempotent (safe to run multiple times)

-- ============================================================================
-- 1. ADD: year column for filtering by decision year
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'cases' AND column_name = 'decision_year'
    ) THEN
        ALTER TABLE cases ADD COLUMN decision_year INTEGER;
    END IF;
END $$;

COMMENT ON COLUMN cases.decision_year IS 'Year of the decision from metadata (for filtering/grouping)';

CREATE INDEX IF NOT EXISTS idx_cases_decision_year ON cases (decision_year);


-- ============================================================================
-- 2. ADD: month column for filtering by decision month
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'cases' AND column_name = 'decision_month'
    ) THEN
        ALTER TABLE cases ADD COLUMN decision_month CITEXT;
    END IF;
END $$;

COMMENT ON COLUMN cases.decision_month IS 'Month of the decision from metadata (January, February, etc.)';

CREATE INDEX IF NOT EXISTS idx_cases_decision_month ON cases (decision_month);


-- ============================================================================
-- 3. ADD: case_info_url column for the case information page URL
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'cases' AND column_name = 'case_info_url'
    ) THEN
        ALTER TABLE cases ADD COLUMN case_info_url TEXT;
    END IF;
END $$;

COMMENT ON COLUMN cases.case_info_url IS 'URL to the case information page (distinct from PDF URL)';


-- ============================================================================
-- 4. ADD: opinion_type column for Supreme Court vs Court of Appeals from metadata
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'cases' AND column_name = 'opinion_type'
    ) THEN
        ALTER TABLE cases ADD COLUMN opinion_type CITEXT;
    END IF;
END $$;

COMMENT ON COLUMN cases.opinion_type IS 'Opinion type from metadata: Supreme Court, Court of Appeals Published, Court of Appeals Unpublished';


-- ============================================================================
-- Summary of changes:
-- ============================================================================
-- 1. Added decision_year (INTEGER) - from metadata 'year'
-- 2. Added decision_month (CITEXT) - from metadata 'month' 
-- 3. Added case_info_url (TEXT) - from metadata 'case_info_url'
-- 4. Added opinion_type (CITEXT) - from metadata 'opinion_type'
