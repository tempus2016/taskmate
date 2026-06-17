/**
 * TaskMate Reminders Card
 * Read-only view of the custom scheduled reminders configured in the panel
 * (name, time, days). Editing reminders remains an admin action in the panel.
 */
const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;
const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const _DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

class TaskMateRemindersCard extends LitElement {
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

  _daysLabel(mask) {
    if (mask == null) return "";
    const m = Number(mask);
    if ((m & 0b1111111) === 0b1111111) return this._t("reminders.every_day");
    if ((m & 0b1111111) === 0b0011111) return this._t("reminders.weekdays");
    if ((m & 0b1111111) === 0b1100000) return this._t("reminders.weekends");
    const days = _DAYS.filter((_, i) => m & (1 << i)).map(d => this._t("reminders.day_" + d));
    return days.join(", ") || this._t("reminders.never");
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
    const reminders = (attrs.custom_reminders || []).filter(r => r.enabled !== false);
    const header = _safeColor(this.config.header_color, "#e08a3c");

    return html`
      <ha-card style="--tm-h:${header}">
        <div class="hdr">${this.config.title || this._t("reminders.title")}</div>
        <div class="body">
          ${reminders.length === 0
            ? html`<div class="empty">${this._t("reminders.empty")}</div>`
            : reminders.map(r => html`
                <div class="rem">
                  <ha-icon icon="mdi:bell-outline"></ha-icon>
                  <div class="rem-main">
                    <div class="rem-name">${r.name}</div>
                    <div class="rem-meta">${this._daysLabel(r.day_mask)}</div>
                  </div>
                  <div class="rem-time">${r.time || ""}</div>
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
      .rem { display: flex; align-items: center; gap: 12px; padding: 10px 4px; border-top: 1px solid var(--divider-color, #eee); }
      .rem:first-child { border-top: 0; }
      .rem ha-icon { color: var(--tm-h); }
      .rem-main { flex: 1; }
      .rem-name { font-weight: 600; }
      .rem-meta { font-size: 0.82rem; color: var(--secondary-text-color); }
      .rem-time { font-variant-numeric: tabular-nums; font-weight: 700; color: var(--tm-h); }
    `;
  }
}

customElements.define("taskmate-reminders-card", TaskMateRemindersCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-reminders-card",
  name: "TaskMate Reminders",
  description: "Read-only view of custom scheduled reminders",
  preview: true,
});
