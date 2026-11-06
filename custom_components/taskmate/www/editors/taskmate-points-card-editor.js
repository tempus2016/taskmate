/**
 * TaskMate points card editor (visual card editor).
 *
 * Loaded on demand by taskmate-points-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Card Editor
class TaskMatePointsCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  static get styles() {
    return css`
      :host { display: block; padding: 4px 0; }
      ha-form { display: block; margin-bottom: 16px; }
      .amounts-preview { display: flex; flex-wrap: wrap; gap: 5px; margin: 4px 0 16px; }
      .preview-btn { padding: 3px 9px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; border: none; }
      .preview-btn.add { background: var(--success-color, #4caf50); color: var(--text-primary-color, #fff); }
      .preview-btn.remove { background: var(--error-color, #db4437); color: var(--text-primary-color, #fff); }
    `;
  }

  setConfig(config) { this.config = config; }

  _parseAmounts(str, defaults) {
    if (!str) return defaults;
    return str.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n > 0);
  }

  _amountsToString(arr) {
    return Array.isArray(arr) ? arr.join(', ') : '';
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
              : [{ value: 'global', label: this._t('common.design.use_global') }],
            mode: 'dropdown',
          },
        },
      },
      { name: 'quick_add_amounts', selector: { text: {} } },
      { name: 'quick_remove_amounts', selector: { text: {} } },
      { name: 'show_dialog', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      show_adults: this._t('common.editor.show_adults'),
      entity: this._t('points_card.editor.entity_label'),
      title: this._t('points_card.editor.title_label'),
      card_design: this._t('common.design.field_label'),
      quick_add_amounts: this._t('points_card.editor.add_buttons_label'),
      quick_remove_amounts: this._t('points_card.editor.remove_buttons_label'),
      show_dialog: this._t('points_card.editor.show_dialog_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      show_adults: this._t('common.editor.show_adults_helper'),
      entity: this._t('points_card.editor.entity_helper'),
      quick_add_amounts: this._t('points_card.editor.add_buttons_helper'),
      quick_remove_amounts: this._t('points_card.editor.remove_buttons_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;

    const addAmounts = this.config.quick_add_amounts || [1, 5, 10];
    const removeAmounts = this.config.quick_remove_amounts || [1, 5, 10];

    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      card_design: this.config.card_design || 'global',
      quick_add_amounts: this._amountsToString(addAmounts),
      quick_remove_amounts: this._amountsToString(removeAmounts),
      show_dialog: this.config.show_dialog !== false,
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
      <div class="amounts-preview">
        ${addAmounts.map(a => html`<span class="preview-btn add">+${(window.__taskmate_numbers ? window.__taskmate_numbers.format(this.hass, a) : a)}</span>`)}
        ${removeAmounts.map(a => html`<span class="preview-btn remove">−${(window.__taskmate_numbers ? window.__taskmate_numbers.format(this.hass, a) : a)}</span>`)}
      </div>
      ${this._renderColourPicker('header_color', '')}
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
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
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
      } else if (key === 'show_dialog' && value === true) {
        delete newConfig[key];
      } else if (key === 'quick_add_amounts' || key === 'quick_remove_amounts') {
        const parsed = this._parseAmounts(value, null);
        if (parsed && parsed.length) newConfig[key] = parsed;
        else delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === undefined || value === '') delete newConfig[key];
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

if (!customElements.get("taskmate-points-card-editor")) {
  customElements.define("taskmate-points-card-editor", TaskMatePointsCardEditor);
}
