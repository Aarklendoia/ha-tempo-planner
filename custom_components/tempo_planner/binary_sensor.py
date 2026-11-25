"""Whether to plug the car in tonight, and whether each appliance is shed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TempoPlannerConfigEntry, TempoPlannerCoordinator
from .entity import ApplianceEntity, setup_appliances


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TempoPlannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PlugTonightSensor(entry.runtime_data)])
    setup_appliances(hass, entry, async_add_entities, ShedSensor)


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


class ShedSensor(ApplianceEntity, BinarySensorEntity):
    """On while the appliance is shed."""

    suffix = "shed"
    _attr_translation_key = "shed"

    @property
    def is_on(self) -> bool:
        return self._shedder.status(self._id).shed

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        appliance, status = self.appliance, self._shedder.status(self._id)
        return {
            "appliance_entity": appliance.entity_id if appliance else None,
            "behaviour": str(appliance.behaviour) if appliance else None,
            "reason": str(status.reason) if status.reason else None,
            "until": status.until.isoformat() if status.until else None,
        }
