"""
Modelos ORM SQLAlchemy — mapeamento objeto-relacional das tabelas do banco.
Estes modelos são exclusivos da camada de infraestrutura e nunca são expostos
ao domínio diretamente. Os repositórios convertem ORM ↔ entidades de domínio.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
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
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rpg_system: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    tone: Mapped[str] = mapped_column(String(100), nullable=False, default="heroic")
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
