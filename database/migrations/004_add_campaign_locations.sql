-- Migration 004: add locations_json column to campaigns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS locations_json TEXT;
