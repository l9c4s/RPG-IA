import pytest
import pytest_asyncio
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import Base, get_db
from main import app

TEST_DB_URL = (
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://rpg_user:change_me_strong_password@localhost:5432/rpg_platform"
    )
    .replace("@postgres:", "@localhost:")
    .replace("/rpg_platform", "/rpg_test")
)

FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf content for testing"

EXTRA_DDL = """
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
        ARRAY_AGG(DISTINCT rpg_system) FILTER (WHERE rpg_system IS NOT NULL) AS systems_covered,
        0::bigint AS total_sources,
        0::bigint AS processing_count
    FROM knowledge_chunks;
"""


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # Drop extra objects too
        await conn.execute(text("DROP VIEW IF EXISTS v_knowledge_status CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS knowledge_chunks CASCADE"))
        await conn.run_sync(Base.metadata.create_all)
        # Create knowledge_chunks and view that depend on pdf_sources
        for stmt in EXTRA_DDL.strip().split(";"):
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


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    mock_minio = MagicMock()
    mock_minio.bucket_exists.return_value = True
    mock_minio.put_object.return_value = None

    mock_task = MagicMock()
    mock_task.delay.return_value = MagicMock(id="task-123")

    app.dependency_overrides[get_db] = override_get_db

    with patch("main.minio_client", mock_minio), \
         patch("main.process_pdf", mock_task):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()
