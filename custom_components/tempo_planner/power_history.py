"""The power chart: the recorder's history read into series for the panel."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import const
from .chart import bucket_means, on_intervals, value_before
from .coordinator import TempoPlannerCoordinator
from .planner import tempo_day
from .shedding import to_kw

_LOGGER = logging.getLogger(__name__)

STEP = timedelta(minutes=5)


async def async_power_history(
    hass: HomeAssistant, coordinator: TempoPlannerCoordinator, hours: int
) -> dict[str, Any]:
    """The last hours of grid power, limits, appliance power and shedding."""
    shedder = coordinator.shedder
    settings = coordinator.settings
    end = dt_util.now()
    # Buckets on round 5 minutes, the last one in progress.
    end_bucket = end.replace(second=0, microsecond=0)
    end_bucket += timedelta(minutes=5 - end_bucket.minute % 5)
    start = end_bucket - timedelta(hours=hours)
    count = int((end_bucket - start) // STEP)

    registry = er.async_get(hass)
    appliances = sorted(shedder.appliances.values(), key=lambda a: (a.priority, a.name))
    shed_entities = {
        a.id: registry.async_get_entity_id(
            "binary_sensor", const.DOMAIN, f"{shedder.entry_id}_{a.id}_shed"
        )
        for a in appliances
    }
    grid = shedder.power.power_entity
    house = shedder.power.house_entity
    powers = [e for e in {a.power_entity for a in appliances} | {grid, house} if e]
    states = await _async_states(hass, powers, start, end, attributes=False)
    sheds = await _async_states(
        hass, [e for e in shed_entities.values() if e], start, end, attributes=True
    )

    def series(entity_id: str | None) -> list[float | None] | None:
        if not entity_id:
            return None
        current = hass.states.get(entity_id)
        unit = current.attributes.get("unit_of_measurement") if current else None
        samples = [
            (state.last_changed, None if _missing(state) else to_kw(state.state, unit))
            for state in states.get(entity_id, [])
        ]
        return bucket_means(samples, start, end, STEP)[:count]

    soft = []
    for index in range(count):
        at = dt_util.as_local(start + STEP * index)
        day = tempo_day(at, settings)
        color = shedder.color() if day == tempo_day(end, settings) else coordinator.color_of(day)
        offpeak = not (settings.offpeak_end <= at.time() < settings.offpeak_start)
        soft.append(shedder.power.soft_for(color, offpeak))

    slots = {appliance_id: index for index, appliance_id in enumerate(shedder.appliances)}
    result = []
    for appliance in appliances:
        power = series(appliance.power_entity)
        samples = [
            (state.last_changed, state.state == STATE_ON, state.attributes.get("reason"))
            for state in sheds.get(shed_entities[appliance.id] or "", [])
            if not _missing(state)
        ]
        shed = []
        for begin, finish, reason in on_intervals(samples, start, end):
            avoided = value_before(power, start, begin, STEP) if power else None
            if avoided is None:
                avoided = appliance.power_kw
            shed.append(
                {
                    "start": dt_util.as_local(begin).isoformat(),
                    "end": dt_util.as_local(finish).isoformat(),
                    "reason": reason,
                    "avoided_kw": avoided,
                }
            )
        result.append(
            {
                "id": appliance.id,
                "name": appliance.name,
                # Its colour follows the appliance (the order it was added), not its priority.
                "slot": slots[appliance.id],
                "power": power,
                "shed": shed,
            }
        )

    return {
        "start": start.isoformat(),
        "step": int(STEP.total_seconds()),
        "count": count,
        "now": end.isoformat(),
        "grid": series(grid),
        "house": series(house),
        "soft": soft,
        "hard": shedder.power.hard_limit_kw,
        "appliances": result,
    }


async def _async_states(
    hass: HomeAssistant,
    entity_ids: list[str],
    start: datetime,
    end: datetime,
    attributes: bool,
) -> dict[str, list[State]]:
    if not entity_ids or "recorder" not in hass.config.components:
        return {}

    # Imported here: the recorder is only an after-dependency.
    from homeassistant.components.recorder import get_instance, history

    try:
        found = await get_instance(hass).async_add_executor_job(
            history.get_significant_states,
            hass,
            start,
            end,
            entity_ids,
            None,
            True,  # include_start_time_state
            False,  # significant_changes_only
            False,  # minimal_response
            not attributes,  # no_attributes
        )
    except Exception:  # noqa: BLE001 - a chart without history is still a chart
        _LOGGER.exception("Cannot read the history of %s", entity_ids)
        return {}
    return {
        entity_id: sorted(states, key=lambda s: s.last_changed)
        for entity_id, states in found.items()
    }


def _missing(state: State) -> bool:
    return state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
