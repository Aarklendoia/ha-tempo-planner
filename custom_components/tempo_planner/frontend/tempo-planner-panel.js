// Tempo Planner panel: where the house stands now, and the sheddable appliances.
//
// Plain ES module, no build step: Lit is bundled next to it (lit.js). Home
// Assistant's own elements (ha-form, ha-icon, ha-menu-button) and theme
// variables keep it in line with the rest of the interface.

import { LitElement, html, css, nothing } from "./lit.js";

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
    help_off: "Turned off, back on afterwards if it was on. Turned back on by someone: off again, with a notification.",
    help_reduced: "A mode is forced (Eco, a preset…), the previous one restored afterwards.",
    help_alert: "Nothing is driven: a notification when it starts running while shed.",
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
    help_off: "Coupé, puis rallumé s'il l'était. Rallumé par quelqu'un : recoupé, avec une notification.",
    help_reduced: "Un mode est imposé (Eco, un preset…), puis le précédent est remis.",
    help_alert: "Rien n'est piloté : une notification quand il se met à fonctionner pendant le délestage.",
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
  }

  connectedCallback() {
    super.connectedCallback();
    if (this.hass) this._subscribe();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsubscribe();
  }

  updated(changed) {
    if (changed.has("hass") && this.hass && !this._unsub) this._subscribe();
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
        ${["now", "appliances"].map(
          (tab) => html`
            <button
              role="tab"
              aria-selected=${this._tab === tab}
              class=${this._tab === tab ? "tab active" : "tab"}
              @click=${() => (this._tab = tab)}
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
            : this._renderAppliances()}
      </div>
    `;
  }

  _chip(color) {
    return html`<span class="chip ${color || "unknown"}">${this._t(color || "unknown")}</span>`;
  }

  _renderNow() {
    const s = this._snapshot;
    const shed = s.appliances.filter((a) => a.status.shed);
    const period = s.offpeak
      ? this._t("offpeak_until", { time: s.offpeak_end })
      : this._t("peak_until", { time: s.offpeak_start });
    return html`
      ${!s.today_color_entity
        ? html`<div class="banner warning">${this._t("no_today_color")}</div>`
        : nothing}
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
      </div>
    `;
  }

  _renderAppliances() {
    const appliances = this._snapshot.appliances;
    return html`
      ${this._draft && !this._draft.id ? this._renderEditor() : nothing}
      ${appliances.length === 0 && !this._draft
        ? html`<div class="card"><p class="muted">${this._t("no_appliance")}</p></div>`
        : nothing}
      ${appliances.map((a) =>
        this._draft?.id === a.id ? this._renderEditor() : this._renderAppliance(a),
      )}
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
              ${this._form(draft, this._schemaRest(draft))}`
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
      { name: "enabled", selector: { boolean: {} } },
    );
    return schema;
  }

  _valid(draft) {
    if (!draft.name || !draft.entity_id || !draft.colors?.length) return false;
    if (draft.behaviour === "reduced" && !draft.reduced_option) return false;
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
      cursor: pointer;
    }
    .tab.active {
      opacity: 1;
      border-bottom-color: currentColor;
    }
    .content {
      max-width: 720px;
      margin: 0 auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .card {
      background: var(--card-background-color, var(--ha-card-background));
      border-radius: var(--ha-card-border-radius, 12px);
      border: 1px solid var(--divider-color);
      box-shadow: var(--ha-card-box-shadow, none);
      padding: 16px;
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
    }
  `;
}

customElements.define("tempo-planner-panel", TempoPlannerPanel);
