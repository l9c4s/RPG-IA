"""
DTOs para os casos de uso de Sessão.
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class StartSessionDTO:
    campaign_id: UUID


@dataclass
class SessionResponseDTO:
    id: str
    campaign_id: str
    started_at: Optional[str]
    init_status: str
    has_opening: bool


@dataclass
class PlayerActionDTO:
    session_id: UUID
    player_id: UUID
    action_text: str
    character_id: Optional[UUID] = None


@dataclass
class MessageDTO:
    id: str
    session_id: str
    role: str
    content: str
    player_id: Optional[str]
    character_id: Optional[str]
    created_at: Optional[str]
