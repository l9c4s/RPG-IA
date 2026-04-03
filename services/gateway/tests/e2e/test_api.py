"""E2E tests — full HTTP stack via ASGI + real PostgreSQL database."""
import pytest

REGISTER_PAYLOAD = {
    "username": "player01",
    "email": "player01@example.com",
    "password": "password123",
}


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealth:
    async def test_health_returns_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["service"] == "gateway"


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------


class TestRegister:
    async def test_register_success_201(self, client):
        r = await client.post("/auth/register", json=REGISTER_PAYLOAD)
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == "player01"
        assert data["email"] == "player01@example.com"
        assert data["is_active"] is True
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data

    async def test_register_duplicate_email_409(self, client):
        await client.post("/auth/register", json=REGISTER_PAYLOAD)
        r = await client.post("/auth/register", json={
            **REGISTER_PAYLOAD,
            "username": "other_user",
        })
        assert r.status_code == 409

    async def test_register_duplicate_username_409(self, client):
        await client.post("/auth/register", json=REGISTER_PAYLOAD)
        r = await client.post("/auth/register", json={
            **REGISTER_PAYLOAD,
            "email": "other@example.com",
        })
        assert r.status_code == 409

    async def test_register_short_password_422(self, client):
        r = await client.post("/auth/register", json={
            **REGISTER_PAYLOAD,
            "password": "short",
        })
        assert r.status_code == 422

    async def test_register_invalid_email_422(self, client):
        r = await client.post("/auth/register", json={
            **REGISTER_PAYLOAD,
            "email": "not-an-email",
        })
        assert r.status_code == 422

    async def test_register_short_username_422(self, client):
        r = await client.post("/auth/register", json={
            **REGISTER_PAYLOAD,
            "username": "ab",
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


class TestLogin:
    async def test_login_success_returns_token(self, client, registered_user):
        r = await client.post("/auth/login", json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password_401(self, client, registered_user):
        r = await client.post("/auth/login", json={
            "email": registered_user["email"],
            "password": "wrongpassword",
        })
        assert r.status_code == 401

    async def test_login_unknown_email_401(self, client):
        r = await client.post("/auth/login", json={
            "email": "ghost@example.com",
            "password": "password123",
        })
        assert r.status_code == 401

    async def test_login_invalid_email_format_422(self, client):
        r = await client.post("/auth/login", json={
            "email": "not-an-email",
            "password": "password123",
        })
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


class TestMe:
    async def test_me_with_valid_token_200(self, client, auth_headers, registered_user):
        r = await client.get("/auth/me", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == registered_user["email"]
        assert data["username"] == registered_user["username"]
        assert data["is_active"] is True

    async def test_me_without_token_401(self, client):
        r = await client.get("/auth/me")
        assert r.status_code == 401

    async def test_me_with_invalid_token_401(self, client):
        r = await client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401

    async def test_me_with_malformed_bearer_401(self, client):
        r = await client.get("/auth/me", headers={"Authorization": "NotBearer token"})
        assert r.status_code == 401
