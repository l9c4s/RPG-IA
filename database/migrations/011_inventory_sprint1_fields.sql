-- Migration 011: Sprint 1 inventory fields
-- Adds stat_bonuses, special_effects, rarity, is_starting_item, description
-- to character_inventory table.

ALTER TABLE inventory_items
    ADD COLUMN IF NOT EXISTS stat_bonuses      JSONB    NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS special_effects   JSONB    NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS rarity            VARCHAR(20) NOT NULL DEFAULT 'common',
    ADD COLUMN IF NOT EXISTS is_starting_item  BOOLEAN  NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS description       TEXT;
