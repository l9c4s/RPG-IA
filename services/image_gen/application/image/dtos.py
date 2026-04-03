"""Application-layer DTOs — pure Python dataclasses, no Pydantic."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


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


@dataclass
class GeneratedImageDTO:
    id: UUID
    image_type: str
    description: str
    image_url: str
    minio_path: str
    character_id: UUID | None
    campaign_id: UUID | None
    location_id: UUID | None
    created_at: datetime
