"""Night planner for the EDF Tempo tariff.

Pure Python, no Home Assistant import: everything here can be tested on its own.

A Tempo day runs from 06:00 to 06:00. Its off-peak hours are 22:00-06:00, at
the end of the day, so the night before a Tempo day is still priced at the
previous day's off-peak rate. The plan is made for the next night and for the
Tempo day that follows it ("tomorrow").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import StrEnum


class Color(StrEnum):
    """Colour of a Tempo day."""

    BLUE = "blue"
    WHITE = "white"
    RED = "red"
    UNKNOWN = "unknown"


_COLOR_NAMES = {
    "blue": Color.BLUE,
    "bleu": Color.BLUE,
    "white": Color.WHITE,
    "blanc": Color.WHITE,
    "red": Color.RED,
    "rouge": Color.RED,
}


def parse_color(value: str | None) -> Color:
    """Read a colour as the Tempo integrations write it (French or English)."""
    if not value:
        return Color.UNKNOWN
    return _COLOR_NAMES.get(value.strip().lower(), Color.UNKNOWN)


class Reason(StrEnum):
    """Why the plan looks the way it does; shown as attributes."""

    COLOR_UNKNOWN = "color_unknown"
    BATTERY_SOLAR_COVERS = "battery_solar_covers"
    BATTERY_BLUE_NO_GRID = "battery_blue_no_grid"
    BATTERY_ALREADY_FULL = "battery_already_full"
    BATTERY_CHARGE = "battery_charge"
    BATTERY_UNKNOWN_SOC = "battery_unknown_soc"
    CAR_FULL = "car_full"
    CAR_BELOW_MINIMUM = "car_below_minimum"
    CAR_UNKNOWN_SOC = "car_unknown_soc"
    CAR_NOT_PLUGGED = "car_not_plugged"
    CAR_OVERFLOWS_OFFPEAK = "car_overflows_offpeak"
    DISHWASHER_SOLAR = "dishwasher_solar"
    DISHWASHER_NIGHT = "dishwasher_night"
    PEAK_OVER_LIMIT = "peak_over_limit"


@dataclass(frozen=True)
class Settings:
    """What the user tells us about the house."""

    offpeak_start: time = time(22, 0)
    offpeak_end: time = time(6, 0)
    # Grid draw allowed for the planned loads, with what the house keeps for itself.
    max_power_kw: float = 9.0

    battery_capacity_kwh: float = 10.0
    battery_reserve_pct: float = 5.0
    battery_charge_kw: float = 3.0
    battery_efficiency: float = 0.9
    battery_charge_on_blue: bool = False
    # House consumption between 06:00 and 22:00, before solar.
    peak_load_kwh: float = 8.0

    car_capacity_kwh: float = 60.0
    car_charge_kw: float = 7.4
    car_target_pct: float = 80.0
    car_efficiency: float = 0.9
    # Below this, the car is not worth a charging session.
    car_min_kwh: float = 3.0
    car_margin: timedelta = timedelta(minutes=15)

    dishwasher_duration: timedelta = timedelta(hours=5, minutes=10)
    dishwasher_power_kw: float = 2.2
    # A blue day with at least this much solar forecast runs the dishwasher at noon.
    dishwasher_solar_kwh: float = 6.0
    stagger: timedelta = timedelta(minutes=30)


@dataclass(frozen=True)
class Inputs:
    """The state of the house when the plan is made."""

    now: datetime
    tomorrow: Color
    solar_tomorrow_kwh: float | None = None
    solar_peak_tomorrow: datetime | None = None
    battery_soc: float | None = None
    car_soc: float | None = None
    car_plugged: bool | None = None
    car_target_pct: float | None = None


@dataclass(frozen=True)
class Slot:
    """A load planned between two instants."""

    start: datetime
    end: datetime
    power_kw: float

    @property
    def hours(self) -> float:
        return (self.end - self.start).total_seconds() / 3600


@dataclass
class Plan:
    """The plan for the next night and the Tempo day after it."""

    night_start: datetime
    night_end: datetime
    tomorrow: Color
    battery_target_pct: float | None = None
    battery_grid_kwh: float = 0.0
    battery: Slot | None = None
    car_energy_kwh: float = 0.0
    car: Slot | None = None
    dishwasher: Slot | None = None
    dishwasher_mode: str | None = None
    peak_kw: float = 0.0
    reasons: list[Reason] = field(default_factory=list)


def next_night(now: datetime, settings: Settings) -> tuple[datetime, datetime]:
    """The off-peak window in progress, or the next one."""
    today_start = datetime.combine(now.date(), settings.offpeak_start, now.tzinfo)
    today_end = datetime.combine(now.date(), settings.offpeak_end, now.tzinfo)
    if now < today_end:
        # Early morning: the window started yesterday evening.
        return today_start - timedelta(days=1), today_end
    return today_start, today_end + timedelta(days=1)


def make_plan(inputs: Inputs, settings: Settings) -> Plan:
    """Plan the next night."""
    night_start, night_end = next_night(inputs.now, settings)
    plan = Plan(night_start=night_start, night_end=night_end, tomorrow=inputs.tomorrow)
    if inputs.tomorrow is Color.UNKNOWN:
        plan.reasons.append(Reason.COLOR_UNKNOWN)

    _plan_battery(plan, inputs, settings)
    _plan_car(plan, inputs, settings)
    _plan_dishwasher(plan, inputs, settings)
    plan.peak_kw = night_peak(
        [s for s in (plan.battery, plan.car, plan.dishwasher) if s is not None],
        night_start,
        night_end,
    )
    if plan.peak_kw > settings.max_power_kw:
        plan.reasons.append(Reason.PEAK_OVER_LIMIT)
    return plan


def _plan_battery(plan: Plan, inputs: Inputs, settings: Settings) -> None:
    capacity = settings.battery_capacity_kwh
    solar = inputs.solar_tomorrow_kwh or 0.0
    need_kwh = max(0.0, settings.peak_load_kwh - solar)

    if need_kwh == 0:
        target = settings.battery_reserve_pct
        plan.reasons.append(Reason.BATTERY_SOLAR_COVERS)
    elif plan.tomorrow is Color.BLUE and not settings.battery_charge_on_blue:
        target = settings.battery_reserve_pct
        plan.reasons.append(Reason.BATTERY_BLUE_NO_GRID)
    else:
        target = min(100.0, settings.battery_reserve_pct + need_kwh / capacity * 100)
    plan.battery_target_pct = round(target)

    if inputs.battery_soc is None:
        plan.reasons.append(Reason.BATTERY_UNKNOWN_SOC)
        return
    missing_kwh = (target - inputs.battery_soc) / 100 * capacity
    if missing_kwh <= 0:
        if target > settings.battery_reserve_pct:
            plan.reasons.append(Reason.BATTERY_ALREADY_FULL)
        return

    plan.battery_grid_kwh = round(missing_kwh / settings.battery_efficiency, 2)
    plan.reasons.append(Reason.BATTERY_CHARGE)
    duration = timedelta(hours=plan.battery_grid_kwh / settings.battery_charge_kw)
    # First in the night: the car comes last and the dishwasher in between.
    plan.battery = Slot(
        plan.night_start,
        min(plan.night_start + duration, plan.night_end),
        settings.battery_charge_kw,
    )


def _plan_car(plan: Plan, inputs: Inputs, settings: Settings) -> None:
    if inputs.car_soc is None:
        plan.reasons.append(Reason.CAR_UNKNOWN_SOC)
        return
    if inputs.car_plugged is False:
        plan.reasons.append(Reason.CAR_NOT_PLUGGED)
    target = inputs.car_target_pct or settings.car_target_pct
    missing_kwh = (target - inputs.car_soc) / 100 * settings.car_capacity_kwh
    if missing_kwh <= 0:
        plan.reasons.append(Reason.CAR_FULL)
        return

    energy_kwh = round(missing_kwh / settings.car_efficiency, 2)
    if energy_kwh < settings.car_min_kwh:
        plan.reasons.append(Reason.CAR_BELOW_MINIMUM)
        return
    plan.car_energy_kwh = energy_kwh
    duration = timedelta(hours=plan.car_energy_kwh / settings.car_charge_kw)
    # Finish just before the end of the off-peak hours, so the start does not
    # pile up with everything that begins at 22:00.
    end = plan.night_end - settings.car_margin
    start = end - duration
    if start < plan.night_start:
        start = plan.night_start
        end = start + duration
        if end > plan.night_end:
            plan.reasons.append(Reason.CAR_OVERFLOWS_OFFPEAK)
    plan.car = Slot(start, end, settings.car_charge_kw)


def _plan_dishwasher(plan: Plan, inputs: Inputs, settings: Settings) -> None:
    duration = settings.dishwasher_duration
    solar = inputs.solar_tomorrow_kwh or 0.0
    if (
        plan.tomorrow is Color.BLUE
        and solar >= settings.dishwasher_solar_kwh
        and inputs.solar_peak_tomorrow is not None
    ):
        start = inputs.solar_peak_tomorrow - duration / 2
        plan.dishwasher = Slot(start, start + duration, settings.dishwasher_power_kw)
        plan.dishwasher_mode = "solar"
        plan.reasons.append(Reason.DISHWASHER_SOLAR)
        return

    start = plan.night_start + settings.stagger
    if start + duration > plan.night_end:
        start = plan.night_start
    plan.dishwasher = Slot(start, start + duration, settings.dishwasher_power_kw)
    plan.dishwasher_mode = "night"
    plan.reasons.append(Reason.DISHWASHER_NIGHT)


def night_peak(slots: list[Slot], start: datetime, end: datetime) -> float:
    """Highest sum of the planned loads during the night, in kW.

    The dishwasher only draws its full power while heating; counting it over the
    whole programme makes this an upper bound.
    """
    instants = sorted({start, end, *(s.start for s in slots), *(s.end for s in slots)})
    peak = 0.0
    for instant in instants:
        if not start <= instant < end:
            continue
        load = sum(s.power_kw for s in slots if s.start <= instant < s.end)
        peak = max(peak, load)
    return round(peak, 2)
