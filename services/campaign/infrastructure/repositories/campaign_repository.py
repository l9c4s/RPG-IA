"""
Implementação concreta do ICampaignRepository usando SQLAlchemy + asyncpg.
Converte entre ORM (CampaignORM) e entidade de domínio (Campaign).
"""

from uuid import UUID, uuid4

from sqlalchemy import delete as sa_delete, select as sa_select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.campaign.entity import Campaign
from domain.campaign.value_objects import CampaignStatus, Difficulty, InitStatus
from infrastructure.database.orm_models import (
    CampaignORM,
    CampaignPlayerORM,
    CampaignSnapshotORM,
    CampaignStateORM,
    GmMemoryORM,
    LocationORM,
    NpcORM,
    SessionMessageORM,
    SessionORM,
)


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
            ai_players_count=orm.ai_players_count,
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
        orm.ai_players_count = campaign.ai_players_count
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

    # ------------------------------------------------------------------
    # GM Memory
    # ------------------------------------------------------------------

    async def save_gm_memory(
        self,
        *,
        campaign_id: UUID,
        content: str,
        memory_type: str = "narrative",
        importance: int = 5,
    ) -> None:
        orm = GmMemoryORM(
            campaign_id=campaign_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
        )
        self._db.add(orm)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Campaign State (upsert)
    # ------------------------------------------------------------------

    async def upsert_campaign_state(
        self,
        *,
        campaign_id: UUID,
        current_scene: str | None = None,
        current_location: str | None = None,
        world_state: dict | None = None,
    ) -> None:
        stmt = (
            pg_insert(CampaignStateORM)
            .values(
                id=uuid4(),
                campaign_id=campaign_id,
                current_scene=current_scene,
                current_location=current_location,
                world_state=world_state or {},
                active_quests=[],
                completed_quests=[],
                npc_states={},
            )
            .on_conflict_do_update(
                index_elements=["campaign_id"],
                set_={
                    "current_scene": current_scene,
                    "current_location": current_location,
                    "world_state": world_state or {},
                },
            )
        )
        await self._db.execute(stmt)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Campaign Snapshot
    # ------------------------------------------------------------------

    async def save_snapshot(
        self,
        *,
        campaign_id: UUID,
        session_id: UUID,
        state_data: dict,
    ) -> None:
        orm = CampaignSnapshotORM(
            campaign_id=campaign_id,
            session_id=session_id,
            state_data=state_data,
        )
        self._db.add(orm)
        await self._db.flush()

    # ------------------------------------------------------------------
    # NPCs
    # ------------------------------------------------------------------

    async def save_npc(
        self,
        *,
        campaign_id: UUID,
        name: str,
        description: str | None = None,
    ) -> None:
        orm = NpcORM(
            campaign_id=campaign_id,
            name=name,
            description=description,
        )
        self._db.add(orm)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    async def save_location(
        self,
        *,
        campaign_id: UUID,
        name: str,
        description: str | None = None,
        map_url: str | None = None,
        properties: dict | None = None,
    ) -> None:
        orm = LocationORM(
            campaign_id=campaign_id,
            name=name,
            description=description,
            map_url=map_url,
            properties=properties or {},
        )
        self._db.add(orm)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Campaign Players
    # ------------------------------------------------------------------

    async def register_player(
        self,
        *,
        campaign_id: UUID,
        character_id: UUID,
        user_id: UUID | None = None,
        is_ai: bool = False,
        ai_personality: dict | None = None,
    ) -> None:
        """Registra um jogador na campanha. Ignora duplicata (mesmo character_id)."""
        existing = await self._db.execute(
            sa_select(CampaignPlayerORM).where(
                CampaignPlayerORM.campaign_id == campaign_id,
                CampaignPlayerORM.character_id == character_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return

        orm = CampaignPlayerORM(
            campaign_id=campaign_id,
            user_id=user_id,
            character_id=character_id,
            is_ai=is_ai,
            ai_personality=ai_personality,
        )
        self._db.add(orm)
        await self._db.flush()
