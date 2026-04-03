"""User aggregate root — framework-agnostic pure Python dataclass."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.user.value_objects import Email, PasswordHash, Username


@dataclass
class User:
    id: UUID
    username: Username
    email: Email
    password_hash: PasswordHash
    is_active: bool
    created_at: datetime

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        username: str,
        email: str,
        password_hash: str,
    ) -> "User":
        return cls(
            id=uuid4(),
            username=Username(username),
            email=Email(email),
            password_hash=PasswordHash(password_hash),
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Business logic
    # ------------------------------------------------------------------

    def deactivate(self) -> None:
        """Soft-deactivate the account."""
        self.is_active = False
