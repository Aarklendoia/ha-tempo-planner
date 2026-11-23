"""Plain-language explanations of the plan, for the dashboard."""

from __future__ import annotations

from .planner import Reason

_TEXTS: dict[str, dict[Reason, str]] = {
    "en": {
        Reason.COLOR_UNKNOWN: "Tomorrow's colour is not published yet: planned as a white day.",
        Reason.BATTERY_SOLAR_COVERS: "The sun should cover peak hours: no grid charge.",
        Reason.BATTERY_BLUE_NO_GRID: "Blue day: the battery stays off the grid.",
        Reason.BATTERY_ALREADY_FULL: "The battery already holds enough for peak hours.",
        Reason.BATTERY_CHARGE: "The battery charges in off-peak hours for tomorrow's peak hours.",
        Reason.BATTERY_UNKNOWN_SOC: "Battery level unknown.",
        Reason.CAR_FULL: "The car is at its target.",
        Reason.CAR_BELOW_MINIMUM: "The car is close to its target: not worth a charge.",
        Reason.CAR_UNKNOWN_SOC: "Car level unknown.",
        Reason.CAR_NOT_PLUGGED: "The car is not plugged in.",
        Reason.CAR_OVERFLOWS_OFFPEAK: "The car cannot finish within off-peak hours.",
        Reason.DISHWASHER_SOLAR: "Sunny blue day: the dishwasher runs around the solar peak.",
        Reason.DISHWASHER_NIGHT: "The dishwasher runs at night, after the battery.",
        Reason.PEAK_OVER_LIMIT: "The planned loads exceed the available power.",
    },
    "fr": {
        Reason.COLOR_UNKNOWN: "Couleur de demain pas encore publiée : prévu comme un jour blanc.",
        Reason.BATTERY_SOLAR_COVERS: "Le soleil couvrira les heures pleines : pas de charge.",
        Reason.BATTERY_BLUE_NO_GRID: "Jour bleu : la batterie ne charge pas sur le réseau.",
        Reason.BATTERY_ALREADY_FULL: "La batterie a déjà de quoi passer les heures pleines.",
        Reason.BATTERY_CHARGE: "La batterie charge en heures creuses pour les heures pleines.",
        Reason.BATTERY_UNKNOWN_SOC: "Niveau de la batterie inconnu.",
        Reason.CAR_FULL: "La voiture est à son objectif.",
        Reason.CAR_BELOW_MINIMUM: "La voiture est presque à son objectif : pas de charge.",
        Reason.CAR_UNKNOWN_SOC: "Niveau de la voiture inconnu.",
        Reason.CAR_NOT_PLUGGED: "La voiture n'est pas branchée.",
        Reason.CAR_OVERFLOWS_OFFPEAK: "La voiture ne peut pas finir en heures creuses.",
        Reason.DISHWASHER_SOLAR: "Jour bleu ensoleillé : lave-vaisselle autour du pic solaire.",
        Reason.DISHWASHER_NIGHT: "Lave-vaisselle la nuit, après la batterie.",
        Reason.PEAK_OVER_LIMIT: "Les charges prévues dépassent la puissance disponible.",
    },
}


def explain(reasons: list[Reason], language: str | None) -> list[str]:
    """The reasons in the user's language (English when it is not available)."""
    texts = _TEXTS.get((language or "en").split("-")[0], _TEXTS["en"])
    return [texts[r] for r in reasons]
