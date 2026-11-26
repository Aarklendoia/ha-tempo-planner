"""Tempo Planner: plan the night's loads for the EDF Tempo tariff."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from . import panel, websocket
from .announcer import Announcer
from .const import DOMAIN
from .coordinator import TempoPlannerConfigEntry, TempoPlannerCoordinator, entry_config
from .load_shedding import LoadShedder

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    websocket.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: TempoPlannerConfigEntry) -> bool:
    coordinator = TempoPlannerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    coordinator.async_start_tracking()
    coordinator.shedder = LoadShedder(
        hass, entry.entry_id, coordinator.settings, entry_config(entry)
    )
    await coordinator.shedder.async_load()
    coordinator.announcer = Announcer(
        hass, entry.entry_id, coordinator.settings, entry_config(entry), coordinator.shedder
    )
    await coordinator.announcer.async_load()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # After the platforms: the appliances' entities follow from the start.
    await coordinator.shedder.async_start()
    entry.async_on_unload(coordinator.shedder.async_stop)
    await coordinator.announcer.async_start()
    entry.async_on_unload(coordinator.announcer.async_stop)
    integration = await async_get_integration(hass, DOMAIN)
    await panel.async_register_panel(hass, str(integration.version))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TempoPlannerConfigEntry) -> bool:
    panel.async_remove_panel(hass)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
