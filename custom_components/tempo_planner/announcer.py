"""Announce tomorrow's colour: a notification once it is known, a voice in the evening."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from . import const
from .announcements import AnnouncementSettings, Channel, Tomorrow, car_to_plug, compose
from .load_shedding import LoadShedder, signal_update
from .planner import Color, Settings, parse_color, tempo_day
from .shedding import Behaviour

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


class Announcer:
    """Announces the next Tempo day, at most once per channel, day and colour."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        settings: Settings,
        config: dict,
        shedder: LoadShedder,
    ):
        self.hass = hass
        self.entry_id = entry_id
        self._settings = settings
        self._tomorrow_entity: str | None = config.get(const.CONF_TOMORROW_COLOR)
        self._car_entity: str | None = config.get(const.CONF_CAR_SOC)
        self._shedder = shedder
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{const.DOMAIN}.{entry_id}.announcements"
        )
        self.settings = AnnouncementSettings()
        # What each channel announced last: the day and its colour.
        self._sent: dict[Channel, tuple[date, Color]] = {}
        self._unsubs: list[Callable[[], None]] = []

    # --- Life cycle -------------------------------------------------------

    async def async_load(self) -> None:
        stored = await self._store.async_load() or {}
        try:
            self.settings = AnnouncementSettings.from_dict(stored.get("settings") or {})
        except (TypeError, ValueError):
            _LOGGER.warning("Ignoring stored announcement settings that cannot be read")
        for channel, (day, color) in (stored.get("sent") or {}).items():
            try:
                self._sent[Channel(channel)] = (date.fromisoformat(day), Color(color))
            except ValueError:
                continue

    async def async_start(self) -> None:
        if self._tomorrow_entity:
            self._unsubs.append(
                async_track_state_change_event(self.hass, self._tomorrow_entity, self._on_tomorrow)
            )
        at = self.settings.voice_time
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._on_voice_time, hour=at.hour, minute=at.minute, second=at.second
            )
        )
        # Known while Home Assistant was down: announced now, if not yet.
        await self.async_announce(Channel.NOTIFY)

    async def async_stop(self) -> None:
        await self._store.async_save(self._data())
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    async def async_save(self, data: dict[str, Any]) -> AnnouncementSettings:
        """New settings; the voice follows its new time."""
        self.settings = AnnouncementSettings.from_dict(data)
        self._save()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        await self.async_start()
        async_dispatcher_send(self.hass, signal_update(self.entry_id))
        return self.settings

    # --- Announcing -------------------------------------------------------

    @callback
    def _on_tomorrow(self, _: Event[EventStateChangedData]) -> None:
        self.hass.async_create_task(self.async_announce(Channel.NOTIFY))

    @callback
    def _on_voice_time(self, _: datetime) -> None:
        self.hass.async_create_task(self.async_announce(Channel.VOICE))

    def tomorrow(self, color: Color | None = None) -> Tomorrow:
        """The next Tempo day as it stands now, or as if it were of `color`."""
        if color is None:
            state = self.hass.states.get(self._tomorrow_entity) if self._tomorrow_entity else None
            color = parse_color(state.state if state else None)
        return Tomorrow(
            color=color,
            offpeak_start=self._settings.offpeak_start,
            offpeak_end=self._settings.offpeak_end,
            shed=[
                a.name
                for a in sorted(
                    self._shedder.appliances.values(), key=lambda a: (a.priority, a.name)
                )
                if a.enabled and a.behaviour is not Behaviour.ALERT and color in a.colors
            ],
            car_pct=car_to_plug(color, self._car_pct(), self.settings.car_reminder_pct),
        )

    async def async_announce(self, channel: Channel) -> bool:
        """Announce tomorrow on a channel if it is due; whether it was."""
        tomorrow = self.tomorrow()
        if not self.settings.enabled(channel) or tomorrow.color not in self.settings.colors(
            channel
        ):
            return False
        day = tempo_day(dt_util.now(), self._settings) + timedelta(days=1)
        if self._sent.get(channel) == (day, tomorrow.color):
            return False
        if channel is Channel.VOICE and self.settings.voice_only_home and not self._home():
            return False
        self._sent[channel] = (day, tomorrow.color)
        self._save()
        await self._send(channel, tomorrow)
        return True

    async def async_test(self, channel: Channel) -> None:
        """Announce now, whatever the settings say: tomorrow, or a red day when unknown."""
        tomorrow = self.tomorrow()
        if tomorrow.color is Color.UNKNOWN:
            tomorrow = self.tomorrow(Color.RED)
        await self._send(channel, tomorrow)

    async def _send(self, channel: Channel, tomorrow: Tomorrow) -> None:
        language = self.hass.config.language
        title, message = compose(tomorrow, language, channel)
        if channel is Channel.NOTIFY:
            for target in self.settings.notify_targets:
                domain, service = target.split(".", 1)
                await self._call(domain, service, {"title": title, "message": message})
            return
        data = {
            "entity_id": self.settings.tts_entity,
            "media_player_entity_id": self.settings.media_players,
            "message": message,
        }
        # The engine may not know the bare language: then its own default.
        if not await self._call("tts", "speak", {**data, "language": language}, quiet=True):
            await self._call("tts", "speak", data)

    async def _call(
        self, domain: str, service: str, data: dict[str, Any], quiet: bool = False
    ) -> bool:
        try:
            await self.hass.services.async_call(domain, service, data, blocking=True)
        except HomeAssistantError as err:
            if not quiet:
                _LOGGER.warning("Announcement: %s.%s failed: %s", domain, service, err)
            return False
        return True

    def _home(self) -> bool:
        """Whether someone is at home; true when it can't be told."""
        state = self.hass.states.get("zone.home")
        try:
            return int(state.state) > 0 if state else True
        except ValueError:
            return True

    def _car_pct(self) -> float | None:
        state = self.hass.states.get(self._car_entity) if self._car_entity else None
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    # --- Storage ----------------------------------------------------------

    def _save(self) -> None:
        self._store.async_delay_save(self._data, 1)

    def _data(self) -> dict[str, Any]:
        return {
            "settings": self.settings.to_dict(),
            "sent": {str(c): [d.isoformat(), str(col)] for c, (d, col) in self._sent.items()},
        }
