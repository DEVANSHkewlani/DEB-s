-- Create chat_sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- Add update trigger for chat_sessions
CREATE TRIGGER trg_chat_sessions_updated BEFORE
UPDATE ON chat_sessions FOR EACH ROW EXECUTE FUNCTION update_updated_at();
-- Migrate chat_history to use sessions
-- First, add the column allowing NULLs to migrate existing data (though likely we'll just wipe or default them)
-- For this project, we can just delete old history or assign to a default session.
-- Let's TRUNCATE chat_history to start fresh as schema is changing significantly.
TRUNCATE TABLE chat_history;
-- Drop old session_id column if it was just a string/uuid without FK
-- The original schema had: session_id UUID NOT NULL DEFAULT uuid_generate_v4()
-- We want it to be a FK now.
ALTER TABLE chat_history DROP COLUMN session_id,
    ADD COLUMN session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE;
-- Add index for session lookups
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id);