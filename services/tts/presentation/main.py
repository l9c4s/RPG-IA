"""FastAPI application factory for the TTS service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from presentation.dependencies import get_storage, init_registry
from presentation.routers.tts import router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_registry()
    await get_storage().ensure_bucket()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TTS Service",
        description="Síntese de voz dinâmica por intenção narrativa — RPG-IA",
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

    app.include_router(router)
    return app


app = create_app()
