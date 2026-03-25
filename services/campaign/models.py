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
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard|deadly)$")
    tone: str = Field(default="heroic", max_length=100)


class SessionCreate(BaseModel):
    campaign_id: UUID
