"""
Cliente HTTP para o serviço de conhecimento (pdf_ingestion).
Implementa IKnowledgeRetriever via duck typing (Protocol).
"""

import asyncio
import logging
import os

import httpx
from langchain_community.vectorstores import PGVector
from langchain_openai import OpenAIEmbeddings

logger = logging.getLogger(__name__)

KNOWLEDGE_SERVICE_URL: str = os.getenv("KNOWLEDGE_SERVICE_URL", "http://pdf_service:8001")
KNOWLEDGE_GATE_MIN_CHUNKS: int = int(os.getenv("KNOWLEDGE_GATE_MIN_CHUNKS", "3"))
VECTOR_DB_URL: str = os.getenv(
    "VECTOR_DB_URL",
    "postgresql+psycopg2://rpg:rpg@localhost:5432/rpg_campaign",
)


class KnowledgeClient:
    """
    Verifica o knowledge gate e recupera contexto RAG do banco de embeddings.
    Implementa IKnowledgeRetriever via duck typing.
    """

    async def check_gate(self) -> bool:
        """
        Consulta o serviço de conhecimento para verificar se há chunks suficientes.
        Retorna False em caso de falha (fail closed em produção).
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{KNOWLEDGE_SERVICE_URL}/knowledge/stats")
                if resp.status_code == 200:
                    data = resp.json()
                    return int(data.get("total_chunks", 0)) >= KNOWLEDGE_GATE_MIN_CHUNKS
        except Exception as exc:
            logger.warning("Knowledge gate check falhou: %s", exc)
        return False

    async def get_context(self, query: str) -> str:
        """
        Busca os top-4 chunks mais relevantes para a query via PGVector.
        Retorna string vazia em caso de falha.
        """
        try:
            embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=os.getenv("OPENAI_API_KEY"),
            )
            store = PGVector(
                connection_string=VECTOR_DB_URL,
                embedding_function=embeddings,
                collection_name="knowledge_chunks",
            )
            retriever = store.as_retriever(search_kwargs={"k": 4})
            docs = await asyncio.get_event_loop().run_in_executor(
                None, lambda: retriever.invoke(query)
            )
            return "\n\n".join(d.page_content for d in docs)
        except Exception as exc:
            logger.warning("Falha ao buscar contexto RAG: %s", exc)
            return ""
