from typing import Protocol
from uuid import UUID

from domain.session.entity import Session, SessionMessage


class ISessionRepository(Protocol):
    """
    Interface para persistência de sessões de jogo.
    """

    async def get_by_id(self, session_id: UUID) -> Session | None:
        """Retorna a sessão pelo ID ou None."""
        ...

    async def get_latest_by_campaign(self, campaign_id: UUID) -> Session | None:
        """Retorna a sessão mais recente de uma campanha ou None."""
        ...

    async def save(self, session: Session) -> Session:
        """Persiste uma sessão e retorna o estado salvo."""
        ...


class IMessageRepository(Protocol):
    """
    Interface para persistência de mensagens de sessão.
    """

    async def save(self, message: SessionMessage) -> None:
        """Persiste uma mensagem de sessão."""
        ...

    async def list_by_session(self, session_id: UUID) -> list[SessionMessage]:
        """Lista todas as mensagens de uma sessão em ordem cronológica."""
        ...
