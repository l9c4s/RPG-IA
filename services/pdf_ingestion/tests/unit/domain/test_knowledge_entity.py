"""Unit tests for knowledge domain entities."""
import pytest
from uuid import UUID, uuid4

from domain.knowledge.entity import ChunkResult, KnowledgeChunk


class TestKnowledgeChunkCreate:
    def test_create_sets_id_and_fields(self):
        source_id = uuid4()
        chunk = KnowledgeChunk.create(
            source_id=source_id,
            chunk_index=0,
            content="The wizard casts fireball.",
            rpg_system="D&D 5e",
        )
        assert isinstance(chunk.id, UUID)
        assert chunk.source_id == source_id
        assert chunk.chunk_index == 0
        assert chunk.content == "The wizard casts fireball."
        assert chunk.rpg_system == "D&D 5e"

    def test_token_count_calculated(self):
        chunk = KnowledgeChunk.create(
            source_id=uuid4(),
            chunk_index=0,
            content="one two three four five",
        )
        assert chunk.token_count == 5

    def test_rpg_system_optional(self):
        chunk = KnowledgeChunk.create(source_id=uuid4(), chunk_index=0, content="text")
        assert chunk.rpg_system is None


class TestChunkResult:
    def test_frozen(self):
        result = ChunkResult(content="x", source_id="abc", rpg_system=None, score=0.1)
        with pytest.raises((TypeError, AttributeError)):
            result.score = 0.5

    def test_fields(self):
        result = ChunkResult(content="text", source_id="id", rpg_system="Pathfinder", score=0.3)
        assert result.content == "text"
        assert result.rpg_system == "Pathfinder"
        assert result.score == 0.3
