from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.character.entity import Ability, Character, InventoryItem


class ICharacterRepository(Protocol):
    async def get_by_id(self, character_id: UUID) -> Character | None: ...

    async def list_by_campaign(self, campaign_id: UUID) -> list[Character]: ...

    async def save(self, character: Character) -> Character: ...

    async def get_inventory_item(
        self, character_id: UUID, item_id: UUID
    ) -> InventoryItem | None: ...

    async def add_inventory_item(self, item: InventoryItem) -> InventoryItem: ...

    async def remove_inventory_item(self, item_id: UUID) -> None: ...

    async def add_ability(self, ability: Ability) -> Ability: ...
