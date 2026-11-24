"""Peak-hour consumption learnt from the recorder."""

from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.tempo_planner import const

from .conftest import PARIS
from .test_init import ENTITIES, SETTINGS


@pytest.fixture
def mock_recorder_before_hass(async_setup_recorder_instance) -> None:
    """Start the recorder before Home Assistant."""


def import_hours(hass: HomeAssistant, kwh_per_hour: dict[int, float]) -> None:
    """Hourly statistics of the house meter, for whole days of November."""
    rows = []
    total = 0.0
    for day, kwh in sorted(kwh_per_hour.items()):
        start = datetime(2026, 11, day, 0, 0, tzinfo=PARIS)
        for hour in range(24):
            total += kwh
            rows.append({"start": dt_util.as_utc(start + timedelta(hours=hour)), "sum": total})
    async_import_statistics(
        hass,
        {
            "mean_type": StatisticMeanType.NONE,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistic_id": "sensor.house_energy",
            "unit_class": "energy",
            "unit_of_measurement": "kWh",
        },
        rows,
    )


async def setup_planner(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=const.DOMAIN,
        entry_id="planner",
        data={**ENTITIES, const.CONF_HOUSE_ENERGY: "sensor.house_energy"},
        options=SETTINGS,
        unique_id=const.DOMAIN,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def later(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Past the refresh cooldown and the store's save delay."""
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def peak(hass: HomeAssistant):
    return hass.states.get("sensor.tempo_planner_peak_hour_consumption")


async def test_peak_load_from_the_recorder(recorder_mock, hass: HomeAssistant, house) -> None:
    # Two full days of history, colours unknown: 0.5 kWh an hour, then 1 kWh.
    import_hours(hass, {21: 0.5, 22: 1.0})
    await async_wait_recording_done(hass)
    await setup_planner(hass)

    # (8 + 16) / 2, instead of the 8 kWh setting.
    assert float(peak(hass).state) == 12.0
    assert peak(hass).attributes["source"] == "history"
    assert peak(hass).attributes["days"] == 2
    assert peak(hass).attributes["color"] == "all"
    # 12 kWh, 3 from the sun: 9 kWh above the 5 % reserve of a 10 kWh battery.
    assert hass.states.get("sensor.tempo_planner_home_battery_target").state == "95"


async def test_peak_load_of_tomorrows_colour(
    recorder_mock, hass: HomeAssistant, house, hass_storage, freezer: FrozenDateTimeFactory
) -> None:
    hass_storage["tempo_planner.planner"] = {
        "version": 1,
        "key": "tempo_planner.planner",
        "data": {
            "colors": {
                "2026-11-18": "white",
                "2026-11-19": "white",
                "2026-11-20": "white",
                "2026-11-21": "blue",
                "2026-11-22": "blue",
            }
        },
    }
    # White days at 1 kWh an hour (16 kWh), blue days at 0.5 (8 kWh).
    import_hours(hass, {18: 1.0, 19: 1.0, 20: 1.0, 21: 0.5, 22: 0.5})
    await async_wait_recording_done(hass)
    await setup_planner(hass)

    # Tomorrow is white: the three white days.
    assert float(peak(hass).state) == 16.0
    assert peak(hass).attributes["color"] == "white"
    assert peak(hass).attributes["days"] == 3

    # Tomorrow is blue: only two blue days, so the recent days of any colour.
    hass.states.async_set("sensor.rte_tempo_prochaine_couleur", "Bleu")
    await later(hass, freezer)
    assert float(peak(hass).state) == (16 * 3 + 8 * 2) / 5
    assert peak(hass).attributes["color"] == "all"
    assert peak(hass).attributes["days"] == 5

    # Today's colour was remembered for the days to come.
    assert hass_storage["tempo_planner.planner"]["data"]["colors"]["2026-11-23"] == "blue"


async def test_colours_recorded_before_the_setup(
    recorder_mock, hass: HomeAssistant, house, hass_storage, freezer: FrozenDateTimeFactory
) -> None:
    # The recorder saw two days of today's colour before the planner was set up.
    for day, color in ((21, "Rouge"), (22, "Blanc")):
        freezer.move_to(datetime(2026, 11, day, 6, 30, tzinfo=PARIS))
        hass.states.async_set("sensor.rte_tempo_couleur_actuelle", color)
        await async_wait_recording_done(hass)
    freezer.move_to(datetime(2026, 11, 23, 16, 0, tzinfo=PARIS))
    hass.states.async_set("sensor.rte_tempo_couleur_actuelle", "Bleu")
    await async_wait_recording_done(hass)

    await setup_planner(hass)
    await later(hass, freezer)
    colors = hass_storage["tempo_planner.planner"]["data"]["colors"]
    assert colors == {"2026-11-21": "red", "2026-11-22": "white", "2026-11-23": "blue"}


async def test_review_of_the_last_day(
    recorder_mock, hass: HomeAssistant, house, hass_storage, freezer: FrozenDateTimeFactory
) -> None:
    async def at(day: int, hour: int, minute: int = 0) -> None:
        freezer.move_to(datetime(2026, 11, day, hour, minute, tzinfo=PARIS))
        # The coordinator's 15-minute timer runs on the loop's clock, which the
        # freezer does not move: fire it explicitly.
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=16))
        await hass.async_block_till_done(wait_background_tasks=True)

    # The afternoon before (the house fixture): a white day tomorrow, the battery
    # at 20 %.
    await setup_planner(hass)
    # 8 kWh forecast (no history yet), 3 from the sun: charge to 55 %.
    assert hass.states.get("sensor.tempo_planner_home_battery_target").state == "55"

    # The night: the EcoFlow battery charges as well.
    for day, hour, soc in ((23, 21, "10"), (24, 1, "60"), (24, 5, "58")):
        await at(day, hour)
        hass.states.async_set("sensor.battery_soc", soc)
        await async_wait_recording_done(hass)

    # The white day uses 16 kWh during peak hours; the review comes after midnight.
    await at(24, 23)
    import_hours(hass, {24: 1.0})
    await async_wait_recording_done(hass)
    await at(25, 0, 30)

    last_day = hass.states.get("sensor.tempo_planner_last_day_s_peak_hour_consumption")
    assert float(last_day.state) == 16.0
    assert last_day.attributes["day"] == "2026-11-24"
    assert last_day.attributes["forecast"] == 8.0
    assert last_day.attributes["error"] == -8.0
    assert last_day.attributes["mean_abs_error"] == 8.0

    battery = hass.states.get("sensor.tempo_planner_last_night_s_battery")
    assert battery.state == "agreed_charge"
    assert battery.attributes["level_start"] == 10.0
    assert battery.attributes["level_max"] == 60.0
    assert battery.attributes["level_end"] == 58.0
    assert battery.attributes["agreement"] == 100

    # Kept for the summaries after a restart.
    await at(25, 1)
    reviews = hass_storage["tempo_planner.planner"]["data"]["reviews"]
    assert reviews["2026-11-24"]["actual_kwh"] == 16.0
