-- ─────────────────────────────────────────────────────────────────────────────
-- RPG Platform — Schema completo
-- ─────────────────────────────────────────────────────────────────────────────

-- ─── Knowledge Bank ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pdf_sources (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title       TEXT NOT NULL,
    rpg_system  TEXT,               -- "D&D 5e", "Pathfinder", "homebrew", etc.
    source_type TEXT,               -- "rulebook", "adventure", "bestiary", "lore", "supplement"
    filename    TEXT NOT NULL,
    minio_path  TEXT NOT NULL,
    uploaded_by UUID,
    processed   BOOLEAN DEFAULT FALSE,
    chunk_count INTEGER DEFAULT 0,
    error_msg   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id   UUID REFERENCES pdf_sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content     TEXT NOT NULL,
    rpg_system  TEXT,
    embedding   vector(1536),
    token_count INTEGER,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Índice vetorial para busca por similaridade cosine
CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding
    ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_source
    ON knowledge_chunks(source_id);

-- View de status do banco de conhecimento
CREATE OR REPLACE VIEW v_knowledge_status AS
SELECT
    COUNT(*)                              AS total_chunks,
    COUNT(*) >= 1                         AS gm_is_ready,
    COUNT(DISTINCT rpg_system)            AS total_systems,
    ARRAY_AGG(DISTINCT rpg_system)        AS sistemas_cobertos,
    COUNT(DISTINCT source_id)             AS total_sources
FROM knowledge_chunks;

-- ─── Usuários ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username      TEXT UNIQUE NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Campanhas ───────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS campaigns (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id        UUID REFERENCES users(id),
    title           TEXT NOT NULL,
    description     TEXT,
    rpg_system      TEXT DEFAULT 'D&D 5e',
    difficulty      TEXT DEFAULT 'normal',  -- easy, normal, hard, deadly
    tone            TEXT DEFAULT 'heroic',  -- heroic, dark, comedic, mystery
    current_chapter INTEGER DEFAULT 1,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaign_state (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id      UUID REFERENCES campaigns(id) ON DELETE CASCADE UNIQUE,
    current_scene    TEXT,
    current_location TEXT,
    active_quests    JSONB DEFAULT '[]',
    completed_quests JSONB DEFAULT '[]',
    world_state      JSONB DEFAULT '{}',
    npc_states       JSONB DEFAULT '{}',
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaign_snapshots (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    session_id  UUID,
    state_data  JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS campaign_players (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id  UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    user_id      UUID REFERENCES users(id),
    character_id UUID,
    is_ai        BOOLEAN DEFAULT FALSE,
    ai_personality JSONB,             -- para AI companions
    joined_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(campaign_id, user_id)
);

-- ─── Sessões ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    ended_at    TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS session_messages (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  UUID REFERENCES sessions(id) ON DELETE CASCADE,
    player_id   UUID,                 -- NULL = mensagem do GM
    role        TEXT NOT NULL,        -- "player", "gm", "system"
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}',   -- rolls, state updates, image refs
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_messages_session
    ON session_messages(session_id, created_at);

-- ─── Personagens ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS characters (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    owner_id    UUID REFERENCES users(id),
    name        TEXT NOT NULL,
    race        TEXT,
    class       TEXT,
    subclass    TEXT,
    level       INTEGER DEFAULT 1,
    proficiency_bonus INTEGER DEFAULT 2,
    background  TEXT,
    alignment   TEXT,
    char_type   TEXT DEFAULT 'pc',    -- pc, npc, ai_companion
    backstory   TEXT,
    appearance  TEXT,
    image_url   TEXT,
    is_alive    BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS character_status (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    character_id    UUID REFERENCES characters(id) ON DELETE CASCADE UNIQUE,
    hp_current      INTEGER NOT NULL DEFAULT 0,
    hp_max          INTEGER NOT NULL DEFAULT 0,
    hp_temp         INTEGER DEFAULT 0,
    spell_slots     JSONB DEFAULT '{}',   -- {"1": {"max": 4, "used": 1}, ...}
    death_saves     JSONB DEFAULT '{"successes": 0, "failures": 0}',
    conditions      JSONB DEFAULT '[]',   -- ["poisoned", "prone", ...]
    exhaustion      INTEGER DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS character_attributes (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    character_id  UUID REFERENCES characters(id) ON DELETE CASCADE UNIQUE,
    strength      INTEGER DEFAULT 10,
    dexterity     INTEGER DEFAULT 10,
    constitution  INTEGER DEFAULT 10,
    intelligence  INTEGER DEFAULT 10,
    wisdom        INTEGER DEFAULT 10,
    charisma      INTEGER DEFAULT 10,
    armor_class   INTEGER DEFAULT 10,
    initiative    INTEGER DEFAULT 0,
    speed         INTEGER DEFAULT 30,
    proficiency   INTEGER DEFAULT 2,
    saving_throws JSONB DEFAULT '{}',
    skill_profs   JSONB DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS character_inventory (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    item_name    TEXT NOT NULL,
    item_type    TEXT,                 -- weapon, armor, consumable, misc
    quantity     INTEGER DEFAULT 1,
    weight       NUMERIC(6,2) DEFAULT 0,
    value_gp     NUMERIC(10,2) DEFAULT 0,
    properties   JSONB DEFAULT '{}',
    equipped     BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS character_abilities (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    character_id UUID REFERENCES characters(id) ON DELETE CASCADE,
    ability_name TEXT NOT NULL,
    ability_type TEXT,                -- feature, spell, action, bonus_action
    description  TEXT,
    spell_level  INTEGER,
    uses_max     INTEGER,
    uses_current INTEGER,
    recharge     TEXT                 -- "short_rest", "long_rest", "dawn"
);

-- ─── Memória do GM ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gm_memory (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    memory_type TEXT,                 -- "event", "npc_decision", "player_choice", "lore"
    importance  INTEGER DEFAULT 5,    -- 1-10
    embedding   vector(1536),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gm_memory_embedding
    ON gm_memory USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

CREATE INDEX IF NOT EXISTS idx_gm_memory_campaign
    ON gm_memory(campaign_id, importance DESC);

-- ─── NPCs ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS npcs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    personality JSONB DEFAULT '{}',
    location_id UUID,
    voice_id    TEXT,                 -- ElevenLabs voice ID fixo por NPC
    is_alive    BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Locais ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS locations (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    map_url     TEXT,
    parent_id   UUID REFERENCES locations(id),
    properties  JSONB DEFAULT '{}'
);

-- ─── Dados ───────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS dice_rolls (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id   UUID REFERENCES sessions(id) ON DELETE CASCADE,
    character_id UUID REFERENCES characters(id),
    roll_type    TEXT NOT NULL,       -- "attack", "saving_throw", "skill", "damage"
    dice_expr    TEXT NOT NULL,       -- "1d20+5"
    result       INTEGER NOT NULL,
    breakdown    JSONB,               -- detalhes dos dados individuais
    rolled_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Imagens Geradas ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS generated_images (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id  UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    image_type   TEXT NOT NULL,       -- "character", "npc", "scene", "map"
    prompt       TEXT,
    minio_path   TEXT NOT NULL,
    url          TEXT NOT NULL,
    reference_id UUID,               -- character_id, location_id, etc.
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
