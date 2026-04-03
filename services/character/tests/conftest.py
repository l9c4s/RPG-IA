"""Shared fixtures for all test layers (unit, integration, e2e)."""
from __future__ import annotations

import os
import sys

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Make service root importable from any test subdirectory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.character.entity import Character, CharacterAttributes
from infrastructure.database.connection import get_db
from infrastructure.database.orm_models import Base
from presentation.main import create_app

# ---------------------------------------------------------------------------
# Test database URL
# ---------------------------------------------------------------------------

TEST_DB_URL = (
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://rpg_user:change_me_strong_password@localhost:5432/rpg_platform",
    )
    .replace("@postgres:", "@localhost:")
    .replace("/rpg_platform", "/rpg_test")
)

# ---------------------------------------------------------------------------
# Shared payload (reusable across e2e and integration)
# ---------------------------------------------------------------------------

CHARACTER_PAYLOAD = {
    "name": "Aragorn",
    "race": "Human",
    "class": "Ranger",
    "level": 1,
    "char_type": "player",
    "alignment": "Lawful Good",
    "campaign_id": "550e8400-e29b-41d4-a716-446655440000",
    "owner_id": "550e8400-e29b-41d4-a716-446655440099",
    "attributes": {
        "strength": 15,
        "dexterity": 14,
        "constitution": 13,
        "intelligence": 12,
        "wisdom": 10,
        "charisma": 8,
        "armor_class": 12,
        "initiative": 2,
        "speed": 30,
    },
}


# ---------------------------------------------------------------------------
# Database fixtures (integration + e2e)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Isolated DB session — drops and recreates all tables per test function."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async with factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


# ---------------------------------------------------------------------------
# ASGI HTTP client fixture (e2e)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """Full ASGI client with DB override — used for E2E tests."""

    async def override_get_db():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Convenience fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def created_character(client):
    """Creates a character via HTTP and returns the JSON response."""
    r = await client.post("/characters", json=CHARACTER_PAYLOAD)
    assert r.status_code == 201
    return r.json()


@pytest_asyncio.fixture
async def sample_character():
    """Domain Character entity ready to be saved by the repository."""
    char = Character.create(
        name="Aragorn",
        race="Human",
        class_="Ranger",
        level=1,
    )
    char.attributes = CharacterAttributes.create_default(
        char.id,
        strength=15,
        dexterity=14,
        constitution=13,
        intelligence=12,
        wisdom=10,
        charisma=8,
        armor_class=12,
        initiative=2,
        speed=30,
    )
    return char
