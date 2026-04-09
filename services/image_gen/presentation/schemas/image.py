"""Pydantic v2 request/response schemas — presentation layer only."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class GenerateCharacterRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    character_id: UUID | None = None
    campaign_id: UUID | None = None
    style: str = Field("pixel_art", pattern="^(pixel_art|realistic)$")


class GenerateSceneRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    campaign_id: UUID | None = None


class LocationPoint(BaseModel):
    id: str
    name: str
    type: str
    x: float = Field(..., ge=0, le=100)
    y: float = Field(..., ge=0, le=100)
    is_current: bool = False
    discovered: bool = True


class GenerateMapRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    location_id: UUID | None = None
    campaign_id: UUID | None = None
    locations: list[LocationPoint] = []


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ImageResponse(BaseModel):
    image_id: str
    image_url: str | None
    image_type: str
    status: str = "completed"
