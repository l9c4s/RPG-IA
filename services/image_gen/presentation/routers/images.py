"""Image generation router — /generate/* , /images/* e SSE /images/{id}/stream."""
from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from application.image.dtos import (
    GenerateCharacterImageDTO,
    GenerateMapDTO,
    GenerateNpcImageDTO,
    GenerateSceneDTO,
    LocationPointDTO,
)
from application.image.use_cases import (
    FinalizeImageUseCase,
    GenerateCharacterImageUseCase,
    GenerateMapUseCase,
    GenerateNpcImageUseCase,
    GenerateSceneUseCase,
)
from domain.image.value_objects import ImageSize, ImageStatus, ImageUrl, Prompt
from infrastructure.ai.dalle_service import DalleService
from infrastructure.database.connection import AsyncSessionLocal
from infrastructure.repositories.image_repository import GeneratedImageRepository
from infrastructure.storage.minio_service import MinioService
from infrastructure.svg.map_svg_builder import LocationPoint as SvgLocationPoint
from infrastructure.svg.map_svg_builder import build_map_svg
from presentation.dependencies import (
    get_generate_character_uc,
    get_generate_map_uc,
    get_generate_npc_uc,
    get_generate_scene_uc,
    get_image_repo,
)
from presentation.schemas.image import (
    GenerateCharacterRequest,
    GenerateMapRequest,
    GenerateSceneRequest,
    ImageResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Image Generation"])

# ---------------------------------------------------------------------------
# Singletons para background tasks (sessão própria — não depende do request)
# ---------------------------------------------------------------------------
_bg_dalle = DalleService()
_bg_minio = MinioService()

# ---------------------------------------------------------------------------
# In-memory SSE notification bus
# Chave: str(image_id) → asyncio.Event
# Resultado: str(image_id) → dict com status/image_url/error
# ---------------------------------------------------------------------------
_sse_events: dict[str, asyncio.Event] = {}
_sse_results: dict[str, dict] = {}


def _notify(image_id: str, payload: dict) -> None:
    _sse_results[image_id] = payload
    event = _sse_events.get(image_id)
    if event:
        event.set()


# ---------------------------------------------------------------------------
# Background task — cria sessão própria para não depender do request scope
# ---------------------------------------------------------------------------


async def _run_finalize(image_id: UUID, prompt: Prompt, size: ImageSize) -> None:
    """Executa geração de imagem em background com sessão de DB independente."""
    key = str(image_id)
    logger.info("Background task iniciada para imagem %s", key)
    try:
        async with AsyncSessionLocal() as session:
            repo = GeneratedImageRepository(session)
            uc = FinalizeImageUseCase(repo, _bg_dalle, _bg_minio)
            dto = await uc.execute(image_id, prompt, size)
            await session.commit()
        logger.info("Imagem %s gerada com sucesso: %s", key, dto.image_url)
        _notify(key, {"status": "completed", "image_id": key, "image_url": dto.image_url})
    except Exception as exc:
        logger.error("Falha ao gerar imagem %s: %s", key, exc, exc_info=True)
        _notify(key, {"status": "failed", "image_id": key, "error": str(exc)})


async def _run_finalize_map(
    image_id: UUID,
    prompt: Prompt,
    size: ImageSize,
    locations: list[SvgLocationPoint],
) -> None:
    """Gera mapa: DALL-E → PNG → SVG composto com âncoras de localização."""
    key = str(image_id)
    logger.info("Background task de mapa iniciada para imagem %s", key)
    try:
        # 1. Gerar PNG com DALL-E
        image_bytes = await _bg_dalle.generate(prompt, size)

        # 2. Upload PNG no MinIO
        png_name = f"images/{uuid4()}.png"
        png_url = await _bg_minio.upload(image_bytes, png_name)
        logger.info("PNG do mapa salvo em %s", png_url)

        # 3. Construir SVG composto (PNG + âncoras de localização)
        svg_content = build_map_svg(png_url, locations)

        # 4. Upload SVG no MinIO
        svg_name = f"images/{uuid4()}.svg"
        svg_url = await _bg_minio.upload_svg(svg_content, svg_name)
        logger.info("SVG do mapa salvo em %s", svg_url)

        # 5. Persistir no banco (usa o SVG como URL final)
        async with AsyncSessionLocal() as session:
            repo = GeneratedImageRepository(session)
            image = await repo.get_by_id(image_id)
            if image is None:
                raise ValueError(f"Imagem {image_id} não encontrada no banco.")
            image.complete(prompt, svg_name, ImageUrl(svg_url))
            await repo.save(image)
            await session.commit()

        _notify(key, {"status": "completed", "image_id": key, "image_url": svg_url})
    except Exception as exc:
        logger.error("Falha ao gerar mapa %s: %s", key, exc, exc_info=True)
        # Marcar como falha no banco
        try:
            async with AsyncSessionLocal() as session:
                repo = GeneratedImageRepository(session)
                image = await repo.get_by_id(image_id)
                if image:
                    image.fail()
                    await repo.save(image)
                    await session.commit()
        except Exception:
            pass
        _notify(key, {"status": "failed", "image_id": key, "error": str(exc)})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dto_to_response(dto) -> ImageResponse:
    return ImageResponse(
        image_id=str(dto.id),
        image_url=dto.image_url,
        image_type=dto.image_type,
        status=dto.status,
    )


# ---------------------------------------------------------------------------
# SSE stream endpoint
# ---------------------------------------------------------------------------


@router.get("/images/{image_id}/stream")
async def stream_image_status(
    image_id: UUID,
    repo: GeneratedImageRepository = Depends(get_image_repo),
):
    """SSE — envia eventos de status até a imagem estar pronta ou falhar."""

    async def event_generator():
        key = str(image_id)

        # Verifica se já está pronta no banco
        image = await repo.get_by_id(image_id)
        if image and image.status == ImageStatus.completed:
            payload = {"status": "completed", "image_id": key, "image_url": str(image.image_url)}
            yield f"data: {json.dumps(payload)}\n\n"
            return
        if image and image.status == ImageStatus.failed:
            yield f"data: {json.dumps({'status': 'failed', 'image_id': key})}\n\n"
            return

        # Registra event para notificação em tempo real
        event = asyncio.Event()
        _sse_events[key] = event

        # Envia heartbeat inicial
        yield f"data: {json.dumps({'status': 'pending', 'image_id': key})}\n\n"

        try:
            await asyncio.wait_for(event.wait(), timeout=180.0)
            result = _sse_results.get(key, {"status": "failed", "image_id": key})
            yield f"data: {json.dumps(result)}\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'status': 'failed', 'image_id': key, 'error': 'timeout'})}\n\n"
        finally:
            _sse_events.pop(key, None)
            _sse_results.pop(key, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # desliga buffer do nginx
        },
    )


# ---------------------------------------------------------------------------
# GET image by character
# ---------------------------------------------------------------------------


@router.get("/images/character/{character_id}", response_model=ImageResponse)
async def get_character_image(
    character_id: UUID,
    repo: GeneratedImageRepository = Depends(get_image_repo),
):
    image = await repo.get_latest_by_character(character_id)
    if not image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No image found for this character")
    return ImageResponse(
        image_id=str(image.id),
        image_url=str(image.image_url) if image.image_url else None,
        image_type=image.image_type.value,
        status=image.status.value,
    )


# ---------------------------------------------------------------------------
# POST generate/* — retorna pending imediatamente, gera em background
# ---------------------------------------------------------------------------


@router.post("/generate/character", response_model=ImageResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_character(
    body: GenerateCharacterRequest,
    background_tasks: BackgroundTasks,
    uc: GenerateCharacterImageUseCase = Depends(get_generate_character_uc),
):
    try:
        dto = await uc.create_pending(GenerateCharacterImageDTO(
            description=body.description,
            character_id=body.character_id,
            campaign_id=body.campaign_id,
        ))
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    background_tasks.add_task(
        _run_finalize,
        dto.id,
        Prompt.build_character(body.description, style=body.style),
        ImageSize.square,
    )
    return _dto_to_response(dto)


@router.post("/generate/npc", response_model=ImageResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_npc(
    body: GenerateCharacterRequest,
    background_tasks: BackgroundTasks,
    uc: GenerateNpcImageUseCase = Depends(get_generate_npc_uc),
):
    try:
        dto = await uc.create_pending(GenerateNpcImageDTO(
            description=body.description,
            character_id=body.character_id,
            campaign_id=body.campaign_id,
        ))
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    background_tasks.add_task(
        _run_finalize,
        dto.id,
        Prompt.build_npc(body.description),
        ImageSize.square,
    )
    return _dto_to_response(dto)


@router.post("/generate/scene", response_model=ImageResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_scene(
    body: GenerateSceneRequest,
    background_tasks: BackgroundTasks,
    uc: GenerateSceneUseCase = Depends(get_generate_scene_uc),
):
    try:
        dto = await uc.create_pending(GenerateSceneDTO(
            description=body.description,
            campaign_id=body.campaign_id,
        ))
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    background_tasks.add_task(
        _run_finalize,
        dto.id,
        Prompt.build_scene(body.description),
        ImageSize.wide,
    )
    return _dto_to_response(dto)


@router.post("/generate/map", response_model=ImageResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_map(
    body: GenerateMapRequest,
    background_tasks: BackgroundTasks,
    uc: GenerateMapUseCase = Depends(get_generate_map_uc),
):
    try:
        dto = await uc.create_pending(GenerateMapDTO(
            description=body.description,
            location_id=body.location_id,
            campaign_id=body.campaign_id,
            locations=[
                LocationPointDTO(
                    id=loc.id,
                    name=loc.name,
                    type=loc.type,
                    x=loc.x,
                    y=loc.y,
                    is_current=loc.is_current,
                    discovered=loc.discovered,
                )
                for loc in body.locations
            ],
        ))
    except Exception as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    svg_locations = [
        SvgLocationPoint(
            id=loc.id,
            name=loc.name,
            type=loc.type,
            x=loc.x,
            y=loc.y,
            is_current=loc.is_current,
            discovered=loc.discovered,
        )
        for loc in body.locations
    ]

    loc_dicts = [
        {"name": l.name, "type": l.type, "x": l.x, "y": l.y}
        for l in body.locations
    ]
    background_tasks.add_task(
        _run_finalize_map,
        dto.id,
        Prompt.build_map(body.description, loc_dicts),
        ImageSize.wide,
        svg_locations,
    )
    return _dto_to_response(dto)


@router.get("/images/map/campaign/{campaign_id}", response_model=ImageResponse)
async def get_campaign_map(
    campaign_id: UUID,
    repo: GeneratedImageRepository = Depends(get_image_repo),
):
    """Retorna o mapa mais recente (concluído) de uma campanha."""
    image = await repo.get_latest_map_by_campaign(campaign_id)
    if not image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No map found for this campaign")
    return ImageResponse(
        image_id=str(image.id),
        image_url=str(image.image_url) if image.image_url else None,
        image_type=image.image_type.value,
        status=image.status.value,
    )
