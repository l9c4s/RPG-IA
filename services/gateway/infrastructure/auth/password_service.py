"""bcrypt password hashing — implements IPasswordService."""
from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordService:
    def hash(self, plain: str) -> str:
        return _pwd_context.hash(plain)

    def verify(self, plain: str, hashed: str) -> bool:
        return _pwd_context.verify(plain, hashed)
