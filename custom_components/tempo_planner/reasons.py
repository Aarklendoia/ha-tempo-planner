"""Plain-language explanations of the plan, for the dashboard."""

from __future__ import annotations

from .planner import Reason

_TEXTS: dict[str, dict[Reason, str]] = {
    "en": {
        Reason.COLOR_UNKNOWN: "Tomorrow's colour is not published yet: planned as a white day.",
        Reason.BATTERY_SOLAR_COVERS: "The sun should cover peak hours: no grid charge.",
        Reason.BATTERY_NOT_WORTH: (
            "Tomorrow's peak price does not beat tonight's off-peak price"
            " by enough to pay for losses and wear: no grid charge."
        ),
        Reason.BATTERY_ALREADY_FULL: "The battery already holds enough for peak hours.",
        Reason.BATTERY_CHARGE: "The battery charges in off-peak hours for tomorrow's peak hours.",
        Reason.BATTERY_UNKNOWN_SOC: "Battery level unknown.",
        Reason.CAR_FULL: "The car is at its target.",
        Reason.CAR_BELOW_MINIMUM: "The car is close to its target: not worth a charge.",
        Reason.CAR_UNKNOWN_SOC: "Car level unknown.",
        Reason.CAR_NOT_PLUGGED: "The car is not plugged in: no charge planned.",
        Reason.CAR_OVERFLOWS_OFFPEAK: "The car cannot finish within off-peak hours.",
        Reason.CAR_ADVICE_BLUE_NIGHT: "Blue night: charge the car to its usual target.",
        Reason.CAR_ADVICE_COVERED: (
            "White or red night: the car holds until the next blue night without charging."
        ),
        Reason.CAR_ADVICE_BRIDGE: (
            "White or red night: charge the car just enough to reach the next blue night."
        ),
        Reason.CAR_ADVICE_TRIP: "Trip tomorrow: charge the car to 100 %.",
        Reason.CAR_ADVICE_TRIP_EARLY: (
            "Trip the day after tomorrow and tomorrow night is dearer: fill the car tonight."
        ),
        Reason.DISHWASHER_SOLAR: "Sunny blue day: the dishwasher runs around the solar peak.",
        Reason.DISHWASHER_NIGHT: "The dishwasher runs at night, after the battery.",
        Reason.PEAK_OVER_LIMIT: "The planned loads exceed the available power.",
    },
    "fr": {
        Reason.COLOR_UNKNOWN: "Couleur de demain pas encore publiée : prévu comme un jour blanc.",
        Reason.BATTERY_SOLAR_COVERS: "Le soleil couvrira les heures pleines : pas de charge.",
        Reason.BATTERY_NOT_WORTH: (
            "L'écart entre les heures creuses de cette nuit et les heures pleines"
            " de demain ne paie pas les pertes et l'usure : pas de charge."
        ),
        Reason.BATTERY_ALREADY_FULL: "La batterie a déjà de quoi passer les heures pleines.",
        Reason.BATTERY_CHARGE: "La batterie charge en heures creuses pour les heures pleines.",
        Reason.BATTERY_UNKNOWN_SOC: "Niveau de la batterie inconnu.",
        Reason.CAR_FULL: "La voiture est à son objectif.",
        Reason.CAR_BELOW_MINIMUM: "La voiture est presque à son objectif : pas de charge.",
        Reason.CAR_UNKNOWN_SOC: "Niveau de la voiture inconnu.",
        Reason.CAR_NOT_PLUGGED: "La voiture n'est pas branchée : pas de charge prévue.",
        Reason.CAR_OVERFLOWS_OFFPEAK: "La voiture ne peut pas finir en heures creuses.",
        Reason.CAR_ADVICE_BLUE_NIGHT: "Nuit bleue : charger la voiture à son objectif habituel.",
        Reason.CAR_ADVICE_COVERED: (
            "Nuit blanche ou rouge : la voiture tient sans charge jusqu'à la prochaine nuit bleue."
        ),
        Reason.CAR_ADVICE_BRIDGE: (
            "Nuit blanche ou rouge : charger juste de quoi tenir jusqu'à la prochaine nuit bleue."
        ),
        Reason.CAR_ADVICE_TRIP: "Voyage demain : charger la voiture à 100 %.",
        Reason.CAR_ADVICE_TRIP_EARLY: (
            "Voyage après-demain et la nuit de demain est plus chère : remplir dès ce soir."
        ),
        Reason.DISHWASHER_SOLAR: "Jour bleu ensoleillé : lave-vaisselle autour du pic solaire.",
        Reason.DISHWASHER_NIGHT: "Lave-vaisselle la nuit, après la batterie.",
        Reason.PEAK_OVER_LIMIT: "Les charges prévues dépassent la puissance disponible.",
    },
}


def explain(reasons: list[Reason], language: str | None) -> list[str]:
    """The reasons in the user's language (English when it is not available)."""
    texts = _TEXTS.get((language or "en").split("-")[0], _TEXTS["en"])
    return [texts[r] for r in reasons]
