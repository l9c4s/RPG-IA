"""
Gerador de habilidades iniciais via LLM (OpenAI GPT-4o).

Gera 3-5 habilidades de classe adequadas para o personagem, baseadas na
classe, raça e nível. Modela-se no mesmo padrão do inventory_generator.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


# ─── Habilidades padrão por classe (fallback se LLM falhar) ──────────────────

_FALLBACK_ABILITIES: dict[str, list[dict]] = {
    "bárbaro":    [
        {"ability_name": "Fúria", "ability_type": "action", "uses_max": 2, "recharge": "long_rest",
         "description": "Entra em fúria bárbarica, ganhando vantagem em testes de Força e resistência a dano físico."},
        {"ability_name": "Defesa sem Armadura", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "CA = 10 + mod de Destreza + mod de Constituição enquanto não usar armadura."},
        {"ability_name": "Ataque Extra", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Pode atacar duas vezes por ação (disponível a partir do nível 5)."},
    ],
    "bardo":      [
        {"ability_name": "Inspiração de Bardo", "ability_type": "bonus_action", "uses_max": 3, "recharge": "long_rest",
         "description": "Concede um dado de inspiração (1d6) a um aliado, que pode adicionar ao próximo teste."},
        {"ability_name": "Conhecimento de Jack-of-all-trades", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Adiciona metade do bônus de proficiência a todos os testes de habilidade nos quais não é proficiente."},
    ],
    "clérigo":    [
        {"ability_name": "Conjurar Magia Divina", "ability_type": "action", "uses_max": 4, "recharge": "long_rest",
         "spell_level": 1, "description": "Lança magias divinas usando Sabedoria como atributo primário."},
        {"ability_name": "Tornar Mortos-Vivos", "ability_type": "action", "uses_max": 3, "recharge": "short_rest",
         "description": "Apresenta símbolo sagrado para forçar mortos-vivos a fugirem por 1 minuto."},
    ],
    "druida":     [
        {"ability_name": "Forma Selvagem", "ability_type": "action", "uses_max": 2, "recharge": "short_rest",
         "description": "Transforma-se em uma besta que já observou. Mantém pontos de vida separados."},
        {"ability_name": "Conjurar Magia Druidica", "ability_type": "action", "uses_max": 4, "recharge": "long_rest",
         "spell_level": 1, "description": "Lança magias da natureza usando Sabedoria como atributo primário."},
    ],
    "guerreiro":  [
        {"ability_name": "Estilo de Combate", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Escolheu um estilo especializado de combate, ganhando bônus específico."},
        {"ability_name": "Retomar o Fôlego", "ability_type": "bonus_action", "uses_max": 1, "recharge": "short_rest",
         "description": "Recupera HP igual a 1d10 + nível de guerreiro."},
        {"ability_name": "Surto de Ação", "ability_type": "action", "uses_max": 1, "recharge": "short_rest",
         "description": "Realiza uma ação adicional além da normal neste turno."},
    ],
    "monge":      [
        {"ability_name": "Artes Marciais", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Usa Destreza em vez de Força para ataques desarmados, que causam 1d4 de dano."},
        {"ability_name": "Ponto de Ki", "ability_type": "feature", "uses_max": 2, "recharge": "short_rest",
         "description": "Gasta pontos de ki para usar técnicas especiais como Flurry of Blows."},
    ],
    "paladino":   [
        {"ability_name": "Sentido Divino", "ability_type": "action", "uses_max": 3, "recharge": "long_rest",
         "description": "Detecta celestiais, demoníacos e mortos-vivos num raio de 60 pés."},
        {"ability_name": "Cura pelas Mãos", "ability_type": "action", "uses_max": 5, "recharge": "long_rest",
         "description": "Toca um ser e restaura uma quantidade de HP igual a nível x 5."},
    ],
    "ladino":     [
        {"ability_name": "Ataque Furtivo", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Causa 1d6 extra de dano quando tem vantagem no ataque ou há um aliado adjacente ao alvo."},
        {"ability_name": "Linguagem Ladrões", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Conhece a linguagem secreta dos ladrões, podendo comunicar mensagens ocultas."},
        {"ability_name": "Evasão", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Quando sofre efeito de área com teste de Destreza, não sofre dano em um sucesso."},
    ],
    "mago":       [
        {"ability_name": "Recuperação Arcana", "ability_type": "feature", "uses_max": 1, "recharge": "long_rest",
         "description": "Recupera espaços de magia gastos totalizando metade do nível (arredondado acima)."},
        {"ability_name": "Conjurar Magias Arcanas", "ability_type": "action", "uses_max": 4, "recharge": "long_rest",
         "spell_level": 1, "description": "Lança magias arcanas usando Inteligência como atributo primário."},
    ],
    "feiticeiro": [
        {"ability_name": "Pontos de Feitiçaria", "ability_type": "feature", "uses_max": 2, "recharge": "long_rest",
         "description": "Acumula pontos de feitiçaria para criar espaços de magia ou metamagia."},
        {"ability_name": "Metamagia", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Modifica magias com efeitos especiais: Magia Sutil, Magia Gêmea, etc."},
    ],
    "bruxo":      [
        {"ability_name": "Invocações Místicas", "ability_type": "feature", "uses_max": None, "recharge": None,
         "description": "Conhece fragmentos de conhecimento proibido que concedem habilidades sobrenaturais."},
        {"ability_name": "Magia de Pacto", "ability_type": "action", "uses_max": 1, "recharge": "short_rest",
         "spell_level": 1, "description": "Espaço de magia único recuperado em descanso curto, negociado com o patrono."},
    ],
}

_DEFAULT_ABILITIES = [
    {"ability_name": "Ataque", "ability_type": "action", "uses_max": None, "recharge": None,
     "description": "Realiza um ataque com sua arma equipada."},
    {"ability_name": "Resistência", "ability_type": "feature", "uses_max": None, "recharge": None,
     "description": "Treinamento defensivo que reduz o impacto de ataques físicos."},
]


async def generate_starting_abilities(
    class_: str,
    race: str,
    level: int,
    character_id: UUID,
    character_name: str = "",
    background: str = "Plebeu",
) -> list[dict[str, Any]]:
    """
    Gera 3-5 habilidades iniciais via LLM.

    Retorna lista de dicts prontos para Ability.create(**item).
    Em caso de falha, usa fallback estático.
    """
    try:
        abilities = await _call_llm(
            class_=class_,
            race=race,
            level=level,
            character_name=character_name,
            background=background,
        )
        return _attach_character_id(abilities, character_id)
    except Exception as exc:
        logger.warning(
            "Falha ao gerar habilidades via LLM para %s %s: %s — usando fallback",
            class_,
            character_name,
            exc,
        )
        return _fallback_abilities(class_, character_id)


async def _call_llm(
    class_: str,
    race: str,
    level: int,
    character_name: str,
    background: str,
) -> list[dict[str, Any]]:
    """Chama GPT-4o e retorna lista de habilidades parseada."""
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""Você é um mestre de RPG (D&D 5e) gerando as habilidades iniciais de um personagem.

Personagem:
- Nome: {character_name or 'Aventureiro'}
- Raça: {race}
- Classe: {class_}
- Background: {background}
- Nível: {level}

Gere entre 3 e 5 habilidades iniciais adequadas para esta classe e nível no sistema D&D 5e.
Inclua habilidades de classe fundamentais (não magias de spell_level alto para nível 1).

Responda APENAS com um JSON array válido, sem markdown:
[
  {{
    "ability_name": "Nome da Habilidade",
    "ability_type": "feature",
    "description": "Descrição clara e breve da mecânica.",
    "spell_level": null,
    "uses_max": null,
    "uses_current": null,
    "recharge": null
  }}
]

ability_type válidos: feature, action, bonus_action, reaction, spell
recharge válidos: null, "short_rest", "long_rest", "dawn", "turn"
spell_level: null para não-magias, 1-9 para magias
uses_max: null para ilimitadas, número inteiro para recursos limitados"""

    def _sync_call() -> str:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200,
        )
        return response.choices[0].message.content or "[]"

    raw = await asyncio.to_thread(_sync_call)
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    abilities: list[dict] = json.loads(raw)
    if not isinstance(abilities, list):
        raise ValueError("LLM retornou formato inválido")
    return abilities[:5]


def _attach_character_id(
    abilities: list[dict],
    character_id: UUID,
) -> list[dict[str, Any]]:
    """Normaliza e injeta character_id em cada habilidade."""
    valid_types = {"feature", "action", "bonus_action", "reaction", "spell"}
    valid_recharges = {None, "short_rest", "long_rest", "dawn", "turn"}
    result = []
    for ab in abilities:
        ability_type = ab.get("ability_type", "feature")
        if ability_type not in valid_types:
            ability_type = "feature"
        recharge = ab.get("recharge")
        if recharge not in valid_recharges:
            recharge = None
        uses_max = ab.get("uses_max")
        result.append({
            "character_id": character_id,
            "ability_name": ab.get("ability_name", "Habilidade"),
            "ability_type": ability_type,
            "description": ab.get("description"),
            "spell_level": ab.get("spell_level"),
            "uses_max": uses_max,
            "uses_current": uses_max,  # começa com usos cheios
            "recharge": recharge,
        })
    return result


def _fallback_abilities(class_: str, character_id: UUID) -> list[dict[str, Any]]:
    """Habilidades genéricas estáticas para usar se o LLM falhar."""
    raw = _FALLBACK_ABILITIES.get(class_.lower(), _DEFAULT_ABILITIES)
    return [
        {
            "character_id": character_id,
            "ability_name": ab["ability_name"],
            "ability_type": ab.get("ability_type", "feature"),
            "description": ab.get("description"),
            "spell_level": ab.get("spell_level"),
            "uses_max": ab.get("uses_max"),
            "uses_current": ab.get("uses_max"),
            "recharge": ab.get("recharge"),
        }
        for ab in raw
    ]
