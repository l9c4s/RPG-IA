"""Application DTOs for the knowledge context."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkResultDTO:
    content: str
    source_id: str
    rpg_system: str | None
    score: float


@dataclass(frozen=True)
class ProcessingResultDTO:
    source_id: str
    chunk_count: int
    status: str
