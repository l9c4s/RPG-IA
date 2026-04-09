-- Migration 009: Sistema de Rounds Coletivos
-- Adiciona session_rounds e round_actions para turnos simultâneos com d20 de iniciativa.
-- round_actions também serve como training data para a IA.

-- ─── Rounds ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS session_rounds (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id    UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    round_number  INTEGER NOT NULL DEFAULT 1,
    status        TEXT NOT NULL DEFAULT 'collecting',
    -- 'collecting'    → aguardando ações dos jogadores
    -- 'resolving'     → rolando d20 e ordenando
    -- 'gm_processing' → GM narrando as ações em ordem
    -- 'completed'     → round encerrado
    started_at    TIMESTAMPTZ DEFAULT NOW(),
    resolved_at   TIMESTAMPTZ,      -- quando a fase de resolução terminou
    completed_at  TIMESTAMPTZ       -- quando o GM terminou de narrar
);

CREATE INDEX IF NOT EXISTS idx_session_rounds_session
    ON session_rounds(session_id, round_number DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_session_rounds_active
    ON session_rounds(session_id)
    WHERE status NOT IN ('completed');

-- ─── Ações por Round ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS round_actions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    round_id         UUID NOT NULL REFERENCES session_rounds(id) ON DELETE CASCADE,
    session_id       UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    player_id        UUID,                    -- NULL para AI companions
    character_id     UUID REFERENCES characters(id),
    character_name   TEXT NOT NULL,
    is_ai            BOOLEAN NOT NULL DEFAULT FALSE,
    action_text      TEXT,                   -- NULL quando is_pass = TRUE
    is_pass          BOOLEAN NOT NULL DEFAULT FALSE,
    -- Campos preenchidos na fase de resolução
    d20_roll         INTEGER CHECK (d20_roll BETWEEN 0 AND 20),
    initiative_order INTEGER,                 -- 1 = age primeiro (maior d20)
    -- Campos preenchidos após o GM processar
    gm_response      TEXT,
    gm_rolled_dice   BOOLEAN,               -- GM usou [ROLAGEM:] para este ação?
    outcome_roll     INTEGER,               -- resultado do dado do GM, se aplicável
    submitted_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_round_actions_round
    ON round_actions(round_id, initiative_order ASC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_round_actions_session
    ON round_actions(session_id, submitted_at DESC);

-- Índice específico para queries de treinamento de IA
CREATE INDEX IF NOT EXISTS idx_round_actions_training
    ON round_actions(is_ai, d20_roll, gm_rolled_dice)
    WHERE action_text IS NOT NULL;

-- Garante que cada personagem submeta no máximo uma ação por round
CREATE UNIQUE INDEX IF NOT EXISTS idx_round_actions_unique_character
    ON round_actions(round_id, character_id);
