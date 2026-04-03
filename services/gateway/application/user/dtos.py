"""Application-layer DTOs — pure Python dataclasses, no Pydantic."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class RegisterDTO:
    username: str
    email: str
    password: str


@dataclass
class LoginDTO:
    email: str
    password: str


@dataclass
class UserDTO:
    id: UUID
    username: str
    email: str
    is_active: bool
    created_at: datetime


@dataclass
class TokenDTO:
    access_token: str
    token_type: str = "bearer"
