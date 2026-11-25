"""Turn the load shedding of an appliance on and off."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TempoPlannerConfigEntry
from .entity import ApplianceEntity, device_info, setup_appliances
from .load_shedding import LoadShedder, signal_update


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TempoPlannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    setup_appliances(hass, entry, async_add_entities, ShedSwitch)
    async_add_entities([PowerSheddingSwitch(entry.runtime_data.shedder)])


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


class PowerSheddingSwitch(SwitchEntity):
    """On while appliances are shed by power."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "power_shedding"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, shedder: LoadShedder) -> None:
        self._shedder = shedder
        self._attr_unique_id = f"{shedder.entry_id}_power_shedding"
        self._attr_device_info = device_info(shedder.entry_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._shedder.entry_id), self.async_write_ha_state
            )
        )

    @property
    def available(self) -> bool:
        # Nothing to switch on without a power sensor.
        return self._shedder.power.power_entity is not None

    @property
    def is_on(self) -> bool:
        return self._shedder.power.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._shedder.async_set_power_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._shedder.async_set_power_enabled(False)
