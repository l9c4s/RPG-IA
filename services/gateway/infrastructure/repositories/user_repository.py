"""Concrete UserRepository — implements IUserRepository using SQLAlchemy."""
from __future__ import annotations

from datetime import timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.user.entity import User
from domain.user.value_objects import Email, PasswordHash, Username
from infrastructure.database.orm_models import UserDB


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # ORM ↔ Domain conversion
    # ------------------------------------------------------------------

    def _to_domain(self, orm: UserDB) -> User:
        created_at = orm.created_at
        if created_at.tzinfo is None:
            from datetime import timezone as tz
            created_at = created_at.replace(tzinfo=tz.utc)
        return User(
            id=UUID(str(orm.id)),
            username=Username(orm.username),
            email=Email(orm.email),
            password_hash=PasswordHash(orm.password_hash),
            is_active=orm.is_active,
            created_at=created_at,
        )

    def _apply_to_orm(self, user: User, orm: UserDB) -> None:
        orm.username = str(user.username)
        orm.email = str(user.email)
        orm.password_hash = str(user.password_hash)
        orm.is_active = user.is_active

    # ------------------------------------------------------------------
    # IUserRepository implementation
    # ------------------------------------------------------------------

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(UserDB).where(UserDB.id == str(user_id))
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserDB).where(UserDB.email == email.strip().lower())
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(UserDB).where(UserDB.username == username.strip().lower())
        )
        orm = result.scalar_one_or_none()
        return self._to_domain(orm) if orm else None

    async def save(self, user: User) -> User:
        result = await self._session.execute(
            select(UserDB).where(UserDB.id == str(user.id))
        )
        orm = result.scalar_one_or_none()

        if orm is None:
            orm = UserDB(id=str(user.id))
            self._apply_to_orm(user, orm)
            self._session.add(orm)
        else:
            self._apply_to_orm(user, orm)

        await self._session.flush()
        await self._session.refresh(orm)
        return self._to_domain(orm)
