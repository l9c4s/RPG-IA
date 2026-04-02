-- Migration 006: add character_id to session_messages
ALTER TABLE session_messages
    ADD COLUMN IF NOT EXISTS character_id UUID;
