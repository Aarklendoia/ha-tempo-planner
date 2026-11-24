"""When tomorrow's solar surplus is worth charging the car rather than selling it.

Pure Python, no Home Assistant import.

A car draws its full charging power: what the surplus does not cover comes
from the grid, or from the home battery, which then lacks for the evening's
peak hours; both are priced at the peak price. Charging during the day beats
charging the next night when the share `s` of the car's power covered by
surplus (otherwise sold) satisfies

    (1 - s) * peak + s * resale < off-peak,  that is  s > (peak - off-peak) / (peak - resale)

Surplus only counts once the home battery cannot take it: full, or charging
at its maximum power. Solar and battery reach the house through a hybrid
inverter, whose rating caps their output together.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class House:
    """What the simulation needs to know about the house."""

    inverter_kw: float
    battery_capacity_kwh: float
    battery_reserve_pct: float
    battery_charge_kw: float
    car_charge_kw: float


@dataclass(frozen=True)
class SolarWindow:
    """Tomorrow's hours worth a car charge from the surplus."""

    # Share of the car's power the surplus must cover.
    min_share: float
    # Energy sold without the car, kWh.
    sold_kwh: float
    start: datetime | None = None
    end: datetime | None = None
    # Energy the car can take in the window, kWh.
    car_kwh: float = 0.0


def min_surplus_share(peak: float, offpeak: float, resale: float) -> float:
    """Share of the car's power the surplus must cover to beat the night."""
    if peak <= offpeak:
        # The night is not cheaper: any surplus helps.
        return 0.0
    if peak <= resale:
        return 1.0
    return min(1.0, (peak - offpeak) / (peak - resale))


def sold_per_hour(
    solar_kwh: dict[datetime, float],
    load_kwh: dict[int, float],
    battery_soc_pct: float,
    house: House,
) -> dict[datetime, float]:
    """Energy sold each hour without the car, simulating the home battery.

    `solar_kwh` is the forecast production of each hour (by its start),
    `load_kwh` the house's usual consumption for each hour of the day.
    """
    stored = battery_soc_pct / 100 * house.battery_capacity_kwh
    floor = house.battery_reserve_pct / 100 * house.battery_capacity_kwh
    sold: dict[datetime, float] = {}
    for start in sorted(solar_kwh):
        solar = solar_kwh[start]
        load = load_kwh.get(start.hour, 0.0)
        if solar >= load:
            room = house.battery_capacity_kwh - stored
            to_battery = min(solar - load, house.battery_charge_kw, room)
            stored += to_battery
            # Solar reaches the house and the grid through the inverter.
            out = min(solar - to_battery, house.inverter_kw)
            sold[start] = max(0.0, out - load)
        else:
            stored = max(floor, stored - (load - solar))
            sold[start] = 0.0
    return sold


def solar_window(
    solar_kwh: dict[datetime, float],
    load_kwh: dict[int, float],
    battery_soc_pct: float,
    car_room_kwh: float,
    peak: float,
    offpeak: float,
    resale: float,
    house: House,
) -> SolarWindow:
    """Tomorrow's window for a car charge from the surplus."""
    share = min_surplus_share(peak, offpeak, resale)
    sold = sold_per_hour(solar_kwh, load_kwh, battery_soc_pct, house)
    window = SolarWindow(min_share=round(share, 3), sold_kwh=round(sum(sold.values()), 2))
    good = [h for h, kwh in sorted(sold.items()) if kwh > 0 and kwh >= share * house.car_charge_kw]
    if not good or car_room_kwh <= 0:
        return window
    # From the first to the last good hour; the car stops at its target.
    start, last = good[0], good[-1]
    hours = len([h for h in sold if start <= h <= last])
    car_kwh = min(car_room_kwh, hours * house.car_charge_kw)
    return SolarWindow(
        min_share=window.min_share,
        sold_kwh=window.sold_kwh,
        start=start,
        end=last + timedelta(hours=1),
        car_kwh=round(car_kwh, 2),
    )


def hourly_profile(hours: list[tuple[datetime, float]], days: int) -> dict[int, float]:
    """Average consumption of each hour of the day over the last `days` days."""
    recent = sorted({start.date() for start, _ in hours}, reverse=True)[:days]
    keep = set(recent)
    sums: dict[int, list[float]] = {}
    for start, kwh in hours:
        if start.date() in keep:
            sums.setdefault(start.hour, []).append(kwh)
    return {hour: round(sum(v) / len(v), 3) for hour, v in sums.items()}
