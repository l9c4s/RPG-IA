"""Application-layer DTOs — pure Python dataclasses, no Pydantic."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class LocationPointDTO:
    id: str
    name: str
    type: str
    x: float
    y: float
    is_current: bool = False
    discovered: bool = True


@dataclass
class GenerateCharacterImageDTO:
    description: str
    character_id: UUID | None = None
    campaign_id: UUID | None = None


@dataclass
class GenerateNpcImageDTO:
    description: str
    character_id: UUID | None = None
    campaign_id: UUID | None = None


@dataclass
class GenerateSceneDTO:
    description: str
    campaign_id: UUID | None = None


@dataclass
class GenerateMapDTO:
    description: str
    location_id: UUID | None = None
    campaign_id: UUID | None = None
    locations: list[LocationPointDTO] = field(default_factory=list)


@dataclass
class GeneratedImageDTO:
    id: UUID
    image_type: str
    description: str
    status: str
    image_url: str | None
    minio_path: str | None
    character_id: UUID | None
    campaign_id: UUID | None
    location_id: UUID | None
    created_at: datetime
