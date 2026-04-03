"""Database connections — async for FastAPI, sync for Celery worker."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from .orm_models import Base

load_dotenv()

_USER = os.getenv("POSTGRES_USER", "rpg_user")
_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
_DB = os.getenv("POSTGRES_DB", "rpg_platform")
_HOST = os.getenv("POSTGRES_HOST", "postgres")
_PORT = os.getenv("POSTGRES_PORT", "5432")

# ---------------------------------------------------------------------------
# Async engine (FastAPI / asyncpg)
# ---------------------------------------------------------------------------

ASYNC_DATABASE_URL = f"postgresql+asyncpg://{_USER}:{_PASSWORD}@{_HOST}:{_PORT}/{_DB}"

engine = create_async_engine(
    ASYNC_DATABASE_URL,
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


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:  # type: ignore[return]
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Sync engine (Celery worker / psycopg2)
# ---------------------------------------------------------------------------

SYNC_DATABASE_URL = f"postgresql+psycopg2://{_USER}:{_PASSWORD}@{_HOST}:{_PORT}/{_DB}"

_sync_engine = None
_SyncSession = None


def get_sync_session():
    """Lazy-initialised sync DB session for the Celery worker."""
    global _sync_engine, _SyncSession
    if _sync_engine is None:
        _sync_engine = create_engine(
            SYNC_DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        _SyncSession = sessionmaker(bind=_sync_engine, autoflush=False, autocommit=False)
    return _SyncSession()
