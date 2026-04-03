from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DiceRoll:
    """
    Resultado de uma rolagem de dado extraída da resposta do GM.
    Exemplo: [ROLAGEM:2d6+3] → expr="2d6+3", result=9, breakdown="[4, 2] + 3 = 9"
    """

    expr: str
    result: int
    breakdown: str


@dataclass
class StateUpdate:
    """
    Atualização de estado de personagem extraída da resposta do GM.
    Exemplo: [ESTADO:hp=-5] → field="hp", value="-5"
    """

    field: str
    value: str


@dataclass
class GMResponse:
    """
    Resposta estruturada do GM após processar a ação de um jogador.
    Inclui texto limpo, rolagens resolvidas, mudanças de estado e URLs de mídia.
    """

    text: str
    roll_results: list[DiceRoll] = field(default_factory=list)
    state_updates: list[StateUpdate] = field(default_factory=list)
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
