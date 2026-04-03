from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

from domain.session.value_objects import MessageRole


@dataclass
class Session:
    """
    Entidade que representa uma sessão de jogo ativa.
    Uma campanha pode ter múltiplas sessões ao longo do tempo.
    """

    id: UUID
    campaign_id: UUID
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    @classmethod
    def create(cls, campaign_id: UUID) -> "Session":
        """Cria uma nova sessão para uma campanha."""
        return cls(id=uuid4(), campaign_id=campaign_id)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "campaign_id": str(self.campaign_id),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }


@dataclass
class SessionMessage:
    """
    Entidade que representa uma mensagem dentro de uma sessão.
    Pode ser do jogador, do GM, da abertura ou de um companheiro IA.
    """

    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    player_id: Optional[UUID] = None
    character_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        session_id: UUID,
        role: MessageRole,
        content: str,
        player_id: Optional[UUID] = None,
        character_id: Optional[UUID] = None,
    ) -> "SessionMessage":
        """Cria uma nova mensagem de sessão."""
        return cls(
            id=uuid4(),
            session_id=session_id,
            role=role,
            content=content,
            player_id=player_id,
            character_id=character_id,
        )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "role": self.role.value,
            "content": self.content,
            "player_id": str(self.player_id) if self.player_id else None,
            "character_id": str(self.character_id) if self.character_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
