"""VoiceProfile value object and VoiceProfileRegistry."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, replace


# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceProfile:
    """
    Immutable voice configuration for a narrative context.

    All parameters map directly to ElevenLabs voice_settings.
    """

    voice_id: str
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speed: float = 1.0
    description: str = ""

    def with_voice_id(self, voice_id: str) -> "VoiceProfile":
        """Return a copy with a different voice_id (for manual overrides)."""
        return replace(self, voice_id=voice_id)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_NPC_POOL = ["tavern", "sage", "villain", "mystery"]


class VoiceProfileRegistry:
    """
    Catalog of all available voice profiles, keyed by narrative context.

    Contexts: narrator, combat, mystery, epic, tavern, sage, villain,
              creature, death, triumph
    """

    def __init__(self, profiles: dict[str, VoiceProfile]) -> None:
        self._profiles = profiles

    def get(self, context: str) -> VoiceProfile | None:
        return self._profiles.get(context)

    def all(self) -> dict[str, VoiceProfile]:
        return dict(self._profiles)

    def available_contexts(self) -> list[str]:
        return list(self._profiles.keys())

    def select_npc_profile(self, npc_name: str, npc_type: str | None) -> VoiceProfile:
        """
        Deterministic NPC voice selection.

        - If npc_type is a known context, return its profile.
        - Otherwise, select from the NPC pool via SHA-256 hash of the name.
          Same NPC name always maps to the same profile.
        """
        if npc_type and npc_type in self._profiles:
            return self._profiles[npc_type]
        index = int(hashlib.sha256(npc_name.encode()).hexdigest(), 16) % len(_NPC_POOL)
        return self._profiles[_NPC_POOL[index]]

    # ------------------------------------------------------------------
    # Factory — loads voice IDs from environment variables
    # ------------------------------------------------------------------

    @classmethod
    def load_from_env(cls) -> "VoiceProfileRegistry":
        """
        Builds the registry from environment variables.
        Falls back to the narrator voice ID when a specific ID is not set.
        """
        narrator_id = os.getenv("VOICE_NARRATOR_ID", os.getenv("GM_VOICE_ID", ""))
        combat_id   = os.getenv("VOICE_COMBAT_ID",   narrator_id)
        mystery_id  = os.getenv("VOICE_MYSTERY_ID",  narrator_id)
        epic_id     = os.getenv("VOICE_EPIC_ID",     narrator_id)
        tavern_id   = os.getenv("VOICE_TAVERN_ID",   os.getenv("NPC_VOICE_ID", narrator_id))
        sage_id     = os.getenv("VOICE_SAGE_ID",     narrator_id)
        villain_id  = os.getenv("VOICE_VILLAIN_ID",  os.getenv("VILLAIN_VOICE_ID", narrator_id))
        creature_id = os.getenv("VOICE_CREATURE_ID", narrator_id)
        death_id    = os.getenv("VOICE_DEATH_ID",    narrator_id)
        triumph_id  = os.getenv("VOICE_TRIUMPH_ID",  narrator_id)

        profiles: dict[str, VoiceProfile] = {
            "narrator": VoiceProfile(
                voice_id=narrator_id,
                stability=0.65, similarity_boost=0.75, style=0.0, speed=1.0,
                description="Narração neutra — exploração e mundo aberto",
            ),
            "mystery": VoiceProfile(
                voice_id=mystery_id,
                stability=0.30, similarity_boost=0.60, style=0.35, speed=0.90,
                description="Dungeons, horror, revelações obscuras — voz instável e lenta",
            ),
            "death": VoiceProfile(
                voice_id=death_id,
                stability=0.45, similarity_boost=0.70, style=0.20, speed=0.80,
                description="Morte, lamento, peso emocional — voz grave e lenta",
            ),
            "combat": VoiceProfile(
                voice_id=combat_id,
                stability=0.35, similarity_boost=0.70, style=0.55, speed=1.15,
                description="Combate ativo, perigo imediato — intenso e acelerado",
            ),
            "epic": VoiceProfile(
                voice_id=epic_id,
                stability=0.40, similarity_boost=0.80, style=0.75, speed=1.05,
                description="Clímax épico, momentos de virada — máxima expressão dramática",
            ),
            "triumph": VoiceProfile(
                voice_id=triumph_id,
                stability=0.50, similarity_boost=0.75, style=0.60, speed=1.10,
                description="Vitória, celebração, conquista — energético e elevado",
            ),
            "tavern": VoiceProfile(
                voice_id=tavern_id,
                stability=0.70, similarity_boost=0.75, style=0.15, speed=1.05,
                description="NPCs comuns, tavernas, conversas cotidianas — relaxado",
            ),
            "sage": VoiceProfile(
                voice_id=sage_id,
                stability=0.80, similarity_boost=0.80, style=0.05, speed=0.92,
                description="Sábios, anciões, divindades — solene e controlado",
            ),
            "villain": VoiceProfile(
                voice_id=villain_id,
                stability=0.55, similarity_boost=0.85, style=0.45, speed=0.95,
                description="Antagonistas, ameaças — frio, calculado, perturbador",
            ),
            "creature": VoiceProfile(
                voice_id=creature_id,
                stability=0.15, similarity_boost=0.55, style=0.80, speed=1.0,
                description="Monstros, entidades — caótico e primitivo",
            ),
        }
        return cls(profiles)
