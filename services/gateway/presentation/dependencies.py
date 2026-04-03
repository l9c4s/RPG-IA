"""FastAPI dependency injection wiring."""
from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from application.user.use_cases import GetMeUseCase, LoginUseCase, RegisterUseCase
from infrastructure.auth.jwt_service import JWTService
from infrastructure.auth.password_service import PasswordService
from infrastructure.database.connection import get_db
from infrastructure.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_jwt_service = JWTService()
_password_service = PasswordService()


# ---------------------------------------------------------------------------
# Infrastructure singletons
# ---------------------------------------------------------------------------


def get_jwt_service() -> JWTService:
    return _jwt_service


def get_password_service() -> PasswordService:
    return _password_service


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


def get_user_repo(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(session)


# ---------------------------------------------------------------------------
# Use cases
# ---------------------------------------------------------------------------


def get_register_uc(
    repo: UserRepository = Depends(get_user_repo),
    pw: PasswordService = Depends(get_password_service),
) -> RegisterUseCase:
    return RegisterUseCase(repo=repo, password_service=pw)


def get_login_uc(
    repo: UserRepository = Depends(get_user_repo),
    pw: PasswordService = Depends(get_password_service),
    jwt: JWTService = Depends(get_jwt_service),
) -> LoginUseCase:
    return LoginUseCase(repo=repo, password_service=pw, jwt_service=jwt)


def get_get_me_uc(
    repo: UserRepository = Depends(get_user_repo),
) -> GetMeUseCase:
    return GetMeUseCase(repo=repo)


# ---------------------------------------------------------------------------
# Current user extractor
# ---------------------------------------------------------------------------


def get_current_user_id(
    token: str = Depends(oauth2_scheme),
    jwt: JWTService = Depends(get_jwt_service),
) -> UUID:
    try:
        payload = jwt.decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("missing_sub")
        return UUID(user_id)
    except (ValueError, Exception):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
