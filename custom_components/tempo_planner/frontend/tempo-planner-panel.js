// Tempo Planner panel: where the house stands now, and the sheddable appliances.
//
// Plain ES module, no build step: Lit is bundled next to it (lit.js). Home
// Assistant's own elements (ha-form, ha-icon, ha-menu-button) and theme
// variables keep it in line with the rest of the interface.

import { LitElement, html, svg, css, nothing } from "./lit.js";

// The next round number (1, 1.2, 1.5, 2… times a power of ten) at or above a value.
function niceCeil(value) {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) {
    if (value <= step * power + 1e-9) return step * power;
  }
  return 10 * power;
}

const TEXTS = {
  en: {
    now: "Now",
    appliances: "Appliances",
    today: "Today",
    tomorrow: "Tomorrow",
    blue: "Blue",
    white: "White",
    red: "Red",
    unknown: "Unknown",
    peak_until: "Peak hours until {time}",
    offpeak_until: "Off-peak hours until {time}",
    shed_now: "Shed now",
    nothing_shed: "No appliance is shed.",
    no_today_color:
      "Load shedding needs today's colour: set it in the integration's options.",
    until: "until {time}",
    reason_tariff: "tariff",
    reason_power: "power",
    add: "Add an appliance",
    edit: "Edit",
    delete: "Delete",
    save: "Save",
    cancel: "Cancel",
    confirm_delete: "Delete {name}? It is released first if it is shed.",
    no_appliance: "No appliance yet. Add the ones that may be shed on red days.",
    shed: "Shed",
    enabled: "Load shedding on",
    disabled: "Load shedding off",
    behaviour_off: "Off",
    behaviour_reduced: "Reduced mode",
    behaviour_alert: "Alert only",
    hours_peak: "peak hours",
    hours_day: "whole Tempo day",
    option_hours_peak: "Peak hours",
    option_hours_day: "Whole Tempo day",
    priority: "priority {value}",
    new_appliance: "New appliance",
    field_name: "Name",
    field_entity_id: "Appliance",
    field_behaviour: "When shed",
    field_reduced_option: "Mode forced while shed",
    field_running_entity: "Tells when it runs (state or power sensor)",
    field_running_above: "Running above (W)",
    field_running_states: "Or in these states (comma separated)",
    field_colors: "Colours",
    field_hours: "Hours",
    field_notify: "Notify with",
    field_priority: "Priority (shed first when low)",
    field_power_entity: "Its power sensor",
    field_power_kw: "Or its power (kW)",
    field_enabled: "Load shedding on",
    field_normal_option: "Mode while a schedule is on",
    field_schedule_blue: "Schedule on blue days",
    field_schedule_white: "Schedule on white days",
    field_schedule_red: "Schedule on red days",
    schedules_title: "Schedules by colour",
    schedules_help:
      "Optional. On a day of that colour the appliance is on (or in its normal mode) while the schedule is on, off (or reduced) otherwise, at each change of the schedule. Shedding wins over schedules.",
    schedules: "schedules: {colors}",
    power: "Power",
    field_hard_only: "Hard limit only (stopping it costs, like a car's charge)",
    hard_only: "hard limit only",
    power_now: "Drawn from the grid",
    power_off: "Load shedding by power is off.",
    power_no_reading: "No reading from the power sensor.",
    level_none: "Under the limits",
    level_soft: "Over the soft limit",
    level_hard: "Over the hard limit",
    soft_limit: "Soft limit {value} kW",
    hard_limit: "Hard limit {value} kW",
    power_settings: "Settings",
    power_help:
      "Over the soft limit, appliances are shed one at a time by priority, after a delay; a reduced mode first. Over the hard limit, as many as needed, fast. They come back one at a time, the last first, once there is room for them.",
    power_order: "Shedding order",
    power_order_help: "Shed from the top; alert-only appliances can't be shed by power.",
    up: "Up",
    down: "Down",
    unknown_power: "power unknown",
    field_power_entity_grid: "Power drawn from the grid",
    field_soft_limit_kw: "Soft limit: not above, if possible (kW)",
    field_hard_limit_kw: "Hard limit: never for long (kW)",
    field_restore_margin_kw: "Margin before bringing one back (kW)",
    field_soft_delay_s: "Delay over the soft limit (s)",
    field_hard_delay_s: "Delay over the hard limit (s)",
    field_restore_delay_s: "Delay before bringing one back (s)",
    field_power_enabled: "Load shedding by power",
    field_soft_limits: "Soft limit by colour and period",
    field_blue_peak: "Blue, peak hours (kW)",
    field_blue_offpeak: "Blue, off-peak hours (kW)",
    field_white_peak: "White, peak hours (kW)",
    field_white_offpeak: "White, off-peak hours (kW)",
    field_red_peak: "Red, peak hours (kW)",
    field_red_offpeak: "Red, off-peak hours (kW)",
    saved: "Saved.",
    chart_title: "Power",
    chart_hours: "{hours} h",
    chart_grid: "From the grid",
    chart_soft: "Soft limit",
    chart_hard: "Hard limit",
    chart_avoided: "Avoided by shedding",
    chart_shed: "Shed",
    chart_no_data: "No power history yet.",
    chart_house: "House",
    chart_supply: "Battery and solar",
    chart_charge: "Charging the battery",
    field_house_entity: "House consumption (power sensor, for the chart)",
    chart_summary: "Power drawn from the grid over the last {hours} hours, with the limits and the appliances.",
    help_off: "Turned off, back on afterwards if it was on. Turned back on by someone: off again, with a notification.",
    help_reduced: "A mode is forced (Eco, a preset…), the previous one restored afterwards.",
    help_alert: "Nothing is driven: a notification when it starts running while shed.",
    announcements: "Announcements",
    announcements_help:
      "Tomorrow's colour, with the appliances shed and, on the eve of a red day, the car to plug in when its charge is low. Once per day and colour.",
    announce_notify: "Notification",
    announce_notify_help: "Sent as soon as tomorrow's colour is known.",
    announce_voice: "Voice",
    announce_voice_help: "Spoken at the set time on the chosen speakers.",
    announce_car: "Car",
    announce_test: "Try it",
    announce_test_help: "Announces tomorrow now (a red day when not known yet), with the saved settings.",
    announce_sent: "Sent.",
    field_notify_enabled: "Notify tomorrow's colour",
    field_notify_colors: "Colours",
    field_notify_targets: "Notify with",
    field_voice_enabled: "Speak tomorrow's colour",
    field_voice_colors: "Colours",
    field_voice_time: "At",
    field_tts_entity: "Voice (text-to-speech)",
    field_media_players: "Speakers",
    field_voice_only_home: "Only when someone is at home",
    field_car_reminder_pct: "Remind to plug the car in under (%), empty: never",
    watched_now: "Watched",
    watched: "Watched",
    running_now: "Running!",
    watched_help: "Alert if it runs",
    error: "Error: {message}",
  },
  fr: {
    now: "Maintenant",
    appliances: "Appareils",
    today: "Aujourd'hui",
    tomorrow: "Demain",
    blue: "Bleu",
    white: "Blanc",
    red: "Rouge",
    unknown: "Inconnu",
    peak_until: "Heures pleines jusqu'à {time}",
    offpeak_until: "Heures creuses jusqu'à {time}",
    shed_now: "Délestés en ce moment",
    nothing_shed: "Aucun appareil délesté.",
    no_today_color:
      "Le délestage a besoin de la couleur du jour : renseignez-la dans les options de l'intégration.",
    until: "jusqu'à {time}",
    reason_tariff: "tarif",
    reason_power: "puissance",
    add: "Ajouter un appareil",
    edit: "Modifier",
    delete: "Supprimer",
    save: "Enregistrer",
    cancel: "Annuler",
    confirm_delete: "Supprimer {name} ? S'il est délesté, il est d'abord rétabli.",
    no_appliance:
      "Aucun appareil pour l'instant. Ajoutez ceux qui peuvent être délestés les jours rouges.",
    shed: "Délesté",
    enabled: "Délestage activé",
    disabled: "Délestage désactivé",
    behaviour_off: "Coupé",
    behaviour_reduced: "Mode réduit",
    behaviour_alert: "Alerte seulement",
    hours_peak: "heures pleines",
    hours_day: "toute la journée Tempo",
    option_hours_peak: "Heures pleines",
    option_hours_day: "Toute la journée Tempo",
    priority: "priorité {value}",
    new_appliance: "Nouvel appareil",
    field_name: "Nom",
    field_entity_id: "Appareil",
    field_behaviour: "Pendant le délestage",
    field_reduced_option: "Mode imposé pendant le délestage",
    field_running_entity: "Indique quand il fonctionne (état ou puissance)",
    field_running_above: "En marche au-dessus de (W)",
    field_running_states: "Ou dans ces états (séparés par des virgules)",
    field_colors: "Couleurs",
    field_hours: "Plage",
    field_notify: "Notifier avec",
    field_priority: "Priorité (délesté en premier si basse)",
    field_power_entity: "Son capteur de puissance",
    field_power_kw: "Ou sa puissance (kW)",
    field_enabled: "Délestage activé",
    field_normal_option: "Mode quand un planning est actif",
    field_schedule_blue: "Planning des jours bleus",
    field_schedule_white: "Planning des jours blancs",
    field_schedule_red: "Planning des jours rouges",
    schedules_title: "Plannings par couleur",
    schedules_help:
      "Facultatif. Un jour de cette couleur, l'appareil est allumé (ou dans son mode normal) tant que le planning est actif, éteint (ou réduit) sinon, à chaque changement du planning. Le délestage passe avant les plannings.",
    schedules: "plannings : {colors}",
    power: "Puissance",
    field_hard_only: "Seuil dur seulement (le couper coûte, comme la charge d'une voiture)",
    hard_only: "seuil dur seulement",
    power_now: "Tiré du réseau",
    power_off: "Le délestage en puissance est désactivé.",
    power_no_reading: "Aucune mesure du capteur de puissance.",
    level_none: "Sous les seuils",
    level_soft: "Au-dessus du seuil souple",
    level_hard: "Au-dessus du seuil dur",
    soft_limit: "Seuil souple {value} kW",
    hard_limit: "Seuil dur {value} kW",
    power_settings: "Réglages",
    power_help:
      "Au-dessus du seuil souple, les appareils sont délestés un par un par priorité, après une temporisation ; le mode réduit d'abord. Au-dessus du seuil dur, autant qu'il faut, vite. Ils reviennent un par un, le dernier d'abord, quand il y a la place.",
    power_order: "Ordre de délestage",
    power_order_help:
      "Délestés en commençant par le haut ; les appareils en alerte seulement ne peuvent pas l'être en puissance.",
    up: "Monter",
    down: "Descendre",
    unknown_power: "puissance inconnue",
    field_power_entity_grid: "Puissance tirée du réseau",
    field_soft_limit_kw: "Seuil souple : à ne pas dépasser si possible (kW)",
    field_hard_limit_kw: "Seuil dur : jamais longtemps (kW)",
    field_restore_margin_kw: "Marge avant de relancer un appareil (kW)",
    field_soft_delay_s: "Temporisation au-dessus du seuil souple (s)",
    field_hard_delay_s: "Temporisation au-dessus du seuil dur (s)",
    field_restore_delay_s: "Temporisation avant de relancer (s)",
    field_power_enabled: "Délestage en puissance",
    field_soft_limits: "Seuil souple par couleur et période",
    field_blue_peak: "Bleu, heures pleines (kW)",
    field_blue_offpeak: "Bleu, heures creuses (kW)",
    field_white_peak: "Blanc, heures pleines (kW)",
    field_white_offpeak: "Blanc, heures creuses (kW)",
    field_red_peak: "Rouge, heures pleines (kW)",
    field_red_offpeak: "Rouge, heures creuses (kW)",
    saved: "Enregistré.",
    chart_title: "Consommation",
    chart_hours: "{hours} h",
    chart_grid: "Tiré du réseau",
    chart_soft: "Seuil souple",
    chart_hard: "Seuil dur",
    chart_avoided: "Évité par le délestage",
    chart_shed: "Délesté",
    chart_no_data: "Pas encore d'historique de puissance.",
    chart_house: "Maison",
    chart_supply: "Batterie et photovoltaïque",
    chart_charge: "Charge de la batterie",
    field_house_entity: "Consommation de la maison (capteur de puissance, pour le graphique)",
    chart_summary: "Puissance tirée du réseau sur les {hours} dernières heures, avec les seuils et les appareils.",
    help_off: "Coupé, puis rallumé s'il l'était. Rallumé par quelqu'un : recoupé, avec une notification.",
    help_reduced: "Un mode est imposé (Eco, un preset…), puis le précédent est remis.",
    help_alert: "Rien n'est piloté : une notification quand il se met à fonctionner pendant le délestage.",
    announcements: "Annonces",
    announcements_help:
      "La couleur de demain, avec les appareils délestés et, la veille d'un jour rouge, la voiture à brancher si sa charge est basse. Une fois par jour et par couleur.",
    announce_notify: "Notification",
    announce_notify_help: "Envoyée dès que la couleur de demain est connue.",
    announce_voice: "Annonce vocale",
    announce_voice_help: "Prononcée à l'heure choisie sur les enceintes choisies.",
    announce_car: "Voiture",
    announce_test: "Essayer",
    announce_test_help: "Annonce demain tout de suite (un jour rouge s'il n'est pas encore connu), avec les réglages enregistrés.",
    announce_sent: "Envoyé.",
    field_notify_enabled: "Notifier la couleur de demain",
    field_notify_colors: "Couleurs",
    field_notify_targets: "Notifier avec",
    field_voice_enabled: "Annoncer la couleur de demain",
    field_voice_colors: "Couleurs",
    field_voice_time: "À",
    field_tts_entity: "Voix (synthèse vocale)",
    field_media_players: "Enceintes",
    field_voice_only_home: "Seulement si quelqu'un est à la maison",
    field_car_reminder_pct: "Rappeler de brancher la voiture sous (%), vide : jamais",
    watched_now: "Sous surveillance",
    watched: "Surveillé",
    running_now: "En marche !",
    watched_help: "Alerte s'il se met en marche",
    error: "Erreur : {message}",
  },
};

const OFF_DOMAINS = [
  "light",
  "switch",
  "fan",
  "input_boolean",
  "climate",
  "water_heater",
  "humidifier",
  "media_player",
];
const REDUCED_DOMAINS = ["select", "input_select", "climate", "water_heater"];
const COLORS = ["blue", "white", "red"];
// Categorical series colours (validated for colour-blind separation), light and dark:
// the appliances take the first six, the battery the green and the violet.
const SERIES = {
  light: ["#257de0", "#f47230", "#00b894", "#f2a600", "#ee7fac", "#ec4647"],
  dark: ["#338ced", "#e76624", "#00a888", "#d28e05", "#e24d8b", "#eb6263"],
};
const SOURCES = {
  light: { supply: "#008a17", charge: "#6a4ce2" },
  dark: { supply: "#0aac23", charge: "#9887ef" },
};
// The power form shares some field names with the appliance form.
const POWER_LABELS = { power_entity: "field_power_entity_grid", enabled: "field_power_enabled" };

const EMPTY = {
  name: "",
  entity_id: "",
  behaviour: "off",
  reduced_option: null,
  running_entity: null,
  running_above: 50,
  running_states: "on",
  colors: ["red"],
  hours: "peak",
  notify: null,
  priority: 0,
  power_entity: null,
  power_kw: null,
  enabled: true,
  hard_only: false,
  schedule_blue: null,
  schedule_white: null,
  schedule_red: null,
  normal_option: null,
};

// ha-form and its selectors are loaded on demand by the frontend: opening a
// card editor pulls them in.
let formsLoaded;
function loadForms() {
  if (!formsLoaded) {
    formsLoaded = (async () => {
      if (customElements.get("ha-form") && customElements.get("ha-selector")) return;
      const helpers = await window.loadCardHelpers();
      for (const config of [
        { type: "entities", entities: [] },
        { type: "tile", entity: "sun.sun" },
      ]) {
        const card = await helpers.createCardElement(config);
        await card.constructor.getConfigElement?.();
      }
      await customElements.whenDefined("ha-form");
    })();
  }
  return formsLoaded;
}

class TempoPlannerPanel extends LitElement {
  static properties = {
    hass: { attribute: false },
    narrow: { type: Boolean },
    route: { attribute: false },
    panel: { attribute: false },
    _tab: { state: true },
    _snapshot: { state: true },
    _draft: { state: true },
    _error: { state: true },
    _formError: { state: true },
    _saving: { state: true },
    _formsReady: { state: true },
    _powerDraft: { state: true },
    _powerError: { state: true },
    _powerSaved: { state: true },
    _chart: { state: true },
    _chartHours: { state: true },
    _chartWidth: { state: true },
    _chartError: { state: true },
    _hover: { state: true },
    _announceDraft: { state: true },
    _announceError: { state: true },
    _announceNote: { state: true },
  };

  constructor() {
    super();
    this._tab = "now";
    this._snapshot = null;
    this._draft = null;
    this._error = null;
    this._formError = null;
    this._saving = false;
    this._formsReady = false;
    this._chart = null;
    this._chartHours = 24;
    this._chartWidth = 0;
    this._hover = null;
  }

  connectedCallback() {
    super.connectedCallback();
    if (this.hass) this._subscribe();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsubscribe();
    this._stopChart();
    this._resize?.disconnect();
    this._resize = undefined;
  }

  updated(changed) {
    if (changed.has("hass") && this.hass && !this._unsub) this._subscribe();
    // The chart refreshes every minute while the Now tab shows it.
    const wanted = this._tab === "now" && !!this._snapshot?.power?.power_entity;
    if (wanted && !this._chartTimer) {
      this._loadChart();
      this._chartTimer = setInterval(() => this._loadChart(), 60000);
    } else if (!wanted) {
      this._stopChart();
    }
    const box = this.shadowRoot.querySelector(".chart-box");
    if (box && box !== this._observed) {
      this._resize ??= new ResizeObserver((entries) => {
        this._chartWidth = Math.floor(entries[0].contentRect.width);
      });
      this._resize.disconnect();
      this._resize.observe(box);
      this._observed = box;
    }
  }

  _stopChart() {
    clearInterval(this._chartTimer);
    this._chartTimer = undefined;
  }

  async _loadChart() {
    try {
      this._chart = await this.hass.callWS({
        type: "tempo_planner/power/history",
        hours: this._chartHours,
      });
      this._chartError = null;
    } catch (err) {
      this._chartError = err.message || String(err);
    }
  }

  _subscribe() {
    if (this._unsub || !this.hass) return;
    this._unsub = this.hass.connection.subscribeMessage(
      (snapshot) => {
        this._snapshot = snapshot;
      },
      { type: "tempo_planner/subscribe" },
    );
    this._unsub.catch((err) => {
      this._error = err.message || String(err);
      this._unsub = undefined;
    });
  }

  _unsubscribe() {
    if (this._unsub) {
      this._unsub.then((unsub) => unsub()).catch(() => {});
      this._unsub = undefined;
    }
  }

  // --- Texts -----------------------------------------------------------

  _t(key, values = {}) {
    const language = (this.hass?.language || "en").split("-")[0];
    const texts = TEXTS[language] || TEXTS.en;
    let text = texts[key] ?? TEXTS.en[key] ?? key;
    for (const [name, value] of Object.entries(values)) {
      text = text.replace(`{${name}}`, value);
    }
    return text;
  }

  _time(iso) {
    if (!iso) return "";
    const when = new Date(iso);
    const options = { hour: "2-digit", minute: "2-digit" };
    if (when.toDateString() !== new Date().toDateString()) options.weekday = "short";
    return when.toLocaleTimeString(this.hass?.locale?.language || this.hass?.language, options);
  }

  _entityName(entityId) {
    const state = this.hass?.states?.[entityId];
    return state?.attributes?.friendly_name || entityId;
  }

  // --- Rendering -------------------------------------------------------

  render() {
    return html`
      <div class="toolbar">
        <ha-menu-button .hass=${this.hass} .narrow=${this.narrow}></ha-menu-button>
        <div class="title">Tempo Planner</div>
      </div>
      <div class="tabs" role="tablist">
        ${["now", "appliances", "power", "announcements"].map(
          (tab) => html`
            <button
              role="tab"
              aria-selected=${this._tab === tab}
              class=${this._tab === tab ? "tab active" : "tab"}
              @click=${() => this._select(tab)}
            >
              ${this._t(tab)}
            </button>
          `,
        )}
      </div>
      <div class="content">
        ${this._error
          ? html`<div class="banner error">${this._t("error", { message: this._error })}</div>`
          : nothing}
        ${!this._snapshot
          ? html`<div class="loading">…</div>`
          : this._tab === "now"
            ? this._renderNow()
            : this._tab === "appliances"
              ? this._renderAppliances()
              : this._tab === "power"
                ? this._renderPower()
                : this._renderAnnouncements()}
      </div>
    `;
  }

  _chip(color) {
    return html`<span class="chip ${color || "unknown"}">${this._t(color || "unknown")}</span>`;
  }

  _renderNow() {
    const s = this._snapshot;
    const shed = s.appliances.filter((a) => a.status.shed);
    const watched = s.appliances.filter((a) => a.status.watched);
    const period = s.offpeak
      ? this._t("offpeak_until", { time: s.offpeak_end })
      : this._t("peak_until", { time: s.offpeak_start });
    return html`
      ${!s.today_color_entity
        ? html`<div class="banner warning">${this._t("no_today_color")}</div>`
        : nothing}
      ${s.power?.power_entity ? this._renderChartCard() : nothing}
      <div class="grid">
      <div class="card">
        <div class="days">
          <div class="day">
            <div class="label">${this._t("today")}</div>
            ${this._chip(s.today)}
          </div>
          <div class="day">
            <div class="label">${this._t("tomorrow")}</div>
            ${this._chip(s.tomorrow)}
          </div>
        </div>
        <div class="period">
          <ha-icon icon=${s.offpeak ? "mdi:weather-night" : "mdi:white-balance-sunny"}></ha-icon>
          ${period}
        </div>
      </div>
      <div class="card">
        <h2>${this._t("shed_now")}</h2>
        ${shed.length === 0
          ? html`<p class="muted">${this._t("nothing_shed")}</p>`
          : html`<ul class="list">
              ${shed.map(
                (a) => html`<li>
                  <ha-icon icon="mdi:flash-off"></ha-icon>
                  <div class="grow">
                    <div class="name">${a.name}</div>
                    <div class="muted">
                      ${this._t(`behaviour_${a.behaviour}`)} ·
                      ${this._t(`reason_${a.status.reason}`)} ·
                      ${this._t("until", { time: this._time(a.status.until) })}
                    </div>
                  </div>
                </li>`,
              )}
            </ul>`}
        ${watched.length
          ? html`<h3>${this._t("watched_now")}</h3>
              <ul class="list">
                ${watched.map(
                  (a) => html`<li>
                    <ha-icon icon=${a.status.running ? "mdi:alert" : "mdi:eye-outline"}></ha-icon>
                    <div class="grow">
                      <div class="name">
                        ${a.name}
                        ${a.status.running
                          ? html`<span class="badge">${this._t("running_now")}</span>`
                          : nothing}
                      </div>
                      <div class="muted">
                        ${this._t("watched_help")} ·
                        ${this._t("until", { time: this._time(a.status.until) })}
                      </div>
                    </div>
                  </li>`,
                )}
              </ul>`
          : nothing}
      </div>
      </div>
    `;
  }

  // --- Power chart ---------------------------------------------------------

  _renderChartCard() {
    return html`
      <div class="card chart-card">
        <div class="chart-head">
          <h2>${this._t("chart_title")}</h2>
          <div class="range" role="group">
            ${[6, 24].map(
              (hours) => html`<button
                class=${this._chartHours === hours ? "active" : ""}
                aria-pressed=${this._chartHours === hours}
                @click=${() => {
                  this._chartHours = hours;
                  this._chart = null;
                  this._loadChart();
                }}
              >
                ${this._t("chart_hours", { hours })}
              </button>`,
            )}
          </div>
        </div>
        ${this._chartError
          ? html`<div class="banner error">${this._t("error", { message: this._chartError })}</div>`
          : nothing}
        <div class="chart-box">${this._renderChart()}</div>
      </div>
    `;
  }

  _palette() {
    return this.hass?.themes?.darkMode ? SERIES.dark : SERIES.light;
  }

  _chartModel() {
    const c = this._chart;
    const n = c.count;
    const start = new Date(c.start).getTime();
    const step = c.step * 1000;
    const palette = this._palette();
    const appliances = c.appliances.map((a) => {
      const avoided = new Array(n).fill(0);
      for (const shed of a.shed) {
        const from = new Date(shed.start).getTime();
        const to = new Date(shed.end).getTime();
        for (let i = 0; i < n; i++) {
          const t = start + i * step;
          if (t + step > from && t < to && shed.avoided_kw) avoided[i] = shed.avoided_kw;
        }
      }
      return { ...a, color: palette[a.slot % palette.length], avoided };
    });
    const drawn = appliances.filter((a) => a.power);
    // Appliances stacked from the bottom, avoided power stacked above the grid line.
    const stack = [];
    let below = new Array(n).fill(0);
    for (const a of drawn) {
      const top = below.map((v, i) => v + (a.power[i] ?? 0));
      stack.push({ appliance: a, low: below, high: top });
      below = top;
    }
    const house = c.house && c.house.some((v) => v !== null) ? c.house : null;
    // What shedding avoided comes on top of what was used: the house, or the grid.
    const avoided = [];
    let base = (c.grid || below).map((g, i) => Math.max(g ?? below[i], house?.[i] ?? 0));
    for (const a of appliances.filter((a) => a.avoided.some((v) => v > 0))) {
      const top = base.map((v, i) => v + a.avoided[i]);
      avoided.push({ appliance: a, low: base, high: top });
      base = top;
    }
    const peak = Math.max(
      1,
      ...base,
      ...below,
      ...(c.grid || []).map((v) => v ?? 0),
      ...c.soft.map((v) => v ?? 0),
      c.hard ?? 0,
    );
    const sources = this.hass?.themes?.darkMode ? SOURCES.dark : SOURCES.light;
    const top = Math.max(peak, ...(house || []).map((v) => v ?? 0));
    return { c, n, start, step, appliances, stack, avoided, house, sources, top: niceCeil(top * 1.05) };
  }

  _renderChart() {
    if (!this._chart) return html`<div class="loading">…</div>`;
    const m = this._chartModel();
    const { c, n } = m;
    if (!c.grid || c.grid.every((v) => v === null)) {
      return html`<p class="muted">${this._t("chart_no_data")}</p>`;
    }
    const W = Math.max(this._chartWidth || 0, 280);
    const H = 240;
    const ml = 44;
    const mr = 12;
    const mt = 10;
    const mb = 24;
    const pw = W - ml - mr;
    const ph = H - mt - mb;
    const x = (i) => ml + (n > 1 ? (i / (n - 1)) * pw : 0);
    const y = (v) => mt + ph - (Math.max(v, 0) / m.top) * ph;
    const area = (low, high) => {
      let d = `M${x(0)},${y(high[0])}`;
      for (let i = 1; i < n; i++) d += `L${x(i)},${y(high[i])}`;
      for (let i = n - 1; i >= 0; i--) d += `L${x(i)},${y(low[i])}`;
      return `${d}Z`;
    };
    const line = (values) => {
      let d = "";
      let pen = false;
      values.forEach((v, i) => {
        if (v === null || v === undefined) {
          pen = false;
          return;
        }
        d += `${pen ? "L" : "M"}${x(i)},${y(v)}`;
        pen = true;
      });
      return d;
    };
    // One segment per run of equal values, so the dashes run on.
    const steps = (values) => {
      let d = "";
      let i = 0;
      while (i < n) {
        const v = values[i];
        let j = i + 1;
        while (j < n && values[j] === v) j++;
        if (v !== null && v !== undefined) {
          d += `M${x(i)},${y(v)}L${x(Math.min(j, n - 1))},${y(v)}`;
          if (j < n && values[j] !== null && values[j] !== undefined) {
            d += `L${x(j)},${y(values[j])}`;
          }
        }
        i = j;
      }
      return d;
    };
    const lastSoft = [...c.soft].reverse().find((v) => v !== null && v !== undefined);
    const ticks = [];
    const tickStep = niceCeil(m.top / 4);
    for (let v = 0; v <= m.top + 1e-9; v += tickStep) ticks.push(v);
    const every = c.count > 100 ? 3 : 1;
    const hours = [];
    for (let i = 0; i < n; i++) {
      const t = new Date(m.start + i * m.step);
      if (t.getMinutes() === 0 && t.getHours() % every === 0) hours.push({ i, t });
    }
    const hover = this._hover;
    const shed = m.appliances.filter((a) => a.shed.length);
    return html`
      <svg
        width=${W}
        height=${H}
        role="img"
        aria-label=${this._t("chart_summary", { hours: this._chartHours })}
        @pointermove=${(ev) => this._onHover(ev, ml, pw, n)}
        @pointerleave=${() => (this._hover = null)}
      >
        <defs>
          ${m.appliances.map(
            (a) => svg`<pattern
              id=${`hatch-${a.slot}`}
              patternUnits="userSpaceOnUse"
              width="6"
              height="6"
              patternTransform="rotate(45)"
            >
              <rect width="6" height="6" fill=${a.color} fill-opacity="0.12"></rect>
              <line x1="0" y1="0" x2="0" y2="6" stroke=${a.color} stroke-width="2"></line>
            </pattern>`,
          )}
        </defs>
        ${ticks.map(
          (v) => svg`<line class="gridline" x1=${ml} x2=${W - mr} y1=${y(v)} y2=${y(v)}></line>
            <text class="tick" x=${ml - 6} y=${y(v) + 4} text-anchor="end">${this._kw(v)}</text>`,
        )}
        ${hours.map(
          ({ i, t }) => svg`<text class="tick" x=${x(i)} y=${H - 6} text-anchor="middle">
            ${t.toLocaleTimeString(this.hass.language, { hour: "2-digit", minute: "2-digit" })}
          </text>`,
        )}
        ${m.stack.map(
          ({ appliance, low, high }) => svg`<path
            class="stack"
            d=${area(low, high)}
            fill=${appliance.color}
            fill-opacity="0.85"
          ></path>`,
        )}
        ${m.house
          ? (() => {
              const grid = c.grid.map((v) => v ?? 0);
              const house = m.house.map((v, i) => v ?? grid[i]);
              const supplyHigh = house.map((h, i) => Math.max(h, grid[i]));
              const chargeLow = house.map((h, i) => Math.min(h, grid[i]));
              return svg`<path
                  d=${area(grid, supplyHigh)}
                  fill=${m.sources.supply}
                  fill-opacity="0.3"
                ></path>
                <path d=${area(chargeLow, grid)} fill=${m.sources.charge} fill-opacity="0.3"></path>
                <path class="house-line" d=${line(m.house)}></path>`;
            })()
          : nothing}
        ${m.avoided.map(
          ({ appliance, low, high }) => svg`<path
            class="stack"
            d=${area(low, high)}
            fill=${`url(#hatch-${appliance.slot})`}
          ></path>`,
        )}
        <path class="soft-line" d=${steps(c.soft)}></path>
        ${lastSoft !== undefined
          ? svg`<text class="limit-label" x=${W - mr - 2} y=${y(lastSoft) - 5} text-anchor="end">
              ${this._t("chart_soft")} ${this._kw(lastSoft)} kW
            </text>`
          : nothing}
        ${c.hard !== null && c.hard !== undefined
          ? svg`<line class="hard-line" x1=${ml} x2=${W - mr} y1=${y(c.hard)} y2=${y(c.hard)}></line>
              <text class="limit-label" x=${W - mr - 2} y=${y(c.hard) - 5} text-anchor="end">
                ${this._t("chart_hard")} ${this._kw(c.hard)} kW
              </text>`
          : nothing}
        <path class="grid-line" d=${line(c.grid)}></path>
        ${hover !== null
          ? svg`<line class="cursor" x1=${x(hover)} x2=${x(hover)} y1=${mt} y2=${mt + ph}></line>
              ${c.grid[hover] !== null
                ? svg`<circle class="dot" cx=${x(hover)} cy=${y(c.grid[hover])} r="4"></circle>`
                : nothing}`
          : nothing}
      </svg>
      ${hover !== null ? this._renderTooltip(m, hover, x(hover), W) : nothing}
      <div class="legend">
        <span><i class="key grid"></i>${this._t("chart_grid")}</span>
        ${m.house
          ? html`<span><i class="key house"></i>${this._t("chart_house")}</span>
              <span
                ><i class="key" style="background: ${m.sources.supply}; opacity: 0.5"></i>${this._t(
                  "chart_supply",
                )}</span
              >
              <span
                ><i class="key" style="background: ${m.sources.charge}; opacity: 0.5"></i>${this._t(
                  "chart_charge",
                )}</span
              >`
          : nothing}
        <span><i class="key soft"></i>${this._t("chart_soft")}</span>
        ${c.hard !== null && c.hard !== undefined
          ? html`<span><i class="key hard"></i>${this._t("chart_hard")}</span>`
          : nothing}
        ${m.stack.map(
          ({ appliance }) =>
            html`<span><i class="key" style="background: ${appliance.color}"></i>${appliance.name}</span>`,
        )}
        ${m.avoided.length
          ? html`<span><i class="key avoided"></i>${this._t("chart_avoided")}</span>`
          : nothing}
      </div>
      ${shed.length
        ? html`<div class="timeline" style="--left: ${ml}px; --right: ${mr}px">
            ${shed.map(
              (a) => html`<div class="row">
                <span class="row-name">${a.name}</span>
                <div class="track">
                  ${a.shed.map((s) => {
                    const span = m.n * m.step;
                    const from = (new Date(s.start).getTime() - m.start) / span;
                    const to = (new Date(s.end).getTime() - m.start) / span;
                    return html`<span
                      class="bar ${s.reason}"
                      style="left: ${from * 100}%; width: ${Math.max((to - from) * 100, 0.5)}%; --c: ${a.color}"
                      title="${this._t("chart_shed")} · ${this._t(`reason_${s.reason}`)} · ${this._time(s.start)} → ${this._time(s.end)}"
                    ></span>`;
                  })}
                </div>
              </div>`,
            )}
          </div>`
        : nothing}
    `;
  }

  _onHover(ev, ml, pw, n) {
    const rect = ev.currentTarget.getBoundingClientRect();
    const i = Math.round(((ev.clientX - rect.left - ml) / pw) * (n - 1));
    this._hover = i < 0 || i >= n ? null : i;
  }

  _renderTooltip(m, i, left, width) {
    const c = m.c;
    const at = new Date(m.start + i * m.step);
    const value = (v) => (v === null || v === undefined ? "–" : `${this._kw(v)} kW`);
    const flip = left > width / 2;
    return html`<div
      class="tooltip"
      style=${flip ? `right: ${width - left + 12}px` : `left: ${left + 12}px`}
    >
      <div class="tip-time">
        ${at.toLocaleTimeString(this.hass.language, { hour: "2-digit", minute: "2-digit" })}
      </div>
      <div><i class="key grid"></i>${this._t("chart_grid")} <b>${value(c.grid[i])}</b></div>
      ${m.house && m.house[i] !== null
        ? html`<div><i class="key house"></i>${this._t("chart_house")} <b>${value(m.house[i])}</b></div>
            ${m.house[i] - (c.grid[i] ?? 0) > 0.05
              ? html`<div>
                  <i class="key" style="background: ${m.sources.supply}"></i>${this._t("chart_supply")}
                  <b>${value(m.house[i] - (c.grid[i] ?? 0))}</b>
                </div>`
              : nothing}
            ${(c.grid[i] ?? 0) - m.house[i] > 0.05
              ? html`<div>
                  <i class="key" style="background: ${m.sources.charge}"></i>${this._t("chart_charge")}
                  <b>${value((c.grid[i] ?? 0) - m.house[i])}</b>
                </div>`
              : nothing}`
        : nothing}
      ${c.soft[i] !== null
        ? html`<div><i class="key soft"></i>${this._t("chart_soft")} <b>${value(c.soft[i])}</b></div>`
        : nothing}
      ${m.stack.map(
        ({ appliance }) =>
          html`<div>
            <i class="key" style="background: ${appliance.color}"></i>${appliance.name}
            <b>${value(appliance.power[i])}</b>
          </div>`,
      )}
      ${m.avoided
        .filter(({ appliance }) => appliance.avoided[i] > 0)
        .map(
          ({ appliance }) =>
            html`<div>
              <i class="key avoided"></i>${appliance.name} (${this._t("chart_avoided").toLowerCase()})
              <b>${value(appliance.avoided[i])}</b>
            </div>`,
        )}
    </div>`;
  }

  _renderAppliances() {
    const appliances = this._snapshot.appliances;
    return html`
      ${this._draft && !this._draft.id ? this._renderEditor() : nothing}
      ${appliances.length === 0 && !this._draft
        ? html`<div class="card"><p class="muted">${this._t("no_appliance")}</p></div>`
        : nothing}
      <div class="grid">
        ${appliances.map((a) =>
          this._draft?.id === a.id ? this._renderEditor() : this._renderAppliance(a),
        )}
      </div>
      ${this._draft
        ? nothing
        : html`<button class="primary add" @click=${() => this._edit(null)}>
            <ha-icon icon="mdi:plus"></ha-icon>${this._t("add")}
          </button>`}
    `;
  }

  _renderAppliance(a) {
    const behaviour =
      a.behaviour === "reduced" && a.reduced_option
        ? `${this._t("behaviour_reduced")} → ${a.reduced_option}`
        : this._t(`behaviour_${a.behaviour}`);
    const details = [
      behaviour,
      this._t(`hours_${a.hours}`),
      this._t("priority", { value: a.priority }),
    ];
    const scheduled = COLORS.filter((c) => a[`schedule_${c}`]);
    if (a.hard_only) details.push(this._t("hard_only"));
    if (scheduled.length) {
      details.push(
        this._t("schedules", { colors: scheduled.map((c) => this._t(c).toLowerCase()).join(", ") }),
      );
    }
    return html`
      <div class="card appliance ${a.enabled ? "" : "disabled"}">
        <div class="row">
          <div class="grow">
            <div class="name">
              ${a.name}
              ${a.status.shed
                ? html`<span class="badge"
                    >${this._t("shed")} · ${this._t("until", { time: this._time(a.status.until) })}</span
                  >`
                : a.status.watched
                  ? html`<span class="badge ${a.status.running ? "" : "quiet"}"
                      >${this._t(a.status.running ? "running_now" : "watched")} ·
                      ${this._t("until", { time: this._time(a.status.until) })}</span
                    >`
                  : nothing}
            </div>
            <div class="muted entity">${a.entity_id}</div>
            <div class="muted">
              ${a.colors.map((c) => this._chip(c))} ${details.join(" · ")}
            </div>
          </div>
          <label class="switch" title=${a.enabled ? this._t("enabled") : this._t("disabled")}>
            <input
              type="checkbox"
              .checked=${a.enabled}
              aria-label=${this._t("field_enabled")}
              @change=${(ev) => this._toggle(a, ev.target.checked)}
            />
            <span class="slider"></span>
          </label>
        </div>
        <div class="actions">
          <button @click=${() => this._edit(a)}>${this._t("edit")}</button>
          <button class="danger" @click=${() => this._delete(a)}>${this._t("delete")}</button>
        </div>
      </div>
    `;
  }

  _renderEditor() {
    const draft = this._draft;
    return html`
      <div class="card editor">
        <h2>${draft.id ? draft.name : this._t("new_appliance")}</h2>
        <p class="muted">${this._t(`help_${draft.behaviour}`)}</p>
        ${this._formsReady
          ? html`${this._form(draft, this._schemaTop(draft))}
              ${draft.entity_id
                ? html`<div class="muted entity picked">${draft.entity_id}</div>`
                : nothing}
              ${this._form(draft, this._schemaRest(draft))}
              ${draft.behaviour === "alert"
                ? nothing
                : html`<h3>${this._t("schedules_title")}</h3>
                    <p class="muted">${this._t("schedules_help")}</p>
                    ${this._form(draft, this._schemaSchedules(draft))}`}`
          : html`<div class="loading">…</div>`}
        ${this._formError
          ? html`<div class="banner error">${this._t("error", { message: this._formError })}</div>`
          : nothing}
        <div class="actions">
          <button @click=${this._cancel}>${this._t("cancel")}</button>
          <button class="primary" ?disabled=${this._saving || !this._valid(draft)} @click=${this._save}>
            ${this._t("save")}
          </button>
        </div>
      </div>
    `;
  }

  _modes(entityId) {
    const state = this.hass.states[entityId];
    if (!state) return [];
    const domain = entityId.split(".")[0];
    const attributes = state.attributes;
    if (domain === "climate") return attributes.preset_modes || [];
    if (domain === "water_heater") return attributes.operation_list || [];
    return attributes.options || [];
  }

  _form(draft, schema) {
    return html`<ha-form
      .hass=${this.hass}
      .data=${draft}
      .schema=${schema}
      .computeLabel=${(field) => this._t(`field_${field.name}`)}
      @value-changed=${this._changed}
    ></ha-form>`;
  }

  // What to do, then to which entity: the entity's domains follow the behaviour.
  _schemaTop(draft) {
    const option = (value, label) => ({ value, label });
    const domains =
      draft.behaviour === "off"
        ? OFF_DOMAINS
        : draft.behaviour === "reduced"
          ? REDUCED_DOMAINS
          : undefined;
    return [
      {
        name: "behaviour",
        required: true,
        selector: {
          select: {
            mode: "dropdown",
            options: ["off", "reduced", "alert"].map((b) => option(b, this._t(`behaviour_${b}`))),
          },
        },
      },
      {
        name: "entity_id",
        required: true,
        selector: { entity: domains ? { domain: domains } : {} },
      },
    ];
  }

  _schemaRest(draft) {
    const option = (value, label) => ({ value, label });
    const behaviour = draft.behaviour;
    const notify = Object.keys(this.hass.services?.notify || {})
      .sort()
      .map((service) => option(`notify.${service}`, service));
    // A plain string field: the text selector leaves a gap below it.
    const schema = [{ name: "name", required: true, type: "string" }];
    if (behaviour === "reduced") {
      schema.push({
        name: "reduced_option",
        required: true,
        selector: {
          select: {
            mode: "dropdown",
            custom_value: true,
            options: this._modes(draft.entity_id).map((m) => option(m, m)),
          },
        },
      });
    }
    if (behaviour === "alert") {
      schema.push(
        { name: "running_entity", selector: { entity: {} } },
        {
          name: "running_above",
          selector: { number: { min: 0, step: 10, mode: "box", unit_of_measurement: "W" } },
        },
        { name: "running_states", selector: { text: {} } },
      );
    }
    schema.push(
      {
        name: "colors",
        required: true,
        selector: {
          select: { multiple: true, options: COLORS.map((c) => option(c, this._t(c))) },
        },
      },
      {
        name: "hours",
        required: true,
        selector: {
          select: {
            mode: "dropdown",
            options: ["peak", "day"].map((h) => option(h, this._t(`option_hours_${h}`))),
          },
        },
      },
      {
        name: "notify",
        selector: { select: { mode: "dropdown", custom_value: true, options: notify } },
      },
      { name: "priority", selector: { number: { min: 0, max: 100, step: 1, mode: "box" } } },
      { name: "power_entity", selector: { entity: { domain: "sensor", device_class: "power" } } },
      {
        name: "power_kw",
        selector: { number: { min: 0, max: 50, step: 0.1, mode: "box", unit_of_measurement: "kW" } },
      },
      { name: "hard_only", selector: { boolean: {} } },
      { name: "enabled", selector: { boolean: {} } },
    );
    return schema;
  }

  _schemaSchedules(draft) {
    const schema = [];
    if (draft.behaviour === "reduced") {
      schema.push({
        name: "normal_option",
        selector: {
          select: {
            mode: "dropdown",
            custom_value: true,
            options: this._modes(draft.entity_id).map((m) => ({ value: m, label: m })),
          },
        },
      });
    }
    for (const color of COLORS) {
      schema.push({ name: `schedule_${color}`, selector: { entity: { domain: "schedule" } } });
    }
    return schema;
  }

  _valid(draft) {
    if (!draft.name || !draft.entity_id || !draft.colors?.length) return false;
    if (draft.behaviour === "reduced" && !draft.reduced_option) return false;
    const scheduled = COLORS.some((c) => draft[`schedule_${c}`]);
    if (scheduled && draft.behaviour === "reduced" && !draft.normal_option) return false;
    return true;
  }

  // --- Actions ---------------------------------------------------------

  async _edit(appliance) {
    this._formError = null;
    this._draft = appliance
      ? {
          ...EMPTY,
          ...appliance,
          running_states: (appliance.running_states || []).join(", "),
        }
      : { ...EMPTY };
    delete this._draft.status;
    if (!this._formsReady) {
      try {
        await loadForms();
        this._formsReady = true;
      } catch (err) {
        this._formError = err.message || String(err);
      }
    }
  }

  _changed(ev) {
    // Two forms share the draft: each sends only its own fields.
    const value = { ...this._draft, ...ev.detail.value };
    // Another behaviour: a mode chosen for the old entity no longer applies.
    if (value.entity_id !== this._draft.entity_id || value.behaviour !== this._draft.behaviour) {
      if (!this._modes(value.entity_id || "").includes(value.reduced_option)) {
        value.reduced_option = null;
      }
    }
    // Named after its entity until a name is typed.
    if (!value.name && value.entity_id) value.name = this._entityName(value.entity_id);
    this._draft = value;
  }

  _cancel() {
    this._draft = null;
    this._formError = null;
  }

  _payload(draft) {
    const appliance = { ...draft };
    appliance.running_states = String(draft.running_states || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!appliance.running_states.length) appliance.running_states = ["on"];
    for (const key of Object.keys(appliance)) {
      if (appliance[key] === "" || appliance[key] === undefined) appliance[key] = null;
    }
    if (appliance.behaviour === "alert") {
      for (const color of COLORS) appliance[`schedule_${color}`] = null;
    }
    if (appliance.priority === null) appliance.priority = 0;
    if (appliance.running_above === null) appliance.running_above = 50;
    if (!appliance.id) delete appliance.id;
    return appliance;
  }

  async _save() {
    this._saving = true;
    this._formError = null;
    try {
      await this.hass.callWS({
        type: "tempo_planner/appliances/save",
        appliance: this._payload(this._draft),
      });
      this._draft = null;
    } catch (err) {
      this._formError = err.message || String(err);
    } finally {
      this._saving = false;
    }
  }

  async _toggle(appliance, enabled) {
    try {
      const { status, ...rest } = appliance;
      await this.hass.callWS({
        type: "tempo_planner/appliances/save",
        appliance: { ...rest, enabled },
      });
    } catch (err) {
      this._error = err.message || String(err);
    }
  }

  // --- Power ---------------------------------------------------------------

  async _select(tab) {
    this._tab = tab;
    if ((tab === "power" || tab === "announcements") && !this._formsReady) {
      try {
        await loadForms();
        this._formsReady = true;
      } catch (err) {
        this._powerError = err.message || String(err);
      }
    }
  }

  _powerSettings() {
    const { power_kw, level, soft_limit_now, hard_limit_now, ...settings } = this._snapshot.power;
    return settings;
  }

  _applianceKw(a) {
    const state = a.power_entity ? this.hass.states[a.power_entity] : null;
    if (state && !isNaN(Number(state.state))) {
      const unit = (state.attributes.unit_of_measurement || "W").toLowerCase();
      return unit === "kw" ? Number(state.state) : Number(state.state) / 1000;
    }
    return a.power_kw;
  }

  _kw(value) {
    return Number(value).toLocaleString(this.hass?.language, { maximumFractionDigits: 1 });
  }

  _renderPower() {
    const p = this._snapshot.power;
    const draft = this._powerDraft || this._powerSettings();
    const order = this._snapshot.appliances.filter((a) => a.behaviour !== "alert");
    return html`
      <div class="grid">
      <div class="card">
        <h2>${this._t("power_now")}</h2>
        ${!p.enabled
          ? html`<p class="muted">${this._t("power_off")}</p>`
          : p.power_kw === null || p.power_kw === undefined
            ? html`<p class="muted">${this._t("power_no_reading")}</p>`
            : this._renderGauge(p)}
      </div>
      <div class="card">
        <h2>${this._t("power_order")}</h2>
        <p class="muted">${this._t("power_order_help")}</p>
        <ol class="order">
          ${order.map((a, index) => {
            const kw = this._applianceKw(a);
            return html`<li>
              <div class="grow">
                <div class="name">${a.name}</div>
                <div class="muted">
                  ${kw === null || kw === undefined ? this._t("unknown_power") : `${this._kw(kw)} kW`}
                  ${a.hard_only ? html` · ${this._t("hard_only")}` : nothing}
                  ${a.status.shed
                    ? html` · <span class="badge">${this._t("shed")}</span>`
                    : nothing}
                </div>
              </div>
              <button
                class="icon"
                title=${this._t("up")}
                aria-label=${this._t("up")}
                ?disabled=${index === 0}
                @click=${() => this._move(order, index, -1)}
              >
                ▲
              </button>
              <button
                class="icon"
                title=${this._t("down")}
                aria-label=${this._t("down")}
                ?disabled=${index === order.length - 1}
                @click=${() => this._move(order, index, 1)}
              >
                ▼
              </button>
            </li>`;
          })}
        </ol>
      </div>
      </div>
      <div class="card editor">
        <h2>${this._t("power_settings")}</h2>
        <p class="muted">${this._t("power_help")}</p>
        ${this._formsReady
          ? html`<ha-form
              .hass=${this.hass}
              .data=${draft}
              .schema=${this._powerSchema()}
              .computeLabel=${(field) => this._t(POWER_LABELS[field.name] || `field_${field.name}`)}
              @value-changed=${(ev) => {
                this._powerDraft = { ...draft, ...ev.detail.value };
                this._powerSaved = false;
              }}
            ></ha-form>`
          : html`<div class="loading">…</div>`}
        ${this._powerError
          ? html`<div class="banner error">${this._t("error", { message: this._powerError })}</div>`
          : nothing}
        <div class="actions">
          ${this._powerSaved ? html`<span class="muted">${this._t("saved")}</span>` : nothing}
          <button
            ?disabled=${!this._powerDraft}
            @click=${() => {
              this._powerDraft = null;
              this._powerError = null;
            }}
          >
            ${this._t("cancel")}
          </button>
          <button class="primary" ?disabled=${!this._powerDraft} @click=${this._savePower}>
            ${this._t("save")}
          </button>
        </div>
      </div>
    `;
  }

  _renderGauge(p) {
    const top = Math.max(p.hard_limit_now || 0, p.soft_limit_now || 0, p.power_kw, 1) * 1.15;
    const pct = (value) => `${Math.min(100, (Math.max(value, 0) / top) * 100)}%`;
    return html`
      <div class="power">
        <span class="value">${this._kw(Math.max(p.power_kw, 0))} kW</span>
        <span class="level ${p.level}">${this._t(`level_${p.level}`)}</span>
      </div>
      <div class="gauge" role="img" aria-label="${this._kw(p.power_kw)} kW">
        <div class="fill ${p.level}" style="width: ${pct(p.power_kw)}"></div>
        ${p.soft_limit_now !== null && p.soft_limit_now !== undefined
          ? html`<div class="mark soft" style="left: ${pct(p.soft_limit_now)}"></div>`
          : nothing}
        ${p.hard_limit_now !== null && p.hard_limit_now !== undefined
          ? html`<div class="mark hard" style="left: ${pct(p.hard_limit_now)}"></div>`
          : nothing}
      </div>
      <div class="muted">
        ${p.soft_limit_now !== null && p.soft_limit_now !== undefined
          ? this._t("soft_limit", { value: this._kw(p.soft_limit_now) })
          : nothing}
        ${p.hard_limit_now !== null && p.hard_limit_now !== undefined
          ? html` · ${this._t("hard_limit", { value: this._kw(p.hard_limit_now) })}`
          : nothing}
      </div>
    `;
  }

  _powerSchema() {
    const kw = { number: { min: 0, max: 100, step: 0.1, mode: "box", unit_of_measurement: "kW" } };
    const seconds = { number: { min: 0, max: 3600, step: 5, mode: "box", unit_of_measurement: "s" } };
    return [
      { name: "enabled", selector: { boolean: {} } },
      { name: "power_entity", selector: { entity: { domain: "sensor", device_class: "power" } } },
      { name: "house_entity", selector: { entity: { domain: "sensor", device_class: "power" } } },
      { name: "soft_limit_kw", selector: kw },
      { name: "hard_limit_kw", selector: kw },
      {
        name: "soft_limits",
        type: "expandable",
        title: this._t("field_soft_limits"),
        schema: ["blue", "white", "red"].flatMap((c) =>
          ["peak", "offpeak"].map((period) => ({ name: `${c}_${period}`, selector: kw })),
        ),
      },
      { name: "restore_margin_kw", selector: kw },
      { name: "soft_delay_s", selector: seconds },
      { name: "hard_delay_s", selector: seconds },
      { name: "restore_delay_s", selector: seconds },
    ];
  }

  async _savePower() {
    this._powerError = null;
    const power = { ...this._powerDraft };
    for (const key of Object.keys(power)) {
      if (power[key] === "" || power[key] === undefined) power[key] = null;
    }
    power.soft_limits = Object.fromEntries(
      Object.entries(power.soft_limits || {}).filter(([, v]) => v !== null && v !== "" && v !== undefined),
    );
    try {
      await this.hass.callWS({ type: "tempo_planner/power/save", power });
      this._powerDraft = null;
      this._powerSaved = true;
    } catch (err) {
      this._powerError = err.message || String(err);
    }
  }

  // --- Announcements -----------------------------------------------------

  _renderAnnouncements() {
    const draft = this._announceDraft || this._snapshot.announcements;
    const option = (value, label) => ({ value, label });
    const colors = {
      select: { multiple: true, options: COLORS.map((c) => option(c, this._t(c))) },
    };
    const notify = Object.keys(this.hass.services?.notify || {})
      .sort()
      .map((service) => option(`notify.${service}`, service));
    const section = (title, help, schema, channel) => html`
      <div class="section">
        <div class="section-head">
          <h3>${this._t(title)}</h3>
          ${channel
            ? html`<button
                ?disabled=${!!this._announceDraft}
                title=${this._t("announce_test_help")}
                @click=${() => this._testAnnouncement(channel)}
              >
                ${this._t("announce_test")}
              </button>`
            : nothing}
        </div>
        ${help ? html`<p class="muted">${this._t(help)}</p>` : nothing}
        <ha-form
          .hass=${this.hass}
          .data=${draft}
          .schema=${schema}
          .computeLabel=${(field) => this._t(`field_${field.name}`)}
          @value-changed=${(ev) => {
            this._announceDraft = { ...draft, ...ev.detail.value };
            this._announceNote = null;
          }}
        ></ha-form>
      </div>
    `;
    if (!this._formsReady) return html`<div class="loading">…</div>`;
    return html`
      <div class="card editor">
        <h2>${this._t("announcements")}</h2>
        <p class="muted">${this._t("announcements_help")}</p>
        <div class="grid">
          ${section(
            "announce_notify",
            "announce_notify_help",
            [
              { name: "notify_enabled", selector: { boolean: {} } },
              { name: "notify_colors", selector: colors },
              {
                name: "notify_targets",
                selector: { select: { multiple: true, custom_value: true, options: notify } },
              },
            ],
            "notify",
          )}
          ${section(
            "announce_voice",
            "announce_voice_help",
            [
              { name: "voice_enabled", selector: { boolean: {} } },
              { name: "voice_colors", selector: colors },
              { name: "voice_time", selector: { time: {} } },
              { name: "tts_entity", selector: { entity: { domain: "tts" } } },
              {
                name: "media_players",
                selector: { entity: { domain: "media_player", multiple: true } },
              },
              { name: "voice_only_home", selector: { boolean: {} } },
            ],
            "voice",
          )}
        </div>
        ${section("announce_car", null, [
          {
            name: "car_reminder_pct",
            selector: { number: { min: 0, max: 100, step: 5, mode: "box", unit_of_measurement: "%" } },
          },
        ])}
        ${this._announceError
          ? html`<div class="banner error">${this._t("error", { message: this._announceError })}</div>`
          : nothing}
        <div class="actions">
          ${this._announceNote ? html`<span class="muted">${this._t(this._announceNote)}</span>` : nothing}
          <button
            ?disabled=${!this._announceDraft}
            @click=${() => {
              this._announceDraft = null;
              this._announceError = null;
            }}
          >
            ${this._t("cancel")}
          </button>
          <button class="primary" ?disabled=${!this._announceDraft} @click=${this._saveAnnouncements}>
            ${this._t("save")}
          </button>
        </div>
      </div>
    `;
  }

  async _saveAnnouncements() {
    this._announceError = null;
    const announcements = { ...this._announceDraft };
    for (const key of ["tts_entity", "car_reminder_pct"]) {
      if (announcements[key] === "" || announcements[key] === undefined) announcements[key] = null;
    }
    try {
      await this.hass.callWS({ type: "tempo_planner/announcements/save", announcements });
      this._announceDraft = null;
      this._announceNote = "saved";
    } catch (err) {
      this._announceError = err.message || String(err);
    }
  }

  async _testAnnouncement(channel) {
    this._announceError = null;
    try {
      await this.hass.callWS({ type: "tempo_planner/announcements/test", channel });
      this._announceNote = "announce_sent";
    } catch (err) {
      this._announceError = err.message || String(err);
    }
  }

  async _move(order, index, step) {
    const moved = [...order];
    [moved[index], moved[index + step]] = [moved[index + step], moved[index]];
    try {
      for (const [priority, appliance] of moved.entries()) {
        if (appliance.priority === priority) continue;
        const { status, ...rest } = appliance;
        await this.hass.callWS({
          type: "tempo_planner/appliances/save",
          appliance: { ...rest, priority },
        });
      }
    } catch (err) {
      this._error = err.message || String(err);
    }
  }

  async _delete(appliance) {
    if (!window.confirm(this._t("confirm_delete", { name: appliance.name }))) return;
    try {
      await this.hass.callWS({
        type: "tempo_planner/appliances/delete",
        appliance_id: appliance.id,
      });
    } catch (err) {
      this._error = err.message || String(err);
    }
  }

  static styles = css`
    :host {
      display: block;
      min-height: 100%;
      background: var(--primary-background-color);
      color: var(--primary-text-color);
      font-family: var(--ha-font-family-body, Roboto, sans-serif);
    }
    .toolbar {
      display: flex;
      align-items: center;
      height: var(--header-height, 56px);
      padding: 0 12px;
      background: var(--app-header-background-color, var(--primary-color));
      color: var(--app-header-text-color, var(--text-primary-color));
      border-bottom: var(--app-header-border-bottom, none);
      box-sizing: border-box;
    }
    .title {
      margin-left: 12px;
      font-size: 20px;
      font-weight: 400;
    }
    .tabs {
      display: flex;
      gap: 4px;
      padding: 0 16px;
      /* Four tabs don't fit a phone: they scroll, not the page. */
      overflow-x: auto;
      scrollbar-width: none;
      background: var(--app-header-background-color, var(--primary-color));
    }
    .tab {
      background: none;
      border: none;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      color: var(--app-header-text-color, var(--text-primary-color));
      opacity: 0.75;
      padding: 12px 16px;
      font: inherit;
      font-weight: 500;
      white-space: nowrap;
      cursor: pointer;
    }
    .tab.active {
      opacity: 1;
      border-bottom-color: currentColor;
    }
    .content {
      max-width: 1600px;
      margin: 0 auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    /* The cards of a tab, side by side on a large screen. */
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 400px), 1fr));
      align-items: start;
      gap: 16px;
    }
    .grid .editor {
      grid-column: 1 / -1;
    }
    .card {
      background: var(--card-background-color, var(--ha-card-background));
      border-radius: var(--ha-card-border-radius, 12px);
      border: 1px solid var(--divider-color);
      box-shadow: var(--ha-card-box-shadow, none);
      padding: 16px;
    }
    .order {
      list-style: none;
      margin: 0;
      padding: 0;
      counter-reset: order;
    }
    .order li {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 0;
      counter-increment: order;
    }
    .order li::before {
      content: counter(order);
      width: 24px;
      color: var(--secondary-text-color);
      font-weight: 500;
    }
    .order li + li {
      border-top: 1px solid var(--divider-color);
    }
    button.icon {
      padding: 4px 10px;
      font-size: 12px;
    }
    .power {
      display: flex;
      align-items: baseline;
      gap: 12px;
      flex-wrap: wrap;
    }
    .power .value {
      font-size: 32px;
      font-weight: 400;
    }
    .level {
      padding: 2px 10px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 500;
      background: var(--success-color, #43a047);
      color: #fff;
    }
    .level.soft,
    .fill.soft {
      background: var(--warning-color, #ffa600);
    }
    .level.hard,
    .fill.hard {
      background: var(--error-color, #db4437);
    }
    .gauge {
      position: relative;
      height: 12px;
      margin: 12px 0 8px;
      border-radius: 6px;
      background: var(--divider-color);
      overflow: hidden;
    }
    .fill {
      height: 100%;
      background: var(--success-color, #43a047);
      transition: width 0.3s;
    }
    .mark {
      position: absolute;
      top: 0;
      bottom: 0;
      width: 2px;
      background: var(--primary-text-color);
      opacity: 0.6;
    }
    .mark.hard {
      opacity: 1;
    }
    .chart-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .chart-head h2 {
      margin: 0;
    }
    .range {
      display: flex;
      gap: 4px;
    }
    .range button {
      padding: 4px 12px;
    }
    .range button.active {
      background: var(--primary-color);
      border-color: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    .chart-box {
      position: relative;
      margin-top: 12px;
    }
    .chart-box svg {
      display: block;
      touch-action: pan-y;
    }
    .gridline {
      stroke: var(--divider-color);
      stroke-width: 1;
    }
    .tick {
      fill: var(--secondary-text-color);
      font-size: 11px;
    }
    .stack {
      stroke: var(--card-background-color, var(--ha-card-background, #fff));
      stroke-width: 1;
    }
    .grid-line {
      fill: none;
      stroke: var(--primary-text-color);
      stroke-width: 2;
      stroke-linejoin: round;
    }
    /* The limits in neutral ink and dashes, apart from the series' colours. */
    .house-line {
      fill: none;
      stroke: var(--secondary-text-color);
      stroke-width: 1.5;
      stroke-linejoin: round;
    }
    .soft-line {
      fill: none;
      stroke: var(--secondary-text-color);
      stroke-width: 2;
      stroke-dasharray: 6 4;
    }
    .limit-label {
      fill: var(--secondary-text-color);
      font-size: 11px;
      paint-order: stroke;
      stroke: var(--card-background-color, #fff);
      stroke-width: 3px;
    }
    .hard-line {
      stroke: var(--error-color, #db4437);
      stroke-width: 2;
      stroke-dasharray: 2 4;
    }
    .cursor {
      stroke: var(--secondary-text-color);
      stroke-width: 1;
    }
    .dot {
      fill: var(--primary-text-color);
      stroke: var(--card-background-color, #fff);
      stroke-width: 2;
    }
    .tooltip {
      position: absolute;
      top: 8px;
      z-index: 1;
      padding: 8px 10px;
      border-radius: 8px;
      background: var(--card-background-color, #fff);
      border: 1px solid var(--divider-color);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      font-size: 13px;
      line-height: 1.6;
      pointer-events: none;
      white-space: nowrap;
    }
    .tip-time {
      font-weight: 500;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 4px 16px;
      margin-top: 8px;
      font-size: 13px;
      color: var(--secondary-text-color);
    }
    .key {
      display: inline-block;
      width: 12px;
      height: 12px;
      margin-right: 6px;
      border-radius: 3px;
      vertical-align: -1px;
    }
    .key.grid {
      height: 2px;
      vertical-align: 3px;
      background: var(--primary-text-color);
    }
    .key.house {
      height: 2px;
      vertical-align: 3px;
      background: var(--secondary-text-color);
    }
    .key.soft,
    .key.hard {
      height: 0;
      vertical-align: 3px;
      border-top: 2px dashed var(--secondary-text-color);
      border-radius: 0;
    }
    .key.hard {
      border-top: 2px dotted var(--error-color, #db4437);
    }
    .key.avoided {
      background: repeating-linear-gradient(
        45deg,
        var(--secondary-text-color) 0 2px,
        transparent 2px 5px
      );
    }
    .timeline {
      margin-top: 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .timeline .row {
      display: grid;
      grid-template-columns: minmax(80px, 160px) 1fr;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }
    .row-name {
      color: var(--secondary-text-color);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .track {
      position: relative;
      height: 12px;
      border-radius: 6px;
      background: var(--divider-color);
    }
    .bar {
      position: absolute;
      top: 0;
      bottom: 0;
      border-radius: 6px;
      background: var(--c);
    }
    .bar.power {
      background: repeating-linear-gradient(45deg, var(--c) 0 3px, transparent 3px 6px);
      border: 1px solid var(--c);
      box-sizing: border-box;
    }
    .editor h3,
    .card > h3 {
      margin: 24px 0 0;
      font-size: 16px;
      font-weight: 500;
    }
    .card h2 {
      margin: 0 0 12px;
      font-size: 18px;
      font-weight: 500;
    }
    .days {
      display: flex;
      gap: 32px;
    }
    .label {
      color: var(--secondary-text-color);
      font-size: 14px;
      margin-bottom: 6px;
    }
    .period {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 16px;
      color: var(--secondary-text-color);
    }
    .chip {
      display: inline-block;
      padding: 2px 10px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 500;
      border: 1px solid transparent;
      margin-right: 4px;
    }
    .chip.blue {
      background: #1e88e5;
      color: #fff;
    }
    .chip.white {
      background: #fff;
      color: #212121;
      border-color: var(--divider-color);
    }
    .chip.red {
      background: #e53935;
      color: #fff;
    }
    .chip.unknown {
      background: var(--disabled-color, #bdbdbd);
      color: var(--primary-text-color);
    }
    .list {
      list-style: none;
      margin: 0;
      padding: 0;
    }
    .list li {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 0;
    }
    .list li + li {
      border-top: 1px solid var(--divider-color);
    }
    .row {
      display: flex;
      align-items: flex-start;
      gap: 12px;
    }
    .grow {
      flex: 1;
      min-width: 0;
    }
    .name {
      font-weight: 500;
      overflow-wrap: anywhere;
    }
    .muted {
      color: var(--secondary-text-color);
      font-size: 14px;
      margin: 4px 0 0;
    }
    .badge.quiet {
      background: var(--secondary-text-color, #727272);
    }
    .badge {
      display: inline-block;
      margin-left: 8px;
      padding: 1px 8px;
      border-radius: 10px;
      background: var(--error-color, #db4437);
      color: #fff;
      font-size: 12px;
      font-weight: 500;
    }
    .entity {
      font-family: var(--ha-font-family-code, monospace);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .entity.picked {
      margin: 4px 0 16px;
    }
    .appliance.disabled .grow {
      opacity: 0.6;
    }
    .section-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
    }
    .section-head h3 {
      margin: 8px 0 0;
      font-size: 16px;
      font-weight: 500;
    }
    .grid + .section {
      margin-top: 16px;
    }
    .actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      margin-top: 12px;
    }
    button {
      font: inherit;
      font-weight: 500;
      padding: 8px 14px;
      border-radius: 18px;
      border: 1px solid var(--divider-color);
      background: none;
      color: var(--primary-color);
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.5;
      cursor: default;
    }
    button.primary {
      background: var(--primary-color);
      border-color: var(--primary-color);
      color: var(--text-primary-color, #fff);
    }
    button.danger {
      color: var(--error-color, #db4437);
    }
    button.add {
      align-self: flex-start;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .banner {
      padding: 12px 16px;
      border-radius: 8px;
    }
    .banner.error {
      background: rgba(219, 68, 55, 0.12);
      color: var(--error-color, #db4437);
    }
    .banner.warning {
      background: rgba(255, 166, 0, 0.14);
      color: var(--warning-color, #ffa600);
    }
    .loading {
      color: var(--secondary-text-color);
      padding: 16px;
      text-align: center;
    }
    .switch {
      position: relative;
      display: inline-block;
      width: 40px;
      height: 22px;
      flex: none;
    }
    .switch input {
      opacity: 0;
      width: 0;
      height: 0;
    }
    .slider {
      position: absolute;
      inset: 0;
      border-radius: 11px;
      background: var(--disabled-color, #bdbdbd);
      cursor: pointer;
      transition: background 0.2s;
    }
    .slider::before {
      content: "";
      position: absolute;
      width: 18px;
      height: 18px;
      left: 2px;
      top: 2px;
      border-radius: 50%;
      background: #fff;
      transition: transform 0.2s;
    }
    .switch input:checked + .slider {
      background: var(--primary-color);
    }
    .switch input:checked + .slider::before {
      transform: translateX(18px);
    }
    .switch input:focus-visible + .slider {
      outline: 2px solid var(--primary-color);
      outline-offset: 2px;
    }
    @media (max-width: 600px) {
      .content {
        padding: 12px;
      }
      .days {
        gap: 20px;
      }
      .tabs {
        padding: 0 4px;
      }
      .tab {
        padding: 12px 10px;
      }
    }
  `;
}

customElements.define("tempo-planner-panel", TempoPlannerPanel);
