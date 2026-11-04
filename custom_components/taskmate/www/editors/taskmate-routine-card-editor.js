/**
 * TaskMate routine card editor (visual card editor).
 *
 * Loaded on demand by taskmate-routine-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Shared with taskmate-routine-card.js; tests/frontend/taskmate-lazy-editors.test.cjs keeps the copies equal.
const TIME_CATEGORIES = ["all", "morning", "afternoon", "evening", "night", "anytime"];
const DEFAULT_ACCENT = "#7c3aed";

class TaskMateRoutineCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-form { display: block; margin-bottom: 16px; }
    `;
  }

  setConfig(config) { this.config = config; }

  _buildSchema() {
    const entity = this.config && this.config.entity ? this.hass && this.hass.states && this.hass.states[this.config.entity] : null;
    const attrs = window.__taskmate_attrs && this.config && this.config.entity
      ? window.__taskmate_attrs(this.hass, this.config.entity)
      : (entity && entity.attributes) || {};
    const children = Array.isArray(attrs.children) ? attrs.children : [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      {
        name: "child_id",
        selector: {
          select: { options: children.map((c) => ({ value: c.id, label: c.name })), mode: "dropdown" },
        },
      },
      {
        name: "time_category",
        selector: {
          select: {
            options: TIME_CATEGORIES.map((value) => ({ value, label: this._t(`routine.editor.time_${value}`) })),
            mode: "dropdown",
          },
        },
      },
      { name: "title", selector: { text: {} } },
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

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t("common.editor.overview_entity"),
      child_id: this._t("routine.editor.child"),
      time_category: this._t("routine.editor.time_category"),
      title: this._t("common.editor.card_title"),
      card_design: this._t("common.design.field_label"),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t("common.editor.overview_entity_helper"),
      child_id: this._t("routine.editor.child_helper"),
      time_category: this._t("routine.editor.time_category_helper"),
      title: this._t("routine.editor.title_helper"),
    };
    return helpers[entry.name] ?? "";
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      time_category: this.config.time_category || "all",
      title: this.config.title || "",
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
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue,
      current: this.config[key] || defaultValue,
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
      // "all" and "global" are the card's defaults, not values to store.
      if (
        value === "" || value === null || value === undefined
        || (key === "card_design" && value === "global")
        || (key === "time_category" && value === "all")
      ) {
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
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }
}

if (!customElements.get("taskmate-routine-card-editor")) {
  customElements.define("taskmate-routine-card-editor", TaskMateRoutineCardEditor);
}
