"""
Handler WebSocket para multiplayer em tempo real.
Aceita mensagens de tipo 'player_action' (turno livre) e 'submit_action' (turno coletivo).
"""

import logging
import os
from uuid import UUID

import jwt as pyjwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from presentation.websocket.connection_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/session/{session_id}/player/{player_id}")
async def websocket_endpoint(
    session_id: str,
    player_id: str,
    ws: WebSocket,
    token: str = Query(...),
) -> None:
    """
    Endpoint WebSocket para multiplayer em tempo real.

    Tipos de mensagem aceitos do cliente:
    - player_action   → ação direta ao GM (turno livre, legado)
    - submit_action   → submissão ao round coletivo com d20

    Mensagens broadcast do servidor:
    - round_started       → novo round iniciado, jogadores podem submeter ações
    - action_submitted    → um jogador submeteu (sem revelar o texto)
    - initiative_board    → d20 rolados, ordem revelada
    - gm_round_response   → GM narrou uma ação específica
    - round_completed     → round encerrado
    - gm_response         → resposta do GM (turno livre)
    - companion_reaction  → reação de companheiro IA
    - state_update        → atualização de status do personagem
    - system_message      → mensagem do sistema
    - gate_blocked        → knowledge gate fechado
    """
    jwt_secret = os.getenv("JWT_SECRET", "")
    try:
        pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
    except pyjwt.PyJWTError:
        await ws.close(code=4001)
        return

    await manager.connect(session_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type", "")
            data["session_id"] = session_id

            if msg_type == "submit_action":
                # Processa submissão de ação ao round via use case
                await _handle_submit_action(session_id, player_id, data)
            else:
                # Para todos os outros tipos, apenas broadcast na sessão
                await manager.broadcast(session_id, data)

    except WebSocketDisconnect:
        manager.disconnect(session_id, ws)
    except Exception as exc:
        logger.warning("Erro WS session=%s: %s", session_id, exc)
        manager.disconnect(session_id, ws)


async def _handle_submit_action(session_id: str, player_id: str, data: dict) -> None:
    """
    Processa submissão de ação via WebSocket.
    Chama SubmitActionUseCase diretamente, com sessão de DB própria.
    O use case faz broadcast dos eventos necessários.
    """
    from infrastructure.database.connection import AsyncSessionLocal
    from infrastructure.external.image_client import CharacterServiceClient
    from infrastructure.repositories.round_repository import RoundRepository
    from infrastructure.repositories.session_repository import SessionRepository
    from application.round.use_cases import SubmitActionUseCase
    from application.round.dtos import SubmitActionDTO

    payload = data.get("payload", {})
    try:
        campaign_id = UUID(payload["campaign_id"])
        character_id = UUID(payload["character_id"])
        is_pass = bool(payload.get("is_pass", False))
        action_text = payload.get("action_text") if not is_pass else None
        character_name = payload.get("character_name", "Jogador")

        async with AsyncSessionLocal() as db:
            uc = SubmitActionUseCase(
                round_repo=RoundRepository(db),
                session_repo=SessionRepository(db),
                character_client=CharacterServiceClient(),
                ws_broadcast_fn=manager.broadcast,
            )
            await uc.execute(
                SubmitActionDTO(
                    session_id=UUID(session_id),
                    campaign_id=campaign_id,
                    character_id=character_id,
                    character_name=character_name,
                    is_pass=is_pass,
                    player_id=UUID(player_id) if player_id else None,
                    is_ai=False,
                    action_text=action_text,
                )
            )
            await db.commit()
    except Exception as exc:
        logger.warning("Falha ao processar submit_action WS session=%s: %s", session_id, exc)
        await manager.broadcast(
            session_id,
            {
                "type": "error",
                "payload": {"message": str(exc)},
            },
        )
