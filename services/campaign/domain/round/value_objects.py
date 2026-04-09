"""Value objects do domínio de rounds."""
from __future__ import annotations

from enum import Enum


class RoundStatus(str, Enum):
    COLLECTING    = "collecting"     # aguardando ações de todos os jogadores
    RESOLVING     = "resolving"      # rolando d20 e ordenando iniciativa
    GM_PROCESSING = "gm_processing"  # GM narrando ações em ordem de iniciativa
    COMPLETED     = "completed"      # round encerrado
