"""JWT creation and verification — implements IJWTService."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

_ALGORITHM = "HS256"
_DEFAULT_EXPIRY_HOURS = 24
_JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")


class JWTService:
    def __init__(
        self,
        secret: str = _JWT_SECRET,
        algorithm: str = _ALGORITHM,
        expiry_hours: int = _DEFAULT_EXPIRY_HOURS,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._expiry_hours = expiry_hours

    def create_token(self, user_id: UUID, username: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(hours=self._expiry_hours)
        payload = {"sub": str(user_id), "username": username, "exp": expire}
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_token(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except JWTError as exc:
            raise ValueError("invalid_token") from exc
