from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import (
    AbilityDB,
    CharacterAttributesDB,
    CharacterDB,
    CharacterStatusDB,
    InventoryItemDB,
    get_db,
    init_db,
)
from models import (
    AbilityCreate,
    AbilityOut,
    AttributesCreate,
    CharacterCreate,
    CharacterFull,
    CharacterOut,
    CharacterStatusUpdate,
    CharacterUpdate,
    InventoryItemCreate,
    InventoryItemOut,
    LevelUpResponse,
    calc_proficiency_bonus,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Character Service",
    description="Serviço de personagens para a plataforma RPG-IA (D&D 5e)",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def startup() -> None:
    await init_db()
    logger.info("Banco de dados inicializado com sucesso.")


# ---------------------------------------------------------------------------
# Dependency alias
# ---------------------------------------------------------------------------

DBSession = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_character_or_404(
    character_id: UUID, db: AsyncSession
) -> CharacterDB:
    result = await db.execute(
        select(CharacterDB)
        .options(
            selectinload(CharacterDB.status),
            selectinload(CharacterDB.attributes),
            selectinload(CharacterDB.inventory),
            selectinload(CharacterDB.abilities),
        )
        .where(CharacterDB.id == character_id, CharacterDB.is_alive == True)  # noqa: E712
    )
    character = result.scalar_one_or_none()
    if character is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Personagem não encontrado ou foi removido.",
        )
    return character


async def _get_inventory_item_or_404(
    character_id: UUID, item_id: UUID, db: AsyncSession
) -> InventoryItemDB:
    result = await db.execute(
        select(InventoryItemDB).where(
            InventoryItemDB.id == item_id,
            InventoryItemDB.character_id == character_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item de inventário não encontrado para este personagem.",
        )
    return item


def _init_status(character_id: UUID) -> CharacterStatusDB:
    return CharacterStatusDB(
        id=uuid4(),
        character_id=character_id,
        hp_max=0,
        hp_current=0,
        hp_temp=0,
        conditions=[],
        spell_slots={},
        exhaustion=0,
        death_saves_success=0,
        death_saves_failure=0,
    )


def _init_attributes(character_id: UUID) -> CharacterAttributesDB:
    return CharacterAttributesDB(
        id=uuid4(),
        character_id=character_id,
    )


# ---------------------------------------------------------------------------
# Routes — Characters CRUD
# ---------------------------------------------------------------------------


@app.post(
    "/characters",
    response_model=CharacterFull,
    status_code=status.HTTP_201_CREATED,
    summary="Criar personagem",
)
async def create_character(payload: CharacterCreate, db: DBSession) -> CharacterFull:
    """
    Cria um novo personagem D&D e inicializa automaticamente
    seu status de combate e atributos com valores padrão.
    """
    proficiency = calc_proficiency_bonus(payload.level)

    character = CharacterDB(
        id=uuid4(),
        name=payload.name,
        race=payload.race,
        class_=payload.class_,
        subclass=payload.subclass,
        level=payload.level,
        proficiency_bonus=proficiency,
        background=payload.background,
        alignment=payload.alignment,
        char_type=payload.char_type,
        backstory=payload.backstory,
        appearance=payload.appearance,
        campaign_id=payload.campaign_id,
        owner_id=payload.owner_id,
        is_alive=True,
    )

    db.add(character)
    await db.flush()  # persist to get ID before inserting children

    status_row = _init_status(character.id)
    attrs_row = _init_attributes(character.id)
    db.add(status_row)
    db.add(attrs_row)

    await db.flush()

    # Reload with relations
    full = await _get_character_or_404(character.id, db)
    return CharacterFull.model_validate(full)


@app.get(
    "/characters/{character_id}",
    response_model=CharacterFull,
    summary="Obter personagem completo",
)
async def get_character(
    character_id: Annotated[UUID, Path(description="ID do personagem")],
    db: DBSession,
) -> CharacterFull:
    """
    Retorna o personagem com todos os dados relacionados:
    status, atributos, inventário e habilidades/magias.
    """
    character = await _get_character_or_404(character_id, db)
    return CharacterFull.model_validate(character)


@app.patch(
    "/characters/{character_id}",
    response_model=CharacterOut,
    summary="Atualizar campos do personagem",
)
async def update_character(
    character_id: Annotated[UUID, Path(description="ID do personagem")],
    payload: CharacterUpdate,
    db: DBSession,
) -> CharacterOut:
    """Atualiza parcialmente os campos básicos do personagem (PATCH)."""
    character = await _get_character_or_404(character_id, db)

    update_data = payload.model_dump(exclude_none=True, by_alias=False)

    # Map alias "class" back to ORM attribute "class_"
    if "class" in update_data:
        update_data["class_"] = update_data.pop("class")

    for field, value in update_data.items():
        setattr(character, field, value)

    await db.flush()
    return CharacterOut.model_validate(character)


@app.delete(
    "/characters/{character_id}",
    status_code=status.HTTP_200_OK,
    summary="Remover personagem (soft delete)",
)
async def delete_character(
    character_id: Annotated[UUID, Path(description="ID do personagem")],
    db: DBSession,
) -> JSONResponse:
    """
    Realiza remoção lógica do personagem definindo is_alive=False.
    O personagem não aparecerá mais nas buscas mas permanece no banco.
    """
    character = await _get_character_or_404(character_id, db)
    character.is_alive = False
    await db.flush()
    return JSONResponse(
        content={"mensagem": "Personagem removido com sucesso.", "id": str(character_id)}
    )


# ---------------------------------------------------------------------------
# Route — List characters by campaign
# ---------------------------------------------------------------------------


@app.get(
    "/campaigns/{campaign_id}/characters",
    response_model=list[CharacterOut],
    summary="Listar personagens de uma campanha",
)
async def list_campaign_characters(
    campaign_id: Annotated[UUID, Path(description="ID da campanha")],
    db: DBSession,
) -> list[CharacterOut]:
    """Retorna todos os personagens ativos vinculados a uma campanha."""
    result = await db.execute(
        select(CharacterDB).where(
            CharacterDB.campaign_id == campaign_id,
            CharacterDB.is_alive == True,  # noqa: E712
        )
    )
    characters = result.scalars().all()
    return [CharacterOut.model_validate(c) for c in characters]


# ---------------------------------------------------------------------------
# Route — Combat status update (real-time)
# ---------------------------------------------------------------------------


@app.patch(
    "/characters/{character_id}/status",
    response_model=CharacterFull,
    summary="Atualizar status de combate",
)
async def update_character_status(
    character_id: Annotated[UUID, Path(description="ID do personagem")],
    payload: CharacterStatusUpdate,
    db: DBSession,
) -> CharacterFull:
    """
    Atualiza HP, condições ativas, espaços de magia e exaustão em tempo real
    durante o combate. Apenas os campos enviados serão alterados.
    """
    character = await _get_character_or_404(character_id, db)

    if character.status is None:
        # Should not happen in normal flow, but guard just in case
        status_row = _init_status(character.id)
        db.add(status_row)
        await db.flush()
        character = await _get_character_or_404(character_id, db)

    st = character.status
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(st, field, value)

    await db.flush()
    return CharacterFull.model_validate(character)


# ---------------------------------------------------------------------------
# Routes — Inventory
# ---------------------------------------------------------------------------


@app.post(
    "/characters/{character_id}/inventory",
    response_model=InventoryItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar item ao inventário",
)
async def add_inventory_item(
    character_id: Annotated[UUID, Path(description="ID do personagem")],
    payload: InventoryItemCreate,
    db: DBSession,
) -> InventoryItemOut:
    """Adiciona um novo item ao inventário do personagem."""
    # Ensure character exists
    await _get_character_or_404(character_id, db)

    item = InventoryItemDB(
        id=uuid4(),
        character_id=character_id,
        item_name=payload.item_name,
        item_type=payload.item_type,
        quantity=payload.quantity,
        weight=payload.weight,
        value_gp=payload.value_gp,
        properties=payload.properties,
        equipped=payload.equipped,
    )
    db.add(item)
    await db.flush()
    return InventoryItemOut.model_validate(item)


@app.delete(
    "/characters/{character_id}/inventory/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Remover item do inventário",
)
async def remove_inventory_item(
    character_id: Annotated[UUID, Path(description="ID do personagem")],
    item_id: Annotated[UUID, Path(description="ID do item")],
    db: DBSession,
) -> JSONResponse:
    """Remove permanentemente um item do inventário do personagem."""
    await _get_character_or_404(character_id, db)
    item = await _get_inventory_item_or_404(character_id, item_id, db)
    await db.delete(item)
    await db.flush()
    return JSONResponse(
        content={
            "mensagem": "Item removido do inventário com sucesso.",
            "item_id": str(item_id),
        }
    )


# ---------------------------------------------------------------------------
# Routes — Abilities & Spells
# ---------------------------------------------------------------------------


@app.post(
    "/characters/{character_id}/abilities",
    response_model=AbilityOut,
    status_code=status.HTTP_201_CREATED,
    summary="Adicionar habilidade ou magia",
)
async def add_ability(
    character_id: Annotated[UUID, Path(description="ID do personagem")],
    payload: AbilityCreate,
    db: DBSession,
) -> AbilityOut:
    """
    Adiciona uma habilidade de classe, traço racial, ação ou magia
    ao personagem. Magias devem especificar spell_level.
    """
    await _get_character_or_404(character_id, db)

    ability = AbilityDB(
        id=uuid4(),
        character_id=character_id,
        ability_name=payload.ability_name,
        ability_type=payload.ability_type,
        description=payload.description,
        spell_level=payload.spell_level,
        uses_max=payload.uses_max,
        uses_remaining=payload.uses_max,  # initialize to max
        recharge=payload.recharge,
    )
    db.add(ability)
    await db.flush()
    return AbilityOut.model_validate(ability)


# ---------------------------------------------------------------------------
# Route — Level up
# ---------------------------------------------------------------------------


@app.post(
    "/characters/{character_id}/levelup",
    response_model=LevelUpResponse,
    summary="Subir de nível",
)
async def level_up(
    character_id: Annotated[UUID, Path(description="ID do personagem")],
    db: DBSession,
) -> LevelUpResponse:
    """
    Incrementa o nível do personagem em 1 (máximo 20) e recalcula o
    bônus de proficiência usando a fórmula D&D 5e: 2 + (nível-1)//4.
    """
    character = await _get_character_or_404(character_id, db)

    if character.level >= 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O personagem já atingiu o nível máximo (20).",
        )

    new_level = character.level + 1
    new_proficiency = calc_proficiency_bonus(new_level)

    character.level = new_level
    character.proficiency_bonus = new_proficiency
    await db.flush()

    return LevelUpResponse(
        character_id=character.id,
        new_level=new_level,
        new_proficiency_bonus=new_proficiency,
        message=(
            f"{character.name} avançou para o nível {new_level}! "
            f"Bônus de proficiência atualizado para +{new_proficiency}."
        ),
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok", "service": "character"})
