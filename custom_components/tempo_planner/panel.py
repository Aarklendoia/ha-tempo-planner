"""The Tempo Planner panel in the sidebar."""

from __future__ import annotations

from pathlib import Path

from homeassistant.core import HomeAssistant

from .const import DOMAIN

URL_PATH = "tempo-planner"
STATIC_URL = f"/{DOMAIN}_static"
WEBCOMPONENT = "tempo-planner-panel"
_STATIC_REGISTERED = f"{DOMAIN}_static_registered"


async def async_register_panel(hass: HomeAssistant, version: str) -> None:
    """Serve the panel's files and add it to the sidebar, for admins only.

    Without the frontend (tests, a headless install), there is nothing to show.
    """
    if "frontend" not in hass.config.components or getattr(hass, "http", None) is None:
        return

    # Imported here: the frontend is only an after-dependency.
    from homeassistant.components import panel_custom
    from homeassistant.components.http import StaticPathConfig

    if not hass.data.get(_STATIC_REGISTERED):
        # Served once per run: the files don't change until the next restart.
        await hass.http.async_register_static_paths(
            [StaticPathConfig(STATIC_URL, str(Path(__file__).parent / "frontend"), False)]
        )
        hass.data[_STATIC_REGISTERED] = True

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=URL_PATH,
        webcomponent_name=WEBCOMPONENT,
        sidebar_title="Tempo Planner",
        sidebar_icon="mdi:flash-alert",
        # The version busts the browser's cache after an update.
        module_url=f"{STATIC_URL}/tempo-planner-panel.js?v={version}",
        require_admin=True,
        # No config_panel_domain: the integration's Configure button would open
        # the panel instead of the options flow, which holds the settings.
    )


def async_remove_panel(hass: HomeAssistant) -> None:
    if "frontend" not in hass.config.components:
        return
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, URL_PATH, warn_if_unknown=False)
