"""
Banco Global de Conhecimento — Gate e Retriever.

check_gate(db):
    Retorna True se knowledge_chunks contiver ao menos 1 linha.
    Usado pelo GM antes de cada chamada ao LangChain — se False, o GM é bloqueado.

GlobalRetriever.search(query, db, top_k):
    Embeds a query com text-embedding-3-small e retorna os top_k chunks mais
    próximos por distância cosseno (operador <=> do pgvector).
"""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

load_dotenv()

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = "text-embedding-3-small"

# Cliente assíncrono OpenAI (singleton por processo)
_async_openai: AsyncOpenAI | None = None


def _get_async_openai() -> AsyncOpenAI:
    global _async_openai
    if _async_openai is None:
        _async_openai = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _async_openai


# ─── Gate ─────────────────────────────────────────────────────────────────────

async def check_gate(db: AsyncSession) -> bool:
    """
    Verifica se o banco global de conhecimento está populado.

    Returns:
        True  — knowledge_chunks tem >= 1 linha → GM liberado.
        False — tabela vazia → GM bloqueado (não chamar LLM).
    """
    result = await db.execute(
        text("SELECT EXISTS (SELECT 1 FROM knowledge_chunks LIMIT 1) AS has_chunks")
    )
    row = result.mappings().one_or_none()
    if row is None:
        return False
    return bool(row["has_chunks"])


# ─── Retriever ────────────────────────────────────────────────────────────────

class GlobalRetriever:
    """
    Busca semântica no banco global de chunks de PDFs.

    Usa distância cosseno via pgvector (<=> operator) com cast explícito ::vector
    conforme exigido pelo índice IVFFlat.
    """

    async def search(
        self,
        query: str,
        db: AsyncSession,
        top_k: int = 8,
    ) -> list[dict]:
        """
        Embeds a query e retorna os top_k chunks mais relevantes.

        Args:
            query:  Texto da ação/pergunta do jogador.
            db:     Sessão assíncrona do banco de dados.
            top_k:  Número de resultados (padrão: 8, conforme regra de negócio).

        Returns:
            Lista de dicionários com chaves:
              - content    (str)        — texto do chunk
              - source_id  (str)        — UUID da fonte PDF
              - rpg_system (str | None) — sistema de RPG
              - score      (float)      — distância cosseno (0 = idêntico, 2 = oposto)
        """
        if not query.strip():
            logger.warning("[GlobalRetriever] Query vazia recebida — retornando lista vazia.")
            return []

        # Gera embedding da query
        openai_client = _get_async_openai()
        embed_response = await openai_client.embeddings.create(
            input=[query],
            model=EMBEDDING_MODEL,
        )
        query_vector: list[float] = embed_response.data[0].embedding

        # Converte para literal pgvector
        vec_literal = "[" + ",".join(map(str, query_vector)) + "]"

        # Busca por similaridade cosseno com cast explícito ::vector
        result = await db.execute(
            text(
                """
                SELECT
                    kc.content,
                    kc.source_id::text            AS source_id,
                    kc.rpg_system,
                    kc.embedding <=> :vec::vector AS score
                FROM knowledge_chunks kc
                ORDER BY kc.embedding <=> :vec::vector
                LIMIT :top_k
                """
            ),
            {"vec": vec_literal, "top_k": top_k},
        )
        rows = result.mappings().all()

        chunks: list[dict] = [
            {
                "content": row["content"],
                "source_id": row["source_id"],
                "rpg_system": row["rpg_system"],
                "score": float(row["score"]),
            }
            for row in rows
        ]

        logger.info(
            "[GlobalRetriever] Busca concluída — query='%.60s...', top_k=%d, resultados=%d",
            query,
            top_k,
            len(chunks),
        )

        return chunks
