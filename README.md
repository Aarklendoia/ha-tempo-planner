# Tempo Planner

A Home Assistant integration that plans the night's loads for the French EDF
**Tempo** tariff: when to charge the home battery from the grid, when to charge
the car, and when the dishwasher should run.

> **For now, it only observes.** It computes a plan and exposes it as sensors;
> it controls nothing yet. Compare the plan with what you would have done for a
> week or two, then use the sensors in your own automations.

*[Français plus bas](#français).*

## What it plans

A Tempo day runs from 06:00 to 06:00 and its off-peak hours (22:00–06:00) are
at its end. Each evening, the planner looks at the colour of the next Tempo day
and the solar forecast:

- **Home battery** — charge in off-peak hours what the house will use during
  peak hours minus what the sun will give, but only when it pays. The night is
  billed at *today's* off-peak price and replaces *tomorrow's* peak hours, so the
  saving per kWh is tomorrow's peak price minus today's off-peak price divided
  by the battery's efficiency. The battery charges when that saving beats a
  threshold you set to what a cycle costs in wear (3 c/kWh by default). With
  the default prices, that means before every red day and on blue → white
  nights (about 4 c); not on white → white (about 2 c) or before a blue day.
- **Car** — charge up to the target and finish just before the end of the
  off-peak hours, rather than starting at 22:00 with everything else.
- **Dishwasher** — on a blue day with enough sun forecast, run it around the
  solar peak; otherwise start it at night, after the battery.

Each day it also reviews the day before against what actually happened: the
peak-hour consumption measured by the house meter, and whether the battery
charged during the night (from the recorder's history of its level). Run it
next to the EcoFlow AI mode for a while: if both agree night after night, the
planner can be trusted with more.

It also estimates the night's peak power and flags a plan that goes over the
power you allow.

## Sensors

| Sensor | Value |
| --- | --- |
| Tomorrow | colour of the next Tempo day; attributes: the night's window, the reasons behind the plan and their explanation in your language |
| Peak-hour consumption | what the house should use during tomorrow's peak hours, kWh; attributes: `source` (`history` or `setting`), the number of `days` behind it and their `color` (`blue`/`white`/`red`, or `all`) |
| Home battery target | state of charge to reach, % |
| Home battery grid charge | energy to take from the grid, kWh; attributes: tonight's off-peak price, tomorrow's peak price and the saving per kWh |
| Home battery charge start / end | the battery's slot |
| Car charge energy | energy to take from the grid, kWh |
| Car charge start / end | the car's slot |
| Dishwasher start / end | the dishwasher's slot (`mode`: `night` or `solar`) |
| Last day's peak-hour consumption | measured on the last Tempo day over, kWh; attributes: `day`, `color`, the `forecast` frozen when its night started, the `error` (forecast − measured), the `mean_abs_error` over the last 14 days reviewed |
| Last night's battery | the plan against the battery during the night before that day: `agreed_charge`, `agreed_idle`, `planner_only` or `battery_only` (a rise of 5 points or more counts as a charge); attributes: the levels at the start, highest and end, and the `agreement` rate over the last 14 nights |
| Night peak power | sum of the planned loads at their highest, kW |

## Installation

HACS → ⋮ → *Custom repositories* → `https://github.com/Aarklendoia/ha-tempo-planner`,
category *Integration*. Install **Tempo Planner**, restart Home Assistant, then
*Settings → Devices & services → Add integration → Tempo Planner*.

## Configuration

Only tomorrow's colour is required: any sensor that reads `Bleu`/`Blanc`/`Rouge`
or `blue`/`white`/`red`, such as the next colour of the
[RTE Tempo](https://github.com/hekmon/rtetempo) integration. Optional entities:
the solar forecast for tomorrow and its peak time (Forecast.Solar, Solcast…),
today's colour (the current colour of RTE Tempo; without it the night is
priced as white), the home battery and car states of charge, whether the car is
plugged in, the car's charge target, the house consumption meter, and the six
Tempo prices in EUR/kWh (without them, default prices are used).

With a house consumption meter (an energy sensor of what the house uses, with
long-term statistics — not the grid import, which already nets out solar and the
battery), the peak-hour consumption is learnt from the recorder: the average of
the last 14 days (adjustable) **of tomorrow's colour** whose peak hours are all
recorded, read once a day. While fewer than 3 days of that colour are known, the
most recent days of any colour are used instead. The colour of each day comes
from today's colour entity: the planner remembers it from day to day, and fills
in the first days from the recorder's state history. Without a meter, or until
a full day is recorded, the setting applies.

The house itself (capacities, powers, consumption during peak hours, programme
length…) is set in the integration's options.

## Releases

Versions follow [Conventional Commits](https://www.conventionalcommits.org/):
`feat:` bumps the minor version, `fix:` the patch. On each push to `main`,
[release-please](https://github.com/googleapis/release-please) keeps a release
pull request up to date (changelog and `manifest.json` version); merging it tags
the version and publishes the GitHub release that HACS offers.

## Development

```sh
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt ruff
pytest && ruff check . && ruff format --check .
```

`planner.py` has no Home Assistant import: the planning rules are tested on
their own in `tests/test_planner.py`.

---

## Français

Une intégration Home Assistant qui planifie les consommations de la nuit pour
l'option **Tempo** d'EDF : quand charger la batterie domestique sur le réseau,
quand charger la voiture, quand faire tourner le lave-vaisselle.

**Pour l'instant, elle se contente d'observer** : elle calcule un plan et l'expose en
capteurs, sans rien piloter. Comparez-le pendant une ou deux semaines avec ce que
vous auriez fait, puis servez-vous des capteurs dans vos automatisations.

- **Batterie** : elle charge en heures creuses ce que la maison consommera en
  heures pleines, moins le solaire prévu, mais seulement si c'est rentable. La
  nuit est facturée au tarif heures creuses du jour et remplace les heures
  pleines du lendemain : la charge n'a lieu que si l'écart, pertes comprises,
  dépasse un seuil d'usure réglable (3 c/kWh par défaut). Avec les tarifs par
  défaut : avant chaque jour rouge et les nuits bleu → blanc, jamais blanc →
  blanc ni avant un jour bleu. La consommation en heures pleines est apprise de
  l'historique d'un compteur de consommation de la maison : moyenne des 14
  derniers jours de la couleur de demain (des jours les plus récents tant qu'il
  y en a moins de 3), ou à défaut tirée du réglage.
- **Voiture** : charge jusqu'à l'objectif, en finissant juste avant la fin des
  heures creuses plutôt qu'en démarrant à 22 h avec tout le reste.
- **Lave-vaisselle** : un jour bleu bien ensoleillé, autour du pic solaire ;
  sinon la nuit, après la batterie.

Chaque jour, elle compare aussi la veille à ce qui s'est réellement passé : la
consommation mesurée en heures pleines face à la prévision, et la charge ou non
de la batterie pendant la nuit face au plan. De quoi vérifier qu'elle prend les
mêmes décisions que le mode IA d'EcoFlow avant de lui confier quoi que ce soit.

Installation par HACS (dépôt personnalisé ci-dessus), puis *Paramètres →
Appareils et services → Ajouter une intégration → Tempo Planner*. Seule la
couleur de demain est obligatoire ; le reste se règle dans les options.

## Licence

MIT
