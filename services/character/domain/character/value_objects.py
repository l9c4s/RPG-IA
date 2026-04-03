from __future__ import annotations

from enum import Enum


class CharacterType(str, Enum):
    PLAYER = "player"
    NPC = "npc"
    AI_COMPANION = "ai_companion"


class AbilityType(str, Enum):
    SPELL = "spell"
    FEATURE = "feature"
    ACTION = "action"
    BONUS_ACTION = "bonus_action"
    REACTION = "reaction"


class RechargeType(str, Enum):
    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"
    DAWN = "dawn"
