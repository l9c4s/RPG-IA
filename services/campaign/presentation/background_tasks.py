"""
Background tasks com sessão própria — independentes do request HTTP.
"""

import logging
import os
from uuid import UUID

from application.gm.use_cases import GenerateOpeningNarrativeUseCase
from infrastructure.ai.langchain_gm_service import LangchainGMService
from infrastructure.database.connection import AsyncSessionLocal
from infrastructure.external.image_client import CharacterServiceClient
from infrastructure.external.knowledge_client import KnowledgeClient
from infrastructure.repositories.campaign_repository import CampaignRepository
from infrastructure.repositories.session_repository import MessageRepository, SessionRepository

logger = logging.getLogger(__name__)

VECTOR_DB_URL: str = os.getenv(
    "VECTOR_DB_URL", "postgresql+psycopg2://rpg:rpg@localhost:5432/rpg_campaign",
)


async def run_opening_background(campaign_id: UUID, session_id: UUID) -> None:
    """
    Gera narrativa de abertura em background com sua própria sessão de DB.
    Nunca compartilha sessão com o request HTTP que a disparou.
    """
    async with AsyncSessionLocal() as db:
        try:
            uc = GenerateOpeningNarrativeUseCase(
                campaign_repo=CampaignRepository(db),
                session_repo=SessionRepository(db),
                message_repo=MessageRepository(db),
                gm_service=LangchainGMService(VECTOR_DB_URL),
                knowledge_retriever=KnowledgeClient(),
                character_client=CharacterServiceClient(),
            )
            await uc.execute(campaign_id, session_id)
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                "run_opening_background falhou: campaign=%s session=%s",
                campaign_id,
                session_id,
            )
