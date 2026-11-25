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


def test_current_color_at_the_start_of_the_day():
    from custom_components.tempo_planner.shedding import current_color

    start = at(27, 6)
    # 06:00:00, the entity still shows yesterday's red: the announced white wins.
    assert current_color(Color.RED, at(26, 6), Color.WHITE, start) is Color.WHITE
    # Updated since the day started: the entity wins.
    assert current_color(Color.WHITE, at(27, 6, 1), Color.WHITE, start) is Color.WHITE
    assert current_color(Color.BLUE, at(27, 6, 1), Color.WHITE, start) is Color.BLUE
    # Nothing announced: the entity, as before.
    assert current_color(Color.RED, at(26, 6), None, start) is Color.RED
    assert current_color(Color.RED, at(26, 6), Color.UNKNOWN, start) is Color.RED
    assert current_color(Color.UNKNOWN, None, Color.RED, start) is Color.RED


def test_schedules():
    from custom_components.tempo_planner.shedding import scheduled_state

    tree = Appliance(
        id="t",
        name="Tree",
        entity_id="light.tree",
        schedule_blue="schedule.tree",
        schedule_white="schedule.tree_white",
    )
    assert tree.schedule_for(Color.BLUE) == "schedule.tree"
    assert tree.schedule_for(Color.WHITE) == "schedule.tree_white"
    assert tree.schedule_for(Color.RED) is None
    assert tree.schedule_for(Color.UNKNOWN) is None
    assert tree.schedules == ["schedule.tree", "schedule.tree_white"]
    assert scheduled_state(tree, True) == "on"
    assert scheduled_state(tree, False) == "off"
    assert Appliance.from_dict(tree.to_dict()) == tree

    radiator = Appliance(
        id="r",
        name="R",
        entity_id="input_select.r",
        behaviour=Behaviour.REDUCED,
        reduced_option="Eco",
        normal_option="Confort",
        schedule_blue="schedule.r",
    )
    assert scheduled_state(radiator, True) == "Confort"
    assert scheduled_state(radiator, False) == "Eco"
    assert problems(radiator) == []


def test_schedule_problems():
    assert problems(
        Appliance(
            id="r",
            name="R",
            entity_id="input_select.r",
            behaviour=Behaviour.REDUCED,
            reduced_option="Eco",
            schedule_blue="schedule.r",
        )
    ) == ["normal_option_missing"]
    assert problems(
        Appliance(
            id="c",
            name="C",
            entity_id="sensor.c",
            behaviour=Behaviour.ALERT,
            schedule_red="schedule.c",
        )
    ) == ["alert_has_no_schedule"]
    assert problems(
        Appliance(id="t", name="T", entity_id="light.t", schedule_blue="input_boolean.t")
    ) == ["schedule_not_a_schedule"]


def _power():
    from custom_components.tempo_planner.shedding import PowerSettings

    return PowerSettings(
        enabled=True,
        power_entity="sensor.grid",
        soft_limit_kw=6,
        hard_limit_kw=9,
        soft_delay_s=120,
        hard_delay_s=5,
        restore_delay_s=300,
    )


def _candidates():
    from custom_components.tempo_planner.shedding import Candidate

    tree = Appliance(id="tree", name="Tree", entity_id="light.tree", priority=0)
    radiator = Appliance(id="rad", name="Rad", entity_id="switch.rad", priority=1)
    car = Appliance(id="car", name="Car", entity_id="switch.car", priority=2, hard_only=True)
    return [Candidate(tree, 0.1), Candidate(radiator, 1.5), Candidate(car, 7.0)]


def test_power_soft_limit_one_at_a_time():
    from custom_components.tempo_planner.shedding import PowerTimers, power_step

    settings, timers, candidates = _power(), PowerTimers(), _candidates()
    t0 = at(26, 10)
    from datetime import timedelta

    assert power_step(t0, 7, 6, 9, settings, timers, [], candidates).shed == ()
    assert (
        power_step(t0 + timedelta(seconds=119), 7, 6, 9, settings, timers, [], candidates).shed
        == ()
    )
    decision = power_step(t0 + timedelta(seconds=120), 7, 6, 9, settings, timers, [], candidates)
    assert decision.shed == ("tree",)
    # The delay starts again before the next one.
    later = t0 + timedelta(seconds=180)
    assert power_step(later, 7, 6, 9, settings, timers, [], candidates[1:]).shed == ()
    # A short peak under the limit resets it.
    assert power_step(later, 5, 6, 9, settings, timers, [], candidates[1:]).shed == ()
    assert (
        power_step(
            later + timedelta(seconds=150), 7, 6, 9, settings, timers, [], candidates[1:]
        ).shed
        == ()
    )


def test_power_soft_limit_leaves_hard_only_appliances():
    from custom_components.tempo_planner.shedding import PowerTimers, power_step

    settings, timers = _power(), PowerTimers()
    car_only = _candidates()[2:]
    power_step(at(26, 10), 7, 6, 9, settings, timers, [], car_only)
    assert power_step(at(26, 10, 5), 7, 6, 9, settings, timers, [], car_only).shed == ()


def test_power_hard_limit_sheds_as_many_as_needed():
    from datetime import timedelta

    from custom_components.tempo_planner.shedding import Candidate, PowerTimers, power_step

    settings, timers, candidates = _power(), PowerTimers(), _candidates()
    t0 = at(26, 10)
    assert power_step(t0, 10, 6, 9, settings, timers, [], candidates).shed == ()
    decision = power_step(t0 + timedelta(seconds=5), 10, 6, 9, settings, timers, [], candidates)
    # 10 - 0.1 - 1.5 = 8.4 kW: under 9 after the radiator, the car stays.
    assert decision.shed == ("tree", "rad")
    # Unknown power: one, then measure again.
    unknown = [Candidate(c.appliance, None) for c in candidates]
    timers = PowerTimers()
    power_step(t0, 12, 6, 9, settings, timers, [], unknown)
    assert power_step(t0 + timedelta(seconds=5), 12, 6, 9, settings, timers, [], unknown).shed == (
        "tree",
    )
    # Hard-only appliances go too above the hard limit.
    timers = PowerTimers()
    power_step(t0, 15, 6, 9, settings, timers, [], candidates)
    assert power_step(
        t0 + timedelta(seconds=5), 15, 6, 9, settings, timers, [], candidates
    ).shed == (
        "tree",
        "rad",
        "car",
    )


def test_power_restores_the_last_one_with_room_for_it():
    from datetime import timedelta

    from custom_components.tempo_planner.shedding import PowerShed, PowerTimers, power_step

    settings, timers = _power(), PowerTimers()
    shed = [PowerShed("tree", 0.1), PowerShed("rad", 1.5)]
    t0 = at(26, 10)
    # 4.5 + 1.5 = 6 > 6 - 0.5: no room for the radiator.
    assert power_step(t0, 4.5, 6, 9, settings, timers, shed, []).restore == ()
    assert (
        power_step(t0 + timedelta(seconds=400), 4.5, 6, 9, settings, timers, shed, []).restore == ()
    )
    # 3 + 1.5 = 4.5 < 5.5: back after the delay, the last one first.
    assert power_step(t0, 3, 6, 9, settings, timers, shed, []).restore == ()
    assert power_step(t0 + timedelta(seconds=300), 3, 6, 9, settings, timers, shed, []).restore == (
        "rad",
    )


def test_power_reading_lost():
    from datetime import timedelta

    from custom_components.tempo_planner.shedding import PowerShed, PowerTimers, power_step

    settings, timers = _power(), PowerTimers()
    shed = [PowerShed("tree", 0.1), PowerShed("rad", 1.5)]
    assert power_step(at(26, 10), None, 6, 9, settings, timers, shed, _candidates()).shed == ()
    decision = power_step(
        at(26, 10) + timedelta(seconds=300), None, 6, 9, settings, timers, shed, _candidates()
    )
    assert decision.restore == ("rad", "tree")


def test_power_helpers():
    from custom_components.tempo_planner.shedding import (
        PowerLevel,
        PowerSettings,
        power_level,
        to_kw,
    )

    settings = PowerSettings(soft_limit_kw=6, hard_limit_kw=9, soft_limits={"red_peak": 3})
    assert settings.soft_for(Color.RED, offpeak=False) == 3
    assert settings.soft_for(Color.RED, offpeak=True) == 6
    assert settings.soft_for(Color.UNKNOWN, offpeak=False) == 6
    assert PowerSettings.from_dict(settings.to_dict()) == settings
    assert to_kw("1500", "W") == 1.5
    assert to_kw("1.5", "kW") == 1.5
    assert to_kw("unknown", "W") is None
    assert power_level(10, 6, 9) is PowerLevel.HARD
    assert power_level(7, 6, 9) is PowerLevel.SOFT
    assert power_level(5, 6, 9) is PowerLevel.NONE
    assert power_level(None, 6, 9) is PowerLevel.NONE
