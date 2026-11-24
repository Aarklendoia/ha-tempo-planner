"""Recompute the plan when an input changes, and every 15 minutes."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import const
from .planner import (
    Color,
    Inputs,
    PeakLoad,
    Plan,
    Settings,
    make_plan,
    parse_color,
    peak_load_from_history,
    tempo_day,
)

_LOGGER = logging.getLogger(__name__)

# Statistics read to learn the peak-hour consumption: long enough for a
# winter's red days.
HISTORY_WINDOW = timedelta(days=120)
# Colours of past Tempo days kept in the store.
COLORS_KEPT = timedelta(days=400)
STORAGE_VERSION = 1

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
        # Hourly house consumption, reloaded once a day.
        self._hours: list[tuple[datetime, float]] = []
        self._hours_day: date | None = None
        # Colour of each past Tempo day, kept across restarts.
        self._store: Store[dict[str, dict[str, str]]] = Store(
            hass, STORAGE_VERSION, f"{const.DOMAIN}.{entry.entry_id}"
        )
        self._colors: dict[date, Color] | None = None

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

    def _recorder_ready(self) -> bool:
        return "recorder" in self.hass.config.components

    async def _async_load_hours(self) -> None:
        """Hourly house consumption from the recorder's statistics, once a day."""
        entity_id = self._config.get(const.CONF_HOUSE_ENERGY)
        if not entity_id or not self._recorder_ready():
            return
        today = dt_util.now().date()
        if self._hours_day == today:
            return

        # Imported here: the recorder is only an after-dependency.
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        end = dt_util.start_of_local_day()
        try:
            stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                end - HISTORY_WINDOW,
                end,
                {entity_id},
                "hour",
                {"energy": "kWh"},
                {"change"},
            )
        except Exception:  # noqa: BLE001 - the setting is a good enough fallback
            _LOGGER.exception("Cannot read the history of %s", entity_id)
            return
        self._hours = [
            (dt_util.as_local(dt_util.utc_from_timestamp(row["start"])), row["change"])
            for row in stats.get(entity_id, [])
            if row.get("change") is not None
        ]
        self._hours_day = today

    async def _async_load_colors(self) -> dict[date, Color]:
        """Past colours from the store, completed by the recorder's state history."""
        if self._colors is not None:
            return self._colors
        stored = await self._store.async_load() or {}
        colors = {
            date.fromisoformat(day): color
            for day, value in stored.get("colors", {}).items()
            if (color := parse_color(value)) is not Color.UNKNOWN
        }
        for day, color in (await self._async_recorded_colors()).items():
            colors.setdefault(day, color)
        self._colors = colors
        return colors

    async def _async_recorded_colors(self) -> dict[date, Color]:
        """Colour of each day the recorder still has, read at noon."""
        entity_id = self._config.get(const.CONF_TODAY_COLOR)
        if not entity_id or not self._recorder_ready():
            return {}

        from homeassistant.components.recorder import get_instance, history

        now = dt_util.now()
        start = dt_util.start_of_local_day() - HISTORY_WINDOW
        try:
            found = await get_instance(self.hass).async_add_executor_job(
                history.get_significant_states,
                self.hass,
                start,
                now,
                [entity_id],
                None,
                True,  # include_start_time_state
                False,  # significant_changes_only
                False,  # minimal_response
                True,  # no_attributes
            )
        except Exception:  # noqa: BLE001 - the store fills up day after day anyway
            _LOGGER.exception("Cannot read the history of %s", entity_id)
            return {}
        states = sorted(found.get(entity_id, []), key=lambda st: st.last_changed)
        colors: dict[date, Color] = {}
        day = start.date()
        while day < tempo_day(now, self._settings):
            noon = datetime.combine(day, time(12), now.tzinfo)
            before = [st for st in states if st.last_changed <= noon]
            if before and (color := parse_color(before[-1].state)) is not Color.UNKNOWN:
                colors[day] = color
            day += timedelta(days=1)
        return colors

    def _remember_today(self, inputs: Inputs) -> None:
        """Store the colour of the Tempo day in progress."""
        if self._colors is None or inputs.today is Color.UNKNOWN:
            return
        day = tempo_day(inputs.now, self._settings)
        if self._colors.get(day) is inputs.today:
            return
        self._colors[day] = inputs.today
        oldest = day - COLORS_KEPT
        self._colors = {d: c for d, c in self._colors.items() if d >= oldest}
        self._store.async_delay_save(self._colors_data, 10)

    def _colors_data(self) -> dict[str, dict[str, str]]:
        colors = self._colors or {}
        return {"colors": {d.isoformat(): str(c) for d, c in sorted(colors.items())}}

    def read_inputs(self) -> Inputs:
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
        )

    async def _async_update_data(self) -> Plan:
        colors = await self._async_load_colors()
        await self._async_load_hours()
        inputs = self.read_inputs()
        self._remember_today(inputs)
        peak_load: PeakLoad | None = None
        if self._hours:
            peak_load = peak_load_from_history(self._hours, self._settings, colors, inputs.tomorrow)
        return make_plan(replace(inputs, peak_load=peak_load), self._settings)
