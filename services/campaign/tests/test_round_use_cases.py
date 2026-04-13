"""
Testes unitários dos use cases de Round.
Usa mocks para repositório, WS, character client e GM service.
"""

import asyncio
import pytest
import pytest_asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from application.round.dtos import StartRoundDTO, SubmitActionDTO
from application.round.use_cases import (
    ProcessGMTurnUseCase,
    ResolveRoundUseCase,
    StartRoundUseCase,
    SubmitActionUseCase,
)
from domain.round.entity import Round, RoundAction
from domain.round.value_objects import RoundStatus
from domain.session.entity import Session


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_session(campaign_id=None):
    s = Session(
        id=uuid4(),
        campaign_id=campaign_id or uuid4(),
    )
    return s


def make_round(session_id, status=RoundStatus.COLLECTING, num_actions=0):
    r = Round.create(session_id=session_id, round_number=1)
    r.status = status
    for i in range(num_actions):
        char_id = uuid4()
        action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name=f"Player{i}",
            is_ai=False,
            is_pass=False,
            character_id=char_id,
            action_text=f"Action {i}",
        )
        r.actions.append(action)
    return r


def make_round_repo(
    active_round=None,
    last_number=0,
    round_by_id=None,
):
    repo = AsyncMock()
    repo.get_active_by_session = AsyncMock(return_value=active_round)
    repo.get_last_round_number = AsyncMock(return_value=last_number)
    repo.get_by_id = AsyncMock(return_value=round_by_id)
    repo.save = AsyncMock(side_effect=lambda r: r)
    repo.save_action = AsyncMock(return_value=None)
    repo.update_action = AsyncMock(return_value=None)
    return repo


def make_session_repo(session=None):
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=session)
    return repo


def make_character_client(characters=None):
    client = AsyncMock()
    client.list_campaign_characters = AsyncMock(return_value=characters or [])
    return client


def make_gm_service():
    gm = AsyncMock()
    gm.generate_companion_action = AsyncMock(return_value="Ataco o goblin!")
    gm.process_round = AsyncMock(return_value=["O goblin cai!", "O feitiço acerta!"])
    return gm


# ─── StartRoundUseCase ────────────────────────────────────────────────────────

class TestStartRoundUseCase:
    @pytest.fixture
    def session(self):
        return make_session()

    @pytest.fixture
    def basic_uc(self, session):
        return StartRoundUseCase(
            round_repo=make_round_repo(active_round=None),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=[
                {"id": str(uuid4()), "name": "Thorin", "char_type": "pc"},
            ]),
            gm_service=make_gm_service(),
            ws_broadcast_fn=AsyncMock(),
        )

    @pytest.mark.asyncio
    async def test_creates_round_with_collecting_status(self, basic_uc, session):
        dto = StartRoundDTO(session_id=session.id, campaign_id=session.campaign_id)
        result = await basic_uc.execute(dto)
        assert result.status == "collecting"
        assert result.round_number == 1

    @pytest.mark.asyncio
    async def test_raises_if_session_not_found(self, session):
        uc = StartRoundUseCase(
            round_repo=make_round_repo(),
            session_repo=make_session_repo(session=None),
            character_client=make_character_client(),
            gm_service=make_gm_service(),
        )
        with pytest.raises(ValueError, match="não encontrada"):
            await uc.execute(StartRoundDTO(session_id=uuid4(), campaign_id=uuid4()))

    @pytest.mark.asyncio
    async def test_raises_if_active_round_exists(self, session):
        existing_round = make_round(session.id)
        uc = StartRoundUseCase(
            round_repo=make_round_repo(active_round=existing_round),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(),
            gm_service=make_gm_service(),
        )
        with pytest.raises(ValueError, match="round ativo"):
            await uc.execute(StartRoundDTO(session_id=session.id, campaign_id=session.campaign_id))

    @pytest.mark.asyncio
    async def test_round_number_increments(self, session):
        uc = StartRoundUseCase(
            round_repo=make_round_repo(active_round=None, last_number=5),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=[
                {"id": str(uuid4()), "name": "Thorin", "char_type": "pc"},
            ]),
            gm_service=make_gm_service(),
            ws_broadcast_fn=AsyncMock(),
        )
        result = await uc.execute(StartRoundDTO(session_id=session.id, campaign_id=session.campaign_id))
        assert result.round_number == 6

    @pytest.mark.asyncio
    async def test_broadcasts_round_started(self, session):
        broadcast = AsyncMock()
        uc = StartRoundUseCase(
            round_repo=make_round_repo(),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=[
                {"id": str(uuid4()), "name": "Thorin", "char_type": "pc"},
            ]),
            gm_service=make_gm_service(),
            ws_broadcast_fn=broadcast,
        )
        await uc.execute(StartRoundDTO(session_id=session.id, campaign_id=session.campaign_id))
        # Aguarda tasks de background
        await asyncio.sleep(0.01)
        broadcast.assert_called()
        calls = [str(c) for c in broadcast.call_args_list]
        assert any("round_started" in c for c in calls)

    @pytest.mark.asyncio
    async def test_expected_count_matches_party(self, session):
        party = [
            {"id": str(uuid4()), "name": "A", "char_type": "pc"},
            {"id": str(uuid4()), "name": "B", "char_type": "pc"},
            {"id": str(uuid4()), "name": "C (IA)", "char_type": "ai_companion"},
        ]
        uc = StartRoundUseCase(
            round_repo=make_round_repo(),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=party),
            gm_service=make_gm_service(),
            ws_broadcast_fn=AsyncMock(),
        )
        result = await uc.execute(StartRoundDTO(session_id=session.id, campaign_id=session.campaign_id))
        assert result.expected_count == 3


# ─── SubmitActionUseCase ──────────────────────────────────────────────────────

class TestSubmitActionUseCase:
    @pytest.fixture
    def session(self):
        return make_session()

    def make_submit_dto(self, session, character_id=None, is_pass=False, action_text="Ataco!"):
        return SubmitActionDTO(
            session_id=session.id,
            campaign_id=session.campaign_id,
            character_id=character_id or uuid4(),
            character_name="Thorin",
            is_pass=is_pass,
            player_id=uuid4(),
            is_ai=False,
            action_text=None if is_pass else action_text,
        )

    @pytest.mark.asyncio
    async def test_raises_if_no_active_round(self, session):
        uc = SubmitActionUseCase(
            round_repo=make_round_repo(active_round=None),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=[{"id": str(uuid4()), "char_type": "pc", "name": "X"}]),
        )
        with pytest.raises(ValueError, match="round ativo"):
            await uc.execute(self.make_submit_dto(session))

    @pytest.mark.asyncio
    async def test_raises_if_round_not_collecting(self, session):
        active = make_round(session.id, status=RoundStatus.GM_PROCESSING)
        uc = SubmitActionUseCase(
            round_repo=make_round_repo(active_round=active),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=[{"id": str(uuid4()), "char_type": "pc", "name": "X"}]),
        )
        with pytest.raises(ValueError, match="gm_processing"):
            await uc.execute(self.make_submit_dto(session))

    @pytest.mark.asyncio
    async def test_raises_if_character_already_submitted(self, session):
        char_id = uuid4()
        active = make_round(session.id)
        existing = RoundAction.create(
            round_id=active.id,
            session_id=session.id,
            character_name="Thorin",
            is_ai=False,
            is_pass=False,
            character_id=char_id,
            action_text="Ataco",
        )
        active.actions.append(existing)

        uc = SubmitActionUseCase(
            round_repo=make_round_repo(active_round=active),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=[{"id": str(uuid4()), "char_type": "pc", "name": "X"}]),
        )
        with pytest.raises(ValueError, match="já submeteu"):
            dto = self.make_submit_dto(session, character_id=char_id)
            await uc.execute(dto)

    @pytest.mark.asyncio
    async def test_submits_action_successfully(self, session):
        active = make_round(session.id)
        party = [{"id": str(uuid4()), "char_type": "pc", "name": "Thorin"}]

        uc = SubmitActionUseCase(
            round_repo=make_round_repo(active_round=active),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=party),
            ws_broadcast_fn=AsyncMock(),
        )
        result = await uc.execute(self.make_submit_dto(session))
        assert result.submitted_count == 1
        assert result.all_submitted is True  # 1 player, 1 submitted

    @pytest.mark.asyncio
    async def test_submits_pass_action(self, session):
        active = make_round(session.id)
        party = [{"id": str(uuid4()), "char_type": "pc", "name": "Thorin"}]

        uc = SubmitActionUseCase(
            round_repo=make_round_repo(active_round=active),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=party),
            ws_broadcast_fn=AsyncMock(),
        )
        result = await uc.execute(self.make_submit_dto(session, is_pass=True))
        assert result.all_submitted is True

    @pytest.mark.asyncio
    async def test_not_all_submitted_if_partial(self, session):
        active = make_round(session.id)
        party = [
            {"id": str(uuid4()), "char_type": "pc", "name": "A"},
            {"id": str(uuid4()), "char_type": "pc", "name": "B"},
        ]
        uc = SubmitActionUseCase(
            round_repo=make_round_repo(active_round=active),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=party),
            ws_broadcast_fn=AsyncMock(),
        )
        result = await uc.execute(self.make_submit_dto(session))
        assert result.all_submitted is False
        assert result.expected_count == 2

    @pytest.mark.asyncio
    async def test_broadcasts_action_submitted(self, session):
        broadcast = AsyncMock()
        active = make_round(session.id)
        party = [{"id": str(uuid4()), "char_type": "pc", "name": "Thorin"}]

        uc = SubmitActionUseCase(
            round_repo=make_round_repo(active_round=active),
            session_repo=make_session_repo(session=session),
            character_client=make_character_client(characters=party),
            ws_broadcast_fn=broadcast,
        )
        await uc.execute(self.make_submit_dto(session))
        await asyncio.sleep(0.01)
        broadcast.assert_called()
        calls_str = str(broadcast.call_args_list)
        assert "action_submitted" in calls_str


# ─── ResolveRoundUseCase ──────────────────────────────────────────────────────

class TestResolveRoundUseCase:
    @pytest.mark.asyncio
    async def test_raises_if_round_not_found(self):
        uc = ResolveRoundUseCase(round_repo=make_round_repo(round_by_id=None))
        with pytest.raises(ValueError, match="não encontrado"):
            await uc.execute(uuid4())

    @pytest.mark.asyncio
    async def test_transitions_through_resolving(self):
        session_id = uuid4()
        r = make_round(session_id, status=RoundStatus.COLLECTING, num_actions=2)
        broadcast = AsyncMock()

        # Patch _dispatch_gm to avoid real DB calls
        with patch.object(ResolveRoundUseCase, '_dispatch_gm', AsyncMock()):
            uc = ResolveRoundUseCase(
                round_repo=make_round_repo(round_by_id=r),
                ws_broadcast_fn=broadcast,
            )
            result = await uc.execute(r.id)

        assert len(result.initiative_board) == 2
        # GM_PROCESSING após roll_initiative
        assert r.status == RoundStatus.GM_PROCESSING

    @pytest.mark.asyncio
    async def test_broadcasts_initiative_board(self):
        session_id = uuid4()
        r = make_round(session_id, status=RoundStatus.COLLECTING, num_actions=2)
        broadcast = AsyncMock()

        with patch.object(ResolveRoundUseCase, '_dispatch_gm', AsyncMock()):
            uc = ResolveRoundUseCase(
                round_repo=make_round_repo(round_by_id=r),
                ws_broadcast_fn=broadcast,
            )
            await uc.execute(r.id)

        await asyncio.sleep(0.01)
        calls_str = str(broadcast.call_args_list)
        assert "initiative_board" in calls_str

    @pytest.mark.asyncio
    async def test_initiative_board_ordered_by_d20(self):
        session_id = uuid4()
        r = make_round(session_id, status=RoundStatus.COLLECTING, num_actions=3)

        with patch.object(ResolveRoundUseCase, '_dispatch_gm', AsyncMock()):
            uc = ResolveRoundUseCase(
                round_repo=make_round_repo(round_by_id=r),
                ws_broadcast_fn=AsyncMock(),
            )
            result = await uc.execute(r.id)

        rolls = [e.d20_roll for e in result.initiative_board]
        assert rolls == sorted(rolls, reverse=True)


# ─── ProcessGMTurnUseCase — dice roll saving ──────────────────────────────────

def make_gm_processing_round(session_id, d20_rolls=(14, 7)):
    """Cria round em GM_PROCESSING com ações que já têm d20 rolado."""
    r = Round.create(session_id=session_id, round_number=1)
    r.status = RoundStatus.GM_PROCESSING
    for i, roll in enumerate(d20_rolls):
        char_id = uuid4()
        action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name=f"Player{i}",
            is_ai=False,
            is_pass=False,
            character_id=char_id,
            action_text=f"Ataco o inimigo {i}",
        )
        action.d20_roll = roll
        action.initiative_order = i + 1
        r.actions.append(action)
    return r


def make_process_gm_uc(round_: Round, gm_responses: list[str], save_dice_roll_side_effect=None):
    """Monta ProcessGMTurnUseCase com todos os mocks necessários."""
    round_repo = make_round_repo(round_by_id=round_)
    round_repo.save_dice_roll = AsyncMock(
        side_effect=save_dice_roll_side_effect
    )

    knowledge = AsyncMock()
    knowledge.check_gate = AsyncMock(return_value=True)

    gm = AsyncMock()
    gm.process_round = AsyncMock(return_value=gm_responses)

    message_repo = AsyncMock()
    message_repo.save = AsyncMock()

    return ProcessGMTurnUseCase(
        round_repo=round_repo,
        message_repo=message_repo,
        gm_service=gm,
        knowledge_retriever=knowledge,
        ws_broadcast_fn=AsyncMock(),
        character_client=None,
    ), round_repo


class TestProcessGMTurnUseCaseDiceRolls:
    @pytest.mark.asyncio
    async def test_saves_initiative_d20_for_each_active_action(self):
        session_id = uuid4()
        round_ = make_gm_processing_round(session_id, d20_rolls=(18, 6))
        uc, repo = make_process_gm_uc(round_, gm_responses=["Acerta!", "Falha!"])

        await uc.execute(round_.id)

        # save_dice_roll deve ter sido chamado pelo menos 2x (1 por ação — d20 iniciativa)
        initiative_calls = [
            c for c in repo.save_dice_roll.call_args_list
            if c.kwargs.get("roll_type") == "initiative"
        ]
        assert len(initiative_calls) == 2

    @pytest.mark.asyncio
    async def test_initiative_d20_saved_with_correct_expr_and_result(self):
        session_id = uuid4()
        round_ = make_gm_processing_round(session_id, d20_rolls=(18,))
        uc, repo = make_process_gm_uc(round_, gm_responses=["Sucesso crítico!"])

        await uc.execute(round_.id)

        call = next(
            c for c in repo.save_dice_roll.call_args_list
            if c.kwargs.get("roll_type") == "initiative"
        )
        assert call.kwargs["dice_expr"] == "1d20"
        assert call.kwargs["result"] == 18

    @pytest.mark.asyncio
    async def test_initiative_d20_breakdown_contains_tier(self):
        session_id = uuid4()
        round_ = make_gm_processing_round(session_id, d20_rolls=(4,))
        uc, repo = make_process_gm_uc(round_, gm_responses=["Falha catastrófica!"])

        await uc.execute(round_.id)

        call = next(
            c for c in repo.save_dice_roll.call_args_list
            if c.kwargs.get("roll_type") == "initiative"
        )
        assert call.kwargs["breakdown"]["tier"] == "FALHA CRÍTICA"

    @pytest.mark.asyncio
    async def test_saves_gm_roll_when_rolagem_tag_present(self):
        session_id = uuid4()
        round_ = make_gm_processing_round(session_id, d20_rolls=(12,))
        # GM retorna resposta com tag [ROLAGEM:1d20+5] que será parseada
        uc, repo = make_process_gm_uc(
            round_,
            gm_responses=["O goblin tenta resistir [ROLAGEM:1d20+3]. Ele falha!"],
        )

        await uc.execute(round_.id)

        action_calls = [
            c for c in repo.save_dice_roll.call_args_list
            if c.kwargs.get("roll_type") == "action"
        ]
        assert len(action_calls) == 1
        assert action_calls[0].kwargs["dice_expr"] == "1d20+3"

    @pytest.mark.asyncio
    async def test_no_action_roll_saved_when_no_rolagem_tag(self):
        session_id = uuid4()
        round_ = make_gm_processing_round(session_id, d20_rolls=(15,))
        uc, repo = make_process_gm_uc(
            round_,
            gm_responses=["O personagem age com sucesso, sem dados necessários."],
        )

        await uc.execute(round_.id)

        action_calls = [
            c for c in repo.save_dice_roll.call_args_list
            if c.kwargs.get("roll_type") == "action"
        ]
        assert len(action_calls) == 0

    @pytest.mark.asyncio
    async def test_dice_roll_save_failure_does_not_crash_round(self):
        session_id = uuid4()
        round_ = make_gm_processing_round(session_id, d20_rolls=(10,))
        uc, repo = make_process_gm_uc(
            round_,
            gm_responses=["Sucesso normal."],
            save_dice_roll_side_effect=Exception("DB unavailable"),
        )

        # Não deve lançar exceção — erros de save são engolidos
        results = await uc.execute(round_.id)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_pass_actions_not_included_in_initiative_saves(self):
        """Ações is_pass=True ficam fora de active_actions — não geram save de d20."""
        session_id = uuid4()
        r = Round.create(session_id=session_id, round_number=1)
        r.status = RoundStatus.GM_PROCESSING

        pass_action = RoundAction.create(
            round_id=r.id, session_id=session_id,
            character_name="Garet", is_ai=False, is_pass=True,
        )
        pass_action.d20_roll = 0
        pass_action.initiative_order = 2
        r.actions.append(pass_action)

        uc, repo = make_process_gm_uc(r, gm_responses=[])

        await uc.execute(r.id)

        # Nenhum save de d20 pois não há active_actions
        assert repo.save_dice_roll.call_count == 0

    @pytest.mark.asyncio
    async def test_character_id_passed_to_dice_roll_save(self):
        session_id = uuid4()
        char_id = uuid4()
        r = Round.create(session_id=session_id, round_number=1)
        r.status = RoundStatus.GM_PROCESSING

        action = RoundAction.create(
            round_id=r.id, session_id=session_id,
            character_name="Elara", is_ai=False, is_pass=False,
            character_id=char_id, action_text="Lança feitiço",
        )
        action.d20_roll = 19
        action.initiative_order = 1
        r.actions.append(action)

        uc, repo = make_process_gm_uc(r, gm_responses=["Crítico!"])

        await uc.execute(r.id)

        initiative_call = next(
            c for c in repo.save_dice_roll.call_args_list
            if c.kwargs.get("roll_type") == "initiative"
        )
        assert initiative_call.kwargs["character_id"] == char_id
        assert initiative_call.kwargs["session_id"] == session_id
