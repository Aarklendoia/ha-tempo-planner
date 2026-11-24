"""Compare the plan with what actually happened.

Pure Python, no Home Assistant import, like the planner.

When the off-peak hours start, the plan's forecast for the next Tempo day is
frozen. Once that day is over, it is reviewed against the house meter and the
battery level recorded during the night before it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any

from .planner import Color, Plan, Settings, parse_color

# A rise of the battery level this large during the night means a grid charge.
CHARGED_POINTS = 5.0
# Reviews averaged in the summaries.
SUMMARY_DAYS = 14


class BatteryOutcome(StrEnum):
    """The planner's decision for a night against what the battery did."""

    AGREED_CHARGE = "agreed_charge"
    AGREED_IDLE = "agreed_idle"
    PLANNER_ONLY = "planner_only"
    BATTERY_ONLY = "battery_only"


@dataclass(frozen=True)
class Forecast:
    """What the plan expected for a Tempo day, frozen when its night started."""

    day: date
    color: Color
    peak_load_kwh: float
    battery_charge: bool
    battery_target_pct: float | None

    @classmethod
    def from_plan(cls, plan: Plan) -> Forecast:
        return cls(
            day=plan.night_end.date(),
            color=plan.tomorrow,
            peak_load_kwh=plan.peak_load_kwh,
            battery_charge=plan.battery is not None,
            battery_target_pct=plan.battery_target_pct,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "color": str(self.color),
            "peak_load_kwh": self.peak_load_kwh,
            "battery_charge": self.battery_charge,
            "battery_target_pct": self.battery_target_pct,
        }

    @classmethod
    def from_dict(cls, day: date, data: dict[str, Any]) -> Forecast:
        return cls(
            day=day,
            color=parse_color(data.get("color")),
            peak_load_kwh=data["peak_load_kwh"],
            battery_charge=data["battery_charge"],
            battery_target_pct=data.get("battery_target_pct"),
        )


@dataclass(frozen=True)
class DayReview:
    """A Tempo day once over: the forecast and what was measured."""

    day: date
    color: Color = Color.UNKNOWN
    forecast_kwh: float | None = None
    actual_kwh: float | None = None
    planned_charge: bool | None = None
    # Battery level during the night before the day, %.
    soc_start: float | None = None
    soc_max: float | None = None
    soc_end: float | None = None

    @property
    def error_kwh(self) -> float | None:
        """Forecast minus measured: positive when the forecast was too high."""
        if self.forecast_kwh is None or self.actual_kwh is None:
            return None
        return round(self.forecast_kwh - self.actual_kwh, 2)

    @property
    def battery_charged(self) -> bool | None:
        if self.soc_start is None or self.soc_max is None:
            return None
        return self.soc_max - self.soc_start >= CHARGED_POINTS

    @property
    def battery_outcome(self) -> BatteryOutcome | None:
        charged = self.battery_charged
        if self.planned_charge is None or charged is None:
            return None
        if self.planned_charge:
            return BatteryOutcome.AGREED_CHARGE if charged else BatteryOutcome.PLANNER_ONLY
        return BatteryOutcome.BATTERY_ONLY if charged else BatteryOutcome.AGREED_IDLE

    def to_dict(self) -> dict[str, Any]:
        return {
            "color": str(self.color),
            "forecast_kwh": self.forecast_kwh,
            "actual_kwh": self.actual_kwh,
            "planned_charge": self.planned_charge,
            "soc_start": self.soc_start,
            "soc_max": self.soc_max,
            "soc_end": self.soc_end,
        }

    @classmethod
    def from_dict(cls, day: date, data: dict[str, Any]) -> DayReview:
        return cls(
            day=day,
            color=parse_color(data.get("color")),
            forecast_kwh=data.get("forecast_kwh"),
            actual_kwh=data.get("actual_kwh"),
            planned_charge=data.get("planned_charge"),
            soc_start=data.get("soc_start"),
            soc_max=data.get("soc_max"),
            soc_end=data.get("soc_end"),
        )


@dataclass(frozen=True)
class Summary:
    """The last reviews at a glance."""

    mean_abs_error_kwh: float | None = None
    error_days: int = 0
    agreement_pct: float | None = None
    nights: int = 0


def night_before(day: date, settings: Settings, tz: Any) -> tuple[datetime, datetime]:
    """The off-peak hours that end on the morning of a Tempo day."""
    return (
        datetime.combine(day - timedelta(days=1), settings.offpeak_start, tz),
        datetime.combine(day, settings.offpeak_end, tz),
    )


def soc_during(
    samples: list[tuple[datetime, float]], start: datetime, end: datetime
) -> tuple[float | None, float | None, float | None]:
    """Battery level at the start of a night, at its highest and at its end.

    `samples` are the recorded levels in time order, the last one before the
    start included.
    """
    before = [soc for at, soc in samples if at <= start]
    during = [soc for at, soc in samples if start < at <= end]
    first = before[-1] if before else (during[0] if during else None)
    if first is None:
        return None, None, None
    return first, max([first, *during]), during[-1] if during else first


def review_day(
    day: date,
    forecast: Forecast | None,
    actual_kwh: float | None,
    soc: tuple[float | None, float | None, float | None],
    color: Color | None,
) -> DayReview | None:
    """Review a Tempo day; None when nothing is known about it."""
    soc_start, soc_max, soc_end = soc
    if forecast is None and actual_kwh is None and soc_start is None:
        return None
    return DayReview(
        day=day,
        color=color or (forecast.color if forecast else Color.UNKNOWN),
        forecast_kwh=forecast.peak_load_kwh if forecast else None,
        actual_kwh=None if actual_kwh is None else round(actual_kwh, 2),
        planned_charge=forecast.battery_charge if forecast else None,
        soc_start=soc_start,
        soc_max=soc_max,
        soc_end=soc_end,
    )


def summarize(reviews: list[DayReview], days: int = SUMMARY_DAYS) -> Summary:
    """Mean forecast error and agreement with the battery, over the last reviews."""
    recent = sorted(reviews, key=lambda r: r.day, reverse=True)
    errors = [e for r in recent if (e := r.error_kwh) is not None][:days]
    outcomes = [o for r in recent if (o := r.battery_outcome) is not None][:days]
    agreed = sum(o in (BatteryOutcome.AGREED_CHARGE, BatteryOutcome.AGREED_IDLE) for o in outcomes)
    return Summary(
        mean_abs_error_kwh=round(sum(abs(e) for e in errors) / len(errors), 2) if errors else None,
        error_days=len(errors),
        agreement_pct=round(100 * agreed / len(outcomes)) if outcomes else None,
        nights=len(outcomes),
    )
