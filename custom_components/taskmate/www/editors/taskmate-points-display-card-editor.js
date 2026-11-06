/**
 * TaskMate points display card editor (visual card editor).
 *
 * Loaded on demand by taskmate-points-display-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Shared with taskmate-points-display-card.js; tests/frontend/taskmate-lazy-editors.test.cjs keeps the copies equal.
const DEFAULT_HEADER = "#9b59b6";
function getChildren(state) {
  return state.attributes.children || [];
}

class TaskMatePointsDisplayCardEditor extends LitElement {

  static get properties() {
    return {
      hass:   { type: Object },
      config: { type: Object },
      _children: { type: Array },
    };
  }

  constructor() {
    super();
    this._children = [];
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  static get styles() {
    return css`
      :host { display: block; padding: 8px 0; }
      ha-form { display: block; margin-bottom: 16px; }
    `;
  }

  setConfig(config) {
    this.config = config;
  }

  updated(changed) {
    if (changed.has('hass') && this.hass && this.config?.entity) {
      this._loadChildren();
    }
  }

  _loadChildren() {
    const state = this.hass?.states?.[this.config.entity];
    if (!state) { this._children = []; return; }
    this._children = getChildren(state);
  }

  _buildSchema() {
    const mode = this.config.mode || 'single';
    const schema = [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'mode',
        selector: {
          select: {
            options: [
              { value: 'single', label: this._t('points_display.editor.mode_single') },
              { value: 'multi', label: this._t('points_display.editor.mode_multi') },
              { value: 'cumulative', label: this._t('points_display.editor.mode_cumulative') },
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
              : [{ value: 'global', label: this._t('common.design.use_global') }],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'primary_display',
        selector: {
          select: {
            options: [
              { value: 'current_points', label: this._t('points_display.editor.primary_current_points') },
              { value: 'career_score', label: this._t('points_display.editor.primary_career_score') },
            ],
            mode: 'dropdown',
          },
        },
      },
    ];

    if (mode === 'single') {
      schema.push({
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('points_display.editor.select_child') },
              ...this._children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: 'dropdown',
          },
        },
      });
    }

    schema.push({ name: 'show_weekly', selector: { boolean: {} } });
    schema.push({ name: 'show_streak', selector: { boolean: {} } });
    if (mode !== 'single') {
      schema.push({ name: 'show_rank', selector: { boolean: {} } });
    }
    return schema;
  }

  _computeLabel = (entry) => {
    const labels = {
      show_adults: this._t('common.editor.show_adults'),
      entity: this._t('points_display.editor.entity_label'),
      title: this._t('common.editor.card_title'),
      mode: this._t('points_display.editor.mode_label'),
      card_design: this._t('common.design.field_label'),
      primary_display: this._t('points_display.editor.primary_display'),
      child_id: this._t('points_display.editor.child_label'),
      show_weekly: this._t('points_display.editor.show_weekly'),
      show_streak: this._t('points_display.editor.show_streak'),
      show_rank: this._t('points_display.editor.show_rank'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => (entry.name === 'show_adults' ? this._t('common.editor.show_adults_helper') : '');

  render() {
    if (!this.config) return html``;
    const mode = this.config.mode || 'single';
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      mode,
      card_design: this.config.card_design || 'global',
      primary_display: this.config.primary_display || 'current_points',
      child_id: this.config.child_id || '',
      show_weekly: this.config.show_weekly !== false,
      show_streak: this.config.show_streak !== false,
      show_rank: this.config.show_rank !== false,
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
      ${this._renderColourPicker('header_color', DEFAULT_HEADER)}
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
      onInput: (v) => this._set(key, v),
      onPreset: (v) => this._set(key, v),
      onReset: () => this._set(key, defaultValue),
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
      } else if (key === 'mode' && value === 'single') {
        delete newConfig[key];
      } else if (key === 'primary_display' && value === 'current_points') {
        delete newConfig[key];
      } else if ((key === 'show_weekly' || key === 'show_streak' || key === 'show_rank') && value === true) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this._fire(newConfig);
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config },
      bubbles: true,
      composed: true,
    }));
  }

  _set(key, value) {
    this._fire({ ...this.config, [key]: value });
  }
}

if (!customElements.get("taskmate-points-display-card-editor")) {
  customElements.define("taskmate-points-display-card-editor", TaskMatePointsDisplayCardEditor);
}
