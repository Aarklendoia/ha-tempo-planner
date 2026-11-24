"""Constants for Tempo Planner."""

from __future__ import annotations

DOMAIN = "tempo_planner"

# Entities read by the planner.
CONF_TOMORROW_COLOR = "tomorrow_color_entity"
CONF_TODAY_COLOR = "today_color_entity"
CONF_SOLAR_TOMORROW = "solar_tomorrow_entity"
CONF_SOLAR_PEAK = "solar_peak_entity"
CONF_BATTERY_SOC = "battery_soc_entity"
CONF_CAR_SOC = "car_soc_entity"
CONF_CAR_PLUGGED = "car_plugged_entity"
CONF_CAR_CHARGING = "car_charging_entity"
CONF_TRIP_CALENDAR = "trip_calendar_entity"
CONF_CAR_TARGET = "car_target_entity"
# Read from the recorder's statistics once a day, not watched.
CONF_HOUSE_ENERGY = "house_energy_entity"

# One price entity per colour and period, keyed like planner.DEFAULT_PRICES.
PRICE_KEYS = (
    "blue_offpeak",
    "blue_peak",
    "white_offpeak",
    "white_peak",
    "red_offpeak",
    "red_peak",
)
CONF_PRICES = {key: f"price_{key}_entity" for key in PRICE_KEYS}

ENTITY_KEYS = (
    CONF_TOMORROW_COLOR,
    CONF_TODAY_COLOR,
    CONF_SOLAR_TOMORROW,
    CONF_SOLAR_PEAK,
    CONF_BATTERY_SOC,
    CONF_CAR_SOC,
    CONF_CAR_PLUGGED,
    CONF_CAR_CHARGING,
    CONF_TRIP_CALENDAR,
    CONF_CAR_TARGET,
    CONF_HOUSE_ENERGY,
    *CONF_PRICES.values(),
)

# Settings (options); the defaults are those of planner.Settings.
CONF_OFFPEAK_START = "offpeak_start"
CONF_OFFPEAK_END = "offpeak_end"
CONF_MAX_POWER = "max_power_kw"
CONF_BATTERY_CAPACITY = "battery_capacity_kwh"
CONF_BATTERY_RESERVE = "battery_reserve_pct"
CONF_BATTERY_CHARGE_KW = "battery_charge_kw"
# In euro cents per kWh in the options.
CONF_BATTERY_MIN_GAIN = "battery_min_gain_ct"
CONF_PEAK_LOAD = "peak_load_kwh"
CONF_PEAK_LOAD_DAYS = "peak_load_days"
CONF_CAR_CAPACITY = "car_capacity_kwh"
CONF_CAR_CHARGE_KW = "car_charge_kw"
CONF_CAR_TARGET_PCT = "car_target_pct"
CONF_CAR_MIN = "car_min_kwh"
CONF_CAR_STARTS_AT_OFFPEAK = "car_starts_at_offpeak"
CONF_CAR_RESERVE = "car_reserve_pct"
CONF_CAR_DAILY = "car_daily_kwh"
CONF_TRIP_KEYWORD = "trip_keyword"
DEFAULT_TRIP_KEYWORD = "Voyage"
# Calendar events read ahead for trips.
TRIP_LOOKAHEAD_DAYS = 3
CONF_DISHWASHER_MINUTES = "dishwasher_minutes"
CONF_DISHWASHER_SOLAR = "dishwasher_solar_kwh"
