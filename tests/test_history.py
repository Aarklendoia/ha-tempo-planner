"""Peak-hour consumption learnt from the recorder."""

from datetime import datetime, timedelta

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import (
    async_wait_recording_done,
)

from custom_components.tempo_planner import const

from .conftest import PARIS
from .test_init import ENTITIES, SETTINGS


@pytest.fixture
def mock_recorder_before_hass(async_setup_recorder_instance) -> None:
    """Start the recorder before Home Assistant."""


async def test_peak_load_from_the_recorder(recorder_mock, hass: HomeAssistant, house) -> None:
    # Two full days of history: 0.5 kWh an hour, then 1 kWh an hour.
    rows = []
    total = 0.0
    start = datetime(2026, 11, 21, 0, 0, tzinfo=PARIS)
    for hour in range(48):
        total += 0.5 if hour < 24 else 1.0
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
    await async_wait_recording_done(hass)

    entry = MockConfigEntry(
        domain=const.DOMAIN,
        data={**ENTITIES, const.CONF_HOUSE_ENERGY: "sensor.house_energy"},
        options=SETTINGS,
        unique_id=const.DOMAIN,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    peak = hass.states.get("sensor.tempo_planner_peak_hour_consumption")
    # (8 + 16) / 2, instead of the 8 kWh setting.
    assert float(peak.state) == 12.0
    assert peak.attributes["source"] == "history"
    assert peak.attributes["days"] == 2
    # 12 kWh, 3 from the sun: 9 kWh above the 5 % reserve of a 10 kWh battery.
    assert hass.states.get("sensor.tempo_planner_home_battery_target").state == "95"
