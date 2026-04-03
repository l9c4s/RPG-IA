"""Integration tests — UserRepository against a real PostgreSQL database."""
import pytest

from domain.user.entity import User
from infrastructure.repositories.user_repository import UserRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(username="player01", email="player@example.com") -> User:
    return User.create(username=username, email=email, password_hash="$2b$12$hash")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSave:
    async def test_save_creates_user_with_id(self, db_session):
        repo = UserRepository(db_session)
        user = _make_user()
        saved = await repo.save(user)
        assert saved.id == user.id
        assert saved.username == "player01"
        assert saved.email == "player@example.com"

    async def test_save_update_preserves_id(self, db_session):
        repo = UserRepository(db_session)
        user = _make_user()
        await repo.save(user)
        user.deactivate()
        updated = await repo.save(user)
        assert updated.id == user.id
        assert updated.is_active is False


class TestGetByEmail:
    async def test_returns_user_when_found(self, db_session):
        repo = UserRepository(db_session)
        user = _make_user()
        await repo.save(user)
        found = await repo.get_by_email("player@example.com")
        assert found is not None
        assert found.id == user.id

    async def test_email_lookup_is_case_insensitive(self, db_session):
        repo = UserRepository(db_session)
        await repo.save(_make_user())
        found = await repo.get_by_email("PLAYER@EXAMPLE.COM")
        assert found is not None

    async def test_returns_none_when_not_found(self, db_session):
        repo = UserRepository(db_session)
        result = await repo.get_by_email("ghost@example.com")
        assert result is None


class TestGetByUsername:
    async def test_returns_user_when_found(self, db_session):
        repo = UserRepository(db_session)
        await repo.save(_make_user())
        found = await repo.get_by_username("player01")
        assert found is not None

    async def test_returns_none_when_not_found(self, db_session):
        repo = UserRepository(db_session)
        result = await repo.get_by_username("ghost")
        assert result is None


class TestGetById:
    async def test_returns_user_when_found(self, db_session):
        repo = UserRepository(db_session)
        user = _make_user()
        await repo.save(user)
        found = await repo.get_by_id(user.id)
        assert found is not None
        assert found.username == "player01"

    async def test_returns_none_when_not_found(self, db_session):
        from uuid import uuid4
        repo = UserRepository(db_session)
        result = await repo.get_by_id(uuid4())
        assert result is None


class TestUniqueness:
    async def test_duplicate_email_raises(self, db_session):
        from sqlalchemy.exc import IntegrityError
        repo = UserRepository(db_session)
        await repo.save(_make_user(username="user1", email="dup@example.com"))
        await db_session.commit()
        with pytest.raises(Exception):  # IntegrityError or similar
            await repo.save(_make_user(username="user2", email="dup@example.com"))
            await db_session.commit()

    async def test_duplicate_username_raises(self, db_session):
        repo = UserRepository(db_session)
        await repo.save(_make_user(username="dupname", email="a@example.com"))
        await db_session.commit()
        with pytest.raises(Exception):
            await repo.save(_make_user(username="dupname", email="b@example.com"))
            await db_session.commit()
