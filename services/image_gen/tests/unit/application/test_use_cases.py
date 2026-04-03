"""Unit tests — application use cases (AsyncMock, no DB, no HTTP)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from application.image.dtos import (
    GenerateCharacterImageDTO,
    GenerateMapDTO,
    GenerateNpcImageDTO,
    GenerateSceneDTO,
)
from application.image.use_cases import (
    GenerateCharacterImageUseCase,
    GenerateMapUseCase,
    GenerateNpcImageUseCase,
    GenerateSceneUseCase,
)
from domain.image.value_objects import ImageSize, ImageType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_BYTES = b"\x89PNG\r\n\x1a\n"  # minimal PNG header
_FAKE_URL = "/media/images/fake-uuid.png"


def _make_generator(fail: bool = False) -> AsyncMock:
    g = AsyncMock()
    if fail:
        g.generate.side_effect = RuntimeError("DALL-E unavailable")
    else:
        g.generate.return_value = _FAKE_BYTES
    return g


def _make_storage() -> AsyncMock:
    s = AsyncMock()
    s.upload.return_value = _FAKE_URL
    return s


def _make_repo() -> AsyncMock:
    r = AsyncMock()
    r.save.side_effect = lambda img: img
    return r


# ---------------------------------------------------------------------------
# GenerateCharacterImageUseCase
# ---------------------------------------------------------------------------


class TestGenerateCharacterImageUseCase:
    async def test_returns_dto_with_correct_type(self):
        uc = GenerateCharacterImageUseCase(
            repo=_make_repo(), generator=_make_generator(), storage=_make_storage()
        )
        dto = await uc.execute(GenerateCharacterImageDTO(description="a knight"))
        assert dto.image_type == ImageType.character.value

    async def test_calls_generator_with_square_size(self):
        gen = _make_generator()
        uc = GenerateCharacterImageUseCase(
            repo=_make_repo(), generator=gen, storage=_make_storage()
        )
        await uc.execute(GenerateCharacterImageDTO(description="a knight"))
        call_args = gen.generate.call_args
        assert call_args.kwargs["size"] == ImageSize.square or call_args.args[1] == ImageSize.square

    async def test_saves_to_repo(self):
        repo = _make_repo()
        uc = GenerateCharacterImageUseCase(
            repo=repo, generator=_make_generator(), storage=_make_storage()
        )
        await uc.execute(GenerateCharacterImageDTO(description="a mage"))
        repo.save.assert_called_once()

    async def test_generator_error_propagates(self):
        uc = GenerateCharacterImageUseCase(
            repo=_make_repo(), generator=_make_generator(fail=True), storage=_make_storage()
        )
        with pytest.raises(RuntimeError):
            await uc.execute(GenerateCharacterImageDTO(description="a paladin"))

    async def test_image_url_from_storage(self):
        storage = _make_storage()
        storage.upload.return_value = "/media/images/custom.png"
        uc = GenerateCharacterImageUseCase(
            repo=_make_repo(), generator=_make_generator(), storage=storage
        )
        dto = await uc.execute(GenerateCharacterImageDTO(description="a ranger"))
        assert dto.image_url == "/media/images/custom.png"


# ---------------------------------------------------------------------------
# GenerateSceneUseCase
# ---------------------------------------------------------------------------


class TestGenerateSceneUseCase:
    async def test_returns_dto_with_scene_type(self):
        uc = GenerateSceneUseCase(
            repo=_make_repo(), generator=_make_generator(), storage=_make_storage()
        )
        dto = await uc.execute(GenerateSceneDTO(description="a dark forest"))
        assert dto.image_type == ImageType.scene.value

    async def test_calls_generator_with_wide_size(self):
        gen = _make_generator()
        uc = GenerateSceneUseCase(
            repo=_make_repo(), generator=gen, storage=_make_storage()
        )
        await uc.execute(GenerateSceneDTO(description="a battlefield"))
        call_args = gen.generate.call_args
        size_arg = call_args.kwargs.get("size") or call_args.args[1]
        assert size_arg == ImageSize.wide


# ---------------------------------------------------------------------------
# GenerateMapUseCase
# ---------------------------------------------------------------------------


class TestGenerateMapUseCase:
    async def test_returns_dto_with_map_type(self):
        uc = GenerateMapUseCase(
            repo=_make_repo(), generator=_make_generator(), storage=_make_storage()
        )
        dto = await uc.execute(GenerateMapDTO(description="a dungeon layout"))
        assert dto.image_type == ImageType.map.value

    async def test_calls_generator_with_square_size(self):
        gen = _make_generator()
        uc = GenerateMapUseCase(
            repo=_make_repo(), generator=gen, storage=_make_storage()
        )
        await uc.execute(GenerateMapDTO(description="a city"))
        call_args = gen.generate.call_args
        size_arg = call_args.kwargs.get("size") or call_args.args[1]
        assert size_arg == ImageSize.square


# ---------------------------------------------------------------------------
# GenerateNpcImageUseCase
# ---------------------------------------------------------------------------


class TestGenerateNpcImageUseCase:
    async def test_returns_dto_with_npc_type(self):
        uc = GenerateNpcImageUseCase(
            repo=_make_repo(), generator=_make_generator(), storage=_make_storage()
        )
        dto = await uc.execute(GenerateNpcImageDTO(description="a tavern keeper"))
        assert dto.image_type == ImageType.npc.value
