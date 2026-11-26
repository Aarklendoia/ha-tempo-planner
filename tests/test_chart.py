"""Chart series from recorded states, without Home Assistant."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from custom_components.tempo_planner.chart import bucket_means, on_intervals, value_before

PARIS = ZoneInfo("Europe/Paris")
STEP = timedelta(minutes=5)


def at(hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 11, 26, hour, minute, second, tzinfo=PARIS)


def test_bucket_means_are_time_weighted():
    samples = [(at(9, 50), 1.0), (at(10, 2), 4.0), (at(10, 7, 30), None), (at(10, 9), 2.0)]
    means = bucket_means(samples, at(10), at(10, 15), STEP)
    # 10:00-10:05: 2 min at 1, 3 min at 4; 10:05-10:10: 2.5 min at 4, 1 min at 2,
    # 1.5 min unknown; 10:10-10:15: 2.
    assert means == [round((2 * 1 + 3 * 4) / 5, 3), round((2.5 * 4 + 1 * 2) / 3.5, 3), 2.0]


def test_bucket_means_without_values():
    assert bucket_means([], at(10), at(10, 10), STEP) == [None, None]
    # The last bucket may be in progress.
    assert bucket_means([(at(9), 3.0)], at(10), at(10, 7), STEP) == [3.0, 3.0]


def test_on_intervals():
    samples = [
        (at(5), False, None),
        (at(6), True, "tariff"),
        (at(6, 30), True, "tariff"),  # an attribute changed: the same shedding
        (at(8), False, None),
        (at(9), True, "power"),
    ]
    assert on_intervals(samples, at(7), at(10)) == [
        (at(7), at(8), "tariff"),
        (at(9), at(10), "power"),
    ]


def test_value_before():
    series = [1.5, None, 0.2, None]
    assert value_before(series, at(10), at(10, 15), STEP) == 0.2
    assert value_before(series, at(10), at(10, 12), STEP) == 1.5
    assert value_before(series, at(10), at(10, 2), STEP) is None
