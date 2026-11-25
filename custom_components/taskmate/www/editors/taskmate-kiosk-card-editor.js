/**
 * TaskMate kiosk card editor (visual card editor).
 *
 * Loaded on demand by taskmate-kiosk-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Shared with taskmate-kiosk-card.js; tests/frontend/taskmate-lazy-editors.test.cjs keeps the copies equal.
const DEFAULT_HEADER = "#9b59b6";
const DEFAULT_TIMEOUT = 60;
const MIN_TIMEOUT = 15;
const MAX_TIMEOUT = 600;
const DEFAULT_AMBIENT_AFTER = 120;
const clampTimeout = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return DEFAULT_TIMEOUT;
  return Math.min(MAX_TIMEOUT, Math.max(MIN_TIMEOUT, Math.round(n)));
};

class TaskMateKioskCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object }, _pins: { type: Object } };
  }

  setConfig(config) { this.config = { ...config }; }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  updated(changedProps) {
    super.updated?.(changedProps);
    if (changedProps.has("hass") && this.hass && !this._pinsRequested) {
      this._pinsRequested = true;
      this.hass.callWS({ type: "taskmate/kiosk/status" })
        .then(res => {
          const pins = {};
          for (const c of (res && res.children) || []) pins[String(c.id)] = !!c.has_pin;
          this._pins = pins;
        })
        .catch(() => { this._pins = {}; });
    }
  }

  _schema() {
    return [
      { name: "entity", selector: window.__taskmate_entity_selector?.(this) ?? { entity: { domain: "sensor" } } },
      { name: "title", selector: { text: {} } },
      {
        name: "card_design",
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: "global", label: this._t("common.design.use_global") }],
            mode: "dropdown",
          },
        },
      },
      { name: "timeout", selector: { number: { min: MIN_TIMEOUT, max: MAX_TIMEOUT, step: 5, mode: "box", unit_of_measurement: "s" } } },
      { name: "warn_before_return", selector: { boolean: {} } },
      { name: "show_points", selector: { boolean: {} } },
      { name: "show_streak", selector: { boolean: {} } },
      { name: "show_reward_progress", selector: { boolean: {} } },
      { name: "show_description", selector: { boolean: {} } },
      { name: "show_bounties", selector: { boolean: {} } },
      { name: "show_rewards", selector: { boolean: {} } },
      { name: "show_picker_progress", selector: { boolean: {} } },
      {
        name: "completed_mode",
        selector: { select: { mode: "dropdown", options: [
          { value: "show", label: this._t("kiosk.editor.completed_show") },
          { value: "hide", label: this._t("kiosk.editor.completed_hide") },
        ] } },
      },
      { name: "grabs_first", selector: { boolean: {} } },
      {
        name: "elapsed_time_mode",
        selector: { select: { mode: "dropdown", options: [
          { value: "show", label: this._t("kiosk.editor.missed_show") },
          { value: "dim", label: this._t("kiosk.editor.missed_dim") },
          { value: "hide", label: this._t("kiosk.editor.missed_hide") },
        ] } },
      },
      {
        name: "set_times_layout",
        selector: { select: { mode: "dropdown", options: [
          { value: "family", label: this._t("common.set_times.layout_family") },
          { value: "rows", label: this._t("common.set_times.layout_rows") },
          { value: "pills", label: this._t("common.set_times.layout_pills") },
        ] } },
      },
      { name: "play_sounds", selector: { boolean: {} } },
      { name: "show_confetti", selector: { boolean: {} } },
      { name: "show_completion_popup", selector: { boolean: {} } },
      { name: "seasonal", selector: { boolean: {} } },
      {
        name: "ambient_mode",
        selector: {
          select: {
            options: [
              { value: "off", label: this._t("kiosk.editor.ambient_off") },
              { value: "progress", label: this._t("kiosk.editor.ambient_progress") },
              { value: "photos", label: this._t("kiosk.editor.ambient_photos") },
            ],
            mode: "dropdown",
          },
        },
      },
      { name: "ambient_after", selector: { number: { min: 30, max: 1800, step: 30, mode: "box", unit_of_measurement: "s" } } },
      { name: "show_raffle_draws", selector: { boolean: {} } },
      { name: "show_boost_alert", selector: { boolean: {} } },
      { name: "show_pet", selector: { boolean: {} } },
      { name: "show_badges", selector: { boolean: {} } },
      { name: "allow_avatar_change", selector: { boolean: {} } },
      { name: "show_tour", selector: { boolean: {} } },
    ];
  }

  /**
   * The editor's collapsible sections (fields picked from _schema() by name),
   * grouped like the child card editor. Appearance starts open.
   */
  _sections() {
    const byName = Object.fromEntries(this._schema().map((f) => [f.name, f]));
    const pick = (...names) => names.map((n) => byName[n]);
    return {
      top: pick("entity", "title"),
      appearance: pick("card_design"),
      appearanceMore: pick("seasonal", "show_description", "set_times_layout"),
      which: pick("completed_mode", "elapsed_time_mode", "grabs_first"),
      kid: pick("show_points", "show_streak", "show_reward_progress", "show_picker_progress", "show_bounties",
        "show_rewards", "play_sounds", "show_confetti", "show_completion_popup", "show_raffle_draws",
        "show_boost_alert", "show_pet", "show_badges", "allow_avatar_change", "show_tour"),
      advanced: pick("timeout", "warn_before_return", "ambient_mode", "ambient_after"),
    };
  }

  _onOff(on, name) {
    return this._t(on ? "common.editor.summary_on" : "common.editor.summary_off", { name });
  }

  _modeWord(value) {
    return ["hide", "dim", "show"].includes(value) ? this._t(`common.editor.summary_value_${value}`) : value;
  }

  /** One-line summaries shown under each section title, from the form data. */
  _summaries(data, sections) {
    const join = (parts) => parts.filter(Boolean).join(" · ");
    const label = (field, value) => field?.selector?.select?.options?.find((o) => o.value === value)?.label || value;
    const which = [
      this._t("kiosk.editor.summary_done", { value: this._modeWord(data.completed_mode) }),
      this._t("common.editor.summary_missed", { value: this._modeWord(data.elapsed_time_mode) }),
    ];
    return {
      appearance: join([
        data.card_design === "global" ? this._t("common.editor.summary_global_design") : label(sections.appearance[0], data.card_design),
        this._t(this.config.header_color ? "common.editor.summary_header_custom" : "common.editor.summary_header_default"),
        this._onOff(data.seasonal, this._t("common.editor.summary_seasonal")),
      ]),
      which: join([...which, this._t("common.editor.summary_more", { count: sections.which.length - which.length })]),
      kid: this._t("common.editor.summary_count_on", { on: sections.kid.filter((f) => data[f.name]).length, total: sections.kid.length }),
      advanced: join([
        this._t("kiosk.editor.summary_timeout", { seconds: clampTimeout(data.timeout) }),
        label(sections.advanced[2], data.ambient_mode),
      ]),
    };
  }

  _computeLabel = (entry) => ({
    entity: this._t("kiosk.editor.entity"),
    title: this._t("kiosk.editor.title"),
    card_design: this._t("common.design.field_label"),
    timeout: this._t("kiosk.editor.timeout"),
    warn_before_return: this._t("kiosk.editor.warn_before_return"),
    show_points: this._t("kiosk.editor.show_points"),
    show_streak: this._t("kiosk.editor.show_streak"),
    show_reward_progress: this._t("kiosk.editor.show_reward_progress"),
    show_description: this._t("kiosk.editor.show_description"),
    show_bounties: this._t("kiosk.editor.show_bounties"),
    show_rewards: this._t("kiosk.editor.show_rewards"),
    show_picker_progress: this._t("kiosk.editor.show_picker_progress"),
    completed_mode: this._t("kiosk.editor.completed_mode"),
    grabs_first: this._t("kiosk.editor.grabs_first"),
    elapsed_time_mode: this._t("kiosk.editor.missed_mode"),
    set_times_layout: this._t("common.set_times.layout_label"),
    play_sounds: this._t("kiosk.editor.play_sounds"),
    show_confetti: this._t("kiosk.editor.show_confetti"),
    show_completion_popup: this._t("kiosk.editor.show_completion_popup"),
    seasonal: this._t("child.editor.seasonal"),
    ambient_mode: this._t("kiosk.editor.ambient_mode"),
    ambient_after: this._t("kiosk.editor.ambient_after"),
    show_raffle_draws: this._t("kiosk.editor.show_raffle_draws"),
    show_boost_alert: this._t("kiosk.editor.show_boost_alert"),
    show_pet: this._t("kiosk.editor.show_pet"),
    show_badges: this._t("kiosk.editor.show_badges"),
    allow_avatar_change: this._t("kiosk.editor.allow_avatar_change"),
    show_tour: this._t("child.editor.show_tour"),
  })[entry.name] ?? entry.name;

  _computeHelper = (entry) => ({
    title: this._t("kiosk.editor.title_helper"),
    timeout: this._t("kiosk.editor.timeout_helper"),
    warn_before_return: this._t("kiosk.editor.warn_before_return_helper"),
    show_description: this._t("kiosk.editor.show_description_helper"),
    show_bounties: this._t("kiosk.editor.show_bounties_helper"),
    show_rewards: this._t("kiosk.editor.show_rewards_helper"),
    show_picker_progress: this._t("kiosk.editor.show_picker_progress_helper"),
    completed_mode: this._t("kiosk.editor.completed_mode_helper"),
    grabs_first: this._t("kiosk.editor.grabs_first_helper"),
    elapsed_time_mode: this._t("kiosk.editor.missed_mode_helper"),
    set_times_layout: this._t("common.set_times.layout_helper"),
    play_sounds: this._t("kiosk.editor.play_sounds_helper"),
    show_completion_popup: this._t("kiosk.editor.show_completion_popup_helper"),
    seasonal: this._t("child.editor.seasonal_helper"),
    show_tour: this._t("child.editor.show_tour_helper"),
  })[entry.name] ?? "";

  /** Every child, configured ones first in their order, each with shown/require_pin. */
  _childRows() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity || "sensor.taskmate_overview")) || {};
    const all = attrs.children || [];
    const configured = Array.isArray(this.config.children) ? this.config.children : null;
    if (!configured) return all.map(c => ({ child: c, shown: !c.is_guest && (!c.is_adult || this.config.show_adults === true), requirePin: true }));
    const rows = [];
    for (const entry of configured) {
      const child = all.find(c => String(c.id) === String(entry && (entry.child_id ?? entry)));
      if (child && !rows.some(r => r.child.id === child.id)) rows.push({ child, shown: true, requirePin: entry?.require_pin !== false });
    }
    for (const child of all) {
      if (!rows.some(r => r.child.id === child.id)) rows.push({ child, shown: false, requirePin: true });
    }
    return rows;
  }

  _writeChildren(rows) {
    this._dispatch({
      ...this.config,
      children: rows.filter(r => r.shown).map(r => ({ child_id: r.child.id, require_pin: r.requirePin })),
    });
  }

  _toggleShown(index) {
    const rows = this._childRows();
    rows[index] = { ...rows[index], shown: !rows[index].shown };
    this._writeChildren(rows);
  }

  _togglePin(index) {
    const rows = this._childRows();
    rows[index] = { ...rows[index], requirePin: !rows[index].requirePin };
    this._writeChildren(rows);
  }

  _move(index, delta) {
    const rows = this._childRows();
    const target = index + delta;
    if (target < 0 || target >= rows.length) return;
    [rows[index], rows[target]] = [rows[target], rows[index]];
    this._writeChildren(rows);
  }

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "sensor.taskmate_overview",
      title: this.config.title || "",
      card_design: this.config.card_design || "global",
      timeout: this.config.timeout ?? DEFAULT_TIMEOUT,
      warn_before_return: this.config.warn_before_return !== false,
      show_points: this.config.show_points !== false,
      show_streak: this.config.show_streak !== false,
      show_reward_progress: this.config.show_reward_progress !== false,
      show_description: this.config.show_description === true,
      show_bounties: this.config.show_bounties === true,
      show_rewards: this.config.show_rewards === true,
      show_picker_progress: this.config.show_picker_progress !== false,
      completed_mode: this.config.completed_mode || "show",
      grabs_first: this.config.grabs_first === true,
      elapsed_time_mode: this.config.elapsed_time_mode || "show",
      set_times_layout: this.config.set_times_layout || "family",
      play_sounds: this.config.play_sounds !== false,
      show_confetti: this.config.show_confetti !== false,
      show_completion_popup: this.config.show_completion_popup !== false,
      seasonal: this.config.seasonal !== false,
      ambient_mode: this.config.ambient_mode || "off",
      ambient_after: this.config.ambient_after ?? DEFAULT_AMBIENT_AFTER,
      show_raffle_draws: this.config.show_raffle_draws !== false,
      show_boost_alert: this.config.show_boost_alert !== false,
      show_pet: this.config.show_pet !== false,
      show_badges: this.config.show_badges !== false,
      allow_avatar_change: this.config.allow_avatar_change !== false,
      show_tour: this.config.show_tour !== false,
    };
    const rows = this._childRows();
    const pins = this._pins || {};
    const sections = this._sections();
    const summary = this._summaries(data, sections);
    const form = (schema) => html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${schema}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}
      ></ha-form>`;
    const section = (title, secondary, icon, body, expanded = false) => html`
      <ha-expansion-panel outlined .header=${title} .secondary=${secondary} .expanded=${expanded}>
        <ha-icon slot="leading-icon" .icon=${icon}></ha-icon>
        <div class="section-body">${body}</div>
      </ha-expansion-panel>`;
    return html`
      ${form(sections.top)}
      ${section(this._t("common.editor.section_appearance"), summary.appearance, "mdi:palette-outline", html`
        ${form(sections.appearance)}
        ${this._renderColourPicker()}
        ${form(sections.appearanceMore)}`, true)}
      ${section(this._t("common.editor.section_which_chores"), summary.which, "mdi:filter-variant", form(sections.which))}
      ${section(this._t("common.editor.section_kid_features"), summary.kid, "mdi:human-child", form(sections.kid))}
      ${section(this._t("common.editor.section_advanced"), summary.advanced, "mdi:cog-outline", form(sections.advanced))}
      <div class="kiosk-children">
        <div class="kiosk-heading">${this._t("kiosk.editor.children_heading")}</div>
        <div class="kiosk-hint">${this._t("kiosk.editor.children_hint")}</div>
        ${rows.map((row, i) => {
          const hasPin = !!pins[String(row.child.id)];
          return html`
            <div class="kiosk-child ${row.shown ? "" : "hidden"}">
              <input type="checkbox" .checked=${row.shown}
                     aria-label="${this._t("kiosk.editor.show_child", { name: row.child.name })}"
                     @change=${() => this._toggleShown(i)}>
              <div class="kiosk-child-name">
                <b>${row.child.name}</b>
                <small>${hasPin ? html`<span class="mask">••••</span> ${this._t("kiosk.editor.pin_set")}` : this._t("kiosk.editor.no_pin")}</small>
              </div>
              <label class="kiosk-pin-toggle">
                <span>${this._t("kiosk.editor.require_pin")}</span>
                <ha-switch .checked=${row.requirePin && hasPin} ?disabled=${!row.shown || !hasPin}
                           @change=${() => this._togglePin(i)}></ha-switch>
              </label>
              <button class="kiosk-move" title="${this._t("kiosk.editor.move_up")}" aria-label="${this._t("kiosk.editor.move_up")}"
                      ?disabled=${i === 0} @click=${() => this._move(i, -1)}><ha-icon icon="mdi:chevron-up"></ha-icon></button>
              <button class="kiosk-move" title="${this._t("kiosk.editor.move_down")}" aria-label="${this._t("kiosk.editor.move_down")}"
                      ?disabled=${i === rows.length - 1} @click=${() => this._move(i, 1)}><ha-icon icon="mdi:chevron-down"></ha-icon></button>
            </div>`;
        })}
        <div class="kiosk-hint">${this._t("kiosk.editor.pin_note")}</div>
      </div>
    `;
  }

  _renderColourPicker() {
    const d = window.__taskmate_design;
    if (!d || !d.colourPicker) return html``;
    const current = this.config.header_color || DEFAULT_HEADER;
    return d.colourPicker({
      defaultValue: DEFAULT_HEADER, current,
      label: this._t("common.editor.header_colour"),
      helper: this._t("common.editor.header_colour_helper"),
      resetLabel: this._t("common.reset"),
      onInput: (v) => this._set("header_color", v),
      onPreset: (v) => this._set("header_color", v),
      onReset: () => this._set("header_color", undefined),
    });
  }

  _formChanged(e) {
    const values = e.detail.value || {};
    const next = { ...this.config };
    for (const [key, value] of Object.entries(values)) {
      if (value === "" || value === null || value === undefined) delete next[key];
      else if (key === "card_design" && value === "global") delete next[key];
      else if (key === "ambient_mode" && value === "off") delete next[key];
      else if (key === "ambient_after" && Number(value) === DEFAULT_AMBIENT_AFTER) delete next[key];
      // Both list filters default to "show": store only a change from it.
      else if ((key === "completed_mode" || key === "elapsed_time_mode") && value === "show") delete next[key];
      else if (key === "set_times_layout" && value === "family") delete next[key];
      else if (key === "timeout") {
        if (clampTimeout(value) === DEFAULT_TIMEOUT) delete next[key];
        else next[key] = clampTimeout(value);
      } else if (key === "show_bounties" || key === "show_rewards" || key === "show_description") {
        // The toggles that default to off: store only the "on" choice.
        if (value) next[key] = true;
        else delete next[key];
      } else if (typeof value === "boolean" && key !== "entity") {
        // Every toggle defaults to on: store only the "off" choice.
        if (value) delete next[key];
        else next[key] = false;
      } else next[key] = value;
    }
    this._dispatch(next);
  }

  _set(key, value) {
    const next = { ...this.config, [key]: value };
    if (value === undefined || value === "" || value === null) delete next[key];
    this._dispatch(next);
  }

  _dispatch(config) {
    this.config = config;
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-form { display: block; margin-bottom: 16px; }
      ha-expansion-panel { display: block; margin-bottom: 12px; }
      ha-expansion-panel ha-form { margin-bottom: 0; }
      .section-body { display: flex; flex-direction: column; gap: 16px; padding: 12px 0 8px; }
      .kiosk-children { margin-top: 16px; display: flex; flex-direction: column; gap: 6px; }
      .kiosk-heading { font-weight: 600; color: var(--primary-color); }
      .kiosk-hint { font-size: 12px; color: var(--secondary-text-color); }
      .kiosk-child {
        display: grid; grid-template-columns: 28px 1fr auto 36px 36px; gap: 8px; align-items: center;
        padding: 6px 0; border-top: 1px solid var(--divider-color);
      }
      .kiosk-child.hidden .kiosk-child-name { opacity: 0.5; }
      .kiosk-child input { width: 18px; height: 18px; accent-color: var(--primary-color); }
      .kiosk-child-name { display: flex; flex-direction: column; min-width: 0; }
      .kiosk-child-name small { color: var(--secondary-text-color); font-size: 12px; }
      .kiosk-child-name .mask { letter-spacing: 3px; }
      .kiosk-pin-toggle { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--secondary-text-color); }
      .kiosk-move {
        width: 36px; height: 36px; border-radius: 50%; border: 0; background: transparent;
        color: var(--primary-text-color); cursor: pointer; display: grid; place-items: center;
      }
      .kiosk-move:disabled { opacity: 0.3; cursor: default; }
    `;
  }
}

if (!customElements.get("taskmate-kiosk-card-editor")) {
  customElements.define("taskmate-kiosk-card-editor", TaskMateKioskCardEditor);
}
