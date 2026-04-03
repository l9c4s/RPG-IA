"""
Handler WebSocket para multiplayer em tempo real.
"""

import logging
import os

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

    Clientes se conectam aqui e recebem broadcasts das ações dos jogadores
    e respostas do GM. Mensagens enviadas pelo cliente são rebroadcastadas
    para todos os participantes da mesma sessão.
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
            data["session_id"] = session_id
            await manager.broadcast(session_id, data)
    except WebSocketDisconnect:
        manager.disconnect(session_id, ws)
    except Exception as exc:
        logger.warning("Erro WS session=%s: %s", session_id, exc)
        manager.disconnect(session_id, ws)
