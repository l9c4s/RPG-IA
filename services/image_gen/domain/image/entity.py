"""GeneratedImage aggregate root."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from domain.image.value_objects import ImageSize, ImageType, ImageUrl, Prompt


@dataclass
class GeneratedImage:
    id: UUID
    image_type: ImageType
    description: str
    prompt_used: Prompt
    minio_path: str
    image_url: ImageUrl
    character_id: UUID | None
    campaign_id: UUID | None
    location_id: UUID | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        image_type: ImageType,
        description: str,
        prompt: Prompt,
        minio_path: str,
        image_url: ImageUrl,
        character_id: UUID | None = None,
        campaign_id: UUID | None = None,
        location_id: UUID | None = None,
    ) -> "GeneratedImage":
        return cls(
            id=uuid4(),
            image_type=image_type,
            description=description,
            prompt_used=prompt,
            minio_path=minio_path,
            image_url=image_url,
            character_id=character_id,
            campaign_id=campaign_id,
            location_id=location_id,
            created_at=datetime.now(timezone.utc),
        )
