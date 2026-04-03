from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from infrastructure.database.connection import init_db
from presentation.routers.characters import router as characters_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Banco de dados inicializado com sucesso.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Character Service",
        description="Serviço de personagens para a plataforma RPG-IA (D&D 5e)",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.include_router(characters_router)

    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        return JSONResponse(content={"status": "ok", "service": "character"})

    return app


app = create_app()
