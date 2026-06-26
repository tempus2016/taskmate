/**
 * TaskMate Family Goal Card
 * Shows the shared family co-op goal (combined points across all children) with
 * a progress bar toward the target and the reward. Reads the overview sensor's
 * `family_goal` attribute.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateFamilyGoalCard extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("A TaskMate overview entity is required");
    }
    this.config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  getCardSize() {
    return 2;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  render() {
    if (!this.hass || !this.config) return html``;
    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="empty"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t("common.entity_not_found", { entity: this.config.entity })}</div></div></ha-card>`;
    }
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const goal = attrs.family_goal || {};
    const pointsName = attrs.points_name || this._t("common.points");

    if (!goal.enabled || !goal.target) {
      return html`<ha-card><div class="empty"><ha-icon icon="mdi:flag-checkered"></ha-icon><div>${this._t("family_goal.disabled")}</div></div></ha-card>`;
    }

    const progress = Number(goal.progress) || 0;
    const target = Number(goal.target) || 0;
    const pct = target > 0 ? Math.min(100, Math.round((progress / target) * 100)) : 0;
    const achieved = !!goal.achieved || progress >= target;

    return html`
      <ha-card>
        <style>:host { --tm-goal-accent: ${_safeColor(this.config.header_color, "#16a085")}; }</style>
        <div class="head">
          <ha-icon icon="${achieved ? "mdi:trophy" : "mdi:flag-checkered"}"></ha-icon>
          <span class="title">${this.config.title || goal.name || this._t("family_goal.default_title")}</span>
        </div>
        <div class="body">
          <div class="bar"><div class="fill ${achieved ? "done" : ""}" style="width:${pct}%"></div></div>
          <div class="stats">
            <span>${progress} / ${target} ${pointsName}</span>
            <span>${pct}%</span>
          </div>
          ${achieved
            ? html`<div class="reward done">🎉 ${this._t("family_goal.reached", { reward: goal.reward || "" })}</div>`
            : goal.reward
              ? html`<div class="reward">${this._t("family_goal.reward_label", { reward: goal.reward })}</div>`
              : ""}
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      .head { display: flex; align-items: center; gap: 8px; padding: 14px 16px 6px; font-weight: 600; }
      .head ha-icon { color: var(--tm-goal-accent); }
      .body { padding: 4px 16px 16px; }
      .bar { height: 14px; border-radius: 8px; background: var(--secondary-background-color, #eee); overflow: hidden; }
      .fill { height: 100%; background: var(--tm-goal-accent); transition: width .4s ease; }
      .fill.done { background: #d4ac0d; }
      .stats { display: flex; justify-content: space-between; font-size: 0.82rem; color: var(--secondary-text-color); margin-top: 6px; }
      .reward { margin-top: 8px; font-size: 0.85rem; color: var(--primary-text-color); }
      .reward.done { font-weight: 600; color: #d4ac0d; }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 28px 16px; color: var(--secondary-text-color); }
    `;
  }
}

customElements.define("taskmate-family-goal-card", TaskMateFamilyGoalCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-family-goal-card",
  name: "TaskMate Family Goal",
  description: "Shared family goal progress toward a combined points target",
  preview: true,
});
