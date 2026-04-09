-- Migration 007: persiste a quantidade de companheiros IA configurada na criação da campanha
ALTER TABLE campaigns
    ADD COLUMN IF NOT EXISTS ai_players_count INTEGER NOT NULL DEFAULT 0;
