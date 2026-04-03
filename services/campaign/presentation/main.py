"""
App factory do serviço de Campanha/GM.
Monta routers, middlewares e lifespan. Zero lógica de negócio aqui.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.database.connection import init_db
from presentation.routers import campaigns, gm, sessions
from presentation.websocket import handlers as ws_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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

    # WebSocket
    app.include_router(ws_handlers.router)

    @app.get("/health", status_code=200, tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "service": "campaign"}

    return app


app = create_app()
