-- Migration 005: add init_status and opening_generated to campaigns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS init_status VARCHAR(20) NOT NULL DEFAULT 'idle';
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS opening_generated BOOLEAN NOT NULL DEFAULT FALSE;
