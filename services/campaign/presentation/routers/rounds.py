"""
Rotas HTTP do sistema de rounds coletivos.
"""
from __future__ import annotations

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from application.round.dtos import StartRoundDTO, SubmitActionDTO
from application.round.use_cases import StartRoundUseCase, SubmitActionUseCase
from infrastructure.repositories.round_repository import RoundRepository
from presentation.dependencies import get_round_repo, get_start_round_uc, get_submit_action_uc
from presentation.schemas.round import (
    InitiativeEntryResponse,
    StartRoundRequest,
    SubmitActionRequest,
    SubmitActionResponse,
    RoundStateResponse,
)

router = APIRouter(tags=["rounds"])


@router.get(
    "/rounds/active",
    response_model=Optional[RoundStateResponse],
    status_code=status.HTTP_200_OK,
)
async def get_active_round(
    session_id: UUID = Query(...),
    repo: RoundRepository = Depends(get_round_repo),
) -> Optional[RoundStateResponse]:
    """
    Retorna o round ativo da sessão, ou null se não houver nenhum.
    Usado pelo frontend ao carregar a sessão para restaurar o estado do round.
    """
    round_ = await repo.get_active_by_session(session_id)
    if round_ is None:
        return None
    return RoundStateResponse(
        round_id=str(round_.id),
        session_id=str(round_.session_id),
        round_number=round_.round_number,
        status=round_.status.value,
        submitted_count=len(round_.actions),
        expected_count=0,  # frontend atualiza via WS
        actions=[
            InitiativeEntryResponse(
                character_name=a.character_name,
                is_ai=a.is_ai,
                d20_roll=a.d20_roll or 0,
                initiative_order=a.initiative_order or 0,
                action_text=a.action_text,
                is_pass=a.is_pass,
                character_id=str(a.character_id) if a.character_id else None,
            )
            for a in round_.actions
        ],
    )


@router.post(
    "/rounds/start",
    response_model=RoundStateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_round(
    body: StartRoundRequest,
    uc: StartRoundUseCase = Depends(get_start_round_uc),
) -> RoundStateResponse:
    """
    Inicia um novo round coletivo para a sessão.
    Dispara a geração de ações dos AI companions em background.
    Retorna o estado inicial do round (status=collecting).
    """
    try:
        result = await uc.execute(
            StartRoundDTO(
                session_id=body.session_id,
                campaign_id=body.campaign_id,
            )
        )
        return RoundStateResponse(
            round_id=result.round_id,
            session_id=result.session_id,
            round_number=result.round_number,
            status=result.status,
            submitted_count=result.submitted_count,
            expected_count=result.expected_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao iniciar o round.",
        )


@router.post(
    "/rounds/{round_id}/dispatch-gm",
    status_code=status.HTTP_202_ACCEPTED,
)
async def dispatch_gm(
    round_id: UUID,
    repo: RoundRepository = Depends(get_round_repo),
) -> dict:
    """
    Re-despacha o ProcessGMTurnUseCase para um round preso em gm_processing.
    Chamado pelo frontend quando detecta gm_processing ao carregar a sessão.
    """
    import asyncio
    from uuid import UUID as _UUID
    from infrastructure.repositories.session_repository import MessageRepository
    from infrastructure.ai.langchain_gm_service import LangchainGMService
    from infrastructure.external.knowledge_client import KnowledgeClient
    from application.round.use_cases import ProcessGMTurnUseCase
    from presentation.websocket.connection_manager import manager
    from infrastructure.database.connection import AsyncSessionLocal

    round_ = await repo.get_by_id(round_id)
    if round_ is None:
        raise HTTPException(status_code=404, detail="Round não encontrado.")
    if round_.status.value != "gm_processing":
        return {"detail": f"Round está em '{round_.status.value}', não precisa de dispatch."}

    async def _run():
        import os
        vector_db_url = os.getenv(
            "VECTOR_DB_URL",
            "postgresql+psycopg2://rpg_user:change_me_strong_password@postgres:5432/rpg_platform",
        )
        try:
            async with AsyncSessionLocal() as db:
                from infrastructure.repositories.round_repository import RoundRepository as RR
                r = RR(db)
                msg_repo = MessageRepository(db)
                gm_svc = LangchainGMService(vector_db_url)
                knowledge = KnowledgeClient()
                uc = ProcessGMTurnUseCase(
                    round_repo=r,
                    message_repo=msg_repo,
                    gm_service=gm_svc,
                    knowledge_retriever=knowledge,
                    ws_broadcast_fn=manager.broadcast,
                )
                await uc.execute(round_id)
                await db.commit()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("dispatch-gm falhou para round %s: %s", round_id, exc)

    asyncio.create_task(_run())
    return {"detail": "GM dispatched", "round_id": str(round_id)}


@router.post(
    "/rounds/submit",
    response_model=SubmitActionResponse,
    status_code=status.HTTP_200_OK,
)
async def submit_action(
    body: SubmitActionRequest,
    uc: SubmitActionUseCase = Depends(get_submit_action_uc),
) -> SubmitActionResponse:
    """
    Submete a ação de um jogador para o round ativo.
    Quando todos os jogadores submeteram, dispara automaticamente a resolução
    (rolagem de d20 + narração do GM).
    """
    try:
        result = await uc.execute(
            SubmitActionDTO(
                session_id=body.session_id,
                campaign_id=body.campaign_id,
                character_id=body.character_id,
                character_name=body.character_name,
                is_pass=body.is_pass,
                player_id=body.player_id,
                is_ai=False,
                action_text=body.action_text,
            )
        )
        return SubmitActionResponse(
            action_id=result.action_id,
            round_id=result.round_id,
            round_number=result.round_number,
            submitted_count=result.submitted_count,
            expected_count=result.expected_count,
            all_submitted=result.all_submitted,
        )
    except ValueError as exc:
        code = (
            status.HTTP_409_CONFLICT
            if "já submeteu" in str(exc) or "round ativo" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(exc))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao submeter ação.",
        )
