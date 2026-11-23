"""Constants for Tempo Planner."""

from __future__ import annotations

DOMAIN = "tempo_planner"

# Entities read by the planner.
CONF_TOMORROW_COLOR = "tomorrow_color_entity"
CONF_SOLAR_TOMORROW = "solar_tomorrow_entity"
CONF_SOLAR_PEAK = "solar_peak_entity"
CONF_BATTERY_SOC = "battery_soc_entity"
CONF_CAR_SOC = "car_soc_entity"
CONF_CAR_PLUGGED = "car_plugged_entity"
CONF_CAR_TARGET = "car_target_entity"

ENTITY_KEYS = (
    CONF_TOMORROW_COLOR,
    CONF_SOLAR_TOMORROW,
    CONF_SOLAR_PEAK,
    CONF_BATTERY_SOC,
    CONF_CAR_SOC,
    CONF_CAR_PLUGGED,
    CONF_CAR_TARGET,
)

# Settings (options); the defaults are those of planner.Settings.
CONF_OFFPEAK_START = "offpeak_start"
CONF_OFFPEAK_END = "offpeak_end"
CONF_MAX_POWER = "max_power_kw"
CONF_BATTERY_CAPACITY = "battery_capacity_kwh"
CONF_BATTERY_RESERVE = "battery_reserve_pct"
CONF_BATTERY_CHARGE_KW = "battery_charge_kw"
CONF_BATTERY_ON_BLUE = "battery_charge_on_blue"
CONF_PEAK_LOAD = "peak_load_kwh"
CONF_CAR_CAPACITY = "car_capacity_kwh"
CONF_CAR_CHARGE_KW = "car_charge_kw"
CONF_CAR_TARGET_PCT = "car_target_pct"
CONF_DISHWASHER_MINUTES = "dishwasher_minutes"
CONF_DISHWASHER_SOLAR = "dishwasher_solar_kwh"
