"""
Schemas Pydantic para a borda HTTP das rotas de Sessão.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PlayerActionRequest(BaseModel):
    session_id: UUID
    player_id: UUID
    action_text: str = Field(..., min_length=1, max_length=4000)
    character_id: Optional[UUID] = None


class SessionResponse(BaseModel):
    id: str
    campaign_id: str
    started_at: Optional[str]
    init_status: str
    has_opening: bool


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    player_id: Optional[str]
    character_id: Optional[str]
    created_at: Optional[str]
