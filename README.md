# Tempo Planner

A Home Assistant integration that plans the night's loads for the French EDF
**Tempo** tariff: when to charge the home battery from the grid, when to charge
the car, and when the dishwasher should run.

> **Version 0.1 only observes.** It computes a plan and exposes it as sensors;
> it controls nothing yet. Compare the plan with what you would have done for a
> week or two, then use the sensors in your own automations.

*[Français plus bas](#français).*

## What it plans

A Tempo day runs from 06:00 to 06:00 and its off-peak hours (22:00–06:00) are
at its end. Each evening, the planner looks at the colour of the next Tempo day
and the solar forecast:

- **Home battery** — on a white or red day, charge in off-peak hours what the
  house will use during peak hours minus what the sun will give. On a blue day
  it stays off the grid by default: the gain barely covers the battery's losses.
- **Car** — charge up to the target and finish just before the end of the
  off-peak hours, rather than starting at 22:00 with everything else.
- **Dishwasher** — on a blue day with enough sun forecast, run it around the
  solar peak; otherwise start it at night, after the battery.

It also estimates the night's peak power and flags a plan that goes over the
power you allow.

## Sensors

| Sensor | Value |
| --- | --- |
| Tomorrow | colour of the next Tempo day; attributes: the night's window and the reasons behind the plan |
| Home battery target | state of charge to reach, % |
| Home battery grid charge | energy to take from the grid, kWh |
| Home battery charge end | when that charge ends |
| Car charge energy | energy to take from the grid, kWh |
| Car charge start / end | the car's slot |
| Dishwasher start / end | the dishwasher's slot (`mode`: `night` or `solar`) |
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
the home battery and car states of charge, whether the car is plugged in and the
car's charge target.

The house itself (capacities, powers, consumption during peak hours, programme
length…) is set in the integration's options.

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

**La version 0.1 se contente d'observer** : elle calcule un plan et l'expose en
capteurs, sans rien piloter. Comparez-le pendant une ou deux semaines avec ce que
vous auriez fait, puis servez-vous des capteurs dans vos automatisations.

- **Batterie** : un jour blanc ou rouge, elle charge en heures creuses ce que la
  maison consommera en heures pleines, moins le solaire prévu. Un jour bleu, pas
  de charge sur le réseau par défaut.
- **Voiture** : charge jusqu'à l'objectif, en finissant juste avant la fin des
  heures creuses plutôt qu'en démarrant à 22 h avec tout le reste.
- **Lave-vaisselle** : un jour bleu bien ensoleillé, autour du pic solaire ;
  sinon la nuit, après la batterie.

Installation par HACS (dépôt personnalisé ci-dessus), puis *Paramètres →
Appareils et services → Ajouter une intégration → Tempo Planner*. Seule la
couleur de demain est obligatoire ; le reste se règle dans les options.

## Licence

MIT
