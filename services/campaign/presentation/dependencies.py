"""
Injeção de dependências FastAPI.
Monta use cases injetando as implementações de infraestrutura concretas.
"""

import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.campaign.use_cases import (
    AddAIPlayerUseCase,
    CreateCampaignUseCase,
    DeleteCampaignUseCase,
    GenerateMapUseCase,
    GetCampaignLocationsUseCase,
    GetCampaignUseCase,
    GetLobbyUseCase,
    ListCampaignsUseCase,
    UpdateCampaignStatusUseCase,
)
from application.gm.use_cases import (
    Generate8BitCharacterUseCase,
    GenerateOpeningNarrativeUseCase,
    TriggerOpeningUseCase,
)
from application.round.use_cases import StartRoundUseCase, SubmitActionUseCase
from application.session.use_cases import (
    GetCurrentSessionUseCase,
    GetSessionMessagesUseCase,
    ProcessPlayerTurnUseCase,
    StartCampaignSessionUseCase,
)
from infrastructure.ai.langchain_gm_service import LangchainGMService
from infrastructure.database.connection import get_db
from infrastructure.external.image_client import CharacterServiceClient, ImageClient
from infrastructure.external.knowledge_client import KnowledgeClient
from infrastructure.external.tts_client import TTSClient
from infrastructure.repositories.campaign_repository import CampaignRepository
from infrastructure.repositories.round_repository import RoundRepository
from infrastructure.repositories.session_repository import MessageRepository, SessionRepository
from presentation.websocket.connection_manager import manager

VECTOR_DB_URL: str = os.getenv(
    "VECTOR_DB_URL","postgresql+psycopg2://rpg:rpg@localhost:5432/rpg_campaign",
)


# ------------------------------------------------------------------
# Infraestrutura (stateless — recriada por request ou singleton)
# ------------------------------------------------------------------

def get_campaign_repo(db: AsyncSession = Depends(get_db)) -> CampaignRepository:
    return CampaignRepository(db)


def get_session_repo(db: AsyncSession = Depends(get_db)) -> SessionRepository:
    return SessionRepository(db)


def get_message_repo(db: AsyncSession = Depends(get_db)) -> MessageRepository:
    return MessageRepository(db)


def get_gm_service() -> LangchainGMService:
    return LangchainGMService(VECTOR_DB_URL)


def get_knowledge_client() -> KnowledgeClient:
    return KnowledgeClient()


def get_tts_client() -> TTSClient:
    return TTSClient()


def get_image_client() -> ImageClient:
    return ImageClient()


def get_character_client() -> CharacterServiceClient:
    return CharacterServiceClient()


# ------------------------------------------------------------------
# Use cases de Campanha
# ------------------------------------------------------------------

def get_create_campaign_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
    gm: LangchainGMService = Depends(get_gm_service),
    chars: CharacterServiceClient = Depends(get_character_client),
) -> CreateCampaignUseCase:
    return CreateCampaignUseCase(repo, gm, chars)


def get_list_campaigns_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
) -> ListCampaignsUseCase:
    return ListCampaignsUseCase(repo)


def get_campaign_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
) -> GetCampaignUseCase:
    return GetCampaignUseCase(repo)


def get_lobby_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
    chars: CharacterServiceClient = Depends(get_character_client),
) -> GetLobbyUseCase:
    return GetLobbyUseCase(repo, chars)


def get_update_status_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
    chars: CharacterServiceClient = Depends(get_character_client),
) -> UpdateCampaignStatusUseCase:
    return UpdateCampaignStatusUseCase(repo, chars)


def get_delete_campaign_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
) -> DeleteCampaignUseCase:
    return DeleteCampaignUseCase(repo)


def get_add_ai_player_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
    chars: CharacterServiceClient = Depends(get_character_client),
    gm: LangchainGMService = Depends(get_gm_service),
    image: ImageClient = Depends(get_image_client),
) -> AddAIPlayerUseCase:
    return AddAIPlayerUseCase(repo, chars, gm, image)


def get_campaign_locations_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
) -> GetCampaignLocationsUseCase:
    return GetCampaignLocationsUseCase(repo)


def get_generate_map_uc(
    repo: CampaignRepository = Depends(get_campaign_repo),
    gm: LangchainGMService = Depends(get_gm_service),
    chars: CharacterServiceClient = Depends(get_character_client),
) -> GenerateMapUseCase:
    return GenerateMapUseCase(repo, gm, chars)


# ------------------------------------------------------------------
# Use cases de Sessão
# ------------------------------------------------------------------

def get_start_session_uc(
    campaigns: CampaignRepository = Depends(get_campaign_repo),
    sessions: SessionRepository = Depends(get_session_repo),
    chars: CharacterServiceClient = Depends(get_character_client),
) -> StartCampaignSessionUseCase:
    return StartCampaignSessionUseCase(campaigns, sessions, chars)


def get_current_session_uc(
    campaigns: CampaignRepository = Depends(get_campaign_repo),
    sessions: SessionRepository = Depends(get_session_repo),
) -> GetCurrentSessionUseCase:
    return GetCurrentSessionUseCase(campaigns, sessions)


def get_session_messages_uc(
    messages: MessageRepository = Depends(get_message_repo),
) -> GetSessionMessagesUseCase:
    return GetSessionMessagesUseCase(messages)


def get_process_turn_uc(
    sessions: SessionRepository = Depends(get_session_repo),
    messages: MessageRepository = Depends(get_message_repo),
    campaigns: CampaignRepository = Depends(get_campaign_repo),
    gm: LangchainGMService = Depends(get_gm_service),
    knowledge: KnowledgeClient = Depends(get_knowledge_client),
    tts: TTSClient = Depends(get_tts_client),
    image: ImageClient = Depends(get_image_client),
    chars: CharacterServiceClient = Depends(get_character_client),
) -> ProcessPlayerTurnUseCase:
    return ProcessPlayerTurnUseCase(
        session_repo=sessions,
        message_repo=messages,
        campaign_repo=campaigns,
        gm_service=gm,
        knowledge_retriever=knowledge,
        tts_client=tts,
        image_client=image,
        character_client=chars,
        ws_broadcast_fn=manager.broadcast,
    )


# ------------------------------------------------------------------
# Use cases do GM
# ------------------------------------------------------------------

def get_opening_narrative_uc(
    campaigns: CampaignRepository = Depends(get_campaign_repo),
    sessions: SessionRepository = Depends(get_session_repo),
    messages: MessageRepository = Depends(get_message_repo),
    gm: LangchainGMService = Depends(get_gm_service),
    knowledge: KnowledgeClient = Depends(get_knowledge_client),
    chars: CharacterServiceClient = Depends(get_character_client),
) -> GenerateOpeningNarrativeUseCase:
    return GenerateOpeningNarrativeUseCase(campaigns, sessions, messages, gm, knowledge, chars)


def get_trigger_opening_uc(
    campaigns: CampaignRepository = Depends(get_campaign_repo),
    sessions: SessionRepository = Depends(get_session_repo),
) -> TriggerOpeningUseCase:
    return TriggerOpeningUseCase(campaigns, sessions)


def get_8bit_character_uc(
    campaigns: CampaignRepository = Depends(get_campaign_repo),
    gm: LangchainGMService = Depends(get_gm_service),
) -> Generate8BitCharacterUseCase:
    return Generate8BitCharacterUseCase(campaigns, gm)


# ------------------------------------------------------------------
# Use cases de Round
# ------------------------------------------------------------------

def get_round_repo(db: AsyncSession = Depends(get_db)) -> RoundRepository:
    return RoundRepository(db)


def get_start_round_uc(
    rounds: RoundRepository = Depends(get_round_repo),
    sessions: SessionRepository = Depends(get_session_repo),
    chars: CharacterServiceClient = Depends(get_character_client),
    gm: LangchainGMService = Depends(get_gm_service),
) -> StartRoundUseCase:
    return StartRoundUseCase(
        round_repo=rounds,
        session_repo=sessions,
        character_client=chars,
        gm_service=gm,
        ws_broadcast_fn=manager.broadcast,
    )


def get_submit_action_uc(
    rounds: RoundRepository = Depends(get_round_repo),
    sessions: SessionRepository = Depends(get_session_repo),
    chars: CharacterServiceClient = Depends(get_character_client),
) -> SubmitActionUseCase:
    return SubmitActionUseCase(
        round_repo=rounds,
        session_repo=sessions,
        character_client=chars,
        ws_broadcast_fn=manager.broadcast,
    )
