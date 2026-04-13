"""
Testes de integração: loop detection integrado com os use cases de round.

Cobrem:
  - ProcessGMTurnUseCase injeta loop_context quando loop detectado
  - ProcessGMTurnUseCase NÃO injeta quando sem loop
  - StartRoundUseCase._generate_ai_actions injeta anti-loop hint em companions
  - LangchainGMService.process_round recebe loop_context corretamente
  - Fluxo completo: sessão em loop → GM recebe instrução de intervenção

Todos os testes usam mocks (sem DB real, sem OpenAI).
"""

from __future__ import annotations

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4, UUID

from application.round.use_cases import ProcessGMTurnUseCase, StartRoundUseCase
from application.round.dtos import StartRoundDTO
from domain.round.entity import Round, RoundAction
from domain.round.value_objects import RoundStatus
from domain.session.entity import Session, SessionMessage
from domain.session.value_objects import MessageRole
from infrastructure.ai.loop_detector import NarrativeLoopDetector


# ─── Mensagens de teste ────────────────────────────────────────────────────────

LOOP_GM_TEXTS = [
    "Elara Swiftfoot se move habilmente pelas sombras aguardando os guardas silenciosamente.",
    "Elara Swiftfoot tenta se posicionar nas sombras novamente aguardando guardas.",
    "Elara Swiftfoot falha ao tentar se mover para as sombras alertando os guardas.",
    "Elara Swiftfoot encontra nova posição nas sombras aguardando silenciosamente guardas.",
    "Elara Swiftfoot se move furtivamente pelas sombras para surpreender os guardas.",
    "Elara Swiftfoot aguarda silenciosamente nas sombras preparada para atacar guardas.",
]

VARIED_GM_TEXTS = [
    "Os aventureiros chegam à grande cidade de pedra negra.",
    "Uma batalha épica começa quando o dragão desce das nuvens.",
    "Aria lança um feitiço poderoso revelando o vilão disfarçado.",
    "O grupo encontra um mapa antigo com runas arcanas brilhantes.",
    "Thorin negocia com os anões pela libertação dos prisioneiros élficos.",
    "A explosão destrói a ponte cortando a única rota de fuga.",
]


# ─── Helpers ───────────────────────────────────────────────────────────────────

def make_session_message(content: str, role_value: str = "gm") -> SessionMessage:
    role_map = {
        "gm": MessageRole.GM,
        "player": MessageRole.PLAYER,
        "ai_companion": MessageRole.AI_COMPANION,
    }
    msg = MagicMock(spec=SessionMessage)
    msg.role = MagicMock()
    msg.role.value = role_value
    msg.content = content
    return msg


def make_round_with_actions(session_id, n_actions: int = 1, status=RoundStatus.GM_PROCESSING):
    r = Round.create(session_id=session_id, round_number=1)
    r.status = status
    for i in range(n_actions):
        action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name=f"Elara{i}",
            is_ai=True,
            is_pass=False,
            character_id=uuid4(),
            action_text="Me movo para as sombras silenciosamente",
        )
        action.d20_roll = 12
        action.initiative_order = i + 1
        r.actions.append(action)
    return r


def make_message_repo(gm_texts: list[str]) -> AsyncMock:
    """Cria message_repo que retorna mensagens GM mockadas."""
    repo = AsyncMock()
    messages = [make_session_message(t, "gm") for t in gm_texts]
    repo.list_by_session = AsyncMock(return_value=messages)
    repo.save = AsyncMock()
    return repo


def make_round_repo(round_: Round) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=round_)
    repo.save = AsyncMock(side_effect=lambda r: r)
    repo.update_action = AsyncMock()
    repo.save_dice_roll = AsyncMock()
    return repo


def make_gm_service(responses: list[str] | None = None) -> AsyncMock:
    svc = AsyncMock()
    svc.process_round = AsyncMock(return_value=responses or ["O GM narra a cena."])
    svc.generate_companion_action = AsyncMock(return_value="Ataco o goblin!")
    return svc


def make_knowledge_retriever(gate_open: bool = True) -> AsyncMock:
    kr = AsyncMock()
    kr.check_gate = AsyncMock(return_value=gate_open)
    return kr


def make_combat_repo() -> AsyncMock:
    cr = AsyncMock()
    cr.get_active_encounter = AsyncMock(return_value=None)
    cr.format_enemies_for_gm = MagicMock(return_value="")
    return cr


def make_process_gm_uc(
    round_: Round,
    gm_texts: list[str],
    gm_service: AsyncMock | None = None,
) -> ProcessGMTurnUseCase:
    session_id = round_.session_id
    session = MagicMock()
    session.campaign_id = uuid4()

    session_repo = AsyncMock()
    session_repo.get_by_id = AsyncMock(return_value=session)

    campaign_repo = AsyncMock()
    campaign_repo.save_gm_memory = AsyncMock()
    campaign_repo.upsert_campaign_state = AsyncMock()
    campaign_repo.save_snapshot = AsyncMock()
    campaign_repo.save_npc = AsyncMock()
    campaign_repo.save_location = AsyncMock()

    return ProcessGMTurnUseCase(
        round_repo=make_round_repo(round_),
        message_repo=make_message_repo(gm_texts),
        gm_service=gm_service or make_gm_service(),
        knowledge_retriever=make_knowledge_retriever(),
        ws_broadcast_fn=AsyncMock(),
        character_client=AsyncMock(),
        campaign_repo=campaign_repo,
        session_repo=session_repo,
        combat_repo=make_combat_repo(),
    )


# ─── Testes: ProcessGMTurnUseCase + loop detection ───────────────────────────

class TestProcessGMTurnLoopDetection:

    @pytest.mark.asyncio
    async def test_injects_loop_context_when_loop_detected(self):
        """Quando há loop, process_round deve receber loop_context não-vazio."""
        session_id = uuid4()
        round_ = make_round_with_actions(session_id)
        gm_svc = make_gm_service()

        uc = make_process_gm_uc(round_, LOOP_GM_TEXTS, gm_service=gm_svc)
        await uc.execute(round_.id)

        # Verifica que process_round foi chamado com loop_context não-vazio
        call_kwargs = gm_svc.process_round.call_args
        loop_ctx = call_kwargs.kwargs.get("loop_context") or call_kwargs.args[3] if len(call_kwargs.args) > 3 else None
        # Aceita keyword ou positional
        if call_kwargs.kwargs:
            loop_ctx = call_kwargs.kwargs.get("loop_context", "")
        else:
            loop_ctx = ""

        # Pelo menos foi chamado
        assert gm_svc.process_round.called

        # Verifica o argumento diretamente
        all_calls = gm_svc.process_round.call_args_list
        assert len(all_calls) == 1
        kwargs = all_calls[0].kwargs
        assert "loop_context" in kwargs
        assert kwargs["loop_context"] != ""
        assert "LOOP NARRATIVO" in kwargs["loop_context"]

    @pytest.mark.asyncio
    async def test_no_loop_context_when_messages_varied(self):
        """Sem loop, process_round deve receber loop_context vazio."""
        session_id = uuid4()
        round_ = make_round_with_actions(session_id)
        gm_svc = make_gm_service()

        uc = make_process_gm_uc(round_, VARIED_GM_TEXTS, gm_service=gm_svc)
        await uc.execute(round_.id)

        assert gm_svc.process_round.called
        kwargs = gm_svc.process_round.call_args_list[0].kwargs
        assert "loop_context" in kwargs
        assert kwargs["loop_context"] == ""

    @pytest.mark.asyncio
    async def test_no_loop_context_when_few_messages(self):
        """Com poucas mensagens (< 4), nunca dispara loop."""
        session_id = uuid4()
        round_ = make_round_with_actions(session_id)
        gm_svc = make_gm_service()

        uc = make_process_gm_uc(round_, LOOP_GM_TEXTS[:2], gm_service=gm_svc)
        await uc.execute(round_.id)

        assert gm_svc.process_round.called
        kwargs = gm_svc.process_round.call_args_list[0].kwargs
        assert kwargs.get("loop_context", "") == ""

    @pytest.mark.asyncio
    async def test_loop_context_contains_inimigos_instruction(self):
        """O loop_context deve incluir instrução para usar [INIMIGOS:]."""
        session_id = uuid4()
        round_ = make_round_with_actions(session_id)
        gm_svc = make_gm_service()

        uc = make_process_gm_uc(round_, LOOP_GM_TEXTS, gm_service=gm_svc)
        await uc.execute(round_.id)

        kwargs = gm_svc.process_round.call_args_list[0].kwargs
        loop_ctx = kwargs.get("loop_context", "")
        if loop_ctx:  # só verifica se detectou
            assert "[INIMIGOS:]" in loop_ctx

    @pytest.mark.asyncio
    async def test_session_still_completes_when_loop_detected(self):
        """Loop detectado não deve impedir conclusão normal do round."""
        session_id = uuid4()
        round_ = make_round_with_actions(session_id)
        gm_svc = make_gm_service(["GM responde quebrando o loop com combate!"])

        uc = make_process_gm_uc(round_, LOOP_GM_TEXTS, gm_service=gm_svc)
        results = await uc.execute(round_.id)

        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].gm_response == "GM responde quebrando o loop com combate!"

    @pytest.mark.asyncio
    async def test_loop_detection_failure_does_not_break_flow(self):
        """Se o detector falhar, o round deve continuar normalmente."""
        session_id = uuid4()
        round_ = make_round_with_actions(session_id)
        gm_svc = make_gm_service()

        # Message repo que lança exceção
        bad_msg_repo = AsyncMock()
        bad_msg_repo.list_by_session = AsyncMock(side_effect=Exception("DB error"))
        bad_msg_repo.save = AsyncMock()

        session = MagicMock()
        session.campaign_id = uuid4()
        session_repo = AsyncMock()
        session_repo.get_by_id = AsyncMock(return_value=session)
        campaign_repo = AsyncMock()
        campaign_repo.save_gm_memory = AsyncMock()
        campaign_repo.upsert_campaign_state = AsyncMock()
        campaign_repo.save_snapshot = AsyncMock()
        campaign_repo.save_npc = AsyncMock()
        campaign_repo.save_location = AsyncMock()

        uc = ProcessGMTurnUseCase(
            round_repo=make_round_repo(round_),
            message_repo=bad_msg_repo,
            gm_service=gm_svc,
            knowledge_retriever=make_knowledge_retriever(),
            ws_broadcast_fn=AsyncMock(),
            character_client=AsyncMock(),
            campaign_repo=campaign_repo,
            session_repo=session_repo,
            combat_repo=make_combat_repo(),
        )

        # Não deve lançar exceção
        results = await uc.execute(round_.id)
        assert isinstance(results, list)
        # GM ainda foi chamado (com loop_context="" por fallback)
        assert gm_svc.process_round.called


# ─── Testes: NarrativeLoopDetector integrado com dados reais da campanha ──────

class TestLoopDetectorWithRealCampaignData:
    """Usa as mensagens reais da campanha Érebruma para validar o detector."""

    REAL_LOOP_DATA = [
        "Elara Swiftfoot se move habilmente pelas sombras, cada passo e respiração "
        "cuidadosamente calculados. Ela já está familiarizada com o terreno e utiliza "
        "sua experiência para encontrar um novo ponto de vantagem.",
        "Elara Swiftfoot espera pacientemente pelo próximo grupo de guardas, suas adagas "
        "prontas para uma emboscada. Com a habilidade já característica de suas ações "
        "furtivas, ela se move com agilidade e precisão.",
        "Enquanto Elara Swiftfoot tenta se mover silenciosamente para encontrar uma nova "
        "posição de vantagem, seus passos falham terrivelmente. Ao tropeçar em uma pedra "
        "solta, ela não só faz um barulho alto, como também perde o equilíbrio.",
        "Elara Swiftfoot tenta se mover rapidamente para uma posição nas sombras, "
        "preparando-se para uma emboscada surpresa. No entanto, em uma falha crítica, "
        "ela tropeça em uma raiz protuberante e cai de bruços no chão.",
        "Elara Swiftfoot, com um brilho ágil em seus olhos, mergulha rapidamente nas "
        "sombras ao seu redor, desaparecendo quase como por mágica. Seu movimento é tão "
        "fluido e calculado que ela não apenas se torna indetectável.",
        "Elara Swiftfoot, em sua tentativa de aproveitar a rota secreta descoberta para "
        "se posicionar estrategicamente, encontra um imprevisto desastroso.",
    ]

    def test_real_campaign_data_triggers_loop(self):
        detector = NarrativeLoopDetector()
        result = detector.analyze(self.REAL_LOOP_DATA)
        assert result.is_loop is True

    def test_real_campaign_theme_contains_relevant_words(self):
        detector = NarrativeLoopDetector()
        result = detector.analyze(self.REAL_LOOP_DATA)
        theme_lower = result.detected_theme.lower()
        # Pelo menos uma palavra relevante do padrão
        relevant = {"elara", "sombras", "guardas", "swiftfoot", "movimento", "posição"}
        assert any(w in theme_lower for w in relevant)

    def test_real_campaign_context_ready_to_inject(self):
        detector = NarrativeLoopDetector()
        result = detector.analyze(self.REAL_LOOP_DATA)
        assert len(result.loop_context) > 100
        assert result.loop_context.startswith("\n\n⚠️")


# ─── Testes: Anti-loop hint para companions (lógica isolada) ──────────────────

class TestCompanionAntiLoopHintLogic:
    """
    Testa a lógica de geração do hint anti-loop para companions.
    _generate_ai_actions usa NarrativeLoopDetector internamente com os textos do GM.
    Esses testes verificam o comportamento do detector com os textos que seriam
    passados a generate_companion_action.
    """

    def test_loop_gm_texts_trigger_anti_loop_hint(self):
        """GM texts com loop devem gerar hint anti-loop para companions."""
        detector = NarrativeLoopDetector()
        # Primeiro verifica que há loop
        loop_result = detector.analyze(LOOP_GM_TEXTS)
        assert loop_result.is_loop is True

        # Depois verifica que o hint é gerado
        hint = detector.build_companion_anti_loop_hint(LOOP_GM_TEXTS)
        assert hint != ""
        assert "ANTI-LOOP" in hint

    def test_varied_gm_texts_no_anti_loop_hint(self):
        """GM texts variados não devem gerar hint para companions."""
        detector = NarrativeLoopDetector()
        loop_result = detector.analyze(VARIED_GM_TEXTS)
        assert loop_result.is_loop is False

        hint = detector.build_companion_anti_loop_hint(VARIED_GM_TEXTS)
        assert hint == ""

    def test_enriched_context_contains_scene_and_hint(self):
        """Contexto enriquecido deve conter a cena original + hint anti-loop."""
        detector = NarrativeLoopDetector()
        scene_context = "\n\n".join(LOOP_GM_TEXTS)
        hint = detector.build_companion_anti_loop_hint(LOOP_GM_TEXTS)

        enriched = scene_context + hint
        # Conteúdo da cena original
        assert "Elara" in enriched
        # Hint de intervenção
        if hint:
            assert "ANTI-LOOP" in enriched

    def test_no_hint_appended_when_no_loop(self):
        """Sem loop, contexto não deve ser modificado."""
        detector = NarrativeLoopDetector()
        scene_context = "\n\n".join(VARIED_GM_TEXTS)
        hint = detector.build_companion_anti_loop_hint(VARIED_GM_TEXTS)
        enriched = scene_context + hint

        assert "ANTI-LOOP" not in enriched
        assert enriched == scene_context  # sem modificação


# ─── Testes: LangchainGMService.process_round com loop_context ────────────────

class TestLangchainGMServiceProcessRound:
    """
    Testa que process_round injeta corretamente o loop_context no prompt.
    Mocka a chamada ao LLM para não precisar de OpenAI real.
    """

    @pytest.mark.asyncio
    async def test_process_round_accepts_loop_context_kwarg(self):
        """process_round deve aceitar loop_context sem erros."""
        from infrastructure.ai.langchain_gm_service import LangchainGMService

        svc = LangchainGMService.__new__(LangchainGMService)
        svc._vector_db_url = "postgresql+psycopg2://fake"

        mock_llm_result = MagicMock()
        mock_llm_result.content = "GM narrou algo épico.\n---\nOutra narração épica."
        svc._llm = MagicMock()
        svc._llm.invoke = MagicMock(return_value=mock_llm_result)

        actions = [
            {"character_name": "Elara", "action_text": "Me movo para as sombras", "d20_roll": 12, "initiative_order": 1, "is_ai": True},
        ]
        result = await svc.process_round(
            session_id="test-session",
            ordered_actions=actions,
            enemy_context="",
            loop_context="⚠️ LOOP DETECTADO: quebre o ciclo!",
        )
        assert isinstance(result, list)
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_loop_context_appears_in_llm_prompt(self):
        """Quando loop_context fornecido, deve aparecer no prompt enviado ao LLM."""
        from infrastructure.ai.langchain_gm_service import LangchainGMService

        svc = LangchainGMService.__new__(LangchainGMService)
        svc._vector_db_url = "postgresql+psycopg2://fake"

        captured_prompts: list[str] = []

        def capture_invoke(prompt):
            captured_prompts.append(str(prompt))
            result = MagicMock()
            result.content = "Resposta narrativa."
            return result

        svc._llm = MagicMock()
        svc._llm.invoke = MagicMock(side_effect=capture_invoke)

        loop_ctx = "⚠️ ALERTA DE LOOP NARRATIVO — INTERVENÇÃO OBRIGATÓRIA!"
        actions = [
            {"character_name": "Elara", "action_text": "Me movo para as sombras", "d20_roll": 8, "initiative_order": 1, "is_ai": True},
        ]

        await svc.process_round(
            session_id="test-session",
            ordered_actions=actions,
            loop_context=loop_ctx,
        )

        assert len(captured_prompts) == 1
        assert loop_ctx in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_empty_loop_context_does_not_add_noise(self):
        """Sem loop_context, o prompt não deve ter texto extra de alerta."""
        from infrastructure.ai.langchain_gm_service import LangchainGMService

        svc = LangchainGMService.__new__(LangchainGMService)
        svc._vector_db_url = "postgresql+psycopg2://fake"

        captured_prompts: list[str] = []

        def capture_invoke(prompt):
            captured_prompts.append(str(prompt))
            result = MagicMock()
            result.content = "Resposta narrativa."
            return result

        svc._llm = MagicMock()
        svc._llm.invoke = MagicMock(side_effect=capture_invoke)

        actions = [
            {"character_name": "Thorin", "action_text": "Ataco o goblin", "d20_roll": 18, "initiative_order": 1, "is_ai": False},
        ]

        await svc.process_round(
            session_id="test-session",
            ordered_actions=actions,
            loop_context="",
        )

        assert len(captured_prompts) == 1
        assert "LOOP NARRATIVO" not in captured_prompts[0]
        assert "INTERVENÇÃO" not in captured_prompts[0]
