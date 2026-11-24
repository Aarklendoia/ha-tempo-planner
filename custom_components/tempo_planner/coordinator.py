"""Recompute the plan when an input changes, and every 15 minutes."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import const
from .planner import (
    Inputs,
    PeakLoad,
    Plan,
    Settings,
    make_plan,
    parse_color,
    peak_load_from_history,
)

_LOGGER = logging.getLogger(__name__)

type TempoPlannerConfigEntry = ConfigEntry[TempoPlannerCoordinator]


def entry_config(entry: ConfigEntry) -> dict:
    """Entities from the setup, overridden by the options."""
    return {**entry.data, **entry.options}


def settings_from(config: dict) -> Settings:
    """Settings from the options; anything missing keeps its default."""
    default = Settings()

    def num(key: str, fallback: float) -> float:
        value = config.get(key)
        return fallback if value is None else float(value)

    def clock(key: str, fallback: time) -> time:
        value = config.get(key)
        return fallback if not value else time.fromisoformat(value)

    return Settings(
        offpeak_start=clock(const.CONF_OFFPEAK_START, default.offpeak_start),
        offpeak_end=clock(const.CONF_OFFPEAK_END, default.offpeak_end),
        max_power_kw=num(const.CONF_MAX_POWER, default.max_power_kw),
        battery_capacity_kwh=num(const.CONF_BATTERY_CAPACITY, default.battery_capacity_kwh),
        battery_reserve_pct=num(const.CONF_BATTERY_RESERVE, default.battery_reserve_pct),
        battery_charge_kw=num(const.CONF_BATTERY_CHARGE_KW, default.battery_charge_kw),
        battery_min_gain_eur_kwh=num(
            const.CONF_BATTERY_MIN_GAIN, default.battery_min_gain_eur_kwh * 100
        )
        / 100,
        peak_load_kwh=num(const.CONF_PEAK_LOAD, default.peak_load_kwh),
        peak_load_days=int(num(const.CONF_PEAK_LOAD_DAYS, default.peak_load_days)),
        car_capacity_kwh=num(const.CONF_CAR_CAPACITY, default.car_capacity_kwh),
        car_charge_kw=num(const.CONF_CAR_CHARGE_KW, default.car_charge_kw),
        car_target_pct=num(const.CONF_CAR_TARGET_PCT, default.car_target_pct),
        car_min_kwh=num(const.CONF_CAR_MIN, default.car_min_kwh),
        dishwasher_duration=timedelta(
            minutes=num(
                const.CONF_DISHWASHER_MINUTES,
                default.dishwasher_duration.total_seconds() / 60,
            )
        ),
        dishwasher_solar_kwh=num(const.CONF_DISHWASHER_SOLAR, default.dishwasher_solar_kwh),
    )


class TempoPlannerCoordinator(DataUpdateCoordinator[Plan]):
    """Holds the current plan."""

    config_entry: TempoPlannerConfigEntry

    def __init__(self, hass: HomeAssistant, entry: TempoPlannerConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=const.DOMAIN,
            update_interval=timedelta(minutes=15),
        )
        self._config = entry_config(entry)
        self._settings = settings_from(self._config)
        self._peak_load: PeakLoad | None = None
        self._peak_load_day: date | None = None

    @property
    def watched(self) -> list[str]:
        # The house energy meter moves all the time; its history is read daily.
        return [
            e
            for k in const.ENTITY_KEYS
            if k != const.CONF_HOUSE_ENERGY and (e := self._config.get(k))
        ]

    @callback
    def async_start_tracking(self) -> None:
        """Recompute as soon as an input changes."""

        @callback
        def _changed(event: Event[EventStateChangedData]) -> None:
            self.hass.async_create_task(self.async_request_refresh())

        self.config_entry.async_on_unload(
            async_track_state_change_event(self.hass, self.watched, _changed)
        )

    def _state(self, key: str) -> str | None:
        entity_id = self._config.get(key)
        if not entity_id or (state := self.hass.states.get(entity_id)) is None:
            return None
        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None
        return state.state

    def _number(self, key: str) -> float | None:
        try:
            return float(self._state(key))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

    def _instant(self, key: str) -> datetime | None:
        value = self._state(key)
        return dt_util.parse_datetime(value) if value else None

    def _plugged(self) -> bool | None:
        value = self._state(const.CONF_CAR_PLUGGED)
        if value is None:
            return None
        # A binary sensor, or the Renault plug status ("plugged" / "unplugged").
        return value in (STATE_ON, "plugged")

    async def _async_peak_load(self) -> PeakLoad | None:
        """Peak-hour consumption from the recorder, read once a day."""
        entity_id = self._config.get(const.CONF_HOUSE_ENERGY)
        if not entity_id or "recorder" not in self.hass.config.components:
            return None
        today = dt_util.now().date()
        if self._peak_load_day == today:
            return self._peak_load

        # Imported here: the recorder is only an after-dependency.
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        end = dt_util.start_of_local_day()
        start = end - timedelta(days=self._settings.peak_load_days)
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start,
                end,
                {entity_id},
                "hour",
                {"energy": "kWh"},
                {"change"},
            )
        except Exception:  # noqa: BLE001 - the setting is a good enough fallback
            _LOGGER.exception("Cannot read the history of %s", entity_id)
            return None
        hours = [
            (dt_util.as_local(dt_util.utc_from_timestamp(row["start"])), row["change"])
            for row in stats.get(entity_id, [])
            if row.get("change") is not None
        ]
        self._peak_load = peak_load_from_history(hours, self._settings)
        self._peak_load_day = today
        if self._peak_load is None:
            _LOGGER.info("No complete day in the history of %s yet", entity_id)
        return self._peak_load

    def read_inputs(self, peak_load: PeakLoad | None = None) -> Inputs:
        return Inputs(
            now=dt_util.now(),
            tomorrow=parse_color(self._state(const.CONF_TOMORROW_COLOR)),
            today=parse_color(self._state(const.CONF_TODAY_COLOR)),
            prices={
                key: price
                for key, conf in const.CONF_PRICES.items()
                if (price := self._number(conf)) is not None
            },
            solar_tomorrow_kwh=self._number(const.CONF_SOLAR_TOMORROW),
            solar_peak_tomorrow=self._instant(const.CONF_SOLAR_PEAK),
            battery_soc=self._number(const.CONF_BATTERY_SOC),
            car_soc=self._number(const.CONF_CAR_SOC),
            car_plugged=self._plugged(),
            car_target_pct=self._number(const.CONF_CAR_TARGET),
            peak_load=peak_load,
        )

    async def _async_update_data(self) -> Plan:
        peak_load = await self._async_peak_load()
        return make_plan(self.read_inputs(peak_load), self._settings)
