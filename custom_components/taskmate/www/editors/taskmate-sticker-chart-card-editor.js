/**
 * TaskMate sticker chart card editor (visual card editor).
 *
 * Loaded on demand by taskmate-sticker-chart-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateStickerChartCardEditor extends LitElement {
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

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || (this.config?.entity ? this.hass?.states?.[this.config.entity]?.attributes : null)
      || {};
  }

  _buildSchema() {
    const attrs = this._attrs();
    const children = attrs.children || [];
    const rewards = attrs.rewards || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      {
        name: "child_id",
        selector: {
          select: {
            options: [
              { value: "", label: this._t("sticker_chart.editor.child_all") },
              ...children.map(c => ({ value: c.id, label: c.name })),
            ],
            mode: "dropdown",
          },
        },
      },
      {
        name: "reward_id",
        selector: {
          select: {
            options: [
              { value: "", label: this._t("sticker_chart.editor.reward_auto") },
              ...rewards.map(r => ({ value: r.id, label: `${r.name} (${(window.__taskmate_numbers ? window.__taskmate_numbers.format(this.hass, r.cost) : r.cost)})` })),
            ],
            mode: "dropdown",
          },
        },
      },
      {
        name: "goal",
        selector: {
          select: {
            options: [
              { value: "reward", label: this._t("sticker_chart.editor.goal_reward") },
              { value: "week", label: this._t("sticker_chart.editor.goal_week") },
            ],
            mode: "dropdown",
          },
        },
      },
      { name: "title", selector: { text: {} } },
      { name: "columns", selector: { number: { min: 2, max: 6, mode: "slider" } } },
      { name: "show_today", selector: { boolean: {} } },
      { name: "show_claim", selector: { boolean: {} } },
      { name: "allow_undo", selector: { boolean: {} } },
      { name: "sound", selector: { boolean: {} } },
      {
        name: "card_design",
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: "global", label: this._t("common.design.use_global") }],
            mode: "dropdown",
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      show_adults: this._t("common.editor.show_adults"),
      entity: this._t("common.editor.overview_entity"),
      child_id: this._t("sticker_chart.editor.child"),
      reward_id: this._t("sticker_chart.editor.reward"),
      goal: this._t("sticker_chart.editor.goal"),
      title: this._t("sticker_chart.editor.title"),
      columns: this._t("sticker_chart.editor.columns"),
      show_today: this._t("sticker_chart.editor.show_today"),
      show_claim: this._t("sticker_chart.editor.show_claim"),
      allow_undo: this._t("sticker_chart.editor.allow_undo"),
      sound: this._t("sticker_chart.editor.sound"),
      card_design: this._t("common.design.field_label"),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      show_adults: this._t("common.editor.show_adults_helper"),
      entity: this._t("common.editor.overview_entity_helper"),
      reward_id: this._t("sticker_chart.editor.reward_helper"),
      goal: this._t("sticker_chart.editor.goal_helper"),
      title: this._t("sticker_chart.editor.title_helper"),
      show_today: this._t("sticker_chart.editor.show_today_helper"),
      show_claim: this._t("sticker_chart.editor.show_claim_helper"),
      allow_undo: this._t("sticker_chart.editor.allow_undo_helper"),
    };
    return helpers[entry.name] ?? "";
  };

  // Booleans that default to true are only written when switched off, and the
  // default column count is omitted, so a card's YAML stays minimal.
  _valueChanged(e) {
    e.stopPropagation();
    const defaultsOn = new Set(["show_today", "show_claim", "allow_undo", "sound"]);
    const newConfig = {};
    for (const [key, value] of Object.entries(e.detail.value)) {
      if (value === "" || value === null || value === undefined) continue;
      if (key === "card_design" && value === "global") continue;
      if (key === "goal" && value === "reward") continue;
      if (defaultsOn.has(key) && value === true) continue;
      if (key === "columns" && Number(value) === 4) continue;
      newConfig[key] = value;
    }
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  render() {
    if (!this.hass || !this.config) return html``;
    const data = { goal: "reward", show_today: true, show_claim: true, allow_undo: true, sound: true, columns: 4, ...this.config };
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._buildSchema().concat(window.__taskmate_adults_field ? window.__taskmate_adults_field(this.hass, this.config) : [])}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._valueChanged}
      ></ha-form>
    `;
  }
}

if (!customElements.get("taskmate-sticker-chart-card-editor")) {
  customElements.define("taskmate-sticker-chart-card-editor", TaskMateStickerChartCardEditor);
}
