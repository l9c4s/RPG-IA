import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from langchain.vectorstores.base import VectorStoreRetriever
from langchain_community.vectorstores import PGVector
from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import (
    get_db,
    init_db,
    CampaignDB,
    SessionDB,
    SessionMessageDB,
)
from gm_chain import build_gm_chain, get_embeddings
from models import (
    CampaignCreate,
    GMResponse,
    PlayerAction,
    RollResult,
    SessionCreate,
    StateUpdate,
)
from state_parser import parse_gm_response, roll_dice

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TTS_SERVICE_URL: str = os.getenv("TTS_SERVICE_URL", "http://localhost:8003")
IMAGE_SERVICE_URL: str = os.getenv("IMAGE_SERVICE_URL", "http://localhost:8004")
KNOWLEDGE_SERVICE_URL: str = os.getenv("KNOWLEDGE_SERVICE_URL", "http://localhost:8001")
VECTOR_DB_URL: str = os.getenv(
    "VECTOR_DB_URL",
    "postgresql+psycopg2://rpg:rpg@localhost:5432/rpg_campaign",
)
KNOWLEDGE_GATE_MIN_CHUNKS: int = int(os.getenv("KNOWLEDGE_GATE_MIN_CHUNKS", "3"))

# ---------------------------------------------------------------------------
# WebSocket connection manager (multiplayer broadcast)
# ---------------------------------------------------------------------------


class ConnectionManager:
    def __init__(self) -> None:
        # Maps session_id → list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(session_id, []).append(ws)
        logger.info("WS connected: session=%s total=%d", session_id, len(self._connections[session_id]))

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(session_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns:
            self._connections.pop(session_id, None)
        logger.info("WS disconnected: session=%s", session_id)

    async def broadcast(self, session_id: str, message: dict[str, Any]) -> None:
        conns = self._connections.get(session_id, [])
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(session_id, ws)


manager = ConnectionManager()

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Campaign/GM service started on port 8002")
    yield
    logger.info("Campaign/GM service shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RPG-IA Campaign/GM Service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_retriever() -> VectorStoreRetriever:
    """Build a PGVector retriever that searches knowledge_chunks."""
    embeddings = get_embeddings()
    store = PGVector(
        connection_string=VECTOR_DB_URL,
        embedding_function=embeddings,
        collection_name="knowledge_chunks",
    )
    return store.as_retriever(search_kwargs={"k": 8})


async def check_gate() -> bool:
    """
    Knowledge gate: ensure the vector store has at least
    KNOWLEDGE_GATE_MIN_CHUNKS documents before allowing GM turns.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{KNOWLEDGE_SERVICE_URL}/knowledge/stats")
            if resp.status_code == 200:
                data = resp.json()
                return int(data.get("total_chunks", 0)) >= KNOWLEDGE_GATE_MIN_CHUNKS
    except Exception as exc:
        logger.warning("Knowledge gate check failed: %s", exc)
    # Fail open only if the service is unreachable — prevents blocking when
    # the knowledge service is simply not deployed yet in development.
    return False


async def _fire_tts(text: str, session_id: str) -> str | None:
    """Fire-and-forget TTS request; returns the audio URL or None."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{TTS_SERVICE_URL}/tts/generate",
                json={"text": text, "session_id": session_id},
            )
            if resp.status_code == 200:
                return resp.json().get("audio_url")
    except Exception as exc:
        logger.warning("TTS dispatch failed: %s", exc)
    return None


async def _fire_image(description: str, session_id: str) -> str | None:
    """Fire-and-forget image generation request; returns the image URL or None."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{IMAGE_SERVICE_URL}/images/generate",
                json={"description": description, "session_id": session_id},
            )
            if resp.status_code == 200:
                return resp.json().get("image_url")
    except Exception as exc:
        logger.warning("Image generation dispatch failed: %s", exc)
    return None


async def _save_message(
    db: AsyncSession,
    *,
    session_id: UUID,
    role: str,
    content: str,
    player_id: UUID | None = None,
    character_id: UUID | None = None,
) -> None:
    stmt = insert(SessionMessageDB).values(
        id=uuid4(),
        session_id=session_id,
        role=role,
        content=content,
        player_id=player_id,
        character_id=character_id,
    )
    await db.execute(stmt)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/session/action", response_model=GMResponse, status_code=status.HTTP_200_OK)
async def session_action(
    payload: PlayerAction,
    db: AsyncSession = Depends(get_db),
) -> GMResponse:
    """
    Main GM turn endpoint.

    1. Check knowledge gate.
    2. Embed player action and retrieve top-8 knowledge chunks.
    3. Call the GM chain (streaming internally, collected here).
    4. Parse [ROLAGEM], [ESTADO], [IMAGEM] tags.
    5. Persist player + GM messages.
    6. Dispatch TTS and image generation asynchronously.
    7. Return structured GMResponse.
    """
    # 1 — Knowledge gate
    gate_open = await check_gate()
    if not gate_open:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="O GM ainda não tem conhecimento suficiente. Envie PDFs de RPG primeiro.",
        )

    # 2 — Validate session exists
    session_row = await db.get(SessionDB, payload.session_id)
    if session_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sessão não encontrada.",
        )

    # 3 — Build retriever + GM chain and invoke
    try:
        retriever = _get_retriever()
        chain = build_gm_chain(retriever)
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: chain({"question": payload.action_text}),
        )
        raw_gm_text: str = result.get("answer", "")
    except Exception as exc:
        logger.exception("GM chain error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar a ação com o GM.",
        )

    # 4 — Parse tags
    parsed = parse_gm_response(raw_gm_text)
    clean_text: str = parsed["clean_text"]
    actions: list[dict[str, Any]] = parsed["actions"]

    roll_results: list[RollResult] = []
    state_updates: list[StateUpdate] = []
    image_description: str | None = None

    for action in actions:
        if action["type"] == "roll":
            try:
                roll = roll_dice(action["expr"])
                roll_results.append(
                    RollResult(
                        expr=roll["expr"],
                        result=roll["result"],
                        breakdown=roll["breakdown"],
                    )
                )
            except ValueError as exc:
                logger.warning("Dice parse error: %s", exc)

        elif action["type"] == "state":
            state_updates.append(
                StateUpdate(field=action["field"], value=action["value"])
            )

        elif action["type"] == "image":
            image_description = action["description"]

    # 5 — Persist messages
    await _save_message(
        db,
        session_id=payload.session_id,
        role="player",
        content=payload.action_text,
        player_id=payload.player_id,
        character_id=payload.character_id,
    )
    await _save_message(
        db,
        session_id=payload.session_id,
        role="gm",
        content=raw_gm_text,
    )

    # 6 — Fire-and-forget media generation
    session_id_str = str(payload.session_id)
    tts_task = asyncio.create_task(_fire_tts(clean_text, session_id_str))
    image_task = (
        asyncio.create_task(_fire_image(image_description, session_id_str))
        if image_description
        else None
    )

    # Broadcast to WebSocket listeners (non-blocking)
    asyncio.create_task(
        manager.broadcast(
            session_id_str,
            {
                "type": "gm_response",
                "text": clean_text,
                "roll_results": [r.model_dump() for r in roll_results],
                "state_updates": [s.model_dump() for s in state_updates],
            },
        )
    )

    # Collect media URLs with a short timeout so the HTTP response stays fast
    audio_url: str | None = None
    image_url: str | None = None
    try:
        audio_url = await asyncio.wait_for(asyncio.shield(tts_task), timeout=2.0)
    except (asyncio.TimeoutError, Exception):
        pass

    if image_task:
        try:
            image_url = await asyncio.wait_for(asyncio.shield(image_task), timeout=2.0)
        except (asyncio.TimeoutError, Exception):
            pass

    return GMResponse(
        text=clean_text,
        roll_results=roll_results,
        state_updates=state_updates,
        image_url=image_url,
        audio_url=audio_url,
    )


# ---------------------------------------------------------------------------
# WebSocket — real-time multiplayer
# ---------------------------------------------------------------------------


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(session_id: str, ws: WebSocket) -> None:
    """
    WebSocket endpoint for real-time multiplayer.

    Clients connect here and receive broadcasts of player actions and
    GM responses as they happen. Clients may also send JSON messages
    which are broadcast to all other participants in the same session.
    """
    await manager.connect(session_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            # Annotate inbound message with session context and broadcast
            data["session_id"] = session_id
            await manager.broadcast(session_id, data)
    except WebSocketDisconnect:
        manager.disconnect(session_id, ws)
    except Exception as exc:
        logger.warning("WS error session=%s: %s", session_id, exc)
        manager.disconnect(session_id, ws)


# ---------------------------------------------------------------------------
# Campaign routes
# ---------------------------------------------------------------------------


@app.post("/campaigns", status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new campaign."""
    campaign = CampaignDB(
        id=uuid4(),
        title=payload.title,
        description=payload.description,
        rpg_system=payload.rpg_system,
        difficulty=payload.difficulty,
        tone=payload.tone,
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)
    return {
        "id": str(campaign.id),
        "title": campaign.title,
        "description": campaign.description,
        "rpg_system": campaign.rpg_system,
        "difficulty": campaign.difficulty,
        "tone": campaign.tone,
        "created_at": campaign.created_at.isoformat(),
    }


@app.get("/campaigns/{campaign_id}", status_code=status.HTTP_200_OK)
async def get_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get campaign details by ID."""
    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada.",
        )
    return {
        "id": str(campaign.id),
        "title": campaign.title,
        "description": campaign.description,
        "rpg_system": campaign.rpg_system,
        "difficulty": campaign.difficulty,
        "tone": campaign.tone,
        "created_at": campaign.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Session routes
# ---------------------------------------------------------------------------


@app.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Start a new game session for an existing campaign."""
    campaign = await db.get(CampaignDB, payload.campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada.",
        )

    session = SessionDB(id=uuid4(), campaign_id=payload.campaign_id)
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return {
        "id": str(session.id),
        "campaign_id": str(session.campaign_id),
        "started_at": session.started_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "campaign"}
