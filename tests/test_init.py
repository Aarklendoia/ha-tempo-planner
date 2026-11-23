"""Setup, sensors and options, inside Home Assistant."""

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tempo_planner import const

PARIS = ZoneInfo("Europe/Paris")

ENTITIES = {
    const.CONF_TOMORROW_COLOR: "sensor.rte_tempo_prochaine_couleur",
    const.CONF_SOLAR_TOMORROW: "sensor.energy_production_tomorrow",
    const.CONF_BATTERY_SOC: "sensor.battery_soc",
    const.CONF_CAR_SOC: "sensor.car_battery",
    const.CONF_CAR_PLUGGED: "sensor.car_plug",
    const.CONF_CAR_TARGET: "number.car_target",
}


@pytest.fixture
async def house(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to(datetime(2026, 11, 23, 16, 0, tzinfo=PARIS))
    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Blanc")
    hass.states.async_set("sensor.energy_production_tomorrow", "3")
    hass.states.async_set("sensor.battery_soc", "20")
    hass.states.async_set("sensor.car_battery", "50")
    hass.states.async_set("sensor.car_plug", "plugged")
    hass.states.async_set("number.car_target", "80")


async def test_config_flow(hass: HomeAssistant, house) -> None:
    result = await hass.config_entries.flow.async_init(const.DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTITIES)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ENTITIES

    # Only one planner per house.
    result = await hass.config_entries.flow.async_init(const.DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT


async def test_sensors_follow_the_inputs(hass: HomeAssistant, house) -> None:
    entry = MockConfigEntry(domain=const.DOMAIN, data=ENTITIES, unique_id=const.DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.tempo_planner_tomorrow").state == "white"
    assert hass.states.get("sensor.tempo_planner_home_battery_target").state == "55"
    assert hass.states.get("sensor.tempo_planner_car_charge_end").state == (
        "2026-11-24T04:45:00+00:00"
    )

    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Bleu")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tempo_planner_tomorrow").state == "blue"
    assert hass.states.get("sensor.tempo_planner_home_battery_target").state == "5"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_flow(hass: HomeAssistant, house) -> None:
    entry = MockConfigEntry(domain=const.DOMAIN, data=ENTITIES, unique_id=const.DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "init"
    # Drop the car target entity: the settings' target applies.
    entities = {k: v for k, v in ENTITIES.items() if k != const.CONF_CAR_TARGET}
    result = await hass.config_entries.options.async_configure(result["flow_id"], entities)
    assert result["step_id"] == "settings"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            const.CONF_OFFPEAK_START: "22:00:00",
            const.CONF_OFFPEAK_END: "06:00:00",
            const.CONF_MAX_POWER: 9,
            const.CONF_PEAK_LOAD: 8,
            const.CONF_BATTERY_CAPACITY: 10,
            const.CONF_BATTERY_RESERVE: 5,
            const.CONF_BATTERY_CHARGE_KW: 3,
            const.CONF_BATTERY_ON_BLUE: False,
            const.CONF_CAR_CAPACITY: 87,
            const.CONF_CAR_CHARGE_KW: 7.4,
            const.CONF_CAR_TARGET_PCT: 60,
            const.CONF_DISHWASHER_MINUTES: 310,
            const.CONF_DISHWASHER_SOLAR: 6,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[const.CONF_CAR_TARGET] is None
    # 10 % of 87 kWh at 90 %: 9.67 kWh.
    assert hass.states.get("sensor.tempo_planner_car_charge_energy").state == "9.67"
