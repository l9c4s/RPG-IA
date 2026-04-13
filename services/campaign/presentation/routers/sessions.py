"""
Rotas HTTP de Sessão — borda da aplicação.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from application.session.dtos import PlayerActionDTO, StartSessionDTO
from application.session.use_cases import (
    GetCurrentSessionUseCase,
    GetSessionMessagesUseCase,
    ProcessPlayerTurnUseCase,
    StartCampaignSessionUseCase,
)
from infrastructure.database.connection import get_db
from infrastructure.database.orm_models import CampaignStateORM, SessionORM
from infrastructure.repositories.combat_repository import CombatRepository
from presentation.background_tasks import run_opening_background
from presentation.dependencies import (
    get_current_session_uc,
    get_process_turn_uc,
    get_session_messages_uc,
    get_start_session_uc,
)
from presentation.schemas.gm import GMResponseSchema, RollResultResponse, StateUpdateResponse
from presentation.schemas.session import (
    MessageResponse,
    PlayerActionRequest,
    SessionResponse,
)

router = APIRouter(tags=["sessions"])


@router.post("/session/action", response_model=GMResponseSchema, status_code=status.HTTP_200_OK)
async def session_action(
    body: PlayerActionRequest,
    uc: ProcessPlayerTurnUseCase = Depends(get_process_turn_uc),
) -> GMResponseSchema:
    """Turno do GM: processa a ação do jogador e retorna resposta estruturada."""
    try:
        result = await uc.execute(
            PlayerActionDTO(
                session_id=body.session_id,
                player_id=body.player_id,
                action_text=body.action_text,
                character_id=body.character_id,
            )
        )
        return GMResponseSchema(
            text=result.text,
            roll_results=[
                RollResultResponse(expr=r.expr, result=r.result, breakdown=r.breakdown)
                for r in result.roll_results
            ],
            state_updates=[
                StateUpdateResponse(field=s.field, value=s.value)
                for s in result.state_updates
            ],
            image_url=result.image_url,
            audio_url=result.audio_url,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar a ação com o GM.",
        )


@router.post(
    "/campaigns/{campaign_id}/sessions/start",
    status_code=status.HTTP_201_CREATED,
)
async def start_campaign_session(
    campaign_id: UUID,
    background_tasks: BackgroundTasks,
    start_uc: StartCampaignSessionUseCase = Depends(get_start_session_uc),
) -> SessionResponse:
    """Inicia uma nova sessão e dispara a abertura em background se necessário."""
    try:
        result = await start_uc.execute(StartSessionDTO(campaign_id=campaign_id))
        if not result.has_opening:
            background_tasks.add_task(
                run_opening_background, campaign_id, UUID(result.id)
            )
        return SessionResponse(**vars(result))
    except ValueError as exc:
        code = (
            status.HTTP_400_BAD_REQUEST
            if "personagem" in str(exc).lower() or "status" in str(exc).lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=str(exc))


@router.get(
    "/campaigns/{campaign_id}/sessions/current",
    status_code=status.HTTP_200_OK,
)
async def get_current_session(
    campaign_id: UUID,
    uc: GetCurrentSessionUseCase = Depends(get_current_session_uc),
) -> SessionResponse:
    try:
        result = await uc.execute(campaign_id)
        return SessionResponse(**vars(result))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/sessions/{session_id}/state", status_code=status.HTTP_200_OK)
async def get_session_state(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Retorna o estado atual da sessão: modo (exploration/combat), inimigos vivos
    e cena atual. Chamado pelo frontend sempre que recebe 'session_state_changed'.
    """
    combat_repo = CombatRepository(db)

    # Estado de combate
    in_combat = False
    enemies: list[dict] = []
    try:
        encounter = await combat_repo.get_active_encounter(session_id)
        if encounter:
            alive = await combat_repo.get_alive_enemies(encounter.id)
            if alive:
                in_combat = True
                enemies = [
                    {
                        "name": e.display_name,
                        "slug": e.slug,
                        "hp_current": e.hp_current,
                        "hp_max": e.hp_max,
                    }
                    for e in alive
                ]
    except Exception:
        pass

    # Cena atual — via campaign_state da sessão
    current_scene: str | None = None
    try:
        session_row = await db.get(SessionORM, session_id)
        if session_row:
            result = await db.execute(
                select(CampaignStateORM).where(
                    CampaignStateORM.campaign_id == session_row.campaign_id
                )
            )
            state_orm = result.scalar_one_or_none()
            if state_orm:
                current_scene = state_orm.current_scene
    except Exception:
        pass

    return {
        "session_mode": "combat" if in_combat else "exploration",
        "combat": {
            "in_combat": in_combat,
            "enemies": enemies,
        },
        "current_scene": current_scene,
    }


@router.get("/sessions/{session_id}/messages", status_code=status.HTTP_200_OK)
async def get_session_messages(
    session_id: UUID,
    uc: GetSessionMessagesUseCase = Depends(get_session_messages_uc),
) -> list[MessageResponse]:
    messages = await uc.execute(session_id)
    return [MessageResponse(**vars(m)) for m in messages]
