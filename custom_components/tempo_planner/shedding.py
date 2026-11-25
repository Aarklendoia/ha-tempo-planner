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

from .planner import Color


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

    @property
    def domain(self) -> str:
        return self.entity_id.split(".", 1)[0]

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
