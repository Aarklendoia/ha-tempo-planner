"""Tests of the planner alone (no Home Assistant needed)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.tempo_planner.planner import (
    Color,
    Inputs,
    Reason,
    Settings,
    Slot,
    make_plan,
    next_night,
    night_peak,
    parse_color,
)

PARIS = ZoneInfo("Europe/Paris")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=PARIS)


@pytest.mark.parametrize(
    ("value", "color"),
    [
        ("Bleu", Color.BLUE),
        ("blanc", Color.WHITE),
        (" ROUGE ", Color.RED),
        ("red", Color.RED),
        ("inconnu", Color.UNKNOWN),
        (None, Color.UNKNOWN),
    ],
)
def test_parse_color(value, color):
    assert parse_color(value) is color


def test_next_night():
    s = Settings()
    assert next_night(at(23, 15), s) == (at(23, 22), at(24, 6))
    assert next_night(at(23, 23), s) == (at(23, 22), at(24, 6))
    # Before 06:00 the window started the evening before.
    assert next_night(at(24, 3), s) == (at(23, 22), at(24, 6))
    assert next_night(at(24, 6), s) == (at(24, 22), at(25, 6))


def test_night_before_a_white_day_charges_the_battery_for_peak_hours():
    plan = make_plan(
        Inputs(
            now=at(22, 16),
            today=Color.BLUE,
            tomorrow=Color.WHITE,
            solar_tomorrow_kwh=3,
            battery_soc=20,
        ),
        Settings(peak_load_kwh=8, battery_capacity_kwh=10, battery_reserve_pct=5),
    )
    # 8 kWh needed, 3 from the sun: 5 kWh above the 5 % reserve.
    assert plan.battery_target_pct == 55
    assert plan.battery_grid_kwh == pytest.approx(3.5 / 0.9, abs=0.01)
    assert plan.battery.start == at(22, 22)
    assert Reason.BATTERY_CHARGE in plan.reasons


@pytest.mark.parametrize(
    ("today", "tomorrow", "charges", "gain"),
    [
        # The night is billed at today's off-peak price, after 10 % of losses,
        # and saves tomorrow's peak price.
        (Color.BLUE, Color.WHITE, True, 0.1921 - 0.1356 / 0.9),  # about 4.1 c
        (Color.WHITE, Color.WHITE, False, 0.1921 - 0.1536 / 0.9),  # about 2.1 c
        (Color.BLUE, Color.BLUE, False, 0.1654 - 0.1356 / 0.9),  # about 1.5 c
        (Color.WHITE, Color.BLUE, False, 0.1654 - 0.1536 / 0.9),  # a loss
        (Color.BLUE, Color.RED, True, 0.73 - 0.1356 / 0.9),
        (Color.WHITE, Color.RED, True, 0.73 - 0.1536 / 0.9),
        (Color.RED, Color.RED, True, 0.73 - 0.1611 / 0.9),
        # Unknown colours count as white.
        (Color.UNKNOWN, Color.UNKNOWN, False, 0.1921 - 0.1536 / 0.9),
        (Color.BLUE, Color.UNKNOWN, True, 0.1921 - 0.1356 / 0.9),
    ],
)
def test_grid_charge_only_when_the_gap_pays_for_losses_and_wear(today, tomorrow, charges, gain):
    plan = make_plan(
        Inputs(
            now=at(23, 16),
            today=today,
            tomorrow=tomorrow,
            solar_tomorrow_kwh=1,
            battery_soc=5,
        ),
        Settings(battery_min_gain_eur_kwh=0.03),
    )
    assert plan.battery_gain_eur_kwh == pytest.approx(gain, abs=1e-4)
    assert (plan.battery is not None) is charges
    assert (Reason.BATTERY_NOT_WORTH in plan.reasons) is not charges
    if not charges:
        assert plan.battery_target_pct == 5


def test_price_entities_override_the_defaults():
    inputs = Inputs(
        now=at(23, 16),
        today=Color.WHITE,
        tomorrow=Color.WHITE,
        solar_tomorrow_kwh=0,
        battery_soc=5,
        prices={"white_offpeak": 0.10, "white_peak": 0.20},
    )
    plan = make_plan(inputs, Settings())
    assert plan.offpeak_price == 0.10
    assert plan.peak_price == 0.20
    assert plan.battery is not None


def test_a_lower_threshold_charges_on_white_nights():
    plan = make_plan(
        Inputs(
            now=at(23, 16),
            today=Color.WHITE,
            tomorrow=Color.WHITE,
            solar_tomorrow_kwh=0,
            battery_soc=5,
        ),
        Settings(battery_min_gain_eur_kwh=0.02),
    )
    assert plan.battery is not None


def test_enough_sun_means_no_charge():
    plan = make_plan(
        Inputs(now=at(23, 16), tomorrow=Color.RED, solar_tomorrow_kwh=12, battery_soc=30),
        Settings(peak_load_kwh=8),
    )
    assert plan.battery is None
    assert Reason.BATTERY_SOLAR_COVERS in plan.reasons


def test_unknown_colour_is_reported():
    plan = make_plan(
        Inputs(now=at(24, 7), tomorrow=Color.UNKNOWN, solar_tomorrow_kwh=0, battery_soc=5),
        Settings(peak_load_kwh=5),
    )
    assert Reason.COLOR_UNKNOWN in plan.reasons
    assert plan.peak_price == 0.1921


def test_car_finishes_before_the_end_of_off_peak():
    plan = make_plan(
        Inputs(now=at(23, 16), tomorrow=Color.WHITE, car_soc=50, car_target_pct=80),
        Settings(car_capacity_kwh=60, car_charge_kw=7.2, car_efficiency=0.9),
    )
    # 30 % of 60 kWh = 18 kWh, 20 kWh from the grid, 2 h 47 at 7.2 kW.
    assert plan.car_energy_kwh == 20
    assert plan.car.end == at(24, 5, 45)
    assert plan.car.start == plan.car.end - timedelta(hours=20 / 7.2)


def test_car_that_cannot_finish_starts_at_once():
    plan = make_plan(
        Inputs(now=at(23, 16), tomorrow=Color.RED, car_soc=0, car_target_pct=100),
        Settings(car_capacity_kwh=87, car_charge_kw=7.4),
    )
    assert plan.car.start == at(23, 22)
    assert plan.car.end > at(24, 6)
    assert Reason.CAR_OVERFLOWS_OFFPEAK in plan.reasons


def test_full_car_needs_nothing():
    plan = make_plan(
        Inputs(now=at(23, 16), tomorrow=Color.WHITE, car_soc=81, car_target_pct=80),
        Settings(),
    )
    assert plan.car is None
    assert Reason.CAR_FULL in plan.reasons


def test_small_car_top_up_is_skipped():
    plan = make_plan(
        Inputs(now=at(23, 16), tomorrow=Color.WHITE, car_soc=79, car_target_pct=80),
        Settings(car_capacity_kwh=87, car_min_kwh=3),
    )
    assert plan.car is None
    assert plan.car_energy_kwh == 0
    assert Reason.CAR_BELOW_MINIMUM in plan.reasons


def test_dishwasher_night_starts_after_the_battery():
    plan = make_plan(Inputs(now=at(23, 16), tomorrow=Color.WHITE), Settings())
    assert plan.dishwasher_mode == "night"
    assert plan.dishwasher.start == at(23, 22, 30)
    assert plan.dishwasher.end == at(24, 3, 40)


def test_dishwasher_runs_at_noon_on_a_sunny_blue_day():
    plan = make_plan(
        Inputs(
            now=at(23, 16),
            tomorrow=Color.BLUE,
            solar_tomorrow_kwh=9,
            solar_peak_tomorrow=at(24, 13),
        ),
        Settings(dishwasher_solar_kwh=6),
    )
    assert plan.dishwasher_mode == "solar"
    assert plan.dishwasher.start == at(24, 10, 25)
    assert plan.dishwasher.end == at(24, 15, 35)


def test_night_peak_and_limit():
    slots = [
        Slot(at(23, 22), at(24, 1), 3.0),
        Slot(at(23, 22, 30), at(24, 3, 40), 2.2),
        Slot(at(24, 0), at(24, 5), 7.4),
    ]
    assert night_peak(slots, at(23, 22), at(24, 6)) == 12.6
    plan = make_plan(
        Inputs(
            now=at(23, 16),
            tomorrow=Color.RED,
            solar_tomorrow_kwh=0,
            battery_soc=5,
            car_soc=10,
            car_target_pct=80,
        ),
        Settings(car_capacity_kwh=87),
    )
    assert plan.peak_kw > Settings().max_power_kw
    assert Reason.PEAK_OVER_LIMIT in plan.reasons


def test_explanations():
    from custom_components.tempo_planner.reasons import explain

    reasons = [Reason.BATTERY_CHARGE, Reason.CAR_NOT_PLUGGED]
    assert explain(reasons, "fr")[1] == "La voiture n'est pas branchée."
    assert explain(reasons, "en-GB")[1] == "The car is not plugged in."
    # Unknown language: English. Every reason has a text in every language.
    assert explain(list(Reason), "de") == explain(list(Reason), "en")
    assert len(explain(list(Reason), "fr")) == len(Reason)
