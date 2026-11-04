/**
 * TaskMate leaderboard card editor (visual card editor).
 *
 * Loaded on demand by taskmate-leaderboard-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateLeaderboardCardEditor extends LitElement {
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
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'sort_by',
        selector: {
          select: {
            options: [
              { value: 'points', label: this._t('leaderboard.editor.sort_option_points') },
              { value: 'streak', label: this._t('leaderboard.editor.sort_option_streak') },
              { value: 'weekly', label: this._t('leaderboard.editor.sort_option_weekly') },
              { value: 'career', label: this._t('leaderboard.editor.sort_option_career') },
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
      { name: 'show_streak', selector: { boolean: {} } },
      { name: 'show_weekly', selector: { boolean: {} } },
      { name: 'show_career', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      show_adults: this._t('common.editor.show_adults'),
      entity: this._t('leaderboard.editor.entity_label'),
      title: this._t('leaderboard.editor.title_label'),
      sort_by: this._t('leaderboard.editor.rank_by_label'),
      card_design: this._t('common.design.field_label'),
      show_streak: this._t('leaderboard.editor.show_streak'),
      show_weekly: this._t('leaderboard.editor.show_weekly'),
      show_career: this._t('leaderboard.editor.show_career'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      show_adults: this._t('common.editor.show_adults_helper'),
      entity: this._t('leaderboard.editor.entity_helper'),
      sort_by: this._t('leaderboard.editor.rank_by_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      sort_by: this.config.sort_by || 'points',
      card_design: this.config.card_design || 'global',
      show_streak: this.config.show_streak !== false,
      show_weekly: this.config.show_weekly !== false,
      show_career: this.config.show_career !== false,
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
      ${this._renderColourPicker('header_color', '#b7950b')}
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
      } else if ((key === 'show_streak' || key === 'show_weekly' || key === 'show_career') && value === true) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (key === 'sort_by' && value === 'points') {
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

if (!customElements.get("taskmate-leaderboard-card-editor")) {
  customElements.define("taskmate-leaderboard-card-editor", TaskMateLeaderboardCardEditor);
}
