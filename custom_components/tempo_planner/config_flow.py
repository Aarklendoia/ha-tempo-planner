"""Config and options flow."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from . import const
from .coordinator import entry_config
from .planner import Settings

_SENSOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
_NUMBER = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "number", "input_number"])
)
_ENERGY = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
)
_CALENDAR = selector.EntitySelector(selector.EntitySelectorConfig(domain="calendar"))
_PLUG = selector.EntitySelector(selector.EntitySelectorConfig(domain=["binary_sensor", "sensor"]))

_ENTITY_SELECTORS = {
    const.CONF_TOMORROW_COLOR: _SENSOR,
    const.CONF_TODAY_COLOR: _SENSOR,
    const.CONF_SOLAR_TOMORROW: _SENSOR,
    const.CONF_SOLAR_PEAK: _SENSOR,
    const.CONF_BATTERY_SOC: _SENSOR,
    const.CONF_CAR_SOC: _SENSOR,
    const.CONF_CAR_PLUGGED: _PLUG,
    const.CONF_CAR_CHARGING: _PLUG,
    const.CONF_TRIP_CALENDAR: _CALENDAR,
    const.CONF_CAR_TARGET: _NUMBER,
    const.CONF_HOUSE_ENERGY: _ENERGY,
    const.CONF_CAR_ENERGY: _ENERGY,
    **{conf: _NUMBER for conf in const.CONF_PRICES.values()},
}


def _entities_schema(values: dict[str, Any]) -> vol.Schema:
    fields: dict[Any, Any] = {}
    for key, sel in _ENTITY_SELECTORS.items():
        if key == const.CONF_TOMORROW_COLOR:
            fields[vol.Required(key, default=values.get(key, vol.UNDEFINED))] = sel
        else:
            fields[vol.Optional(key, description={"suggested_value": values.get(key)})] = sel
    return vol.Schema(fields)


def _num(lo: float, hi: float, step: float, unit: str) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=lo,
            max=hi,
            step=step,
            unit_of_measurement=unit,
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _settings_schema(values: dict[str, Any]) -> vol.Schema:
    d = Settings()
    defaults: dict[str, tuple[Any, Any]] = {
        const.CONF_OFFPEAK_START: (d.offpeak_start.isoformat(), selector.TimeSelector()),
        const.CONF_OFFPEAK_END: (d.offpeak_end.isoformat(), selector.TimeSelector()),
        const.CONF_MAX_POWER: (d.max_power_kw, _num(1, 36, 0.1, "kW")),
        const.CONF_PEAK_LOAD: (d.peak_load_kwh, _num(0, 100, 0.5, "kWh")),
        const.CONF_PEAK_LOAD_DAYS: (d.peak_load_days, _num(1, 60, 1, "d")),
        const.CONF_BATTERY_CAPACITY: (d.battery_capacity_kwh, _num(0, 100, 0.1, "kWh")),
        const.CONF_BATTERY_RESERVE: (d.battery_reserve_pct, _num(0, 100, 1, "%")),
        const.CONF_BATTERY_CHARGE_KW: (d.battery_charge_kw, _num(0.1, 22, 0.1, "kW")),
        const.CONF_INVERTER_KW: (d.inverter_kw, _num(0.5, 30, 0.1, "kW")),
        const.CONF_RESALE: (round(d.resale_eur_kwh * 100, 2), _num(0, 50, 0.1, "c€/kWh")),
        const.CONF_BATTERY_MIN_GAIN: (
            round(d.battery_min_gain_eur_kwh * 100, 2),
            _num(0, 50, 0.1, "c€/kWh"),
        ),
        const.CONF_CAR_CAPACITY: (d.car_capacity_kwh, _num(1, 200, 0.1, "kWh")),
        const.CONF_CAR_CHARGE_KW: (d.car_charge_kw, _num(1, 22, 0.1, "kW")),
        const.CONF_CAR_TARGET_PCT: (d.car_target_pct, _num(10, 100, 1, "%")),
        const.CONF_CAR_MIN: (d.car_min_kwh, _num(0, 50, 0.5, "kWh")),
        const.CONF_CAR_RESERVE: (d.car_reserve_pct, _num(0, 100, 1, "%")),
        const.CONF_CAR_DAILY: (d.car_daily_kwh, _num(0, 100, 0.5, "kWh")),
        const.CONF_TRIP_KEYWORD: (const.DEFAULT_TRIP_KEYWORD, selector.TextSelector()),
        const.CONF_CAR_STARTS_AT_OFFPEAK: (d.car_starts_at_offpeak, selector.BooleanSelector()),
        const.CONF_DISHWASHER_MINUTES: (
            d.dishwasher_duration.total_seconds() / 60,
            _num(10, 600, 5, "min"),
        ),
        const.CONF_DISHWASHER_SOLAR: (d.dishwasher_solar_kwh, _num(0, 100, 0.5, "kWh")),
    }
    return vol.Schema(
        {
            vol.Required(key, default=values.get(key, default)): sel
            for key, (default, sel) in defaults.items()
        }
    )


class TempoPlannerConfigFlow(ConfigFlow, domain=const.DOMAIN):
    """Pick the entities the planner reads."""

    VERSION = 1

    def __init__(self) -> None:
        self._entities: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(const.DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            self._entities = user_input
            return await self.async_step_settings()
        return self.async_show_form(step_id="user", data_schema=_entities_schema({}))

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The house, right after the entities."""
        if user_input is not None:
            return self.async_create_entry(
                title="Tempo Planner", data=self._entities, options=user_input
            )
        return self.async_show_form(step_id="settings", data_schema=_settings_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> TempoPlannerOptionsFlow:
        return TempoPlannerOptionsFlow()


class TempoPlannerOptionsFlow(OptionsFlowWithReload):
    """Change the entities, then the settings of the house."""

    def __init__(self) -> None:
        self._entities: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            # An optional field left empty is absent: it must also clear the old value.
            self._entities = {k: user_input.get(k) for k in const.ENTITY_KEYS}
            return await self.async_step_settings()
        return self.async_show_form(
            step_id="init",
            data_schema=_entities_schema(entry_config(self.config_entry)),
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={**self._entities, **user_input})
        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(dict(self.config_entry.options)),
        )
