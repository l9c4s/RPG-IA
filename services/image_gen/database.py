import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, func
from uuid import UUID, uuid4
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://rpg:rpg@localhost:5432/rpg_images",
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


class GeneratedImageDB(Base):
    __tablename__ = "generated_images"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    image_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "character" | "npc" | "scene" | "map"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_used: Mapped[str] = mapped_column(Text, nullable=False)
    minio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    character_id: Mapped[UUID | None] = mapped_column(nullable=True)
    campaign_id: Mapped[UUID | None] = mapped_column(nullable=True)
    location_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
