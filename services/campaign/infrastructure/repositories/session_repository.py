"""
Implementação concreta de ISessionRepository e IMessageRepository.
Converte entre ORM (SessionORM, SessionMessageORM) e entidades de domínio.
"""

from uuid import UUID

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.session.entity import Session, SessionMessage
from domain.session.value_objects import MessageRole
from infrastructure.database.orm_models import SessionMessageORM, SessionORM


class SessionRepository:
    """
    Repositório concreto de sessões de jogo.
    Implementa ISessionRepository via duck typing (Protocol).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    def _to_domain(orm: SessionORM) -> Session:
        return Session(
            id=orm.id,
            campaign_id=orm.campaign_id,
            started_at=orm.started_at,
            ended_at=orm.ended_at,
        )

    async def get_by_id(self, session_id: UUID) -> Session | None:
        orm = await self._db.get(SessionORM, session_id)
        return self._to_domain(orm) if orm else None

    async def get_latest_by_campaign(self, campaign_id: UUID) -> Session | None:
        result = await self._db.execute(
            sa_select(SessionORM)
            .where(SessionORM.campaign_id == campaign_id)
            .order_by(SessionORM.started_at.desc())
            .limit(1)
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def save(self, session: Session) -> Session:
        orm = await self._db.get(SessionORM, session.id)
        if orm is None:
            orm = SessionORM(id=session.id, campaign_id=session.campaign_id)
            self._db.add(orm)

        await self._db.flush()
        await self._db.refresh(orm)
        return self._to_domain(orm)


class MessageRepository:
    """
    Repositório concreto de mensagens de sessão.
    Implementa IMessageRepository via duck typing (Protocol).
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    @staticmethod
    def _to_domain(orm: SessionMessageORM) -> SessionMessage:
        return SessionMessage(
            id=orm.id,
            session_id=orm.session_id,
            role=MessageRole(orm.role),
            content=orm.content,
            player_id=orm.player_id,
            character_id=orm.character_id,
            created_at=orm.created_at,
        )

    async def save(self, message: SessionMessage) -> None:
        orm = SessionMessageORM(
            id=message.id,
            session_id=message.session_id,
            role=message.role.value,
            content=message.content,
            player_id=message.player_id,
            character_id=message.character_id,
        )
        self._db.add(orm)
        await self._db.flush()

    async def list_by_session(self, session_id: UUID) -> list[SessionMessage]:
        result = await self._db.execute(
            sa_select(SessionMessageORM)
            .where(SessionMessageORM.session_id == session_id)
            .order_by(SessionMessageORM.created_at.asc())
        )
        return [self._to_domain(row) for row in result.scalars().all()]
