"""
DTOs para os casos de uso do Game Master.
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class GMTurnResultDTO:
    text: str
    roll_results: list[dict]
    state_updates: list[dict]
    image_url: Optional[str] = None
    audio_url: Optional[str] = None


@dataclass
class TriggerOpeningDTO:
    campaign_id: UUID


@dataclass
class OpeningStatusDTO:
    init_status: str
    message: str


@dataclass
class Generate8BitCharacterDTO:
    campaign_id: UUID
    description: str
