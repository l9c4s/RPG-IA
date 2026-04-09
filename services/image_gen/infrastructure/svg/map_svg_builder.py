"""Builds a composite SVG map from a DALL-E PNG URL + location anchor points.

viewBox="0 0 100 100" — location x/y (0-100 percentages) map 1-to-1 to SVG
coordinates, so markers placed by the frontend always align with the stored data.
"""
from __future__ import annotations

from dataclasses import dataclass
from xml.sax.saxutils import escape


@dataclass
class LocationPoint:
    id: str
    name: str
    type: str
    x: float          # 0-100 percentage
    y: float          # 0-100 percentage
    is_current: bool = False
    discovered: bool = True


def build_map_svg(png_url: str, locations: list[LocationPoint]) -> str:
    """Return SVG string embedding the PNG + invisible location anchor nodes."""

    loc_nodes: list[str] = []
    for loc in locations:
        cx = round(loc.x, 4)
        cy = round(loc.y, 4)
        loc_nodes.append(
            f'    <g class="loc"'
            f' data-id="{escape(loc.id)}"'
            f' data-name="{escape(loc.name)}"'
            f' data-type="{escape(loc.type)}"'
            f' data-current="{str(loc.is_current).lower()}"'
            f' data-discovered="{str(loc.discovered).lower()}">'
            f'<circle cx="{cx}" cy="{cy}" r="0.4" fill="transparent"/></g>'
        )

    locations_block = "\n".join(loc_nodes) if loc_nodes else "    <!-- no locations -->"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 100 100"
     preserveAspectRatio="xMidYMid slice"
     data-map-version="1">
  <image href="{escape(png_url)}"
         x="0" y="0" width="100" height="100"
         preserveAspectRatio="xMidYMid slice"/>
  <g id="locations">
{locations_block}
  </g>
</svg>"""
