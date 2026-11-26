"""Announcements of tomorrow's colour inside Home Assistant."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.tempo_planner import const

from .conftest import PARIS
from .test_init import ENTITIES, SETTINGS
from .test_load_shedding import move_to, save

TOMORROW = "sensor.rte_tempo_prochaine_couleur"

NOTIFY = {"notify_enabled": True, "notify_targets": ["notify.famille"]}
VOICE = {
    "voice_enabled": True,
    "tts_entity": "tts.google",
    "media_players": ["media_player.kitchen", "media_player.living_room"],
}


@pytest.fixture
async def planner(hass: HomeAssistant, house) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=const.DOMAIN, data=ENTITIES, options=SETTINGS, unique_id=const.DOMAIN
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def calls(hass: HomeAssistant) -> dict[str, list]:
    return {
        "notify": async_mock_service(hass, "notify", "famille"),
        "speak": async_mock_service(hass, "tts", "speak"),
    }


async def configure(client, **settings) -> dict:
    await client.send_json_auto_id(
        {"type": "tempo_planner/announcements/save", "announcements": settings}
    )
    return await client.receive_json()


async def test_notified_once_when_tomorrow_is_known(
    hass: HomeAssistant,
    planner,
    calls,
    hass_ws_client,
) -> None:
    client = await hass_ws_client(hass)
    assert (await save(client, name="Tree", entity_id="light.tree", colors=["red"]))["success"]
    hass.states.async_set("sensor.car_battery", "62")
    hass.states.async_set(TOMORROW, "unavailable")
    reply = await configure(client, **NOTIFY)
    assert reply["success"], reply
    await hass.async_block_till_done()
    assert calls["notify"] == []

    hass.states.async_set(TOMORROW, "Rouge")
    await hass.async_block_till_done()
    assert len(calls["notify"]) == 1
    data = calls["notify"][0].data
    assert data["title"] == "🔴 Red day tomorrow"
    assert data["message"] == (
        "Peak hours from 06:00 to 22:00: avoid the big loads."
        " Shed: Tree. Car at 62 %: plug it in tonight."
    )

    # The sensor flickers: no second notification for the same day.
    hass.states.async_set(TOMORROW, "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set(TOMORROW, "Rouge")
    await hass.async_block_till_done()
    assert len(calls["notify"]) == 1


async def test_known_colour_notified_when_turned_on_blue_never(
    hass: HomeAssistant,
    planner,
    calls,
    hass_ws_client,
) -> None:
    client = await hass_ws_client(hass)
    # Tomorrow is white in the house: announced as soon as it is turned on.
    assert (await configure(client, **NOTIFY))["success"]
    await hass.async_block_till_done()
    assert [c.data["title"] for c in calls["notify"]] == ["⚪ White day tomorrow"]
    # Saved again: already announced.
    assert (await configure(client, **NOTIFY))["success"]
    await hass.async_block_till_done()
    assert len(calls["notify"]) == 1

    hass.states.async_set(TOMORROW, "Bleu")
    await hass.async_block_till_done()
    assert len(calls["notify"]) == 1


async def test_voice_in_the_evening_when_someone_is_home(
    hass: HomeAssistant,
    planner,
    calls,
    hass_ws_client,
    freezer: FrozenDateTimeFactory,
) -> None:
    hass.states.async_set("zone.home", "0")
    client = await hass_ws_client(hass)
    assert (await configure(client, **VOICE))["success"]
    await hass.async_block_till_done()
    assert calls["speak"] == []

    # Nobody at home at 19:00: silent.
    await move_to(hass, freezer, datetime(2026, 11, 23, 19, 0, tzinfo=PARIS))
    assert calls["speak"] == []

    hass.states.async_set("zone.home", "2")
    await move_to(hass, freezer, datetime(2026, 11, 24, 19, 0, tzinfo=PARIS))
    assert len(calls["speak"]) == 1
    data = calls["speak"][0].data
    assert data["entity_id"] == "tts.google"
    assert data["media_player_entity_id"] == ["media_player.kitchen", "media_player.living_room"]
    assert data["language"] == "en"
    assert data["message"].startswith("For your information, tomorrow is a white day.")


async def test_voice_time_follows_the_settings(
    hass: HomeAssistant,
    planner,
    calls,
    hass_ws_client,
    freezer: FrozenDateTimeFactory,
) -> None:
    client = await hass_ws_client(hass)
    assert (await configure(client, **VOICE, voice_time="18:30"))["success"]
    await move_to(hass, freezer, datetime(2026, 11, 23, 18, 30, tzinfo=PARIS))
    assert len(calls["speak"]) == 1
    await move_to(hass, freezer, datetime(2026, 11, 23, 19, 0, tzinfo=PARIS))
    assert len(calls["speak"]) == 1


async def test_test_command_and_snapshot(
    hass: HomeAssistant,
    planner,
    calls,
    hass_ws_client,
) -> None:
    client = await hass_ws_client(hass)
    hass.states.async_set(TOMORROW, "unknown")
    assert (await configure(client, notify_targets=["notify.famille"]))["success"]
    await client.send_json_auto_id(
        {"type": "tempo_planner/announcements/test", "channel": "notify"}
    )
    reply = await client.receive_json()
    assert reply["success"], reply
    await hass.async_block_till_done()
    # Tomorrow unknown: a red day as an example, though announcements are off.
    assert [c.data["title"] for c in calls["notify"]] == ["🔴 Red day tomorrow"]

    await client.send_json_auto_id({"type": "tempo_planner/subscribe"})
    assert (await client.receive_json())["success"]
    event = await client.receive_json()
    assert event["event"]["announcements"]["notify_targets"] == ["notify.famille"]
    assert event["event"]["announcements"]["voice_time"] == "19:00:00"


async def test_invalid_settings(hass: HomeAssistant, planner, hass_ws_client) -> None:
    client = await hass_ws_client(hass)
    reply = await configure(client, notify_enabled=True)
    assert reply["error"]["code"] == "invalid_announcements"
    reply = await configure(client, voice_time="25:00")
    assert reply["error"]["code"] == "invalid_format"


async def test_settings_kept_across_a_reload(
    hass: HomeAssistant,
    planner,
    calls,
    hass_ws_client,
) -> None:
    client = await hass_ws_client(hass)
    assert (await configure(client, **NOTIFY))["success"]
    await hass.async_block_till_done()
    assert len(calls["notify"]) == 1
    assert await hass.config_entries.async_reload(planner.entry_id)
    await hass.async_block_till_done()
    announcer = planner.runtime_data.announcer
    assert announcer.settings.notify_targets == ["notify.famille"]
    # Already announced before the reload.
    assert len(calls["notify"]) == 1
