"""KnowledgeChunk entity and ChunkResult value object."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4


@dataclass
class KnowledgeChunk:
    id: UUID
    source_id: UUID
    chunk_index: int
    content: str
    rpg_system: str | None
    token_count: int
    created_at: datetime | None = None

    @classmethod
    def create(
        cls,
        source_id: UUID,
        chunk_index: int,
        content: str,
        rpg_system: str | None = None,
    ) -> "KnowledgeChunk":
        return cls(
            id=uuid4(),
            source_id=source_id,
            chunk_index=chunk_index,
            content=content,
            rpg_system=rpg_system,
            token_count=len(content.split()),
        )


@dataclass(frozen=True)
class ChunkResult:
    """Value object returned by semantic search."""

    content: str
    source_id: str
    rpg_system: str | None
    score: float
