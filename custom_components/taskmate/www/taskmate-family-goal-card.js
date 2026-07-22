/**
 * TaskMate Family Goal Card
 * Shows the shared family co-op goal (combined points across all children) with
 * a progress bar toward the target and the reward. Reads the overview sensor's
 * `family_goal` attribute.
 *
 * Single layout, so it consumes the design tokens directly (like the routine
 * card) rather than carrying a second _renderDesigned() template. Every
 * --tmd-* reference has the card's original value as its fallback, so classic
 * — which defines no tokens — renders exactly as it did before.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const DEFAULT_ACCENT = "#16a085";

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

  /**
   * Resolve the active design, stamp data-tm-design on the host (which is what
   * makes the :host-scoped token block apply inside this shadow root), and set
   * the accent. The accent is set as an inline host property, not from a
   * <style> in the template: a shadow tree's <style> is ordered before
   * adoptedStyleSheets, so it loses to the :host default in static styles().
   */
  _applyDesign() {
    if (window.__taskmate_design) {
      window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity);
    }
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--fg-accent", _safeColor(configured, DEFAULT_ACCENT));
    } else {
      this.style.removeProperty("--fg-accent");
    }
  }

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="fg-empty"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t("common.entity_not_found", { entity: this.config.entity })}</div></div></ha-card>`;
    }
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const goal = attrs.family_goal || {};
    const pointsName = attrs.points_name || this._t("common.points");

    if (!goal.enabled || !goal.target) {
      return html`<ha-card><div class="fg-empty"><ha-icon icon="mdi:flag-checkered"></ha-icon><div>${this._t("family_goal.disabled")}</div></div></ha-card>`;
    }

    const progress = Number(goal.progress) || 0;
    const target = Number(goal.target) || 0;
    const pct = target > 0 ? Math.min(100, Math.round((progress / target) * 100)) : 0;
    const achieved = !!goal.achieved || progress >= target;

    return html`
      <ha-card>
        <div class="fg-head">
          <ha-icon icon="${achieved ? "mdi:trophy" : "mdi:flag-checkered"}"></ha-icon>
          <span class="fg-title">${this.config.title || goal.name || this._t("family_goal.default_title")}</span>
        </div>
        <div class="fg-body">
          <div class="fg-bar"><div class="fg-fill ${achieved ? "done" : ""}" style="width:${pct}%"></div></div>
          <div class="fg-stats">
            <span>${progress} / ${target} ${pointsName}</span>
            <span>${pct}%</span>
          </div>
          ${achieved
            ? html`<div class="fg-reward done">🎉 ${this._t("family_goal.reached", { reward: goal.reward || "" })}</div>`
            : goal.reward
              ? html`<div class="fg-reward">${this._t("family_goal.reward_label", { reward: goal.reward })}</div>`
              : ""}
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    // Layout classes carry an fg- prefix because the shared design kit defines
    // its own .bar (and .stat / .grid / …); a bare .bar here would pick up the
    // kit's rules under a designed style.
    const base = css`
      :host { --fg-accent: var(--tmd-accent, #16a085); }
      ha-card {
        overflow: hidden;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px));
        font-family: var(--tmd-font-body, inherit);
      }
      .fg-head {
        display: flex; align-items: center; gap: 8px;
        padding: 14px 16px 6px; font-weight: 600;
        font-family: var(--tmd-font-display, inherit);
      }
      .fg-head ha-icon { color: var(--fg-accent); }
      .fg-body { padding: 4px 16px 16px; }
      .fg-bar {
        height: 14px; border-radius: var(--tmd-radius-sm, 8px);
        background: var(--tmd-surface-2, var(--secondary-background-color, #eee));
        border: 1px solid var(--tmd-border, transparent);
        box-sizing: border-box;
        overflow: hidden;
      }
      .fg-fill { height: 100%; background: var(--fg-accent); transition: width .4s ease; }
      .fg-fill.done { background: var(--tmd-gold, #d4ac0d); }
      .fg-stats {
        display: flex; justify-content: space-between;
        font-size: 0.82rem; color: var(--tmd-dim, var(--secondary-text-color)); margin-top: 6px;
      }
      .fg-reward { margin-top: 8px; font-size: 0.85rem; color: var(--tmd-text, var(--primary-text-color)); }
      .fg-reward.done { font-weight: 600; color: var(--tmd-gold, #d4ac0d); }
      .fg-empty {
        display: flex; flex-direction: column; align-items: center; gap: 8px;
        padding: 28px 16px; color: var(--tmd-dim, var(--secondary-text-color));
      }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

customElements.define("taskmate-family-goal-card", TaskMateFamilyGoalCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-family-goal-card",
  name: "TaskMate Family Goal",
  description: "Shared family goal progress toward a combined points target",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-family-goal-card", "overview"),
});
