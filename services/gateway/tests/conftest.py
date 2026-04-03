"""Shared fixtures for all test layers."""
from __future__ import annotations

import os
import sys

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Make service root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from infrastructure.database.connection import get_db
from infrastructure.database.orm_models import Base
from presentation.main import create_app

TEST_DB_URL = (
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://rpg_user:change_me_strong_password@localhost:5432/rpg_platform",
    )
    .replace("@postgres:", "@localhost:")
    .replace("/rpg_platform", "/rpg_test")
)

REGISTER_PAYLOAD = {
    "username": "player01",
    "email": "player01@example.com",
    "password": "password123",
}


# ---------------------------------------------------------------------------
# DB session fixture (integration + E2E)
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
# HTTP client fixture (E2E)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Pre-registered user + auth token (E2E)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def registered_user(client: AsyncClient) -> dict:
    r = await client.post("/auth/register", json=REGISTER_PAYLOAD)
    assert r.status_code == 201, r.text
    return {**REGISTER_PAYLOAD, "id": r.json()["id"]}


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client: AsyncClient, registered_user: dict) -> dict:
    r = await client.post("/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
