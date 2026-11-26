"""Announcements of tomorrow's colour: their settings and their texts.

Pure Python, no Home Assistant import: everything here can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from enum import StrEnum
from typing import Any

from .planner import Color


class Channel(StrEnum):
    """How an announcement reaches the house."""

    NOTIFY = "notify"
    VOICE = "voice"


def _colors(values: Any, default: list[Color]) -> list[Color]:
    if values is None:
        return list(default)
    return [Color(c) for c in values if c != Color.UNKNOWN]


@dataclass
class AnnouncementSettings:
    """What is announced, when and to whom."""

    notify_enabled: bool = False
    notify_colors: list[Color] = field(default_factory=lambda: [Color.WHITE, Color.RED])
    # notify.* services.
    notify_targets: list[str] = field(default_factory=list)
    voice_enabled: bool = False
    voice_colors: list[Color] = field(default_factory=lambda: [Color.WHITE, Color.RED])
    voice_time: time = time(19, 0)
    tts_entity: str | None = None
    media_players: list[str] = field(default_factory=list)
    # Spoken only when someone is at home (zone.home counts the people in it).
    voice_only_home: bool = True
    # The speakers' volume (%) for the announcement; None: as they are.
    voice_volume: float | None = None
    # On the eve of a red day, the car under this charge (%) is to be plugged in.
    car_reminder_pct: float | None = 80.0

    def colors(self, channel: Channel) -> list[Color]:
        return self.notify_colors if channel is Channel.NOTIFY else self.voice_colors

    def enabled(self, channel: Channel) -> bool:
        if channel is Channel.NOTIFY:
            return self.notify_enabled and bool(self.notify_targets)
        return self.voice_enabled and bool(self.tts_entity) and bool(self.media_players)

    def to_dict(self) -> dict[str, Any]:
        return {
            "notify_enabled": self.notify_enabled,
            "notify_colors": [str(c) for c in self.notify_colors],
            "notify_targets": list(self.notify_targets),
            "voice_enabled": self.voice_enabled,
            "voice_colors": [str(c) for c in self.voice_colors],
            "voice_time": self.voice_time.strftime("%H:%M:%S"),
            "tts_entity": self.tts_entity,
            "media_players": list(self.media_players),
            "voice_only_home": self.voice_only_home,
            "voice_volume": self.voice_volume,
            "car_reminder_pct": self.car_reminder_pct,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnnouncementSettings:
        default = cls()
        at = data.get("voice_time")
        return cls(
            notify_enabled=bool(data.get("notify_enabled", default.notify_enabled)),
            notify_colors=_colors(data.get("notify_colors"), default.notify_colors),
            notify_targets=list(data.get("notify_targets") or []),
            voice_enabled=bool(data.get("voice_enabled", default.voice_enabled)),
            voice_colors=_colors(data.get("voice_colors"), default.voice_colors),
            voice_time=time.fromisoformat(at) if at else default.voice_time,
            tts_entity=data.get("tts_entity"),
            media_players=list(data.get("media_players") or []),
            voice_only_home=bool(data.get("voice_only_home", default.voice_only_home)),
            voice_volume=data.get("voice_volume"),
            car_reminder_pct=data.get("car_reminder_pct", default.car_reminder_pct),
        )

    def problems(self) -> list[str]:
        """What prevents the announcements from working, as translation keys."""
        found = []
        if any(not t.startswith("notify.") for t in self.notify_targets):
            found.append("notify_not_a_notify_service")
        if self.notify_enabled and not self.notify_targets:
            found.append("no_notify_target")
        if self.tts_entity and not self.tts_entity.startswith("tts."):
            found.append("tts_not_a_tts_entity")
        if self.voice_enabled and not (self.tts_entity and self.media_players):
            found.append("no_voice_target")
        return found


@dataclass(frozen=True)
class Tomorrow:
    """What an announcement says about the next Tempo day."""

    color: Color
    offpeak_start: time
    offpeak_end: time
    # The appliances shed tomorrow, by name.
    shed: list[str] = field(default_factory=list)
    # The car's charge (%), when it is to be plugged in tonight.
    car_pct: float | None = None


def car_to_plug(color: Color, car_pct: float | None, threshold: float | None) -> float | None:
    """The car's charge when it must be reminded, None otherwise."""
    if color is not Color.RED or car_pct is None or threshold is None:
        return None
    return car_pct if car_pct < threshold else None


_TEXTS: dict[str, dict[str, str]] = {
    "en": {
        "title_blue": "🔵 Blue day tomorrow",
        "title_white": "⚪ White day tomorrow",
        "title_red": "🔴 Red day tomorrow",
        "notify_blue": "Low price all day.",
        "notify_white": "Middle price: move what you can to the off-peak hours ({start} to {end}).",
        "notify_red": "Peak hours from {end} to {start}: avoid the big loads.",
        "notify_shed": " Shed: {names}.",
        "notify_car": " Car at {pct} %: plug it in tonight.",
        "voice_blue": "Tomorrow is a blue day.",
        "voice_white": "For your information, tomorrow is a white day."
        " Move what you can to the off-peak hours.",
        "voice_red": "Warning, tomorrow is a red day."
        " Avoid the big loads between {end} and {start}.",
        "voice_shed": " Shed tomorrow: {names}.",
        "voice_car": " The car is at {pct} percent, plug it in tonight.",
        "and": "and",
    },
    "fr": {
        "title_blue": "🔵 Jour bleu demain",
        "title_white": "⚪ Jour blanc demain",
        "title_red": "🔴 Jour rouge demain",
        "notify_blue": "Tarif bas toute la journée.",
        "notify_white": "Tarif intermédiaire : décale ce qui peut l'être en heures creuses"
        " (de {start} à {end}).",
        "notify_red": "Heures pleines de {end} à {start} : évite les gros consommateurs.",
        "notify_shed": " Délestés : {names}.",
        "notify_car": " Voiture à {pct} % : pense à la brancher cette nuit.",
        "voice_blue": "Demain est un jour bleu.",
        "voice_white": "Pour information, demain est un jour blanc."
        " Décalez ce qui peut l'être en heures creuses.",
        "voice_red": "Attention, demain est un jour rouge."
        " Évitez les gros consommateurs entre {end} et {start}.",
        "voice_shed": " Seront délestés : {names}.",
        "voice_car": " La voiture est à {pct} pour cent, pensez à la brancher cette nuit.",
        "and": "et",
    },
}


def _clock(at: time, language: str, voice: bool) -> str:
    if language == "fr":
        if voice:
            return f"{at.hour} heures {at.minute}" if at.minute else f"{at.hour} heures"
        return f"{at.hour} h {at.minute:02d}" if at.minute else f"{at.hour} h"
    return at.strftime("%H:%M")


def _names(names: list[str], word: str) -> str:
    if len(names) < 2:
        return "".join(names)
    return f"{', '.join(names[:-1])} {word} {names[-1]}"


def compose(tomorrow: Tomorrow, language: str, channel: Channel) -> tuple[str, str]:
    """The title and the message announcing tomorrow, in the house's language."""
    lang = language.split("-")[0]
    if lang not in _TEXTS:
        lang = "en"
    texts = _TEXTS[lang]
    color = tomorrow.color if tomorrow.color is not Color.UNKNOWN else Color.WHITE
    voice = channel is Channel.VOICE
    prefix = "voice" if voice else "notify"
    hours = {
        "start": _clock(tomorrow.offpeak_start, lang, voice),
        "end": _clock(tomorrow.offpeak_end, lang, voice),
    }
    message = texts[f"{prefix}_{color}"].format(**hours)
    if tomorrow.shed:
        message += texts[f"{prefix}_shed"].format(names=_names(tomorrow.shed, texts["and"]))
    if tomorrow.car_pct is not None:
        message += texts[f"{prefix}_car"].format(pct=round(tomorrow.car_pct))
    return texts[f"title_{color}"], message
