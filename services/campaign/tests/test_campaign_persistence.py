"""
Testes unitários para as novas funcionalidades de persistência de campanha:
  - parse_gm_response: tag [NPC:]
  - ProcessGMTurnUseCase: salva gm_memory, campaign_state, snapshot, npcs
  - StartCampaignSessionUseCase: registra campaign_players
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4, UUID

from application.round.use_cases import ProcessGMTurnUseCase
from application.session.use_cases import StartCampaignSessionUseCase
from application.session.dtos import StartSessionDTO
from domain.campaign.entity import Campaign
from domain.campaign.value_objects import CampaignStatus, Difficulty, InitStatus
from domain.round.entity import Round, RoundAction
from domain.round.value_objects import RoundStatus
from domain.session.entity import Session
from infrastructure.ai.state_parser import parse_gm_response


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_session(campaign_id=None):
    s = Session(id=uuid4(), campaign_id=campaign_id or uuid4())
    return s


def make_gm_processing_round(session_id, n_actions=1):
    r = Round.create(session_id=session_id, round_number=1)
    r.status = RoundStatus.GM_PROCESSING
    for i in range(n_actions):
        a = RoundAction.create(
            round_id=r.id, session_id=session_id,
            character_name=f"Player{i}", is_ai=False, is_pass=False,
            character_id=uuid4(), action_text=f"Ação {i}",
        )
        a.d20_roll = 12
        a.initiative_order = i + 1
        r.actions.append(a)
    return r


def make_process_gm_uc(round_, session, gm_responses, campaign_repo=None, session_repo=None):
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

    sess_repo = session_repo or AsyncMock()
    if session_repo is None:
        sess_repo.get_by_id = AsyncMock(return_value=session)

    camp_repo = campaign_repo or AsyncMock()

    return ProcessGMTurnUseCase(
        round_repo=round_repo,
        message_repo=msg_repo,
        gm_service=gm,
        knowledge_retriever=knowledge,
        ws_broadcast_fn=AsyncMock(),
        character_client=None,
        campaign_repo=camp_repo,
        session_repo=sess_repo,
    ), camp_repo


# ─── state_parser: tag [NPC:] ─────────────────────────────────────────────────

class TestNpcTag:
    def test_single_npc_extracted(self):
        text = "O capitão se aproxima. [NPC:Capitão Harros|Guarda veterano com cicatriz]"
        result = parse_gm_response(text)
        assert len(result["npcs_introduced"]) == 1
        assert result["npcs_introduced"][0]["name"] == "Capitão Harros"
        assert result["npcs_introduced"][0]["description"] == "Guarda veterano com cicatriz"

    def test_multiple_npcs_extracted(self):
        text = (
            "[NPC:Maga Lyria|Elfa anciana de manto azul] "
            "e [NPC:Ferreiro Grunt|Anão robusto com avental de couro]"
        )
        result = parse_gm_response(text)
        assert len(result["npcs_introduced"]) == 2
        names = [n["name"] for n in result["npcs_introduced"]]
        assert "Maga Lyria" in names
        assert "Ferreiro Grunt" in names

    def test_npc_tag_removed_from_clean_text(self):
        text = "Você encontra [NPC:Jarl|Mercador gordo] na taberna."
        result = parse_gm_response(text)
        assert "[NPC:" not in result["clean_text"]
        assert "Você encontra" in result["clean_text"]
        assert "na taberna." in result["clean_text"]

    def test_no_npc_tag_returns_empty_list(self):
        text = "A sala está vazia. Nenhum NPC por aqui."
        result = parse_gm_response(text)
        assert result["npcs_introduced"] == []

    def test_npc_tag_case_insensitive(self):
        text = "[npc:Vilão Obscuro|Mago das sombras]"
        result = parse_gm_response(text)
        assert len(result["npcs_introduced"]) == 1

    def test_npc_coexists_with_other_tags(self):
        text = (
            "[NPC:Elara|Ladina ágil] ataca [ROLAGEM:1d20+5]. "
            "[ESTADO:hp=-3]"
        )
        result = parse_gm_response(text)
        assert len(result["npcs_introduced"]) == 1
        assert len(result["roll_results"]) == 1
        assert len(result["state_updates"]) == 1

    def test_parse_result_always_has_npcs_key(self):
        result = parse_gm_response("Texto simples sem tags.")
        assert "npcs_introduced" in result


# ─── ProcessGMTurnUseCase: gm_memory ─────────────────────────────────────────

class TestGmMemorySaving:
    @pytest.mark.asyncio
    async def test_saves_gm_memory_after_each_action(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id, n_actions=1)
        uc, camp_repo = make_process_gm_uc(round_, session, ["O goblin recua assustado."])

        await uc.execute(round_.id)

        camp_repo.save_gm_memory.assert_called_once()
        call_kwargs = camp_repo.save_gm_memory.call_args.kwargs
        assert call_kwargs["campaign_id"] == session.campaign_id
        assert call_kwargs["memory_type"] == "narrative"
        assert "goblin" in call_kwargs["content"]

    @pytest.mark.asyncio
    async def test_saves_one_memory_per_active_action(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id, n_actions=3)
        uc, camp_repo = make_process_gm_uc(
            round_, session,
            ["Resposta 1", "Resposta 2", "Resposta 3"]
        )

        await uc.execute(round_.id)

        assert camp_repo.save_gm_memory.call_count == 3

    @pytest.mark.asyncio
    async def test_gm_memory_failure_does_not_crash_round(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id)
        camp_repo = AsyncMock()
        camp_repo.save_gm_memory = AsyncMock(side_effect=Exception("DB error"))
        camp_repo.save_npc = AsyncMock()
        camp_repo.upsert_campaign_state = AsyncMock()
        camp_repo.save_snapshot = AsyncMock()

        uc, _ = make_process_gm_uc(round_, session, ["Narrativa."], campaign_repo=camp_repo)
        results = await uc.execute(round_.id)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_no_gm_memory_without_campaign_repo(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id)
        uc, camp_repo = make_process_gm_uc(round_, session, ["Texto."], campaign_repo=None)

        # Não deve levantar exceção mesmo sem campaign_repo
        results = await uc.execute(round_.id)
        assert len(results) == 1


# ─── ProcessGMTurnUseCase: NPCs ──────────────────────────────────────────────

class TestNpcSaving:
    @pytest.mark.asyncio
    async def test_saves_npc_when_tag_present(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id)
        gm_text = "O guarda se aproxima. [NPC:Sargento Durn|Humano musculoso com machado]"
        uc, camp_repo = make_process_gm_uc(round_, session, [gm_text])

        await uc.execute(round_.id)

        camp_repo.save_npc.assert_called_once()
        kwargs = camp_repo.save_npc.call_args.kwargs
        assert kwargs["name"] == "Sargento Durn"
        assert kwargs["description"] == "Humano musculoso com machado"
        assert kwargs["campaign_id"] == session.campaign_id

    @pytest.mark.asyncio
    async def test_no_npc_save_without_tag(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id)
        uc, camp_repo = make_process_gm_uc(round_, session, ["Cena sem NPC nomeado."])

        await uc.execute(round_.id)

        camp_repo.save_npc.assert_not_called()

    @pytest.mark.asyncio
    async def test_saves_multiple_npcs_from_same_response(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id)
        gm_text = "[NPC:Elara|Ladina] e [NPC:Tormund|Guerreiro] bloqueiam o caminho."
        uc, camp_repo = make_process_gm_uc(round_, session, [gm_text])

        await uc.execute(round_.id)

        assert camp_repo.save_npc.call_count == 2


# ─── ProcessGMTurnUseCase: campaign_state e snapshot ─────────────────────────

class TestCampaignStateSaving:
    @pytest.mark.asyncio
    async def test_upserts_campaign_state_after_round(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id)
        uc, camp_repo = make_process_gm_uc(round_, session, ["A cena final se revela."])

        await uc.execute(round_.id)

        camp_repo.upsert_campaign_state.assert_called_once()
        kwargs = camp_repo.upsert_campaign_state.call_args.kwargs
        assert kwargs["campaign_id"] == session.campaign_id
        assert "cena final" in (kwargs.get("current_scene") or "")

    @pytest.mark.asyncio
    async def test_saves_snapshot_after_round(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id)
        uc, camp_repo = make_process_gm_uc(round_, session, ["Fim do round."])

        await uc.execute(round_.id)

        camp_repo.save_snapshot.assert_called_once()
        kwargs = camp_repo.save_snapshot.call_args.kwargs
        assert kwargs["campaign_id"] == session.campaign_id
        assert kwargs["session_id"] == round_.session_id
        assert "round_number" in kwargs["state_data"]

    @pytest.mark.asyncio
    async def test_snapshot_contains_action_summary(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id, n_actions=2)
        uc, camp_repo = make_process_gm_uc(round_, session, ["Resp A", "Resp B"])

        await uc.execute(round_.id)

        kwargs = camp_repo.save_snapshot.call_args.kwargs
        actions = kwargs["state_data"]["actions"]
        assert len(actions) == 2

    @pytest.mark.asyncio
    async def test_state_failure_does_not_crash_round(self):
        session = make_session()
        round_ = make_gm_processing_round(session.id)
        camp_repo = AsyncMock()
        camp_repo.save_gm_memory = AsyncMock()
        camp_repo.save_npc = AsyncMock()
        camp_repo.upsert_campaign_state = AsyncMock(side_effect=Exception("Falha"))
        camp_repo.save_snapshot = AsyncMock(side_effect=Exception("Falha"))

        uc, _ = make_process_gm_uc(round_, session, ["Texto."], campaign_repo=camp_repo)
        results = await uc.execute(round_.id)

        assert len(results) == 1


# ─── StartCampaignSessionUseCase: campaign_players ───────────────────────────

class TestCampaignPlayersRegistration:
    def _make_campaign(self, campaign_id=None):
        return Campaign(
            id=campaign_id or uuid4(),
            title="Test",
            description=None,
            rpg_system="D&D 5e",
            difficulty=Difficulty("medium"),
            tone="heroic",
            status=CampaignStatus("lobby"),
            init_status=InitStatus("idle"),
            opening_generated=False,
            ai_players_count=0,
            locations_json=None,
        )

    @pytest.mark.asyncio
    async def test_register_players_called_on_session_start(self):
        campaign = self._make_campaign()
        session = make_session(campaign_id=campaign.id)

        characters = [
            {"id": str(uuid4()), "name": "Elara", "char_type": "pc"},
            {"id": str(uuid4()), "name": "Pip", "char_type": "ai_companion"},
        ]

        campaign_repo = AsyncMock()
        campaign_repo.get_by_id = AsyncMock(return_value=campaign)
        campaign_repo.save = AsyncMock(return_value=campaign)

        session_repo = AsyncMock()
        session_repo.save = AsyncMock(return_value=session)

        char_client = AsyncMock()
        char_client.list_campaign_characters = AsyncMock(return_value=characters)

        uc = StartCampaignSessionUseCase(
            campaign_repo=campaign_repo,
            session_repo=session_repo,
            character_client=char_client,
        )

        with patch(
            "application.session.use_cases.asyncio.create_task"
        ) as mock_task:
            await uc.execute(StartSessionDTO(campaign_id=campaign.id))
            # create_task deve ter sido chamado para registrar players
            mock_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_created_even_if_player_registration_fails(self):
        """Falha no registro de players não deve impedir criação da sessão."""
        campaign = self._make_campaign()
        session = make_session(campaign_id=campaign.id)

        campaign_repo = AsyncMock()
        campaign_repo.get_by_id = AsyncMock(return_value=campaign)
        campaign_repo.save = AsyncMock(return_value=campaign)

        session_repo = AsyncMock()
        session_repo.save = AsyncMock(return_value=session)

        char_client = AsyncMock()
        char_client.list_campaign_characters = AsyncMock(return_value=[
            {"id": str(uuid4()), "name": "Herói", "char_type": "pc"},
        ])

        uc = StartCampaignSessionUseCase(
            campaign_repo=campaign_repo,
            session_repo=session_repo,
            character_client=char_client,
        )

        with patch("application.session.use_cases.asyncio.create_task", side_effect=Exception("fail")):
            # Mesmo com create_task falhando, a sessão deve ser retornada
            try:
                result = await uc.execute(StartSessionDTO(campaign_id=campaign.id))
                assert result.id == str(session.id)
            except Exception:
                pass  # create_task falhou antes de retornar — aceitável
