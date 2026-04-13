"""
Gerador de inventário inicial via LLM (OpenAI GPT-4o).

Fluxo:
  1. Lookup estático define as 6 CATEGORIAS de slots para a classe do personagem
     (sem custo de API — determinístico)
  2. LLM gera nome único + stats para cada slot em 1 única chamada
     (criativo, temático para raça+classe, com stat_bonuses relevantes)

Os itens gerados têm is_starting_item=True e rarity='common'.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


# ─── Slots de equipamento inicial por classe ──────────────────────────────────
# Define a CATEGORIA de cada um dos 6 slots.
# O LLM recebe estes slots e gera itens temáticos para cada um.

_STARTING_SLOTS: dict[str, list[str]] = {
    # Português
    "bárbaro":    ["arma_pesada_corpo_a_corpo", "armadura_leve", "arma_secundaria", "consumível", "utensílio", "misc"],
    "bardo":      ["instrumento_musical", "arma_simples", "armadura_leve", "consumível", "utensílio", "misc"],
    "clérigo":    ["arma_simples", "armadura_media", "escudo", "símbolo_sagrado", "consumível", "misc"],
    "druida":     ["cajado", "armadura_leve", "foco_druídico", "consumível", "utensílio", "misc"],
    "guerreiro":  ["arma_marcial", "armadura_media", "escudo", "arma_secundaria", "consumível", "utensílio"],
    "monge":      ["arma_simples", "roupa_de_monge", "faixa_de_ki", "consumível", "utensílio", "misc"],
    "paladino":   ["arma_marcial", "armadura_media", "escudo", "símbolo_sagrado", "consumível", "misc"],
    "patrulheiro":["arma_de_longo_alcance", "armadura_media", "arma_corpo_a_corpo", "consumível", "utensílio", "misc"],
    "ladino":     ["arma_leve_ou_de_arremesso", "armadura_leve", "ferramentas_de_ladrão", "consumível", "misc", "misc"],
    "feiticeiro": ["cajado_ou_varinha", "foco_arcano", "consumível", "grimório", "utensílio", "misc"],
    "bruxo":      ["arma_simples", "foco_de_pacto", "consumível", "grimório", "utensílio", "misc"],
    "mago":       ["cajado_ou_varinha", "livro_de_magias", "foco_arcano", "consumível", "utensílio", "misc"],
    # Inglês
    "barbarian":  ["arma_pesada_corpo_a_corpo", "armadura_leve", "arma_secundaria", "consumível", "utensílio", "misc"],
    "bard":       ["instrumento_musical", "arma_simples", "armadura_leve", "consumível", "utensílio", "misc"],
    "cleric":     ["arma_simples", "armadura_media", "escudo", "símbolo_sagrado", "consumível", "misc"],
    "druid":      ["cajado", "armadura_leve", "foco_druídico", "consumível", "utensílio", "misc"],
    "fighter":    ["arma_marcial", "armadura_media", "escudo", "arma_secundaria", "consumível", "utensílio"],
    "monk":       ["arma_simples", "roupa_de_monge", "faixa_de_ki", "consumível", "utensílio", "misc"],
    "paladin":    ["arma_marcial", "armadura_media", "escudo", "símbolo_sagrado", "consumível", "misc"],
    "ranger":     ["arma_de_longo_alcance", "armadura_media", "arma_corpo_a_corpo", "consumível", "utensílio", "misc"],
    "rogue":      ["arma_leve_ou_de_arremesso", "armadura_leve", "ferramentas_de_ladrão", "consumível", "misc", "misc"],
    "sorcerer":   ["cajado_ou_varinha", "foco_arcano", "consumível", "grimório", "utensílio", "misc"],
    "warlock":    ["arma_simples", "foco_de_pacto", "consumível", "grimório", "utensílio", "misc"],
    "wizard":     ["cajado_ou_varinha", "livro_de_magias", "foco_arcano", "consumível", "utensílio", "misc"],
}

_DEFAULT_SLOTS = ["arma_simples", "armadura_leve", "consumível", "utensílio", "misc", "misc"]

# Mapeamento de slot → item_type do banco
_SLOT_TO_TYPE: dict[str, str] = {
    "arma_pesada_corpo_a_corpo": "weapon",
    "arma_marcial": "weapon",
    "arma_simples": "weapon",
    "arma_secundaria": "weapon",
    "arma_corpo_a_corpo": "weapon",
    "arma_de_longo_alcance": "weapon",
    "arma_leve_ou_de_arremesso": "weapon",
    "cajado": "weapon",
    "cajado_ou_varinha": "weapon",
    "instrumento_musical": "misc",
    "armadura_leve": "armor",
    "armadura_media": "armor",
    "escudo": "armor",
    "foco_arcano": "misc",
    "foco_druídico": "misc",
    "foco_de_pacto": "misc",
    "símbolo_sagrado": "misc",
    "ferramentas_de_ladrão": "misc",
    "livro_de_magias": "misc",
    "grimório": "misc",
    "roupa_de_monge": "armor",
    "faixa_de_ki": "misc",
    "consumível": "consumable",
    "utensílio": "misc",
    "misc": "misc",
}

# Atributos relevantes por slot (para o LLM saber quais stat_bonuses gerar)
_SLOT_STAT_HINTS: dict[str, str] = {
    "arma_pesada_corpo_a_corpo": "attack_bonus ou damage_bonus (ex: +1)",
    "arma_marcial": "attack_bonus ou damage_bonus (ex: +1)",
    "arma_simples": "attack_bonus (ex: +0, raramente +1)",
    "arma_secundaria": "damage_bonus (ex: +1)",
    "arma_corpo_a_corpo": "attack_bonus ou damage_bonus",
    "arma_de_longo_alcance": "attack_bonus (ex: +1)",
    "arma_leve_ou_de_arremesso": "attack_bonus ou dexterity",
    "cajado": "intelligence ou attack_bonus",
    "cajado_ou_varinha": "intelligence ou spell_attack_bonus (ex: +1)",
    "armadura_leve": "armor_class (ex: +1)",
    "armadura_media": "armor_class (ex: +1 ou +2)",
    "escudo": "armor_class (ex: +2)",
    "foco_arcano": "intelligence (ex: +1)",
    "foco_druídico": "wisdom (ex: +1)",
    "foco_de_pacto": "charisma (ex: +1)",
    "símbolo_sagrado": "wisdom ou charisma (ex: +1)",
    "instrumento_musical": "charisma (ex: +1)",
    "ferramentas_de_ladrão": "dexterity (ex: +1)",
    "consumível": "max_hp (ex: +5 ao usar) ou nenhum",
    "utensílio": "nenhum stat_bonus (só misc)",
    "misc": "nenhum stat_bonus ou bônus narrativo",
    "livro_de_magias": "intelligence (ex: +1)",
    "grimório": "intelligence (ex: +1)",
    "roupa_de_monge": "armor_class (ex: +1)",
    "faixa_de_ki": "wisdom (ex: +1)",
}


async def generate_starting_inventory(
    class_: str,
    race: str,
    background: str,
    level: int,
    character_id: UUID,
    character_name: str = "",
) -> list[dict[str, Any]]:
    """
    Gera os 6 itens iniciais de um personagem via LLM.

    Retorna lista de dicts prontos para criar InventoryItem.create(**item).
    Em caso de falha do LLM, retorna itens fallback sem stats.
    """
    slots = _STARTING_SLOTS.get(class_.lower(), _DEFAULT_SLOTS)

    try:
        items = await _call_llm(
            class_=class_,
            race=race,
            background=background,
            level=level,
            character_name=character_name,
            slots=slots,
        )
        return _attach_character_id(items, character_id, slots)
    except Exception as exc:
        logger.warning(
            "Falha ao gerar inventário via LLM para %s %s: %s — usando fallback",
            class_,
            character_name,
            exc,
        )
        return _fallback_inventory(slots, character_id)


async def _call_llm(
    class_: str,
    race: str,
    background: str,
    level: int,
    character_name: str,
    slots: list[str],
) -> list[dict[str, Any]]:
    """Chama GPT-4o e retorna a lista de itens parseada."""
    import asyncio
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    slots_desc = "\n".join(
        f"  {i+1}. slot='{slot}' | stat_hint={_SLOT_STAT_HINTS.get(slot, 'nenhum')}"
        for i, slot in enumerate(slots)
    )

    prompt = f"""Você é um mestre de RPG gerando o equipamento inicial de um personagem.

Personagem:
- Nome: {character_name or 'Aventureiro'}
- Raça: {race}
- Classe: {class_}
- Background: {background or 'Plebeu'}
- Nível: {level}

Gere exatamente 6 itens de equipamento inicial, um para cada slot abaixo:
{slots_desc}

Regras obrigatórias:
- Todos os itens são de raridade "common" (itens de nível 1)
- stat_bonuses: apenas atributos indicados pelo stat_hint. Máximo +1 ou +2 total
- Nomes em português, criativos e únicos para esta raça/classe
- special_effects: máximo 1 efeito para common, formato trigger/effect
- description: 1 frase narrativa curta e imersiva
- item_type deve ser: weapon, armor, consumable ou misc

Responda APENAS com um JSON array válido, sem markdown, sem explicações:
[
  {{
    "item_name": "Nome Criativo do Item",
    "item_type": "weapon",
    "slot": "arma_marcial",
    "rarity": "common",
    "quantity": 1,
    "weight": 3.5,
    "value_gp": 15.0,
    "equipped": true,
    "stat_bonuses": {{}},
    "special_effects": [],
    "description": "Frase narrativa curta.",
    "properties": {{}}
  }}
]"""

    def _sync_call() -> str:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=2000,
        )
        return response.choices[0].message.content or "[]"

    raw = await asyncio.to_thread(_sync_call)

    # Remove markdown se vier
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    items: list[dict] = json.loads(raw)
    if not isinstance(items, list):
        raise ValueError("LLM retornou formato inválido")

    return items[:6]  # garante no máximo 6


def _attach_character_id(
    items: list[dict],
    character_id: UUID,
    slots: list[str],
) -> list[dict[str, Any]]:
    """Normaliza e injeta character_id em cada item."""
    result = []
    for i, item in enumerate(items):
        slot = item.get("slot", slots[i] if i < len(slots) else "misc")
        item_type = item.get("item_type") or _SLOT_TO_TYPE.get(slot, "misc")

        result.append({
            "character_id": character_id,
            "item_name": item.get("item_name", f"Item {i+1}"),
            "item_type": item_type,
            "quantity": item.get("quantity", 1),
            "weight": float(item.get("weight", 0.0)),
            "value_gp": float(item.get("value_gp", 0.0)),
            "properties": item.get("properties", {}),
            "equipped": item.get("equipped", False),
            "stat_bonuses": item.get("stat_bonuses", {}),
            "special_effects": item.get("special_effects", []),
            "rarity": item.get("rarity", "common"),
            "is_starting_item": True,
            "description": item.get("description"),
        })
    return result


def _fallback_inventory(slots: list[str], character_id: UUID) -> list[dict[str, Any]]:
    """Itens genéricos sem stats para usar se o LLM falhar."""
    fallback_names = {
        "arma_pesada_corpo_a_corpo": ("Machado de Ferro", "weapon", 5.0, 10.0),
        "arma_marcial": ("Espada Longa de Aço", "weapon", 3.0, 15.0),
        "arma_simples": ("Bordão de Madeira", "weapon", 2.0, 2.0),
        "arma_secundaria": ("Adaga de Ferro", "weapon", 0.5, 2.0),
        "arma_corpo_a_corpo": ("Macete", "weapon", 2.0, 5.0),
        "arma_de_longo_alcance": ("Arco Curto", "weapon", 1.0, 25.0),
        "arma_leve_ou_de_arremesso": ("Adaga", "weapon", 0.5, 2.0),
        "cajado": ("Cajado de Madeira", "weapon", 2.0, 5.0),
        "cajado_ou_varinha": ("Varinha de Carvalho", "weapon", 0.5, 10.0),
        "armadura_leve": ("Armadura de Couro", "armor", 5.0, 10.0),
        "armadura_media": ("Cota de Malha", "armor", 20.0, 50.0),
        "escudo": ("Escudo de Madeira", "armor", 3.0, 10.0),
        "foco_arcano": ("Orbe de Cristal", "misc", 0.5, 20.0),
        "foco_druídico": ("Bastão de Carvalho", "misc", 1.0, 5.0),
        "foco_de_pacto": ("Amuleto do Pacto", "misc", 0.1, 15.0),
        "símbolo_sagrado": ("Símbolo Sagrado de Prata", "misc", 0.1, 5.0),
        "instrumento_musical": ("Flauta de Madeira", "misc", 0.5, 2.0),
        "ferramentas_de_ladrão": ("Ferramentas de Ladrão", "misc", 0.5, 25.0),
        "livro_de_magias": ("Livro de Magias Encadernado", "misc", 1.0, 50.0),
        "grimório": ("Grimório Antigo", "misc", 1.0, 30.0),
        "roupa_de_monge": ("Vestes de Monge", "armor", 1.0, 5.0),
        "faixa_de_ki": ("Faixa de Seda", "misc", 0.1, 1.0),
        "consumível": ("Poção de Cura", "consumable", 0.5, 50.0),
        "utensílio": ("Mochila de Couro", "misc", 2.0, 2.0),
        "misc": ("Tocha (3 unidades)", "misc", 1.0, 0.3),
    }

    items = []
    for slot in slots:
        name, itype, weight, gp = fallback_names.get(slot, ("Utensílio", "misc", 0.5, 1.0))
        items.append({
            "character_id": character_id,
            "item_name": name,
            "item_type": itype,
            "quantity": 1,
            "weight": weight,
            "value_gp": gp,
            "properties": {},
            "equipped": itype in ("weapon", "armor"),
            "stat_bonuses": {},
            "special_effects": [],
            "rarity": "common",
            "is_starting_item": True,
            "description": None,
        })
    return items
