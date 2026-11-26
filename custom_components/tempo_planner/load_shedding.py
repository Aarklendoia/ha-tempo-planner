"""Load shedding inside Home Assistant: drive the appliances, keep their state."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any
import uuid

from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import const
from .planner import Color, Settings, parse_color, tempo_day
from .shedding import (
    Appliance,
    Behaviour,
    Candidate,
    PowerLevel,
    PowerSettings,
    PowerShed,
    PowerTimers,
    ShedReason,
    current_color,
    is_running,
    power_level,
    power_step,
    scheduled_state,
    tariff_until,
    to_kw,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1

_MISSING = (None, STATE_UNAVAILABLE, STATE_UNKNOWN)

# The power delays are counted on this tick, between readings.
POWER_TICK = timedelta(seconds=5)
# Below this, an appliance draws nothing worth shedding.
IDLE_KW = 0.05

# Service and field that force a mode, and where the current mode is read.
_MODES: dict[str, tuple[str, str, str | None]] = {
    "select": ("select_option", "option", None),
    "input_select": ("select_option", "option", None),
    "climate": ("set_preset_mode", "preset_mode", "preset_mode"),
    "water_heater": ("set_operation_mode", "operation_mode", None),
}

_TEXTS = {
    "en": {
        "title": "⚡ Load shedding",
        "turned_on": "{name} was turned back on while shed: turned off again until {until}."
        " Turn its load shedding off to keep it on.",
        "mode_changed": "{name} left its reduced mode while shed: set back until {until}."
        " Turn its load shedding off to keep it.",
        "running": "{name} runs while it should not, until {until}.",
        "until_power": "the power comes down",
    },
    "fr": {
        "title": "⚡ Délestage",
        "turned_on": "{name} a été rallumé pendant le délestage : recoupé jusqu'à {until}."
        " Désactive son délestage pour le garder allumé.",
        "mode_changed": "{name} a quitté son mode réduit pendant le délestage : remis jusqu'à"
        " {until}. Désactive son délestage pour le garder.",
        "running": "{name} fonctionne alors qu'il ne devrait pas, jusqu'à {until}.",
        "until_power": "ce que la consommation baisse",
    },
}


def signal_update(entry_id: str) -> str:
    """Sent when the shedding state of the appliances changes."""
    return f"{const.DOMAIN}_{entry_id}_shedding"


def signal_added(entry_id: str) -> str:
    """Sent with an appliance that needs its entities."""
    return f"{const.DOMAIN}_{entry_id}_appliance_added"


@dataclass
class ShedState:
    """Where an appliance stands; kept across restarts."""

    shed: bool = False
    reason: ShedReason | None = None
    until: datetime | None = None
    # The state to restore: "on"/"off", or the mode before the reduced one.
    saved: str | None = None
    # The alert behaviour notifies once per running spell.
    running: bool = False
    # The state seen when the shedding started (its context): no override, even
    # when its change event is handled after the start.
    seen: str | None = None
    # Shed by power: when, and what it drew then.
    since: datetime | None = None
    power_kw: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "shed": self.shed,
            "reason": str(self.reason) if self.reason else None,
            "until": self.until.isoformat() if self.until else None,
            "saved": self.saved,
            "running": self.running,
            "seen": self.seen,
            "since": self.since.isoformat() if self.since else None,
            "power_kw": self.power_kw,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ShedState:
        return cls(
            shed=bool(data.get("shed")),
            reason=ShedReason(r) if (r := data.get("reason")) else None,
            until=dt_util.parse_datetime(u) if (u := data.get("until")) else None,
            saved=data.get("saved"),
            running=bool(data.get("running")),
            seen=data.get("seen"),
            since=dt_util.parse_datetime(t) if (t := data.get("since")) else None,
            power_kw=data.get("power_kw"),
        )


class LoadShedder:
    """Holds the appliances and sheds them."""

    def __init__(self, hass: HomeAssistant, entry_id: str, settings: Settings, config: dict):
        self.hass = hass
        self.entry_id = entry_id
        self._settings = settings
        self._color_entity: str | None = config.get(const.CONF_TODAY_COLOR)
        self._tomorrow_entity: str | None = config.get(const.CONF_TOMORROW_COLOR)
        # The colour of each Tempo day as announced the day before.
        self._announced: dict[date, Color] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{const.DOMAIN}.{entry_id}.appliances"
        )
        self.appliances: dict[str, Appliance] = {}
        self.states: dict[str, ShedState] = {}
        self._lock = asyncio.Lock()
        self._unsubs: list[Callable[[], None]] = []
        self._unsub_watch: Callable[[], None] | None = None
        self._unsub_schedules: Callable[[], None] | None = None
        # The colour whose schedules the appliances follow; they switch when it changes.
        self._schedule_color: Color | None = None
        # Load shedding by power.
        self.power = PowerSettings()
        self.power_kw: float | None = None
        self.level = PowerLevel.NONE
        self._timers = PowerTimers()
        self._unsub_power: list[Callable[[], None]] = []

    # --- Life cycle -------------------------------------------------------

    async def async_load(self) -> None:
        """Read the appliances, before their entities are set up."""
        stored = await self._store.async_load() or {}
        for data in stored.get("appliances", []):
            try:
                appliance = Appliance.from_dict(data)
            except (KeyError, ValueError):
                _LOGGER.warning("Ignoring a stored appliance that cannot be read: %s", data)
                continue
            self.appliances[appliance.id] = appliance
        self.states = {
            key: ShedState.from_dict(data)
            for key, data in stored.get("states", {}).items()
            if key in self.appliances
        }
        try:
            self.power = PowerSettings.from_dict(stored.get("power") or {})
        except (TypeError, ValueError):
            _LOGGER.warning("Ignoring stored power settings that cannot be read")
        for day, color in stored.get("announced", {}).items():
            try:
                self._announced[date.fromisoformat(day)] = Color(color)
            except ValueError:
                continue

    async def async_start(self) -> None:
        """Follow the tariff and the appliances, and shed what must be."""
        for boundary in (self._settings.offpeak_start, self._settings.offpeak_end):
            self._unsubs.append(
                async_track_time_change(
                    self.hass,
                    self._on_time,
                    hour=boundary.hour,
                    minute=boundary.minute,
                    second=boundary.second,
                )
            )
        if self._color_entity:
            self._unsubs.append(
                async_track_state_change_event(self.hass, self._color_entity, self._on_color)
            )
        if self._tomorrow_entity:
            self._unsubs.append(
                async_track_state_change_event(self.hass, self._tomorrow_entity, self._on_tomorrow)
            )
            self._remember_tomorrow()
        self._watch()
        # Started in the middle of a day: schedules act at their next change only,
        # like an automation, so a manual change made meanwhile is kept.
        self._schedule_color = self.color()
        await self.async_evaluate()
        self._start_power()

    async def async_stop(self) -> None:
        """Stop acting; appliances stay as they are and are taken over on the next start."""
        await self._store.async_save(self._data())
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._unwatch()
        self._stop_power()

    @callback
    def _unwatch(self) -> None:
        for unsub in (self._unsub_watch, self._unsub_schedules):
            if unsub:
                unsub()
        self._unsub_watch = self._unsub_schedules = None

    @callback
    def _watch(self) -> None:
        self._unwatch()
        watched = sorted({a.watched_entity for a in self.appliances.values()})
        if watched:
            self._unsub_watch = async_track_state_change_event(
                self.hass, watched, self._on_appliance
            )
        schedules = sorted({s for a in self.appliances.values() for s in a.schedules})
        if schedules:
            self._unsub_schedules = async_track_state_change_event(
                self.hass, schedules, self._on_schedule
            )

    # --- Changes from the API and the switches ------------------------------

    async def async_save_appliance(self, data: dict[str, Any]) -> Appliance:
        """Add an appliance, or replace the one with the same id."""
        appliance_id = data.get("id") or uuid.uuid4().hex
        appliance = Appliance.from_dict({**data, "id": appliance_id})
        old = self.appliances.get(appliance_id)
        async with self._lock:
            state = self._state(appliance_id)
            if old is not None and state.shed and _drives_otherwise(old, appliance):
                # Restored with the old settings, shed again with the new ones.
                await self._release(old, state)
            self.appliances[appliance_id] = appliance
            self._save()
        self._watch()
        if old is None:
            async_dispatcher_send(self.hass, signal_added(self.entry_id), appliance)
        await self.async_evaluate()
        if old is None or _schedules_of(old) != _schedules_of(appliance):
            # New schedules apply at once.
            async with self._lock:
                if not self._state(appliance_id).shed:
                    await self._follow_schedule(appliance, self.color())
        if old is not None and old.name != appliance.name:
            # Entity names are translated once: reloading renames them.
            self.hass.config_entries.async_schedule_reload(self.entry_id)
        return appliance

    async def async_delete_appliance(self, appliance_id: str) -> None:
        appliance = self.appliances.get(appliance_id)
        if appliance is None:
            raise KeyError(appliance_id)
        async with self._lock:
            if self._state(appliance_id).shed:
                # Handed back as it was, whatever its schedules say.
                await self._release(appliance, self._state(appliance_id), follow_schedule=False)
            del self.appliances[appliance_id]
            self.states.pop(appliance_id, None)
            self._save()
        self._watch()
        registry = er.async_get(self.hass)
        for platform, suffix in (("switch", "shed_enabled"), ("binary_sensor", "shed")):
            unique_id = f"{self.entry_id}_{appliance_id}_{suffix}"
            if entity_id := registry.async_get_entity_id(platform, const.DOMAIN, unique_id):
                registry.async_remove(entity_id)
        async_dispatcher_send(self.hass, signal_update(self.entry_id))

    async def async_set_enabled(self, appliance_id: str, enabled: bool) -> None:
        appliance = self.appliances[appliance_id]
        await self.async_save_appliance({**appliance.to_dict(), "enabled": enabled})

    # --- Evaluation -------------------------------------------------------

    @callback
    def _on_time(self, _: datetime) -> None:
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _on_color(self, _: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _on_tomorrow(self, _: Event[EventStateChangedData]) -> None:
        self._remember_tomorrow()

    @callback
    def _remember_tomorrow(self) -> None:
        """Keep the next day's colour: the current colour entity lags behind at 06:00."""
        state = self.hass.states.get(self._tomorrow_entity) if self._tomorrow_entity else None
        color = parse_color(state.state if state else None)
        if color is Color.UNKNOWN:
            return
        today = tempo_day(dt_util.now(), self._settings)
        tomorrow = today + timedelta(days=1)
        if self._announced.get(tomorrow) is color:
            return
        self._announced = {d: c for d, c in self._announced.items() if d >= today} | {
            tomorrow: color
        }
        self._save()

    def color(self) -> Color:
        """Colour of the Tempo day in progress."""
        now = dt_util.now()
        day = tempo_day(now, self._settings)
        state = self.hass.states.get(self._color_entity) if self._color_entity else None
        return current_color(
            parse_color(state.state if state else None),
            state.last_updated if state else None,
            self._announced.get(day),
            datetime.combine(day, self._settings.offpeak_end, now.tzinfo),
        )

    async def async_evaluate(self) -> None:
        """Shed or release every appliance by the current tariff."""
        now = dt_util.now()
        color = self.color()
        async with self._lock:
            changed = False
            # Released by this pass: already put where their schedule wants them.
            released: set[str] = set()
            for appliance in list(self.appliances.values()):
                state = self._state(appliance.id)
                until = tariff_until(
                    appliance,
                    now,
                    color,
                    self._settings.offpeak_start,
                    self._settings.offpeak_end,
                )
                # The colour entity is briefly unavailable: no flicker, the
                # shedding in progress goes on until its end.
                if (
                    color is Color.UNKNOWN
                    and state.shed
                    and appliance.enabled
                    and state.until is not None
                    and now < state.until
                ):
                    continue
                if state.shed and not appliance.enabled:
                    # Its switch is off: handed back, whatever the reason.
                    await self._release(appliance, state)
                    released.add(appliance.id)
                    changed = True
                elif until is not None and not state.shed:
                    await self._shed(appliance, state, until)
                    changed = True
                elif until is not None and state.reason is ShedReason.POWER:
                    # Already shed by power: the tariff takes over, with the same
                    # state to restore.
                    state.reason, state.until = ShedReason.TARIFF, until
                    state.since = state.power_kw = None
                    changed = True
                elif until is not None and state.until != until:
                    state.until = until
                    changed = True
                elif until is None and state.shed and state.reason is ShedReason.TARIFF:
                    await self._release(appliance, state)
                    released.add(appliance.id)
                    changed = True
            if changed:
                self._save()
            if color is not Color.UNKNOWN and color != self._schedule_color:
                # A new Tempo day: each appliance follows the schedule of its colour.
                self._schedule_color = color
                for appliance in list(self.appliances.values()):
                    if appliance.id not in released and not self._state(appliance.id).shed:
                        await self._follow_schedule(appliance, color)
        async_dispatcher_send(self.hass, signal_update(self.entry_id))

    def _state(self, appliance_id: str) -> ShedState:
        return self.states.setdefault(appliance_id, ShedState())

    async def _shed(
        self,
        appliance: Appliance,
        state: ShedState,
        until: datetime | None,
        reason: ShedReason = ShedReason.TARIFF,
    ) -> None:
        state.shed, state.reason, state.until = True, reason, until
        if (seen := self.hass.states.get(appliance.watched_entity)) is not None:
            state.seen = seen.context.id
        current = self.hass.states.get(appliance.entity_id)
        if appliance.behaviour is Behaviour.OFF:
            state.saved = None if _missing(current) else _on_off(current)
            if state.saved == "on":
                await self._call(appliance.domain, "turn_off", appliance.entity_id)
        elif appliance.behaviour is Behaviour.REDUCED:
            mode = _mode(appliance, current)
            state.saved = mode
            if mode is not None and mode != appliance.reduced_option:
                await self._set_mode(appliance, appliance.reduced_option)
        else:
            state.saved = None
            watched = self.hass.states.get(appliance.watched_entity)
            state.running = is_running(appliance, None if _missing(watched) else watched.state)
            if state.running:
                await self._notify(appliance, "running", until)

    async def _release(
        self, appliance: Appliance, state: ShedState, follow_schedule: bool = True
    ) -> None:
        self.states[appliance.id] = ShedState()
        # With a schedule for today's colour, it says what the appliance does next.
        if follow_schedule and await self._follow_schedule(appliance, self.color()):
            return
        current = self.hass.states.get(appliance.entity_id)
        if appliance.behaviour is Behaviour.OFF:
            if state.saved == "on" and not _missing(current) and _on_off(current) == "off":
                await self._call(appliance.domain, "turn_on", appliance.entity_id)
        elif appliance.behaviour is Behaviour.REDUCED:
            mode = _mode(appliance, current)
            if state.saved and mode == appliance.reduced_option and state.saved != mode:
                await self._set_mode(appliance, state.saved)

    # --- Schedules --------------------------------------------------------

    @callback
    def _on_schedule(self, event: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(
            self._async_schedule_changed(event.data["entity_id"], event.data["new_state"])
        )

    async def _async_schedule_changed(self, entity_id: str, new: State | None) -> None:
        if _missing(new):
            return
        async with self._lock:
            color = self.color()
            for appliance in list(self.appliances.values()):
                if (
                    appliance.enabled
                    and appliance.schedule_for(color) == entity_id
                    and not self._state(appliance.id).shed
                ):
                    await self._apply(appliance, scheduled_state(appliance, new.state == "on"))

    async def _follow_schedule(self, appliance: Appliance, color: Color) -> bool:
        """Put the appliance where its schedule for `color` wants it; False without one."""
        if not appliance.enabled or (schedule := appliance.schedule_for(color)) is None:
            return False
        state = self.hass.states.get(schedule)
        if _missing(state):
            return False
        await self._apply(appliance, scheduled_state(appliance, state.state == "on"))
        return True

    async def _apply(self, appliance: Appliance, target: str | None) -> None:
        current = self.hass.states.get(appliance.entity_id)
        if target is None or _missing(current):
            return
        if appliance.behaviour is Behaviour.OFF:
            if _on_off(current) != target:
                service = "turn_on" if target == "on" else "turn_off"
                await self._call(appliance.domain, service, appliance.entity_id)
        elif appliance.behaviour is Behaviour.REDUCED and _mode(appliance, current) != target:
            await self._set_mode(appliance, target)

    # --- Appliances changed by someone else --------------------------------

    @callback
    def _on_appliance(self, event: Event[EventStateChangedData]) -> None:
        # Read now, in the order of the events: a change made before a shedding
        # started is no override, even when handled after it.
        entity_id = event.data["entity_id"]
        shed = [
            a.id
            for a in self.appliances.values()
            if a.watched_entity == entity_id and self.status(a.id).shed
        ]
        if shed:
            self.hass.async_create_task(self._async_enforce(shed, event.data["new_state"]))

    async def _async_enforce(self, appliance_ids: list[str], current: State | None) -> None:
        async with self._lock:
            changed = False
            for appliance_id in appliance_ids:
                appliance = self.appliances.get(appliance_id)
                state = self.states.get(appliance_id)
                if appliance is None or state is None or not state.shed:
                    continue
                changed |= await self._enforce(appliance, state, current)
            if changed:
                self._save()
        if changed:
            # An alert-only appliance started or stopped running.
            async_dispatcher_send(self.hass, signal_update(self.entry_id))

    async def _enforce(self, appliance: Appliance, state: ShedState, current: State | None) -> bool:
        if _missing(current) or current.context.id == state.seen:
            return False
        if appliance.behaviour is Behaviour.OFF:
            if _on_off(current) != "on":
                return False
            first = state.saved is None
            if first:
                # Unavailable when the shedding started: it was on.
                state.saved = "on"
            await self._call(appliance.domain, "turn_off", appliance.entity_id)
            if not first:
                await self._notify(appliance, "turned_on", state.until)
            return first
        if appliance.behaviour is Behaviour.REDUCED:
            mode = _mode(appliance, current)
            if mode is None or mode == appliance.reduced_option:
                return False
            first = state.saved is None
            if first:
                state.saved = mode
            await self._set_mode(appliance, appliance.reduced_option)
            if not first:
                await self._notify(appliance, "mode_changed", state.until)
            return first
        running = is_running(appliance, current.state)
        if running and not state.running:
            await self._notify(appliance, "running", state.until)
        if running != state.running:
            state.running = running
            return True
        return False

    # --- Load shedding by power ----------------------------------------------

    @callback
    def _start_power(self) -> None:
        if not self.power.enabled or not self.power.power_entity:
            return
        self._unsub_power = [
            async_track_state_change_event(
                self.hass, self.power.power_entity, self._on_power_reading
            ),
            async_track_time_interval(self.hass, self._on_power_tick, POWER_TICK),
        ]

    @callback
    def _stop_power(self) -> None:
        for unsub in self._unsub_power:
            unsub()
        self._unsub_power = []
        self._timers = PowerTimers()

    @callback
    def _on_power_reading(self, _: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(self.async_power_step())

    @callback
    def _on_power_tick(self, _: datetime) -> None:
        self.hass.async_create_task(self.async_power_step())

    async def async_save_power(self, data: dict[str, Any]) -> PowerSettings:
        """New power settings: what was shed by power comes back, then it starts over."""
        settings = PowerSettings.from_dict(data)
        self._stop_power()
        async with self._lock:
            for appliance in list(self.appliances.values()):
                state = self._state(appliance.id)
                if state.shed and state.reason is ShedReason.POWER:
                    await self._release(appliance, state)
            self.power = settings
            self.level, self.power_kw = PowerLevel.NONE, None
            self._save()
        self._start_power()
        await self.async_power_step()
        async_dispatcher_send(self.hass, signal_update(self.entry_id))
        return settings

    async def async_set_power_enabled(self, enabled: bool) -> None:
        await self.async_save_power({**self.power.to_dict(), "enabled": enabled})

    def limits(self) -> tuple[float | None, float | None]:
        """The soft and hard limits now, in kW."""
        now = dt_util.now().time()
        offpeak = not (self._settings.offpeak_end <= now < self._settings.offpeak_start)
        return self.power.soft_for(self.color(), offpeak), self.power.hard_limit_kw

    def _read_kw(self, entity_id: str | None) -> float | None:
        state = self.hass.states.get(entity_id) if entity_id else None
        if _missing(state):
            return None
        return to_kw(state.state, state.attributes.get("unit_of_measurement"))

    def _draws(self, appliance: Appliance) -> tuple[bool, float | None]:
        """Whether shedding the appliance frees something, and how much (None: unknown)."""
        current = self.hass.states.get(appliance.entity_id)
        if _missing(current):
            return False, None
        if appliance.behaviour is Behaviour.OFF and _on_off(current) == "off":
            return False, None
        if appliance.behaviour is Behaviour.REDUCED and (
            _mode(appliance, current) == appliance.reduced_option
        ):
            return False, None
        measured = self._read_kw(appliance.power_entity)
        if measured is not None:
            return measured > IDLE_KW, measured
        return True, appliance.power_kw

    async def async_power_step(self) -> None:
        """Shed or bring back one step by the power drawn now."""
        if not self.power.enabled or not self.power.power_entity:
            return
        now = dt_util.now()
        async with self._lock:
            power_kw = self._read_kw(self.power.power_entity)
            soft, hard = self.limits()
            candidates = []
            for appliance in sorted(self.appliances.values(), key=lambda a: (a.priority, a.name)):
                if (
                    not appliance.enabled
                    or appliance.behaviour is Behaviour.ALERT
                    or self._state(appliance.id).shed
                ):
                    continue
                draws, kw = self._draws(appliance)
                if draws:
                    candidates.append(Candidate(appliance, kw))
            shed = sorted(
                (
                    (state.since or now, PowerShed(appliance_id, state.power_kw))
                    for appliance_id, state in self.states.items()
                    if state.shed and state.reason is ShedReason.POWER
                ),
                key=lambda item: item[0],
            )
            decision = power_step(
                now,
                power_kw,
                soft,
                hard,
                self.power,
                self._timers,
                [p for _, p in shed],
                candidates,
            )
            freed = {c.appliance.id: c.power_kw for c in candidates}
            for appliance_id in decision.shed:
                state = self._state(appliance_id)
                await self._shed(self.appliances[appliance_id], state, None, ShedReason.POWER)
                state.since, state.power_kw = now, freed.get(appliance_id)
            for appliance_id in decision.restore:
                if (appliance := self.appliances.get(appliance_id)) is not None:
                    await self._release(appliance, self._state(appliance_id))
            if decision.shed or decision.restore:
                self._save()
            level = power_level(power_kw, soft, hard)
            moved = (
                level is not self.level
                or (power_kw is None) != (self.power_kw is None)
                or (
                    power_kw is not None
                    and self.power_kw is not None
                    and abs(power_kw - self.power_kw) >= 0.1
                )
            )
            if moved:
                self.level, self.power_kw = level, power_kw
        if decision.shed or decision.restore or moved:
            async_dispatcher_send(self.hass, signal_update(self.entry_id))

    # --- Service calls ----------------------------------------------------

    async def _call(self, domain: str, service: str, entity_id: str, **data: Any) -> None:
        try:
            await self.hass.services.async_call(
                domain, service, {"entity_id": entity_id, **data}, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Load shedding: %s.%s on %s failed: %s", domain, service, entity_id, err
            )

    async def _set_mode(self, appliance: Appliance, mode: str | None) -> None:
        service, field, _ = _MODES[appliance.domain]
        await self._call(appliance.domain, service, appliance.entity_id, **{field: mode})

    async def _notify(self, appliance: Appliance, key: str, until: datetime | None) -> None:
        if not appliance.notify:
            return
        texts = _TEXTS.get(self.hass.config.language.split("-")[0], _TEXTS["en"])
        local = dt_util.as_local(until).strftime("%H:%M") if until else texts["until_power"]
        message = texts[key].format(name=appliance.name, until=local)
        domain, service = appliance.notify.split(".", 1)
        try:
            await self.hass.services.async_call(
                domain, service, {"title": texts["title"], "message": message}, blocking=True
            )
        except HomeAssistantError as err:
            _LOGGER.warning("Load shedding: cannot notify with %s: %s", appliance.notify, err)

    # --- Storage ----------------------------------------------------------

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 1)

    def _data(self) -> dict[str, Any]:
        return {
            "appliances": [a.to_dict() for a in self.appliances.values()],
            "states": {k: s.to_dict() for k, s in self.states.items() if s.shed},
            "announced": {d.isoformat(): str(c) for d, c in self._announced.items()},
            "power": self.power.to_dict(),
        }

    def status(self, appliance_id: str) -> ShedState:
        return self.states.get(appliance_id) or ShedState()

    def watched(self, appliance_id: str) -> bool:
        """An alert-only appliance in its period: nothing is shed, it is watched."""
        appliance = self.appliances.get(appliance_id)
        return (
            appliance is not None
            and appliance.behaviour is Behaviour.ALERT
            and self.status(appliance_id).shed
        )

    def is_shed(self, appliance_id: str) -> bool:
        """Shed for real: an alert-only appliance never is."""
        return self.status(appliance_id).shed and not self.watched(appliance_id)

    def as_list(self) -> list[dict[str, Any]]:
        """The appliances with where they stand, for the API and the panel."""
        return [
            {
                **a.to_dict(),
                "status": {
                    **self.status(a.id).to_dict(),
                    "shed": self.is_shed(a.id),
                    "watched": self.watched(a.id),
                },
            }
            for a in sorted(self.appliances.values(), key=lambda a: (a.priority, a.name))
        ]


def _schedules_of(appliance: Appliance) -> tuple:
    return (
        appliance.schedule_blue,
        appliance.schedule_white,
        appliance.schedule_red,
        appliance.normal_option,
        appliance.enabled,
    )


def _drives_otherwise(old: Appliance, new: Appliance) -> bool:
    """Whether a change of settings changes what a shedding in progress does."""
    return (old.entity_id, old.behaviour, old.reduced_option) != (
        new.entity_id,
        new.behaviour,
        new.reduced_option,
    )


def _missing(state: State | None) -> bool:
    return state is None or state.state in _MISSING


def _on_off(state: State) -> str:
    return "off" if state.state == STATE_OFF else "on"


def _mode(appliance: Appliance, state: State | None) -> str | None:
    if _missing(state):
        return None
    _, _, attribute = _MODES.get(appliance.domain, (None, None, None))
    return state.attributes.get(attribute) if attribute else state.state
