"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from infrastructure.database.connection import init_db
from infrastructure.storage.minio_service import MinioService
from presentation.routers.images import router as images_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    MinioService().ensure_bucket()
    logger.info("Image Generation service started.")
    yield
    logger.info("Image Generation service shutting down.")


def create_app() -> FastAPI:
    application = FastAPI(
        title="RPG-IA Image Generation Service",
        version="2.0.0",
        lifespan=lifespan,
    )

    application.include_router(images_router)

    @application.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "service": "image_gen"}

    return application


app = create_app()
