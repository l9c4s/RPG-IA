"""Unit tests for auth.py — hashing, JWT creation/validation."""
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from jose import jwt

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    verify_token,
)
from config import settings


# ── Password hashing ──────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_returns_non_plaintext(self):
        hashed = get_password_hash("secret123")
        assert hashed != "secret123"

    def test_hash_is_bcrypt(self):
        hashed = get_password_hash("secret123")
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = get_password_hash("secret123")
        assert verify_password("secret123", hashed) is True

    def test_verify_wrong_password(self):
        hashed = get_password_hash("secret123")
        assert verify_password("wrong", hashed) is False

    def test_same_password_different_hashes(self):
        h1 = get_password_hash("secret")
        h2 = get_password_hash("secret")
        assert h1 != h2  # bcrypt uses random salt


# ── JWT tokens ────────────────────────────────────────────────────────────────

class TestJWT:
    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "user-123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_sub(self):
        token = create_access_token({"sub": "user-123"})
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert payload["sub"] == "user-123"

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "user-123"})
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        assert "exp" in payload

    def test_custom_expiry_respected(self):
        short = create_access_token({"sub": "u"}, expires_delta=timedelta(seconds=1))
        long = create_access_token({"sub": "u"}, expires_delta=timedelta(hours=24))
        p_short = jwt.decode(short, settings.jwt_secret, algorithms=["HS256"])
        p_long = jwt.decode(long, settings.jwt_secret, algorithms=["HS256"])
        assert p_long["exp"] > p_short["exp"]

    def test_verify_valid_token(self):
        token = create_access_token({"sub": "user-abc"})
        payload = verify_token(token)
        assert payload["sub"] == "user-abc"

    def test_verify_invalid_token_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            verify_token("totally.invalid.token")
        assert exc.value.status_code == 401

    def test_verify_tampered_token_raises(self):
        from fastapi import HTTPException
        token = create_access_token({"sub": "user-abc"})
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException):
            verify_token(tampered)
