"""
Modelos ORM SQLAlchemy — mapeamento objeto-relacional das tabelas do banco.
Estes modelos são exclusivos da camada de infraestrutura e nunca são expostos
ao domínio diretamente. Os repositórios convertem ORM ↔ entidades de domínio.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CampaignORM(Base):
    """
    Mapeamento ORM da tabela `campaigns`.
    Armazena dados de configuração e estado de uma campanha.
    """

    __tablename__ = "campaigns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID | None] = mapped_column(nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rpg_system: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    tone: Mapped[str] = mapped_column(String(100), nullable=False, default="heroic")
    current_chapter: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="lobby")
    locations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Quantidade de companheiros IA configurada na criação (0 = nenhum)
    ai_players_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Progresso assíncrono da abertura: "idle" | "generating" | "ready" | "failed"
    init_status: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")
    opening_generated: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SessionORM(Base):
    """
    Mapeamento ORM da tabela `sessions`.
    Uma campanha pode ter múltiplas sessões de jogo.
    """

    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)


class SessionMessageORM(Base):
    """
    Mapeamento ORM da tabela `session_messages`.
    Histórico completo de mensagens de uma sessão (player, gm, gm_opening, ai_companion).
    """

    __tablename__ = "session_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    player_id: Mapped[UUID | None] = mapped_column(nullable=True)
    character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    msg_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SessionRoundORM(Base):
    """
    Mapeamento ORM da tabela `session_rounds`.
    Cada round agrupa as ações de todos os jogadores antes de ir ao GM.
    """

    __tablename__ = "session_rounds"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="collecting")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EnemyTemplateORM(Base):
    """
    Catálogo global de templates de inimigos.
    Populado por PDFs (bestiários), geração LLM ou homebrew.
    Não é uma lista fechada — qualquer criatura pode ser adicionada.
    """

    __tablename__ = "enemy_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enemy_type: Mapped[str] = mapped_column(String(50), nullable=False, default="humanoid")
    size: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    cr: Mapped[float] = mapped_column(Numeric(4, 2), nullable=True, default=1)
    hp_dice: Mapped[str] = mapped_column(String(30), nullable=False, default="2d8")
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    speed: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    strength: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    constitution: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    wisdom: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    charisma: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    attack_pattern: Mapped[str] = mapped_column(String(30), nullable=False, default="melee_single")
    attacks: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    special_abilities: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    damage_immunities: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    damage_resistances: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    condition_immunities: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    loot_table: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CombatEncounterORM(Base):
    """Encontro de combate ativo em uma sessão."""

    __tablename__ = "combat_encounters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    round_id_start: Mapped[UUID | None] = mapped_column(
        ForeignKey("session_rounds.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    location_desc: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CombatEnemyORM(Base):
    """
    Instância de inimigo em um encontro.
    5 goblins = 5 linhas com slugs goblin_1..goblin_5.
    """

    __tablename__ = "combat_enemies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    encounter_id: Mapped[UUID] = mapped_column(
        ForeignKey("combat_encounters.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("enemy_templates.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enemy_type: Mapped[str] = mapped_column(String(50), nullable=False, default="humanoid")
    size: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    hp_current: Mapped[int] = mapped_column(Integer, nullable=False)
    hp_max: Mapped[int] = mapped_column(Integer, nullable=False)
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False)
    attack_pattern: Mapped[str] = mapped_column(String(30), nullable=False, default="melee_single")
    attacks: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    special_abilities: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    strength: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    constitution: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    loot_rolled: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    spawned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CombatEventORM(Base):
    """Log de eventos de combate: ataques, dano, itens, mortes."""

    __tablename__ = "combat_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    encounter_id: Mapped[UUID] = mapped_column(
        ForeignKey("combat_encounters.id", ondelete="CASCADE"), nullable=False
    )
    round_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("session_rounds.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_id: Mapped[UUID | None] = mapped_column(nullable=True)
    target_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    target_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_group_attack: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    damage_dealt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    damage_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    attack_roll: Mapped[int | None] = mapped_column(Integer, nullable=True)
    damage_roll: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    item_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GmMemoryORM(Base):
    """
    Memória narrativa persistente do GM.
    Armazena fatos importantes com embedding para RAG futuro.
    """

    __tablename__ = "gm_memory"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=True, default=5)
    # embedding armazenado como JSON (lista de floats) — pgvector não está no ORM
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CampaignStateORM(Base):
    """
    Estado atual da campanha: cena, local, quests, estado do mundo.
    Uma linha por campanha (upsert).
    """

    __tablename__ = "campaign_state"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    current_scene: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_quests: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    completed_quests: Mapped[dict] = mapped_column(JSONB, nullable=True, default=list)
    world_state: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    npc_states: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CampaignSnapshotORM(Base):
    """
    Snapshot do estado da campanha ao fim de cada round.
    Permite rollback e auditoria de progresso.
    """

    __tablename__ = "campaign_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID | None] = mapped_column(nullable=True)
    state_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NpcORM(Base):
    """
    NPCs narrados pelo GM durante a campanha.
    Populado automaticamente quando o GM usa a tag [NPC:].
    """

    __tablename__ = "npcs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    location_id: Mapped[UUID | None] = mapped_column(nullable=True)
    voice_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CampaignPlayerORM(Base):
    """
    Registro de jogadores (humanos e IA) em uma campanha.
    Populado ao iniciar a sessão.
    """

    __tablename__ = "campaign_players"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    # user_id referencia users (serviço gateway) — sem FK ORM
    user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    # character_id referencia characters (serviço externo) — sem FK ORM
    character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_personality: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class LocationORM(Base):
    """
    Locais descobertos ou narrados pelo GM durante a campanha.
    Populado automaticamente quando o GM usa a tag [LOCAL:].
    """

    __tablename__ = "locations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    map_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[UUID | None] = mapped_column(nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)


class DiceRollORM(Base):
    """
    Mapeamento ORM da tabela `dice_rolls`.
    Registra toda rolagem de dado: d20 de iniciativa e rolagens do GM por ação.
    """

    __tablename__ = "dice_rolls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    # character_id referencia characters (serviço externo) — sem FK ORM
    character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    roll_type: Mapped[str] = mapped_column(String(50), nullable=False)
    dice_expr: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[int] = mapped_column(Integer, nullable=False)
    breakdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RoundActionORM(Base):
    """
    Mapeamento ORM da tabela `round_actions`.
    Cada linha é a ação de um jogador (humano ou IA) em um round.
    Serve como training data para a IA.
    """

    __tablename__ = "round_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    round_id: Mapped[UUID] = mapped_column(
        ForeignKey("session_rounds.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    player_id: Mapped[UUID | None] = mapped_column(nullable=True)
    character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    character_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    action_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    d20_roll: Mapped[int | None] = mapped_column(Integer, nullable=True)
    initiative_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gm_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    gm_rolled_dice: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome_roll: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
