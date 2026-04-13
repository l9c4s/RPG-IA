-- Migration 010: Sistema de Combate Persistente
-- Cria tabelas para inimigos, encontros, eventos de combate.
-- Expande inventory_items com campos de stats de itens.

-- ─── Templates de Inimigos (catálogo global) ─────────────────────────────────
-- Não é lista fechada — qualquer criatura pode ser gerada e salva aqui.
-- Populado por: PDF ingestion (bestiários), geração LLM on-the-fly, homebrew.

CREATE TABLE IF NOT EXISTS enemy_templates (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,
    enemy_type          TEXT NOT NULL DEFAULT 'humanoid',
    -- humanoid | beast | dragon | undead | construct | fiend |
    -- celestial | elemental | fey | monstrosity | ooze | plant | giant
    size                TEXT NOT NULL DEFAULT 'medium',
    -- tiny | small | medium | large | huge | gargantuan
    cr                  NUMERIC(4,2) DEFAULT 1,          -- Challenge Rating (0.125 → 30)

    -- Stats base
    hp_dice             TEXT NOT NULL DEFAULT '2d8',     -- "2d8+4", "15d20+120"
    armor_class         INTEGER NOT NULL DEFAULT 12,
    speed               INTEGER DEFAULT 30,

    -- Atributos (STR/DEX/CON/INT/WIS/CHA)
    strength            INTEGER DEFAULT 10,
    dexterity           INTEGER DEFAULT 10,
    constitution        INTEGER DEFAULT 10,
    intelligence        INTEGER DEFAULT 3,
    wisdom              INTEGER DEFAULT 10,
    charisma            INTEGER DEFAULT 5,

    -- Padrão de ataque — determina comportamento automático do backend
    -- melee_single    → ataca 1 alvo (goblin, orc, kobold)
    -- melee_multi     → multi-ataque corpo-a-corpo (ogre, troll)
    -- ranged_single   → projétil em 1 alvo (goblin arqueiro)
    -- ranged_volley   → grupo atira junto — todos os jogadores (5 goblins)
    -- breath_cone     → sopro em cone — todos os jogadores (dragão)
    -- breath_line     → sopro em linha — jogadores na linha (dragonborn)
    -- swarm           → enxame — bônus contra 1 alvo (ratos, abelhas)
    -- grapple         → tenta agarrar 1 alvo (polvo gigante, kraken)
    -- aura            → dano de aura — todos os jogadores (fantasma, lich)
    -- narrative_only  → GM decide via tag [ATAQUE_INIMIGO:] (bosses únicos)
    attack_pattern      TEXT NOT NULL DEFAULT 'melee_single',

    -- Ataques (suporta multi-ataque)
    attacks             JSONB NOT NULL DEFAULT '[]',
    -- ex: [{"name":"Mordida","attack_bonus":7,"damage":"2d10+5","damage_type":"piercing"},
    --       {"name":"Garra","attack_bonus":7,"damage":"2d6+5","damage_type":"slashing","hits":2}]

    -- Habilidades especiais
    special_abilities   JSONB DEFAULT '[]',
    -- ex: [{"name":"Resistência Mágica","description":"Vantagem em saves contra magia"},
    --       {"name":"Sopro de Fogo","recharge":"5-6","damage":"16d6",
    --        "save":{"type":"dex","dc":21},"area":"cone"}]

    -- Imunidades e resistências
    damage_immunities   JSONB DEFAULT '[]',   -- ["fire","poison"]
    damage_resistances  JSONB DEFAULT '[]',   -- ["bludgeoning","piercing"]
    condition_immunities JSONB DEFAULT '[]',  -- ["charmed","frightened"]

    -- Loot ao morrer
    loot_table          JSONB DEFAULT '[]',
    -- ex: [{"item":"Moedas de Ouro","qty":"2d6","chance":0.8},
    --       {"item":"Espada Enferrujada","qty":1,"chance":0.3}]

    source              TEXT DEFAULT 'generated',  -- pdf | generated | homebrew
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enemy_templates_type
    ON enemy_templates(enemy_type, cr);

CREATE INDEX IF NOT EXISTS idx_enemy_templates_name
    ON enemy_templates USING gin(to_tsvector('portuguese', name));

-- ─── Encontros de Combate ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS combat_encounters (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    round_id_start  UUID REFERENCES session_rounds(id),
    status          TEXT NOT NULL DEFAULT 'active',  -- active | resolved
    location_desc   TEXT,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_combat_encounters_session
    ON combat_encounters(session_id, status);

-- ─── Instâncias de Inimigos em um Encontro ───────────────────────────────────
-- Cada linha = 1 inimigo individual (5 goblins = 5 linhas)

CREATE TABLE IF NOT EXISTS combat_enemies (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    encounter_id    UUID NOT NULL REFERENCES combat_encounters(id) ON DELETE CASCADE,
    template_id     UUID REFERENCES enemy_templates(id),  -- NULL se gerado on-the-fly

    -- Identificação
    name            TEXT NOT NULL,          -- "Goblin" (nome base)
    slug            TEXT NOT NULL,          -- "goblin_1", "goblin_2" (match fuzzy)
    display_name    TEXT NOT NULL,          -- "Goblin Arqueiro #2"
    enemy_type      TEXT NOT NULL DEFAULT 'humanoid',
    size            TEXT NOT NULL DEFAULT 'medium',

    -- Estado atual
    hp_current      INTEGER NOT NULL,
    hp_max          INTEGER NOT NULL,
    armor_class     INTEGER NOT NULL,

    -- Comportamento copiado do template (pode ser sobrescrito)
    attack_pattern  TEXT NOT NULL DEFAULT 'melee_single',
    attacks         JSONB NOT NULL DEFAULT '[]',
    special_abilities JSONB DEFAULT '[]',

    -- Estado
    is_alive        BOOLEAN NOT NULL DEFAULT TRUE,
    conditions      JSONB DEFAULT '[]',     -- ["poisoned","prone","stunned"]

    -- Stats para saves
    strength        INTEGER DEFAULT 10,
    dexterity       INTEGER DEFAULT 10,
    constitution    INTEGER DEFAULT 10,

    -- Loot desta instância (rolado no spawn a partir do loot_table do template)
    loot_rolled     JSONB DEFAULT '[]',

    spawned_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_combat_enemies_encounter
    ON combat_enemies(encounter_id, is_alive);

CREATE INDEX IF NOT EXISTS idx_combat_enemies_slug
    ON combat_enemies(encounter_id, slug);

-- ─── Log de Eventos de Combate ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS combat_events (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    encounter_id    UUID NOT NULL REFERENCES combat_encounters(id) ON DELETE CASCADE,
    round_id        UUID REFERENCES session_rounds(id),

    event_type      TEXT NOT NULL,
    -- player_attack    → jogador atacou inimigo
    -- enemy_attack     → inimigo atacou jogador(es)
    -- ability_used     → habilidade especial usada
    -- condition_applied → condição aplicada (poisoned, prone, etc.)
    -- item_gained      → jogador ganhou item
    -- enemy_died       → inimigo morreu
    -- player_downed    → jogador chegou a 0 HP
    -- combat_ended     → todos os inimigos derrotados

    source_type     TEXT,               -- player | enemy | environment
    source_name     TEXT,               -- "Aragon" ou "goblin_1"
    source_id       UUID,               -- character_id ou enemy_id
    target_type     TEXT,               -- player | enemy | group
    target_name     TEXT,
    target_id       UUID,

    is_group_attack BOOLEAN DEFAULT FALSE,
    damage_dealt    INTEGER,
    damage_type     TEXT,               -- piercing | slashing | fire | cold | ...
    is_hit          BOOLEAN,
    attack_roll     INTEGER,
    damage_roll     JSONB,              -- {"dice":"2d6","result":8,"modifier":3}

    item_data       JSONB,              -- para event_type='item_gained'
    narrative       TEXT,              -- trecho do GM associado ao evento

    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_combat_events_encounter
    ON combat_events(encounter_id, created_at);

CREATE INDEX IF NOT EXISTS idx_combat_events_round
    ON combat_events(round_id);

-- ─── Expansão de inventory_items ─────────────────────────────────────────────
-- O character service usa a tabela inventory_items (não character_inventory).
-- Adicionamos campos de stats de itens que melhoram atributos do personagem.

ALTER TABLE inventory_items
    ADD COLUMN IF NOT EXISTS stat_bonuses     JSONB DEFAULT '{}',
    -- ex: {"strength":2,"armor_class":1,"attack_bonus":1,"damage_bonus":2,
    --       "dexterity":1,"wisdom":1,"max_hp":5}

    ADD COLUMN IF NOT EXISTS special_effects  JSONB DEFAULT '[]',
    -- ex: [{"trigger":"on_hit","effect":"1d6 fire damage"},
    --       {"trigger":"on_equip","effect":"advantage on stealth checks"}]

    ADD COLUMN IF NOT EXISTS rarity           TEXT DEFAULT 'common',
    -- common | uncommon | rare | very_rare | legendary

    ADD COLUMN IF NOT EXISTS is_starting_item BOOLEAN DEFAULT FALSE,
    -- TRUE para os 6 itens gerados na criação do personagem

    ADD COLUMN IF NOT EXISTS description      TEXT;
    -- descrição narrativa do item (gerada pelo LLM)
