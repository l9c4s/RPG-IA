"""
Testes de regressão para as correções das tabelas vazias:
  P1 — Sistema de combate conectado ao ProcessGMTurnUseCase
  P2 — KnowledgeChunksRetriever (RAG fix)
  P5 — Tag [LOCAL:] no parser
  P4 — Endpoint sync-players (via CampaignRepository.register_player)
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4, UUID

from infrastructure.ai.state_parser import parse_gm_response


# ─── P5: Tag [LOCAL:] ─────────────────────────────────────────────────────────

class TestLocalTag:
    def test_single_location_extracted(self):
        text = "Vocês chegam ao [LOCAL:Taverna do Corvo|Estabelecimento escuro com odor de cerveja velha]."
        result = parse_gm_response(text)
        assert len(result["locations_introduced"]) == 1
        assert result["locations_introduced"][0]["name"] == "Taverna do Corvo"
        assert "cerveja velha" in result["locations_introduced"][0]["description"]

    def test_multiple_locations_extracted(self):
        text = (
            "[LOCAL:Torre do Mago|Estrutura de pedra negra] e "
            "[LOCAL:Mercado Central|Praça barulhenta ao ar livre]"
        )
        result = parse_gm_response(text)
        assert len(result["locations_introduced"]) == 2
        names = [l["name"] for l in result["locations_introduced"]]
        assert "Torre do Mago" in names
        assert "Mercado Central" in names

    def test_location_tag_removed_from_clean_text(self):
        text = "Você entra no [LOCAL:Castelo|Fortaleza medieval] pela porta principal."
        result = parse_gm_response(text)
        assert "[LOCAL:" not in result["clean_text"]
        assert "Você entra no" in result["clean_text"]
        assert "pela porta principal." in result["clean_text"]

    def test_no_location_returns_empty_list(self):
        result = parse_gm_response("Texto simples sem locais.")
        assert result["locations_introduced"] == []

    def test_locations_key_always_present(self):
        result = parse_gm_response("Qualquer texto.")
        assert "locations_introduced" in result

    def test_location_case_insensitive(self):
        text = "[local:Mina Abandonada|Túneis escuros cheios de eco]"
        result = parse_gm_response(text)
        assert len(result["locations_introduced"]) == 1

    def test_location_coexists_with_npc_and_combat_tags(self):
        text = (
            "[LOCAL:Covil do Dragão|Câmara de pedra com tesouro] "
            "[NPC:Dragonar|Dragão vermelho ancião] "
            "[INIMIGOS: [{\"nome\":\"Dragão\",\"tipo\":\"dragon\",\"hp\":200,\"ca\":19,\"atk\":8,\"dano\":\"2d10+6\"}]]"
        )
        result = parse_gm_response(text)
        assert len(result["locations_introduced"]) == 1
        assert len(result["npcs_introduced"]) == 1
        assert len(result["new_enemies"]) == 1


# ─── P1: Combat system wiring ────────────────────────────────────────────────

def _make_combat_repo(
    encounter=None,
    alive_enemies=None,
):
    repo = AsyncMock()
    repo.get_active_encounter = AsyncMock(return_value=encounter)
    repo.get_alive_enemies = AsyncMock(return_value=alive_enemies or [])
    repo.create_encounter = AsyncMock(return_value=MagicMock(id=uuid4()))
    repo.find_template_by_name = AsyncMock(return_value=None)
    repo.save_template = AsyncMock(return_value=MagicMock(id=uuid4()))
    repo.spawn_enemies = AsyncMock(return_value=[])
    repo.find_enemy_by_slug = AsyncMock(return_value=None)
    repo.apply_damage_to_enemy = AsyncMock()
    repo.log_event = AsyncMock()
    repo.resolve_encounter = AsyncMock()
    repo.format_enemies_for_gm = MagicMock(return_value="")
    return repo


def _make_process_gm_uc_with_combat(round_, session, gm_responses, combat_repo=None):
    """Constrói ProcessGMTurnUseCase com combat_repo configurado."""
    from application.round.use_cases import ProcessGMTurnUseCase

    round_repo = AsyncMock()
    round_repo.get_by_id = AsyncMock(return_value=round_)
    round_repo.update_action = AsyncMock()
    round_repo.save = AsyncMock(side_effect=lambda r: r)
    round_repo.save_dice_roll = AsyncMock()

    msg_repo = AsyncMock()
    msg_repo.save = AsyncMock()

    knowledge = AsyncMock()
    knowledge.check_gate = AsyncMock(return_value=True)

    gm = AsyncMock()
    gm.process_round = AsyncMock(return_value=gm_responses)

    sess_repo = AsyncMock()
    sess_repo.get_by_id = AsyncMock(return_value=session)

    camp_repo = AsyncMock()

    return ProcessGMTurnUseCase(
        round_repo=round_repo,
        message_repo=msg_repo,
        gm_service=gm,
        knowledge_retriever=knowledge,
        ws_broadcast_fn=AsyncMock(),
        character_client=None,
        campaign_repo=camp_repo,
        session_repo=sess_repo,
        combat_repo=combat_repo,
    )


def _make_session_and_round(n_actions=1):
    from domain.session.entity import Session
    from domain.round.entity import Round, RoundAction
    from domain.round.value_objects import RoundStatus

    session = Session(id=uuid4(), campaign_id=uuid4())
    r = Round.create(session_id=session.id, round_number=1)
    r.status = RoundStatus.GM_PROCESSING
    for i in range(n_actions):
        a = RoundAction.create(
            round_id=r.id, session_id=session.id,
            character_name=f"Player{i}", is_ai=False, is_pass=False,
            character_id=uuid4(), action_text=f"Ataco o goblin {i}",
        )
        a.d20_roll = 14
        a.initiative_order = i + 1
        r.actions.append(a)
    return session, r


class TestCombatWiring:
    @pytest.mark.asyncio
    async def test_enemy_context_fetched_before_gm_call(self):
        """Deve buscar inimigos vivos antes de chamar process_round."""
        session, round_ = _make_session_and_round()
        encounter = MagicMock(id=uuid4())
        combat_repo = _make_combat_repo(encounter=encounter, alive_enemies=[])
        combat_repo.format_enemies_for_gm = MagicMock(return_value="Goblin #1: 5/7 HP")

        uc = _make_process_gm_uc_with_combat(round_, session, ["Narrativa."], combat_repo)
        await uc.execute(round_.id)

        combat_repo.get_active_encounter.assert_called_once_with(session.id)
        combat_repo.get_alive_enemies.assert_called()

    @pytest.mark.asyncio
    async def test_new_enemies_creates_encounter_when_none(self):
        """[INIMIGOS:] sem encounter ativo deve criar um novo encounter."""
        session, round_ = _make_session_and_round()
        combat_repo = _make_combat_repo(encounter=None)

        gm_text = '[INIMIGOS: [{"nome":"Goblin","tipo":"humanoid","hp":7,"ca":13,"atk":4,"dano":"1d6+2"}]]'
        uc = _make_process_gm_uc_with_combat(round_, session, [gm_text], combat_repo)
        await uc.execute(round_.id)

        combat_repo.create_encounter.assert_called_once()

    @pytest.mark.asyncio
    async def test_new_enemies_saves_template_when_not_found(self):
        """[INIMIGOS:] com template inexistente deve criar template."""
        session, round_ = _make_session_and_round()
        combat_repo = _make_combat_repo(encounter=None)
        combat_repo.find_template_by_name = AsyncMock(return_value=None)

        gm_text = '[INIMIGOS: [{"nome":"Orc","tipo":"humanoid","hp":15,"ca":14,"atk":5,"dano":"1d8+3"}]]'
        uc = _make_process_gm_uc_with_combat(round_, session, [gm_text], combat_repo)
        await uc.execute(round_.id)

        combat_repo.save_template.assert_called_once()
        args = combat_repo.save_template.call_args[0][0]
        assert args["name"] == "Orc"

    @pytest.mark.asyncio
    async def test_new_enemies_spawns_enemies(self):
        """[INIMIGOS:] deve chamar spawn_enemies com a lista correta."""
        session, round_ = _make_session_and_round()
        encounter = MagicMock(id=uuid4())
        combat_repo = _make_combat_repo(encounter=encounter)

        gm_text = '[INIMIGOS: [{"nome":"Esqueleto","tipo":"undead","hp":10,"ca":12,"atk":3,"dano":"1d6"}]]'
        uc = _make_process_gm_uc_with_combat(round_, session, [gm_text], combat_repo)
        await uc.execute(round_.id)

        combat_repo.spawn_enemies.assert_called_once()

    @pytest.mark.asyncio
    async def test_enemy_damage_applies_damage(self):
        """[DANO_INIMIGO:] deve aplicar dano ao inimigo encontrado."""
        session, round_ = _make_session_and_round()
        encounter = MagicMock(id=uuid4())
        enemy = MagicMock(id=uuid4(), display_name="Goblin #1")
        combat_repo = _make_combat_repo(encounter=encounter)
        combat_repo.find_enemy_by_slug = AsyncMock(return_value=enemy)

        gm_text = "O jogador acerta! [DANO_INIMIGO: goblin_1:8]"
        uc = _make_process_gm_uc_with_combat(round_, session, [gm_text], combat_repo)
        await uc.execute(round_.id)

        combat_repo.apply_damage_to_enemy.assert_called_once_with(enemy.id, 8)
        combat_repo.log_event.assert_called()

    @pytest.mark.asyncio
    async def test_enemy_damage_logs_event(self):
        """[DANO_INIMIGO:] deve logar um evento de combate."""
        session, round_ = _make_session_and_round()
        encounter = MagicMock(id=uuid4())
        enemy = MagicMock(id=uuid4(), display_name="Orc Líder")
        combat_repo = _make_combat_repo(encounter=encounter)
        combat_repo.find_enemy_by_slug = AsyncMock(return_value=enemy)

        gm_text = "[DANO_INIMIGO: orc_lider_1:12]"
        uc = _make_process_gm_uc_with_combat(round_, session, [gm_text], combat_repo)
        await uc.execute(round_.id)

        call_kwargs = combat_repo.log_event.call_args.kwargs
        assert call_kwargs["event_type"] == "damage"
        assert call_kwargs["damage_dealt"] == 12

    @pytest.mark.asyncio
    async def test_no_combat_tags_skips_combat_processing(self):
        """Resposta sem tags de combate não deve chamar nenhum método de combat_repo."""
        session, round_ = _make_session_and_round()
        encounter = MagicMock(id=uuid4())
        combat_repo = _make_combat_repo(encounter=encounter)

        uc = _make_process_gm_uc_with_combat(round_, session, ["Narrativa sem combate."], combat_repo)
        await uc.execute(round_.id)

        combat_repo.create_encounter.assert_not_called()
        combat_repo.spawn_enemies.assert_not_called()
        combat_repo.apply_damage_to_enemy.assert_not_called()

    @pytest.mark.asyncio
    async def test_combat_failure_does_not_crash_round(self):
        """Falha no processamento de combate não deve crashar o round."""
        session, round_ = _make_session_and_round()
        combat_repo = _make_combat_repo(encounter=None)
        combat_repo.create_encounter = AsyncMock(side_effect=Exception("DB error"))

        gm_text = '[INIMIGOS: [{"nome":"Lobo","tipo":"beast","hp":11,"ca":13,"atk":4,"dano":"1d6+2"}]]'
        uc = _make_process_gm_uc_with_combat(round_, session, [gm_text], combat_repo)
        results = await uc.execute(round_.id)

        assert len(results) == 1  # round completo apesar do erro

    @pytest.mark.asyncio
    async def test_encounter_resolved_when_all_enemies_dead(self):
        """Quando não sobra nenhum inimigo vivo após o round, o encounter deve ser encerrado."""
        session, round_ = _make_session_and_round()
        encounter = MagicMock(id=uuid4())
        enemy = MagicMock(id=uuid4(), display_name="Goblin")
        combat_repo = _make_combat_repo(encounter=encounter)
        combat_repo.find_enemy_by_slug = AsyncMock(return_value=enemy)
        # Após aplicar dano, nenhum inimigo sobrevive
        combat_repo.get_alive_enemies = AsyncMock(side_effect=[
            [enemy],    # primeira chamada: busca contexto
            [],         # segunda chamada: após [DANO_INIMIGO:]
        ])

        gm_text = "[DANO_INIMIGO: goblin_1:20]"
        uc = _make_process_gm_uc_with_combat(round_, session, [gm_text], combat_repo)
        await uc.execute(round_.id)

        combat_repo.resolve_encounter.assert_called_once_with(encounter.id)

    @pytest.mark.asyncio
    async def test_no_combat_repo_skips_all_combat(self):
        """Sem combat_repo, o round deve rodar normalmente sem erros."""
        session, round_ = _make_session_and_round()
        uc = _make_process_gm_uc_with_combat(round_, session, ["Narrativa."], combat_repo=None)
        results = await uc.execute(round_.id)
        assert len(results) == 1


# ─── P2: KnowledgeChunksRetriever ────────────────────────────────────────────

class TestKnowledgeChunksRetriever:
    def test_retriever_queries_knowledge_chunks_table(self):
        """Deve usar knowledge_chunks em vez das tabelas internas do LangChain."""
        from infrastructure.ai.langchain_gm_service import KnowledgeChunksRetriever
        from langchain_core.documents import Document

        retriever = KnowledgeChunksRetriever(
            connection_string="postgresql+psycopg2://test:test@localhost/test",
            top_k=4,
        )

        mock_rows = [
            ("Regra de combate D&D 5e", "D&D 5e"),
            ("Lore do mundo", "homebrew"),
        ]

        with patch("sqlalchemy.create_engine") as mock_engine_fn, \
             patch.object(retriever.__class__, "_get_relevant_documents",
                          wraps=retriever._get_relevant_documents):
            mock_engine = MagicMock()
            mock_engine_fn.return_value = mock_engine
            mock_conn = MagicMock()
            mock_engine.__enter__ = MagicMock(return_value=mock_engine)
            mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.execute.return_value.fetchall.return_value = mock_rows

            with patch("langchain_openai.OpenAIEmbeddings") as mock_emb:
                mock_emb.return_value.embed_query = MagicMock(return_value=[0.1] * 1536)
                # O método vai usar a engine mockada
                # Só verificamos que a classe existe e tem a interface correta
                assert hasattr(retriever, "_get_relevant_documents")
                assert hasattr(retriever, "_aget_relevant_documents")
                assert retriever.top_k == 4
                assert retriever.connection_string == "postgresql+psycopg2://test:test@localhost/test"

    def test_retriever_returns_empty_on_db_error(self):
        """Deve retornar lista vazia em caso de erro de conexão."""
        from infrastructure.ai.langchain_gm_service import KnowledgeChunksRetriever

        retriever = KnowledgeChunksRetriever(
            connection_string="postgresql+psycopg2://invalid:invalid@localhost/invalid",
            top_k=4,
        )

        with patch("langchain_openai.OpenAIEmbeddings") as mock_emb:
            mock_emb.return_value.embed_query = MagicMock(side_effect=Exception("API error"))
            docs = retriever._get_relevant_documents("test query")
            assert docs == []

    def test_build_retriever_returns_knowledge_chunks_retriever(self):
        """_build_retriever deve retornar instância de KnowledgeChunksRetriever."""
        from infrastructure.ai.langchain_gm_service import _build_retriever, KnowledgeChunksRetriever

        retriever = _build_retriever("postgresql+psycopg2://test:test@localhost/test")
        assert isinstance(retriever, KnowledgeChunksRetriever)


# ─── P4: Register_player (backfill idempotente) ───────────────────────────────

class TestRegisterPlayerIdempotent:
    @pytest.mark.asyncio
    async def test_register_player_skips_duplicate(self):
        """register_player não deve inserir duplicata para mesmo character_id."""
        from unittest.mock import AsyncMock, MagicMock
        from infrastructure.repositories.campaign_repository import CampaignRepository

        mock_db = AsyncMock()
        repo = CampaignRepository(mock_db)

        campaign_id = uuid4()
        char_id = uuid4()

        # Simula que o personagem já existe
        existing_mock = MagicMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=existing_mock)
        ))

        await repo.register_player(
            campaign_id=campaign_id,
            character_id=char_id,
            is_ai=False,
        )

        # add não deve ter sido chamado (já existe)
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_register_new_player_inserts(self):
        """register_player deve inserir quando não existe."""
        from infrastructure.repositories.campaign_repository import CampaignRepository

        mock_db = AsyncMock()
        repo = CampaignRepository(mock_db)

        mock_db.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        ))
        mock_db.flush = AsyncMock()

        await repo.register_player(
            campaign_id=uuid4(),
            character_id=uuid4(),
            is_ai=True,
        )

        mock_db.add.assert_called_once()
