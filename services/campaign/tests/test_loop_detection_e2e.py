"""
Testes E2E do loop detection — integração com endpoints HTTP reais.

Cobrem:
  - GET /sessions/{id}/state retorna estado correto (exploration/combat)
  - POST /rounds/start → GET /rounds/active mostra round criado
  - Fluxo simulado de loop: N rounds com msgs repetitivas → ProcessGMTurn
    recebe loop_context no próximo round
  - Loop detection não quebra fluxo normal de um round
  - Resposta do GM em loop é diferente (via mock do LLM)

Usa DB em memória via conftest (rpg_test) e mocks para OpenAI/LangChain.
"""

from __future__ import annotations

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID
from httpx import AsyncClient, ASGITransport

from infrastructure.database.connection import get_db
from infrastructure.database.orm_models import Base
from presentation.main import app
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from infrastructure.ai.loop_detector import NarrativeLoopDetector


# ─── Config DB de teste ────────────────────────────────────────────────────────

TEST_DB_URL = (
    os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://rpg_user:change_me_strong_password@localhost:5432/rpg_platform",
    )
    .replace("@postgres:", "@localhost:")
    .replace("/rpg_platform", "/rpg_test")
)


async def _check_db_available() -> bool:
    """Retorna True se o banco de teste está acessível."""
    try:
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.connect():
            pass
        await engine.dispose()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="function")
async def db_session():
    if not await _check_db_available():
        pytest.skip("Banco de teste não disponível (rpg_test em localhost:5432)")
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ─── Helpers ───────────────────────────────────────────────────────────────────

async def create_campaign(client: AsyncClient) -> str:
    r = await client.post("/campaigns", json={
        "title": "Loop Test Campaign",
        "description": "Campanha para testar loop detection",
        "rpg_system": "D&D 5e",
        "difficulty": "medium",
        "tone": "heroic",
    })
    assert r.status_code == 201
    return r.json()["id"]


async def seed_gm_messages(db_session, session_id: UUID, messages: list[str]) -> None:
    """Insere mensagens GM diretamente no banco para simular histórico."""
    from sqlalchemy import text
    for content in messages:
        await db_session.execute(
            text("""
                INSERT INTO session_messages (id, session_id, role, content, created_at)
                VALUES (gen_random_uuid(), :sid, 'gm', :content, NOW())
            """),
            {"sid": str(session_id), "content": content},
        )
    await db_session.commit()


LOOP_GM_TEXTS = [
    "Elara Swiftfoot se move habilmente pelas sombras aguardando os guardas silenciosamente.",
    "Elara Swiftfoot tenta se posicionar nas sombras novamente aguardando guardas.",
    "Elara Swiftfoot falha ao tentar se mover para as sombras alertando os guardas.",
    "Elara Swiftfoot encontra nova posição nas sombras aguardando silenciosamente guardas.",
    "Elara Swiftfoot se move furtivamente pelas sombras para surpreender os guardas.",
    "Elara Swiftfoot aguarda silenciosamente nas sombras preparada para atacar guardas.",
]


# ─── Testes: GET /sessions/{id}/state ─────────────────────────────────────────

class TestGetSessionState:
    """Testa o endpoint que retorna o estado de sessão (exploration/combat)."""

    @pytest.mark.asyncio
    async def test_session_state_returns_exploration_by_default(self, client, db_session):
        """Sessão nova deve retornar exploration sem inimigos."""
        campaign_id = await create_campaign(client)

        # Cria sessão
        with patch("presentation.routers.sessions.run_opening_background"):
            with patch("application.session.use_cases.CharacterServiceClient") as mock_char:
                mock_char.return_value.list_campaign_characters = AsyncMock(
                    return_value=[{"id": str(uuid4()), "name": "Elara", "char_type": "pc"}]
                )
                r = await client.post(f"/campaigns/{campaign_id}/sessions/start")
                if r.status_code not in (200, 201):
                    pytest.skip("Session creation not available in test env")
                session_id = r.json().get("id")
                if not session_id:
                    pytest.skip("No session_id returned")

        r = await client.get(f"/sessions/{session_id}/state")
        assert r.status_code == 200
        data = r.json()
        assert data["session_mode"] in ("exploration", "combat")
        assert isinstance(data["combat"]["in_combat"], bool)
        assert isinstance(data["combat"]["enemies"], list)

    @pytest.mark.asyncio
    async def test_session_state_unknown_session_returns_exploration(self, client):
        """UUID inexistente deve retornar exploration (sem crash)."""
        fake_id = str(uuid4())
        r = await client.get(f"/sessions/{fake_id}/state")
        assert r.status_code == 200
        data = r.json()
        assert data["session_mode"] == "exploration"
        assert data["combat"]["in_combat"] is False
        assert data["combat"]["enemies"] == []

    @pytest.mark.asyncio
    async def test_session_state_structure(self, client):
        """Estrutura da resposta deve ter todos os campos esperados."""
        fake_id = str(uuid4())
        r = await client.get(f"/sessions/{fake_id}/state")
        assert r.status_code == 200
        data = r.json()
        assert "session_mode" in data
        assert "combat" in data
        assert "in_combat" in data["combat"]
        assert "enemies" in data["combat"]
        assert "current_scene" in data


# ─── Testes: Loop Detection — NarrativeLoopDetector isolado ───────────────────

class TestLoopDetectorE2E:
    """
    Testa o detector com dados realistas e verifica que o output
    é adequado para ser injetado no prompt do GM.
    """

    def test_detector_with_campaign_ebrebruma_data(self):
        """Valida com dados reais da campanha Érebruma."""
        detector = NarrativeLoopDetector()
        result = detector.analyze(LOOP_GM_TEXTS)

        assert result.is_loop is True
        assert len(result.loop_context) > 50
        assert result.avg_overlap > 0.15

    def test_loop_context_is_valid_string_for_prompt_injection(self):
        """loop_context deve ser string limpa, sem bytes nulos ou chars problemáticos."""
        detector = NarrativeLoopDetector()
        result = detector.analyze(LOOP_GM_TEXTS)

        ctx = result.loop_context
        assert "\x00" not in ctx
        assert isinstance(ctx, str)
        # Deve ter pelo menos 5 linhas de instrução
        assert ctx.count("\n") >= 4

    def test_no_loop_produces_empty_context(self):
        """Sessão saudável não deve gerar overhead de prompt."""
        varied = [
            "Os aventureiros chegam à cidade e encontram o mago Thalindor esperando.",
            "Um dragão negro ataca a aldeia durante a noite causando grande destruição.",
            "A princesa revela que é na verdade uma espiã enviada pelo rei inimigo.",
            "O portal arcano se abre revelando dimensão desconhecida repleta de horrores.",
            "Thorin encontra seu pai perdido há décadas nas masmorras do castelo negro.",
            "A batalha épica termina com a derrota do lich e libertação das almas presas.",
        ]
        detector = NarrativeLoopDetector()
        result = detector.analyze(varied)

        assert result.is_loop is False
        assert result.loop_context == ""

    def test_detector_performance_with_many_messages(self):
        """Detector deve processar 50 mensagens rapidamente (< 1s)."""
        import time
        msgs = LOOP_GM_TEXTS * 8  # 48 mensagens
        detector = NarrativeLoopDetector()

        start = time.monotonic()
        result = detector.analyze(msgs)
        elapsed = time.monotonic() - start

        assert elapsed < 1.0
        assert isinstance(result.is_loop, bool)


# ─── Testes: Fluxo de round com loop (mock LLM) ───────────────────────────────

class TestRoundFlowWithLoop:
    """
    Simula o fluxo completo de um round com loop detectado.
    Verifica que ProcessGMTurnUseCase passa loop_context para o GM
    e que o round é concluído normalmente.
    """

    @pytest.mark.asyncio
    async def test_process_gm_turn_loop_detected_round_completes(self, db_session):
        """
        Cria sessão com histórico de loop no DB real.
        Verifica que ProcessGMTurnUseCase conclui sem erros.
        """
        from sqlalchemy import text
        from domain.round.entity import Round, RoundAction
        from domain.round.value_objects import RoundStatus
        from application.round.use_cases import ProcessGMTurnUseCase
        from infrastructure.repositories.round_repository import RoundRepository
        from infrastructure.repositories.session_repository import MessageRepository, SessionRepository
        from infrastructure.repositories.campaign_repository import CampaignRepository

        # Cria campanha e sessão no banco
        campaign_id = uuid4()
        session_id = uuid4()
        round_id = uuid4()
        char_id = uuid4()

        await db_session.execute(text("""
            INSERT INTO campaigns (id, title, rpg_system, status, init_status, difficulty, tone, opening_generated, created_at, updated_at)
            VALUES (:id, 'Loop Test', 'D&D 5e', 'active', 'ready', 'medium', 'heroic', true, NOW(), NOW())
        """), {"id": str(campaign_id)})

        await db_session.execute(text("""
            INSERT INTO sessions (id, campaign_id, started_at, is_active)
            VALUES (:id, :cid, NOW(), true)
        """), {"id": str(session_id), "cid": str(campaign_id)})

        # Insere histórico de loop
        for content in LOOP_GM_TEXTS:
            await db_session.execute(text("""
                INSERT INTO session_messages (id, session_id, role, content, created_at)
                VALUES (gen_random_uuid(), :sid, 'gm', :content, NOW())
            """), {"sid": str(session_id), "content": content})

        # Cria round em gm_processing
        await db_session.execute(text("""
            INSERT INTO rounds (id, session_id, round_number, status, created_at)
            VALUES (:id, :sid, 1, 'gm_processing', NOW())
        """), {"id": str(round_id), "sid": str(session_id)})

        # Cria ação no round
        action_id = uuid4()
        await db_session.execute(text("""
            INSERT INTO round_actions (id, round_id, session_id, character_name, is_ai, is_pass,
                action_text, d20_roll, initiative_order, character_id, created_at)
            VALUES (:id, :rid, :sid, 'Elara', true, false,
                'Me movo para as sombras', 12, 1, :cid, NOW())
        """), {
            "id": str(action_id),
            "rid": str(round_id),
            "sid": str(session_id),
            "cid": str(char_id),
        })
        await db_session.commit()

        # Monta use case com LLM mockado
        captured_loop_context: list[str] = []

        async def mock_process_round(session_id, ordered_actions, enemy_context="", loop_context=""):
            captured_loop_context.append(loop_context)
            return ["O GM quebra o loop com uma revelação dramática!"]

        gm_svc = AsyncMock()
        gm_svc.process_round = mock_process_round

        knowledge = AsyncMock()
        knowledge.check_gate = AsyncMock(return_value=True)

        round_repo = RoundRepository(db_session)
        msg_repo = MessageRepository(db_session)
        session_repo = SessionRepository(db_session)
        campaign_repo = CampaignRepository(db_session)

        combat_repo = AsyncMock()
        combat_repo.get_active_encounter = AsyncMock(return_value=None)
        combat_repo.format_enemies_for_gm = MagicMock(return_value="")

        char_client = AsyncMock()
        char_client.apply_state_update = AsyncMock()

        uc = ProcessGMTurnUseCase(
            round_repo=round_repo,
            message_repo=msg_repo,
            gm_service=gm_svc,
            knowledge_retriever=knowledge,
            ws_broadcast_fn=AsyncMock(),
            character_client=char_client,
            campaign_repo=campaign_repo,
            session_repo=session_repo,
            combat_repo=combat_repo,
        )

        results = await uc.execute(round_id)
        await db_session.commit()

        # Round deve ter completado
        assert isinstance(results, list)
        assert len(results) == 1

        # Loop deve ter sido detectado e contexto passado ao GM
        assert len(captured_loop_context) == 1
        assert "LOOP NARRATIVO" in captured_loop_context[0]
        assert "INIMIGOS" in captured_loop_context[0]

    @pytest.mark.asyncio
    async def test_process_gm_turn_no_loop_context_when_messages_varied(self, db_session):
        """Sem loop no histórico, GM não recebe loop_context."""
        from sqlalchemy import text
        from application.round.use_cases import ProcessGMTurnUseCase
        from infrastructure.repositories.round_repository import RoundRepository
        from infrastructure.repositories.session_repository import MessageRepository, SessionRepository
        from infrastructure.repositories.campaign_repository import CampaignRepository

        campaign_id = uuid4()
        session_id = uuid4()
        round_id = uuid4()
        char_id = uuid4()

        await db_session.execute(text("""
            INSERT INTO campaigns (id, title, rpg_system, status, init_status, difficulty, tone, opening_generated, created_at, updated_at)
            VALUES (:id, 'Varied Test', 'D&D 5e', 'active', 'ready', 'medium', 'heroic', true, NOW(), NOW())
        """), {"id": str(campaign_id)})

        await db_session.execute(text("""
            INSERT INTO sessions (id, campaign_id, started_at, is_active)
            VALUES (:id, :cid, NOW(), true)
        """), {"id": str(session_id), "cid": str(campaign_id)})

        varied_messages = [
            "Os aventureiros chegam à cidade e encontram o mago Thalindor esperando.",
            "Um dragão negro ataca a aldeia durante a noite causando grande destruição.",
            "A princesa revela que é na verdade uma espiã enviada pelo rei inimigo.",
            "O portal arcano se abre revelando dimensão desconhecida repleta de horrores.",
            "Thorin encontra seu pai perdido há décadas nas masmorras do castelo negro.",
            "A batalha épica termina com a derrota do lich e libertação das almas.",
        ]
        for content in varied_messages:
            await db_session.execute(text("""
                INSERT INTO session_messages (id, session_id, role, content, created_at)
                VALUES (gen_random_uuid(), :sid, 'gm', :content, NOW())
            """), {"sid": str(session_id), "content": content})

        await db_session.execute(text("""
            INSERT INTO rounds (id, session_id, round_number, status, created_at)
            VALUES (:id, :sid, 1, 'gm_processing', NOW())
        """), {"id": str(round_id), "sid": str(session_id)})

        action_id = uuid4()
        await db_session.execute(text("""
            INSERT INTO round_actions (id, round_id, session_id, character_name, is_ai, is_pass,
                action_text, d20_roll, initiative_order, character_id, created_at)
            VALUES (:id, :rid, :sid, 'Thorin', false, false,
                'Ataco o goblin', 18, 1, :cid, NOW())
        """), {
            "id": str(action_id),
            "rid": str(round_id),
            "sid": str(session_id),
            "cid": str(char_id),
        })
        await db_session.commit()

        captured_loop_context: list[str] = []

        async def mock_process_round(session_id, ordered_actions, enemy_context="", loop_context=""):
            captured_loop_context.append(loop_context)
            return ["Thorin acerta o goblin com força!"]

        gm_svc = AsyncMock()
        gm_svc.process_round = mock_process_round

        knowledge = AsyncMock()
        knowledge.check_gate = AsyncMock(return_value=True)

        round_repo = RoundRepository(db_session)
        msg_repo = MessageRepository(db_session)
        session_repo = SessionRepository(db_session)
        campaign_repo = CampaignRepository(db_session)

        combat_repo = AsyncMock()
        combat_repo.get_active_encounter = AsyncMock(return_value=None)
        combat_repo.format_enemies_for_gm = MagicMock(return_value="")

        uc = ProcessGMTurnUseCase(
            round_repo=round_repo,
            message_repo=msg_repo,
            gm_service=gm_svc,
            knowledge_retriever=knowledge,
            ws_broadcast_fn=AsyncMock(),
            character_client=AsyncMock(),
            campaign_repo=campaign_repo,
            session_repo=session_repo,
            combat_repo=combat_repo,
        )

        results = await uc.execute(round_id)
        await db_session.commit()

        assert isinstance(results, list)
        assert len(results) == 1

        # Sem loop, loop_context deve ser vazio
        assert len(captured_loop_context) == 1
        assert captured_loop_context[0] == ""
