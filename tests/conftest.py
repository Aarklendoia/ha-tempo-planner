"""Fixtures for the Home Assistant tests."""

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
import pytest

PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


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
