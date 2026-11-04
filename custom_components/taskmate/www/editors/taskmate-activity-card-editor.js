/**
 * TaskMate activity card editor (visual card editor).
 *
 * Loaded on demand by taskmate-activity-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Card Editor
class TaskMateActivityCardEditor extends LitElement {
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
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const children = entity?.attributes?.children || [];
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '__all__', label: this._t('common.editor.filter_by_child_all') },
              ...children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
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
      { name: 'max_items', selector: { number: { min: 5, max: 200, mode: 'box' } } },
      { name: 'show_filter_chips', selector: { boolean: {} } },
      { name: 'accent_stripes', selector: { boolean: {} } },
      { name: 'show_relative_time', selector: { boolean: {} } },
      { name: 'show_undo', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      title: this._t('common.editor.card_title'),
      card_design: this._t('common.design.field_label'),
      child_id: this._t('common.editor.filter_by_child'),
      max_items: this._t('activity.editor.max_items'),
      show_filter_chips: this._t('activity.editor.show_filter_chips'),
      accent_stripes: this._t('activity.editor.accent_stripes'),
      show_relative_time: this._t('activity.editor.show_relative_time'),
      show_undo: this._t('activity.editor.show_undo'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('activity.editor.filter_child_helper'),
      max_items: this._t('activity.editor.max_items_helper'),
      show_filter_chips: this._t('activity.editor.show_filter_chips_helper'),
      accent_stripes: this._t('activity.editor.accent_stripes_helper'),
      show_relative_time: this._t('activity.editor.show_relative_time_helper'),
      show_undo: this._t('activity.editor.show_undo_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      card_design: this.config.card_design || 'global',
      child_id: this.config.child_id || '__all__',
      max_items: this.config.max_items || 30,
      show_filter_chips: this.config.show_filter_chips !== false,
      accent_stripes: this.config.accent_stripes !== false,
      show_relative_time: this.config.show_relative_time !== false,
      show_undo: this.config.show_undo !== false,
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
      ${this._renderColourPicker('header_color', '#2471a3')}
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
    // Booleans whose default is `true` — drop them from config when true to keep YAML minimal.
    const trueDefaultBooleans = new Set(['show_filter_chips', 'accent_stripes', 'show_relative_time']);
    for (const [key, value] of Object.entries(newValues)) {
      if (
        value === '' || value === null || value === undefined
        || (key === 'child_id' && value === '__all__')
      ) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (key === 'max_items' && value === 30) {
        delete newConfig[key];
      } else if (trueDefaultBooleans.has(key) && value === true) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
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

if (!customElements.get("taskmate-activity-card-editor")) {
  customElements.define("taskmate-activity-card-editor", TaskMateActivityCardEditor);
}
