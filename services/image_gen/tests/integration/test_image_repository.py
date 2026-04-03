"""Integration tests — GeneratedImageRepository against real PostgreSQL."""
from uuid import uuid4

import pytest

from domain.image.entity import GeneratedImage
from domain.image.value_objects import ImageType, ImageUrl, Prompt
from infrastructure.repositories.image_repository import GeneratedImageRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_image(
    image_type: ImageType = ImageType.character,
    description: str = "a brave knight",
    campaign_id=None,
) -> GeneratedImage:
    return GeneratedImage.create(
        image_type=image_type,
        description=description,
        prompt=Prompt.build_character(description),
        minio_path=f"images/{uuid4()}.png",
        image_url=ImageUrl("/media/images/test.png"),
        campaign_id=campaign_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSave:
    async def test_save_creates_record(self, db_session):
        repo = GeneratedImageRepository(db_session)
        image = _make_image()
        saved = await repo.save(image)
        assert saved.id == image.id
        assert saved.image_type == ImageType.character
        assert saved.description == "a brave knight"

    async def test_save_returns_domain_entity(self, db_session):
        repo = GeneratedImageRepository(db_session)
        saved = await repo.save(_make_image())
        assert isinstance(saved, GeneratedImage)
        assert saved.created_at is not None


class TestGetById:
    async def test_returns_image_when_found(self, db_session):
        repo = GeneratedImageRepository(db_session)
        image = _make_image()
        await repo.save(image)
        found = await repo.get_by_id(image.id)
        assert found is not None
        assert found.id == image.id
        assert found.image_type == ImageType.character

    async def test_returns_none_when_not_found(self, db_session):
        repo = GeneratedImageRepository(db_session)
        result = await repo.get_by_id(uuid4())
        assert result is None


class TestListByCampaign:
    async def test_returns_images_for_campaign(self, db_session):
        repo = GeneratedImageRepository(db_session)
        campaign_id = uuid4()
        await repo.save(_make_image(campaign_id=campaign_id))
        await repo.save(_make_image(campaign_id=campaign_id))
        await repo.save(_make_image())  # different campaign

        results = await repo.list_by_campaign(campaign_id)
        assert len(results) == 2
        assert all(r.campaign_id == campaign_id for r in results)

    async def test_returns_empty_for_unknown_campaign(self, db_session):
        repo = GeneratedImageRepository(db_session)
        results = await repo.list_by_campaign(uuid4())
        assert results == []

    async def test_different_image_types_returned(self, db_session):
        repo = GeneratedImageRepository(db_session)
        campaign_id = uuid4()
        await repo.save(_make_image(ImageType.character, campaign_id=campaign_id))
        await repo.save(_make_image(ImageType.scene, campaign_id=campaign_id))

        results = await repo.list_by_campaign(campaign_id)
        types = {r.image_type for r in results}
        assert ImageType.character in types
        assert ImageType.scene in types
