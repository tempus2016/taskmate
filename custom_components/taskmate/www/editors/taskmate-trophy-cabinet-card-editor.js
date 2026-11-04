/**
 * TaskMate trophy cabinet card editor (visual card editor).
 *
 * Loaded on demand by taskmate-trophy-cabinet-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Shared with taskmate-trophy-cabinet-card.js; tests/frontend/taskmate-lazy-editors.test.cjs keeps the copies equal.
const DEFAULT_ACCENT = "#8d6e63";
const SHELVES = ["seasons", "bests", "badges", "quests", "perfect_weeks", "pets"];
const DEFAULT_SHELVES = ["seasons", "bests", "badges", "quests", "perfect_weeks"];
const DEFAULT_PER_SHELF = 5;
const DEFAULT_NEW_DAYS = 7;

class TaskMateTrophyCabinetCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  setConfig(config) { this.config = config; }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _buildSchema() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const children = (attrs.children || []).filter((c) => !c.is_adult);
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      { name: "title", selector: { text: {} } },
      {
        name: "shelves",
        selector: {
          select: {
            multiple: true, mode: "list",
            options: SHELVES.map((s) => ({ value: s, label: this._t(`trophy.shelf_${s}`) })),
          },
        },
      },
      {
        name: "children",
        selector: { select: { multiple: true, mode: "list", options: children.map((c) => ({ value: c.id, label: c.name })) } },
      },
      { name: "badges_per_shelf", selector: { number: { min: 1, max: 30, mode: "box" } } },
      { name: "new_days", selector: { number: { min: 0, max: 60, mode: "box" } } },
      { name: "show_spotlight", selector: { boolean: {} } },
      {
        name: "card_design",
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: "global", label: "Use global default" }],
            mode: "dropdown",
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => ({
    entity: this._t("common.editor.overview_entity"),
    title: this._t("trophy.editor.title"),
    shelves: this._t("trophy.editor.shelves"),
    children: this._t("trophy.editor.children"),
    badges_per_shelf: this._t("trophy.editor.per_shelf"),
    new_days: this._t("trophy.editor.new_days"),
    show_spotlight: this._t("trophy.editor.show_spotlight"),
    show_adults: this._t("common.editor.show_adults"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  _computeHelper = (entry) => ({
    entity: this._t("common.editor.overview_entity_helper"),
    shelves: this._t("trophy.editor.shelves_helper"),
    children: this._t("trophy.editor.children_helper"),
    badges_per_shelf: this._t("trophy.editor.per_shelf_helper"),
    new_days: this._t("trophy.editor.new_days_helper"),
    show_adults: this._t("common.editor.show_adults_helper"),
  }[entry.name] ?? "");

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      title: this.config.title || "",
      shelves: Array.isArray(this.config.shelves) ? this.config.shelves : DEFAULT_SHELVES,
      children: Array.isArray(this.config.children) ? this.config.children : [],
      badges_per_shelf: this.config.badges_per_shelf ?? DEFAULT_PER_SHELF,
      new_days: this.config.new_days ?? DEFAULT_NEW_DAYS,
      show_spotlight: this.config.show_spotlight !== false,
      card_design: this.config.card_design || "global",
    };
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${this.config.show_adults === true ? { ...data, show_adults: true } : data}
        .schema=${this._buildSchema().concat(window.__taskmate_adults_field ? window.__taskmate_adults_field(this.hass, this.config) : [])}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}
      ></ha-form>
      ${this._renderColourPicker("header_color", DEFAULT_ACCENT)}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    const current = this.config[key] || defaultValue;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current,
      label: this._t("common.editor.header_colour"),
      helper: this._t("common.editor.header_colour_helper"),
      resetLabel: this._t("common.reset"),
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
    });
  }

  // Defaults are the absence of a key, so a saved card only carries what was
  // changed from them.
  static _isDefault(key, value) {
    if (value === "" || value === null || value === undefined) return true;
    if (key === "card_design") return value === "global";
    if (key === "children") return Array.isArray(value) && value.length === 0;
    if (key === "shelves") {
      return Array.isArray(value) && value.length === DEFAULT_SHELVES.length
        && DEFAULT_SHELVES.every((s, i) => value[i] === s);
    }
    if (key === "badges_per_shelf") return Number(value) === DEFAULT_PER_SHELF;
    if (key === "new_days") return Number(value) === DEFAULT_NEW_DAYS;
    if (key === "show_spotlight") return value === true;
    if (key === "show_adults") return value === false;
    return false;
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (TaskMateTrophyCabinetCardEditor._isDefault(key, value)) delete newConfig[key];
      else newConfig[key] = value;
    }
    this._fire(newConfig);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this._fire(newConfig);
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-form { display: block; margin-bottom: 16px; }
      .colour-field { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; border: 1px solid var(--outline-color, var(--divider-color, #e0e0e0)); border-radius: 4px; background: var(--mdc-text-field-fill-color, var(--card-background-color)); }
      .colour-field-label { font-size: 0.82rem; color: var(--primary-color); font-weight: 500; }
      .colour-field-body { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
      .colour-swatch-wrapper { position: relative; width: 36px; height: 36px; border-radius: 50%; overflow: hidden; cursor: pointer; border: 2px solid var(--divider-color, #e0e0e0); flex-shrink: 0; }
      .colour-swatch-wrapper input[type="color"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; border: 0; padding: 0; }
      .colour-swatch-preview { position: absolute; inset: 0; pointer-events: none; }
      .colour-hex { font-family: var(--code-font-family, monospace); font-size: 0.85rem; color: var(--secondary-text-color); min-width: 70px; }
      .colour-presets { display: flex; gap: 6px; flex-wrap: wrap; }
      .preset-swatch { width: 22px; height: 22px; border-radius: 50%; cursor: pointer; border: 2px solid var(--divider-color, #e0e0e0); transition: transform 0.1s; padding: 0; }
      .preset-swatch:hover { transform: scale(1.15); }
      .preset-swatch.active { border-color: var(--primary-text-color); box-shadow: 0 0 0 2px var(--primary-color); }
      .colour-reset { font-size: 0.78rem; color: var(--secondary-text-color); background: none; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; padding: 4px 10px; cursor: pointer; margin-inline-start: auto; }
      .colour-helper { color: var(--secondary-text-color); font-size: 0.82rem; line-height: 1.3; }
    `;
  }
}

if (!customElements.get("taskmate-trophy-cabinet-card-editor")) {
  customElements.define("taskmate-trophy-cabinet-card-editor", TaskMateTrophyCabinetCardEditor);
}
