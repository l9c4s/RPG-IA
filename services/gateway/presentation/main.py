"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.database.connection import init_db
from presentation.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="RPG-IA API Gateway",
        description="Gateway de autenticação e roteamento para a plataforma RPG-IA",
        version="2.0.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth_router)

    @application.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "ok", "service": "gateway"}

    return application


app = create_app()
