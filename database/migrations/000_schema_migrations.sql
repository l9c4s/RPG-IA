-- Migration 000: Tabela de controle de migrations
-- Deve ser aplicada ANTES de qualquer outra migration.
-- Registra automaticamente cada migration aplicada com timestamp.

CREATE TABLE IF NOT EXISTS schema_migrations (
    id          SERIAL PRIMARY KEY,
    migration   VARCHAR(255) NOT NULL UNIQUE,   -- nome do arquivo, ex: "001_add_campaign_status.sql"
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE schema_migrations IS
    'Controle de versão do schema — registra cada migration aplicada e quando.';
