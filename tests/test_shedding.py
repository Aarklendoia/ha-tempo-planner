"""Load shedding rules, without Home Assistant."""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from custom_components.tempo_planner.planner import Color
from custom_components.tempo_planner.shedding import (
    Appliance,
    Behaviour,
    Hours,
    is_running,
    problems,
    tariff_until,
)

PARIS = ZoneInfo("Europe/Paris")
START, END = time(22), time(6)


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=PARIS)


TREE = Appliance(id="tree", name="Tree", entity_id="light.tree")


def test_shed_during_red_peak_hours_only():
    assert tariff_until(TREE, at(26, 6), Color.RED, START, END) == at(26, 22)
    assert tariff_until(TREE, at(26, 21, 59), Color.RED, START, END) == at(26, 22)
    assert tariff_until(TREE, at(26, 22), Color.RED, START, END) is None
    # Before 06:00 the day in progress is still the previous one.
    assert tariff_until(TREE, at(26, 5, 59), Color.RED, START, END) is None


def test_not_shed_on_other_colours_or_when_disabled():
    assert tariff_until(TREE, at(26, 10), Color.WHITE, START, END) is None
    assert tariff_until(TREE, at(26, 10), Color.UNKNOWN, START, END) is None
    disabled = Appliance(id="t", name="T", entity_id="light.t", enabled=False)
    assert tariff_until(disabled, at(26, 10), Color.RED, START, END) is None


def test_white_days_when_chosen():
    both = Appliance(
        id="t", name="T", entity_id="light.t", colors=frozenset({Color.WHITE, Color.RED})
    )
    assert tariff_until(both, at(26, 10), Color.WHITE, START, END) == at(26, 22)


def test_whole_tempo_day():
    day = Appliance(id="t", name="T", entity_id="light.t", hours=Hours.DAY)
    assert tariff_until(day, at(26, 10), Color.RED, START, END) == at(27, 6)
    assert tariff_until(day, at(26, 23), Color.RED, START, END) == at(27, 6)
    # After midnight, the red day goes on until 06:00.
    assert tariff_until(day, at(27, 3), Color.RED, START, END) == at(27, 6)


def test_running():
    car = Appliance(id="c", name="Car", entity_id="sensor.car", behaviour=Behaviour.ALERT)
    assert is_running(car, "3000")
    assert not is_running(car, "20")
    assert is_running(car, "on")
    assert not is_running(car, "off")
    assert not is_running(car, None)
    plug = Appliance(
        id="c",
        name="Car",
        entity_id="sensor.car",
        behaviour=Behaviour.ALERT,
        running_states=("charge_in_progress",),
    )
    assert is_running(plug, "charge_in_progress")
    assert not is_running(plug, "waiting_for_current_charge")


def test_problems():
    assert problems(TREE) == []
    assert problems(Appliance(id="s", name="S", entity_id="sensor.s")) == ["domain_cannot_turn_off"]
    reduced = Appliance(
        id="r", name="R", entity_id="input_select.radiator", behaviour=Behaviour.REDUCED
    )
    assert problems(reduced) == ["reduced_option_missing"]
    assert problems(
        Appliance(
            id="r", name="R", entity_id="light.r", behaviour=Behaviour.REDUCED, reduced_option="Eco"
        )
    ) == ["domain_has_no_mode"]
    assert problems(
        Appliance(id="t", name="T", entity_id="light.t", notify="persistent_notification")
    ) == ["notify_not_a_notify_service"]
    assert problems(Appliance(id="t", name="T", entity_id="light.t", colors=frozenset())) == [
        "no_color"
    ]


def test_round_trip():
    appliance = Appliance(
        id="r",
        name="Radiator",
        entity_id="climate.bathroom",
        behaviour=Behaviour.REDUCED,
        reduced_option="eco",
        colors=frozenset({Color.WHITE, Color.RED}),
        hours=Hours.DAY,
        notify="notify.phone",
        priority=3,
        power_kw=1.5,
    )
    data = appliance.to_dict()
    assert data["colors"] == ["red", "white"]
    assert Appliance.from_dict(data) == appliance
