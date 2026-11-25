"""Load shedding: which appliances to shed, and until when.

Pure Python, no Home Assistant import: everything here can be tested on its own.

An appliance is shed by tariff when the current Tempo day has one of its colours:
during the peak hours only, or for the whole Tempo day (06:00 to 06:00).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta
from enum import StrEnum
from typing import Any

from .planner import Color, price_key


class Behaviour(StrEnum):
    """What shedding does to an appliance."""

    # Turned off, and back on afterwards if it was on.
    OFF = "off"
    # An option, preset or operation mode forced, the previous one restored afterwards.
    REDUCED = "reduced"
    # Nothing can be driven: a notification when it runs while shed.
    ALERT = "alert"


class Hours(StrEnum):
    """When a tariff shedding applies on a day of the appliance's colours."""

    PEAK = "peak"
    DAY = "day"


class ShedReason(StrEnum):
    """Why an appliance is shed."""

    TARIFF = "tariff"
    POWER = "power"


class PowerLevel(StrEnum):
    """How hard the house is shedding by power."""

    NONE = "none"
    SOFT = "soft"
    HARD = "hard"


# Domains each behaviour can drive.
OFF_DOMAINS = frozenset(
    {
        "light",
        "switch",
        "fan",
        "input_boolean",
        "climate",
        "water_heater",
        "humidifier",
        "media_player",
    }
)
REDUCED_DOMAINS = frozenset({"select", "input_select", "climate", "water_heater"})


@dataclass(frozen=True)
class Appliance:
    """An appliance the planner may shed."""

    id: str
    name: str
    entity_id: str
    behaviour: Behaviour = Behaviour.OFF
    # Forced while shed, for the reduced behaviour: an option, preset or operation mode.
    reduced_option: str | None = None
    # Tells when the appliance runs, for the alert behaviour; the entity itself without it.
    running_entity: str | None = None
    # A numeric state (a power, in W) above this means running.
    running_above: float = 50.0
    # Otherwise, these states mean running.
    running_states: tuple[str, ...] = ("on",)
    colors: frozenset[Color] = field(default_factory=lambda: frozenset({Color.RED}))
    hours: Hours = Hours.PEAK
    # A notify service, e.g. "notify.mobile_app_phone".
    notify: str | None = None
    # Shed first when low; used by the power trigger.
    priority: int = 0
    # The appliance's own power: a sensor, or a declared value.
    power_entity: str | None = None
    power_kw: float | None = None
    enabled: bool = True
    # A schedule per colour: on while it is on, off (or reduced) otherwise.
    schedule_blue: str | None = None
    schedule_white: str | None = None
    schedule_red: str | None = None
    # The mode while a schedule is on, for the reduced behaviour.
    normal_option: str | None = None
    # Shed by power above the hard limit only (stopping it costs, like a car's charge).
    hard_only: bool = False

    @property
    def domain(self) -> str:
        return self.entity_id.split(".", 1)[0]

    def schedule_for(self, color: Color) -> str | None:
        """The schedule the appliance follows on a day of this colour."""
        return {
            Color.BLUE: self.schedule_blue,
            Color.WHITE: self.schedule_white,
            Color.RED: self.schedule_red,
        }.get(color)

    @property
    def schedules(self) -> list[str]:
        return [s for s in (self.schedule_blue, self.schedule_white, self.schedule_red) if s]

    @property
    def watched_entity(self) -> str:
        """The entity whose changes matter while shed."""
        if self.behaviour is Behaviour.ALERT and self.running_entity:
            return self.running_entity
        return self.entity_id

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["behaviour"] = str(self.behaviour)
        data["hours"] = str(self.hours)
        data["colors"] = sorted(str(c) for c in self.colors)
        data["running_states"] = list(self.running_states)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Appliance:
        default = cls(id="", name="", entity_id="")
        return cls(
            id=data["id"],
            name=data["name"],
            entity_id=data["entity_id"],
            behaviour=Behaviour(data.get("behaviour", default.behaviour)),
            reduced_option=data.get("reduced_option"),
            running_entity=data.get("running_entity"),
            running_above=float(data.get("running_above", default.running_above)),
            running_states=tuple(data.get("running_states", default.running_states)),
            colors=frozenset(Color(c) for c in data.get("colors", ("red",))),
            hours=Hours(data.get("hours", default.hours)),
            notify=data.get("notify"),
            priority=int(data.get("priority", default.priority)),
            power_entity=data.get("power_entity"),
            power_kw=data.get("power_kw"),
            enabled=bool(data.get("enabled", True)),
            schedule_blue=data.get("schedule_blue"),
            schedule_white=data.get("schedule_white"),
            schedule_red=data.get("schedule_red"),
            normal_option=data.get("normal_option"),
            hard_only=bool(data.get("hard_only", False)),
        )


def problems(appliance: Appliance) -> list[str]:
    """What prevents an appliance from working, as translation keys."""
    found = []
    if appliance.behaviour is Behaviour.OFF and appliance.domain not in OFF_DOMAINS:
        found.append("domain_cannot_turn_off")
    if appliance.behaviour is Behaviour.REDUCED:
        if appliance.domain not in REDUCED_DOMAINS:
            found.append("domain_has_no_mode")
        if not appliance.reduced_option:
            found.append("reduced_option_missing")
    if appliance.notify and not appliance.notify.startswith("notify."):
        found.append("notify_not_a_notify_service")
    if appliance.schedules:
        if appliance.behaviour is Behaviour.ALERT:
            found.append("alert_has_no_schedule")
        if appliance.behaviour is Behaviour.REDUCED and not appliance.normal_option:
            found.append("normal_option_missing")
        if any(not s.startswith("schedule.") for s in appliance.schedules):
            found.append("schedule_not_a_schedule")
    if not appliance.colors:
        found.append("no_color")
    return found


def tariff_until(
    appliance: Appliance,
    now: datetime,
    color: Color,
    offpeak_start: time,
    offpeak_end: time,
) -> datetime | None:
    """End of the tariff shedding in progress; None when the appliance is not shed.

    `color` is the colour of the Tempo day in progress, which changes at the end
    of the off-peak hours.
    """
    if not appliance.enabled or color not in appliance.colors:
        return None
    clock = now.time()
    if appliance.hours is Hours.PEAK:
        if offpeak_end <= clock < offpeak_start:
            return datetime.combine(now.date(), offpeak_start, now.tzinfo)
        return None
    # The whole Tempo day: until it ends, at the end of the off-peak hours.
    day = now.date() if clock < offpeak_end else now.date() + timedelta(days=1)
    return datetime.combine(day, offpeak_end, now.tzinfo)


def is_running(appliance: Appliance, state: str | None) -> bool:
    """Whether the state of the running entity says the appliance runs."""
    if state is None:
        return False
    try:
        return float(state) > appliance.running_above
    except ValueError:
        return state in appliance.running_states


def current_color(
    entity_color: Color,
    entity_updated: datetime | None,
    announced: Color | None,
    day_start: datetime,
) -> Color:
    """Colour of the Tempo day in progress.

    The current colour entity switches a few seconds after the day starts: until
    it has been updated since `day_start`, the colour announced the day before
    for this day wins.
    """
    stale = entity_updated is None or entity_updated < day_start
    if stale and announced is not None and announced is not Color.UNKNOWN:
        return announced
    return entity_color


def scheduled_state(appliance: Appliance, schedule_on: bool) -> str | None:
    """What a schedule asks of an appliance: "on"/"off", or a mode."""
    if appliance.behaviour is Behaviour.OFF:
        return "on" if schedule_on else "off"
    if appliance.behaviour is Behaviour.REDUCED:
        return appliance.normal_option if schedule_on else appliance.reduced_option
    return None


@dataclass(frozen=True)
class PowerSettings:
    """Load shedding by power: what to read and the limits to keep under."""

    enabled: bool = False
    # The power drawn from the grid, in W or kW.
    power_entity: str | None = None
    # Not above, if possible: shed gently, one appliance at a time.
    soft_limit_kw: float | None = None
    # Never for long: shed fast, as many as needed.
    hard_limit_kw: float | None = None
    # The soft limit by colour and period, keyed like the prices ("red_peak").
    soft_limits: dict[str, float] = field(default_factory=dict)
    # An appliance comes back only this far under the soft limit, with its own power.
    restore_margin_kw: float = 0.5
    soft_delay_s: int = 120
    hard_delay_s: int = 5
    restore_delay_s: int = 300

    def soft_for(self, color: Color, offpeak: bool) -> float | None:
        override = self.soft_limits.get(price_key(color, offpeak))
        return override if override is not None else self.soft_limit_kw

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PowerSettings:
        default = cls()
        return cls(
            enabled=bool(data.get("enabled", default.enabled)),
            power_entity=data.get("power_entity"),
            soft_limit_kw=_float(data.get("soft_limit_kw")),
            hard_limit_kw=_float(data.get("hard_limit_kw")),
            soft_limits={
                k: float(v) for k, v in (data.get("soft_limits") or {}).items() if v is not None
            },
            restore_margin_kw=float(data.get("restore_margin_kw", default.restore_margin_kw)),
            soft_delay_s=int(data.get("soft_delay_s", default.soft_delay_s)),
            hard_delay_s=int(data.get("hard_delay_s", default.hard_delay_s)),
            restore_delay_s=int(data.get("restore_delay_s", default.restore_delay_s)),
        )


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


@dataclass
class PowerTimers:
    """Since when each condition holds; a shedding step restarts its timer."""

    above_soft: datetime | None = None
    above_hard: datetime | None = None
    below: datetime | None = None
    missing: datetime | None = None


@dataclass(frozen=True)
class Candidate:
    """An appliance that can be shed by power now, with what it draws (None: unknown)."""

    appliance: Appliance
    power_kw: float | None


@dataclass(frozen=True)
class PowerShed:
    """An appliance shed by power, with what it drew then."""

    appliance_id: str
    power_kw: float | None


@dataclass(frozen=True)
class PowerDecision:
    shed: tuple[str, ...] = ()
    restore: tuple[str, ...] = ()


def power_level(power_kw: float | None, soft: float | None, hard: float | None) -> PowerLevel:
    if power_kw is None:
        return PowerLevel.NONE
    if hard is not None and power_kw > hard:
        return PowerLevel.HARD
    if soft is not None and power_kw > soft:
        return PowerLevel.SOFT
    return PowerLevel.NONE


def power_step(
    now: datetime,
    power_kw: float | None,
    soft: float | None,
    hard: float | None,
    settings: PowerSettings,
    timers: PowerTimers,
    shed: list[PowerShed],
    candidates: list[Candidate],
) -> PowerDecision:
    """What to shed or bring back now.

    `shed` is in the order the appliances were shed; `candidates` in the order
    to shed them (lowest priority first). `timers` is updated in place.
    """
    if power_kw is None:
        # No reading: nothing new is shed, and what was shed comes back after a while.
        timers.above_soft = timers.above_hard = timers.below = None
        timers.missing = timers.missing or now
        if shed and _since(now, timers.missing) >= settings.restore_delay_s:
            timers.missing = now
            return PowerDecision(restore=tuple(p.appliance_id for p in reversed(shed)))
        return PowerDecision()
    timers.missing = None
    power_kw = max(power_kw, 0.0)

    if hard is not None and power_kw > hard:
        timers.below = timers.above_soft = None
        timers.above_hard = timers.above_hard or now
        if _since(now, timers.above_hard) < settings.hard_delay_s:
            return PowerDecision()
        timers.above_hard = now
        ids: list[str] = []
        left = power_kw
        for candidate in candidates:
            if left <= hard:
                break
            ids.append(candidate.appliance.id)
            if candidate.power_kw is None:
                # What it frees is unknown: measure again before going on.
                break
            left -= candidate.power_kw
        return PowerDecision(shed=tuple(ids))
    timers.above_hard = None

    if soft is not None and power_kw > soft:
        timers.below = None
        timers.above_soft = timers.above_soft or now
        if _since(now, timers.above_soft) < settings.soft_delay_s:
            return PowerDecision()
        timers.above_soft = now
        gentle = [c for c in candidates if not c.appliance.hard_only]
        return PowerDecision(shed=(gentle[0].appliance.id,) if gentle else ())
    timers.above_soft = None

    ceiling = soft if soft is not None else hard
    if not shed or ceiling is None:
        timers.below = None
        return PowerDecision()
    last = shed[-1]
    if power_kw + (last.power_kw or 0.0) > ceiling - settings.restore_margin_kw:
        timers.below = None
        return PowerDecision()
    timers.below = timers.below or now
    if _since(now, timers.below) < settings.restore_delay_s:
        return PowerDecision()
    timers.below = now
    return PowerDecision(restore=(last.appliance_id,))


def _since(now: datetime, then: datetime) -> float:
    return (now - then).total_seconds()


def to_kw(value: str | None, unit: str | None) -> float | None:
    """A power state in kW; None when it can't be read."""
    if value is None:
        return None
    try:
        number = float(value)
    except ValueError:
        return None
    return number if (unit or "").lower() == "kw" else number / 1000
