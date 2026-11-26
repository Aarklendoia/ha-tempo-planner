# Tempo Planner

A Home Assistant integration that plans the night's loads for the French EDF
**Tempo** tariff: when to charge the home battery from the grid, when to charge
the car, and when the dishwasher should run. It also sheds the appliances you
choose on red days.

> **The plan only observes.** It is exposed as sensors and controls nothing:
> compare it with what you would have done for a week or two, then use the
> sensors in your own automations. **Load shedding acts**: it drives only the
> appliances you add to it.

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
- **Car** — charge up to the target. By default the car is expected to start
  as soon as the off-peak hours open, as a car on its own charge program does;
  for a charger the planner will drive, it can instead finish just before
  their end. An unplugged car gets no slot.
- **Car target advice** — on a blue night, the usual target; on a white or red
  night, only what keeps a reserve until the next blue night (tomorrow night if
  tomorrow is blue, otherwise Sunday night, always blue), from the energy the car
  uses a day, learnt from the reviews. Before a trip (an event in a calendar
  whose title contains "Voyage", adjustable): 100 % the night before, or
  already tonight if tonight is blue and tomorrow night is not. The planner only
  recommends: an automation can copy the target into the car or notify you. The
  usual target is the planner's setting, not the car's, so that copying does not
  feed back.
- **Solar charge of the car** — from the hourly solar forecast (the energy
  platform of Forecast.Solar, Solcast…), the house's hourly consumption and the
  home battery, which takes the surplus first, the planner finds tomorrow's
  hours when the energy *sold* covers enough of the car's power to beat
  charging it the next night: `(1 − s) × peak + s × resale < off-peak`. The rest
  comes from the grid or the battery, both priced at the peak price; the hybrid
  inverter caps solar and battery together. About a quarter of the car's power
  on blue and white days, out of reach on red days.
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
| Recommended car target | what the car should be charged to tonight, %; attributes: `advice`, its `explanation`, the next `trip` and the car's `daily_energy` |
| Plug in the car tonight (binary) | on when tonight's recommendation is worth a charge (at least the car's minimum charge) |
| Solar car charge tomorrow | energy the car can take from tomorrow's surplus, kWh; attributes: window `start` and `end`, energy `sold_energy` without the car, `min_share` of the car's power the surplus must cover, % |
| Last day's peak-hour consumption | measured on the last Tempo day over, kWh; attributes: `day`, `color`, the `forecast` frozen when its night started, the `error` (forecast − measured), the `mean_abs_error` over the last 14 days reviewed |
| Last night's battery | the plan against the battery during the night before that day: `agreed_charge`, `agreed_idle`, `planner_only` or `battery_only` (a rise of 5 points or more counts as a charge); attributes: the levels at the start, highest and end, and the `agreement` rate over the last 14 nights |
| Last night's car charge | grid energy the car took during the night before the last day reviewed, kWh (from its level and capacity); attributes: actual `start` and `end` (from the car charging entity), levels, planned start, end and energy, and the `start_offset` in minutes |
| Night peak power | sum of the planned loads at their highest, kW |

## Load shedding

The appliances you add are shed on the days of their colours (red by default,
white too if you want), during peak hours or for the whole Tempo day. It needs
today's colour entity. Each appliance has one behaviour:

- **Off**: turned off (`light`, `switch`, `fan`, `input_boolean`, `climate`,
  `water_heater`, `humidifier`, `media_player`), and back on afterwards if it
  was on. Turned on by someone while shed, it is turned off again, with a
  notification: turn its shedding switch off to keep it on.
- **Reduced mode**: an option, preset or operation mode is forced
  (`select`, `input_select`, `climate` preset, `water_heater`), the previous one
  restored afterwards.
- **Alert only**: for what can't be driven, such as a car. A state or power
  sensor tells when it runs (a number above 50 W, or `on`, or the states you
  give); a notification goes out when it starts running while shed.

**Schedules by colour** (optional, not for alerts): a `schedule` entity per
colour. On a day of that colour, the appliance is turned on (or put in its
normal mode, such as `Confort`) when the schedule turns on, and off (or
reduced) when it turns off; the day's schedule also applies when the Tempo day
changes at 06:00. Between those changes, a manual change is left alone. A
colour without a schedule leaves the appliance alone; shedding always wins,
and when it ends the schedule says what the appliance does next. The
appliance's switch turns its schedules off too.

**Load shedding by power** (optional): from a sensor of the power drawn from
the grid, two limits keep the house under its subscription. Over the **soft
limit** (not above, if possible; it can differ by colour and period, e.g. 3 kW
on red peak hours) appliances are shed one at a time by priority, after a delay
(2 min by default), a reduced mode being a step of its own; appliances marked
*hard limit only* (a car's charge) are left alone. Over the **hard limit** (the
subscription's) as many as needed are shed after a few seconds, from their power
sensor or declared power. They come back one at a time, the last one first, once
the power plus theirs stays a margin under the soft limit for a while (5 min by
default). Alert-only appliances can't be shed by power; an appliance shed by
power when a red day starts is taken over by the tariff. Entities: *Power load
shedding* (switch), *Power headroom* (kW before the soft limit) and *Load
shedding level* (`none`, `soft`, `hard`). The panel has a *Power* tab: the power
now against the limits, the shedding order (up/down) and the settings. The *Now*
tab charts the last 6 or 24 hours: the power drawn from the grid, the limits,
each appliance's power stacked, the power avoided by shedding (hatched, above
the grid line) and a row per appliance with its shedding periods
(`tempo_planner/power/history`). With a *house consumption* power sensor in the
power settings, the chart also draws what the house uses: the gap with the grid
is what the battery and the solar panels supply, or, when the grid draws more, the
battery charging.

At 06:00 the current colour entity of RTE Tempo lags a few seconds behind: the
colour announced the day before is used until it catches up.

The shedding in progress is kept across restarts. Each appliance also has a
priority and a power, used by the power-based shedding to come.

| Entity | Value |
| --- | --- |
| Shed *appliance* (switch) | whether the appliance may be shed |
| *Appliance* shed (binary) | on while shed; attributes: `reason` (`tariff`), `until`, `behaviour`, `appliance_entity` |
| Shed appliances | how many appliances are shed now; attribute: the list |

Appliances are managed in the **Tempo Planner** panel, in the sidebar (admins
only): the *Now* tab shows today's and tomorrow's colours, the current tariff
period and what is shed until when; the *Appliances* tab adds, edits, deletes
and turns their shedding on and off. The panel follows Home Assistant's theme
and language (English, French).

The same is available with WebSocket commands (admin only):
`tempo_planner/subscribe` (a snapshot now, then on every change),
`tempo_planner/appliances/list`,
`tempo_planner/appliances/save` with an `appliance` (`name`, `entity_id`,
`behaviour`: `off`/`reduced`/`alert`, `reduced_option`, `running_entity`,
`running_above`, `running_states`, `colors`, `hours`: `peak`/`day`, `notify`
such as `notify.mobile_app_phone`, `priority`, `power_entity`, `power_kw`,
`enabled`; with its `id` to change it), and `tempo_planner/appliances/delete`
with an `appliance_id`.

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
plugged in, the car's charge target, the house consumption meter, the car's
charging meter, and the six Tempo prices in EUR/kWh (without them, default
prices are used).

With a house consumption meter (an energy sensor of what the house uses, with
long-term statistics — not the grid import, which already nets out solar and the
battery), the peak-hour consumption is learnt from the recorder: the average of
the last 14 days (adjustable) **of tomorrow's colour** whose peak hours are all
recorded, read once a day. While fewer than 3 days of that colour are known, the
most recent days of any colour are used instead. The colour of each day comes
from today's colour entity: the planner remembers it from day to day, and fills
in the first days from the recorder's state history. Without a meter, or until
a full day is recorded, the setting applies.

When the house meter measures the whole panel, the car's charger is part of it.
Set the car's charging meter (an energy sensor of the charger, with long-term
statistics) and its consumption is taken out of the house history, hour by hour:
a charge in the sun during peak hours then no longer counts as house load.

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

**Le plan se contente d'observer** : il est exposé en capteurs, sans rien
piloter. Comparez-le pendant une ou deux semaines avec ce que vous auriez fait,
puis servez-vous des capteurs dans vos automatisations. **Le délestage, lui,
agit**, mais seulement sur les appareils que vous lui confiez.

- **Batterie** : elle charge en heures creuses ce que la maison consommera en
  heures pleines, moins le solaire prévu, mais seulement si c'est rentable. La
  nuit est facturée au tarif heures creuses du jour et remplace les heures
  pleines du lendemain : la charge n'a lieu que si l'écart, pertes comprises,
  dépasse un seuil d'usure réglable (3 c/kWh par défaut). Avec les tarifs par
  défaut : avant chaque jour rouge et les nuits bleu → blanc, jamais blanc →
  blanc ni avant un jour bleu. La consommation en heures pleines est apprise de
  l'historique d'un compteur de consommation de la maison : moyenne des 14
  derniers jours de la couleur de demain (des jours les plus récents tant qu'il
  y en a moins de 3), ou à défaut tirée du réglage. Si ce compteur inclut la
  borne, un compteur de charge de la voiture en retire la recharge, heure par
  heure.
- **Voiture** : charge jusqu'à l'objectif. Par défaut, elle démarre dès
  l'ouverture des heures creuses, comme une voiture qui suit son propre
  programme ; pour une borne pilotée plus tard, elle peut finir juste avant la
  fin. Débranchée, pas de créneau. Le bilan quotidien montre quand elle a
  réellement chargé.
- **Objectif de charge conseillé** : une nuit bleue, l'objectif habituel ; une
  nuit blanche ou rouge, juste de quoi garder une réserve jusqu'à la prochaine
  nuit bleue (demain soir si demain est bleu, sinon dimanche soir), d'après
  l'énergie quotidienne de la voiture apprise par les bilans. Avant un voyage
  (événement « Voyage » dans un calendrier) : 100 % la veille, ou dès ce soir si
  ce soir est bleu et pas demain. Un capteur « Brancher la voiture ce soir »
  l'accompagne. Le planificateur conseille seulement : une automatisation peut
  recopier l'objectif dans la voiture ou vous prévenir.
- **Recharge solaire de la voiture** : d'après la prévision solaire heure par
  heure, la consommation horaire de la maison et la batterie (servie en
  premier), le planificateur repère les heures de demain où le surplus *vendu*
  couvre assez de la puissance de la voiture pour battre la charge de la nuit
  suivante. L'onduleur hybride plafonne solaire et batterie ensemble.
- **Lave-vaisselle** : un jour bleu bien ensoleillé, autour du pic solaire ;
  sinon la nuit, après la batterie.

Chaque jour, elle compare aussi la veille à ce qui s'est réellement passé : la
consommation mesurée en heures pleines face à la prévision, et la charge ou non
de la batterie pendant la nuit face au plan. De quoi vérifier qu'elle prend les
mêmes décisions que le mode IA d'EcoFlow avant de lui confier quoi que ce soit.

**Délestage** : les appareils ajoutés sont délestés les jours de leurs couleurs
(rouge par défaut, blanc en option), en heures pleines ou toute la journée
Tempo. Selon l'appareil : coupé puis rallumé s'il l'était (et recoupé, avec une
notification, si quelqu'un le rallume entre-temps), passé en mode réduit (Eco,
preset…) puis remis dans son mode, ou simplement surveillé avec une alerte
quand il fonctionne (la voiture). Chaque appareil peut aussi suivre un
**planning par couleur** (une entité `schedule` pour les jours bleus, blancs,
rouges) : allumé ou en mode normal tant que le planning est actif, éteint ou
réduit sinon ; le délestage passe avant. Un interrupteur par appareil active ou
non son délestage et ses plannings, un capteur dit s'il est délesté et jusqu'à quand. Les appareils
se gèrent dans le panneau **Tempo Planner** de la barre latérale (administrateurs) :
l'onglet *Maintenant* montre les couleurs du jour et du lendemain, la période
tarifaire et ce qui est délesté jusqu'à quand ; l'onglet *Appareils* permet
d'ajouter, modifier, supprimer et activer ou non leur délestage.

**Délestage en puissance** : d'après un capteur de la puissance tirée du
réseau, au-dessus d'un **seuil souple** (à ne pas dépasser si possible,
réglable par couleur et période) les appareils sont délestés un par un par
priorité après une temporisation, le mode réduit d'abord ; au-dessus d'un
**seuil dur** (l'abonnement), autant qu'il faut, en quelques secondes, y compris
ceux marqués « seuil dur seulement » (la borne de la voiture). Ils reviennent un
par un, le dernier d'abord, quand il y a la place. L'onglet *Puissance* du
panneau montre la puissance face aux seuils, l'ordre de délestage et les
réglages ; l'onglet *Maintenant* trace les 6 ou 24 dernières heures : la
puissance tirée du réseau, la consommation de la maison (l'écart, c'est la
batterie : ce qu'elle fournit ou ce qu'elle charge), les seuils, la
consommation de chaque appareil et ce que le délestage a évité.

Installation par HACS (dépôt personnalisé ci-dessus), puis *Paramètres →
Appareils et services → Ajouter une intégration → Tempo Planner*. Seule la
couleur de demain est obligatoire ; le reste se règle dans les options.

## Licence

MIT
