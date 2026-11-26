"""Load shedding inside Home Assistant."""

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.tempo_planner import const

from .conftest import PARIS
from .test_init import ENTITIES, SETTINGS

COLOR = "sensor.rte_tempo_couleur_actuelle"
SHED = "binary_sensor.tempo_planner_tree_shed"
SWITCH = "switch.tempo_planner_shed_tree"
TOTAL = "sensor.tempo_planner_shed_appliances"


@pytest.fixture
async def planner(hass: HomeAssistant, house) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=const.DOMAIN, data=ENTITIES, options=SETTINGS, unique_id=const.DOMAIN
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def calls(hass: HomeAssistant) -> dict[str, list]:
    return {
        "off": async_mock_service(hass, "light", "turn_off"),
        "on": async_mock_service(hass, "light", "turn_on"),
        "select": async_mock_service(hass, "input_select", "select_option"),
        "notify": async_mock_service(hass, "notify", "phone"),
    }


async def save(client, **appliance) -> dict:
    await client.send_json_auto_id(
        {"type": "tempo_planner/appliances/save", "appliance": appliance}
    )
    return await client.receive_json()


async def red_day(hass: HomeAssistant) -> None:
    hass.states.async_set(COLOR, "Rouge")
    await hass.async_block_till_done()


async def move_to(hass: HomeAssistant, freezer: FrozenDateTimeFactory, when: datetime) -> None:
    freezer.move_to(when)
    async_fire_time_changed(hass, when)
    await hass.async_block_till_done()


async def test_off_on_red_peak_hours_then_back_on(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set("light.tree", "on")
    client = await hass_ws_client(hass)
    reply = await save(client, name="Tree", entity_id="light.tree", notify="notify.phone")
    assert reply["success"], reply
    await hass.async_block_till_done()
    # A blue day: nothing happens.
    assert hass.states.get(SHED).state == "off"
    assert hass.states.get(SWITCH).state == "on"
    assert hass.states.get(TOTAL).state == "0"
    assert calls["off"] == []

    await red_day(hass)
    assert [c.data["entity_id"] for c in calls["off"]] == ["light.tree"]
    shed = hass.states.get(SHED)
    assert shed.state == "on"
    assert shed.attributes["reason"] == "tariff"
    assert shed.attributes["until"] == "2026-11-23T22:00:00+01:00"
    total = hass.states.get(TOTAL)
    assert total.state == "1"
    assert total.attributes["appliances"][0]["name"] == "Tree"

    # Turned off, then back on by someone: off again, with a notification.
    hass.states.async_set("light.tree", "off")
    await hass.async_block_till_done()
    hass.states.async_set("light.tree", "on")
    await hass.async_block_till_done()
    assert len(calls["off"]) == 2
    assert "22:00" in calls["notify"][0].data["message"]
    hass.states.async_set("light.tree", "off")
    await hass.async_block_till_done()

    # Renamed while shed: not turned back on in between.
    await save(client, id=reply["result"]["appliance"]["id"], name="Sapin", entity_id="light.tree")
    await hass.async_block_till_done()
    assert calls["on"] == []
    # The entity id stays.
    assert hass.states.get(SHED).name == "Tempo Planner Sapin shed"

    # Off-peak hours: back on.
    await move_to(hass, freezer, datetime(2026, 11, 23, 22, 0, tzinfo=PARIS))
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]
    assert hass.states.get(SHED).state == "off"
    assert hass.states.get(TOTAL).state == "0"


async def test_an_appliance_already_off_stays_off(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set("light.tree", "off")
    client = await hass_ws_client(hass)
    assert (await save(client, name="Tree", entity_id="light.tree"))["success"]
    await red_day(hass)
    assert hass.states.get(SHED).state == "on"
    assert calls["off"] == []
    await move_to(hass, freezer, datetime(2026, 11, 23, 22, 0, tzinfo=PARIS))
    assert calls["on"] == []


async def test_reduced_mode(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set("input_select.radiator", "Confort")
    client = await hass_ws_client(hass)
    reply = await save(
        client,
        name="Radiator",
        entity_id="input_select.radiator",
        behaviour="reduced",
        reduced_option="Eco",
    )
    assert reply["success"], reply
    await red_day(hass)
    assert calls["select"][-1].data == {"entity_id": "input_select.radiator", "option": "Eco"}
    hass.states.async_set("input_select.radiator", "Eco")
    await hass.async_block_till_done()

    await move_to(hass, freezer, datetime(2026, 11, 23, 22, 0, tzinfo=PARIS))
    assert calls["select"][-1].data == {
        "entity_id": "input_select.radiator",
        "option": "Confort",
    }


async def test_alert_only(hass: HomeAssistant, planner, calls, hass_ws_client) -> None:
    hass.states.async_set("sensor.charger_power", "0")
    client = await hass_ws_client(hass)
    reply = await save(
        client,
        name="Car",
        entity_id="sensor.car_charge",
        behaviour="alert",
        running_entity="sensor.charger_power",
        notify="notify.phone",
    )
    assert reply["success"], reply
    await red_day(hass)
    assert calls["notify"] == []
    # Watched, not shed: not counted, its sensor off while it does not run.
    car = "binary_sensor.tempo_planner_car_shed"
    assert hass.states.get(car).state == "off"
    assert hass.states.get(TOTAL).state == "0"
    await client.send_json_auto_id({"type": "tempo_planner/appliances/list"})
    status = (await client.receive_json())["result"]["appliances"][0]["status"]
    assert (status["shed"], status["watched"], status["running"]) == (False, True, False)

    hass.states.async_set("sensor.charger_power", "7400")
    await hass.async_block_till_done()
    assert hass.states.get(car).state == "on"
    assert hass.states.get(TOTAL).state == "0"
    hass.states.async_set("sensor.charger_power", "7300")
    await hass.async_block_till_done()
    # Once per running spell.
    assert len(calls["notify"]) == 1
    assert "Car" in calls["notify"][0].data["message"]
    hass.states.async_set("sensor.charger_power", "0")
    await hass.async_block_till_done()
    assert hass.states.get(car).state == "off"


async def test_switch_off_releases(hass: HomeAssistant, planner, calls, hass_ws_client) -> None:
    hass.states.async_set("light.tree", "on")
    client = await hass_ws_client(hass)
    assert (await save(client, name="Tree", entity_id="light.tree"))["success"]
    await red_day(hass)
    hass.states.async_set("light.tree", "off")
    await hass.async_block_till_done()

    await hass.services.async_call("switch", "turn_off", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "off"
    assert hass.states.get(SHED).state == "off"
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]

    # Back on: shed again. The light turned on just before is no override.
    hass.states.async_set("light.tree", "on")
    await hass.services.async_call("switch", "turn_on", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(SHED).state == "on"
    assert len(calls["off"]) == 2


async def test_delete_releases_and_removes_the_entities(
    hass: HomeAssistant, planner, calls, hass_ws_client
) -> None:
    hass.states.async_set("light.tree", "on")
    client = await hass_ws_client(hass)
    appliance = (await save(client, name="Tree", entity_id="light.tree"))["result"]["appliance"]
    await red_day(hass)
    hass.states.async_set("light.tree", "off")
    await hass.async_block_till_done()

    await client.send_json_auto_id(
        {"type": "tempo_planner/appliances/delete", "appliance_id": appliance["id"]}
    )
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]
    registry = er.async_get(hass)
    assert registry.async_get(SHED) is None
    assert registry.async_get(SWITCH) is None
    await client.send_json_auto_id({"type": "tempo_planner/appliances/list"})
    assert (await client.receive_json())["result"] == {"appliances": []}


async def test_shedding_survives_a_reload(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set("light.tree", "on")
    client = await hass_ws_client(hass)
    assert (await save(client, name="Tree", entity_id="light.tree"))["success"]
    await red_day(hass)
    hass.states.async_set("light.tree", "off")
    # Past the store's delayed write.
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_reload(planner.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SHED).state == "on"
    # Still known as on before the shedding: turned back on at 22:00.
    await move_to(hass, freezer, datetime(2026, 11, 23, 22, 0, tzinfo=PARIS))
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]


async def test_list_and_errors(hass: HomeAssistant, planner, hass_ws_client) -> None:
    client = await hass_ws_client(hass)
    reply = await save(client, name="Radiator", entity_id="input_select.r", behaviour="reduced")
    assert reply["error"]["code"] == "invalid_appliance"
    assert "reduced_option_missing" in reply["error"]["message"]
    reply = await save(client, name="Tree", entity_id="not an entity")
    assert reply["error"]["code"] == "invalid_format"
    reply = await save(client, id="nope", name="Tree", entity_id="light.tree")
    assert reply["error"]["code"] == "not_found"

    await save(client, name="B", entity_id="light.b", priority=2)
    await save(client, name="A", entity_id="light.a", priority=1)
    await client.send_json_auto_id({"type": "tempo_planner/appliances/list"})
    listed = (await client.receive_json())["result"]["appliances"]
    assert [a["name"] for a in listed] == ["A", "B"]
    assert listed[0]["status"]["shed"] is False


async def test_no_flicker_when_the_colour_is_briefly_unavailable(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set("light.tree", "on")
    client = await hass_ws_client(hass)
    assert (await save(client, name="Tree", entity_id="light.tree"))["success"]
    await red_day(hass)
    hass.states.async_set("light.tree", "off")
    await hass.async_block_till_done()

    hass.states.async_set(COLOR, "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(SHED).state == "on"
    assert calls["on"] == []
    await red_day(hass)
    assert len(calls["off"]) == 1

    # Still unknown when the peak hours end: released all the same.
    hass.states.async_set(COLOR, "unavailable")
    await move_to(hass, freezer, datetime(2026, 11, 23, 22, 0, tzinfo=PARIS))
    assert hass.states.get(SHED).state == "off"
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]


async def test_the_day_after_a_red_day_starts_white_at_once(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    """At 06:00 the current colour entity still shows yesterday's red for a few seconds."""
    hass.states.async_set("light.tree", "on")
    client = await hass_ws_client(hass)
    assert (await save(client, name="Tree", entity_id="light.tree"))["success"]
    await red_day(hass)
    hass.states.async_set("light.tree", "off")
    await hass.async_block_till_done()
    # Announced for tomorrow: white.
    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Blanc")
    await hass.async_block_till_done()
    await move_to(hass, freezer, datetime(2026, 11, 23, 22, 0, tzinfo=PARIS))
    assert len(calls["on"]) == 1
    hass.states.async_set("light.tree", "on")
    await hass.async_block_till_done()

    # 06:00:00, still "Rouge": not shed again.
    await move_to(hass, freezer, datetime(2026, 11, 24, 6, 0, tzinfo=PARIS))
    assert len(calls["off"]) == 1
    assert hass.states.get(SHED).state == "off"
    # 06:00:08, the entity catches up.
    freezer.move_to(datetime(2026, 11, 24, 6, 0, 8, tzinfo=PARIS))
    hass.states.async_set(COLOR, "Blanc")
    await hass.async_block_till_done()
    assert len(calls["off"]) == 1


async def test_a_red_day_after_a_red_day_is_shed_at_once(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    hass.states.async_set("light.tree", "on")
    client = await hass_ws_client(hass)
    assert (await save(client, name="Tree", entity_id="light.tree"))["success"]
    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Rouge")
    await hass.async_block_till_done()
    await move_to(hass, freezer, datetime(2026, 11, 24, 6, 0, tzinfo=PARIS))
    # The current colour entity still says blue, from yesterday.
    assert hass.states.get(SHED).state == "on"
    assert len(calls["off"]) == 1


async def test_schedules_per_colour(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    """Blue: the normal schedule; white: a reduced one; red: off all day."""
    hass.states.async_set("light.tree", "off")
    hass.states.async_set("schedule.tree", "on")
    hass.states.async_set("schedule.tree_white", "off")
    client = await hass_ws_client(hass)
    reply = await save(
        client,
        name="Tree",
        entity_id="light.tree",
        hours="day",
        schedule_blue="schedule.tree",
        schedule_white="schedule.tree_white",
    )
    assert reply["success"], reply
    await hass.async_block_till_done()
    # A blue day with its schedule on: turned on at once.
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]
    hass.states.async_set("light.tree", "on")

    # The schedule ends: off.
    hass.states.async_set("schedule.tree", "off")
    await hass.async_block_till_done()
    assert len(calls["off"]) == 1
    hass.states.async_set("light.tree", "off")
    await hass.async_block_till_done()
    # Turned on by hand outside the schedule: left alone.
    hass.states.async_set("light.tree", "on")
    await hass.async_block_till_done()
    assert len(calls["off"]) == 1
    hass.states.async_set("light.tree", "off")

    # Next day white, announced: at 06:00 the white schedule applies (off: nothing to do).
    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Blanc")
    await hass.async_block_till_done()
    await move_to(hass, freezer, datetime(2026, 11, 24, 6, 0, tzinfo=PARIS))
    hass.states.async_set(COLOR, "Blanc")
    await hass.async_block_till_done()
    # The blue schedule no longer drives it.
    hass.states.async_set("schedule.tree", "on")
    await hass.async_block_till_done()
    assert len(calls["on"]) == 1
    hass.states.async_set("schedule.tree_white", "on")
    await hass.async_block_till_done()
    assert len(calls["on"]) == 2
    hass.states.async_set("light.tree", "on")
    await hass.async_block_till_done()

    # Next day red: shed all day, whatever the schedules.
    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Rouge")
    await hass.async_block_till_done()
    await move_to(hass, freezer, datetime(2026, 11, 25, 6, 0, tzinfo=PARIS))
    hass.states.async_set(COLOR, "Rouge")
    await hass.async_block_till_done()
    assert hass.states.get(SHED).state == "on"
    assert len(calls["off"]) == 2
    hass.states.async_set("light.tree", "off")
    hass.states.async_set("schedule.tree_white", "off")
    hass.states.async_set("schedule.tree_white", "on")
    await hass.async_block_till_done()
    assert len(calls["on"]) == 2

    # The red day ends on a white day with the white schedule on: the schedule
    # decides, not the state before the shedding.
    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Blanc")
    await hass.async_block_till_done()
    await move_to(hass, freezer, datetime(2026, 11, 26, 6, 0, tzinfo=PARIS))
    assert hass.states.get(SHED).state == "off"
    assert len(calls["on"]) == 3


async def test_reduced_mode_schedule(hass: HomeAssistant, planner, calls, hass_ws_client) -> None:
    hass.states.async_set("input_select.radiator", "Eco")
    hass.states.async_set("schedule.radiator", "off")
    client = await hass_ws_client(hass)
    reply = await save(
        client,
        name="Radiator",
        entity_id="input_select.radiator",
        behaviour="reduced",
        reduced_option="Eco",
        normal_option="Confort",
        schedule_blue="schedule.radiator",
    )
    assert reply["success"], reply
    await hass.async_block_till_done()
    # Off and already in Eco: nothing to do.
    assert calls["select"] == []
    hass.states.async_set("schedule.radiator", "on")
    await hass.async_block_till_done()
    assert calls["select"][-1].data["option"] == "Confort"
    hass.states.async_set("input_select.radiator", "Confort")
    hass.states.async_set("schedule.radiator", "off")
    await hass.async_block_till_done()
    assert calls["select"][-1].data["option"] == "Eco"


async def test_schedules_stop_with_the_switch(
    hass: HomeAssistant, planner, calls, hass_ws_client
) -> None:
    hass.states.async_set("light.tree", "off")
    hass.states.async_set("schedule.tree", "off")
    client = await hass_ws_client(hass)
    assert (await save(client, name="Tree", entity_id="light.tree", schedule_blue="schedule.tree"))[
        "success"
    ]
    await hass.services.async_call("switch", "turn_off", {"entity_id": SWITCH}, blocking=True)
    await hass.async_block_till_done()
    hass.states.async_set("schedule.tree", "on")
    await hass.async_block_till_done()
    assert calls["on"] == []


async def test_schedule_errors(hass: HomeAssistant, planner, hass_ws_client) -> None:
    client = await hass_ws_client(hass)
    reply = await save(
        client,
        name="Car",
        entity_id="sensor.car",
        behaviour="alert",
        schedule_red="schedule.car",
    )
    assert "alert_has_no_schedule" in reply["error"]["message"]


GRID = "sensor.grid_power"


async def power_house(hass: HomeAssistant, client, **power) -> dict:
    """A tree, a radiator and a car charger, with power shedding on."""
    hass.states.async_set(GRID, "2000", {"unit_of_measurement": "W"})
    hass.states.async_set("light.tree", "on")
    hass.states.async_set("input_select.radiator", "Confort")
    hass.states.async_set("sensor.radiator_power", "1500", {"unit_of_measurement": "W"})
    hass.states.async_set("switch.charger", "on")
    ids = {}
    for name, appliance in {
        "tree": {"entity_id": "light.tree", "priority": 0, "power_kw": 0.1},
        "radiator": {
            "entity_id": "input_select.radiator",
            "behaviour": "reduced",
            "reduced_option": "Eco",
            "priority": 1,
            "power_entity": "sensor.radiator_power",
        },
        "charger": {
            "entity_id": "switch.charger",
            "priority": 2,
            "power_kw": 7.4,
            "hard_only": True,
        },
    }.items():
        reply = await save(client, name=name.capitalize(), **appliance)
        assert reply["success"], reply
        ids[name] = reply["result"]["appliance"]["id"]
    await client.send_json_auto_id(
        {
            "type": "tempo_planner/power/save",
            "power": {
                "enabled": True,
                "power_entity": GRID,
                "soft_limit_kw": 6,
                "hard_limit_kw": 9,
                "soft_delay_s": 60,
                "hard_delay_s": 5,
                "restore_delay_s": 120,
                **power,
            },
        }
    )
    reply = await client.receive_json()
    assert reply["success"], reply
    await hass.async_block_till_done()
    return ids


async def tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int) -> None:
    for _ in range(seconds // 5):
        freezer.tick(timedelta(seconds=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


async def test_power_soft_then_back(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    switch_off = async_mock_service(hass, "switch", "turn_off")
    client = await hass_ws_client(hass)
    await power_house(hass, client)
    assert hass.states.get("sensor.tempo_planner_load_shedding_level").state == "none"
    assert hass.states.get("sensor.tempo_planner_power_headroom").state == "4.0"

    # 7 kW: over the soft limit.
    hass.states.async_set(GRID, "7000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tempo_planner_load_shedding_level").state == "soft"
    await tick(hass, freezer, 55)
    assert calls["off"] == []
    await tick(hass, freezer, 10)
    # The lowest priority first: the tree.
    assert [c.data["entity_id"] for c in calls["off"]] == ["light.tree"]
    shed = hass.states.get(SHED)
    assert shed.state == "on"
    assert shed.attributes["reason"] == "power"
    assert shed.attributes["until"] is None
    hass.states.async_set("light.tree", "off")
    await tick(hass, freezer, 60)
    # Then the radiator, reduced; never the charger below the hard limit.
    assert calls["select"][-1].data == {"entity_id": "input_select.radiator", "option": "Eco"}
    hass.states.async_set("input_select.radiator", "Eco")
    hass.states.async_set("sensor.radiator_power", "300", {"unit_of_measurement": "W"})
    await tick(hass, freezer, 120)
    assert switch_off == []

    # Down to 3 kW: the radiator comes back first, after the delay.
    hass.states.async_set(GRID, "3000", {"unit_of_measurement": "W"})
    await tick(hass, freezer, 115)
    assert calls["select"][-1].data["option"] == "Eco"
    await tick(hass, freezer, 10)
    assert calls["select"][-1].data["option"] == "Confort"
    hass.states.async_set("input_select.radiator", "Confort")
    await tick(hass, freezer, 125)
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]
    assert hass.states.get(SHED).state == "off"


async def test_power_hard_limit(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    switch_off = async_mock_service(hass, "switch", "turn_off")
    async_mock_service(hass, "switch", "turn_on")
    client = await hass_ws_client(hass)
    await power_house(hass, client)
    hass.states.async_set(GRID, "12000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tempo_planner_load_shedding_level").state == "hard"
    await tick(hass, freezer, 5)
    # 12 - 0.1 - 1.5 = 10.4 > 9: the charger goes too.
    assert len(calls["off"]) == 1
    assert len(calls["select"]) == 1
    assert [c.data["entity_id"] for c in switch_off] == ["switch.charger"]


async def test_power_then_tariff(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    """Shed by power, then a red day starts: the tariff takes over, with the same state."""
    client = await hass_ws_client(hass)
    await power_house(hass, client)
    hass.states.async_set(GRID, "7000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    await tick(hass, freezer, 65)
    assert len(calls["off"]) == 1
    hass.states.async_set("light.tree", "off")
    await red_day(hass)
    assert hass.states.get(SHED).attributes["reason"] == "tariff"
    # The power comes down: the tree stays off, it's a red day.
    hass.states.async_set(GRID, "1000", {"unit_of_measurement": "W"})
    await tick(hass, freezer, 300)
    assert calls["on"] == []
    # 22:00: back on, as it was before the power shedding.
    await move_to(hass, freezer, datetime(2026, 11, 23, 22, 0, tzinfo=PARIS))
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]


async def test_power_switch_off_brings_back(
    hass: HomeAssistant, planner, calls, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    client = await hass_ws_client(hass)
    await power_house(hass, client)
    hass.states.async_set(GRID, "7000", {"unit_of_measurement": "W"})
    await hass.async_block_till_done()
    await tick(hass, freezer, 65)
    hass.states.async_set("light.tree", "off")
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.tempo_planner_power_load_shedding"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert [c.data["entity_id"] for c in calls["on"]] == ["light.tree"]
    assert hass.states.get("sensor.tempo_planner_load_shedding_level").state == "unknown"
    # Off: no more shedding.
    await tick(hass, freezer, 120)
    assert len(calls["off"]) == 1


async def test_power_settings_errors(hass: HomeAssistant, planner, hass_ws_client) -> None:
    client = await hass_ws_client(hass)
    for power, code in (
        ({"enabled": True}, "no_power_entity"),
        ({"power_entity": GRID, "soft_limit_kw": 9, "hard_limit_kw": 6}, "invalid_limits"),
        ({"soft_limits": {"purple_peak": 3}}, "invalid_format"),
    ):
        await client.send_json_auto_id({"type": "tempo_planner/power/save", "power": power})
        reply = await client.receive_json()
        assert reply["error"]["code"] == code, reply
