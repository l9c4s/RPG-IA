-- Migration 001: Add status column to campaigns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'lobby';
