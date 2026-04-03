"""
Parser de resposta do GM: extrai tags estruturadas do texto narrativo.
Implementação de infra — os tipos de retorno vivem em domain/gm/entity.py.
"""

import random
import re
from typing import Any

from domain.gm.entity import DiceRoll, StateUpdate

# Padrões regex para as tags do GM
_ROLL_PATTERN = re.compile(r"\[ROLAGEM:([^\]]+)\]", re.IGNORECASE)
_STATE_PATTERN = re.compile(r"\[ESTADO:([^=\]]+)=([^\]]+)\]", re.IGNORECASE)
_IMAGE_PATTERN = re.compile(r"\[IMAGEM:([^\]]+)\]", re.IGNORECASE)

# Expressão de dado: "2d6+3", "1d20", "3d8-1"
_DICE_EXPR_PATTERN = re.compile(
    r"^(?P<num>\d+)d(?P<sides>\d+)(?P<mod>[+-]\d+)?$", re.IGNORECASE
)


def parse_gm_response(text: str) -> dict[str, Any]:
    """
    Extrai tags estruturadas do texto bruto do GM.

    Retorna:
        {
            "clean_text": str,       # texto sem as tags
            "roll_results": list[DiceRoll],
            "state_updates": list[StateUpdate],
            "image_description": str | None,
        }
    """
    roll_results: list[DiceRoll] = []
    state_updates: list[StateUpdate] = []
    image_description: str | None = None

    # Extrai e resolve rolagens
    for match in _ROLL_PATTERN.finditer(text):
        expr = match.group(1).strip()
        try:
            roll = roll_dice(expr)
            roll_results.append(roll)
        except ValueError:
            pass

    # Extrai mudanças de estado
    for match in _STATE_PATTERN.finditer(text):
        field = match.group(1).strip()
        value = match.group(2).strip()
        state_updates.append(StateUpdate(field=field, value=value))

    # Extrai descrição de imagem (apenas a primeira)
    image_match = _IMAGE_PATTERN.search(text)
    if image_match:
        image_description = image_match.group(1).strip()

    # Remove todas as tags do texto
    clean_text = _ROLL_PATTERN.sub("", text)
    clean_text = _STATE_PATTERN.sub("", clean_text)
    clean_text = _IMAGE_PATTERN.sub("", clean_text)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

    return {
        "clean_text": clean_text,
        "roll_results": roll_results,
        "state_updates": state_updates,
        "image_description": image_description,
    }


def roll_dice(expr: str) -> DiceRoll:
    """
    Interpreta e rola uma expressão de dados como "2d6+3" ou "1d20".

    Retorna um DiceRoll com expr, result e breakdown legível.
    Lança ValueError se a expressão for inválida.
    """
    expr = expr.strip()
    m = _DICE_EXPR_PATTERN.match(expr)
    if not m:
        raise ValueError(
            f"Expressão de dado inválida: '{expr}'. "
            "Formato esperado: NdS, NdS+M ou NdS-M (ex: 2d6+3, 1d20, 3d8-1)"
        )

    num_dice = int(m.group("num"))
    sides = int(m.group("sides"))
    modifier_str = m.group("mod") or "+0"
    modifier = int(modifier_str)

    if num_dice < 1 or num_dice > 100:
        raise ValueError(f"Número de dados deve ser entre 1 e 100, recebido: {num_dice}")
    if sides < 2 or sides > 1000:
        raise ValueError(f"Número de faces deve ser entre 2 e 1000, recebido: {sides}")

    rolls = [random.randint(1, sides) for _ in range(num_dice)]
    dice_total = sum(rolls)
    final_result = dice_total + modifier

    rolls_str = str(rolls) if len(rolls) > 1 else str(rolls[0])
    if modifier == 0:
        breakdown = f"{rolls_str} = {final_result}"
    elif modifier > 0:
        breakdown = f"{rolls_str} + {modifier} = {final_result}"
    else:
        breakdown = f"{rolls_str} - {abs(modifier)} = {final_result}"

    return DiceRoll(expr=expr, result=final_result, breakdown=breakdown)
