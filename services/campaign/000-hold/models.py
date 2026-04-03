from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID


class PlayerAction(BaseModel):
    session_id: UUID
    player_id: UUID
    action_text: str = Field(..., min_length=1, max_length=4000)
    character_id: Optional[UUID] = None


class RollResult(BaseModel):
    expr: str
    result: int
    breakdown: str


class StateUpdate(BaseModel):
    field: str
    value: str


class GMResponse(BaseModel):
    text: str
    roll_results: list[RollResult] = Field(default_factory=list)
    state_updates: list[StateUpdate] = Field(default_factory=list)
    image_url: Optional[str] = None
    audio_url: Optional[str] = None


class CampaignCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    rpg_system: str = Field(..., min_length=1, max_length=100)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    tone: str = Field(default="heroic", max_length=100)


class CampaignStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(lobby|active|paused|completed|archived)$")


class SessionCreate(BaseModel):
    campaign_id: UUID


class MapLocation(BaseModel):
    id: str
    name: str
    description: str
    x: float
    y: float
    type: str
    is_current: bool = False
    discovered: bool = False


class GenerateMapResponse(BaseModel):
    locations: list[MapLocation]
