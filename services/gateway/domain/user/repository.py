"""Repository interface (Protocol) for the User aggregate."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.user.entity import User


class IUserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def get_by_username(self, username: str) -> User | None: ...
    async def save(self, user: User) -> User: ...
