"""
Implementação concreta do ICampaignRepository usando SQLAlchemy + asyncpg.
Converte entre ORM (CampaignORM) e entidade de domínio (Campaign).
"""

from uuid import UUID

from sqlalchemy import delete as sa_delete, select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.campaign.entity import Campaign
from domain.campaign.value_objects import CampaignStatus, Difficulty, InitStatus
from infrastructure.database.orm_models import CampaignORM, SessionMessageORM, SessionORM


class CampaignRepository:
    """
    Repositório concreto de campanhas.
    Implementa ICampaignRepository via duck typing (Protocol).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Conversores ORM ↔ Domínio
    # ------------------------------------------------------------------

    @staticmethod
    def _to_domain(orm: CampaignORM) -> Campaign:
        return Campaign(
            id=orm.id,
            title=orm.title,
            description=orm.description,
            rpg_system=orm.rpg_system,
            difficulty=Difficulty(orm.difficulty),
            tone=orm.tone,
            status=CampaignStatus(orm.status),
            init_status=InitStatus(orm.init_status),
            opening_generated=orm.opening_generated,
            locations_json=orm.locations_json,
            created_at=orm.created_at,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def _apply_to_orm(campaign: Campaign, orm: CampaignORM) -> None:
        """Aplica os valores da entidade de domínio no objeto ORM (in-place)."""
        orm.title = campaign.title
        orm.description = campaign.description
        orm.rpg_system = campaign.rpg_system
        orm.difficulty = campaign.difficulty.value
        orm.tone = campaign.tone
        orm.status = campaign.status.value
        orm.init_status = campaign.init_status.value
        orm.opening_generated = campaign.opening_generated
        orm.locations_json = campaign.locations_json

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    async def get_by_id(self, campaign_id: UUID) -> Campaign | None:
        orm = await self._db.get(CampaignORM, campaign_id)
        return self._to_domain(orm) if orm else None

    async def list_all(self) -> list[Campaign]:
        result = await self._db.execute(
            sa_select(CampaignORM).order_by(CampaignORM.created_at.desc())
        )
        return [self._to_domain(row) for row in result.scalars().all()]

    async def save(self, campaign: Campaign) -> Campaign:
        """Cria ou atualiza uma campanha. Retorna a entidade com dados do banco."""
        orm = await self._db.get(CampaignORM, campaign.id)
        if orm is None:
            orm = CampaignORM(id=campaign.id)
            self._db.add(orm)

        self._apply_to_orm(campaign, orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return self._to_domain(orm)

    async def delete(self, campaign_id: UUID) -> None:
        """Remove campanha e todos os dados relacionados respeitando FK."""
        # 1. Busca IDs de sessões
        sessions_result = await self._db.execute(
            sa_select(SessionORM).where(SessionORM.campaign_id == campaign_id)
        )
        session_ids = [s.id for s in sessions_result.scalars().all()]

        # 2. Remove mensagens → sessões → campanha
        if session_ids:
            await self._db.execute(
                sa_delete(SessionMessageORM).where(
                    SessionMessageORM.session_id.in_(session_ids)
                )
            )
            await self._db.execute(
                sa_delete(SessionORM).where(SessionORM.campaign_id == campaign_id)
            )

        orm = await self._db.get(CampaignORM, campaign_id)
        if orm:
            await self._db.delete(orm)

        await self._db.flush()
