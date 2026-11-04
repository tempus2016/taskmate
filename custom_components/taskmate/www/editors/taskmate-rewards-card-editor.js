/**
 * TaskMate rewards card editor (visual card editor).
 *
 * Loaded on demand by taskmate-rewards-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Card Editor for visual configuration in Lovelace UI
class TaskMateRewardsCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
    };
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

  setConfig(config) {
    this.config = config;
  }

  // Build the ha-form schema based on the current state (e.g. child list from the entity).
  _buildSchema() {
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const children = entity?.attributes?.children || [];

    const childOptions = [
      { value: '__all__', label: this._t('rewards.editor.filter_by_child_all') },
      ...children.map((c) => ({ value: c.id, label: c.name })),
    ];

    return [
      {
        name: 'entity',
        selector: { entity: { domain: 'sensor' } },
      },
      {
        name: 'title',
        selector: { text: {} },
      },
      {
        name: 'child_id',
        selector: { select: { options: childOptions, mode: 'dropdown' } },
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
      {
        name: 'show_child_badges',
        selector: { boolean: {} },
      },
      {
        name: 'enable_pool_mode',
        selector: { boolean: {} },
      },
      {
        name: 'expand_to_fit',
        selector: { boolean: {} },
      },
    ];
  }

  _computeLabel = (schemaEntry) => {
    const labels = {
      entity: this._t('rewards.editor.entity'),
      title: this._t('rewards.editor.title'),
      child_id: this._t('rewards.editor.filter_by_child'),
      card_design: this._t('common.design.field_label'),
      show_child_badges: this._t('rewards.editor.show_child_badges'),
      enable_pool_mode: this._t('rewards.editor.enable_pool_mode'),
      expand_to_fit: this._t('rewards.editor.expand_to_fit'),
      show_adults: this._t('common.editor.show_adults'),
    };
    return labels[schemaEntry.name] ?? schemaEntry.name;
  };

  _computeHelper = (schemaEntry) => {
    const helpers = {
      entity: this._t('rewards.editor.entity_helper'),
      title: this._t('rewards.editor.title_helper'),
      child_id: this._t('rewards.editor.filter_by_child_helper'),
      show_child_badges: this._t('rewards.editor.show_child_badges_helper'),
      enable_pool_mode: this._t('rewards.editor.enable_pool_mode_helper'),
      expand_to_fit: this._t('rewards.editor.expand_to_fit_helper'),
      show_adults: this._t('common.editor.show_adults_helper'),
    };
    return helpers[schemaEntry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) {
      return html``;
    }
    // ha-form treats missing keys as empty; normalise for consistent values.
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      child_id: this.config.child_id || '__all__',
      card_design: this.config.card_design || 'global',
      show_child_badges: this.config.show_child_badges !== false,
      enable_pool_mode: this.config.enable_pool_mode === true,
      expand_to_fit: this.config.expand_to_fit !== false,
      show_adults: this.config.show_adults === true,
    };

    return html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._buildSchema().concat(window.__taskmate_adults_field ? window.__taskmate_adults_field(this.hass, this.config) : [])}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}
      ></ha-form>
      ${this._renderColourPicker('header_color', '#e67e22')}
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
    // Merge into config, removing keys that are empty/default so the YAML stays clean.
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (
        value === '' || value === null || value === undefined
        || (key === 'child_id' && value === '__all__')
      ) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (key === 'show_child_badges' && value === true) {
        // Default is true — omit to keep config minimal
        delete newConfig[key];
      } else if ((key === 'enable_pool_mode' || key === 'show_adults') && value === false) {
        delete newConfig[key];
      } else if (key === 'expand_to_fit' && value === true) {
        // Default is true (fluid) — omit to keep config minimal
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this._dispatchConfig(newConfig);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === undefined || value === '' || value === null) {
      delete newConfig[key];
    }
    this._dispatchConfig(newConfig);
  }

  _dispatchConfig(newConfig) {
    this.dispatchEvent(
      new CustomEvent('config-changed', {
        detail: { config: newConfig },
        bubbles: true,
        composed: true,
      })
    );
  }
}

if (!customElements.get("taskmate-rewards-card-editor")) {
  customElements.define("taskmate-rewards-card-editor", TaskMateRewardsCardEditor);
}
