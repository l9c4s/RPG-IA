"""
App factory do serviço de Campanha/GM.
Monta routers, middlewares e lifespan. Zero lógica de negócio aqui.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.database.connection import init_db
from presentation.routers import campaigns, gm, rounds, sessions
from presentation.websocket import handlers as ws_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _recover_stuck_rounds() -> None:
    """
    Ao iniciar, re-dispara rounds presos em 'gm_processing'.
    Isso acontece quando o servidor reinicia durante um round em andamento.
    """
    try:
        from sqlalchemy import text
        from infrastructure.database.connection import AsyncSessionLocal
        from infrastructure.repositories.round_repository import RoundRepository
        from application.round.use_cases import ResolveRoundUseCase
        from presentation.websocket.connection_manager import manager

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text("SELECT id FROM session_rounds WHERE status = 'gm_processing'")
            )
            stuck_ids = [row[0] for row in result.fetchall()]

        if stuck_ids:
            logger.info("Recovery: %d round(s) presos em gm_processing — re-despachando GM.", len(stuck_ids))
            for round_id in stuck_ids:
                from application.round.use_cases import ResolveRoundUseCase
                asyncio.create_task(_redispatch_gm(round_id))
        else:
            logger.info("Recovery: nenhum round preso encontrado.")
    except Exception as exc:
        logger.warning("Recovery de rounds falhou: %s", exc)


async def _redispatch_gm(round_id) -> None:
    """Re-executa o ProcessGMTurnUseCase para um round preso."""
    import os
    from uuid import UUID
    from infrastructure.database.connection import AsyncSessionLocal
    from infrastructure.repositories.round_repository import RoundRepository
    from infrastructure.repositories.session_repository import MessageRepository
    from infrastructure.ai.langchain_gm_service import LangchainGMService
    from infrastructure.external.knowledge_client import KnowledgeClient
    from application.round.use_cases import ProcessGMTurnUseCase
    from presentation.websocket.connection_manager import manager

    vector_db_url = os.getenv(
        "VECTOR_DB_URL",
        "postgresql+psycopg2://rpg_user:change_me_strong_password@postgres:5432/rpg_platform",
    )

    try:
        async with AsyncSessionLocal() as db:
            repo = RoundRepository(db)
            msg_repo = MessageRepository(db)
            gm_svc = LangchainGMService(vector_db_url)
            knowledge = KnowledgeClient()
            uc = ProcessGMTurnUseCase(
                round_repo=repo,
                message_repo=msg_repo,
                gm_service=gm_svc,
                knowledge_retriever=knowledge,
                ws_broadcast_fn=manager.broadcast,
            )
            await uc.execute(UUID(str(round_id)))
            await db.commit()
            logger.info("Recovery: round %s processado com sucesso.", round_id)
    except Exception as exc:
        logger.error("Recovery: falha ao processar round %s: %s", round_id, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(_recover_stuck_rounds())
    logger.info("Campaign/GM service iniciado na porta 8002")
    yield
    logger.info("Campaign/GM service encerrando")


def create_app() -> FastAPI:
    app = FastAPI(
        title="RPG-IA Campaign/GM Service",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers HTTP
    app.include_router(campaigns.router)
    app.include_router(sessions.router)
    app.include_router(gm.router)
    app.include_router(rounds.router)

    # WebSocket
    app.include_router(ws_handlers.router)

    @app.get("/health", status_code=200, tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "service": "campaign"}

    return app


app = create_app()
