import pytest
import pytest_asyncio
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import database
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


@pytest_asyncio.fixture(scope="function")
async def client():
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

    # Patch module-level AsyncSessionLocal so get_db uses our test factory
    original_factory = database.AsyncSessionLocal
    database.AsyncSessionLocal = factory

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    database.AsyncSessionLocal = original_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def created_character(client):
    r = await client.post("/characters", json=CHARACTER_PAYLOAD)
    assert r.status_code == 201
    return r.json()
