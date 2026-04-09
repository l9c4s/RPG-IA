"""Entidades de domínio para o sistema de rounds coletivos."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from domain.round.value_objects import RoundStatus


@dataclass
class RoundAction:
    """
    Ação declarada por um jogador (humano ou IA) em um round.
    Serve também como registro de training data para a IA.
    """

    id: UUID
    round_id: UUID
    session_id: UUID
    character_name: str
    is_ai: bool
    is_pass: bool
    player_id: Optional[UUID] = None
    character_id: Optional[UUID] = None
    action_text: Optional[str] = None
    # Preenchidos na fase de resolução
    d20_roll: Optional[int] = None
    initiative_order: Optional[int] = None
    # Preenchidos após o GM processar
    gm_response: Optional[str] = None
    gm_rolled_dice: Optional[bool] = None
    outcome_roll: Optional[int] = None
    submitted_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        round_id: UUID,
        session_id: UUID,
        character_name: str,
        is_ai: bool,
        is_pass: bool,
        player_id: Optional[UUID] = None,
        character_id: Optional[UUID] = None,
        action_text: Optional[str] = None,
    ) -> "RoundAction":
        if not is_pass and not action_text:
            raise ValueError("action_text é obrigatório quando is_pass=False.")
        return cls(
            id=uuid4(),
            round_id=round_id,
            session_id=session_id,
            character_name=character_name,
            is_ai=is_ai,
            is_pass=is_pass,
            player_id=player_id,
            character_id=character_id,
            action_text=action_text if not is_pass else None,
        )

    def roll_d20(self) -> int:
        """Rola d20 para determinar ordem de iniciativa. Passe sempre = 0."""
        if self.is_pass:
            self.d20_roll = 0
        else:
            self.d20_roll = random.randint(1, 20)
        return self.d20_roll

    def record_gm_outcome(
        self,
        gm_response: str,
        gm_rolled_dice: bool,
        outcome_roll: Optional[int] = None,
    ) -> None:
        self.gm_response = gm_response
        self.gm_rolled_dice = gm_rolled_dice
        self.outcome_roll = outcome_roll

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "round_id": str(self.round_id),
            "session_id": str(self.session_id),
            "player_id": str(self.player_id) if self.player_id else None,
            "character_id": str(self.character_id) if self.character_id else None,
            "character_name": self.character_name,
            "is_ai": self.is_ai,
            "is_pass": self.is_pass,
            "action_text": self.action_text,
            "d20_roll": self.d20_roll,
            "initiative_order": self.initiative_order,
            "gm_response": self.gm_response,
            "gm_rolled_dice": self.gm_rolled_dice,
            "outcome_roll": self.outcome_roll,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
        }


@dataclass
class Round:
    """
    Entidade que representa um round coletivo dentro de uma sessão.
    Um round agrupa as ações de todos os jogadores (humanos + IA) antes
    de enviá-las ao GM para resolução.
    """

    id: UUID
    session_id: UUID
    round_number: int
    status: RoundStatus
    actions: list[RoundAction] = field(default_factory=list)
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @classmethod
    def create(cls, session_id: UUID, round_number: int) -> "Round":
        return cls(
            id=uuid4(),
            session_id=session_id,
            round_number=round_number,
            status=RoundStatus.COLLECTING,
        )

    # ─── Queries ────────────────────────────────────────────────────────────

    def all_submitted(self, expected_count: int) -> bool:
        """Retorna True quando todos os jogadores esperados submeteram."""
        return len(self.actions) >= expected_count

    def character_already_submitted(self, character_id: UUID) -> bool:
        return any(
            a.character_id == character_id for a in self.actions
        )

    def active_actions(self) -> list[RoundAction]:
        """Ações que não são passe, ordenadas por iniciativa."""
        return [a for a in self.actions if not a.is_pass]

    def sorted_by_initiative(self) -> list[RoundAction]:
        """Todas as ações ordenadas por d20 desc (passes no fim)."""
        return sorted(self.actions, key=lambda a: a.d20_roll or 0, reverse=True)

    # ─── Transições de estado ────────────────────────────────────────────────

    def start_resolving(self) -> None:
        if self.status != RoundStatus.COLLECTING:
            raise ValueError(f"Não é possível resolver um round em status '{self.status}'.")
        self.status = RoundStatus.RESOLVING

    def roll_initiative(self) -> list[RoundAction]:
        """
        Rola d20 para cada ação, atribui initiative_order e transita para GM_PROCESSING.
        Retorna a lista ordenada (maior d20 primeiro).
        """
        if self.status != RoundStatus.RESOLVING:
            raise ValueError(f"Iniciativa só pode ser rolada em status 'resolving', não '{self.status}'.")

        for action in self.actions:
            action.roll_d20()

        ordered = sorted(self.actions, key=lambda a: a.d20_roll or 0, reverse=True)
        for i, action in enumerate(ordered):
            action.initiative_order = i + 1

        self.status = RoundStatus.GM_PROCESSING
        return ordered

    def complete(self) -> None:
        if self.status != RoundStatus.GM_PROCESSING:
            raise ValueError(f"Só é possível completar um round em 'gm_processing', não '{self.status}'.")
        self.status = RoundStatus.COMPLETED

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "round_number": self.round_number,
            "status": self.status.value,
            "actions": [a.to_dict() for a in self.actions],
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
