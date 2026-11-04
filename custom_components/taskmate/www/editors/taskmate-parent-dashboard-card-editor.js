/**
 * TaskMate parent dashboard card editor (visual card editor).
 *
 * Loaded on demand by taskmate-parent-dashboard-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateParentDashboardCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
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

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _buildSchema() {
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'card_design',
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: 'global', label: 'Use global default' }],
            mode: 'dropdown',
          },
        },
      },
      { name: 'quick_points_amount', selector: { number: { min: 1, max: 100, mode: 'box' } } },
      { name: 'show_claims', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      show_adults: this._t('common.editor.show_adults'),
      entity: this._t('dashboard.editor.entity_label'),
      title: this._t('dashboard.editor.title_label'),
      card_design: this._t('common.design.field_label'),
      quick_points_amount: this._t('dashboard.editor.quick_points_label'),
      show_claims: this._t('dashboard.editor.show_claims'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      show_adults: this._t('common.editor.show_adults_helper'),
      entity: this._t('dashboard.editor.entity_helper'),
      quick_points_amount: this._t('dashboard.editor.quick_points_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      card_design: this.config.card_design || 'global',
      quick_points_amount: this.config.quick_points_amount || 5,
      show_claims: this.config.show_claims !== false,
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
      ${this._renderColourPicker('header_color', '#c0392b')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    const current = this.config[key] || defaultValue;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current,
      label: this._t('common.editor.header_colour'),
      helper: this._t('common.editor.header_colour_helper'),
      resetLabel: this._t('common.reset'),
      onInput: (v) => this._update(key, v),
      onPreset: (v) => this._update(key, v),
      onReset: () => this._update(key, defaultValue),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === '' || value === null || value === undefined) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (key === 'show_claims' && value === true) {
        delete newConfig[key];
      } else if (key === 'quick_points_amount' && value === 5) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _update(key, value) {
    const cfg = { ...this.config, [key]: value };
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: cfg }, bubbles: true, composed: true }));
  }
}

if (!customElements.get("taskmate-parent-dashboard-card-editor")) {
  customElements.define("taskmate-parent-dashboard-card-editor", TaskMateParentDashboardCardEditor);
}
