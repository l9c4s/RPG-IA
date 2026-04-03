"""Domain services for context inference."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Keyword map for automatic context inference
# ---------------------------------------------------------------------------

CONTEXT_KEYWORDS: dict[str, list[str]] = {
    "combat":  ["ataca", "espada", "golpe", "sangue", "luta", "combate", "ferido",
                "dano", "criatura avança", "dispara", "flecha", "magia ofensiva",
                "hp", "morte iminente", "rola para"],
    "mystery": ["sombra", "sussurro", "segredo", "maldição", "dungeon", "escuridão",
                "porta tranca", "runa", "esqueleto", "presença estranha", "frio",
                "horror", "visão", "sonho", "espírito"],
    "villain": ["ameaça", "destruição", "não há esperança", "tolos", "dominação",
                "poder absoluto", "esmagá", "render", "rendição", "obedeçam"],
    "epic":    ["lenda", "profecia", "destino", "herói", "sacrifício", "glória",
                "épico", "mundo trêmulo", "forças do mal", "última batalha", "hora final"],
    "death":   ["morreu", "faleceu", "último suspiro", "alma partiu", "luto",
                "tumba", "sepulcro", "chora", "adeus", "partiu para sempre"],
    "triumph": ["vitória", "venceram", "derrotado", "recompensa", "celebra",
                "sobreviveram", "heróis", "conquista", "missão cumprida"],
    "sage":    ["sábio diz", "anciã", "divindade", "profecia", "ensinamento",
                "minha criança", "tempo é cíclico", "ouve bem", "há muito tempo"],
    "tavern":  ["estalagem", "taberna", "cerveja", "hospedeiro", "boas-vindas",
                "sentem-se", "viajantes", "descansem", "boa noite", "mercador"],
    "creature": ["RRAARRGH", "rugido", "grunhido", "bestial", "garras", "fauces",
                 "monstro", "cria das trevas", "devorar"],
}


class ContextInferenceService:
    """
    Infers the narrative context from text content.

    Counts keyword matches per context and returns the highest-scoring one.
    Falls back to 'narrator' when no keywords match.
    """

    def infer(self, text: str) -> str:
        text_lower = text.lower()
        scores = {
            ctx: sum(1 for kw in keywords if kw in text_lower)
            for ctx, keywords in CONTEXT_KEYWORDS.items()
        }
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else "narrator"
