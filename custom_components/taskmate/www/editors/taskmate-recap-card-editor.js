/**
 * TaskMate recap card editor (visual card editor).
 *
 * Loaded on demand by taskmate-recap-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const RECAP_FREQUENCIES = ["weekly", "monthly", "every_3_months", "every_6_months", "every_9_months", "yearly"];

// Card Editor
class TaskMateRecapCardEditor extends LitElement {
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

  setConfig(config) { this.config = config; }

  _buildSchema() {
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const children = entity?.attributes?.children || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      {
        name: "child_id",
        selector: {
          select: {
            options: children.map((c) => ({ value: c.id, label: c.name })),
            mode: "dropdown",
          },
        },
      },
      { name: "title", selector: { text: {} } },
      {
        name: "default_frequency",
        selector: {
          select: {
            options: [
              { value: "__newest__", label: this._t("recap.editor.newest") },
              ...RECAP_FREQUENCIES.map((f) => ({ value: f, label: this._t(`recap.freq.${f}`) })),
            ],
            mode: "dropdown",
          },
        },
      },
      { name: "autoplay", selector: { boolean: {} } },
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
      child_id: this._t("recap.editor.child"),
      title: this._t("common.editor.card_title"),
      default_frequency: this._t("recap.editor.default_frequency"),
      autoplay: this._t("recap.editor.autoplay"),
      card_design: this._t("common.design.field_label"),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t("common.editor.overview_entity_helper"),
      child_id: this._t("recap.editor.child_helper"),
      default_frequency: this._t("recap.editor.default_frequency_helper"),
      autoplay: this._t("recap.editor.autoplay_helper"),
    };
    return helpers[entry.name] ?? "";
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
      default_frequency: this.config.default_frequency || "__newest__",
      autoplay: this.config.autoplay === true,
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
      ${this._renderColourPicker("header_color", "#9b59b6")}
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

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (
        value === "" || value === null || value === undefined
        || (key === "default_frequency" && value === "__newest__")
        || (key === "card_design" && value === "global")
        || (key === "autoplay" && value === false)
      ) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

if (!customElements.get("taskmate-recap-card-editor")) {
  customElements.define("taskmate-recap-card-editor", TaskMateRecapCardEditor);
}
