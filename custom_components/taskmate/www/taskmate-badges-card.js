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

const DESIGN_HEADER = "#6c5ce7";

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

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
    this._subscribing = false;
    this._justEarnedTimeout = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this._subscribeEvents();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._unsubscribeEvents?.();
    this._unsubscribeEvents = null;
    if (this._justEarnedTimeout) {
      clearTimeout(this._justEarnedTimeout);
      this._justEarnedTimeout = null;
    }
  }

  _subscribeEvents() {
    if (!this.hass) return;
    if (this._unsubscribeEvents || this._subscribing) return;
    this._subscribing = true;
    this.hass.connection.subscribeEvents((event) => {
      const data = event.data || {};
      if (data.child_id && this.config?.child_id && String(data.child_id) !== String(this.config.child_id)) return;
      if (data.badge_id) {
        this._justEarned = String(data.badge_id);
        this.requestUpdate();
        this._justEarnedTimeout = setTimeout(() => {
          this._justEarned = null;
          this.requestUpdate();
        }, 1800);
      }
    }, "taskmate_badge_earned").then(unsub => {
      this._subscribing = false;
      if (!this.isConnected) {
        unsub();
        return;
      }
      this._unsubscribeEvents = unsub;
    }).catch(() => {
      this._subscribing = false;
    });
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
    const base = css`
      :host {
        display: block;
        --t-bronze:   #e08a3c;
        --t-silver:   #a8b8c8;
        --t-gold:     #ffc107;
        --t-platinum: #4dd9e8;

        --t-bronze-bg:   linear-gradient(135deg, #fdf0e4 0%, #f9dfc2 100%);
        --t-silver-bg:   linear-gradient(135deg, #f0f3f7 0%, #dce4ec 100%);
        --t-gold-bg:     linear-gradient(135deg, #fffde6 0%, #fff3b0 100%);
        --t-platinum-bg: linear-gradient(135deg, #e8fbfd 0%, #c4f0f6 100%);
        --t-locked-bg:   linear-gradient(135deg, #f8f9fa 0%, #eef0f2 100%);
      }

      ha-card { overflow: hidden; }

      /* ── Header ── */
      .badges-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 18px 20px 16px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: rgba(255,255,255,0.25);
        border: 2px solid rgba(255,255,255,0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        --mdc-icon-size: 26px;
        color: white;
      }

      .badges-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #fff;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .badges-count {
        font-size: 0.75rem;
        color: rgba(255,255,255,0.8);
        margin-top: 2px;
      }

      .badges-filter {
        background: rgba(255,255,255,0.2);
        border: 1px solid rgba(255,255,255,0.35);
        color: #fff;
        padding: 6px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        flex-shrink: 0;
        cursor: pointer;
        backdrop-filter: blur(4px);
      }

      .badges-filter option {
        color: var(--primary-text-color, #333);
        background: var(--card-background-color, #fff);
      }

      /* ── Grid ── */
      .badge-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 14px;
        padding: 18px;
      }

      /* ── Tier colour helpers ── */
      .tier-bronze   { --t: var(--t-bronze);   --t-glow: rgba(224,138,60,0.35);  --t-bg: var(--t-bronze-bg); }
      .tier-silver   { --t: var(--t-silver);   --t-glow: rgba(168,184,200,0.35); --t-bg: var(--t-silver-bg); }
      .tier-gold     { --t: var(--t-gold);     --t-glow: rgba(255,193,7,0.40);   --t-bg: var(--t-gold-bg); }
      .tier-platinum { --t: var(--t-platinum);  --t-glow: rgba(77,217,232,0.40);  --t-bg: var(--t-platinum-bg); }

      /* ── Badge tile ── */
      .badge {
        background: var(--t-locked-bg);
        border-radius: 16px;
        padding: 18px 12px 14px;
        text-align: center;
        position: relative;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        border: 2px dashed var(--divider-color, #d0d5db);
      }

      .badge.earned {
        background: var(--t-bg);
        border: 2.5px solid var(--t);
        border-style: solid;
        box-shadow: 0 4px 16px var(--t-glow), 0 1px 3px rgba(0,0,0,0.06);
      }

      .badge.earned:hover {
        transform: translateY(-3px) scale(1.02);
        box-shadow: 0 8px 24px var(--t-glow), 0 2px 6px rgba(0,0,0,0.08);
      }

      .badge.locked {
        opacity: 0.5;
        filter: grayscale(0.3);
      }

      .badge.locked:hover {
        opacity: 0.65;
        transform: scale(1.02);
      }

      .badge.just-earned {
        animation: earn-pop 0.6s cubic-bezier(0.34, 1.56, 0.64, 1), earn-shimmer 1.5s ease-out 0.6s;
      }

      @keyframes earn-pop {
        0%   { transform: scale(0.3) rotate(-8deg); opacity: 0; }
        60%  { transform: scale(1.12) rotate(2deg); opacity: 1; }
        100% { transform: scale(1) rotate(0deg); }
      }

      @keyframes earn-shimmer {
        0%   { box-shadow: 0 0 0 0 var(--t-glow), 0 4px 16px var(--t-glow); }
        50%  { box-shadow: 0 0 0 12px transparent, 0 4px 24px var(--t-glow); }
        100% { box-shadow: 0 4px 16px var(--t-glow), 0 1px 3px rgba(0,0,0,0.06); }
      }

      .badge-icon {
        width: 58px;
        height: 58px;
        margin: 0 auto 10px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        --mdc-icon-size: 30px;
        background: var(--divider-color, #e0e0e0);
        color: var(--secondary-text-color);
        transition: transform 0.2s ease;
      }

      .badge.earned .badge-icon {
        background: var(--t);
        color: #fff;
        box-shadow: 0 3px 10px var(--t-glow);
      }

      .badge.earned:hover .badge-icon {
        transform: scale(1.1) rotate(-5deg);
      }

      .tier-gold.earned .badge-icon,
      .tier-bronze.earned .badge-icon {
        color: #2d2000;
      }

      .badge-tier {
        font-size: 0.6rem;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-weight: 800;
        color: var(--t, var(--secondary-text-color));
        margin-bottom: 4px;
      }

      .badge-name {
        font-size: 0.82rem;
        font-weight: 700;
        color: var(--primary-text-color);
        margin-bottom: 3px;
        line-height: 1.25;
      }

      .badge.locked .badge-name { color: var(--secondary-text-color); }

      .badge-meta {
        font-size: 0.65rem;
        color: var(--secondary-text-color);
        margin-bottom: 6px;
        font-weight: 500;
      }

      .badge.earned .badge-meta {
        color: var(--t);
        font-weight: 600;
      }

      .badge-progress {
        height: 7px;
        background: var(--divider-color, #ddd);
        border-radius: 4px;
        overflow: hidden;
        margin-top: 8px;
      }

      .badge-progress-fill {
        height: 100%;
        background: linear-gradient(90deg, var(--t), color-mix(in srgb, var(--t), white 25%));
        border-radius: 4px;
        transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
      }

      .badge-progress-label {
        font-size: 0.65rem;
        color: var(--secondary-text-color);
        margin-top: 4px;
        font-weight: 600;
      }

      .badge-bonus {
        position: absolute;
        top: -4px;
        right: -4px;
        background: linear-gradient(135deg, var(--t), color-mix(in srgb, var(--t), black 15%));
        color: #fff;
        font-size: 0.65rem;
        font-weight: 800;
        padding: 3px 7px;
        border-radius: 999px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        z-index: 1;
      }

      .tier-gold .badge-bonus,
      .tier-bronze .badge-bonus {
        color: #2d2000;
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

      /* ── Designed styles (playroom / console / cleanpro) ── */
      /* Shared .tmd kit + tokens come from taskmate-design.js styles(). */
      .bd-filter { gap: 6px; flex-wrap: wrap; margin-bottom: 11px; }
      .bd-chip { cursor: pointer; }
      .bd-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(82px, 1fr)); gap: 9px; max-height: 360px; overflow-y: auto; }
      .bd-tile {
        background: var(--tmd-surface-2);
        border-radius: 16px;
        padding: 11px 6px;
        text-align: center;
        position: relative;
      }
      .bd-tile.locked { opacity: 0.55; }
      .bd-bonus {
        position: absolute;
        top: 6px;
        right: 8px;
        font-size: 10px;
        font-weight: 800;
        color: var(--tmd-good);
      }
      .bd-ic {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        margin: 0 auto 6px;
        display: grid;
        place-items: center;
        font-size: 22px;
        --mdc-icon-size: 24px;
      }
      .bd-ic.earned {
        background: color-mix(in srgb, var(--bt, var(--tmd-accent)) 22%, var(--tmd-surface));
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--bt, var(--tmd-accent)) 55%, transparent);
        color: var(--bt, var(--tmd-accent));
      }
      .bd-ic.locked {
        background: var(--tmd-surface);
        box-shadow: inset 0 0 0 2px var(--tmd-border);
        color: var(--tmd-dim);
      }
      .bd-name { font-weight: 800; font-size: 11.5px; }
      .bd-tile.locked .bd-name { color: var(--tmd-dim); }
      .bd-date { font-size: 10px; }
      .bd-prog-label { font-size: 10px; margin-top: 3px; }

      /* Console tile overrides */
      :host([data-tm-design="console"]) .bd-tile { border-radius: 8px; }
      :host([data-tm-design="console"]) .bd-tile.earned {
        box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--bt, var(--tmd-accent)) 50%, transparent),
                    0 0 16px color-mix(in srgb, var(--bt, var(--tmd-accent)) 22%, transparent);
      }
      :host([data-tm-design="console"]) .bd-tile.locked {
        background: #0b1424;
        border: 1px solid var(--tmd-border);
        opacity: 1;
      }
      :host([data-tm-design="console"]) .bd-ic.earned {
        background: transparent;
        box-shadow: inset 0 0 0 1px var(--bt, var(--tmd-accent)),
                    0 0 14px color-mix(in srgb, var(--bt, var(--tmd-accent)) 55%, transparent);
      }
      :host([data-tm-design="console"]) .bd-ic.locked {
        box-shadow: inset 0 0 0 1px var(--tmd-border);
      }
      :host([data-tm-design="console"]) .bd-name { font-weight: 700; font-size: 11px; }

      /* Clean Pro tile overrides */
      :host([data-tm-design="cleanpro"]) .bd-tile {
        background: transparent;
        border: 1px solid var(--tmd-border);
        border-radius: 11px;
      }
      :host([data-tm-design="cleanpro"]) .bd-tile.locked { background: var(--tmd-surface-2); }
      :host([data-tm-design="cleanpro"]) .bd-ic { width: 40px; height: 40px; font-size: 20px; }
      :host([data-tm-design="cleanpro"]) .bd-ic.earned {
        background: color-mix(in srgb, var(--bt, var(--tmd-accent)) 14%, transparent);
        box-shadow: none;
      }
      :host([data-tm-design="cleanpro"]) .bd-ic.locked { box-shadow: none; }
      :host([data-tm-design="cleanpro"]) .bd-name { font-weight: 600; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
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
    return { entity: "sensor.taskmate_overview" };
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
    const isPreview = !attrs.earned && !attrs.available;
    const earned = isPreview
      ? [{ id: "s1", name: "Early Bird", icon: "mdi:weather-sunny", tier: "gold", point_bonus: 10, earned_at: new Date().toISOString() },
         { id: "s2", name: "Streak Star", icon: "mdi:fire", tier: "silver", point_bonus: 5, earned_at: new Date().toISOString() }]
      : (attrs.earned || []);
    const available = isPreview
      ? [{ id: "s3", name: "Helping Hand", icon: "mdi:hand-heart", tier: "bronze", point_bonus: 5, progress_pct: 60, progress_label: "3 / 5" }]
      : (attrs.available || []);
    const childName = isPreview ? "Child" : (attrs.child_name || attrs.name || "");
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

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") {
      return this._renderDesigned(design, {
        title, childName, earned, available, totalBadges,
        filteredEarned, filteredLocked, filter,
      });
    }

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

// Designed-style render methods are added to the prototype below.
TaskMateBadgesCard.prototype._tierTone = function (tier) {
  // Map badge tiers onto shared design tokens (kit defines --tmd-gold).
  switch (tier) {
    case "platinum": return "var(--tmd-accent)";
    case "gold":     return "var(--tmd-gold)";
    case "silver":   return "var(--tmd-dim)";
    case "bronze":   return "var(--tmd-c6)";
    default:         return "var(--tmd-accent)";
  }
};

TaskMateBadgesCard.prototype._designFilters = function (filter) {
  const tiers = ["all", "bronze", "silver", "gold", "platinum"];
  return html`
    <div class="row bd-filter">
      ${tiers.map((t) => html`
        <button class="chip bd-chip ${t === filter ? "soft" : ""}"
          @click="${() => { this._filterTier = t; this.requestUpdate(); }}">
          ${t === "all" ? this._t("badges.all_tiers") : this._tierLabel(t)}
        </button>`)}
    </div>`;
};

TaskMateBadgesCard.prototype._designEarnedTile = function (b) {
  const tone = this._tierTone(b.tier);
  const a = b.icon || "mdi:medal";
  const icon = a.startsWith("mdi:")
    ? html`<ha-icon icon="${a}"></ha-icon>` : a;
  return html`
    <div class="bd-tile earned" style="--bt:${tone}">
      ${b.point_bonus > 0 ? html`<div class="bd-bonus">+${b.point_bonus}</div>` : ""}
      <div class="bd-ic earned" style="--bt:${tone}">${icon}</div>
      <div class="bd-name">${b.name}</div>
      <div class="muted bd-date">${this._formatDate(b.earned_at)}</div>
    </div>`;
};

TaskMateBadgesCard.prototype._designLockedTile = function (b) {
  const tone = this._tierTone(b.tier);
  const pct = (b.progress_pct != null) ? b.progress_pct
    : (b.closest_criterion ? Math.min(100, Math.round((b.closest_criterion.current / b.closest_criterion.target) * 100)) : 0);
  const progressLabel = b.progress_label
    || (b.closest_criterion ? `${b.closest_criterion.current} / ${b.closest_criterion.target}` : null);
  const a = b.icon || "mdi:medal-outline";
  const icon = a.startsWith("mdi:") ? html`<ha-icon icon="${a}"></ha-icon>` : a;
  return html`
    <div class="bd-tile locked" style="--bt:${tone}">
      ${b.point_bonus > 0 ? html`<div class="bd-bonus" style="opacity:0.45">+${b.point_bonus}</div>` : ""}
      <div class="bd-ic locked">${icon}</div>
      <div class="bd-name">${b.name}</div>
      ${progressLabel ? html`
        <div class="bar" style="height:7px;margin-top:6px"><i style="width:${pct}%"></i></div>
        <div class="muted bd-prog-label">${progressLabel}</div>` : ""}
    </div>`;
};

TaskMateBadgesCard.prototype._renderDesigned = function (design, d) {
  const hd = _safeColor(this.config.header_color, DESIGN_HEADER);
  const ic = design === "console" ? "✦" : design === "cleanpro" ? "◈" : "🎖️";
  const sub = d.childName;
  const countPill = this._t("badges.count_label", { earned: d.earned.length, total: d.totalBadges });

  return html`
    <ha-card class="tmd" style="--hd:${hd}">
      <div class="tmd-hd">
        <span class="ic">${ic}</span>
        <span class="tt">${d.title}${sub ? html`<small>${sub}</small>` : ""}</span>
        <span class="pill">${countPill}</span>
      </div>
      <div class="tmd-bd">
        ${this._designFilters(d.filter)}
        ${(d.filteredEarned.length + d.filteredLocked.length) === 0
          ? html`<div class="tmd-empty">${this._t("badges.count_label", { earned: 0, total: d.totalBadges })}</div>`
          : html`<div class="bd-grid">
              ${d.filteredEarned.map((b) => this._designEarnedTile(b))}
              ${d.filteredLocked.map((b) => this._designLockedTile(b))}
            </div>`}
      </div>
    </ha-card>`;
};

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
              : [{ value: 'global', label: 'Use global default' }],
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

customElements.define("taskmate-badges-card", TaskMateBadgesCard);
customElements.define("taskmate-badges-card-editor", TaskMateBadgesCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-badges-card",
  name: "TaskMate Badges",
  description: "Achievement badge grid for a single child",
  preview: true,
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
