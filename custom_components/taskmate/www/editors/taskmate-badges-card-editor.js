/**
 * TaskMate badges card editor (visual card editor).
 *
 * Loaded on demand by taskmate-badges-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;

// Editor: entity + per-card design override.
class TaskMateBadgesCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
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
              : [{ value: 'global', label: this._t('common.design.use_global') }],
            mode: 'dropdown',
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.entity'),
      title: this._t('common.editor.card_title'),
      card_design: this._t('common.design.field_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  render() {
    if (!this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      card_design: this.config.card_design || 'global',
    };
    return html`
      <p style="padding:0 0 8px;color:var(--secondary-text-color)">${this._t('badges.editor_help')}</p>
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._buildSchema()}
        .computeLabel=${this._computeLabel}
        @value-changed=${this._formChanged}
      ></ha-form>
    `;
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === '' || value === null || value === undefined) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

if (!customElements.get("taskmate-badges-card-editor")) {
  customElements.define("taskmate-badges-card-editor", TaskMateBadgesCardEditor);
}
