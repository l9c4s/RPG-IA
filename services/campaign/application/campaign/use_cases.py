"""
Casos de uso de Campanha.
Cada classe encapsula uma única operação de negócio.
Dependências chegam por injeção via construtor (interfaces, não implementações).
"""

import logging
import random
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
from infrastructure.external.image_client import CharacterServiceClient

logger = logging.getLogger(__name__)

# Arquétipos disponíveis para companheiros de IA
_AI_ARCHETYPES = [
    {
        "name": "Aria",
        "class": "Bard",
        "race": "Half-Elf",
        "personality": "Curious and witty, loves stories and lore",
        "backstory": "A wandering bard collecting tales from across the realms.",
    },
    {
        "name": "Gorak",
        "class": "Barbarian",
        "race": "Half-Orc",
        "personality": "Fierce but loyal, speaks little and acts much",
        "backstory": "A former gladiator seeking redemption through honorable battle.",
    },
    {
        "name": "Sylvara",
        "class": "Wizard",
        "race": "Elf",
        "personality": "Analytical and cautious, always planning ahead",
        "backstory": "An elven scholar banished from her tower for forbidden research.",
    },
    {
        "name": "Brother Aldric",
        "class": "Cleric",
        "race": "Human",
        "personality": "Compassionate and devout, never abandons the wounded",
        "backstory": "A traveling healer ministering to those caught between wars.",
    },
    {
        "name": "Nimble",
        "class": "Rogue",
        "race": "Halfling",
        "personality": "Cheerful and opportunistic, trouble finds them naturally",
        "backstory": "A former street thief turned reluctant adventurer.",
    },
]


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
    )


class CreateCampaignUseCase:
    def __init__(self, campaign_repo: ICampaignRepository) -> None:
        self._repo = campaign_repo

    async def execute(self, dto: CreateCampaignDTO) -> CampaignResponseDTO:
        campaign = Campaign.create(
            title=dto.title,
            rpg_system=dto.rpg_system,
            difficulty=dto.difficulty,
            tone=dto.tone,
            description=dto.description,
        )
        saved = await self._repo.save(campaign)
        return _campaign_to_response_dto(saved)


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
    ) -> None:
        self._repo = campaign_repo
        self._characters = character_client

    async def execute(self, dto: AddAIPlayerDTO) -> dict:
        campaign = await self._repo.get_by_id(dto.campaign_id)
        if campaign is None:
            raise ValueError(f"Campanha {dto.campaign_id} não encontrada.")

        archetype = random.choice(_AI_ARCHETYPES)
        return await self._characters.create_character({
            "name": archetype["name"],
            "class": archetype["class"],
            "race": archetype["race"],
            "char_type": "ai_companion",
            "backstory": archetype["backstory"],
            "campaign_id": str(dto.campaign_id),
            "level": 1,
        })


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
