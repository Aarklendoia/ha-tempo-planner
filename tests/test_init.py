"""Setup, sensors and options, inside Home Assistant."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.tempo_planner import const

PARIS = ZoneInfo("Europe/Paris")

ENTITIES = {
    const.CONF_TOMORROW_COLOR: "sensor.rte_tempo_prochaine_couleur",
    const.CONF_TODAY_COLOR: "sensor.rte_tempo_couleur_actuelle",
    const.CONF_SOLAR_TOMORROW: "sensor.energy_production_tomorrow",
    const.CONF_BATTERY_SOC: "sensor.battery_soc",
    const.CONF_CAR_SOC: "sensor.car_battery",
    const.CONF_CAR_PLUGGED: "sensor.car_plug",
    const.CONF_CAR_TARGET: "number.car_target",
    const.CONF_PRICES["white_peak"]: "sensor.price_white_peak",
}


SETTINGS = {
    const.CONF_OFFPEAK_START: "22:00:00",
    const.CONF_OFFPEAK_END: "06:00:00",
    const.CONF_MAX_POWER: 9,
    const.CONF_PEAK_LOAD: 8,
    const.CONF_BATTERY_CAPACITY: 10,
    const.CONF_BATTERY_RESERVE: 5,
    const.CONF_BATTERY_CHARGE_KW: 3,
    const.CONF_BATTERY_MIN_GAIN: 3,
    const.CONF_CAR_CAPACITY: 87,
    const.CONF_CAR_CHARGE_KW: 7.4,
    const.CONF_CAR_TARGET_PCT: 60,
    const.CONF_CAR_MIN: 3,
    const.CONF_DISHWASHER_MINUTES: 310,
    const.CONF_DISHWASHER_SOLAR: 6,
}


@pytest.fixture
async def house(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to(datetime(2026, 11, 23, 16, 0, tzinfo=PARIS))
    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Blanc")
    hass.states.async_set("sensor.rte_tempo_couleur_actuelle", "Bleu")
    hass.states.async_set("sensor.energy_production_tomorrow", "3")
    hass.states.async_set("sensor.battery_soc", "20")
    hass.states.async_set("sensor.car_battery", "50")
    hass.states.async_set("sensor.car_plug", "plugged")
    hass.states.async_set("number.car_target", "80")


async def test_config_flow(hass: HomeAssistant, house) -> None:
    result = await hass.config_entries.flow.async_init(const.DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTITIES)
    # The house comes right after the entities.
    assert result["step_id"] == "settings"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SETTINGS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ENTITIES
    assert result["options"] == SETTINGS

    # Only one planner per house.
    result = await hass.config_entries.flow.async_init(const.DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.ABORT


async def test_sensors_follow_the_inputs(
    hass: HomeAssistant, house, freezer: FrozenDateTimeFactory
) -> None:
    entry = MockConfigEntry(
        domain=const.DOMAIN, data=ENTITIES, options=SETTINGS, unique_id=const.DOMAIN
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.tempo_planner_tomorrow").state == "white"
    assert hass.states.get("sensor.tempo_planner_home_battery_target").state == "55"
    tomorrow = hass.states.get("sensor.tempo_planner_tomorrow")
    assert "The home battery" not in tomorrow.attributes["explanation"][0]
    assert tomorrow.attributes["explanation"][0].startswith("The battery charges")
    assert hass.states.get("sensor.tempo_planner_home_battery_charge_start").state == (
        "2026-11-23T21:00:00+00:00"
    )
    assert hass.states.get("sensor.tempo_planner_car_charge_end").state == (
        "2026-11-24T04:45:00+00:00"
    )

    # Blue night before a white day: worth it with the default prices.
    grid = hass.states.get("sensor.tempo_planner_home_battery_grid_charge")
    assert grid.attributes["offpeak_price"] == 0.1356
    assert grid.attributes["gain_per_kwh"] == pytest.approx(0.1921 - 0.1356 / 0.9, abs=1e-4)

    # A cheaper white peak hour read from its entity: no longer worth it.
    hass.states.async_set("sensor.price_white_peak", "0.16")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.tempo_planner_home_battery_target").state == "5"
    hass.states.async_remove("sensor.price_white_peak")

    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Bleu")
    # Past the coordinator's refresh cooldown.
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
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
    result = await hass.config_entries.options.async_configure(result["flow_id"], SETTINGS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[const.CONF_CAR_TARGET] is None
    # 10 % of 87 kWh at 90 %: 9.67 kWh.
    assert hass.states.get("sensor.tempo_planner_car_charge_energy").state == "9.67"
