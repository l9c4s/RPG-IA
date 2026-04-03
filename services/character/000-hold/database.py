import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    Float,
    JSON,
    func,
)
from uuid import UUID, uuid4
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

POSTGRES_USER: str = os.getenv("POSTGRES_USER", "rpg")
POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "rpg")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "rpg_character")

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@postgres:5432/{POSTGRES_DB}",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# ORM Tables
# ---------------------------------------------------------------------------


class CharacterDB(Base):
    __tablename__ = "characters"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    race: Mapped[str] = mapped_column(String(100), nullable=False)
    class_: Mapped[str] = mapped_column("class", String(100), nullable=False)
    subclass: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    proficiency_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    background: Mapped[str | None] = mapped_column(String(200), nullable=True)
    alignment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    char_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="player"
    )  # player | npc | monster
    backstory: Mapped[str | None] = mapped_column(Text, nullable=True)
    appearance: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_id: Mapped[UUID | None] = mapped_column(nullable=True)
    owner_id: Mapped[UUID | None] = mapped_column(nullable=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    status: Mapped["CharacterStatusDB"] = relationship(
        "CharacterStatusDB", back_populates="character", uselist=False, lazy="select"
    )
    attributes: Mapped["CharacterAttributesDB"] = relationship(
        "CharacterAttributesDB",
        back_populates="character",
        uselist=False,
        lazy="select",
    )
    inventory: Mapped[list["InventoryItemDB"]] = relationship(
        "InventoryItemDB", back_populates="character", lazy="select"
    )
    abilities: Mapped[list["AbilityDB"]] = relationship(
        "AbilityDB", back_populates="character", lazy="select"
    )


class CharacterStatusDB(Base):
    __tablename__ = "character_status"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    hp_max: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hp_current: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hp_temp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # JSON list of active condition strings, e.g. ["poisoned", "prone"]
    conditions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # JSON object mapping spell level (str) to remaining slots, e.g. {"1": 4, "2": 2}
    spell_slots: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    exhaustion: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    death_saves_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    death_saves_failure: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    character: Mapped["CharacterDB"] = relationship(
        "CharacterDB", back_populates="status"
    )


class CharacterAttributesDB(Base):
    __tablename__ = "character_attributes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    strength: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    constitution: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    wisdom: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    charisma: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    initiative: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    speed: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    character: Mapped["CharacterDB"] = relationship(
        "CharacterDB", back_populates="attributes"
    )


class InventoryItemDB(Base):
    __tablename__ = "inventory_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    item_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="misc"
    )  # weapon | armor | potion | misc …
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    value_gp: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # JSON object for extra properties, e.g. {"damage": "1d6", "damage_type": "slashing"}
    properties: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    equipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    character: Mapped["CharacterDB"] = relationship(
        "CharacterDB", back_populates="inventory"
    )


class AbilityDB(Base):
    __tablename__ = "abilities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    character_id: Mapped[UUID] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    ability_name: Mapped[str] = mapped_column(String(200), nullable=False)
    ability_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="feature"
    )  # spell | feature | action | bonus_action | reaction
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    spell_level: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # None for non-spell abilities
    uses_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recharge: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # short_rest | long_rest | dawn | None

    character: Mapped["CharacterDB"] = relationship(
        "CharacterDB", back_populates="abilities"
    )


# ---------------------------------------------------------------------------
# DB lifecycle helpers
# ---------------------------------------------------------------------------


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
