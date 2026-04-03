"""Value objects for the image generation domain."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ImageType(str, Enum):
    character = "character"
    npc = "npc"
    scene = "scene"
    map = "map"


class ImageSize(str, Enum):
    square = "1024x1024"
    wide = "1792x1024"


@dataclass(frozen=True)
class ImageUrl:
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Prompt:
    """Immutable prompt — built via factory methods that encode DALL-E rules."""

    value: str

    def __str__(self) -> str:
        return self.value

    # ------------------------------------------------------------------
    # Factory methods — business rules live here, not in the use cases
    # ------------------------------------------------------------------

    @classmethod
    def build_character(cls, description: str) -> "Prompt":
        return cls(
            f"upper body portrait of {description}, "
            "facing slightly left, neutral dark background, "
            "fantasy RPG art style, detailed, No text, no watermarks"
        )

    @classmethod
    def build_npc(cls, description: str) -> "Prompt":
        return cls(
            f"upper body portrait of {description}, "
            "facing slightly left, neutral dark background, "
            "fantasy RPG art style, detailed, No text, no watermarks"
        )

    @classmethod
    def build_scene(cls, description: str) -> "Prompt":
        return cls(
            f"{description}, wide establishing shot, "
            "cinematic composition, fantasy RPG art, "
            "dramatic lighting, No text, no watermarks"
        )

    @classmethod
    def build_map(cls, description: str) -> "Prompt":
        return cls(
            f"{description}, top-down view, "
            "hand-drawn parchment map style, aged paper texture, "
            "fantasy cartography, No text, no watermarks"
        )
