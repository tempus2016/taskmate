/**
 * TaskMate reward progress card editor (visual card editor).
 *
 * Loaded on demand by taskmate-reward-progress-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateRewardProgressCardEditor extends LitElement {
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
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity)) || (this.config?.entity ? this.hass?.states?.[this.config.entity]?.attributes : null) || {};
    const rewards = attrs.rewards || [];
    const children = attrs.children || [];
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'reward_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('reward_progress.editor.first_available') },
              ...rewards.map((r) => ({ value: r.id, label: r.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('reward_progress.editor.child_filter_all') },
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
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      show_adults: this._t('common.editor.show_adults'),
      entity: this._t('common.editor.overview_entity'),
      title: this._t('common.editor.card_title'),
      reward_id: this._t('reward_progress.editor.reward_to_display'),
      child_id: this._t('common.editor.filter_by_child'),
      card_design: this._t('common.design.field_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      show_adults: this._t('common.editor.show_adults_helper'),
      entity: this._t('common.editor.overview_entity_helper'),
      reward_id: this._t('reward_progress.editor.reward_helper'),
      child_id: this._t('reward_progress.editor.child_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      reward_id: this.config.reward_id || '',
      child_id: this.config.child_id || '',
      card_design: this.config.card_design || 'global',
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
      onInput: (v) => this._update(key, v),
      onPreset: (v) => this._update(key, v),
      onReset: () => this._update(key, defaultValue),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === '' || value === null || value === undefined) delete newConfig[key];
      else if (key === 'card_design' && value === 'global') delete newConfig[key];
      else newConfig[key] = value;
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _update(key, value) {
    const cfg = { ...this.config, [key]: value };
    if (!value) delete cfg[key];
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: cfg }, bubbles: true, composed: true }));
  }
}

if (!customElements.get("taskmate-reward-progress-card-editor")) {
  customElements.define("taskmate-reward-progress-card-editor", TaskMateRewardProgressCardEditor);
}
