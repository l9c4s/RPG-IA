"""
NarrativeLoopDetector — detecta quando a sessão está presa num padrão repetitivo.

Algoritmo:
  1. Extrai as top-N palavras mais frequentes de cada mensagem do GM (sem stopwords)
  2. Calcula sobreposição (Jaccard) entre pares de mensagens consecutivas
  3. Se a média de sobreposição for >= threshold → loop detectado
  4. Identifica o "tema" dominante (as 3 palavras mais recorrentes entre todas as msgs)

Uso:
    detector = NarrativeLoopDetector()
    result = detector.analyze(last_gm_messages)
    if result.is_loop:
        inject loop_context into GM prompt
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections import Counter
from typing import Sequence


# ─── Stopwords PT-BR (mínimas — apenas as mais comuns para RPG) ───────────────

_STOPWORDS: frozenset[str] = frozenset({
    "a", "o", "e", "de", "do", "da", "dos", "das", "um", "uma", "uns", "umas",
    "em", "no", "na", "nos", "nas", "ao", "à", "pelo", "pela", "pelos", "pelas",
    "para", "por", "com", "sem", "se", "que", "não", "mas", "ou", "como",
    "mais", "já", "ela", "ele", "eles", "elas", "seu", "sua", "seus", "suas",
    "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
    "isso", "isto", "aqui", "ali", "lá", "quando", "onde", "ainda", "também",
    "então", "assim", "apenas", "muito", "bem", "foi", "era", "está", "está",
    "são", "ser", "ter", "fazer", "ir", "vir", "ver", "dar", "ficar", "poder",
    "pode", "seu", "sua", "seus", "suas", "um", "uma", "the", "and", "in",
    "ao", "após", "antes", "entre", "sobre", "contra", "até", "desde",
    "enquanto", "durante", "através", "mediante", "conforme", "segundo",
})

# Threshold de sobreposição Jaccard entre pares → se média >= isso, é loop
# Narrativas de RPG são verbosas: mesmo repetitivas, o vocabulário varia bastante.
# 0.12 detecta loops reais (Érebruma: avg~0.12) sem falsos positivos em sessões variadas.
_JACCARD_THRESHOLD = 0.12

# Mínimo de mensagens para rodar a análise
_MIN_MESSAGES = 4

# Quantas palavras top extrair por mensagem
_TOP_K_WORDS = 15


@dataclass
class LoopAnalysisResult:
    is_loop: bool
    detected_theme: str           # e.g. "guardas / sombras / posição"
    consecutive_rounds: int       # quantas msgs foram analisadas
    avg_overlap: float            # Jaccard médio entre pares
    loop_context: str             # bloco de instrução pronto para injetar no prompt


def _tokenize(text: str) -> list[str]:
    """Tokeniza texto em palavras relevantes (sem stopwords, min 4 chars)."""
    words = re.findall(r'\b[a-záàâãéêíóôõúüçA-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ]{4,}\b', text)
    return [w.lower() for w in words if w.lower() not in _STOPWORDS]


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Similaridade de Jaccard entre dois conjuntos."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


def _extract_top_words(text: str, k: int = _TOP_K_WORDS) -> set[str]:
    tokens = _tokenize(text)
    counter = Counter(tokens)
    return {w for w, _ in counter.most_common(k)}


def _detect_theme(messages: Sequence[str], top_n: int = 4) -> str:
    """Retorna as N palavras mais frequentes em todas as mensagens combinadas."""
    all_tokens: list[str] = []
    for msg in messages:
        all_tokens.extend(_tokenize(msg))
    counter = Counter(all_tokens)
    top = [w for w, _ in counter.most_common(top_n * 2) if len(w) > 4][:top_n]
    return " / ".join(top) if top else "padrão repetitivo"


def _build_loop_context(theme: str, msg_count: int, avg_overlap: float) -> str:
    return (
        f"\n\n⚠️ ALERTA DE LOOP NARRATIVO — INTERVENÇÃO OBRIGATÓRIA:\n"
        f"Os últimos {msg_count} turnos estão presos num padrão repetitivo de [{theme}] "
        f"(similaridade narrativa: {avg_overlap:.0%}).\n"
        "Como Mestre, você DEVE quebrar este ciclo neste turno com uma consequência "
        "DRAMÁTICA e IRREVERSÍVEL. Escolha a mais adequada para a cena:\n\n"
        "1. Os guardas/inimigos detectam definitivamente o grupo → inicie combate com [INIMIGOS:]\n"
        "2. Um evento externo muda tudo: explosão, grito distante, armadilha ativada, fogo\n"
        "3. Um NPC com agência própria interfere — o capitão entra, um aliado aparece\n"
        "4. Consequência acumulada das falhas: use [ESTADO:hp=-5] ou condição [ESTADO:condition=exhausted]\n"
        "5. O ambiente muda irreversivelmente: porta trava, corredor desmorona, luz se apaga\n\n"
        "NÃO continue o mesmo padrão narrativo. Esta rodada MUDA A CENA COMPLETAMENTE.\n"
    )


class NarrativeLoopDetector:
    """
    Detecta loops narrativos analisando sobreposição de vocabulário entre
    as últimas mensagens do GM.
    """

    def __init__(
        self,
        jaccard_threshold: float = _JACCARD_THRESHOLD,
        min_messages: int = _MIN_MESSAGES,
    ) -> None:
        self._threshold = jaccard_threshold
        self._min_messages = min_messages

    def analyze(self, gm_messages: Sequence[str]) -> LoopAnalysisResult:
        """
        Analisa as últimas N mensagens do GM.

        Args:
            gm_messages: Lista de textos do GM, ordenados do mais antigo ao mais recente.

        Returns:
            LoopAnalysisResult com is_loop, detected_theme, loop_context e métricas.
        """
        msgs = [m for m in gm_messages if m and m.strip()]

        if len(msgs) < self._min_messages:
            return LoopAnalysisResult(
                is_loop=False,
                detected_theme="",
                consecutive_rounds=len(msgs),
                avg_overlap=0.0,
                loop_context="",
            )

        # Extrai set de palavras-chave por mensagem
        word_sets = [_extract_top_words(m) for m in msgs]

        # Calcula Jaccard entre cada par consecutivo
        overlaps: list[float] = []
        for i in range(1, len(word_sets)):
            overlaps.append(_jaccard(word_sets[i - 1], word_sets[i]))

        avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0.0
        is_loop = avg_overlap >= self._threshold

        theme = _detect_theme(msgs) if is_loop else ""
        context = _build_loop_context(theme, len(msgs), avg_overlap) if is_loop else ""

        return LoopAnalysisResult(
            is_loop=is_loop,
            detected_theme=theme,
            consecutive_rounds=len(msgs),
            avg_overlap=avg_overlap,
            loop_context=context,
        )

    def build_companion_anti_loop_hint(self, last_actions: Sequence[str]) -> str:
        """
        Retorna uma instrução para injetar no prompt do companion quando ele
        está repetindo as mesmas ações.

        Args:
            last_actions: Últimas ações geradas pelo companion (texto da ação).
        """
        if not last_actions:
            return ""

        # Detecta repetição trivial: mais de 50% das últimas ações são quase idênticas
        tokens_per_action = [frozenset(_tokenize(a)) for a in last_actions]
        if len(tokens_per_action) < 2:
            return ""

        pairs = [
            _jaccard(set(tokens_per_action[i]), set(tokens_per_action[i - 1]))
            for i in range(1, len(tokens_per_action))
        ]
        avg = sum(pairs) / len(pairs)

        if avg < self._threshold:
            return ""

        # Monta a última ação como exemplo a evitar
        last = last_actions[-1][:120] if last_actions else ""
        return (
            "\n\nALERTA ANTI-LOOP: Você repetiu a mesma ação nos últimos turnos. "
            f"Sua última ação foi: \"{last}\". "
            "Desta vez, faça algo COMPLETAMENTE DIFERENTE — confronte diretamente, "
            "use uma habilidade especial, recue, peça ajuda, ou tome uma decisão inesperada. "
            "NÃO repita movimentos furtivos ou espera passiva."
        )
