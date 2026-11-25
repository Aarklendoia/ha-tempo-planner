"""The panel: its registration and the live snapshot it reads."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tempo_planner import const

from .test_init import ENTITIES, SETTINGS


async def setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=const.DOMAIN, data=ENTITIES, options=SETTINGS, unique_id=const.DOMAIN
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_panel_registered_with_the_frontend(hass: HomeAssistant, house) -> None:
    hass.config.components.add("frontend")
    with (
        patch(
            "homeassistant.components.panel_custom.async_register_panel", AsyncMock()
        ) as register,
        patch("homeassistant.components.frontend.async_remove_panel") as remove,
        patch(
            "homeassistant.components.http.HomeAssistantHTTP.async_register_static_paths",
            AsyncMock(),
        ) as static_paths,
    ):
        entry = await setup(hass)
        kwargs = register.call_args.kwargs
        assert kwargs["frontend_url_path"] == "tempo-planner"
        assert kwargs["webcomponent_name"] == "tempo-planner-panel"
        # The Configure button keeps opening the options.
        assert "config_panel_domain" not in kwargs
        assert kwargs["require_admin"] is True
        assert kwargs["module_url"].startswith("/tempo_planner_static/tempo-planner-panel.js?v=")
        static = static_paths.call_args.args[0][0]
        assert static.url_path == "/tempo_planner_static"
        assert static.path.endswith("tempo_planner/frontend")

        # Reloaded: the panel again, the files only once.
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert register.call_count == 2
        assert static_paths.call_count == 1
        assert remove.call_count == 1


async def test_no_panel_without_the_frontend(hass: HomeAssistant, house) -> None:
    with patch(
        "homeassistant.components.panel_custom.async_register_panel", AsyncMock()
    ) as register:
        await setup(hass)
    register.assert_not_called()


async def test_subscribe(hass: HomeAssistant, house, hass_ws_client) -> None:
    await setup(hass)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "tempo_planner/subscribe"})
    assert (await client.receive_json())["success"]
    snapshot = (await client.receive_json())["event"]
    assert snapshot["today"] == "blue"
    assert snapshot["tomorrow"] == "white"
    # 16:00: peak hours.
    assert snapshot["offpeak"] is False
    assert snapshot["offpeak_start"] == "22:00"
    assert snapshot["offpeak_end"] == "06:00"
    assert snapshot["today_color_entity"] == "sensor.rte_tempo_couleur_actuelle"
    assert snapshot["appliances"] == []

    # An appliance added: a new snapshot with it.
    await client.send_json_auto_id(
        {
            "type": "tempo_planner/appliances/save",
            "appliance": {"name": "Tree", "entity_id": "light.tree"},
        }
    )
    names = []
    while True:
        message = await client.receive_json()
        if message.get("type") == "event":
            names = [a["name"] for a in message["event"]["appliances"]]
            if names:
                break
    assert names == ["Tree"]
