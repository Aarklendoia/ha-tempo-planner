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
from .reasons import explain
from .review import BatteryOutcome


def _peak_review(plan: Plan, _: str) -> dict[str, Any]:
    review, summary = plan.review, plan.summary
    return {
        "day": review.day.isoformat() if review else None,
        "color": str(review.color) if review else None,
        "forecast": review.forecast_kwh if review else None,
        "error": review.error_kwh if review else None,
        "mean_abs_error": summary.mean_abs_error_kwh if summary else None,
        "days": summary.error_days if summary else 0,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _car_review(plan: Plan, _: str) -> dict[str, Any]:
    review = plan.review
    car = review.car if review else None
    return {
        "day": review.day.isoformat() if review else None,
        "start": _iso(car.start) if car else None,
        "end": _iso(car.end) if car else None,
        "level_start": car.soc_start if car else None,
        "level_end": car.soc_end if car else None,
        "planned_start": _iso(review.car_planned_start) if review else None,
        "planned_end": _iso(review.car_planned_end) if review else None,
        "planned_energy": review.car_planned_kwh if review else None,
        "start_offset": review.car_start_offset_min if review else None,
    }


def _battery_review(plan: Plan, _: str) -> dict[str, Any]:
    review, summary = plan.review, plan.summary
    return {
        "day": review.day.isoformat() if review else None,
        "planned_charge": review.planned_charge if review else None,
        "level_start": review.soc_start if review else None,
        "level_max": review.soc_max if review else None,
        "level_end": review.soc_end if review else None,
        "agreement": summary.agreement_pct if summary else None,
        "nights": summary.nights if summary else 0,
    }


def _start(slot: Slot | None) -> datetime | None:
    return slot.start if slot else None


def _end(slot: Slot | None) -> datetime | None:
    return slot.end if slot else None


def _plan_attributes(plan: Plan, language: str) -> dict[str, Any]:
    return {
        "night_start": plan.night_start.isoformat(),
        "night_end": plan.night_end.isoformat(),
        "reasons": [str(r) for r in plan.reasons],
        "explanation": explain(plan.reasons, language),
    }


@dataclass(frozen=True, kw_only=True)
class PlanSensorDescription(SensorEntityDescription):
    value: Callable[[Plan], Any]
    attributes: Callable[[Plan, str], dict[str, Any]] | None = None


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
        key="peak_load",
        translation_key="peak_load",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value=lambda p: p.peak_load_kwh,
        attributes=lambda p, _: {
            "source": "setting" if p.peak_load_days is None else "history",
            "days": p.peak_load_days,
            "color": None if p.peak_load_days is None else str(p.peak_load_color or "all"),
        },
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
        attributes=lambda p, _: {
            "gain_per_kwh": p.battery_gain_eur_kwh,
            "offpeak_price": p.offpeak_price,
            "peak_price": p.peak_price,
        },
    ),
    PlanSensorDescription(
        key="battery_charge_start",
        translation_key="battery_charge_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: _start(p.battery),
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
        attributes=lambda p, _: {"mode": p.dishwasher_mode},
    ),
    PlanSensorDescription(
        key="dishwasher_end",
        translation_key="dishwasher_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value=lambda p: _end(p.dishwasher),
    ),
    PlanSensorDescription(
        key="last_day_peak_load",
        translation_key="last_day_peak_load",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value=lambda p: p.review.actual_kwh if p.review else None,
        attributes=_peak_review,
    ),
    PlanSensorDescription(
        key="last_night_battery",
        translation_key="last_night_battery",
        device_class=SensorDeviceClass.ENUM,
        options=[str(o) for o in BatteryOutcome],
        value=lambda p: str(o) if p.review and (o := p.review.battery_outcome) else None,
        attributes=_battery_review,
    ),
    PlanSensorDescription(
        key="last_night_car",
        translation_key="last_night_car",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value=lambda p: p.review.car.grid_kwh if p.review and p.review.car else None,
        attributes=_car_review,
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
        return self.entity_description.attributes(self.coordinator.data, self.hass.config.language)
