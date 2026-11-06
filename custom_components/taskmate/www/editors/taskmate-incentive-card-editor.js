/**
 * TaskMate incentive card editor (Bonuses + Penalties visual card editor).
 *
 * Loaded on demand by taskmate-incentive-card.js getConfigElement(), so a
 * dashboard never downloads or parses it until someone opens the card editor.
 * The two cards share one editor class, parameterised by the same P
 * object the card factory gets.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

export function defineIncentiveEditor(P) {
  const tag = P.tag + "-editor";
  if (customElements.get(tag)) return;

  class IncentiveCardEditor extends LitElement {
    static get properties() {
      return { hass: { type: Object }, config: { type: Object } };
    }

    _t(key, params) {
      const fn = window.__taskmate_localize;
      return fn ? fn(this.hass, key, params) : key;
    }

    _tp(key, params) {
      return this._t(P.i18n + "." + key, params);
    }

    static get styles() {
      return css`
        :host { display: block; }
        ha-form { display: block; margin-bottom: 16px; }
        .info-note { font-size: 0.85rem; color: var(--secondary-text-color); background: var(--secondary-background-color, #f5f5f5); border-radius: 8px; padding: 10px 14px; line-height: 1.4; margin-bottom: 16px; display: flex; gap: 10px; align-items: flex-start; }
        .info-note ha-icon { flex-shrink: 0; color: var(--primary-color); --mdc-icon-size: 20px; margin-top: 1px; }
      `;
    }

    setConfig(config) { this.config = config; }

    _buildSchema() {
      return [
        { name: 'entity', selector: { entity: { domain: 'sensor' } } },
        { name: 'title', selector: { text: {} } },
        { name: 'show_parent_actions', selector: { boolean: {} } },
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
        entity: this._t('common.editor.overview_entity'),
        title: this._t('common.editor.card_title'),
        show_parent_actions: this._t('common.editor.show_parent_actions'),
        card_design: this._t('common.design.field_label'),
        show_adults: this._t('common.editor.show_adults'),
      };
      return labels[entry.name] ?? entry.name;
    };

    _computeHelper = (entry) => {
      const helpers = {
        entity: this._t('common.editor.overview_entity_helper'),
        show_parent_actions: this._t('common.editor.show_parent_actions_helper'),
        show_adults: this._t('common.editor.show_adults_helper'),
      };
      return helpers[entry.name] ?? '';
    };

    render() {
      if (!this.hass || !this.config) return html``;
      const data = {
        entity: this.config.entity || '',
        title: this.config.title || '',
        show_parent_actions: this.config.show_parent_actions !== false,
        card_design: this.config.card_design || 'global',
        show_adults: this.config.show_adults === true,
      };
      return html`
        <div class="info-note">
          <ha-icon icon="mdi:information-outline"></ha-icon>
          <span>${this._tp('editor.manage_note')}</span>
        </div>
        <ha-form
          .hass=${this.hass}
          .data=${data}
          .schema=${this._buildSchema().concat(window.__taskmate_adults_field ? window.__taskmate_adults_field(this.hass, this.config) : [])}
          .computeLabel=${this._computeLabel}
          .computeHelper=${this._computeHelper}
          @value-changed=${this._formChanged}
        ></ha-form>
        ${this._renderColourPicker('header_color', P.accent)}
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
        else if (key === 'show_adults' && value === false) delete newConfig[key];
        else newConfig[key] = value;
      }
      this._fire(newConfig);
    }

    _update(key, value) {
      this._fire({ ...this.config, [key]: value });
    }

    _fire(config) {
      this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
    }
  }

  customElements.define(tag, IncentiveCardEditor);
}
