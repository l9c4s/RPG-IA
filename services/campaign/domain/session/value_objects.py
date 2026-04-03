from enum import Enum


class MessageRole(str, Enum):
    PLAYER = "player"
    GM = "gm"
    GM_OPENING = "gm_opening"
    AI_COMPANION = "ai_companion"
