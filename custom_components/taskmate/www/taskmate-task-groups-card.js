/**
 * TaskMate Task Groups Card
 * Read-only view of configured task groups (rotation coordination): each
 * group's name, policy and member chores.
 */
const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;
const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateTaskGroupsCard extends LitElement {
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

  static getStubConfig() { return { entity: "sensor.taskmate_overview" }; }

  render() {
    if (!this.hass || !this.config) return html``;
    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="empty">${this._t("common.entity_not_found", { entity: this.config.entity })}</div></ha-card>`;
    }
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const groups = attrs.task_groups || [];
    const chores = attrs.chores || [];
    const choreName = (id) => (chores.find(c => c.id === id) || {}).name || id;
    const header = _safeColor(this.config.header_color, "#5b8def");

    return html`
      <ha-card style="--tm-h:${header}">
        <div class="hdr">${this.config.title || this._t("task_groups.title")}</div>
        <div class="body">
          ${groups.length === 0
            ? html`<div class="empty">${this._t("task_groups.empty")}</div>`
            : groups.map(g => html`
                <div class="grp">
                  <div class="grp-head">
                    <span class="grp-name">${g.name}</span>
                    <span class="grp-policy">${this._t("task_groups.policy_" + (g.policy || "sticky"))}</span>
                  </div>
                  <div class="grp-chores">
                    ${(g.chore_ids || []).length === 0
                      ? html`<span class="muted">${this._t("task_groups.no_chores")}</span>`
                      : (g.chore_ids || []).map(id => html`<span class="chip">${choreName(id)}</span>`)}
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
      .body { padding: 12px 16px; display: flex; flex-direction: column; gap: 12px; }
      .empty, .muted { color: var(--secondary-text-color); font-size: 0.9rem; }
      .grp { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 10px; padding: 10px 12px; }
      .grp-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
      .grp-name { font-weight: 600; }
      .grp-policy { font-size: 0.72rem; text-transform: uppercase; letter-spacing: .04em; color: #fff; background: var(--tm-h); padding: 2px 8px; border-radius: 999px; }
      .grp-chores { display: flex; flex-wrap: wrap; gap: 6px; }
      .chip { background: var(--secondary-background-color, #f1f1f1); border-radius: 999px; padding: 3px 10px; font-size: 0.82rem; }
    `;
  }
}

customElements.define("taskmate-task-groups-card", TaskMateTaskGroupsCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-task-groups-card",
  name: "TaskMate Task Groups",
  description: "Read-only view of task groups and their member chores",
  preview: true,
});
