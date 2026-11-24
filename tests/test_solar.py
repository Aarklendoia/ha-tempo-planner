"""Tests of the solar window alone (no Home Assistant needed)."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.tempo_planner.planner import Color, Inputs, Reason, Settings, make_plan
from custom_components.tempo_planner.solar import (
    House,
    hourly_profile,
    min_surplus_share,
    solar_window,
    sold_per_hour,
)

PARIS = ZoneInfo("Europe/Paris")
HOUSE = House(
    inverter_kw=6.0,
    battery_capacity_kwh=10.0,
    battery_reserve_pct=5.0,
    battery_charge_kw=5.0,
    car_charge_kw=7.4,
)


def at(day: int, hour: int) -> datetime:
    return datetime(2026, 6, day, hour, tzinfo=PARIS)


def sunny(day: int, kwh: dict[int, float]) -> dict[datetime, float]:
    # Outside the given hours, the sun just covers the house: the battery stays put.
    return {at(day, h): kwh.get(h, 0.5) for h in range(6, 22)}


FLAT_LOAD = {h: 0.5 for h in range(24)}


@pytest.mark.parametrize(
    ("peak", "offpeak", "share"),
    [
        (0.1654, 0.1356, 0.238),  # blue
        (0.1921, 0.1536, 0.253),  # white
        (0.73, 0.1611, 0.824),  # red
        (0.15, 0.16, 0.0),  # night dearer: any surplus helps
    ],
)
def test_min_surplus_share(peak, offpeak, share):
    assert min_surplus_share(peak, offpeak, 0.04) == pytest.approx(share, abs=0.001)


def test_the_battery_takes_the_surplus_first():
    # Half full: 5 kWh of room, 5 kW at most.
    sold = sold_per_hour(sunny(10, {10: 4.0, 11: 4.0, 12: 4.0}), FLAT_LOAD, 50, HOUSE)
    # 10:00: 3.5 kWh to the battery; 11:00: the last 1.5 kWh, 2 kWh sold; then 3.5.
    assert sold[at(10, 10)] == 0
    assert sold[at(10, 11)] == pytest.approx(2.0)
    assert sold[at(10, 12)] == pytest.approx(3.5)


def test_the_inverter_caps_what_reaches_the_grid():
    sold = sold_per_hour(sunny(10, {12: 7.0}), FLAT_LOAD, 100, HOUSE)
    assert sold[at(10, 12)] == pytest.approx(5.5)


def test_summer_window_on_a_blue_day():
    solar = sunny(10, {10: 3.0, 11: 4.5, 12: 4.8, 13: 4.6, 14: 4.0, 15: 2.0})
    window = solar_window(solar, FLAT_LOAD, 100, 20.0, 0.1654, 0.1356, 0.04, HOUSE)
    # Needs 24 % of 7.4 kW, 1.76 kWh an hour: from 10:00 (2.5 sold) to 15:00 (1.5: no).
    assert window.start == at(10, 10)
    assert window.end == at(10, 15)
    # Five hours at 7.4 kW, but the car only has room for 20 kWh.
    assert window.car_kwh == 20.0
    assert window.sold_kwh == pytest.approx(2.5 + 4.0 + 4.3 + 4.1 + 3.5 + 1.5)


def test_no_window_on_a_red_day_or_in_winter():
    summer = sunny(10, {12: 4.8})
    red = solar_window(summer, FLAT_LOAD, 100, 20.0, 0.73, 0.1611, 0.04, HOUSE)
    assert red.start is None and red.car_kwh == 0
    winter = sunny(10, {12: 1.0})
    blue = solar_window(winter, FLAT_LOAD, 100, 20.0, 0.1654, 0.1356, 0.04, HOUSE)
    assert blue.start is None


def test_hourly_profile():
    hours = [(at(d, h), 0.4 + d / 100) for d in (8, 9, 10) for h in range(24)]
    profile = hourly_profile(hours, days=2)
    # The last two days: 0.49 and 0.50.
    assert profile[12] == pytest.approx(0.495)
    assert len(profile) == 24


def test_plan_advises_a_solar_charge():
    plan = make_plan(
        Inputs(
            now=at(9, 16),
            today=Color.BLUE,
            tomorrow=Color.BLUE,
            battery_soc=100,
            car_soc=60,
            solar_hours=sunny(10, {11: 4.5, 12: 4.8, 13: 4.6}),
            load_profile=FLAT_LOAD,
        ),
        Settings(battery_capacity_kwh=10, battery_charge_kw=5, car_capacity_kwh=87),
    )
    assert plan.solar.start == at(10, 11)
    assert plan.solar.car_kwh > 0
    assert Reason.SOLAR_CAR in plan.reasons


def test_no_solar_window_without_an_hourly_forecast():
    plan = make_plan(Inputs(now=at(9, 16), tomorrow=Color.BLUE), Settings())
    assert plan.solar is None


def test_morning_use_makes_room_in_the_battery():
    # Full at 06:00, no sun until 10:00: 2 kWh used from the battery, taken
    # back from the first surplus before anything is sold.
    solar = {at(10, h): 0.0 for h in range(6, 10)} | {at(10, 10): 3.0}
    sold = sold_per_hour(solar, FLAT_LOAD, 100, HOUSE)
    assert sold[at(10, 10)] == pytest.approx(0.5)
