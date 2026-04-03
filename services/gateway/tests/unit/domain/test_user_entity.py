"""Unit tests — User entity and value objects (no DB, no HTTP)."""
import pytest

from domain.user.entity import User
from domain.user.value_objects import Email, PasswordHash, Username


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class TestEmail:
    def test_normalizes_to_lowercase(self):
        email = Email("  TEST@EXAMPLE.COM  ")
        assert email == "test@example.com"

    def test_valid_email_accepted(self):
        assert Email("user@example.com") == "user@example.com"

    def test_invalid_email_raises(self):
        with pytest.raises(ValueError):
            Email("not-an-email")

    def test_missing_domain_raises(self):
        with pytest.raises(ValueError):
            Email("user@")


class TestUsername:
    def test_normalizes_to_lowercase(self):
        username = Username("  Player01  ")
        assert username == "player01"

    def test_min_length_valid(self):
        assert Username("abc") == "abc"

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            Username("ab")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            Username("")


class TestPasswordHash:
    def test_wraps_string(self):
        h = PasswordHash("$2b$12$hash")
        assert str(h) == "$2b$12$hash"


# ---------------------------------------------------------------------------
# User entity
# ---------------------------------------------------------------------------


class TestUserCreate:
    def test_creates_with_valid_data(self):
        user = User.create(
            username="player01",
            email="player@example.com",
            password_hash="$2b$12$hash",
        )
        assert user.username == "player01"
        assert user.email == "player@example.com"
        assert user.is_active is True
        assert user.id is not None
        assert user.created_at is not None

    def test_each_create_has_unique_id(self):
        u1 = User.create("user1", "a@b.com", "hash")
        u2 = User.create("user2", "c@d.com", "hash")
        assert u1.id != u2.id

    def test_email_is_normalized(self):
        user = User.create("user", "  USER@EXAMPLE.COM  ", "hash")
        assert user.email == "user@example.com"


class TestUserDeactivate:
    def test_deactivate_sets_is_active_false(self):
        user = User.create("user", "u@example.com", "hash")
        assert user.is_active is True
        user.deactivate()
        assert user.is_active is False

    def test_deactivate_is_idempotent(self):
        user = User.create("user", "u@example.com", "hash")
        user.deactivate()
        user.deactivate()
        assert user.is_active is False
