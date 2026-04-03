"""Unit tests — application use cases (AsyncMock repo, no DB, no HTTP)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from application.user.dtos import LoginDTO, RegisterDTO
from application.user.use_cases import GetMeUseCase, LoginUseCase, RegisterUseCase
from domain.user.entity import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(**overrides) -> User:
    defaults = dict(username="player01", email="player@example.com", password_hash="$2b$hash")
    defaults.update(overrides)
    return User.create(**defaults)


def _make_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_email.return_value = None
    repo.get_by_username.return_value = None
    repo.save.side_effect = lambda u: u
    return repo


def _make_pw(valid: bool = True) -> MagicMock:
    pw = MagicMock()
    pw.hash.return_value = "$2b$12$hashed"
    pw.verify.return_value = valid
    return pw


def _make_jwt() -> MagicMock:
    jwt = MagicMock()
    jwt.create_token.return_value = "jwt.token.here"
    return jwt


# ---------------------------------------------------------------------------
# RegisterUseCase
# ---------------------------------------------------------------------------


class TestRegisterUseCase:
    async def test_success_returns_user_dto(self):
        repo = _make_repo()
        uc = RegisterUseCase(repo=repo, password_service=_make_pw())
        dto = await uc.execute(RegisterDTO("player01", "p@example.com", "secret123"))
        assert dto.username == "player01"
        assert dto.email == "p@example.com"
        repo.save.assert_called_once()

    async def test_email_taken_raises(self):
        repo = _make_repo()
        repo.get_by_email.return_value = _make_user()
        uc = RegisterUseCase(repo=repo, password_service=_make_pw())
        with pytest.raises(ValueError, match="email_taken"):
            await uc.execute(RegisterDTO("other", "taken@example.com", "secret123"))

    async def test_username_taken_raises(self):
        repo = _make_repo()
        repo.get_by_username.return_value = _make_user()
        uc = RegisterUseCase(repo=repo, password_service=_make_pw())
        with pytest.raises(ValueError, match="username_taken"):
            await uc.execute(RegisterDTO("player01", "new@example.com", "secret123"))

    async def test_password_is_hashed_before_save(self):
        repo = _make_repo()
        pw = _make_pw()
        uc = RegisterUseCase(repo=repo, password_service=pw)
        await uc.execute(RegisterDTO("player01", "p@example.com", "plain_pass"))
        pw.hash.assert_called_once_with("plain_pass")


# ---------------------------------------------------------------------------
# LoginUseCase
# ---------------------------------------------------------------------------


class TestLoginUseCase:
    async def test_success_returns_user_and_token(self):
        user = _make_user()
        repo = _make_repo()
        repo.get_by_email.return_value = user
        uc = LoginUseCase(repo=repo, password_service=_make_pw(valid=True), jwt_service=_make_jwt())
        user_dto, token_dto = await uc.execute(LoginDTO("player@example.com", "secret"))
        assert user_dto.email == "player@example.com"
        assert token_dto.access_token == "jwt.token.here"
        assert token_dto.token_type == "bearer"

    async def test_wrong_password_raises(self):
        user = _make_user()
        repo = _make_repo()
        repo.get_by_email.return_value = user
        uc = LoginUseCase(repo=repo, password_service=_make_pw(valid=False), jwt_service=_make_jwt())
        with pytest.raises(ValueError, match="invalid_credentials"):
            await uc.execute(LoginDTO("player@example.com", "wrongpass"))

    async def test_unknown_email_raises(self):
        repo = _make_repo()
        repo.get_by_email.return_value = None
        uc = LoginUseCase(repo=repo, password_service=_make_pw(), jwt_service=_make_jwt())
        with pytest.raises(ValueError, match="invalid_credentials"):
            await uc.execute(LoginDTO("ghost@example.com", "pass"))

    async def test_inactive_user_raises(self):
        user = _make_user()
        user.deactivate()
        repo = _make_repo()
        repo.get_by_email.return_value = user
        uc = LoginUseCase(repo=repo, password_service=_make_pw(valid=True), jwt_service=_make_jwt())
        with pytest.raises(ValueError, match="inactive_user"):
            await uc.execute(LoginDTO("player@example.com", "secret"))

    async def test_jwt_created_with_correct_user_id(self):
        user = _make_user()
        repo = _make_repo()
        repo.get_by_email.return_value = user
        jwt = _make_jwt()
        uc = LoginUseCase(repo=repo, password_service=_make_pw(valid=True), jwt_service=jwt)
        await uc.execute(LoginDTO("player@example.com", "secret"))
        jwt.create_token.assert_called_once_with(user_id=user.id, username=str(user.username))


# ---------------------------------------------------------------------------
# GetMeUseCase
# ---------------------------------------------------------------------------


class TestGetMeUseCase:
    async def test_success_returns_user_dto(self):
        user = _make_user()
        repo = _make_repo()
        repo.get_by_id.return_value = user
        uc = GetMeUseCase(repo=repo)
        dto = await uc.execute(user.id)
        assert dto.id == user.id
        assert dto.email == str(user.email)

    async def test_user_not_found_raises(self):
        repo = _make_repo()
        repo.get_by_id.return_value = None
        uc = GetMeUseCase(repo=repo)
        with pytest.raises(ValueError, match="user_not_found"):
            await uc.execute(uuid4())
