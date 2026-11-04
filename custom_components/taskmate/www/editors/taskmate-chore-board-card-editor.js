/**
 * TaskMate chore board card editor (visual card editor).
 *
 * Loaded on demand by taskmate-chore-board-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Shared with taskmate-chore-board-card.js; tests/frontend/taskmate-lazy-editors.test.cjs keeps the copies equal.
const DEFAULT_ACCENT = "#3f51b5";

class TaskMateChoreBoardCardEditor extends LitElement {
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
      { name: "title", selector: { text: {} } },
      {
        name: "children",
        selector: { select: { multiple: true, mode: "list", options: children.map(c => ({ value: c.id, label: c.name })) } },
      },
      {
        name: "default_view",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "today", label: this._t("chore_board.today") },
              { value: "week", label: this._t("chore_board.this_week") },
            ],
          },
        },
      },
      { name: "show_week", selector: { boolean: {} } },
      { name: "tap_to_complete", selector: { boolean: {} } },
      { name: "show_legend", selector: { boolean: {} } },
      { name: "hide_done_periods", selector: { boolean: {} } },
      { name: "show_parent_actions", selector: { boolean: {} } },
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
    title: this._t("common.editor.card_title"),
    children: this._t("chore_board.editor.children"),
    default_view: this._t("chore_board.editor.default_view"),
    show_week: this._t("chore_board.editor.show_week"),
    tap_to_complete: this._t("chore_board.editor.tap_to_complete"),
    show_legend: this._t("chore_board.editor.show_legend"),
    hide_done_periods: this._t("chore_board.editor.hide_done_periods"),
    show_parent_actions: this._t("common.editor.show_parent_actions"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  _computeHelper = (entry) => ({
    entity: this._t("common.editor.overview_entity_helper"),
    children: this._t("chore_board.editor.children_helper"),
    tap_to_complete: this._t("chore_board.editor.tap_to_complete_helper"),
    hide_done_periods: this._t("chore_board.editor.hide_done_periods_helper"),
    show_parent_actions: this._t("common.editor.show_parent_actions_helper"),
  }[entry.name] ?? "");

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      title: this.config.title || "",
      children: Array.isArray(this.config.children) ? this.config.children : [],
      default_view: this.config.default_view || "today",
      show_week: this.config.show_week !== false,
      tap_to_complete: this.config.tap_to_complete !== false,
      show_legend: this.config.show_legend !== false,
      hide_done_periods: this.config.hide_done_periods === true,
      show_parent_actions: this.config.show_parent_actions !== false,
      card_design: this.config.card_design || "global",
    };
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._buildSchema()}
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
    if (key === "default_view") return value === "today";
    if (key === "children") return Array.isArray(value) && value.length === 0;
    if (["show_week", "tap_to_complete", "show_legend", "show_parent_actions"].includes(key)) return value === true;
    if (key === "hide_done_periods") return value === false;
    return false;
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (TaskMateChoreBoardCardEditor._isDefault(key, value)) delete newConfig[key];
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
    `;
  }
}

if (!customElements.get("taskmate-chore-board-card-editor")) {
  customElements.define("taskmate-chore-board-card-editor", TaskMateChoreBoardCardEditor);
}
