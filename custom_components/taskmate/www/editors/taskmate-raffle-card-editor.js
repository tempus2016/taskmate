/**
 * TaskMate raffle card editor (visual card editor).
 *
 * Loaded on demand by taskmate-raffle-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Shared with taskmate-raffle-card.js; tests/frontend/taskmate-lazy-editors.test.cjs keeps the copies equal.
const DEFAULT_ACCENT = "#8e44ad";

class TaskMateRaffleCardEditor extends LitElement {
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
    const children = attrs.children || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      {
        name: "child_id",
        selector: {
          select: {
            options: [{ value: "", label: this._t("raffle.editor.family_view") }, ...children.map(c => ({ value: c.id, label: c.name }))],
            mode: "dropdown",
          },
        },
      },
      { name: "title", selector: { text: {} } },
      { name: "show_reveal", selector: { boolean: {} } },
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
    ];
  }

  _computeLabel = (entry) => ({
    entity: this._t("common.editor.overview_entity"),
    child_id: this._t("raffle.editor.child"),
    title: this._t("common.editor.card_title"),
    show_reveal: this._t("raffle.editor.show_reveal"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  _computeHelper = (entry) => ({
    entity: this._t("common.editor.overview_entity_helper"),
    child_id: this._t("raffle.editor.child_helper"),
  }[entry.name] ?? "");

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
      show_reveal: this.config.show_reveal !== false,
      card_design: this.config.card_design || "global",
    };
    return html`
      <ha-form .hass=${this.hass} .data=${data} .schema=${this._buildSchema()}
        .computeLabel=${this._computeLabel} .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}></ha-form>
      ${this._renderColourPicker("header_color", DEFAULT_ACCENT)}`;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current: this.config[key] || defaultValue,
      label: this._t("common.editor.header_colour"),
      helper: this._t("common.editor.header_colour_helper"),
      resetLabel: this._t("common.reset"),
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === "" || value === null || value === undefined || (key === "card_design" && value === "global")
        || (key === "show_reveal" && value === true)) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this._fire(newConfig);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this._fire(newConfig);
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-form { display: block; margin-bottom: 16px; }
    `;
  }
}

if (!customElements.get("taskmate-raffle-card-editor")) {
  customElements.define("taskmate-raffle-card-editor", TaskMateRaffleCardEditor);
}
