"""Application use cases for the User bounded context."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.user.entity import User
from domain.user.repository import IUserRepository
from application.user.dtos import LoginDTO, RegisterDTO, TokenDTO, UserDTO


# ---------------------------------------------------------------------------
# Port interfaces for infrastructure services (injected at runtime)
# ---------------------------------------------------------------------------


class IPasswordService(Protocol):
    def hash(self, plain: str) -> str: ...
    def verify(self, plain: str, hashed: str) -> bool: ...


class IJWTService(Protocol):
    def create_token(self, user_id: UUID, username: str) -> str: ...
    def decode_token(self, token: str) -> dict: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_dto(user: User) -> UserDTO:
    return UserDTO(
        id=user.id,
        username=str(user.username),
        email=str(user.email),
        is_active=user.is_active,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


class RegisterUseCase:
    def __init__(self, repo: IUserRepository, password_service: IPasswordService) -> None:
        self._repo = repo
        self._pw = password_service

    async def execute(self, dto: RegisterDTO) -> UserDTO:
        if await self._repo.get_by_email(dto.email) is not None:
            raise ValueError("email_taken")
        if await self._repo.get_by_username(dto.username) is not None:
            raise ValueError("username_taken")

        hashed = self._pw.hash(dto.password)
        user = User.create(
            username=dto.username,
            email=dto.email,
            password_hash=hashed,
        )
        saved = await self._repo.save(user)
        return _to_dto(saved)


class LoginUseCase:
    def __init__(
        self,
        repo: IUserRepository,
        password_service: IPasswordService,
        jwt_service: IJWTService,
    ) -> None:
        self._repo = repo
        self._pw = password_service
        self._jwt = jwt_service

    async def execute(self, dto: LoginDTO) -> tuple[UserDTO, TokenDTO]:
        user = await self._repo.get_by_email(dto.email)
        if user is None or not self._pw.verify(dto.password, str(user.password_hash)):
            raise ValueError("invalid_credentials")
        if not user.is_active:
            raise ValueError("inactive_user")

        token = self._jwt.create_token(user_id=user.id, username=str(user.username))
        return _to_dto(user), TokenDTO(access_token=token)


class GetMeUseCase:
    def __init__(self, repo: IUserRepository) -> None:
        self._repo = repo

    async def execute(self, user_id: UUID) -> UserDTO:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise ValueError("user_not_found")
        return _to_dto(user)
