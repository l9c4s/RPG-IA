"""Domain services for the knowledge context."""
from __future__ import annotations

from .repository import IAsyncKnowledgeChunkRepository


class KnowledgeGateService:
    """
    Checks whether the GM knowledge bank is ready.

    The GM is considered ready when knowledge_chunks has >= 1 row.
    This must be checked before every LangChain call in the campaign service.
    """

    def __init__(self, repo: IAsyncKnowledgeChunkRepository) -> None:
        self._repo = repo

    async def is_ready(self) -> bool:
        return await self._repo.count() > 0
