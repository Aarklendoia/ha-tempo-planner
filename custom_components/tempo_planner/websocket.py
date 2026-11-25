"""WebSocket commands to read and change the sheddable appliances."""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util
import voluptuous as vol

from . import const
from .coordinator import TempoPlannerCoordinator, entry_config
from .load_shedding import LoadShedder, signal_update
from .planner import Color
from .shedding import Appliance, Behaviour, Hours, problems

_APPLIANCE = vol.Schema(
    {
        vol.Optional("id"): cv.string,
        vol.Required("name"): vol.All(cv.string, vol.Length(min=1)),
        vol.Required("entity_id"): cv.entity_id,
        vol.Optional("behaviour", default=str(Behaviour.OFF)): vol.In([str(b) for b in Behaviour]),
        vol.Optional("reduced_option"): vol.Any(None, cv.string),
        vol.Optional("running_entity"): vol.Any(None, cv.entity_id),
        vol.Optional("running_above", default=50.0): vol.Coerce(float),
        vol.Optional("running_states", default=["on"]): [cv.string],
        vol.Optional("colors", default=[str(Color.RED)]): [
            vol.In([str(Color.BLUE), str(Color.WHITE), str(Color.RED)])
        ],
        vol.Optional("hours", default=str(Hours.PEAK)): vol.In([str(h) for h in Hours]),
        vol.Optional("notify"): vol.Any(None, cv.string),
        vol.Optional("priority", default=0): vol.Coerce(int),
        vol.Optional("power_entity"): vol.Any(None, cv.entity_id),
        vol.Optional("power_kw"): vol.Any(None, vol.All(vol.Coerce(float), vol.Range(min=0))),
        vol.Optional("enabled", default=True): cv.boolean,
        vol.Optional("schedule_blue"): vol.Any(None, cv.entity_id),
        vol.Optional("schedule_white"): vol.Any(None, cv.entity_id),
        vol.Optional("schedule_red"): vol.Any(None, cv.entity_id),
        vol.Optional("normal_option"): vol.Any(None, cv.string),
    }
)


@callback
def async_register(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_save)
    websocket_api.async_register_command(hass, ws_delete)
    websocket_api.async_register_command(hass, ws_subscribe)


def _coordinator(hass: HomeAssistant) -> TempoPlannerCoordinator | None:
    for entry in hass.config_entries.async_loaded_entries(const.DOMAIN):
        return entry.runtime_data
    return None


def _shedder(hass: HomeAssistant) -> LoadShedder | None:
    coordinator = _coordinator(hass)
    return coordinator.shedder if coordinator else None


def snapshot(coordinator: TempoPlannerCoordinator) -> dict[str, Any]:
    """Where the house stands, for the panel."""
    settings = coordinator.settings
    clock = dt_util.now().time()
    plan = coordinator.data
    return {
        "today": str(coordinator.shedder.color()),
        "tomorrow": str(plan.tomorrow) if plan else None,
        "offpeak": not (settings.offpeak_end <= clock < settings.offpeak_start),
        "offpeak_start": settings.offpeak_start.strftime("%H:%M"),
        "offpeak_end": settings.offpeak_end.strftime("%H:%M"),
        "today_color_entity": entry_config(coordinator.config_entry).get(const.CONF_TODAY_COLOR),
        "appliances": coordinator.shedder.as_list(),
    }


def _not_loaded(connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    connection.send_error(msg["id"], "not_loaded", "Tempo Planner is not loaded")


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "tempo_planner/appliances/list"})
@callback
def ws_list(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    if (shedder := _shedder(hass)) is None:
        _not_loaded(connection, msg)
        return
    connection.send_result(msg["id"], {"appliances": shedder.as_list()})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "tempo_planner/appliances/save", vol.Required("appliance"): dict}
)
@websocket_api.async_response
async def ws_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    if (shedder := _shedder(hass)) is None:
        _not_loaded(connection, msg)
        return
    try:
        data = _APPLIANCE(msg["appliance"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    if data.get("id") and data["id"] not in shedder.appliances:
        connection.send_error(msg["id"], "not_found", f"No appliance {data['id']}")
        return
    if found := problems(Appliance.from_dict({**data, "id": data.get("id") or "new"})):
        connection.send_error(msg["id"], "invalid_appliance", ", ".join(found))
        return
    appliance = await shedder.async_save_appliance(data)
    connection.send_result(msg["id"], {"appliance": appliance.to_dict()})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "tempo_planner/appliances/delete",
        vol.Required("appliance_id"): cv.string,
    }
)
@websocket_api.async_response
async def ws_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    if (shedder := _shedder(hass)) is None:
        _not_loaded(connection, msg)
        return
    try:
        await shedder.async_delete_appliance(msg["appliance_id"])
    except KeyError:
        connection.send_error(msg["id"], "not_found", f"No appliance {msg['appliance_id']}")
        return
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "tempo_planner/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """The snapshot now, then again whenever the plan or the shedding changes."""
    if (coordinator := _coordinator(hass)) is None:
        _not_loaded(connection, msg)
        return

    @callback
    def _send() -> None:
        connection.send_message(websocket_api.event_message(msg["id"], snapshot(coordinator)))

    unsubs = [
        async_dispatcher_connect(hass, signal_update(coordinator.shedder.entry_id), _send),
        coordinator.async_add_listener(_send),
    ]

    @callback
    def _unsubscribe() -> None:
        for unsub in unsubs:
            unsub()

    connection.subscriptions[msg["id"]] = _unsubscribe
    connection.send_result(msg["id"])
    _send()
