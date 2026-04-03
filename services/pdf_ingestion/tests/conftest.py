"""Shared fixtures for all test layers."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from infrastructure.database.connection import get_db
from infrastructure.database.orm_models import Base
from presentation.dependencies import get_minio, get_task_queue
from presentation.main import create_app

TEST_DB_URL = (
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://rpg_user:change_me_strong_password@localhost:5432/rpg_platform",
    )
    .replace("@postgres:", "@localhost:")
    .replace("/rpg_platform", "/rpg_test")
)

# knowledge_chunks and v_knowledge_status must be created manually in tests
# because they depend on pgvector (vector column) that is not in the ORM Base.
_EXTRA_DDL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES pdf_sources(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    rpg_system TEXT,
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE OR REPLACE VIEW v_knowledge_status AS
    SELECT
        COUNT(*) AS total_chunks,
        COUNT(*) > 0 AS gm_is_ready,
        COUNT(DISTINCT rpg_system) AS total_systems,
        ARRAY_AGG(DISTINCT rpg_system) FILTER (WHERE rpg_system IS NOT NULL) AS sistemas_cobertos,
        (SELECT COUNT(*) FROM pdf_sources)::bigint AS total_sources,
        (SELECT COUNT(*) FROM pdf_sources WHERE processed = false AND error_msg IS NULL)::bigint AS processing_count
    FROM knowledge_chunks;
"""


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("DROP VIEW IF EXISTS v_knowledge_status CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS knowledge_chunks CASCADE"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _EXTRA_DDL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.execute(text("DROP VIEW IF EXISTS v_knowledge_status CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS knowledge_chunks CASCADE"))
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Fake adapters for E2E
# ---------------------------------------------------------------------------


def _fake_minio():
    mock = MagicMock()
    mock.bucket_exists.return_value = True
    mock.upload.return_value = "pdfs/fake-uuid_test.pdf"
    mock.ensure_bucket.return_value = None
    return mock


def _fake_task_queue():
    mock = MagicMock()
    mock.enqueue_pdf_processing.return_value = None
    return mock


# ---------------------------------------------------------------------------
# HTTP client (E2E)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_minio] = _fake_minio
    app.dependency_overrides[get_task_queue] = _fake_task_queue

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
