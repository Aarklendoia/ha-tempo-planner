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
    hass.states.async_set("sensor.charger_power", "7400")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.charger_power", "7300")
    await hass.async_block_till_done()
    # Once per running spell.
    assert len(calls["notify"]) == 1
    assert "Car" in calls["notify"][0].data["message"]


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

    # Back on: shed again.
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
