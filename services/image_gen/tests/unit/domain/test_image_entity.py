"""Unit tests — domain entities and value objects (no DB, no HTTP)."""
import pytest

from domain.image.entity import GeneratedImage
from domain.image.value_objects import ImageSize, ImageType, ImageUrl, Prompt


# ---------------------------------------------------------------------------
# Prompt value object
# ---------------------------------------------------------------------------


class TestPrompt:
    def test_build_character_includes_upper_body(self):
        p = Prompt.build_character("a wizard")
        assert "upper body portrait" in str(p)
        assert "a wizard" in str(p)

    def test_build_character_has_no_watermarks_rule(self):
        p = Prompt.build_character("a warrior")
        assert "No text, no watermarks" in str(p)

    def test_build_npc_has_no_watermarks_rule(self):
        p = Prompt.build_npc("a merchant")
        assert "No text, no watermarks" in str(p)

    def test_build_scene_includes_wide_shot(self):
        p = Prompt.build_scene("a dark dungeon")
        assert "wide establishing shot" in str(p)
        assert "No text, no watermarks" in str(p)

    def test_build_map_includes_top_down(self):
        p = Prompt.build_map("a mountain range")
        assert "top-down view" in str(p)
        assert "parchment" in str(p)
        assert "No text, no watermarks" in str(p)

    def test_prompt_is_frozen(self):
        p = Prompt.build_character("x")
        with pytest.raises((AttributeError, TypeError)):
            p.value = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ImageType & ImageSize
# ---------------------------------------------------------------------------


class TestImageType:
    def test_all_types_defined(self):
        assert set(ImageType) == {
            ImageType.character,
            ImageType.npc,
            ImageType.scene,
            ImageType.map,
        }

    def test_values_are_strings(self):
        assert ImageType.character.value == "character"
        assert ImageType.scene.value == "scene"


class TestImageSize:
    def test_square_value(self):
        assert ImageSize.square.value == "1024x1024"

    def test_wide_value(self):
        assert ImageSize.wide.value == "1792x1024"


# ---------------------------------------------------------------------------
# GeneratedImage entity
# ---------------------------------------------------------------------------


class TestGeneratedImageCreate:
    def _make(self, **overrides):
        defaults = dict(
            image_type=ImageType.character,
            description="a brave knight",
            prompt=Prompt.build_character("a brave knight"),
            minio_path="images/abc.png",
            image_url=ImageUrl("/media/images/abc.png"),
        )
        defaults.update(overrides)
        return GeneratedImage.create(**defaults)

    def test_creates_with_unique_id(self):
        i1 = self._make()
        i2 = self._make()
        assert i1.id != i2.id

    def test_created_at_is_set(self):
        image = self._make()
        assert image.created_at is not None

    def test_optional_fields_default_to_none(self):
        image = self._make()
        assert image.character_id is None
        assert image.campaign_id is None
        assert image.location_id is None

    def test_stores_image_type_correctly(self):
        image = self._make(image_type=ImageType.scene)
        assert image.image_type == ImageType.scene

    def test_stores_prompt_correctly(self):
        prompt = Prompt.build_map("forest")
        image = self._make(prompt=prompt)
        assert str(image.prompt_used) == str(prompt)
