"""
Implementação concreta de IRoundRepository usando SQLAlchemy + asyncpg.
Converte entre ORM (SessionRoundORM, RoundActionORM) e entidades de domínio.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select as sa_select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from domain.round.entity import Round, RoundAction
from domain.round.value_objects import RoundStatus
from infrastructure.database.orm_models import RoundActionORM, SessionRoundORM


class RoundRepository:
    """
    Repositório concreto de rounds e ações.
    Implementa IRoundRepository via duck typing (Protocol).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ─── Conversões ORM ↔ Domain ────────────────────────────────────────────

    @staticmethod
    def _action_to_domain(orm: RoundActionORM) -> RoundAction:
        return RoundAction(
            id=orm.id,
            round_id=orm.round_id,
            session_id=orm.session_id,
            player_id=orm.player_id,
            character_id=orm.character_id,
            character_name=orm.character_name,
            is_ai=orm.is_ai,
            action_text=orm.action_text,
            is_pass=orm.is_pass,
            d20_roll=orm.d20_roll,
            initiative_order=orm.initiative_order,
            gm_response=orm.gm_response,
            gm_rolled_dice=orm.gm_rolled_dice,
            outcome_roll=orm.outcome_roll,
            submitted_at=orm.submitted_at,
        )

    @staticmethod
    def _round_to_domain(orm: SessionRoundORM, actions: list[RoundAction]) -> Round:
        return Round(
            id=orm.id,
            session_id=orm.session_id,
            round_number=orm.round_number,
            status=RoundStatus(orm.status),
            actions=actions,
            started_at=orm.started_at,
            resolved_at=orm.resolved_at,
            completed_at=orm.completed_at,
        )

    # ─── Round CRUD ─────────────────────────────────────────────────────────

    async def save(self, round_: Round) -> Round:
        orm = await self._db.get(SessionRoundORM, round_.id)
        if orm is None:
            orm = SessionRoundORM(
                id=round_.id,
                session_id=round_.session_id,
                round_number=round_.round_number,
            )
            self._db.add(orm)

        orm.status = round_.status.value
        orm.resolved_at = round_.resolved_at
        orm.completed_at = round_.completed_at

        await self._db.flush()
        await self._db.refresh(orm)

        actions = await self._load_actions(round_.id)
        return self._round_to_domain(orm, actions)

    async def get_by_id(self, round_id: UUID) -> Round | None:
        orm = await self._db.get(SessionRoundORM, round_id)
        if orm is None:
            return None
        actions = await self._load_actions(round_id)
        return self._round_to_domain(orm, actions)

    async def get_active_by_session(self, session_id: UUID) -> Round | None:
        result = await self._db.execute(
            sa_select(SessionRoundORM)
            .where(
                SessionRoundORM.session_id == session_id,
                SessionRoundORM.status.not_in(["completed"]),
            )
            .order_by(SessionRoundORM.started_at.desc())
            .limit(1)
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        actions = await self._load_actions(orm.id)
        return self._round_to_domain(orm, actions)

    async def get_last_round_number(self, session_id: UUID) -> int:
        result = await self._db.execute(
            sa_select(sa_func.max(SessionRoundORM.round_number)).where(
                SessionRoundORM.session_id == session_id
            )
        )
        value = result.scalar_one_or_none()
        return value or 0

    # ─── Action CRUD ────────────────────────────────────────────────────────

    async def save_action(self, action: RoundAction) -> None:
        orm = RoundActionORM(
            id=action.id,
            round_id=action.round_id,
            session_id=action.session_id,
            player_id=action.player_id,
            character_id=action.character_id,
            character_name=action.character_name,
            is_ai=action.is_ai,
            action_text=action.action_text,
            is_pass=action.is_pass,
            d20_roll=action.d20_roll,
            initiative_order=action.initiative_order,
            gm_response=action.gm_response,
            gm_rolled_dice=action.gm_rolled_dice,
            outcome_roll=action.outcome_roll,
        )
        self._db.add(orm)
        await self._db.flush()

    async def update_action(self, action: RoundAction) -> None:
        orm = await self._db.get(RoundActionORM, action.id)
        if orm is None:
            return
        orm.d20_roll = action.d20_roll
        orm.initiative_order = action.initiative_order
        orm.gm_response = action.gm_response
        orm.gm_rolled_dice = action.gm_rolled_dice
        orm.outcome_roll = action.outcome_roll
        await self._db.flush()

    # ─── Helpers ────────────────────────────────────────────────────────────

    async def _load_actions(self, round_id: UUID) -> list[RoundAction]:
        result = await self._db.execute(
            sa_select(RoundActionORM)
            .where(RoundActionORM.round_id == round_id)
            .order_by(RoundActionORM.submitted_at.asc())
        )
        return [self._action_to_domain(row) for row in result.scalars().all()]
