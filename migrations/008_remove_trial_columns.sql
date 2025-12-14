-- Migration 008: Remove trial-related columns from cases table
-- These columns are not relevant for appellate cases

-- Drop trial_judge column
ALTER TABLE cases DROP COLUMN IF EXISTS trial_judge;

-- Drop oral_argument_date column
ALTER TABLE cases DROP COLUMN IF EXISTS oral_argument_date;
