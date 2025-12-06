-- Migration: Add users table for user accounts & preferences
-- This migration is idempotent (safe to run multiple times)

-- Create users table if it doesn't exist
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           CITEXT NOT NULL UNIQUE,
    full_name       TEXT   NOT NULL,
    location_state  TEXT   NOT NULL,
    jurisdictions   TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    case_types      TEXT[] NOT NULL DEFAULT '{}'::TEXT[],
    user_type       TEXT   NOT NULL CHECK (user_type IN ('pro_se','lawyer','other')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create or replace the trigger function
CREATE OR REPLACE FUNCTION set_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop and recreate trigger (idempotent)
DROP TRIGGER IF EXISTS trg_users_updated_at ON users;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_users_updated_at();

-- Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_users_location_state ON users(location_state);
CREATE INDEX IF NOT EXISTS idx_users_user_type ON users(user_type);
CREATE INDEX IF NOT EXISTS idx_users_jurisdictions ON users USING gin (jurisdictions);
CREATE INDEX IF NOT EXISTS idx_users_case_types ON users USING gin (case_types);
