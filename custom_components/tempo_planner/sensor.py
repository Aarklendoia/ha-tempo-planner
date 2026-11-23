"""Sensors exposing the plan."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TempoPlannerConfigEntry, TempoPlannerCoordinator
from .planner import Color, Plan, Slot


def _start(slot: Slot | None) -> datetime | None:
    return slot.start if slot else None


def _end(slot: Slot | None) -> datetime | None:
    return slot.end if slot else None


def _plan_attributes(plan: Plan) -> dict[str, Any]:
    return {
        "night_start": plan.night_start.isoformat(),
        "night_end": plan.night_end.isoformat(),
        "reasons": [str(r) for r in plan.reasons],
    }


@dataclass(frozen=True, kw_only=True)
class PlanSensorDescription(SensorEntityDescription):
    value: Callable[[Plan], Any]
    attributes: Callable[[Plan], dict[str, Any]] | None = None


SENSORS: tuple[PlanSensorDescription, ...] = (
    PlanSensorDescription(
        key="tomorrow",
        translation_key="tomorrow",
        device_class=SensorDeviceClass.ENUM,
        options=[str(c) for c in Color],
        value=lambda p: str(p.tomorrow),
        attributes=_plan_attributes,
    ),
    PlanSensorDescription(
        key="battery_target",
        translation_key="battery_target",
        native_unit_of_measurement=PERCENTAGE,
        value=lambda p: p.battery_target_pct,
    ),
    PlanSensorDescription(
        key="battery_grid_energy",
        translation_key="battery_grid_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value=lambda p: p.battery_grid_kwh,
    ),
    PlanSensorDescription(
        key="battery_charge_end",
        translation_key="battery_charge_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: _end(p.battery),
    ),
    PlanSensorDescription(
        key="car_energy",
        translation_key="car_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value=lambda p: p.car_energy_kwh,
    ),
    PlanSensorDescription(
        key="car_charge_start",
        translation_key="car_charge_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: _start(p.car),
    ),
    PlanSensorDescription(
        key="car_charge_end",
        translation_key="car_charge_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: _end(p.car),
    ),
    PlanSensorDescription(
        key="dishwasher_start",
        translation_key="dishwasher_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: _start(p.dishwasher),
        attributes=lambda p: {"mode": p.dishwasher_mode},
    ),
    PlanSensorDescription(
        key="dishwasher_end",
        translation_key="dishwasher_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: _end(p.dishwasher),
    ),
    PlanSensorDescription(
        key="night_peak",
        translation_key="night_peak",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=1,
        value=lambda p: p.peak_kw,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TempoPlannerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PlanSensor(coordinator, d) for d in SENSORS)


class PlanSensor(CoordinatorEntity[TempoPlannerCoordinator], SensorEntity):
    """One value of the plan."""

    _attr_has_entity_name = True
    entity_description: PlanSensorDescription

    def __init__(
        self, coordinator: TempoPlannerCoordinator, description: PlanSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Tempo Planner",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)
