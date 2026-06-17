/**
 * TaskMate Templates Card
 * Read-only view of available chore template packs (built-in + custom).
 * Applying templates remains an admin action in the TaskMate panel.
 */
const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;
const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateTemplatesCard extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass")) {
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
    }
    return true;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("entity is required");
    this.config = config;
  }

  getCardSize() { return 3; }

  static getStubConfig() { return { entity: "sensor.taskmate_overall_stats" }; }

  render() {
    if (!this.hass || !this.config) return html``;
    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="empty">${this._t("common.entity_not_found", { entity: this.config.entity })}</div></ha-card>`;
    }
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const templates = attrs.templates || [];
    const header = _safeColor(this.config.header_color, "#27ae8f");

    return html`
      <ha-card style="--tm-h:${header}">
        <div class="hdr">${this.config.title || this._t("templates.title")}</div>
        <div class="body">
          ${templates.length === 0
            ? html`<div class="empty">${this._t("templates.empty")}</div>`
            : templates.map(t => html`
                <div class="tpl">
                  <ha-icon icon="${t.icon || "mdi:clipboard-list"}"></ha-icon>
                  <div class="tpl-main">
                    <div class="tpl-name">${t.name}
                      ${t.builtin ? html`<span class="tag">${this._t("templates.builtin")}</span>` : ""}
                    </div>
                    <div class="tpl-meta">${this._t("templates.chore_count", { count: t.chore_count || 0 })}</div>
                  </div>
                </div>
              `)}
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      ha-card { overflow: hidden; }
      .hdr { background: var(--tm-h); color: #fff; font-weight: 700; padding: 12px 16px; font-size: 1.05rem; }
      .body { padding: 8px 12px; display: flex; flex-direction: column; }
      .empty { color: var(--secondary-text-color); font-size: 0.9rem; padding: 8px 4px; }
      .tpl { display: flex; align-items: center; gap: 12px; padding: 10px 4px; border-top: 1px solid var(--divider-color, #eee); }
      .tpl:first-child { border-top: 0; }
      .tpl ha-icon { color: var(--tm-h); }
      .tpl-main { flex: 1; }
      .tpl-name { font-weight: 600; display: flex; align-items: center; gap: 8px; }
      .tpl-meta { font-size: 0.82rem; color: var(--secondary-text-color); }
      .tag { font-size: 0.68rem; text-transform: uppercase; letter-spacing: .04em; background: var(--secondary-background-color, #eee); color: var(--secondary-text-color); padding: 1px 7px; border-radius: 999px; }
    `;
  }
}

customElements.define("taskmate-templates-card", TaskMateTemplatesCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-templates-card",
  name: "TaskMate Templates",
  description: "Read-only view of available chore template packs",
  preview: true,
});
