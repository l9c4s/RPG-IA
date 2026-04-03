"""
Schemas Pydantic para a borda HTTP das rotas do GM.
"""

from typing import Optional

from pydantic import BaseModel, Field


class RollResultResponse(BaseModel):
    expr: str
    result: int
    breakdown: str


class StateUpdateResponse(BaseModel):
    field: str
    value: str


class GMResponseSchema(BaseModel):
    text: str
    roll_results: list[RollResultResponse] = Field(default_factory=list)
    state_updates: list[StateUpdateResponse] = Field(default_factory=list)
    image_url: Optional[str] = None
    audio_url: Optional[str] = None


class Generate8BitRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)


class Generate8BitResponse(BaseModel):
    name: str
    race: str
    character_class: str = Field(alias="class")
    alignment: str
    background: str
    appearance: str
    backstory: str
    pixel_art_prompt: str

    model_config = {"populate_by_name": True}


class OpeningStatusResponse(BaseModel):
    init_status: str
    message: str
