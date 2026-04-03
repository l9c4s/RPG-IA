"""FastAPI application factory for the pdf_ingestion service."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.database.connection import init_db
from presentation.dependencies import get_minio
from presentation.routers.pdf import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    get_minio().ensure_bucket()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="RPG-IA — PDF Ingestion Service",
        description=(
            "Serviço de ingestão de PDFs: upload para MinIO, extração de texto, "
            "geração de embeddings e armazenamento no banco global de conhecimento."
        ),
        version="1.0.0",
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
