"""
Schemas Pydantic para a borda HTTP das rotas de Campanha.
Definem o contrato de request/response da API.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CampaignCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    rpg_system: str = Field(..., min_length=1, max_length=100)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    tone: str = Field(default="heroic", max_length=100)


class CampaignStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(lobby|active|paused|completed|archived)$")


class CampaignResponse(BaseModel):
    id: str
    title: str
    rpg_system: str
    difficulty: str
    tone: str
    status: str
    description: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class LobbyResponse(BaseModel):
    campaign: CampaignResponse
    characters: list[dict]
    can_start: bool
