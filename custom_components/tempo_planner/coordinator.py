"""Recompute the plan when an input changes, and every 15 minutes."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
import logging
from typing import Any

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
    peak_totals,
    tempo_day,
)
from .review import (
    DayReview,
    Forecast,
    car_daily_use,
    car_night,
    night_before,
    review_day,
    soc_during,
    summarize,
)

_LOGGER = logging.getLogger(__name__)

# Statistics read to learn the peak-hour consumption: long enough for a
# winter's red days.
HISTORY_WINDOW = timedelta(days=120)
# Colours of past Tempo days and reviews kept in the store.
COLORS_KEPT = timedelta(days=400)
# History read before a night, so that its first change is a change.
HISTORY_LEAD = timedelta(hours=1)
# Forecasts waiting for their review.
FORECASTS_KEPT = timedelta(days=30)
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
        car_reserve_pct=num(const.CONF_CAR_RESERVE, default.car_reserve_pct),
        car_daily_kwh=num(const.CONF_CAR_DAILY, default.car_daily_kwh),
        car_starts_at_offpeak=bool(
            config.get(const.CONF_CAR_STARTS_AT_OFFPEAK, default.car_starts_at_offpeak)
        ),
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
        # Kept across restarts: the colour of each past Tempo day, the frozen
        # forecasts and the reviews.
        self._store: Store[dict[str, dict[str, Any]]] = Store(
            hass, STORAGE_VERSION, f"{const.DOMAIN}.{entry.entry_id}"
        )
        self._colors: dict[date, Color] | None = None
        self._forecasts: dict[date, Forecast] = {}
        self._reviews: dict[date, DayReview] = {}
        self._reviewed_on: date | None = None

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

    async def _async_load_store(self) -> dict[date, Color]:
        """Read the store once; past colours are completed by the recorder."""
        if self._colors is not None:
            return self._colors
        stored = await self._store.async_load() or {}
        self._forecasts = {
            day: Forecast.from_dict(day, data)
            for key, data in stored.get("forecasts", {}).items()
            if (day := date.fromisoformat(key))
        }
        self._reviews = {
            day: DayReview.from_dict(day, data)
            for key, data in stored.get("reviews", {}).items()
            if (day := date.fromisoformat(key))
        }
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
        self._save()

    def _remember_forecast(self, inputs: Inputs, plan: Plan) -> None:
        """Freeze the forecast for the next Tempo day until its night starts."""
        if inputs.now >= plan.night_start:
            return
        forecast = Forecast.from_plan(plan)
        if self._forecasts.get(forecast.day) == forecast:
            return
        self._forecasts[forecast.day] = forecast
        oldest = forecast.day - FORECASTS_KEPT
        self._forecasts = {d: f for d, f in self._forecasts.items() if d >= oldest}
        self._save()

    def _save(self) -> None:
        self._store.async_delay_save(self._store_data, 10)

    def _store_data(self) -> dict[str, dict[str, Any]]:
        def by_day(items: dict[date, Any], value: Any) -> dict[str, Any]:
            return {d.isoformat(): value(v) for d, v in sorted(items.items())}

        return {
            "colors": by_day(self._colors or {}, str),
            "forecasts": by_day(self._forecasts, lambda f: f.to_dict()),
            "reviews": by_day(self._reviews, lambda r: r.to_dict()),
        }

    async def _async_review(self) -> None:
        """Once a day, review yesterday and any day missed while stopped."""
        now = dt_util.now()
        if self._reviewed_on == now.date():
            return
        yesterday = now.date() - timedelta(days=1)
        days = {yesterday} | {
            d for d in self._forecasts if d < yesterday and d not in self._reviews
        }
        totals = peak_totals(self._hours, self._settings)
        for day in sorted(days):
            start, end = night_before(day, self._settings, now.tzinfo)
            # From an hour before: a change right at the start (the car's program
            # starts at 22:00 sharp) would otherwise be read as the start state.
            since = start - HISTORY_LEAD
            car = car_night(
                self._charging(await self._async_history(const.CONF_CAR_CHARGING, since, end)),
                self._levels(await self._async_history(const.CONF_CAR_SOC, since, end)),
                start,
                end,
                self._settings,
            )
            review = review_day(
                day,
                self._forecasts.get(day),
                totals.get(day),
                soc_during(
                    self._levels(await self._async_history(const.CONF_BATTERY_SOC, since, end)),
                    start,
                    end,
                ),
                (self._colors or {}).get(day),
                car,
            )
            if review is not None:
                self._reviews[day] = review
        oldest = yesterday - COLORS_KEPT
        self._reviews = {d: r for d, r in self._reviews.items() if d >= oldest}
        self._reviewed_on = now.date()
        self._save()

    async def _async_history(
        self, key: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, str]]:
        """States of an input recorded during a night, the one before it included."""
        entity_id = self._config.get(key)
        if not entity_id or not self._recorder_ready():
            return []

        from homeassistant.components.recorder import get_instance, history

        try:
            found = await get_instance(self.hass).async_add_executor_job(
                history.get_significant_states,
                self.hass,
                start,
                end,
                [entity_id],
                None,
                True,  # include_start_time_state
                False,  # significant_changes_only
                False,  # minimal_response
                True,  # no_attributes
            )
        except Exception:  # noqa: BLE001 - a partial review is still useful
            _LOGGER.exception("Cannot read the history of %s", entity_id)
            return []
        return sorted(
            (dt_util.as_local(state.last_changed), state.state)
            for state in found.get(entity_id, [])
            if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
        )

    @staticmethod
    def _levels(states: list[tuple[datetime, str]]) -> list[tuple[datetime, float]]:
        levels = []
        for at, value in states:
            try:
                levels.append((at, float(value)))
            except ValueError:
                continue
        return levels

    @staticmethod
    def _charging(states: list[tuple[datetime, str]]) -> list[tuple[datetime, bool]]:
        # A binary sensor, or a Renault charge state ("charge_in_progress").
        return [(at, value in (STATE_ON, "charge_in_progress")) for at, value in states]

    async def _async_trip(self) -> date | None:
        """Day of the next trip in the calendar, within the next few days."""
        entity_id = self._config.get(const.CONF_TRIP_CALENDAR)
        if not entity_id:
            return None
        keyword = (
            self._config.get(const.CONF_TRIP_KEYWORD) or const.DEFAULT_TRIP_KEYWORD
        ).casefold()
        now = dt_util.now()
        try:
            response = await self.hass.services.async_call(
                "calendar",
                "get_events",
                {
                    "entity_id": entity_id,
                    "start_date_time": now,
                    "duration": {"days": const.TRIP_LOOKAHEAD_DAYS},
                },
                blocking=True,
                return_response=True,
            )
        except Exception:  # noqa: BLE001 - no trip is a safe default
            _LOGGER.warning("Cannot read the trips in %s", entity_id, exc_info=True)
            return None
        departures = []
        for event in (response or {}).get(entity_id, {}).get("events", []):
            if keyword not in str(event.get("summary", "")).casefold():
                continue
            start = str(event.get("start", ""))
            when = dt_util.parse_datetime(start)
            day = dt_util.as_local(when).date() if when else dt_util.parse_date(start)
            if day is not None and day > now.date():
                departures.append(day)
        return min(departures, default=None)

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
        colors = await self._async_load_store()
        await self._async_load_hours()
        await self._async_review()
        inputs = replace(
            self.read_inputs(),
            car_daily_kwh=car_daily_use(
                list(self._reviews.values()), self._settings.car_capacity_kwh
            ),
            trip_departure=await self._async_trip(),
        )
        self._remember_today(inputs)
        peak_load: PeakLoad | None = None
        if self._hours:
            peak_load = peak_load_from_history(self._hours, self._settings, colors, inputs.tomorrow)
        plan = make_plan(replace(inputs, peak_load=peak_load), self._settings)
        self._remember_forecast(inputs, plan)
        if self._reviews:
            plan.review = self._reviews[max(self._reviews)]
            plan.summary = summarize(list(self._reviews.values()))
        return plan
