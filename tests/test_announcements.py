"""Announcements of tomorrow's colour: settings and texts."""

from datetime import time

from custom_components.tempo_planner.announcements import (
    AnnouncementSettings,
    Channel,
    Tomorrow,
    car_to_plug,
    compose,
)
from custom_components.tempo_planner.planner import Color

HOURS = {"offpeak_start": time(22, 0), "offpeak_end": time(6, 0)}


def test_red_notification_in_french() -> None:
    tomorrow = Tomorrow(
        Color.RED, shed=["Sapin", "Sèche-serviette", "Chauffe-eau"], car_pct=62, **HOURS
    )
    title, message = compose(tomorrow, "fr", Channel.NOTIFY)
    assert title == "🔴 Jour rouge demain"
    assert message == (
        "Heures pleines de 6 h à 22 h : évite les gros consommateurs."
        " Délestés : Sapin, Sèche-serviette et Chauffe-eau."
        " Voiture à 62 % : pense à la brancher cette nuit."
    )


def test_red_voice_in_french() -> None:
    tomorrow = Tomorrow(Color.RED, shed=["Sapin"], **HOURS)
    _, message = compose(tomorrow, "fr-FR", Channel.VOICE)
    assert message == (
        "Attention, demain est un jour rouge. Évitez les gros consommateurs"
        " entre 6 heures et 22 heures. Seront délestés : Sapin."
    )


def test_white_in_english_with_minutes() -> None:
    tomorrow = Tomorrow(Color.WHITE, offpeak_start=time(22, 30), offpeak_end=time(6, 30))
    title, message = compose(tomorrow, "en", Channel.NOTIFY)
    assert title == "⚪ White day tomorrow"
    assert message == "Middle price: move what you can to the off-peak hours (22:30 to 06:30)."
    _, message = compose(tomorrow, "fr", Channel.NOTIFY)
    assert "(de 22 h 30 à 6 h 30)" in message
    _, message = compose(tomorrow, "fr", Channel.VOICE)
    assert message.startswith("Pour information, demain est un jour blanc.")


def test_unknown_language_is_english() -> None:
    title, _ = compose(Tomorrow(Color.BLUE, **HOURS), "de", Channel.NOTIFY)
    assert title == "🔵 Blue day tomorrow"


def test_car_reminder_on_red_days_under_the_threshold() -> None:
    assert car_to_plug(Color.RED, 62, 80) == 62
    assert car_to_plug(Color.RED, 85, 80) is None
    assert car_to_plug(Color.WHITE, 62, 80) is None
    assert car_to_plug(Color.RED, None, 80) is None
    assert car_to_plug(Color.RED, 62, None) is None


def test_settings_round_trip_and_defaults() -> None:
    default = AnnouncementSettings()
    assert default.notify_colors == [Color.WHITE, Color.RED]
    assert default.voice_time == time(19, 0)
    assert not default.enabled(Channel.NOTIFY)
    assert AnnouncementSettings.from_dict({}) == default

    settings = AnnouncementSettings(
        notify_enabled=True,
        notify_colors=[Color.RED],
        notify_targets=["notify.famille"],
        voice_enabled=True,
        voice_time=time(19, 30),
        tts_entity="tts.google",
        media_players=["media_player.kitchen"],
        car_reminder_pct=None,
        voice_volume=70,
    )
    assert AnnouncementSettings.from_dict(settings.to_dict()) == settings
    assert settings.enabled(Channel.NOTIFY) and settings.enabled(Channel.VOICE)
    assert settings.colors(Channel.NOTIFY) == [Color.RED]


def test_settings_problems() -> None:
    assert AnnouncementSettings().problems() == []
    settings = AnnouncementSettings(
        notify_enabled=True, voice_enabled=True, tts_entity="media_player.kitchen"
    )
    assert settings.problems() == ["no_notify_target", "tts_not_a_tts_entity", "no_voice_target"]
    assert AnnouncementSettings(notify_targets=["famille"]).problems() == [
        "notify_not_a_notify_service"
    ]
