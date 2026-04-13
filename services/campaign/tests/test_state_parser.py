"""Unit tests for state_parser — dice rolling and GM response parsing (DDD API)."""
import pytest

from infrastructure.ai.state_parser import parse_gm_response, roll_dice
from domain.gm.entity import DiceRoll, StateUpdate


# ── roll_dice ─────────────────────────────────────────────────────────────────
# Returns DiceRoll dataclass: .expr, .result, .breakdown
# Raises ValueError on invalid input

class TestRollDice:
    def test_basic_d20(self):
        result = roll_dice("1d20")
        assert isinstance(result, DiceRoll)
        assert 1 <= result.result <= 20

    def test_multiple_dice(self):
        result = roll_dice("2d6")
        assert 2 <= result.result <= 12

    def test_with_modifier(self):
        result = roll_dice("1d6+3")
        assert 4 <= result.result <= 9

    def test_negative_modifier(self):
        result = roll_dice("1d4-1")
        assert 0 <= result.result <= 3

    def test_breakdown_included(self):
        result = roll_dice("2d6")
        assert result.breakdown is not None
        assert len(result.breakdown) > 0

    def test_expression_stored(self):
        result = roll_dice("3d8+2")
        assert result.expr == "3d8+2"

    def test_d100_valid(self):
        result = roll_dice("1d100")
        assert 1 <= result.result <= 100

    def test_too_many_dice_raises(self):
        with pytest.raises(ValueError, match="dados"):
            roll_dice("200d6")

    def test_invalid_expression_raises(self):
        with pytest.raises(ValueError, match="[Ii]nválid"):
            roll_dice("notadice")

    def test_d1000_sides_valid(self):
        result = roll_dice("1d1000")
        assert 1 <= result.result <= 1000

    def test_d1_raises_invalid_sides(self):
        with pytest.raises(ValueError):
            roll_dice("1d1")  # sides < 2

    def test_repeated_rolls_vary(self):
        """Statistical test — 100 d20 rolls should not all be the same."""
        results = {roll_dice("1d20").result for _ in range(100)}
        assert len(results) > 1

    def test_modifier_zero_omitted_in_breakdown(self):
        result = roll_dice("1d6")
        assert "+" not in result.breakdown or "= " in result.breakdown

    def test_positive_modifier_in_breakdown(self):
        result = roll_dice("1d6+5")
        assert "+ 5" in result.breakdown

    def test_negative_modifier_in_breakdown(self):
        result = roll_dice("1d6-2")
        assert "- 2" in result.breakdown


# ── parse_gm_response ─────────────────────────────────────────────────────────
# Returns:
#   {
#     "clean_text": str,
#     "roll_results": list[DiceRoll],
#     "state_updates": list[StateUpdate],
#     "image_description": str | None,
#     "new_enemies": list[dict],
#     "enemy_damage": list[tuple],
#     "player_attacks": list[dict],
#     "items_gained": list[dict],
#   }

class TestParseGMResponse:
    def test_no_tags(self):
        result = parse_gm_response("You enter the tavern. The innkeeper nods.")
        assert result["roll_results"] == []
        assert result["state_updates"] == []
        assert result["image_description"] is None
        assert "tavern" in result["clean_text"]

    def test_extracts_roll_tag(self):
        text = "The goblin attacks! [ROLAGEM:1d20+5] You must defend yourself."
        result = parse_gm_response(text)
        rolls = result["roll_results"]
        assert len(rolls) == 1
        assert rolls[0].expr == "1d20+5"

    def test_extracts_multiple_rolls(self):
        text = "[ROLAGEM:1d20] [ROLAGEM:2d6+3] Two rolls here."
        result = parse_gm_response(text)
        assert len(result["roll_results"]) == 2

    def test_extracts_state_tag(self):
        text = "You take damage. [ESTADO:hp_current=15] Your wounds bleed."
        result = parse_gm_response(text)
        states = result["state_updates"]
        assert len(states) == 1
        assert states[0].field == "hp_current"
        assert states[0].value == "15"

    def test_extracts_multiple_states(self):
        text = "[ESTADO:hp_current=8][ESTADO:exhaustion=1] Feeling sick."
        result = parse_gm_response(text)
        assert len(result["state_updates"]) == 2

    def test_extracts_image_tag(self):
        text = "A dragon appears! [IMAGEM:A massive red dragon breathing fire over a castle]"
        result = parse_gm_response(text)
        assert result["image_description"] is not None
        assert "dragon" in result["image_description"].lower()

    def test_text_cleaned_of_roll_tags(self):
        text = "Attack! [ROLAGEM:1d20] Critical hit!"
        result = parse_gm_response(text)
        assert "[ROLAGEM:" not in result["clean_text"]

    def test_text_cleaned_of_state_tags(self):
        text = "You weaken. [ESTADO:hp_current=5] The spell fades."
        result = parse_gm_response(text)
        assert "[ESTADO:" not in result["clean_text"]

    def test_text_cleaned_of_image_tags(self):
        text = "You see it. [IMAGEM:A glowing doorway] Step inside."
        result = parse_gm_response(text)
        assert "[IMAGEM:" not in result["clean_text"]

    def test_empty_response(self):
        result = parse_gm_response("")
        assert result["clean_text"] == ""
        assert result["roll_results"] == []
        assert result["state_updates"] == []

    def test_narrative_preserved(self):
        text = "The hero stands tall. [ROLAGEM:1d20] Victory!"
        result = parse_gm_response(text)
        assert "hero" in result["clean_text"]
        assert "Victory" in result["clean_text"]

    def test_mixed_tags(self):
        text = "[ROLAGEM:1d8] [ESTADO:hp=10] [IMAGEM:Ruins under moonlight]"
        result = parse_gm_response(text)
        assert len(result["roll_results"]) == 1
        assert len(result["state_updates"]) == 1
        assert result["image_description"] is not None
