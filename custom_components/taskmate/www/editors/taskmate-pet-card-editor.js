/**
 * TaskMate pet card editor (visual card editor).
 *
 * Loaded on demand by taskmate-pet-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMatePetCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  setConfig(config) { this.config = config; }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _buildSchema() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const children = attrs.children || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      { name: "child_id", selector: { select: { options: children.map(c => ({ value: c.id, label: c.name })), mode: "dropdown" } } },
      { name: "title", selector: { text: {} } },
      { name: "show_shop", selector: { boolean: {} } },
      { name: "hide_unaffordable", selector: { boolean: {} } },
      {
        name: "card_design",
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: "global", label: "Use global default" }],
            mode: "dropdown",
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => ({
    entity: this._t("common.editor.overview_entity"),
    child_id: this._t("pet.editor.child"),
    title: this._t("common.editor.card_title"),
    show_shop: this._t("pet.editor.show_shop"),
    hide_unaffordable: this._t("pet.editor.hide_unaffordable"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
      show_shop: this.config.show_shop !== false,
      hide_unaffordable: this.config.hide_unaffordable === true,
      card_design: this.config.card_design || "global",
    };
    return html`<ha-form .hass=${this.hass} .data=${data} .schema=${this._buildSchema()}
      .computeLabel=${this._computeLabel} @value-changed=${this._formChanged}></ha-form>`;
  }

  _formChanged(e) {
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(e.detail.value || {})) {
      if (value === "" || value === null || value === undefined || (key === "card_design" && value === "global")
        || (key === "show_shop" && value === true) || (key === "hide_unaffordable" && value === false)) delete newConfig[key];
      else newConfig[key] = value;
    }
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: newConfig }, bubbles: true, composed: true }));
  }

  static get styles() {
    return css`:host { display: block; }`;
  }
}

if (!customElements.get("taskmate-pet-card-editor")) {
  customElements.define("taskmate-pet-card-editor", TaskMatePetCardEditor);
}
