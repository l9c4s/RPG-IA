"""
Testes unitários para o domínio de rounds.
Cobre: RoundStatus, RoundAction, Round (transições de estado, roll_initiative, regras de negócio).
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from uuid import uuid4
from domain.round.entity import Round, RoundAction
from domain.round.value_objects import RoundStatus


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_action(is_pass=False, is_ai=False, action_text="Ataco o goblin"):
    round_id   = uuid4()
    session_id = uuid4()
    char_id    = uuid4()
    return RoundAction.create(
        round_id=round_id,
        session_id=session_id,
        character_name="Thorin" if not is_ai else "Pip (IA)",
        is_ai=is_ai,
        is_pass=is_pass,
        character_id=char_id,
        action_text=action_text if not is_pass else None,
    )


def make_round(num_actions=0, status=RoundStatus.COLLECTING):
    session_id = uuid4()
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


# ─── RoundAction ─────────────────────────────────────────────────────────────

class TestRoundAction:
    def test_create_active_action(self):
        action = make_action()
        assert action.is_pass is False
        assert action.action_text == "Ataco o goblin"
        assert action.d20_roll is None

    def test_create_pass_action(self):
        action = make_action(is_pass=True)
        assert action.is_pass is True
        assert action.action_text is None

    def test_active_action_requires_text(self):
        with pytest.raises(ValueError, match="action_text"):
            RoundAction.create(
                round_id=uuid4(),
                session_id=uuid4(),
                character_name="Hero",
                is_ai=False,
                is_pass=False,
                action_text=None,
            )

    def test_roll_d20_active_action(self):
        action = make_action()
        roll = action.roll_d20()
        assert 1 <= roll <= 20
        assert action.d20_roll == roll

    def test_roll_d20_pass_always_zero(self):
        action = make_action(is_pass=True)
        roll = action.roll_d20()
        assert roll == 0
        assert action.d20_roll == 0

    def test_roll_d20_randomness(self):
        """100 rolls devem ter mais de 1 valor único."""
        results = set()
        for _ in range(100):
            a = make_action()
            results.add(a.roll_d20())
        assert len(results) > 1

    def test_record_gm_outcome(self):
        action = make_action()
        action.record_gm_outcome(
            gm_response="O goblin cai!",
            gm_rolled_dice=True,
            outcome_roll=14,
        )
        assert action.gm_response == "O goblin cai!"
        assert action.gm_rolled_dice is True
        assert action.outcome_roll == 14

    def test_record_gm_outcome_no_roll(self):
        action = make_action()
        action.record_gm_outcome(
            gm_response="Ação bem sucedida.",
            gm_rolled_dice=False,
        )
        assert action.gm_rolled_dice is False
        assert action.outcome_roll is None

    def test_to_dict_includes_required_keys(self):
        action = make_action()
        d = action.to_dict()
        for key in ("id", "round_id", "session_id", "character_name", "is_ai", "is_pass", "action_text"):
            assert key in d

    def test_to_dict_pass_has_null_action_text(self):
        action = make_action(is_pass=True)
        assert action.to_dict()["action_text"] is None

    def test_ai_flag_set_correctly(self):
        ai_action = make_action(is_ai=True)
        human_action = make_action(is_ai=False)
        assert ai_action.is_ai is True
        assert human_action.is_ai is False


# ─── Round ───────────────────────────────────────────────────────────────────

class TestRound:
    def test_create_starts_collecting(self):
        r = Round.create(session_id=uuid4(), round_number=1)
        assert r.status == RoundStatus.COLLECTING
        assert r.round_number == 1
        assert r.actions == []

    def test_all_submitted_false_when_empty(self):
        r = make_round()
        assert r.all_submitted(3) is False

    def test_all_submitted_true_when_enough(self):
        r = make_round(num_actions=3)
        assert r.all_submitted(3) is True

    def test_all_submitted_false_when_partial(self):
        r = make_round(num_actions=2)
        assert r.all_submitted(4) is False

    def test_character_already_submitted(self):
        r = make_round()
        char_id = uuid4()
        action = RoundAction.create(
            round_id=r.id,
            session_id=r.session_id,
            character_name="Elara",
            is_ai=False,
            is_pass=False,
            character_id=char_id,
            action_text="Fireball!",
        )
        r.actions.append(action)
        assert r.character_already_submitted(char_id) is True
        assert r.character_already_submitted(uuid4()) is False

    def test_start_resolving_from_collecting(self):
        r = make_round()
        r.start_resolving()
        assert r.status == RoundStatus.RESOLVING

    def test_start_resolving_fails_from_wrong_status(self):
        r = make_round()
        r.status = RoundStatus.GM_PROCESSING
        with pytest.raises(ValueError, match="resolv"):
            r.start_resolving()

    def test_roll_initiative_requires_resolving(self):
        r = make_round(num_actions=2)
        with pytest.raises(ValueError, match="resolving"):
            r.roll_initiative()

    def test_roll_initiative_orders_correctly(self):
        r = make_round(num_actions=3)
        r.status = RoundStatus.RESOLVING
        ordered = r.roll_initiative()
        # Deve estar em ordem decrescente de d20
        rolls = [a.d20_roll for a in ordered]
        assert rolls == sorted(rolls, reverse=True)

    def test_roll_initiative_assigns_order(self):
        r = make_round(num_actions=3)
        r.status = RoundStatus.RESOLVING
        ordered = r.roll_initiative()
        orders = [a.initiative_order for a in ordered]
        assert sorted(orders) == [1, 2, 3]

    def test_roll_initiative_transitions_to_gm_processing(self):
        r = make_round(num_actions=2)
        r.status = RoundStatus.RESOLVING
        r.roll_initiative()
        assert r.status == RoundStatus.GM_PROCESSING

    def test_passes_get_d20_zero(self):
        session_id = uuid4()
        r = Round.create(session_id=session_id, round_number=1)
        pass_action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name="Garet",
            is_ai=False,
            is_pass=True,
        )
        active_action = RoundAction.create(
            round_id=r.id,
            session_id=session_id,
            character_name="Elara",
            is_ai=False,
            is_pass=False,
            action_text="Lança magia",
        )
        r.actions = [pass_action, active_action]
        r.status = RoundStatus.RESOLVING
        ordered = r.roll_initiative()
        # Passe deve ter d20=0 e estar por último
        pass_entry = next(a for a in ordered if a.is_pass)
        assert pass_entry.d20_roll == 0
        assert pass_entry.initiative_order == 2

    def test_complete_from_gm_processing(self):
        r = make_round()
        r.status = RoundStatus.GM_PROCESSING
        r.complete()
        assert r.status == RoundStatus.COMPLETED

    def test_complete_fails_from_wrong_status(self):
        r = make_round()
        with pytest.raises(ValueError, match="gm_processing"):
            r.complete()

    def test_active_actions_excludes_passes(self):
        session_id = uuid4()
        r = Round.create(session_id=session_id, round_number=1)
        pass_action = RoundAction.create(
            round_id=r.id, session_id=session_id,
            character_name="Garet", is_ai=False, is_pass=True,
        )
        active_action = RoundAction.create(
            round_id=r.id, session_id=session_id,
            character_name="Elara", is_ai=False, is_pass=False,
            action_text="Ataca",
        )
        r.actions = [pass_action, active_action]
        active = r.active_actions()
        assert len(active) == 1
        assert active[0].character_name == "Elara"

    def test_sorted_by_initiative_requires_d20_rolled(self):
        r = make_round(num_actions=2)
        r.status = RoundStatus.RESOLVING
        r.roll_initiative()
        sorted_actions = r.sorted_by_initiative()
        assert all(a.d20_roll is not None for a in sorted_actions)

    def test_to_dict_includes_actions(self):
        r = make_round(num_actions=2)
        d = r.to_dict()
        assert len(d["actions"]) == 2
        assert d["round_number"] == 1
        assert d["status"] == "collecting"


# ─── _d20_tier ────────────────────────────────────────────────────────────────

class TestD20Tier:
    """Testa a função pura _d20_tier() importada do use case."""

    @pytest.fixture(autouse=True)
    def import_tier(self):
        from application.round.use_cases import _d20_tier
        self.tier = _d20_tier

    def test_roll_20_is_critical_success(self):
        assert self.tier(20) == "SUCESSO CRÍTICO"

    def test_roll_16_is_critical_success(self):
        assert self.tier(16) == "SUCESSO CRÍTICO"

    def test_roll_15_is_normal_success(self):
        assert self.tier(15) == "SUCESSO NORMAL"

    def test_roll_10_is_normal_success(self):
        assert self.tier(10) == "SUCESSO NORMAL"

    def test_roll_9_is_failure(self):
        assert self.tier(9) == "FALHA"

    def test_roll_5_is_failure(self):
        assert self.tier(5) == "FALHA"

    def test_roll_4_is_critical_failure(self):
        assert self.tier(4) == "FALHA CRÍTICA"

    def test_roll_1_is_critical_failure(self):
        assert self.tier(1) == "FALHA CRÍTICA"

    def test_boundary_15_vs_16(self):
        assert self.tier(15) != self.tier(16)
        assert self.tier(16) == "SUCESSO CRÍTICO"
        assert self.tier(15) == "SUCESSO NORMAL"

    def test_boundary_9_vs_10(self):
        assert self.tier(9) != self.tier(10)
        assert self.tier(10) == "SUCESSO NORMAL"
        assert self.tier(9) == "FALHA"

    def test_boundary_4_vs_5(self):
        assert self.tier(4) != self.tier(5)
        assert self.tier(5) == "FALHA"
        assert self.tier(4) == "FALHA CRÍTICA"
