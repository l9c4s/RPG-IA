"""
Casos de uso do Game Master.
"""

import json
import logging
from uuid import UUID

from application.gm.dtos import Generate8BitCharacterDTO, OpeningStatusDTO, TriggerOpeningDTO
from domain.campaign.repository import ICampaignRepository
from domain.gm.ports import IGMService, IKnowledgeRetriever
from domain.session.entity import SessionMessage
from domain.session.repository import IMessageRepository, ISessionRepository
from domain.session.value_objects import MessageRole
from infrastructure.external.image_client import CharacterServiceClient

logger = logging.getLogger(__name__)


class GenerateOpeningNarrativeUseCase:
    """
    Orquestra a geração da narrativa de abertura e mapa de uma campanha.
    Executado como background task — usa sua própria sessão de DB.

    Progressão do init_status: idle → generating → ready | failed
    """

    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        session_repo: ISessionRepository,
        message_repo: IMessageRepository,
        gm_service: IGMService,
        knowledge_retriever: IKnowledgeRetriever,
        character_client: CharacterServiceClient,
    ) -> None:
        self._campaigns = campaign_repo
        self._sessions = session_repo
        self._messages = message_repo
        self._gm = gm_service
        self._knowledge = knowledge_retriever
        self._characters = character_client

    async def execute(self, campaign_id: UUID, session_id: UUID) -> None:
        try:
            campaign = await self._campaigns.get_by_id(campaign_id)
            if campaign is None:
                return

            # Guard contra double-trigger (só pula se já concluído ou falhado)
            if campaign.opening_generated or campaign.init_status.value in ("ready", "failed"):
                return

            campaign.start_generating_opening()
            await self._campaigns.save(campaign)

            characters = await self._characters.list_campaign_characters(str(campaign_id))
            query = f"{campaign.title} {campaign.rpg_system} {campaign.description or ''}"
            knowledge_ctx = await self._knowledge.get_context(query)

            campaign_dict = {
                "title": campaign.title,
                "rpg_system": campaign.rpg_system,
                "description": campaign.description,
                "tone": campaign.tone,
                "difficulty": campaign.difficulty.value,
            }

            # Gera narrativa de abertura
            opening_text = await self._gm.generate_opening_narrative(
                campaign=campaign_dict,
                characters=characters,
                knowledge_context=knowledge_ctx,
            )

            # Persiste como primeira mensagem GM da sessão
            opening_msg = SessionMessage.create(
                session_id=session_id,
                role=MessageRole.GM_OPENING,
                content=opening_text,
            )
            await self._messages.save(opening_msg)

            # Gera mapa se ainda não existe
            if not campaign.locations_json:
                locations = await self._gm.generate_map_locations(campaign_dict)
                campaign.set_locations(json.dumps(locations))

            campaign.mark_opening_ready()
            await self._campaigns.save(campaign)

            logger.info(
                "Opening flow completo: campaign=%s session=%s", campaign_id, session_id
            )

        except Exception as exc:
            logger.exception("Opening flow falhou: campaign=%s: %s", campaign_id, exc)
            try:
                campaign = await self._campaigns.get_by_id(campaign_id)
                if campaign:
                    campaign.mark_opening_failed()
                    await self._campaigns.save(campaign)
            except Exception:
                pass


class TriggerOpeningUseCase:
    """
    Dispara manualmente a geração da abertura (idempotente).
    Retorna o status atual imediatamente; a geração ocorre em background.
    """

    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        session_repo: ISessionRepository,
    ) -> None:
        self._campaigns = campaign_repo
        self._sessions = session_repo

    async def execute(self, dto: TriggerOpeningDTO) -> OpeningStatusDTO:
        campaign = await self._campaigns.get_by_id(dto.campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {dto.campaign_id} não encontrada.")

        if campaign.opening_generated:
            return OpeningStatusDTO(init_status="ready", message="Abertura já gerada.")

        if campaign.init_status.value == "generating":
            return OpeningStatusDTO(
                init_status="generating", message="Geração já em andamento."
            )

        session = await self._sessions.get_latest_by_campaign(dto.campaign_id)
        if session is None:
            raise ValueError("Inicie a sessão antes de gerar a abertura.")

        return OpeningStatusDTO(
            init_status="generating",
            message="Geração iniciada.",
            session_id=session.id,
        )


class Generate8BitCharacterUseCase:
    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        gm_service: IGMService,
    ) -> None:
        self._campaigns = campaign_repo
        self._gm = gm_service

    async def execute(self, dto: Generate8BitCharacterDTO) -> dict:
        campaign = await self._campaigns.get_by_id(dto.campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {dto.campaign_id} não encontrada.")
        return await self._gm.generate_character_8bit(dto.description)
