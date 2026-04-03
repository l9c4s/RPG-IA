"""Pydantic v2 request/response schemas — presentation layer only."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class UserCreateRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        examples=["jogador_01"],
    )
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(str_strip_whitespace=True)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    model_config = ConfigDict(str_strip_whitespace=True)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
