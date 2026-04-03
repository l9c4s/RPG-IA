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


class GenerateSceneRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    campaign_id: UUID | None = None


class GenerateMapRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    location_id: UUID | None = None
    campaign_id: UUID | None = None


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ImageResponse(BaseModel):
    image_id: str
    image_url: str
    image_type: str
