"""
DTOs de entrada e saída para os casos de uso de Campanha.
São dataclasses simples — sem dependência de FastAPI ou SQLAlchemy.
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class CreateCampaignDTO:
    title: str
    rpg_system: str
    difficulty: str
    tone: str
    description: Optional[str] = None


@dataclass
class UpdateCampaignStatusDTO:
    campaign_id: UUID
    new_status: str


@dataclass
class CampaignResponseDTO:
    id: str
    title: str
    rpg_system: str
    difficulty: str
    tone: str
    status: str
    description: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


@dataclass
class LobbyResponseDTO:
    campaign: CampaignResponseDTO
    characters: list[dict]
    can_start: bool


@dataclass
class AddAIPlayerDTO:
    campaign_id: UUID


@dataclass
class GenerateMapDTO:
    campaign_id: UUID
