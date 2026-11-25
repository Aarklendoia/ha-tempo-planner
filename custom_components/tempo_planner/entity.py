"""Entities of the sheddable appliances."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import TempoPlannerConfigEntry
from .load_shedding import LoadShedder, signal_added, signal_update
from .shedding import Appliance


def device_info(entry_id: str) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Tempo Planner",
        entry_type=DeviceEntryType.SERVICE,
    )


class ApplianceEntity(Entity):
    """Follows one appliance of the load shedder."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    # Suffix of the unique id, one per platform.
    suffix: str

    def __init__(self, shedder: LoadShedder, appliance: Appliance) -> None:
        self._shedder = shedder
        self._id = appliance.id
        self._attr_unique_id = f"{shedder.entry_id}_{appliance.id}_{self.suffix}"
        self._attr_device_info = device_info(shedder.entry_id)
        self._attr_translation_placeholders = {"appliance": appliance.name}

    @property
    def appliance(self) -> Appliance | None:
        return self._shedder.appliances.get(self._id)

    @property
    def available(self) -> bool:
        return self.appliance is not None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal_update(self._shedder.entry_id), self._updated
            )
        )

    @callback
    def _updated(self) -> None:
        if self.appliance is not None and self.hass is not None:
            self.async_write_ha_state()


def setup_appliances(
    hass: HomeAssistant,
    entry: TempoPlannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    make: Callable[[LoadShedder, Appliance], Entity],
) -> None:
    """Add an entity per appliance, now and whenever one is added."""
    shedder = entry.runtime_data.shedder
    async_add_entities(make(shedder, a) for a in shedder.appliances.values())

    @callback
    def _added(appliance: Appliance) -> None:
        async_add_entities([make(shedder, appliance)])

    entry.async_on_unload(async_dispatcher_connect(hass, signal_added(entry.entry_id), _added))
