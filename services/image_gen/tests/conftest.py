"""Shared fixtures for all test layers."""
from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from infrastructure.database.connection import get_db
from infrastructure.database.orm_models import Base
from presentation.dependencies import get_dalle, get_minio
from presentation.main import create_app

TEST_DB_URL = (
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://rpg_user:change_me_strong_password@localhost:5432/rpg_platform",
    )
    .replace("@postgres:", "@localhost:")
    .replace("/rpg_platform", "/rpg_test")
)

_FAKE_BYTES = b"\x89PNG\r\n\x1a\n"
_FAKE_URL = "/media/images/fake-image.png"


# ---------------------------------------------------------------------------
# DB session (integration + E2E)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# Fake adapters (avoid real DALL-E / MinIO calls in E2E)
# ---------------------------------------------------------------------------


def _fake_dalle():
    mock = AsyncMock()
    mock.generate.return_value = _FAKE_BYTES
    return mock


def _fake_minio():
    mock = AsyncMock()
    mock.upload.return_value = _FAKE_URL
    mock.ensure_bucket.return_value = None
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
    app.dependency_overrides[get_dalle] = _fake_dalle
    app.dependency_overrides[get_minio] = _fake_minio

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
