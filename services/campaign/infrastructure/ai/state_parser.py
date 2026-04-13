"""
Parser de resposta do GM: extrai tags estruturadas do texto narrativo.
Implementação de infra — os tipos de retorno vivem em domain/gm/entity.py.
"""

import random
import re
from typing import Any

from domain.gm.entity import DiceRoll, StateUpdate

# ─── Inferência narrativa de morte ───────────────────────────────────────────
#
# Quando o GM narra a morte de um inimigo em prosa livre sem usar [DANO_INIMIGO:],
# este módulo detecta a morte pela linguagem e injeta automaticamente o dano fatal.
# Isso cobre o caso em que o GPT-4o ignora as tags estruturadas.
#
# Heurística: se o texto contém palavras de morte E não há [DANO_INIMIGO:] já presente,
# marcar como "inferred_kill=True" para o use case aplicar o kill no inimigo ativo.

_DEATH_KEYWORDS_PT = re.compile(
    r"""
    \b(
      silencia(?:ndo|do)|neutraliza(?:ndo|do)|elimina(?:ndo|do)|abate(?:ndo|u)|
      mata(?:ndo|u)|morreu|morre|cai\s+morto|derrubado|derrotado|tombou|tomba|
      incapacita(?:ndo|do)|coloca(?:ndo)?\s+no\s+chão|ampar(?:a|ou)\s+o\s+corpo|
      corpo\s+do|cai\s+inerte|cai\s+ao\s+chão|sem\s+vida|último\s+suspiro|
      golpe\s+fatal|golpe\s+letal|golpe\s+certeiro|golpe\s+mortal|
      coloca(?:ndo)?\s+(?:o|um)\s+(?:guarda|inimigo|criatura|oponente)|
      antes\s+que\s+(?:ele|ela)\s+possa\s+emitir|silenciado\s+para\s+sempre
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Estima o dano fatal com base no HP do inimigo — usamos hp_max como "golpe que zerou"
_INFERRED_KILL_DAMAGE = 999  # valor sentinela: o use case usa hp_current do inimigo

# Padrões regex para as tags existentes do GM
_ROLL_PATTERN = re.compile(r"\[ROLAGEM:([^\]]+)\]", re.IGNORECASE)
_STATE_PATTERN = re.compile(r"\[ESTADO:([^=\]]+)=([^\]]+)\]", re.IGNORECASE)
_IMAGE_PATTERN = re.compile(r"\[IMAGEM:([^\]]+)\]", re.IGNORECASE)

# ─── Novas tags de combate ────────────────────────────────────────────────────
#
# [INIMIGOS: JSON]          → GM declara inimigos (primeira aparição em cena)
#   Formato: [{"nome":"Goblin","tipo":"goblin","hp":7,"ca":13,"atk":4,"dano":"1d6+2"}]
#
# [DANO_INIMIGO: slug:dano] → Jogador acertou um inimigo
#   Formato: goblin_1:8   (slug do inimigo e dano numérico)
#   O slug é fuzzy-matched no backend
#
# [ATAQUE_INIMIGO: alvo:dano:grupo] → Inimigo atacou jogador(es) (tag narrativa)
#   Formato: Aragon:12:false  ou  todos:8:true
#   grupo=true → dano em área (todos os jogadores)
#   Backend usa esta tag quando attack_pattern=narrative_only
#
# [ITEM_GANHO: personagem:item:tipo] → Personagem obteve item
#   Formato: Aragon:Espada Longa:weapon  (tipo: weapon|armor|consumable|misc)

_INIMIGOS_PATTERN = re.compile(
    r"\[INIMIGOS:\s*(\[.*?\])\s*\]",
    re.IGNORECASE | re.DOTALL,
)
_DANO_INIMIGO_PATTERN = re.compile(
    r"\[DANO_INIMIGO:\s*([^\]:]+):(\d+)\s*\]",
    re.IGNORECASE,
)
_ATAQUE_INIMIGO_PATTERN = re.compile(
    r"\[ATAQUE_INIMIGO:\s*([^:]+):(\d+):(true|false|grupo|individual)\s*\]",
    re.IGNORECASE,
)
_ITEM_GANHO_PATTERN = re.compile(
    r"\[ITEM_GANHO:\s*([^:]+):([^:]+):([^\]]+)\s*\]",
    re.IGNORECASE,
)

# [NPC: nome | descrição]  → GM introduz um NPC nomeado
# Exemplo: [NPC: Capitão Harros | Guarda veterano de armadura enferrujada, cicatriz no rosto]
_NPC_PATTERN = re.compile(
    r"\[NPC:\s*([^|\]]+)\|([^\]]+)\]",
    re.IGNORECASE,
)

# [LOCAL: nome | descrição] → GM introduz ou revela um local
# Exemplo: [LOCAL:Taverna do Ancião|Estabelecimento úmido e escuro no centro da cidade]
_LOCAL_PATTERN = re.compile(
    r"\[LOCAL:\s*([^|\]]+)\|([^\]]+)\]",
    re.IGNORECASE,
)

# Expressão de dado: "2d6+3", "1d20", "3d8-1"
_DICE_EXPR_PATTERN = re.compile(
    r"^(?P<num>\d+)d(?P<sides>\d+)(?P<mod>[+-]\d+)?$", re.IGNORECASE
)


def infer_kill_from_narrative(text: str, has_explicit_damage_tags: bool) -> bool:
    """
    Retorna True quando o GM narrou a morte de um inimigo em prosa livre
    sem usar [DANO_INIMIGO:].

    Só ativa quando:
      1. Não há tags [DANO_INIMIGO:] já presentes (evita dupla contagem)
      2. O texto contém vocabulário inequívoco de morte/eliminação
    """
    if has_explicit_damage_tags:
        return False
    return bool(_DEATH_KEYWORDS_PT.search(text))


def parse_gm_response(text: str) -> dict[str, Any]:
    """
    Extrai tags estruturadas do texto bruto do GM.

    Retorna:
        {
            "clean_text": str,            # texto sem as tags
            "roll_results": list[DiceRoll],
            "state_updates": list[StateUpdate],
            "image_description": str | None,
            # ─── Novas tags de combate ───
            "new_enemies": list[dict],    # [INIMIGOS:] → lista de inimigos a spawnar
            "enemy_damage": list[tuple],  # [DANO_INIMIGO:] → [(slug, damage)]
            "player_attacks": list[dict], # [ATAQUE_INIMIGO:] → [{target, damage, is_group}]
            "items_gained": list[dict],   # [ITEM_GANHO:] → [{char_name, item_name, item_type}]
            "inferred_kill": bool,        # True quando morte narrada em prosa sem tag
        }
    """
    import json

    roll_results: list[DiceRoll] = []
    state_updates: list[StateUpdate] = []
    image_description: str | None = None
    new_enemies: list[dict] = []
    enemy_damage: list[tuple[str, int]] = []
    player_attacks: list[dict] = []
    items_gained: list[dict] = []
    npcs_introduced: list[dict] = []
    locations_introduced: list[dict] = []

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

    # ─── Novas tags de combate ────────────────────────────────────────────────

    # [INIMIGOS: [...JSON...]]
    for match in _INIMIGOS_PATTERN.finditer(text):
        raw_json = match.group(1).strip()
        try:
            enemies = json.loads(raw_json)
            if isinstance(enemies, list):
                new_enemies.extend(enemies)
        except (json.JSONDecodeError, ValueError):
            pass

    # [DANO_INIMIGO: slug:damage]
    for match in _DANO_INIMIGO_PATTERN.finditer(text):
        slug_hint = match.group(1).strip()
        damage = int(match.group(2))
        enemy_damage.append((slug_hint, damage))

    # [ATAQUE_INIMIGO: target:damage:grupo]
    for match in _ATAQUE_INIMIGO_PATTERN.finditer(text):
        target = match.group(1).strip()
        damage = int(match.group(2))
        grupo_str = match.group(3).strip().lower()
        is_group = grupo_str in ("true", "grupo")
        player_attacks.append({
            "target": target,
            "damage": damage,
            "is_group": is_group,
        })

    # [ITEM_GANHO: personagem:item:tipo]
    for match in _ITEM_GANHO_PATTERN.finditer(text):
        char_name = match.group(1).strip()
        item_name = match.group(2).strip()
        item_type = match.group(3).strip().lower()
        # Normaliza tipo
        if item_type not in ("weapon", "armor", "consumable", "misc"):
            item_type = "misc"
        items_gained.append({
            "char_name": char_name,
            "item_name": item_name,
            "item_type": item_type,
        })

    # [NPC: nome | descrição]
    for match in _NPC_PATTERN.finditer(text):
        npc_name = match.group(1).strip()
        npc_desc = match.group(2).strip()
        npcs_introduced.append({"name": npc_name, "description": npc_desc})

    # [LOCAL: nome | descrição]
    for match in _LOCAL_PATTERN.finditer(text):
        loc_name = match.group(1).strip()
        loc_desc = match.group(2).strip()
        locations_introduced.append({"name": loc_name, "description": loc_desc})

    # Remove todas as tags do texto limpo
    clean_text = _ROLL_PATTERN.sub("", text)
    clean_text = _STATE_PATTERN.sub("", clean_text)
    clean_text = _IMAGE_PATTERN.sub("", clean_text)
    clean_text = _INIMIGOS_PATTERN.sub("", clean_text)
    clean_text = _DANO_INIMIGO_PATTERN.sub("", clean_text)
    clean_text = _ATAQUE_INIMIGO_PATTERN.sub("", clean_text)
    clean_text = _ITEM_GANHO_PATTERN.sub("", clean_text)
    clean_text = _NPC_PATTERN.sub("", clean_text)
    clean_text = _LOCAL_PATTERN.sub("", clean_text)
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text).strip()

    # Inferência de morte narrativa (fallback quando GM não usou [DANO_INIMIGO:])
    inferred_kill = infer_kill_from_narrative(text, has_explicit_damage_tags=bool(enemy_damage))

    return {
        "clean_text": clean_text,
        "roll_results": roll_results,
        "state_updates": state_updates,
        "image_description": image_description,
        "new_enemies": new_enemies,
        "enemy_damage": enemy_damage,
        "player_attacks": player_attacks,
        "items_gained": items_gained,
        "npcs_introduced": npcs_introduced,
        "locations_introduced": locations_introduced,
        "inferred_kill": inferred_kill,
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
