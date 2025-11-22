-- Migration: Add case outcome columns to briefs table
-- Date: November 22, 2025
-- Description: Adds denormalized outcome columns from cases table for faster queries

-- Add outcome columns
ALTER TABLE briefs 
    ADD COLUMN IF NOT EXISTS winner_legal_role CITEXT,
    ADD COLUMN IF NOT EXISTS winner_personal_role CITEXT,
    ADD COLUMN IF NOT EXISTS appeal_outcome CITEXT;

-- Add comments
COMMENT ON COLUMN briefs.winner_legal_role IS 'Denormalized from cases: Legal role of winning party (appellant/respondent)';
COMMENT ON COLUMN briefs.winner_personal_role IS 'Denormalized from cases: Personal role of winning party';
COMMENT ON COLUMN briefs.appeal_outcome IS 'Denormalized from cases: Final outcome of the appeal';

-- Add indexes for outcome analysis
CREATE INDEX IF NOT EXISTS idx_briefs_appeal_outcome ON briefs(appeal_outcome);
CREATE INDEX IF NOT EXISTS idx_briefs_winner_legal_role ON briefs(winner_legal_role);

-- Backfill existing briefs with outcome data from linked cases
UPDATE briefs b
SET 
    winner_legal_role = c.winner_legal_role,
    winner_personal_role = c.winner_personal_role,
    appeal_outcome = c.appeal_outcome
FROM cases c
WHERE b.case_id = c.case_id
  AND b.case_id IS NOT NULL
  AND b.appeal_outcome IS NULL;

-- Show results
SELECT 
    COUNT(*) as total_briefs,
    COUNT(appeal_outcome) as briefs_with_outcome,
    COUNT(DISTINCT appeal_outcome) as unique_outcomes
FROM briefs;
