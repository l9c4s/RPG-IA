"""Repository and port interfaces (Protocols) for the image domain."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.image.entity import GeneratedImage
from domain.image.value_objects import ImageSize, Prompt


class IGeneratedImageRepository(Protocol):
    async def save(self, image: GeneratedImage) -> GeneratedImage: ...
    async def get_by_id(self, image_id: UUID) -> GeneratedImage | None: ...
    async def list_by_campaign(self, campaign_id: UUID) -> list[GeneratedImage]: ...


class IImageGeneratorPort(Protocol):
    """Port for DALL-E (or any image generation backend)."""

    async def generate(self, prompt: Prompt, size: ImageSize) -> bytes: ...


class IStoragePort(Protocol):
    """Port for object storage (MinIO / S3)."""

    async def upload(self, data: bytes, object_name: str) -> str:
        """Upload bytes and return the public URL."""
        ...
