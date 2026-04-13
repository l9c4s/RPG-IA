from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.character.entity import (
    Ability,
    Character,
    CharacterAttributes,
    CharacterStatus,
    InventoryItem,
)
from infrastructure.database.orm_models import (
    AbilityDB,
    CharacterAttributesDB,
    CharacterDB,
    CharacterStatusDB,
    InventoryItemDB,
)


class CharacterRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -----------------------------------------------------------------------
    # ORM → Domain
    # -----------------------------------------------------------------------

    def _status_to_domain(self, orm: CharacterStatusDB) -> CharacterStatus:
        ds = orm.death_saves or {}
        return CharacterStatus(
            id=orm.id,
            character_id=orm.character_id,
            hp_max=orm.hp_max,
            hp_current=orm.hp_current,
            hp_temp=orm.hp_temp,
            conditions=orm.conditions or [],
            spell_slots=orm.spell_slots or {},
            exhaustion=orm.exhaustion,
            death_saves_success=ds.get("successes", 0),
            death_saves_failure=ds.get("failures", 0),
            updated_at=orm.updated_at or datetime.utcnow(),
        )

    def _attrs_to_domain(self, orm: CharacterAttributesDB) -> CharacterAttributes:
        return CharacterAttributes(
            id=orm.id,
            character_id=orm.character_id,
            strength=orm.strength,
            dexterity=orm.dexterity,
            constitution=orm.constitution,
            intelligence=orm.intelligence,
            wisdom=orm.wisdom,
            charisma=orm.charisma,
            armor_class=orm.armor_class,
            initiative=orm.initiative,
            speed=orm.speed,
            proficiency=orm.proficiency,
            saving_throws=orm.saving_throws or {},
            skill_profs=orm.skill_profs or [],
        )

    def _item_to_domain(self, orm: InventoryItemDB) -> InventoryItem:
        return InventoryItem(
            id=orm.id,
            character_id=orm.character_id,
            item_name=orm.item_name,
            item_type=orm.item_type,
            quantity=orm.quantity,
            weight=orm.weight,
            value_gp=orm.value_gp,
            properties=orm.properties or {},
            equipped=orm.equipped,
            created_at=orm.created_at or datetime.utcnow(),
            stat_bonuses=orm.stat_bonuses or {},
            special_effects=orm.special_effects or [],
            rarity=orm.rarity or "common",
            is_starting_item=orm.is_starting_item or False,
            description=orm.description,
        )

    def _ability_to_domain(self, orm: AbilityDB) -> Ability:
        return Ability(
            id=orm.id,
            character_id=orm.character_id,
            ability_name=orm.ability_name,
            ability_type=orm.ability_type,
            description=orm.description,
            spell_level=orm.spell_level,
            uses_max=orm.uses_max,
            uses_current=orm.uses_current,
            recharge=orm.recharge,
        )

    def _to_domain(self, orm: CharacterDB) -> Character:
        return Character(
            id=orm.id,
            name=orm.name,
            race=orm.race,
            class_=orm.class_,
            subclass=orm.subclass,
            level=orm.level,
            proficiency_bonus=orm.proficiency_bonus,
            background=orm.background,
            alignment=orm.alignment,
            char_type=orm.char_type,
            backstory=orm.backstory,
            appearance=orm.appearance,
            image_url=orm.image_url,
            campaign_id=orm.campaign_id,
            owner_id=orm.owner_id,
            is_alive=orm.is_alive,
            created_at=orm.created_at or datetime.utcnow(),
            updated_at=orm.updated_at or datetime.utcnow(),
            status=self._status_to_domain(orm.status) if orm.status else None,
            attributes=self._attrs_to_domain(orm.attributes) if orm.attributes else None,
            inventory=[self._item_to_domain(i) for i in (orm.inventory or [])],
            abilities=[self._ability_to_domain(a) for a in (orm.abilities or [])],
        )

    # -----------------------------------------------------------------------
    # Domain → ORM
    # -----------------------------------------------------------------------

    def _apply_to_orm(self, character: Character, orm: CharacterDB) -> None:
        orm.name = character.name
        orm.race = character.race
        orm.class_ = character.class_
        orm.subclass = character.subclass
        orm.level = character.level
        orm.proficiency_bonus = character.proficiency_bonus
        orm.background = character.background
        orm.alignment = character.alignment
        orm.char_type = character.char_type
        orm.backstory = character.backstory
        orm.appearance = character.appearance
        orm.image_url = character.image_url
        orm.campaign_id = character.campaign_id
        orm.owner_id = character.owner_id
        orm.is_alive = character.is_alive

    def _apply_status_to_orm(self, status: CharacterStatus, orm: CharacterStatusDB) -> None:
        orm.hp_max = status.hp_max
        orm.hp_current = status.hp_current
        orm.hp_temp = status.hp_temp
        orm.conditions = status.conditions
        orm.spell_slots = status.spell_slots
        orm.exhaustion = status.exhaustion
        orm.death_saves = {"successes": status.death_saves_success, "failures": status.death_saves_failure}

    def _apply_attrs_to_orm(
        self, attrs: CharacterAttributes, orm: CharacterAttributesDB
    ) -> None:
        orm.strength = attrs.strength
        orm.dexterity = attrs.dexterity
        orm.constitution = attrs.constitution
        orm.intelligence = attrs.intelligence
        orm.wisdom = attrs.wisdom
        orm.charisma = attrs.charisma
        orm.armor_class = attrs.armor_class
        orm.initiative = attrs.initiative
        orm.speed = attrs.speed
        orm.proficiency = attrs.proficiency
        orm.saving_throws = attrs.saving_throws
        orm.skill_profs = attrs.skill_profs

    # -----------------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------------

    async def _load_with_relations(self, character_id: UUID) -> CharacterDB | None:
        result = await self._session.execute(
            select(CharacterDB)
            .options(
                selectinload(CharacterDB.status),
                selectinload(CharacterDB.attributes),
                selectinload(CharacterDB.inventory),
                selectinload(CharacterDB.abilities),
            )
            .where(CharacterDB.id == character_id, CharacterDB.is_alive == True)  # noqa: E712
        )
        return result.scalar_one_or_none()

    # -----------------------------------------------------------------------
    # ICharacterRepository implementation
    # -----------------------------------------------------------------------

    async def get_by_id(self, character_id: UUID) -> Character | None:
        orm = await self._load_with_relations(character_id)
        if orm is None:
            return None
        return self._to_domain(orm)

    async def list_by_campaign(self, campaign_id: UUID) -> list[Character]:
        result = await self._session.execute(
            select(CharacterDB)
            .options(
                selectinload(CharacterDB.status),
                selectinload(CharacterDB.attributes),
                selectinload(CharacterDB.inventory),
                selectinload(CharacterDB.abilities),
            )
            .where(
                CharacterDB.campaign_id == campaign_id,
                CharacterDB.is_alive == True,  # noqa: E712
            )
        )
        return [self._to_domain(c) for c in result.scalars().all()]

    async def save(self, character: Character) -> Character:
        result = await self._session.execute(
            select(CharacterDB)
            .options(
                selectinload(CharacterDB.status),
                selectinload(CharacterDB.attributes),
                selectinload(CharacterDB.inventory),
                selectinload(CharacterDB.abilities),
            )
            .where(CharacterDB.id == character.id)
        )
        orm = result.scalar_one_or_none()

        if orm is None:
            # New character — create ORM row
            orm = CharacterDB(id=character.id)
            self._apply_to_orm(character, orm)
            self._session.add(orm)
            await self._session.flush()

            # Initialize status
            if character.status:
                status_orm = CharacterStatusDB(id=character.status.id, character_id=character.id)
                self._apply_status_to_orm(character.status, status_orm)
            else:
                status_orm = CharacterStatusDB(id=uuid4(), character_id=character.id)
            self._session.add(status_orm)

            # Initialize attributes
            if character.attributes:
                attrs_orm = CharacterAttributesDB(
                    id=character.attributes.id,
                    character_id=character.id,
                )
                self._apply_attrs_to_orm(character.attributes, attrs_orm)
                self._session.add(attrs_orm)
            else:
                self._session.add(
                    CharacterAttributesDB(id=uuid4(), character_id=character.id)
                )

            await self._session.flush()
        else:
            # Existing character — update
            self._apply_to_orm(character, orm)

            if character.status and orm.status:
                self._apply_status_to_orm(character.status, orm.status)
            elif character.status and orm.status is None:
                new_status = CharacterStatusDB(id=character.status.id, character_id=character.id)
                self._apply_status_to_orm(character.status, new_status)
                self._session.add(new_status)

            if character.attributes and orm.attributes:
                self._apply_attrs_to_orm(character.attributes, orm.attributes)

            await self._session.flush()

        # Reload fresh from DB with all relations
        reloaded = await self._load_with_relations(character.id)
        if reloaded is None:
            # Soft-deleted — load without is_alive filter
            result2 = await self._session.execute(
                select(CharacterDB)
                .options(
                    selectinload(CharacterDB.status),
                    selectinload(CharacterDB.attributes),
                    selectinload(CharacterDB.inventory),
                    selectinload(CharacterDB.abilities),
                )
                .where(CharacterDB.id == character.id)
            )
            reloaded = result2.scalar_one()
        return self._to_domain(reloaded)

    async def get_inventory_item(
        self, character_id: UUID, item_id: UUID
    ) -> InventoryItem | None:
        result = await self._session.execute(
            select(InventoryItemDB).where(
                InventoryItemDB.id == item_id,
                InventoryItemDB.character_id == character_id,
            )
        )
        orm = result.scalar_one_or_none()
        if orm is None:
            return None
        return self._item_to_domain(orm)

    async def add_inventory_item(self, item: InventoryItem) -> InventoryItem:
        orm = InventoryItemDB(
            id=item.id,
            character_id=item.character_id,
            item_name=item.item_name,
            item_type=item.item_type,
            quantity=item.quantity,
            weight=item.weight,
            value_gp=item.value_gp,
            properties=item.properties,
            equipped=item.equipped,
            stat_bonuses=item.stat_bonuses,
            special_effects=item.special_effects,
            rarity=item.rarity,
            is_starting_item=item.is_starting_item,
            description=item.description,
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return self._item_to_domain(orm)

    async def remove_inventory_item(self, item_id: UUID) -> None:
        result = await self._session.execute(
            select(InventoryItemDB).where(InventoryItemDB.id == item_id)
        )
        orm = result.scalar_one_or_none()
        if orm:
            await self._session.delete(orm)
            await self._session.flush()

    async def add_ability(self, ability: Ability) -> Ability:
        orm = AbilityDB(
            id=ability.id,
            character_id=ability.character_id,
            ability_name=ability.ability_name,
            ability_type=ability.ability_type,
            description=ability.description,
            spell_level=ability.spell_level,
            uses_max=ability.uses_max,
            uses_current=ability.uses_current,
            recharge=ability.recharge,
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return self._ability_to_domain(orm)
