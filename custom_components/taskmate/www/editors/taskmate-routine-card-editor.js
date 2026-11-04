/**
 * TaskMate routine card editor (visual card editor).
 *
 * Moved out of taskmate-routine-card.js with the other editors. The card has
 * never had a getConfigElement(), so Home Assistant does not open this editor
 * yet (the Routine card is configured in YAML); wiring it up needs its English
 * labels translated and its mwc-list-item options replaced first.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Shared with taskmate-routine-card.js; tests/frontend/taskmate-lazy-editors.test.cjs keeps the copies equal.
const TIME_CATEGORIES = ["all", "morning", "afternoon", "evening", "night", "anytime"];

class TaskMateRoutineCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, _config: { type: Object } };
  }

  setConfig(config) { this._config = { ...config }; }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  render() {
    if (!this._config) return html``;
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this._config.entity)) || {};
    const children = attrs.children || [];
    return html`
      <div class="form">
        <ha-textfield
          label="Entity"
          .value=${this._config.entity || "sensor.taskmate_overview"}
          @input=${e => this._set("entity", e.target.value)}
        ></ha-textfield>

        <ha-select
          label="Child"
          .value=${this._config.child_id || ""}
          @selected=${e => this._set("child_id", e.target.value)}
          @closed=${e => e.stopPropagation()}
        >
          ${children.map(c => html`<mwc-list-item .value=${c.id}>${c.name}</mwc-list-item>`)}
        </ha-select>

        <ha-select
          label="Time of day"
          .value=${this._config.time_category || "all"}
          @selected=${e => this._set("time_category", e.target.value)}
          @closed=${e => e.stopPropagation()}
        >
          ${TIME_CATEGORIES.map(t => html`<mwc-list-item .value=${t}>${t}</mwc-list-item>`)}
        </ha-select>

        <ha-textfield
          label="Title (optional)"
          .value=${this._config.title || ""}
          @input=${e => this._set("title", e.target.value)}
        ></ha-textfield>

        <ha-select
          .label=${this._t("common.design.field_label")}
          .value=${this._config.card_design || "global"}
          @selected=${e => this._set("card_design", e.target.value)}
          @closed=${e => e.stopPropagation()}
        >
          ${(window.__taskmate_design
            ? window.__taskmate_design.editorOptions(this._t.bind(this))
            : [{ value: "global", label: "Use global default" }]
          ).map(o => html`<mwc-list-item .value=${o.value}>${o.label}</mwc-list-item>`)}
        </ha-select>
      </div>
    `;
  }

  _set(key, value) {
    const newConfig = { ...this._config, [key]: value };
    // "global" is the absence of a per-card override, not a value to store.
    if (key === "card_design" && value === "global") delete newConfig[key];
    else if (value === null || value === "" || value === undefined) delete newConfig[key];
    this._config = newConfig;
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  static get styles() {
    return css`
      .form { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
    `;
  }
}

if (!customElements.get("taskmate-routine-card-editor")) {
  customElements.define("taskmate-routine-card-editor", TaskMateRoutineCardEditor);
}
