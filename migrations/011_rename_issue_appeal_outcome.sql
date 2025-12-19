-- Migration 011: Rename appeal_outcome to issue_outcome in issues_decisions table
-- Purpose: Clarify that this column represents individual issue outcomes, not overall appeal outcome
-- Date: 2025-12-19

-- Rename the column
ALTER TABLE issues_decisions 
RENAME COLUMN appeal_outcome TO issue_outcome;

-- Add comment to document the column
COMMENT ON COLUMN issues_decisions.issue_outcome IS 'Outcome for this specific issue (e.g., "affirmed", "reversed", "remanded"). Distinct from cases.appeal_outcome which represents the overall appeal outcome.';
