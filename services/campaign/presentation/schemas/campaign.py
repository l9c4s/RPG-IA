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
    ai_players_count: int = Field(default=0, ge=0, le=4, description="Número de jogadores IA gerados automaticamente ao criar a campanha (0–4)")


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
    ai_players_count: int = 0
    ai_players: list[dict] = Field(default_factory=list)


class LobbyResponse(BaseModel):
    campaign: CampaignResponse
    characters: list[dict]
    can_start: bool
