/**
 * TaskMate Badges Card
 * Displays a full grid of achievement badges for a single child.
 * Earned badges show tier colour and earn date; locked badges show
 * closest-criterion progress bar.
 *
 * Config:
 *   entity   - (required) full entity id, e.g. sensor.taskmate_badges_mia
 *   title    - card title override
 *
 * Version: 1.0.0
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateBadgesCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _filterTier: { type: String },
      _justEarned: { type: String },
    };
  }

  constructor() {
    super();
    this._filterTier = "all";
    this._justEarned = null;
    this._unsubscribeEvents = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this._subscribeEvents();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsubscribeEvents?.();
    this._unsubscribeEvents = null;
  }

  _subscribeEvents() {
    if (!this.hass) return;
    this.hass.connection.subscribeEvents((event) => {
      const data = event.data || {};
      if (data.child_id && this.config?.child_id && String(data.child_id) !== String(this.config.child_id)) return;
      if (data.badge_id) {
        this._justEarned = String(data.badge_id);
        this.requestUpdate();
        setTimeout(() => {
          this._justEarned = null;
          this.requestUpdate();
        }, 1800);
      }
    }, "taskmate_badge_earned").then(unsub => {
      this._unsubscribeEvents = unsub;
    }).catch(() => {});
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

  static get styles() {
    return css`
      :host {
        display: block;
        --t-bronze:   #cd7f32;
        --t-silver:   #c0c0c0;
        --t-gold:     #f1c40f;
        --t-platinum: #67e8f9;
      }

      ha-card { overflow: hidden; }

      /* ── Header ── */
      .badges-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 18px 14px;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
        gap: 12px;
      }

      .badges-head-left {
        display: flex;
        align-items: center;
        gap: 12px;
        flex: 1;
        min-width: 0;
      }

      .child-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: var(--primary-color, #1a3a5c);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        --mdc-icon-size: 24px;
        color: white;
      }

      .badges-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .badges-count {
        font-size: 0.75rem;
        color: var(--secondary-text-color);
        margin-top: 1px;
      }

      .badges-filter {
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        color: var(--primary-text-color);
        padding: 6px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        flex-shrink: 0;
        cursor: pointer;
      }

      /* ── Grid ── */
      .badge-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 12px;
        padding: 16px;
      }

      /* ── Tier colour helpers ── */
      .tier-bronze  { --t: var(--t-bronze);   --t-glow: rgba(205,127,50,0.25); }
      .tier-silver  { --t: var(--t-silver);   --t-glow: rgba(192,192,192,0.25); }
      .tier-gold    { --t: var(--t-gold);     --t-glow: rgba(241,196,15,0.30); }
      .tier-platinum{ --t: var(--t-platinum); --t-glow: rgba(103,232,249,0.30); }

      /* ── Badge tile ── */
      .badge {
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 12px;
        padding: 14px 10px;
        text-align: center;
        position: relative;
        transition: transform 0.15s;
        border: 2px solid var(--divider-color, #e0e0e0);
      }

      .badge.earned {
        border-color: var(--t);
        box-shadow: 0 0 0 1px var(--t-glow), 0 4px 12px var(--t-glow);
      }

      .badge.earned:hover { transform: translateY(-2px); }
      .badge.locked { opacity: 0.55; }

      .badge.just-earned {
        animation: earn-pulse 1.6s ease-out;
      }

      @keyframes earn-pulse {
        0%   { transform: scale(0.6); box-shadow: 0 0 0 0 var(--t-glow, rgba(255,255,255,0.1)); }
        50%  { transform: scale(1.08); box-shadow: 0 0 0 16px var(--t-glow, rgba(255,255,255,0.1)); }
        100% { transform: scale(1); box-shadow: 0 0 0 1px var(--t-glow), 0 4px 12px var(--t-glow); }
      }

      .badge-icon {
        width: 52px;
        height: 52px;
        margin: 0 auto 8px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        --mdc-icon-size: 28px;
        background: var(--divider-color, #e0e0e0);
        color: var(--secondary-text-color);
      }

      .badge.earned .badge-icon {
        background: var(--t);
        color: #1a1a1a;
      }

      .badge-tier {
        font-size: 0.6rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 700;
        color: var(--t, var(--secondary-text-color));
        margin-bottom: 4px;
      }

      .badge-name {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--primary-text-color);
        margin-bottom: 3px;
        line-height: 1.25;
      }

      .badge.locked .badge-name { color: var(--secondary-text-color); }

      .badge-meta {
        font-size: 0.65rem;
        color: var(--secondary-text-color);
        margin-bottom: 6px;
      }

      .badge.earned .badge-meta { color: var(--t); }

      .badge-progress {
        height: 4px;
        background: var(--divider-color, #ddd);
        border-radius: 2px;
        overflow: hidden;
        margin-top: 6px;
      }

      .badge-progress-fill {
        height: 100%;
        background: var(--t);
        border-radius: 2px;
        transition: width 0.4s ease;
      }

      .badge-progress-label {
        font-size: 0.62rem;
        color: var(--secondary-text-color);
        margin-top: 3px;
      }

      .badge-bonus {
        position: absolute;
        top: 6px;
        right: 6px;
        background: var(--t);
        color: #1a1a1a;
        font-size: 0.62rem;
        font-weight: 700;
        padding: 2px 5px;
        border-radius: 999px;
      }

      /* ── Empty / error states ── */
      .error-state, .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        color: var(--secondary-text-color);
        text-align: center;
      }

      .error-state { color: var(--error-color, #f44336); }
      .error-state ha-icon, .empty-state ha-icon {
        --mdc-icon-size: 48px;
        margin-bottom: 12px;
        opacity: 0.5;
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("taskmate-badges-card: 'entity' is required (e.g. sensor.taskmate_badges_mia)");
    }
    this.config = { title: null, ...config };
    // Extract child_id from entity name for event matching:
    // sensor.taskmate_badges_<slug> → slug
    const match = config.entity.match(/sensor\.taskmate_badges_(.+)/);
    this._childSlug = match ? match[1] : null;
  }

  getCardSize() { return 5; }

  static getConfigElement() { return document.createElement("taskmate-badges-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_badges_child" };
  }

  _tierLabel(tier) {
    return this._t("badge.tier_" + (tier || "bronze"));
  }

  _formatDate(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
    } catch {
      return iso;
    }
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('badges.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;
    }

    const attrs = entity.attributes || {};
    const earned = attrs.earned || [];
    const available = attrs.available || [];
    const childName = attrs.child_name || attrs.name || "";
    const childAvatar = attrs.child_avatar || "mdi:account-circle";
    const totalBadges = attrs.total_badges || (earned.length + available.length);

    const filter = this._filterTier;
    const filteredEarned = filter === "all" ? earned : earned.filter(b => b.tier === filter);
    const filteredLocked = filter === "all" ? available : available.filter(b => b.tier === filter);

    const latestEarned = earned.length > 0 ? earned[0] : null;
    const countLabel = earned.length > 0 && latestEarned
      ? this._t("badges.count_label_latest", { earned: earned.length, total: totalBadges, latest: latestEarned.name })
      : this._t("badges.count_label", { earned: earned.length, total: totalBadges });

    const title = this.config.title || (childName ? this._t("badges.title_with_name", { name: childName }) : this._t("badges.default_title"));

    return html`
      <ha-card>
        <div class="badges-head">
          <div class="badges-head-left">
            <div class="child-avatar">
              <ha-icon icon="${childAvatar}"></ha-icon>
            </div>
            <div>
              <div class="badges-title">${title}</div>
              <div class="badges-count">${countLabel}</div>
            </div>
          </div>
          <select class="badges-filter"
            .value=${filter}
            @change=${(e) => { this._filterTier = e.target.value; }}>
            <option value="all">${this._t("badges.all_tiers")}</option>
            <option value="bronze">${this._t("badge.tier_bronze")}</option>
            <option value="silver">${this._t("badge.tier_silver")}</option>
            <option value="gold">${this._t("badge.tier_gold")}</option>
            <option value="platinum">${this._t("badge.tier_platinum")}</option>
          </select>
        </div>

        <div class="badge-grid">
          ${filteredEarned.map(b => this._renderEarned(b))}
          ${filteredLocked.map(b => this._renderLocked(b))}
        </div>
      </ha-card>
    `;
  }

  _renderEarned(b) {
    const justEarned = this._justEarned && String(this._justEarned) === String(b.id);
    return html`
      <div class="badge earned tier-${b.tier} ${justEarned ? 'just-earned' : ''}">
        ${b.point_bonus > 0 ? html`<div class="badge-bonus">+${b.point_bonus}</div>` : ''}
        <div class="badge-icon">
          <ha-icon icon="${b.icon || 'mdi:medal'}"></ha-icon>
        </div>
        <div class="badge-tier">${this._tierLabel(b.tier)}</div>
        <div class="badge-name">${b.name}</div>
        <div class="badge-meta">${this._t("badge.earned_date", { date: this._formatDate(b.earned_at) })}</div>
      </div>
    `;
  }

  _renderLocked(b) {
    // progress: either provided directly, or computed from closest_criterion
    const pct = (b.progress_pct != null) ? b.progress_pct
      : (b.closest_criterion ? Math.min(100, Math.round((b.closest_criterion.current / b.closest_criterion.target) * 100)) : 0);
    const progressLabel = b.progress_label
      || (b.closest_criterion ? `${b.closest_criterion.current} / ${b.closest_criterion.target}` : null);

    return html`
      <div class="badge locked tier-${b.tier}">
        ${b.point_bonus > 0 ? html`<div class="badge-bonus" style="opacity:0.4">+${b.point_bonus}</div>` : ''}
        <div class="badge-icon">
          <ha-icon icon="${b.icon || 'mdi:medal-outline'}"></ha-icon>
        </div>
        <div class="badge-tier">${this._tierLabel(b.tier)}</div>
        <div class="badge-name">${b.name}</div>
        ${progressLabel ? html`
          <div class="badge-progress">
            <div class="badge-progress-fill" style="width:${pct}%"></div>
          </div>
          <div class="badge-progress-label">${progressLabel}</div>
        ` : ''}
      </div>
    `;
  }
}

// Minimal stub editor so HA doesn't error on getConfigElement
class TaskMateBadgesCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }
  setConfig(config) { this.config = config; }
  render() {
    return html`<p style="padding:12px;color:var(--secondary-text-color)">Configure via YAML: set <code>entity</code> to your badges sensor (e.g. <code>sensor.taskmate_badges_mia</code>).</p>`;
  }
}

customElements.define("taskmate-badges-card", TaskMateBadgesCard);
customElements.define("taskmate-badges-card-editor", TaskMateBadgesCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-badges-card",
  name: "TaskMate Badges",
  description: "Achievement badge grid for a single child",
  preview: false,
});

const _tmBadgesVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-badges-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE BADGES CARD %c v" + _tmBadgesVersion + " ",
  "background:#9b59b6;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
