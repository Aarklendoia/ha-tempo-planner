"""Night planner for the EDF Tempo tariff.

Pure Python, no Home Assistant import: everything here can be tested on its own.

A Tempo day runs from 06:00 to 06:00. Its off-peak hours are 22:00-06:00, at
the end of the day, so the night before a Tempo day is still priced at the
previous day's off-peak rate. The plan is made for the next night and for the
Tempo day that follows it ("tomorrow").
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .review import DayReview, Summary


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


# EDF Tempo prices in EUR/kWh, used when no price entity is chosen.
DEFAULT_PRICES: dict[str, float] = {
    "blue_offpeak": 0.1356,
    "blue_peak": 0.1654,
    "white_offpeak": 0.1536,
    "white_peak": 0.1921,
    "red_offpeak": 0.1611,
    "red_peak": 0.7300,
}


def price_key(color: Color, offpeak: bool) -> str:
    """Key of a price in DEFAULT_PRICES; an unknown colour is priced as white."""
    if color is Color.UNKNOWN:
        color = Color.WHITE
    return f"{color}_{'offpeak' if offpeak else 'peak'}"


def parse_color(value: str | None) -> Color:
    """Read a colour as the Tempo integrations write it (French or English)."""
    if not value:
        return Color.UNKNOWN
    return _COLOR_NAMES.get(value.strip().lower(), Color.UNKNOWN)


class Reason(StrEnum):
    """Why the plan looks the way it does; shown as attributes."""

    COLOR_UNKNOWN = "color_unknown"
    BATTERY_SOLAR_COVERS = "battery_solar_covers"
    BATTERY_NOT_WORTH = "battery_not_worth"
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
    # A grid charge must save at least this much per kWh given back by the
    # battery, after its losses: what a cycle costs in wear.
    battery_min_gain_eur_kwh: float = 0.03
    # House consumption between 06:00 and 22:00, before solar, when no
    # history is available.
    peak_load_kwh: float = 11.5
    # Days of history averaged to learn the peak-hour consumption.
    peak_load_days: int = 14
    # Fewer days of tomorrow's colour than this: average the recent days instead.
    peak_load_min_color_days: int = 3

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
class PeakLoad:
    """Peak-hour consumption learnt from history."""

    kwh: float
    days: int
    # The colour whose days were averaged; None: the most recent days, any colour.
    color: Color | None = None


def tempo_day(now: datetime, settings: Settings) -> date:
    """The Tempo day in progress: it starts at the end of the off-peak hours."""
    if now.time() < settings.offpeak_end:
        return now.date() - timedelta(days=1)
    return now.date()


def peak_totals(hours: list[tuple[datetime, float]], settings: Settings) -> dict[date, float]:
    """Peak-hour consumption of each day whose every peak hour is known.

    `hours` holds the start of each hour, in local time, and the energy the house
    used during it.
    """
    per_day: dict[date, list[float]] = defaultdict(list)
    for start, kwh in hours:
        if settings.offpeak_end <= start.time() < settings.offpeak_start:
            per_day[start.date()].append(kwh)
    peak_hours = (
        datetime.combine(date.min, settings.offpeak_start)
        - datetime.combine(date.min, settings.offpeak_end)
    ) // timedelta(hours=1)
    return {day: sum(v) for day, v in per_day.items() if len(v) == peak_hours}


def peak_load_from_history(
    hours: list[tuple[datetime, float]],
    settings: Settings,
    colors: dict[date, Color] | None = None,
    color: Color | None = None,
) -> PeakLoad | None:
    """Average peak-hour consumption of past days whose every peak hour is known.

    With the colour of past days, the most recent days of `color`
    are averaged, when there are enough of them; otherwise the most recent days.
    """
    totals = peak_totals(hours, settings)
    recent = sorted(totals, reverse=True)
    if not recent:
        return None

    if color is not None and colors:
        wanted = Color.WHITE if color is Color.UNKNOWN else color
        same = [d for d in recent if colors.get(d) is wanted][: settings.peak_load_days]
        if len(same) >= settings.peak_load_min_color_days:
            return _average(totals, same, wanted)
    return _average(totals, recent[: settings.peak_load_days], None)


def _average(totals: dict[date, float], days: list[date], color: Color | None) -> PeakLoad:
    kwh = sum(totals[d] for d in days) / len(days)
    return PeakLoad(kwh=round(kwh, 2), days=len(days), color=color)


@dataclass(frozen=True)
class Inputs:
    """The state of the house when the plan is made."""

    now: datetime
    tomorrow: Color
    # The Tempo day the next night belongs to: its off-peak price pays the charge.
    today: Color = Color.UNKNOWN
    # Prices read from entities, keyed like DEFAULT_PRICES; missing ones use the defaults.
    prices: dict[str, float] = field(default_factory=dict)
    # Learnt from history; the setting applies without it.
    peak_load: PeakLoad | None = None
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
    # House consumption expected during tomorrow's peak hours, and the number
    # of days of history behind it (None: the setting).
    peak_load_kwh: float = 0.0
    peak_load_days: int | None = None
    peak_load_color: Color | None = None
    battery_target_pct: float | None = None
    battery_grid_kwh: float = 0.0
    battery: Slot | None = None
    # Saving per kWh given back by the battery tomorrow, after its losses.
    battery_gain_eur_kwh: float | None = None
    offpeak_price: float | None = None
    peak_price: float | None = None
    car_energy_kwh: float = 0.0
    car: Slot | None = None
    dishwasher: Slot | None = None
    dishwasher_mode: str | None = None
    peak_kw: float = 0.0
    reasons: list[Reason] = field(default_factory=list)
    # The last Tempo day reviewed, and the last reviews at a glance; filled in
    # by the coordinator.
    review: DayReview | None = None
    summary: Summary | None = None


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


def _price(inputs: Inputs, color: Color, offpeak: bool) -> float:
    key = price_key(color, offpeak)
    return inputs.prices.get(key, DEFAULT_PRICES[key])


def _plan_battery(plan: Plan, inputs: Inputs, settings: Settings) -> None:
    capacity = settings.battery_capacity_kwh
    solar = inputs.solar_tomorrow_kwh or 0.0
    if inputs.peak_load is not None:
        plan.peak_load_kwh = inputs.peak_load.kwh
        plan.peak_load_days = inputs.peak_load.days
        plan.peak_load_color = inputs.peak_load.color
    else:
        plan.peak_load_kwh = settings.peak_load_kwh
    need_kwh = max(0.0, plan.peak_load_kwh - solar)

    # The night is billed at today's off-peak price and replaces tomorrow's peak hours.
    plan.offpeak_price = _price(inputs, inputs.today, offpeak=True)
    plan.peak_price = _price(inputs, plan.tomorrow, offpeak=False)
    gain = plan.peak_price - plan.offpeak_price / settings.battery_efficiency
    plan.battery_gain_eur_kwh = round(gain, 4)

    if need_kwh == 0:
        target = settings.battery_reserve_pct
        plan.reasons.append(Reason.BATTERY_SOLAR_COVERS)
    elif gain < settings.battery_min_gain_eur_kwh:
        target = settings.battery_reserve_pct
        plan.reasons.append(Reason.BATTERY_NOT_WORTH)
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
