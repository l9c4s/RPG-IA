"""
Tests for the campaign / GM service.

Run with:
    docker compose exec campaign_service python -m pytest test_campaign.py -v
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from main import app
import database as db_module

# ---------------------------------------------------------------------------
# pytest-asyncio config
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def campaign_id() -> str:
    return str(uuid4())


@pytest.fixture
def session_id() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# Helper: build a minimal mock CampaignDB / SessionDB
# ---------------------------------------------------------------------------

def _mock_campaign(campaign_id, status="lobby", init_status="idle", opening_generated=False):
    c = MagicMock()
    c.id = campaign_id
    c.title = "Test Campaign"
    c.description = "A test adventure"
    c.rpg_system = "D&D 5e"
    c.difficulty = "medium"
    c.tone = "heroic"
    c.status = status
    c.init_status = init_status
    c.opening_generated = opening_generated
    c.locations_json = None
    c.created_at = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    c.updated_at = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    return c


def _mock_session(session_id, campaign_id):
    s = MagicMock()
    s.id = session_id
    s.campaign_id = campaign_id
    s.started_at = MagicMock(isoformat=lambda: "2024-01-01T00:00:00")
    return s


# ---------------------------------------------------------------------------
# Dependency override helper
# ---------------------------------------------------------------------------

def _override_db(mock_db):
    """Return a FastAPI dependency that yields mock_db."""
    async def _dep():
        yield mock_db
    return _dep


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# GET /campaigns/{id}/sessions/current
# ---------------------------------------------------------------------------

async def test_get_current_session_not_found(campaign_id):
    """Returns 404 when no session exists."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=lambda: None)
    )
    mock_db.get = AsyncMock(return_value=_mock_campaign(campaign_id))

    app.dependency_overrides[db_module.get_db] = _override_db(mock_db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/campaigns/{campaign_id}/sessions/current")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 404


async def test_get_current_session_returns_init_status(campaign_id, session_id):
    """Returns init_status and has_opening alongside the session info."""
    mock_session = _mock_session(session_id, campaign_id)
    mock_campaign = _mock_campaign(campaign_id, init_status="ready", opening_generated=True)

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=lambda: mock_session)
    )
    mock_db.get = AsyncMock(return_value=mock_campaign)

    app.dependency_overrides[db_module.get_db] = _override_db(mock_db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/campaigns/{campaign_id}/sessions/current")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["init_status"] == "ready"
    assert data["has_opening"] is True


# ---------------------------------------------------------------------------
# POST /campaigns/{id}/sessions/start — character guard
# ---------------------------------------------------------------------------

async def test_start_session_requires_characters(campaign_id):
    """Cannot start session without at least 1 character."""
    mock_campaign = _mock_campaign(campaign_id, status="lobby")
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_campaign)

    app.dependency_overrides[db_module.get_db] = _override_db(mock_db)
    try:
        with patch("main._fetch_campaign_characters", new_callable=AsyncMock, return_value=[]):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(f"/campaigns/{campaign_id}/sessions/start")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 400
    assert "personagem" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /campaigns/{id}/generate-opening — idempotency
# ---------------------------------------------------------------------------

async def test_generate_opening_already_done(campaign_id):
    """Returns immediately if opening already generated."""
    mock_campaign = _mock_campaign(campaign_id, opening_generated=True)
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_campaign)

    app.dependency_overrides[db_module.get_db] = _override_db(mock_db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/campaigns/{campaign_id}/generate-opening")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 202
    assert resp.json()["init_status"] == "ready"


async def test_generate_opening_already_generating(campaign_id):
    """Returns 'generating' status if already in progress."""
    mock_campaign = _mock_campaign(campaign_id, init_status="generating")
    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_campaign)

    app.dependency_overrides[db_module.get_db] = _override_db(mock_db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/campaigns/{campaign_id}/generate-opening")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 202
    assert resp.json()["init_status"] == "generating"


# ---------------------------------------------------------------------------
# GET /sessions/{id}/messages
# ---------------------------------------------------------------------------

async def test_get_session_messages_empty(session_id):
    """Returns empty list when no messages."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalars=lambda: MagicMock(all=lambda: []))
    )

    app.dependency_overrides[db_module.get_db] = _override_db(mock_db)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/sessions/{session_id}/messages")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# gm_chain: generate_opening_narrative
# ---------------------------------------------------------------------------

async def test_generate_opening_narrative_returns_string():
    from gm_chain import generate_opening_narrative

    mock_result = MagicMock()
    mock_result.content = "You stand at the gates of a ruined city…"

    with patch("gm_chain.ChatOpenAI") as MockLLM:
        MockLLM.return_value.invoke = MagicMock(return_value=mock_result)
        result = await generate_opening_narrative(
            campaign={
                "title": "Test", "rpg_system": "D&D 5e",
                "description": None, "tone": "heroic", "difficulty": "medium",
            },
            characters=[{"name": "Aria", "level": 1, "character_class": "Bard", "race": "Half-Elf"}],
            knowledge_context="Some lore context.",
        )

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# gm_chain: generate_companion_reaction
# ---------------------------------------------------------------------------

async def test_generate_companion_reaction_returns_string():
    from gm_chain import generate_companion_reaction

    mock_result = MagicMock()
    mock_result.content = "Aria strums her lute nervously."

    with patch("gm_chain.ChatOpenAI") as MockLLM:
        MockLLM.return_value.invoke = MagicMock(return_value=mock_result)
        result = await generate_companion_reaction(
            companion={
                "name": "Aria", "character_class": "Bard",
                "race": "Half-Elf", "personality_traits": "Curious",
            },
            gm_text="The dragon roars from the mountaintop.",
            player_action="I charge at the dragon!",
        )

    assert isinstance(result, str)
    assert len(result) > 0
