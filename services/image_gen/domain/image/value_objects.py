"""Value objects for the image generation domain."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ImageType(str, Enum):
    character = "character"
    npc = "npc"
    scene = "scene"
    map = "map"


class ImageStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


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
    def build_character(cls, description: str, style: str = "pixel_art") -> "Prompt":
        if style == "pixel_art":
            return cls(
                f"8-bit pixel art portrait of {description}, "
                "retro RPG video game sprite, pixelated, solid flat colors, "
                "no gradients, no shading, bold outlines, "
                "neutral dark background, No text, no watermarks"
            )
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
    def build_map(
        cls,
        description: str,
        locations: list[dict] | None = None,
    ) -> "Prompt":
        """Gera prompt de mapa com dicas posicionais por local.

        ``locations`` é uma lista de dicts com keys:
        ``name``, ``type``, ``x`` (0-100), ``y`` (0-100).
        As coordenadas são convertidas em referências de quadrante para
        guiar o DALL-E a colocar cada elemento no lugar certo.
        """
        location_section = ""
        if locations:
            hints: list[str] = []
            for loc in locations:
                x, y = float(loc.get("x", 50)), float(loc.get("y", 50))
                h = "left side" if x < 33 else ("right side" if x > 66 else "center")
                v = "top" if y < 33 else ("bottom" if y > 66 else "middle"  )
                hints.append(
                    f"{loc['name']} ({loc['type']}) placed in the {v} {h}"
                )
            location_section = (
                "Specific locations to place on the map — follow positions carefully: "
                + "; ".join(hints)
                + ". "
            )

        return cls(
            f"Fantasy RPG world map — {description}. "
            f"{location_section}"
            "Overhead cartographic illustration, hand-drawn ink style on aged parchment paper, "
            "sepia and earth tones with muted greens and blues. "
            "Large continent with irregular coastlines surrounded by ocean with waves. "
            "Multiple distinct biomes: snow-capped mountain ranges, dense forests with individual trees, "
            "open plains and grasslands, swamps, deserts, and river deltas flowing to sea. "
            "Scattered walled cities and villages illustrated as small detailed icons. "
            "Winding roads and rivers connecting regions. "
            "Decorative compass rose in one corner, ornate double-line border frame. "
            "Isometric-style terrain icons, classic D&D cartography aesthetic, "
            "cinematic fantasy atlas quality. No readable text, no watermarks."
        )
