-- Migration: Add chat_logs table
-- This table logs all chat interactions for analytics and debugging

CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Request / user info
    ip_address        VARCHAR(45),
    user_agent        VARCHAR(512),
    username          TEXT,
    user_type         TEXT,

    -- LLM info
    llm_provider      TEXT,
    llm_model         TEXT,

    -- Prompt / response
    prompt            TEXT,
    enhanced_prompt   TEXT,
    response          TEXT,

    -- JSON data
    case_filters      JSONB,
    metadata          JSONB,
    attachments       JSONB,

    -- Location info (optional enrichment)
    location_country  TEXT,
    location_region   TEXT,
    location_city     TEXT,

    -- Misc
    duration_ms       INTEGER,
    user_rating       INTEGER,
    error             TEXT
);

-- Index for querying by date
CREATE INDEX IF NOT EXISTS idx_chat_logs_created_at ON chat_logs(created_at);

-- Grant permissions to legal_user if role exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'legal_user') THEN
        GRANT ALL PRIVILEGES ON chat_logs TO legal_user;
        GRANT USAGE, SELECT ON SEQUENCE chat_logs_id_seq TO legal_user;
    END IF;
END $$;
