"""
Configuração assíncrona do banco de dados — SQLAlchemy + asyncpg + pgvector.
Espelha o padrão do serviço gateway.
"""
import os

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

# ─── URL de conexão ───────────────────────────────────────────────────────────

POSTGRES_USER = os.getenv("POSTGRES_USER", "rpg_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.getenv("POSTGRES_DB", "rpg_platform")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

DATABASE_URL = (
    f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# ─── Engine e fábrica de sessões ──────────────────────────────────────────────

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ─── Base declarativa ─────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ─── Modelos ORM ──────────────────────────────────────────────────────────────

class PdfSource(Base):
    """Mapeamento ORM para a tabela pdf_sources."""

    __tablename__ = "pdf_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4())
    title = Column(Text, nullable=False)
    rpg_system = Column(Text, nullable=True)
    source_type = Column(Text, nullable=True)
    filename = Column(Text, nullable=False)
    minio_path = Column(Text, nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), nullable=True)
    processed = Column(Boolean, default=False, nullable=False)
    chunk_count = Column(Integer, default=0, nullable=False)
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


# ─── Injeção de dependência ───────────────────────────────────────────────────

async def get_db() -> AsyncSession:  # type: ignore[return]
    """Gerador de sessão DB para uso com FastAPI Depends()."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
