import os
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
import jwt as pyjwt
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
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
from gm_chain import build_gm_chain, get_embeddings, generate_opening_narrative, generate_companion_reaction
from models import (
    CampaignCreate,
    CampaignStatusUpdate,
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

TTS_SERVICE_URL: str = os.getenv("TTS_SERVICE_URL", "http://tts_service:8005")
IMAGE_SERVICE_URL: str = os.getenv("IMAGE_SERVICE_URL", "http://image_service:8004")
KNOWLEDGE_SERVICE_URL: str = os.getenv("KNOWLEDGE_SERVICE_URL", "http://pdf_service:8001")
CHARACTER_SERVICE_URL: str = os.getenv("CHARACTER_SERVICE_URL", "http://character_service:8003")
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


async def _fetch_campaign_characters(campaign_id: UUID) -> list[dict[str, Any]]:
    characters: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{CHARACTER_SERVICE_URL}/campaigns/{campaign_id}/characters"
            )
            if resp.status_code == 200:
                characters = resp.json()
            else:
                logger.error(
                    "Character service returned %s for campaign=%s",
                    resp.status_code,
                    campaign_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Não foi possível validar os personagens da campanha.",
                )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Falha ao contactar serviço de personagens: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de personagens indisponível.",
        )
    return characters


# ---------------------------------------------------------------------------
# Opening-flow orchestrator (runs as a background asyncio task)
# ---------------------------------------------------------------------------


async def _get_knowledge_context(question: str) -> str:
    """Fetch a small RAG context snippet; returns empty string on any failure."""
    try:
        retriever = _get_retriever()
        docs = await asyncio.get_event_loop().run_in_executor(
            None, lambda: retriever.invoke(question)
        )
        return "\n\n".join(d.page_content for d in docs[:4])
    except Exception as exc:
        logger.warning("Knowledge context fetch failed: %s", exc)
        return ""


async def _run_opening_flow(campaign_id: UUID, session_id: UUID) -> None:
    """
    Background task: generate opening narrative and map for a new session.

    Uses its own AsyncSessionLocal so it outlives the HTTP request scope.
    init_status progression: idle → generating → ready | failed
    """
    from database import AsyncSessionLocal as _DBSession

    async with _DBSession() as db:
        try:
            campaign = await db.get(CampaignDB, campaign_id)
            if campaign is None:
                return

            # Guard against double-trigger
            if campaign.init_status == "generating":
                return

            campaign.init_status = "generating"
            await db.commit()

            characters = await _fetch_campaign_characters(campaign_id)
            query = f"{campaign.title} {campaign.rpg_system} {campaign.description or ''}"
            knowledge_ctx = await _get_knowledge_context(query)

            campaign_dict = {
                "title":       campaign.title,
                "rpg_system":  campaign.rpg_system,
                "description": campaign.description,
                "tone":        campaign.tone,
                "difficulty":  campaign.difficulty,
            }

            # Generate opening narrative
            opening_text = await generate_opening_narrative(
                campaign=campaign_dict,
                characters=characters,
                knowledge_context=knowledge_ctx,
            )

            # Persist opening as first GM message in the session
            await _save_message(
                db,
                session_id=session_id,
                role="gm_opening",
                content=opening_text,
            )

            # Generate map if not already present
            if not campaign.locations_json:
                llm = ChatOpenAI(model="gpt-4o", temperature=0.85)
                map_prompt = (
                    f"You are a fantasy world builder for a tabletop RPG campaign.\n"
                    f'Campaign: "{campaign.title}"\nSystem: {campaign.rpg_system}\n'
                    f"Description: {campaign.description or 'A classic adventure'}\n"
                    f"Tone: {campaign.tone}\n\n"
                    f"Create exactly 6 distinct locations. Return ONLY a valid JSON array "
                    f"with 6 objects: id (loc_1…), name, description, x (5-95), y (5-95), "
                    f'type (city/dungeon/wilderness/landmark/unknown), '
                    f"is_current (true only for first), discovered (true for first 2)."
                )
                result = await asyncio.to_thread(llm.invoke, map_prompt)
                raw = result.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                campaign.locations_json = raw

            campaign.opening_generated = True
            campaign.init_status = "ready"
            await db.commit()
            logger.info("Opening flow complete for campaign=%s session=%s", campaign_id, session_id)

        except Exception as exc:
            logger.exception("Opening flow failed campaign=%s: %s", campaign_id, exc)
            try:
                campaign = await db.get(CampaignDB, campaign_id)
                if campaign:
                    campaign.init_status = "failed"
                    await db.commit()
            except Exception:
                pass


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

    # 5b — AI companion reactions (fire-and-forget, max 2 companions)
    async def _react_and_broadcast(companion: dict[str, Any]) -> None:
        try:
            reaction = await generate_companion_reaction(
                companion=companion,
                gm_text=clean_text,
                player_action=payload.action_text,
            )
            from database import AsyncSessionLocal as _DBSession
            async with _DBSession() as rdb:
                await _save_message(
                    rdb,
                    session_id=payload.session_id,
                    role="ai_companion",
                    content=reaction,
                    character_id=UUID(str(companion["id"])) if companion.get("id") else None,
                )
                await rdb.commit()
            await manager.broadcast(
                session_id_str,
                {
                    "type":           "companion_reaction",
                    "companion_name": companion.get("name", "Companion"),
                    "text":           reaction,
                    "character_id":   str(companion.get("id", "")),
                },
            )
        except Exception as exc:
            logger.warning("Companion reaction failed for %s: %s", companion.get("name"), exc)

    try:
        session_row_for_campaign = await db.get(SessionDB, payload.session_id)
        if session_row_for_campaign:
            companions_resp = await _fetch_campaign_characters(session_row_for_campaign.campaign_id)
            ai_companions = [c for c in companions_resp if c.get("char_type") == "ai_companion"][:2]
            for companion in ai_companions:
                asyncio.create_task(_react_and_broadcast(companion))
    except Exception as exc:
        logger.warning("Could not schedule companion reactions: %s", exc)

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


@app.websocket("/ws/session/{session_id}/player/{player_id}")
async def websocket_endpoint(
    session_id: str,
    player_id: str,
    ws: WebSocket,
    token: str = Query(...),
) -> None:
    """
    WebSocket endpoint for real-time multiplayer.

    Clients connect here and receive broadcasts of player actions and
    GM responses as they happen. Clients may also send JSON messages
    which are broadcast to all other participants in the same session.
    """
    # Validate JWT token
    jwt_secret = os.getenv("JWT_SECRET", "")
    try:
        pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
    except pyjwt.PyJWTError:
        await ws.close(code=4001)
        return

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


@app.get("/campaigns", status_code=status.HTTP_200_OK)
async def list_campaigns(db: AsyncSession = Depends(get_db)) -> list[dict[str, Any]]:
    """Lista todas as campanhas."""
    from sqlalchemy import select as sa_select
    result = await db.execute(sa_select(CampaignDB).order_by(CampaignDB.created_at.desc()))
    campaigns = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "description": c.description,
            "rpg_system": c.rpg_system,
            "difficulty": c.difficulty,
            "tone": c.tone,
            "status": c.status,
            "created_at": c.created_at.isoformat(),
            "updated_at": getattr(c, "updated_at", c.created_at).isoformat(),
        }
        for c in campaigns
    ]


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
        status="lobby",
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
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": getattr(campaign, "updated_at", campaign.created_at).isoformat(),
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
        "status": campaign.status,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": getattr(campaign, "updated_at", campaign.created_at).isoformat(),
    }


# ---------------------------------------------------------------------------
# Lobby endpoints
# ---------------------------------------------------------------------------


@app.get("/campaigns/{campaign_id}/lobby", status_code=status.HTTP_200_OK)
async def get_lobby(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retorna o estado do lobby: campanha + personagens + se pode iniciar."""
    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")

    characters: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{CHARACTER_SERVICE_URL}/campaigns/{campaign_id}/characters"
            )
            if resp.status_code == 200:
                characters = resp.json()
    except Exception:
        pass  # character service unavailable — lobby still loads

    return {
        "campaign": {
            "id": str(campaign.id),
            "title": campaign.title,
            "description": campaign.description,
            "rpg_system": campaign.rpg_system,
            "difficulty": campaign.difficulty,
            "status": campaign.status,
            "created_at": campaign.created_at.isoformat(),
            "updated_at": getattr(campaign, "updated_at", campaign.created_at).isoformat(),
        },
        "characters": characters,
        "can_start": len(characters) >= 2,
    }


@app.patch("/campaigns/{campaign_id}/status", status_code=status.HTTP_200_OK)
async def update_campaign_status(
    campaign_id: UUID,
    payload: CampaignStatusUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Altera o status da campanha. Para 'active', valida >= 2 personagens."""
    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")

    if payload.status == "active":
        characters = await _fetch_campaign_characters(campaign_id)
        if len(characters) < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="É necessário pelo menos 1 personagem para ativar a campanha.",
            )

    campaign.status = payload.status
    await db.commit()
    await db.refresh(campaign)
    return {"id": str(campaign.id), "status": campaign.status}


# AI archetypes for auto-generated companions
_AI_ARCHETYPES = [
    {"name": "Aria", "class": "Bard", "race": "Half-Elf", "personality": "Curious and witty, loves stories and lore", "backstory": "A wandering bard collecting tales from across the realms."},
    {"name": "Gorak", "class": "Barbarian", "race": "Half-Orc", "personality": "Fierce but loyal, speaks little and acts much", "backstory": "A former gladiator seeking redemption through honorable battle."},
    {"name": "Sylvara", "class": "Wizard", "race": "Elf", "personality": "Analytical and cautious, always planning ahead", "backstory": "An elven scholar banished from her tower for forbidden research."},
    {"name": "Brother Aldric", "class": "Cleric", "race": "Human", "personality": "Compassionate and devout, never abandons the wounded", "backstory": "A traveling healer ministering to those caught between wars."},
    {"name": "Nimble", "class": "Rogue", "race": "Halfling", "personality": "Cheerful and opportunistic, trouble finds them naturally", "backstory": "A former street thief turned reluctant adventurer."},
]


@app.post("/campaigns/{campaign_id}/ai-player", status_code=status.HTTP_201_CREATED)
async def add_ai_player(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Adiciona um companheiro de IA à campanha."""
    import random

    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")

    archetype = random.choice(_AI_ARCHETYPES)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{CHARACTER_SERVICE_URL}/characters",
                json={
                    "name": archetype["name"],
                    "class": archetype["class"],
                    "race": archetype["race"],
                    "char_type": "ai_companion",
                    "backstory": archetype["backstory"],
                    "campaign_id": str(campaign_id),
                    "level": 1,
                },
            )
            if resp.status_code not in (200, 201):
                raise HTTPException(status_code=500, detail="Falha ao criar personagem de IA.")
            return resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao adicionar IA: {exc}")


# ---------------------------------------------------------------------------
# 8-bit character generation
# ---------------------------------------------------------------------------


class Generate8BitCharacterRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)


class Generated8BitCharacter(BaseModel):
    name: str
    race: str
    character_class: str = Field(alias="class")
    alignment: str
    background: str
    appearance: str
    backstory: str
    pixel_art_prompt: str

    model_config = {"populate_by_name": True}


@app.post(
    "/campaigns/{campaign_id}/generate-character-8bit",
    response_model=Generated8BitCharacter,
    status_code=status.HTTP_200_OK,
    summary="Gerar personagem 8-bit via LangChain",
)
async def generate_character_8bit(
    campaign_id: UUID,
    payload: Generate8BitCharacterRequest,
    db: AsyncSession = Depends(get_db),
) -> Generated8BitCharacter:
    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")

    prompt = (
        "You are a prompt engineer for 8-bit pixel art RPG characters. "
        "Convert the short description below into a compact character concept and a DALL-E prompt. "
        "Return ONLY valid JSON with these fields: name, race, class, alignment, background, appearance, backstory, pixel_art_prompt. "
        "Do not add any explanation, markdown or extra text.\n\n"
        f"Description: {payload.description}"
    )

    llm = ChatOpenAI(model="gpt-4o", temperature=0.8)
    try:
        result = await asyncio.to_thread(llm.invoke, prompt)
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            trimmed = raw[raw.find("{"): raw.rfind("}") + 1]
            parsed = json.loads(trimmed)
    except Exception as exc:
        logger.exception("Falha ao gerar personagem 8-bit: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar a descrição 8-bit do personagem. Tente novamente.",
        )

    return Generated8BitCharacter.model_validate(parsed)


# ---------------------------------------------------------------------------
# Map generation
# ---------------------------------------------------------------------------


@app.post("/campaigns/{campaign_id}/generate-map", status_code=status.HTTP_200_OK)
async def generate_map(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Gera 6 locais para o mapa da campanha usando GPT-4o e salva no banco.
    Requer pelo menos 1 personagem criado.
    Ao final, seta o status da campanha para 'active'.
    """
    import json

    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")

    # Valida que há pelo menos 1 personagem
    char_count = 0
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{CHARACTER_SERVICE_URL}/campaigns/{campaign_id}/characters")
            if resp.status_code == 200:
                char_count = len(resp.json())
    except Exception:
        pass  # se o serviço estiver indisponível, libera

    if char_count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crie pelo menos 1 personagem antes de gerar o mapa.",
        )

    # Gera locais com GPT-4o via LangChain
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(model="gpt-4o", temperature=0.85)

    prompt = (
        f"You are a fantasy world builder for a tabletop RPG campaign.\n"
        f"Campaign: \"{campaign.title}\"\n"
        f"System: {campaign.rpg_system}\n"
        f"Description: {campaign.description or 'A classic adventure'}\n"
        f"Tone: {campaign.tone}\n\n"
        f"Create exactly 6 distinct, interesting locations for this campaign world.\n"
        f"Return ONLY a valid JSON array — no markdown, no extra text — with 6 objects, each containing:\n"
        f'  "id": unique string like "loc_1",\n'
        f'  "name": evocative location name,\n'
        f'  "description": 1-2 sentence description,\n'
        f'  "x": number 5-95 (horizontal position on map),\n'
        f'  "y": number 5-95 (vertical position on map),\n'
        f'  "type": one of "city", "dungeon", "wilderness", "landmark", "unknown",\n'
        f'  "is_current": true only for the first location,\n'
        f'  "discovered": true for the first 2 locations, false for the rest.\n'
        f"Spread locations across the full map area. Vary location types."
    )

    try:
        result = await asyncio.to_thread(llm.invoke, prompt)
        raw = result.content.strip()
        # remove possível bloco markdown
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        locations: list[dict] = json.loads(raw)
    except Exception as exc:
        logger.exception("Falha ao gerar mapa: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar o mapa da campanha. Tente novamente.",
        )

    campaign.locations_json = json.dumps(locations)
    campaign.status = "active"
    await db.commit()

    return {"locations": locations}


@app.get("/campaigns/{campaign_id}/locations", status_code=status.HTTP_200_OK)
async def get_locations(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retorna os locais gerados para o mapa da campanha."""
    import json

    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")

    if not campaign.locations_json:
        return []

    return json.loads(campaign.locations_json)


# ---------------------------------------------------------------------------
# Delete campaign
# ---------------------------------------------------------------------------


@app.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Apaga uma campanha e todas as sessões e mensagens relacionadas."""
    from sqlalchemy import delete as sa_delete, select as sa_select

    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada.",
        )

    # Apaga mensagens → sessões → campanha (respeita FK)
    sessions_result = await db.execute(
        sa_select(SessionDB).where(SessionDB.campaign_id == campaign_id)
    )
    session_ids = [s.id for s in sessions_result.scalars().all()]

    if session_ids:
        await db.execute(
            sa_delete(SessionMessageDB).where(SessionMessageDB.session_id.in_(session_ids))
        )
        await db.execute(
            sa_delete(SessionDB).where(SessionDB.campaign_id == campaign_id)
        )

    await db.delete(campaign)
    await db.commit()


# ---------------------------------------------------------------------------
# Session routes
# ---------------------------------------------------------------------------


@app.get("/campaigns/{campaign_id}/sessions/current", status_code=status.HTTP_200_OK)
async def get_current_session(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Retorna a sessão mais recente + init_status da campanha, ou 404 se não houver sessão."""
    from sqlalchemy import select as sa_select

    result = await db.execute(
        sa_select(SessionDB)
        .where(SessionDB.campaign_id == campaign_id)
        .order_by(SessionDB.started_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma sessão iniciada.")

    campaign = await db.get(CampaignDB, campaign_id)
    return {
        "id":               str(session.id),
        "campaign_id":      str(session.campaign_id),
        "started_at":       session.started_at.isoformat(),
        "init_status":      campaign.init_status if campaign else "idle",
        "has_opening":      campaign.opening_generated if campaign else False,
    }


@app.post("/campaigns/{campaign_id}/sessions/start", status_code=status.HTTP_201_CREATED)
async def start_campaign_session(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Inicia uma nova sessão. Ativa a campanha automaticamente se ainda estiver em lobby."""
    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campanha não encontrada.",
        )

    if campaign.status not in ("lobby", "active"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível iniciar uma sessão com a campanha em status '{campaign.status}'.",
        )

    characters = await _fetch_campaign_characters(campaign_id)
    if len(characters) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="É necessário pelo menos 1 personagem para iniciar a sessão.",
        )

    # Ativa a campanha automaticamente se ainda estiver em lobby
    if campaign.status == "lobby":
        campaign.status = "active"
        await db.flush()

    session = SessionDB(id=uuid4(), campaign_id=campaign_id)
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # Kick off opening narrative + map generation asynchronously.
    # _run_opening_flow creates its own DB session so it outlives this request.
    if not campaign.opening_generated:
        campaign.init_status = "generating"
        await db.flush()
        asyncio.create_task(_run_opening_flow(campaign_id, session.id))

    return {
        "id":          str(session.id),
        "campaign_id": str(session.campaign_id),
        "started_at":  session.started_at.isoformat(),
        "init_status": campaign.init_status,
        "has_opening": campaign.opening_generated,
    }


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

    if campaign.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A campanha deve estar ativa para iniciar a sessão.",
        )

    characters = await _fetch_campaign_characters(payload.campaign_id)
    if len(characters) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="É necessário pelo menos 1 personagem para iniciar a sessão.",
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
# Session messages
# ---------------------------------------------------------------------------


@app.get("/sessions/{session_id}/messages", status_code=status.HTTP_200_OK)
async def get_session_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Retorna todas as mensagens de uma sessão em ordem cronológica."""
    from sqlalchemy import select as sa_select

    result = await db.execute(
        sa_select(SessionMessageDB)
        .where(SessionMessageDB.session_id == session_id)
        .order_by(SessionMessageDB.created_at.asc())
    )
    messages = result.scalars().all()
    return [
        {
            "id":           str(m.id),
            "session_id":   str(m.session_id),
            "role":         m.role,
            "content":      m.content,
            "player_id":    str(m.player_id) if m.player_id else None,
            "character_id": str(m.character_id) if m.character_id else None,
            "created_at":   m.created_at.isoformat(),
        }
        for m in messages
    ]


# ---------------------------------------------------------------------------
# Manual generate-opening (standalone trigger, idempotent)
# ---------------------------------------------------------------------------


@app.post("/campaigns/{campaign_id}/generate-opening", status_code=status.HTTP_202_ACCEPTED)
async def trigger_generate_opening(
    campaign_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Dispara manualmente a geração da narrativa de abertura.
    Idempotente: ignora se já gerado ou já em andamento.
    Retorna o init_status atual imediatamente (geração ocorre em background).
    """
    campaign = await db.get(CampaignDB, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")

    if campaign.opening_generated:
        return {"init_status": "ready", "message": "Abertura já gerada."}

    if campaign.init_status == "generating":
        return {"init_status": "generating", "message": "Geração já em andamento."}

    # Find the latest session to attach the opening message to
    from sqlalchemy import select as sa_select
    result = await db.execute(
        sa_select(SessionDB)
        .where(SessionDB.campaign_id == campaign_id)
        .order_by(SessionDB.started_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=400,
            detail="Inicie a sessão antes de gerar a abertura.",
        )

    asyncio.create_task(_run_opening_flow(campaign_id, session.id))
    return {"init_status": "generating", "message": "Geração iniciada."}


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "campaign"}
