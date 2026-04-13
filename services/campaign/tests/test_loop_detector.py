"""
Testes unitários do NarrativeLoopDetector.

Cobrem:
  - Detecção positiva de loop (alta sobreposição)
  - Ausência de loop (mensagens variadas)
  - Abaixo do mínimo de mensagens → nunca dispara
  - Conteúdo do loop_context (instrução de intervenção)
  - build_companion_anti_loop_hint
  - Funções internas: _tokenize, _jaccard, _extract_top_words, _detect_theme
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from infrastructure.ai.loop_detector import (
    NarrativeLoopDetector,
    LoopAnalysisResult,
    _tokenize,
    _jaccard,
    _extract_top_words,
    _detect_theme,
)


# ─── Dados de teste ────────────────────────────────────────────────────────────

# Mensagens com alto vocabulário repetitivo (padrão da campanha com problema)
LOOP_MESSAGES = [
    "Elara Swiftfoot se move habilmente pelas sombras, cada passo calculado. "
    "Ela encontra um ponto de vantagem e aguarda os guardas silenciosamente.",
    "Elara Swiftfoot tenta se posicionar nas sombras novamente, movendo-se "
    "silenciosamente pelas sombras para aguardar os guardas.",
    "Elara Swiftfoot falha ao tentar se mover para as sombras, tropeçando "
    "e alertando os guardas que patrulham silenciosamente.",
    "Elara Swiftfoot encontra nova posição nas sombras, aguardando silenciosamente "
    "enquanto os guardas passam pelo corredor.",
    "Elara Swiftfoot se move furtivamente pelas sombras, posicionando-se "
    "para surpreender os guardas quando passarem.",
    "Elara Swiftfoot aguarda silenciosamente nas sombras, preparada para "
    "surpreender os guardas com suas adagas.",
]

# Mensagens variadas — sem loop
VARIED_MESSAGES = [
    "Os aventureiros chegam à taverna e encontram o velho mago Thalindor.",
    "Uma batalha épica começa quando o dragão negro desce das nuvens tempestuosas.",
    "Aria lança um feitiço de telepatia para descobrir os segredos do rei.",
    "O grupo encontra um mapa antigo que revela a localização do artefato perdido.",
    "Thorin negocia com os anões da montanha pela liberação do prisioneiro élfico.",
    "A explosão da bomba alquímica destrói a ponte e corta a rota de fuga.",
]

# Menos que o mínimo de mensagens
FEW_MESSAGES = [
    "Elara se move pelas sombras aguardando os guardas.",
    "Elara aguarda nas sombras.",
]

# Mensagens com loop mas com detector personalizado (threshold baixo)
MILD_LOOP_MESSAGES = [
    "O grupo avança pelo corredor escuro com cautela extrema.",
    "O grupo continua avançando pelo corredor escuro com muita cautela.",
    "O grupo caminha pelo corredor escuro em silêncio absoluto.",
    "O grupo se move lentamente pelo corredor escuro e silencioso.",
]


# ─── Testes: _tokenize ─────────────────────────────────────────────────────────

class TestTokenize:
    def test_remove_stopwords(self):
        tokens = _tokenize("ela se move para as sombras")
        assert "para" not in tokens
        assert "sombras" in tokens

    def test_remove_short_words(self):
        tokens = _tokenize("ela vai lá ver")
        # Palavras com < 4 chars são removidas
        assert all(len(t) >= 4 for t in tokens)

    def test_lowercase(self):
        tokens = _tokenize("Elara Swiftfoot SOMBRAS")
        assert all(t == t.lower() for t in tokens)

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_punctuation_ignored(self):
        tokens = _tokenize("movimento! furtivo, sombras.")
        assert "movimento" in tokens
        assert "furtivo" in tokens
        assert "sombras" in tokens

    def test_accented_words(self):
        tokens = _tokenize("posição masmorra labirinto")
        assert "posição" in tokens or "masmorra" in tokens


# ─── Testes: _jaccard ──────────────────────────────────────────────────────────

class TestJaccard:
    def test_identical_sets(self):
        s = {"sombras", "guardas", "elara"}
        assert _jaccard(s, s) == 1.0

    def test_disjoint_sets(self):
        a = {"sombras", "guardas"}
        b = {"dragão", "magia"}
        assert _jaccard(a, b) == 0.0

    def test_partial_overlap(self):
        a = {"sombras", "guardas", "elara"}
        b = {"sombras", "guardas", "dragão"}
        # intersect=2, union=4 → 0.5
        assert _jaccard(a, b) == pytest.approx(0.5)

    def test_empty_sets(self):
        assert _jaccard(set(), set()) == 0.0
        assert _jaccard({"word"}, set()) == 0.0


# ─── Testes: _extract_top_words ────────────────────────────────────────────────

class TestExtractTopWords:
    def test_returns_most_frequent(self):
        text = "sombras sombras sombras guardas guardas elara"
        words = _extract_top_words(text, k=2)
        assert "sombras" in words

    def test_max_k_words(self):
        text = " ".join(f"palavra_{i}" for i in range(20))
        words = _extract_top_words(text, k=5)
        assert len(words) <= 5

    def test_empty_text(self):
        assert _extract_top_words("") == set()


# ─── Testes: _detect_theme ─────────────────────────────────────────────────────

class TestDetectTheme:
    def test_returns_dominant_words(self):
        messages = [
            "sombras guardas movimento silencioso",
            "sombras guardas posição furtiva",
            "sombras guardas emboscada silenciosa",
        ]
        theme = _detect_theme(messages)
        # "sombras" e "guardas" devem aparecer no tema
        assert "sombras" in theme or "guardas" in theme

    def test_returns_string(self):
        theme = _detect_theme(LOOP_MESSAGES)
        assert isinstance(theme, str)
        assert len(theme) > 0

    def test_empty_messages(self):
        theme = _detect_theme([])
        assert isinstance(theme, str)


# ─── Testes: NarrativeLoopDetector.analyze ─────────────────────────────────────

class TestNarrativeLoopDetectorAnalyze:

    def setup_method(self):
        self.detector = NarrativeLoopDetector()

    # --- Retorno tipado ---

    def test_returns_loop_analysis_result(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        assert isinstance(result, LoopAnalysisResult)

    # --- Loop detectado ---

    def test_detects_loop_in_repetitive_messages(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        assert result.is_loop is True

    def test_loop_has_detected_theme(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        assert result.detected_theme != ""
        assert len(result.detected_theme) > 0

    def test_loop_has_nonempty_context(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        assert result.loop_context != ""
        assert "LOOP NARRATIVO" in result.loop_context
        assert "INTERVENÇÃO OBRIGATÓRIA" in result.loop_context

    def test_loop_context_mentions_inimigos_tag(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        assert "[INIMIGOS:]" in result.loop_context

    def test_loop_avg_overlap_is_high(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        # LOOP_MESSAGES foram projetadas para alta sobreposição (well above threshold)
        assert result.avg_overlap >= 0.12

    def test_loop_consecutive_rounds_count(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        assert result.consecutive_rounds == len(LOOP_MESSAGES)

    # --- Sem loop ---

    def test_no_loop_in_varied_messages(self):
        result = self.detector.analyze(VARIED_MESSAGES)
        assert result.is_loop is False

    def test_no_loop_has_empty_context(self):
        result = self.detector.analyze(VARIED_MESSAGES)
        assert result.loop_context == ""

    def test_no_loop_has_empty_theme(self):
        result = self.detector.analyze(VARIED_MESSAGES)
        assert result.detected_theme == ""

    def test_no_loop_avg_overlap_is_low(self):
        result = self.detector.analyze(VARIED_MESSAGES)
        assert result.avg_overlap < 0.12

    # --- Abaixo do mínimo ---

    def test_below_minimum_messages_never_triggers(self):
        result = self.detector.analyze(FEW_MESSAGES)
        assert result.is_loop is False

    def test_empty_messages_never_triggers(self):
        result = self.detector.analyze([])
        assert result.is_loop is False

    def test_single_message_never_triggers(self):
        result = self.detector.analyze(["Uma única mensagem"])
        assert result.is_loop is False

    # --- Threshold customizado ---

    def test_custom_low_threshold_detects_mild_loop(self):
        detector = NarrativeLoopDetector(jaccard_threshold=0.10, min_messages=3)
        result = detector.analyze(MILD_LOOP_MESSAGES)
        assert result.is_loop is True

    def test_custom_high_threshold_misses_mild_loop(self):
        detector = NarrativeLoopDetector(jaccard_threshold=0.95)
        result = detector.analyze(LOOP_MESSAGES)
        assert result.is_loop is False

    # --- Filtra mensagens vazias ---

    def test_filters_empty_strings(self):
        messages_with_blanks = ["", "  "] + LOOP_MESSAGES
        result = self.detector.analyze(messages_with_blanks)
        # Não deve lançar erro; loop ainda pode ser detectado nas msgs válidas
        assert isinstance(result.is_loop, bool)

    # --- Conteúdo do loop_context ---

    def test_loop_context_contains_overlap_percentage(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        assert "%" in result.loop_context

    def test_loop_context_contains_message_count(self):
        result = self.detector.analyze(LOOP_MESSAGES)
        assert str(len(LOOP_MESSAGES)) in result.loop_context


# ─── Testes: build_companion_anti_loop_hint ────────────────────────────────────

class TestBuildCompanionAntiLoopHint:

    def setup_method(self):
        self.detector = NarrativeLoopDetector()

    def test_returns_empty_for_single_action(self):
        hint = self.detector.build_companion_anti_loop_hint(["Ataco o goblin"])
        assert hint == ""

    def test_returns_empty_for_varied_actions(self):
        actions = [
            "Ataco o goblin com minha espada longa",
            "Lanço bola de fogo no dragão negro voador",
            "Curo meu companheiro ferido com magia divina",
            "Negocio com o mercador de poções raras",
        ]
        hint = self.detector.build_companion_anti_loop_hint(actions)
        assert hint == ""

    def test_returns_hint_for_repetitive_actions(self):
        actions = [
            "Me movo para as sombras silenciosamente aguardando os guardas",
            "Me posiciono nas sombras silenciosas aguardando os guardas",
            "Avanço furtivamente pelas sombras silenciosas aguardando guardas",
            "Me movimento para as sombras escuras aguardando guardas patrulha",
        ]
        hint = self.detector.build_companion_anti_loop_hint(actions)
        assert hint != ""
        assert "ANTI-LOOP" in hint

    def test_hint_mentions_last_action(self):
        actions = [
            "Me movo para as sombras silenciosamente aguardando os guardas",
            "Me posiciono nas sombras silenciosas aguardando os guardas",
            "Avanço furtivamente pelas sombras aguardando guardas próximos",
            "Movimento para sombras escuras aguardando guardas patrulhando corredor",
        ]
        hint = self.detector.build_companion_anti_loop_hint(actions)
        if hint:  # só verifica se hint foi gerado
            assert "última ação" in hint.lower() or actions[-1][:50] in hint

    def test_returns_empty_for_empty_list(self):
        hint = self.detector.build_companion_anti_loop_hint([])
        assert hint == ""
