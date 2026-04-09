"""Schemas Pydantic para as rotas HTTP do sistema de rounds."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StartRoundRequest(BaseModel):
    session_id: UUID
    campaign_id: UUID


class SubmitActionRequest(BaseModel):
    session_id: UUID
    campaign_id: UUID
    character_id: UUID
    character_name: str = Field(..., min_length=1, max_length=200)
    is_pass: bool = False
    player_id: Optional[UUID] = None
    action_text: Optional[str] = Field(None, max_length=2000)


class InitiativeEntryResponse(BaseModel):
    character_name: str
    is_ai: bool
    d20_roll: int
    initiative_order: int
    action_text: Optional[str]
    is_pass: bool
    character_id: Optional[str]


class RoundActionResultResponse(BaseModel):
    character_name: str
    initiative_order: int
    action_text: Optional[str]
    is_pass: bool
    gm_response: Optional[str]
    gm_rolled_dice: bool
    outcome_roll: Optional[int]
    d20_roll: int


class RoundStateResponse(BaseModel):
    round_id: str
    session_id: str
    round_number: int
    status: str
    submitted_count: int
    expected_count: int
    actions: list[InitiativeEntryResponse] = []


class SubmitActionResponse(BaseModel):
    action_id: str
    round_id: str
    round_number: int
    submitted_count: int
    expected_count: int
    all_submitted: bool
