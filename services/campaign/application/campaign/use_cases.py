"""
Casos de uso de Campanha.
Cada classe encapsula uma única operação de negócio.
Dependências chegam por injeção via construtor (interfaces, não implementações).
"""

import logging
from uuid import UUID

from application.campaign.dtos import (
    AddAIPlayerDTO,
    CampaignResponseDTO,
    CreateCampaignDTO,
    GenerateMapDTO,
    LobbyResponseDTO,
    UpdateCampaignStatusDTO,
)
from domain.campaign.entity import Campaign
from domain.campaign.repository import ICampaignRepository
from domain.gm.ports import IGMService
from infrastructure.external.image_client import CharacterServiceClient, ImageClient

logger = logging.getLogger(__name__)


class LimitExceededError(ValueError):
    """Raised when a campaign resource limit is exceeded."""


def _campaign_to_response_dto(campaign: Campaign) -> CampaignResponseDTO:
    return CampaignResponseDTO(
        id=str(campaign.id),
        title=campaign.title,
        rpg_system=campaign.rpg_system,
        difficulty=campaign.difficulty.value,
        tone=campaign.tone,
        status=campaign.status.value,
        description=campaign.description,
        created_at=campaign.created_at.isoformat() if campaign.created_at else None,
        updated_at=campaign.updated_at.isoformat() if campaign.updated_at else None,
        ai_players_count=campaign.ai_players_count,
    )


class CreateCampaignUseCase:
    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        gm_service: IGMService | None = None,
        character_client: CharacterServiceClient | None = None,
    ) -> None:
        self._repo = campaign_repo
        self._gm = gm_service
        self._characters = character_client

    async def execute(self, dto: CreateCampaignDTO) -> CampaignResponseDTO:
        campaign = Campaign.create(
            title=dto.title,
            rpg_system=dto.rpg_system,
            difficulty=dto.difficulty,
            tone=dto.tone,
            description=dto.description,
            ai_players_count=dto.ai_players_count,
        )
        saved = await self._repo.save(campaign)
        response = _campaign_to_response_dto(saved)

        if dto.ai_players_count > 0 and self._gm and self._characters:
            import asyncio
            tasks = [self._gm.generate_ai_companion_archetype() for _ in range(dto.ai_players_count)]
            archetypes = await asyncio.gather(*tasks, return_exceptions=True)
            for archetype in archetypes:
                if isinstance(archetype, Exception):
                    logger.warning("Falha ao gerar arquétipo IA: %s", archetype)
                    continue
                try:
                    character = await self._characters.create_character({
                        "name": archetype["name"],
                        "class": archetype["class"],
                        "race": archetype["race"],
                        "char_type": "ai_companion",
                        "backstory": archetype["backstory"],
                        "campaign_id": str(saved.id),
                        "level": 1,
                    })
                    response.ai_players.append(character)
                except Exception as exc:
                    logger.warning("Falha ao criar personagem IA: %s", exc)

        return response


class GetCampaignUseCase:
    def __init__(self, campaign_repo: ICampaignRepository) -> None:
        self._repo = campaign_repo

    async def execute(self, campaign_id: UUID) -> CampaignResponseDTO:
        campaign = await self._repo.get_by_id(campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {campaign_id} não encontrada.")
        return _campaign_to_response_dto(campaign)


class ListCampaignsUseCase:
    def __init__(self, campaign_repo: ICampaignRepository) -> None:
        self._repo = campaign_repo

    async def execute(self) -> list[CampaignResponseDTO]:
        campaigns = await self._repo.list_all()
        return [_campaign_to_response_dto(c) for c in campaigns]


class GetLobbyUseCase:
    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        character_client: CharacterServiceClient,
    ) -> None:
        self._repo = campaign_repo
        self._characters = character_client

    async def execute(self, campaign_id: UUID) -> LobbyResponseDTO:
        campaign = await self._repo.get_by_id(campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {campaign_id} não encontrada.")

        characters: list[dict] = []
        try:
            characters = await self._characters.list_campaign_characters(str(campaign_id))
        except Exception:
            pass  # lobby carrega mesmo sem o serviço de personagens

        return LobbyResponseDTO(
            campaign=_campaign_to_response_dto(campaign),
            characters=characters,
            can_start=len(characters) >= 2,
        )


class UpdateCampaignStatusUseCase:
    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        character_client: CharacterServiceClient,
    ) -> None:
        self._repo = campaign_repo
        self._characters = character_client

    async def execute(self, dto: UpdateCampaignStatusDTO) -> CampaignResponseDTO:
        campaign = await self._repo.get_by_id(dto.campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {dto.campaign_id} não encontrada.")

        if dto.new_status == "active":
            characters = await self._characters.list_campaign_characters(str(dto.campaign_id))
            if len(characters) < 1:
                raise ValueError("É necessário pelo menos 1 personagem para ativar a campanha.")

        campaign.update_status(dto.new_status)
        saved = await self._repo.save(campaign)
        return _campaign_to_response_dto(saved)


class DeleteCampaignUseCase:
    def __init__(self, campaign_repo: ICampaignRepository) -> None:
        self._repo = campaign_repo

    async def execute(self, campaign_id: UUID) -> None:
        campaign = await self._repo.get_by_id(campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {campaign_id} não encontrada.")
        await self._repo.delete(campaign_id)


class AddAIPlayerUseCase:
    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        character_client: CharacterServiceClient,
        gm_service: IGMService,
        image_client: ImageClient | None = None,
    ) -> None:
        self._repo = campaign_repo
        self._characters = character_client
        self._gm = gm_service
        self._images = image_client

    async def execute(self, dto: AddAIPlayerDTO) -> dict:
        import asyncio

        campaign = await self._repo.get_by_id(dto.campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {dto.campaign_id} não encontrada.")

        # Valida limite baseado no que foi configurado na criação da campanha
        if campaign.ai_players_count == 0:
            raise LimitExceededError(
                "Esta campanha não foi configurada para ter companheiros IA."
            )

        existing = await self._characters.list_campaign_characters(str(dto.campaign_id))
        ai_count = sum(1 for c in existing if c.get("char_type") == "ai_companion")
        if ai_count >= campaign.ai_players_count:
            raise LimitExceededError(
                f"Limite de {campaign.ai_players_count} companheiro(s) IA atingido para esta campanha."
            )

        # Gera conceito 8-bit completo: nome, raça, classe, aparência, backstory, pixel_art_prompt
        concept = await self._gm.generate_character_8bit(
            "a unique and interesting fantasy RPG adventurer companion"
        )

        def _trunc(value: str | None, limit: int) -> str | None:
            return value[:limit] if isinstance(value, str) else value

        character = await self._characters.create_character({
            "name": _trunc(concept.get("name"), 200) or "Companion",
            "class": _trunc(concept.get("class"), 100) or "Fighter",
            "race": _trunc(concept.get("race"), 100) or "Human",
            "char_type": "ai_companion",
            "backstory": _trunc(concept.get("backstory"), 4900),
            "appearance": _trunc(concept.get("appearance"), 1900),
            "alignment": _trunc(concept.get("alignment"), 50),
            "background": _trunc(concept.get("background"), 200),
            "campaign_id": str(dto.campaign_id),
            "level": 1,
        })

        # Solicita geração de imagem — retorna image_id imediatamente (202 pending)
        pixel_prompt = concept.get("pixel_art_prompt")
        if pixel_prompt and self._images and character.get("id"):
            pending_image_id = await self._images.generate_character_image(
                description=pixel_prompt,
                character_id=str(character["id"]),
                campaign_id=str(dto.campaign_id),
            )
            if pending_image_id:
                character["pending_image_id"] = pending_image_id

        return character


class GetCampaignLocationsUseCase:
    def __init__(self, campaign_repo: ICampaignRepository) -> None:
        self._repo = campaign_repo

    async def execute(self, campaign_id: UUID) -> list[dict]:
        import json
        campaign = await self._repo.get_by_id(campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {campaign_id} não encontrada.")
        if not campaign.locations_json:
            return []
        return json.loads(campaign.locations_json)


class GenerateMapUseCase:
    def __init__(
        self,
        campaign_repo: ICampaignRepository,
        gm_service: IGMService,
        character_client: CharacterServiceClient,
    ) -> None:
        self._repo = campaign_repo
        self._gm = gm_service
        self._characters = character_client

    async def execute(self, dto: GenerateMapDTO) -> list[dict]:
        import json

        campaign = await self._repo.get_by_id(dto.campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {dto.campaign_id} não encontrada.")

        # Valida que há ao menos 1 personagem
        char_count = 0
        try:
            chars = await self._characters.list_campaign_characters(str(dto.campaign_id))
            char_count = len(chars)
        except Exception:
            pass

        if char_count < 1:
            raise ValueError("Crie pelo menos 1 personagem antes de gerar o mapa.")

        campaign_dict = {
            "title": campaign.title,
            "rpg_system": campaign.rpg_system,
            "description": campaign.description,
            "tone": campaign.tone,
        }

        locations = await self._gm.generate_map_locations(campaign_dict)

        campaign.set_locations(json.dumps(locations))
        campaign.activate()
        await self._repo.save(campaign)

        return locations
