"""Integration tests for gateway endpoints."""
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio


# ── /health ───────────────────────────────────────────────────────────────────

async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200


# ── /auth/register ────────────────────────────────────────────────────────────

class TestRegister:
    async def test_register_success(self, client):
        r = await client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data

    async def test_register_duplicate_email(self, client):
        payload = {"username": "user1", "email": "dup@example.com", "password": "pass1234"}
        await client.post("/auth/register", json=payload)
        r = await client.post("/auth/register", json={
            "username": "user2", "email": "dup@example.com", "password": "pass1234"
        })
        assert r.status_code == 400

    async def test_register_duplicate_username(self, client):
        await client.post("/auth/register", json={
            "username": "dupname", "email": "a@example.com", "password": "pass1234"
        })
        r = await client.post("/auth/register", json={
            "username": "dupname", "email": "b@example.com", "password": "pass1234"
        })
        assert r.status_code == 400

    async def test_register_short_password(self, client):
        r = await client.post("/auth/register", json={
            "username": "user1", "email": "x@example.com", "password": "short"
        })
        assert r.status_code == 422

    async def test_register_invalid_email(self, client):
        r = await client.post("/auth/register", json={
            "username": "user1", "email": "not-an-email", "password": "password123"
        })
        assert r.status_code == 422

    async def test_register_short_username(self, client):
        r = await client.post("/auth/register", json={
            "username": "ab", "email": "x@example.com", "password": "password123"
        })
        assert r.status_code == 422


# ── /auth/login ───────────────────────────────────────────────────────────────

class TestLogin:
    async def test_login_success(self, client):
        await client.post("/auth/register", json={
            "username": "loginuser", "email": "login@example.com", "password": "password123"
        })
        r = await client.post("/auth/login", json={
            "email": "login@example.com", "password": "password123"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client):
        await client.post("/auth/register", json={
            "username": "loginuser2", "email": "login2@example.com", "password": "password123"
        })
        r = await client.post("/auth/login", json={
            "email": "login2@example.com", "password": "wrongpass"
        })
        assert r.status_code == 401

    async def test_login_unknown_email(self, client):
        r = await client.post("/auth/login", json={
            "email": "ghost@example.com", "password": "password123"
        })
        assert r.status_code == 401


# ── /auth/me ──────────────────────────────────────────────────────────────────

class TestMe:
    async def test_me_authenticated(self, client):
        await client.post("/auth/register", json={
            "username": "meuser", "email": "me@example.com", "password": "password123"
        })
        login = await client.post("/auth/login", json={
            "email": "me@example.com", "password": "password123"
        })
        token = login.json()["access_token"]

        r = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["email"] == "me@example.com"

    async def test_me_no_token(self, client):
        r = await client.get("/auth/me")
        assert r.status_code == 401

    async def test_me_invalid_token(self, client):
        r = await client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert r.status_code == 401
