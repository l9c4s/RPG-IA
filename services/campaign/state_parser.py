import re
import random
from typing import Any


# Regex patterns for GM response tags
_ROLL_PATTERN = re.compile(r"\[ROLAGEM:([^\]]+)\]", re.IGNORECASE)
_STATE_PATTERN = re.compile(r"\[ESTADO:([^=\]]+)=([^\]]+)\]", re.IGNORECASE)
_IMAGE_PATTERN = re.compile(r"\[IMAGEM:([^\]]+)\]", re.IGNORECASE)

# Dice expression: e.g. "2d6+3", "1d20", "3d8-1"
_DICE_EXPR_PATTERN = re.compile(
    r"^(?P<num>\d+)d(?P<sides>\d+)(?P<mod>[+-]\d+)?$", re.IGNORECASE
)


def parse_gm_response(text: str) -> dict[str, Any]:
    """
    Parse GM response text and extract structured action tags.

    Returns:
        {
            "clean_text": str,          # text with all tags removed
            "actions": list[dict],      # list of parsed action objects
        }

    Action shapes:
        {"type": "roll",  "expr": "1d20+5"}
        {"type": "state", "field": "hp", "value": "-5"}
        {"type": "image", "description": "..."}
    """
    actions: list[dict[str, Any]] = []

    # Extract roll tags
    for match in _ROLL_PATTERN.finditer(text):
        expr = match.group(1).strip()
        actions.append({"type": "roll", "expr": expr})

    # Extract state tags
    for match in _STATE_PATTERN.finditer(text):
        field = match.group(1).strip()
        value = match.group(2).strip()
        actions.append({"type": "state", "field": field, "value": value})

    # Extract image tags (only first one matters per response)
    image_match = _IMAGE_PATTERN.search(text)
    if image_match:
        description = image_match.group(1).strip()
        actions.append({"type": "image", "description": description})

    # Remove all tags from text to produce the clean narrative
    clean_text = _ROLL_PATTERN.sub("", text)
    clean_text = _STATE_PATTERN.sub("", clean_text)
    clean_text = _IMAGE_PATTERN.sub("", clean_text)

    # Normalise multiple blank lines left by tag removal
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

    return {"clean_text": clean_text, "actions": actions}


def roll_dice(expr: str) -> dict[str, Any]:
    """
    Parse a dice expression like "2d6+3" or "1d20" and roll it.

    Returns:
        {
            "expr":      str,   # original expression, e.g. "2d6+3"
            "result":    int,   # final total
            "breakdown": str,   # human-readable detail, e.g. "[4, 3] + 3 = 10"
        }

    Raises:
        ValueError: if the expression cannot be parsed.
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

    # Build human-readable breakdown
    rolls_str = str(rolls) if len(rolls) > 1 else str(rolls[0])
    if modifier == 0:
        breakdown = f"{rolls_str} = {final_result}"
    elif modifier > 0:
        breakdown = f"{rolls_str} + {modifier} = {final_result}"
    else:
        breakdown = f"{rolls_str} - {abs(modifier)} = {final_result}"

    return {
        "expr": expr,
        "result": final_result,
        "breakdown": breakdown,
    }
