"""Tests of the review alone (no Home Assistant needed)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.tempo_planner.planner import Color, Inputs, Settings, make_plan
from custom_components.tempo_planner.review import (
    BatteryOutcome,
    CarNight,
    DayReview,
    Forecast,
    car_night,
    charging_span,
    night_before,
    review_day,
    soc_during,
    summarize,
)

PARIS = ZoneInfo("Europe/Paris")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=PARIS)


def test_night_before_a_day():
    assert night_before(date(2026, 11, 23), Settings(), PARIS) == (at(22, 22), at(23, 6))


def test_battery_level_during_the_night():
    start, end = at(22, 22), at(23, 6)
    samples = [(at(22, 18), 30.0), (at(22, 23), 25.0), (at(23, 2), 70.0), (at(23, 5), 68.0)]
    assert soc_during(samples, start, end) == (30.0, 70.0, 68.0)
    # Nothing recorded during the night: the level stayed put.
    assert soc_during([(at(22, 18), 30.0)], start, end) == (30.0, 30.0, 30.0)
    assert soc_during([], start, end) == (None, None, None)
    # Nothing before the night: its first value stands for the start.
    assert soc_during([(at(23, 1), 40.0)], start, end) == (40.0, 40.0, 40.0)


@pytest.mark.parametrize(
    ("planned", "soc_max", "outcome"),
    [
        (True, 60, BatteryOutcome.AGREED_CHARGE),
        (True, 12, BatteryOutcome.PLANNER_ONLY),
        (False, 12, BatteryOutcome.AGREED_IDLE),
        (False, 60, BatteryOutcome.BATTERY_ONLY),
        (None, 60, None),
    ],
)
def test_battery_outcome(planned, soc_max, outcome):
    review = DayReview(
        day=date(2026, 11, 23), planned_charge=planned, soc_start=10, soc_max=soc_max
    )
    assert review.battery_outcome is outcome


def test_review_day():
    forecast = Forecast(date(2026, 11, 23), Color.WHITE, 12.0, True, 95)
    review = review_day(date(2026, 11, 23), forecast, 14.5, (10, 80, 75), None)
    # Forecast 2.5 kWh too low.
    assert review.error_kwh == -2.5
    assert review.color is Color.WHITE
    assert review.battery_outcome is BatteryOutcome.AGREED_CHARGE
    assert review_day(date(2026, 11, 23), None, None, (None, None, None), None) is None
    # Without a forecast, the measure is still kept.
    alone = review_day(date(2026, 11, 23), None, 9.0, (None, None, None), Color.BLUE)
    assert (alone.actual_kwh, alone.error_kwh, alone.color) == (9.0, None, Color.BLUE)


def test_summary():
    reviews = [
        DayReview(day=date(2026, 11, d), forecast_kwh=10, actual_kwh=10 + err)
        for d, err in ((20, 2), (21, -1), (22, 3))
    ] + [
        DayReview(day=date(2026, 11, 23), planned_charge=True, soc_start=10, soc_max=80),
        DayReview(day=date(2026, 11, 24), planned_charge=False, soc_start=10, soc_max=80),
    ]
    summary = summarize(reviews)
    assert summary.mean_abs_error_kwh == 2.0
    assert summary.error_days == 3
    assert (summary.agreement_pct, summary.nights) == (50, 2)
    # Only the most recent days count.
    assert summarize(reviews, days=1).mean_abs_error_kwh == 3.0
    assert summarize([]).agreement_pct is None


def test_forecast_from_a_plan_and_back():
    plan = make_plan(
        Inputs(now=at(22, 16), today=Color.BLUE, tomorrow=Color.WHITE, battery_soc=5),
        Settings(),
    )
    forecast = Forecast.from_plan(plan)
    assert forecast.day == date(2026, 11, 23)
    assert forecast.color is Color.WHITE
    assert forecast.battery_charge is True
    assert Forecast.from_dict(forecast.day, forecast.to_dict()) == forecast
    review = review_day(forecast.day, forecast, 9.0, (5, 60, 55), Color.WHITE)
    assert DayReview.from_dict(review.day, review.to_dict()) == review


def test_charging_span():
    start, end = at(22, 22), at(23, 6)
    # The car's program: from 22:00 to 22:42.
    samples = [(at(22, 18), False), (at(22, 22), True), (at(22, 22, 42), False)]
    assert charging_span(samples, start, end) == (at(22, 22), at(22, 22, 42))
    # Two sessions: first start, last stop.
    samples += [(at(23, 3), True), (at(23, 3, 30), False)]
    assert charging_span(samples, start, end) == (at(22, 22), at(23, 3, 30))
    # Already charging at the start, still charging at the end.
    assert charging_span([(at(22, 21), True)], start, end) == (start, end)
    # Plugged in all night but never charging.
    assert charging_span([(at(22, 18), False)], start, end) == (None, None)


def test_car_night():
    start, end = at(22, 22), at(23, 6)
    night = car_night(
        [(at(22, 22), True), (at(22, 22, 42), False)],
        [(at(22, 18), 75.0), (at(22, 22, 43), 80.0)],
        start,
        end,
        Settings(car_capacity_kwh=87, car_efficiency=0.9),
    )
    # 5 % of 87 kWh stored, 4.83 kWh from the grid.
    assert night == CarNight(at(22, 22), at(22, 22, 42), 75.0, 80.0, 4.83)
    assert car_night([], [], start, end, Settings()) is None


def test_car_review_against_the_plan():
    forecast = Forecast(
        date(2026, 11, 23), Color.WHITE, 12.0, False, 5, at(22, 22), at(22, 22, 40), 4.5
    )
    car = CarNight(at(22, 22, 25), at(22, 22, 50), 77.0, 80.0, 2.9)
    review = review_day(date(2026, 11, 23), forecast, None, (None, None, None), None, car)
    assert review.car_start_offset_min == 25
    assert review.car_planned_kwh == 4.5
    assert DayReview.from_dict(review.day, review.to_dict()) == review
    assert Forecast.from_dict(forecast.day, forecast.to_dict()) == forecast
