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
