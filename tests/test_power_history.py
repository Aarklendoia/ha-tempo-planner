"""The power chart's series, read from the recorder."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.tempo_planner import const
from custom_components.tempo_planner.power_history import async_power_history

from .conftest import PARIS
from .test_init import ENTITIES, SETTINGS

W = {"unit_of_measurement": "W"}


@pytest.fixture
def mock_recorder_before_hass(async_setup_recorder_instance) -> None:
    """Start the recorder before Home Assistant."""


async def test_power_history(
    recorder_mock, hass: HomeAssistant, house, hass_ws_client, freezer: FrozenDateTimeFactory
) -> None:
    async_mock_service(hass, "input_select", "select_option")
    hass.states.async_set("sensor.grid_power", "1000", W)
    hass.states.async_set("sensor.house_power", "1200", W)
    hass.states.async_set("sensor.radiator_power", "1500", W)
    hass.states.async_set("input_select.radiator", "Confort")
    entry = MockConfigEntry(
        domain=const.DOMAIN, data=ENTITIES, options=SETTINGS, unique_id=const.DOMAIN
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "tempo_planner/appliances/save",
            "appliance": {
                "name": "Radiator",
                "entity_id": "input_select.radiator",
                "behaviour": "reduced",
                "reduced_option": "Eco",
                "power_entity": "sensor.radiator_power",
            },
        }
    )
    assert (await client.receive_json())["success"]
    # Watched only: it charges during the red day, but nothing is shed.
    hass.states.async_set("sensor.charger_power", "7400", W)
    await client.send_json_auto_id(
        {
            "type": "tempo_planner/appliances/save",
            "appliance": {
                "name": "Car",
                "entity_id": "sensor.charger_power",
                "behaviour": "alert",
                "priority": 5,
            },
        }
    )
    assert (await client.receive_json())["success"]
    await client.send_json_auto_id(
        {
            "type": "tempo_planner/power/save",
            "power": {
                "power_entity": "sensor.grid_power",
                "house_entity": "sensor.house_power",
                "soft_limit_kw": 6,
                "hard_limit_kw": 9,
                "soft_limits": {"red_peak": 3},
            },
        }
    )
    assert (await client.receive_json())["success"]
    # The command answers (the clock moving on below would expire the connection).
    await client.send_json_auto_id({"type": "tempo_planner/power/history", "hours": 1})
    reply = await client.receive_json()
    assert reply["success"], reply
    assert reply["result"]["count"] == 12
    await async_wait_recording_done(hass)

    # 16:30: 7 kW; 17:00: a red day starts, the radiator is shed.
    freezer.move_to(datetime(2026, 11, 23, 16, 30, tzinfo=PARIS))
    hass.states.async_set("sensor.grid_power", "7000", W)
    await async_wait_recording_done(hass)
    freezer.move_to(datetime(2026, 11, 23, 17, 0, tzinfo=PARIS))
    hass.states.async_set("sensor.rte_tempo_couleur_actuelle", "Rouge")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.radiator_power", "100", W)
    await async_wait_recording_done(hass)
    freezer.move_to(datetime(2026, 11, 23, 17, 32, tzinfo=PARIS))

    chart = await async_power_history(hass, entry.runtime_data, 2)
    # 2 hours of 5-minute buckets, up to 17:35.
    assert chart["step"] == 300
    assert chart["count"] == 24
    assert chart["start"] == "2026-11-23T15:35:00+01:00"
    grid = chart["grid"]
    # 15:35-16:00: no history before the sensor was set, then 1 kW, then 7 kW.
    assert grid[0] is None
    assert grid[6] == 1.0  # 16:05
    assert grid[13] == 7.0  # 16:40
    assert chart["house"][13] == 1.2
    # Today is red: 3 kW in peak hours all along, the hard limit as set.
    assert set(chart["soft"]) == {3}
    assert chart["hard"] == 9
    radiator = chart["appliances"][0]
    assert radiator["name"] == "Radiator"
    assert radiator["slot"] == 0
    assert radiator["power"][13] == 1.5
    assert radiator["power"][-1] == 0.1
    assert radiator["shed"] == [
        {
            "start": "2026-11-23T17:00:00+01:00",
            "end": "2026-11-23T17:32:00+01:00",
            "reason": "tariff",
            "avoided_kw": 1.5,
        }
    ]
    car = chart["appliances"][1]
    assert car["name"] == "Car"
    assert car["shed"] == []
