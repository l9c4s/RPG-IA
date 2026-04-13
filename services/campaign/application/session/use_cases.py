"""
Casos de uso de Sessão de jogo.
"""

import asyncio
import logging
from uuid import UUID

from application.session.dtos import (
    MessageDTO,
    PlayerActionDTO,
    SessionResponseDTO,
    StartSessionDTO,
)
from domain.campaign.repository import ICampaignRepository
from domain.gm.entity import GMResponse
from domain.gm.ports import IGMService, IKnowledgeRetriever
from domain.session.entity import Session, SessionMessage
from domain.session.repository import IMessageRepository, ISessionRepository
from domain.session.value_objects import MessageRole
from infrastructure.ai.state_parser import parse_gm_response
from infrastructure.external.image_client import CharacterServiceClient
from infrastructure.external.image_client import ImageClient
from infrastructure.external.tts_client import TTSClient

logger = logging.getLogger(__name__)


class StartCampaignSessionUseCase:
    """
    Inicia uma nova sessão para a campanha.
    Ativa a campanha automaticamente se ainda estiver em lobby.
    Dispara a geração de abertura + mapa em background se ainda não gerada.
    """

    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        session_repo: ISessionRepository,
        character_client: CharacterServiceClient,
    ) -> None:
        self._campaigns = campaign_repo
        self._sessions = session_repo
        self._characters = character_client

    async def execute(self, dto: StartSessionDTO) -> SessionResponseDTO:
        campaign = await self._campaigns.get_by_id(dto.campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {dto.campaign_id} não encontrada.")

        if campaign.status.value not in ("lobby", "active"):
            raise ValueError(
                f"Não é possível iniciar uma sessão com a campanha em status '{campaign.status.value}'."
            )

        characters = await self._characters.list_campaign_characters(str(dto.campaign_id))
        if len(characters) < 1:
            raise ValueError("É necessário pelo menos 1 personagem para iniciar a sessão.")

        if campaign.status.value == "lobby":
            campaign.activate()

        session = Session.create(dto.campaign_id)
        saved_session = await self._sessions.save(session)

        if not campaign.opening_generated:
            campaign.start_generating_opening()

        await self._campaigns.save(campaign)

        # Registra todos os personagens como campaign_players
        asyncio.create_task(
            self._register_players(dto.campaign_id, characters)
        )

        return SessionResponseDTO(
            id=str(saved_session.id),
            campaign_id=str(saved_session.campaign_id),
            started_at=saved_session.started_at.isoformat() if saved_session.started_at else None,
            init_status=campaign.init_status.value,
            has_opening=campaign.opening_generated,
        )

    async def _register_players(self, campaign_id: UUID, characters: list[dict]) -> None:
        """Registra personagens como campaign_players em background."""
        from infrastructure.database.connection import AsyncSessionLocal
        from infrastructure.repositories.campaign_repository import CampaignRepository
        try:
            async with AsyncSessionLocal() as db:
                repo = CampaignRepository(db)
                for char in characters:
                    char_id = char.get("id")
                    if not char_id:
                        continue
                    await repo.register_player(
                        campaign_id=campaign_id,
                        character_id=UUID(str(char_id)),
                        is_ai=char.get("char_type") == "ai_companion",
                        ai_personality=char.get("personality_traits"),
                    )
                await db.commit()
        except Exception as exc:
            logger.warning("Falha ao registrar campaign_players: %s", exc)


class GetCurrentSessionUseCase:
    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        session_repo: ISessionRepository,
    ) -> None:
        self._campaigns = campaign_repo
        self._sessions = session_repo

    async def execute(self, campaign_id: UUID) -> SessionResponseDTO:
        session = await self._sessions.get_latest_by_campaign(campaign_id)
        if session is None:
            raise ValueError("Nenhuma sessão iniciada.")

        campaign = await self._campaigns.get_by_id(campaign_id)

        return SessionResponseDTO(
            id=str(session.id),
            campaign_id=str(session.campaign_id),
            started_at=session.started_at.isoformat() if session.started_at else None,
            init_status=campaign.init_status.value if campaign else "idle",
            has_opening=campaign.opening_generated if campaign else False,
        )


class GetSessionMessagesUseCase:
    def __init__(self, message_repo: IMessageRepository) -> None:
        self._messages = message_repo

    async def execute(self, session_id: UUID) -> list[MessageDTO]:
        messages = await self._messages.list_by_session(session_id)
        return [MessageDTO(**m.to_dict()) for m in messages]


class ProcessPlayerTurnUseCase:
    """
    Caso de uso central: processa a ação de um jogador e retorna a resposta do GM.

    Fluxo:
    1. Verifica knowledge gate
    2. Valida que a sessão existe
    3. Chama o GM (LangChain RAG)
    4. Parseia tags [ROLAGEM], [ESTADO], [IMAGEM]
    5. Persiste mensagens (player + GM)
    6. Dispara reações de companheiros IA (fire-and-forget)
    7. Dispara TTS e imagem (fire-and-forget, aguarda 2s)
    8. Retorna GMResponse
    """

    def __init__(
        self,
        session_repo: ISessionRepository,
        message_repo: IMessageRepository,
        campaign_repo: ICampaignRepository,
        gm_service: IGMService,
        knowledge_retriever: IKnowledgeRetriever,
        tts_client: TTSClient,
        image_client: ImageClient,
        character_client: CharacterServiceClient,
        ws_broadcast_fn=None,
    ) -> None:
        self._sessions = session_repo
        self._messages = message_repo
        self._campaigns = campaign_repo
        self._gm = gm_service
        self._knowledge = knowledge_retriever
        self._tts = tts_client
        self._image = image_client
        self._characters = character_client
        self._ws_broadcast = ws_broadcast_fn

    async def execute(self, dto: PlayerActionDTO) -> GMResponse:
        # 1 — Knowledge gate
        gate_open = await self._knowledge.check_gate()
        if not gate_open:
            raise PermissionError(
                "O GM ainda não tem conhecimento suficiente. Envie PDFs de RPG primeiro."
            )

        # 2 — Valida sessão
        session = await self._sessions.get_by_id(dto.session_id)
        if session is None:
            raise ValueError(f"Sessão {dto.session_id} não encontrada.")

        # 3 — Chama o GM
        session_id_str = str(dto.session_id)
        raw_gm_text = await self._gm.process_turn(session_id_str, dto.action_text)

        # 4 — Parseia tags
        parsed = parse_gm_response(raw_gm_text)
        clean_text = parsed["clean_text"]
        roll_results = parsed["roll_results"]
        state_updates = parsed["state_updates"]
        image_description = parsed["image_description"]

        # 5 — Persiste mensagens
        player_msg = SessionMessage.create(
            session_id=dto.session_id,
            role=MessageRole.PLAYER,
            content=dto.action_text,
            player_id=dto.player_id,
            character_id=dto.character_id,
        )
        gm_msg = SessionMessage.create(
            session_id=dto.session_id,
            role=MessageRole.GM,
            content=raw_gm_text,
        )
        await self._messages.save(player_msg)
        await self._messages.save(gm_msg)

        # 6 — Reações de companheiros IA (fire-and-forget)
        try:
            companions_resp = await self._characters.list_campaign_characters(
                str(session.campaign_id)
            )
            ai_companions = [c for c in companions_resp if c.get("char_type") == "ai_companion"][:2]
            for companion in ai_companions:
                asyncio.create_task(
                    self._react_and_persist(companion, clean_text, dto.action_text, dto.session_id)
                )
        except Exception as exc:
            logger.warning("Não foi possível agendar reações de companheiros: %s", exc)

        # 7 — Dispara mídia (fire-and-forget, timeout 2s)
        tts_task = asyncio.create_task(self._tts.synthesize(clean_text, session_id_str))
        image_task = (
            asyncio.create_task(self._image.generate_scene(image_description, session_id_str))
            if image_description
            else None
        )

        # Broadcast WebSocket (não bloqueia)
        if self._ws_broadcast:
            asyncio.create_task(
                self._ws_broadcast(
                    session_id_str,
                    {
                        "type": "gm_response",
                        "text": clean_text,
                        "roll_results": [
                            {"expr": r.expr, "result": r.result, "breakdown": r.breakdown}
                            for r in roll_results
                        ],
                        "state_updates": [
                            {"field": s.field, "value": s.value} for s in state_updates
                        ],
                    },
                )
            )

        # Coleta URLs com timeout curto
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

    async def _react_and_persist(
        self, companion: dict, gm_text: str, player_action: str, session_id: UUID
    ) -> None:
        try:
            reaction = await self._gm.generate_companion_reaction(
                companion=companion,
                gm_text=gm_text,
                player_action=player_action,
            )
            from infrastructure.database.connection import AsyncSessionLocal
            from infrastructure.repositories.session_repository import MessageRepository

            async with AsyncSessionLocal() as db:
                repo = MessageRepository(db)
                msg = SessionMessage.create(
                    session_id=session_id,
                    role=MessageRole.AI_COMPANION,
                    content=reaction,
                    character_id=UUID(str(companion["id"])) if companion.get("id") else None,
                )
                await repo.save(msg)
                await db.commit()

            if self._ws_broadcast:
                await self._ws_broadcast(
                    str(session_id),
                    {
                        "type": "companion_reaction",
                        "companion_name": companion.get("name", "Companion"),
                        "text": reaction,
                        "character_id": str(companion.get("id", "")),
                    },
                )
        except Exception as exc:
            logger.warning("Reação de companheiro falhou para %s: %s", companion.get("name"), exc)
