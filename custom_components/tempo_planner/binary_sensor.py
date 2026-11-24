"""Whether to plug the car in tonight."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TempoPlannerConfigEntry, TempoPlannerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TempoPlannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PlugTonightSensor(entry.runtime_data)])


class PlugTonightSensor(CoordinatorEntity[TempoPlannerCoordinator], BinarySensorEntity):
    """On when tonight's recommended charge is worth plugging the car in."""

    _attr_has_entity_name = True
    _attr_translation_key = "plug_car_tonight"

    def __init__(self, coordinator: TempoPlannerCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_plug_car_tonight"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Tempo Planner",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.car_plug_tonight
