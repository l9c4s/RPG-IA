-- Migration 002: Add proficiency_bonus to characters
ALTER TABLE characters
    ADD COLUMN IF NOT EXISTS proficiency_bonus INTEGER NOT NULL DEFAULT 2;
