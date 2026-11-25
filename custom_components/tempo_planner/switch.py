"""Turn the load shedding of an appliance on and off."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TempoPlannerConfigEntry
from .entity import ApplianceEntity, setup_appliances


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TempoPlannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    setup_appliances(hass, entry, async_add_entities, ShedSwitch)


class ShedSwitch(ApplianceEntity, SwitchEntity):
    """On while the appliance may be shed."""

    suffix = "shed_enabled"
    _attr_translation_key = "shed_enabled"
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool | None:
        return self.appliance.enabled if self.appliance else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._shedder.async_set_enabled(self._id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._shedder.async_set_enabled(self._id, False)
