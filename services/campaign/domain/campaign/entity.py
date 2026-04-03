from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4
from typing import Optional

from domain.campaign.value_objects import CampaignStatus, Difficulty, InitStatus


@dataclass
class Campaign:
    """
    Entidade principal do domínio de campanha.
    Representa uma campanha de RPG com todo seu ciclo de vida.
    """

    id: UUID
    title: str
    rpg_system: str
    difficulty: Difficulty
    tone: str
    status: CampaignStatus
    init_status: InitStatus
    opening_generated: bool
    description: Optional[str] = None
    locations_json: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        title: str,
        rpg_system: str,
        difficulty: str,
        tone: str,
        description: Optional[str] = None,
    ) -> "Campaign":
        """Cria uma nova campanha no status inicial (lobby)."""
        return cls(
            id=uuid4(),
            title=title,
            rpg_system=rpg_system,
            difficulty=Difficulty(difficulty),
            tone=tone,
            status=CampaignStatus.LOBBY,
            init_status=InitStatus.IDLE,
            opening_generated=False,
            description=description,
        )

    def activate(self) -> None:
        """Ativa a campanha (lobby → active)."""
        self.status = CampaignStatus.ACTIVE

    def update_status(self, new_status: str) -> None:
        """Altera o status da campanha."""
        self.status = CampaignStatus(new_status)

    def start_generating_opening(self) -> None:
        """Marca que a geração da abertura iniciou."""
        self.init_status = InitStatus.GENERATING

    def mark_opening_ready(self) -> None:
        """Marca a abertura como gerada com sucesso."""
        self.init_status = InitStatus.READY
        self.opening_generated = True

    def mark_opening_failed(self) -> None:
        """Marca falha na geração da abertura."""
        self.init_status = InitStatus.FAILED

    def set_locations(self, locations_json: str) -> None:
        """Salva o JSON dos locais do mapa."""
        self.locations_json = locations_json

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "rpg_system": self.rpg_system,
            "difficulty": self.difficulty.value,
            "tone": self.tone,
            "status": self.status.value,
            "init_status": self.init_status.value,
            "opening_generated": self.opening_generated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
