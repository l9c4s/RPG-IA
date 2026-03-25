import os
import io
import uuid
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Depends, HTTPException
from openai import AsyncOpenAI
from minio import Minio
from minio.error import S3Error
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv

from database import GeneratedImageDB, get_db, init_db

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
MINIO_BUCKET: str = "rpg-media"
MEDIA_BASE_URL: str = os.getenv("MEDIA_BASE_URL", "/media")

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

minio_client = Minio(
    endpoint=MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    _ensure_minio_bucket()
    logger.info("Image Generation service started on port 8004")
    yield
    logger.info("Image Generation service shutting down")


def _ensure_minio_bucket() -> None:
    try:
        if not minio_client.bucket_exists(MINIO_BUCKET):
            minio_client.make_bucket(MINIO_BUCKET)
            logger.info("Bucket '%s' criado com sucesso.", MINIO_BUCKET)
        else:
            logger.info("Bucket '%s' já existe.", MINIO_BUCKET)
    except S3Error as exc:
        logger.error("Erro ao verificar/criar bucket MinIO: %s", exc)
        raise


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RPG-IA Image Generation Service",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class GenerateCharacterRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    character_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None


class GenerateSceneRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    campaign_id: uuid.UUID | None = None


class GenerateMapRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    location_id: uuid.UUID | None = None
    campaign_id: uuid.UUID | None = None


class GenerateImageResponse(BaseModel):
    image_url: str
    image_id: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _generate_and_store(
    *,
    image_type: str,
    description: str,
    prompt: str,
    size: str,
    quality: str,
    character_id: uuid.UUID | None,
    campaign_id: uuid.UUID | None,
    location_id: uuid.UUID | None,
    db: AsyncSession,
) -> GenerateImageResponse:
    """Call DALL-E 3, download the image, upload to MinIO and persist the record."""

    # 1. Generate image via DALL-E 3
    try:
        response = await openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,  # type: ignore[arg-type]
            quality=quality,  # type: ignore[arg-type]
            n=1,
            response_format="url",
        )
    except Exception as exc:
        logger.error("Erro ao chamar a API DALL-E 3: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao gerar imagem com DALL-E 3: {exc}",
        )

    openai_url: str = response.data[0].url  # type: ignore[index]

    # 2. Download generated image from OpenAI's temporary URL
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            img_response = await client.get(openai_url)
            img_response.raise_for_status()
            image_bytes: bytes = img_response.content
    except Exception as exc:
        logger.error("Erro ao baixar imagem gerada: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao baixar imagem da OpenAI: {exc}",
        )

    # 3. Upload to MinIO
    image_uuid = uuid.uuid4()
    minio_object_name = f"images/{image_uuid}.png"

    try:
        minio_client.put_object(
            bucket_name=MINIO_BUCKET,
            object_name=minio_object_name,
            data=io.BytesIO(image_bytes),
            length=len(image_bytes),
            content_type="image/png",
        )
    except S3Error as exc:
        logger.error("Erro ao fazer upload para o MinIO: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao armazenar imagem no MinIO: {exc}",
        )

    public_url = f"{MEDIA_BASE_URL}/images/{image_uuid}.png"

    # 4. Persist record to database
    record = GeneratedImageDB(
        id=image_uuid,
        image_type=image_type,
        description=description,
        prompt_used=prompt,
        minio_path=minio_object_name,
        image_url=public_url,
        character_id=character_id,
        campaign_id=campaign_id,
        location_id=location_id,
    )
    db.add(record)
    await db.flush()

    return GenerateImageResponse(
        image_url=public_url,
        image_id=str(image_uuid),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/generate/character",
    response_model=GenerateImageResponse,
    summary="Gerar retrato de personagem",
)
async def generate_character(
    request: GenerateCharacterRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateImageResponse:
    """Gera um retrato de personagem usando DALL-E 3."""
    prompt = (
        f"upper body portrait of {request.description}, "
        "facing slightly left, neutral dark background, "
        "fantasy RPG art style, detailed, No text, no watermarks"
    )
    return await _generate_and_store(
        image_type="character",
        description=request.description,
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        character_id=request.character_id,
        campaign_id=request.campaign_id,
        location_id=None,
        db=db,
    )


@app.post(
    "/generate/npc",
    response_model=GenerateImageResponse,
    summary="Gerar imagem de NPC",
)
async def generate_npc(
    request: GenerateCharacterRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateImageResponse:
    """Gera uma imagem de NPC usando DALL-E 3."""
    prompt = (
        f"upper body portrait of {request.description}, "
        "facing slightly left, neutral dark background, "
        "fantasy RPG art style, detailed, No text, no watermarks"
    )
    return await _generate_and_store(
        image_type="npc",
        description=request.description,
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        character_id=request.character_id,
        campaign_id=request.campaign_id,
        location_id=None,
        db=db,
    )


@app.post(
    "/generate/scene",
    response_model=GenerateImageResponse,
    summary="Gerar ilustração de cena",
)
async def generate_scene(
    request: GenerateSceneRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateImageResponse:
    """Gera uma ilustração de cena usando DALL-E 3."""
    prompt = (
        f"{request.description}, wide establishing shot, "
        "cinematic composition, fantasy RPG art, "
        "dramatic lighting, No text, no watermarks"
    )
    return await _generate_and_store(
        image_type="scene",
        description=request.description,
        prompt=prompt,
        size="1792x1024",
        quality="standard",
        character_id=None,
        campaign_id=request.campaign_id,
        location_id=None,
        db=db,
    )


@app.post(
    "/generate/map",
    response_model=GenerateImageResponse,
    summary="Gerar mapa de localização",
)
async def generate_map(
    request: GenerateMapRequest,
    db: AsyncSession = Depends(get_db),
) -> GenerateImageResponse:
    """Gera um mapa de localização usando DALL-E 3."""
    prompt = (
        f"{request.description}, top-down view, "
        "hand-drawn parchment map style, aged paper texture, "
        "fantasy cartography, No text, no watermarks"
    )
    return await _generate_and_store(
        image_type="map",
        description=request.description,
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        character_id=None,
        campaign_id=request.campaign_id,
        location_id=request.location_id,
        db=db,
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "image_gen"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=False)
