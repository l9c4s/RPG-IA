"""DTOs (Data Transfer Objects) para o sistema de rounds."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class StartRoundDTO:
    session_id: UUID
    campaign_id: UUID


@dataclass
class SubmitActionDTO:
    session_id: UUID
    campaign_id: UUID
    character_id: UUID
    character_name: str
    is_pass: bool
    player_id: Optional[UUID] = None    # None = AI companion
    is_ai: bool = False
    action_text: Optional[str] = None   # obrigatório quando is_pass=False


@dataclass
class InitiativeEntryDTO:
    character_name: str
    is_ai: bool
    d20_roll: int
    initiative_order: int
    action_text: Optional[str]
    is_pass: bool
    character_id: Optional[str]


@dataclass
class RoundActionResultDTO:
    character_name: str
    initiative_order: int
    action_text: Optional[str]
    is_pass: bool
    gm_response: Optional[str]
    gm_rolled_dice: bool
    outcome_roll: Optional[int]
    d20_roll: int


@dataclass
class RoundStateDTO:
    round_id: str
    session_id: str
    round_number: int
    status: str
    submitted_count: int
    expected_count: int
    actions: list[InitiativeEntryDTO] = field(default_factory=list)


@dataclass
class SubmitActionResultDTO:
    action_id: str
    round_id: str
    round_number: int
    submitted_count: int
    expected_count: int
    all_submitted: bool


@dataclass
class RoundResolutionDTO:
    round_id: str
    round_number: int
    initiative_board: list[InitiativeEntryDTO]
    results: list[RoundActionResultDTO] = field(default_factory=list)
