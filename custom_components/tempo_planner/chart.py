"""Recorded states turned into chart series.

Pure Python, no Home Assistant import: everything here can be tested on its own.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def bucket_means(
    samples: list[tuple[datetime, float | None]],
    start: datetime,
    end: datetime,
    step: timedelta,
) -> list[float | None]:
    """The time-weighted mean of a recorded value over each bucket.

    `samples` are the recorded values in time order, the one in force at `start`
    included; None is an unknown value, left out of the means. A bucket with no
    known value is None.
    """
    count = max(0, -(-(end - start) // step))
    sums = [0.0] * count
    known = [0.0] * count
    for index, (at, value) in enumerate(samples):
        if value is None:
            continue
        until = samples[index + 1][0] if index + 1 < len(samples) else end
        begin, finish = max(at, start), min(until, end)
        while begin < finish:
            bucket = int((begin - start) // step)
            bucket_end = min(start + step * (bucket + 1), finish)
            seconds = (bucket_end - begin).total_seconds()
            sums[bucket] += value * seconds
            known[bucket] += seconds
            begin = bucket_end
    return [round(s / k, 3) if k else None for s, k in zip(sums, known, strict=True)]


def merge_means(
    series: list[float | None],
    rows: list[tuple[datetime, float | None]],
    start: datetime,
    step: timedelta,
) -> list[float | None]:
    """`series` with the buckets the recorder's statistics cover set to their means.

    `rows` are the statistics periods (their start, their mean), one bucket long
    and aligned on the buckets.
    """
    merged = list(series)
    for at, mean in rows:
        index = int((at - start) // step)
        if mean is not None and 0 <= index < len(merged):
            merged[index] = round(mean, 3)
    return merged


def on_intervals(
    samples: list[tuple[datetime, bool, str | None]],
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, datetime, str | None]]:
    """The periods a binary state was on within [start, end], with a label of each."""
    found: list[tuple[datetime, datetime, str | None]] = []
    for index, (at, on, label) in enumerate(samples):
        if not on:
            continue
        until = samples[index + 1][0] if index + 1 < len(samples) else end
        begin, finish = max(at, start), min(until, end)
        if begin >= finish:
            continue
        if found and found[-1][1] == begin and found[-1][2] == label:
            # The same shedding, recorded twice (an attribute changed).
            found[-1] = (found[-1][0], finish, label)
        else:
            found.append((begin, finish, label))
    return found


def value_before(
    series: list[float | None], start: datetime, at: datetime, step: timedelta
) -> float | None:
    """The last known bucket value before `at`: what an appliance drew before being shed."""
    index = int((at - start) // step)
    for bucket in range(min(index, len(series)) - 1, -1, -1):
        if series[bucket] is not None:
            return series[bucket]
    return None
