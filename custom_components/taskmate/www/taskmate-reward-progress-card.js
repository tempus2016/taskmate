/**
 * TaskMate Reward Progress Card
 * Full-screen motivational display showing a single reward's progress.
 * Designed for wall tablets as a persistent motivation display.
 *
 * Version: 1.0.0
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateRewardProgressCard extends LitElement {
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

  static get styles() {
    const base = css`
      :host { display: block; }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, var(--primary-color));
        color: var(--text-primary-color, #fff);
        gap: 12px;
      }

      .header-content { display: flex; align-items: center; gap: 10px; min-width: 0; }
      .header-icon { --mdc-icon-size: 26px; opacity: 0.9; flex-shrink: 0; }
      .header-title {
        font-size: 1.1rem; font-weight: 600;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }

      .card-content { padding: 20px 18px; }

      /* Reward hero section */
      .reward-hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        padding: 12px 0 20px;
        gap: 10px;
      }

      .reward-icon-wrap {
        width: 90px;
        height: 90px;
        border-radius: 50%;
        background: var(--primary-color);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: var(--ha-card-box-shadow, none);
        animation: hero-float 3s ease-in-out infinite;
      }

      @keyframes hero-float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-6px); }
      }

      .reward-icon-wrap ha-icon { --mdc-icon-size: 52px; color: var(--text-primary-color, #fff); }

      .reward-name {
        font-size: 1.6rem;
        font-weight: 700;
        color: var(--primary-text-color);
        line-height: 1.2;
      }

      .reward-description {
        font-size: 0.9rem;
        color: var(--secondary-text-color);
        max-width: 280px;
      }

      /* Children progress blocks */
      .children-section {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .child-progress-block {
        background: var(--secondary-background-color, #f8f8f8);
        border-radius: 16px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }

      .child-progress-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .child-progress-left {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
      }

      .child-avatar {
        width: 40px;
        height: 40px;
        min-width: 40px;
        border-radius: 50%;
        background: var(--primary-color);
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .child-avatar ha-icon { --mdc-icon-size: 24px; color: var(--text-primary-color, #fff); }

      .child-progress-name {
        font-size: 1rem;
        font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .child-points-label {
        font-size: 0.8rem;
        color: var(--secondary-text-color);
      }

      .child-progress-cost {
        text-align: right;
        flex-shrink: 0;
      }

      .cost-label {
        font-size: 0.75rem;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      .cost-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--primary-color);
        display: flex;
        align-items: center;
        gap: 3px;
        justify-content: flex-end;
      }

      .cost-value ha-icon { --mdc-icon-size: 16px; color: #ca8a04; }

      /* Big animated progress bar */
      .big-progress-wrap {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .big-progress-bar {
        height: 22px;
        background: var(--divider-color, #e0e0e0);
        border-radius: 11px;
        overflow: hidden;
        position: relative;
      }

      .big-progress-fill {
        height: 100%;
        border-radius: 11px;
        transition: width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
        position: relative;
        overflow: hidden;
      }

      .big-progress-fill::after {
        content: '';
        position: absolute;
        top: 0; left: -100%;
        width: 60%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        animation: shimmer 2s infinite;
      }

      @keyframes shimmer {
        0% { left: -100%; }
        100% { left: 200%; }
      }

      .big-progress-fill.affordable {
        background: var(--success-color, #4caf50);
      }

      .big-progress-fill.close {
        background: var(--warning-color, #ff9800);
      }

      .big-progress-fill.far {
        background: var(--primary-color);
      }

      .big-progress-fill.complete {
        background: var(--success-color, #4caf50);
      }

      .progress-stat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.82rem;
      }

      .progress-have {
        font-weight: 600;
        color: var(--primary-text-color);
      }

      .progress-need {
        color: var(--secondary-text-color);
      }

      .progress-pct {
        font-weight: 700;
        font-size: 0.95rem;
      }

      .progress-pct.affordable { color: var(--success-color, #4caf50); }
      .progress-pct.close { color: var(--warning-color, #ff9800); }
      .progress-pct.far { color: var(--primary-color); }

      /* Can afford badge */
      .can-afford-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: color-mix(in srgb, var(--success-color, #4caf50) 15%, transparent);
        color: var(--success-color, #4caf50);
        border-radius: 20px;
        padding: 5px 12px;
        font-size: 0.85rem;
        font-weight: 700;
        animation: pulse-green 2s ease-in-out infinite;
        align-self: center;
      }

      .can-afford-badge ha-icon { --mdc-icon-size: 16px; }

      @keyframes pulse-green {
        0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--success-color, #4caf50) 30%, transparent); }
        50% { box-shadow: 0 0 0 6px color-mix(in srgb, var(--success-color, #4caf50) 0%, transparent); }
      }

      /* Jackpot section */
      .jackpot-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #ca8a04;
        color: var(--text-primary-color, #fff);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        align-self: flex-start;
      }

      .jackpot-badge ha-icon { --mdc-icon-size: 14px; }

      /* Availability badges (low stock / sold out / expiring / expired) */
      .availability-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 20px;
        padding: 3px 10px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        align-self: flex-start;
      }
      .availability-badge.badge-sold-out {
        background: color-mix(in srgb, var(--secondary-text-color, #757575) 20%, transparent);
        color: var(--secondary-text-color, #757575);
      }
      .availability-badge.badge-expired {
        background: color-mix(in srgb, var(--secondary-text-color, #757575) 20%, transparent);
        color: var(--secondary-text-color, #757575);
      }
      .availability-badge.badge-low-stock {
        background: color-mix(in srgb, var(--error-color, #db4437) 18%, transparent);
        color: var(--error-color, #db4437);
      }
      .availability-badge.badge-expiring-soon {
        background: color-mix(in srgb, var(--warning-color, #ff9800) 20%, transparent);
        color: var(--warning-color, #ff9800);
      }

      .jackpot-pool {
        display: flex;
        flex-direction: column;
        gap: 8px;
        background: color-mix(in srgb, #ca8a04 8%, transparent);
        border: 1px solid color-mix(in srgb, #ca8a04 25%, transparent);
        border-radius: 12px;
        padding: 12px;
      }

      .jackpot-pool-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      .jackpot-contributors {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .jackpot-contributor {
        display: flex;
        align-items: center;
        gap: 6px;
        background: var(--card-background-color, #fff);
        border-radius: 20px;
        padding: 4px 10px 4px 6px;
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--primary-text-color);
      }

      .jackpot-contributor .mini-avatar {
        width: 22px; height: 22px;
        border-radius: 50%;
        background: #ca8a04;
        display: flex; align-items: center; justify-content: center;
      }

      .jackpot-contributor .mini-avatar ha-icon { --mdc-icon-size: 13px; color: var(--text-primary-color, #fff); }

      /* Error / empty */
      .error-state, .empty-state {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 40px 20px;
        color: var(--secondary-text-color); text-align: center;
      }
      .error-state { color: var(--error-color, #db4437); }
      .error-state ha-icon, .empty-state ha-icon { --mdc-icon-size: 48px; margin-bottom: 12px; opacity: 0.5; }

      /* Responsive */
      @media (max-width: 480px) {
        .card-content { padding: 14px 12px; }
        .reward-icon-wrap { width: 70px; height: 70px; }
        .reward-icon-wrap ha-icon { --mdc-icon-size: 40px; }
        .reward-name { font-size: 1.3rem; }
        .big-progress-bar { height: 18px; border-radius: 9px; }
        .child-progress-block { padding: 12px; }
      }

      /* ── Designed (playroom / console / cleanpro) — shared .tmd kit comes
         from taskmate-design.js styles(); only card-specific layout below. ── */
      .rp-wrap { text-align: center; }
      .rp-hero-emoji { font-size: 60px; line-height: 1; margin: 4px 0;
                       filter: drop-shadow(0 6px 10px rgba(0,0,0,.15)); }
      .rp-hero-icon { width: 84px; height: 84px; border-radius: 50%; margin: 4px auto;
                      display: grid; place-items: center; background: var(--tmd-accent);
                      box-shadow: var(--tmd-shadow); }
      .rp-hero-icon ha-icon { --mdc-icon-size: 46px; color: #fff; }
      :host([data-tm-design="console"]) .rp-hero-emoji {
        filter: drop-shadow(0 0 18px color-mix(in srgb, var(--tmd-accent) 70%, transparent)); }
      .rp-name { font-size: 24px; color: var(--tmd-accent); }
      .rp-desc { font-size: 13px; margin-top: 4px; max-width: 280px; margin-left: auto; margin-right: auto; }
      .rp-jackpot { margin-top: 8px; background: var(--tmd-gold); color: #3a2e26;
                    border-color: transparent; font-weight: 800; text-transform: uppercase;
                    letter-spacing: 0.04em; font-size: 11px; }
      .rp-avail { margin-top: 8px; font-weight: 800; text-transform: uppercase;
                  letter-spacing: 0.04em; font-size: 11px; border-color: transparent; }
      .rp-avail-dim { background: color-mix(in srgb, var(--tmd-dim) 20%, transparent); color: var(--tmd-dim); }
      .rp-avail-bad { background: color-mix(in srgb, var(--tmd-bad) 18%, transparent); color: var(--tmd-bad); }
      .rp-avail-warn { background: color-mix(in srgb, var(--tmd-warn) 20%, transparent); color: var(--tmd-warn); }
      .rp-cost { margin-top: 8px; background: var(--tmd-gold); color: #3a2e26;
                 border-color: transparent; font-weight: 800; }
      .rp-bar { height: 24px; margin-top: 16px; }
      .rp-pct { color: var(--tmd-accent); }
      .rp-pct-c { font-size: 38px; margin-top: 12px; }
      .rp-need-c { font-weight: 800; font-size: 15px; margin-top: 2px; }
      .rp-stat { justify-content: space-between; margin-top: 10px; }
      .rp-stat .rp-pct { font-size: 34px; }
      .rp-stat-r { text-align: right; }
      .rp-frac { font-size: 18px; }
      .rp-need { font-size: 12px; }
      .rp-kids { grid-template-columns: repeat(var(--n, 3), 1fr); gap: 9px; margin-top: 16px; }
      .rp-kid { background: var(--tmd-surface-2); border: 1px solid var(--tmd-border);
                border-radius: var(--tmd-radius-sm); padding: 10px; display: flex;
                flex-direction: column; align-items: center; gap: 4px; }
      .rp-kid .av { margin: 0 auto 2px; }
      .rp-kid-pts { font-size: 20px; color: var(--tmd-accent); }
      .rp-kid-pts span { font-size: 12px; margin-left: 1px; }
      .rp-kid-name { font-size: 12px; font-weight: 800; }
      .rp-kid-bar { width: 100%; height: 7px; margin-top: 3px; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) throw new Error(this._t('reward_progress.error.entity_required'));
    this.config = {
      title: null,
      reward_id: null,
      child_id: null,
    ...config,
    };
  }

  getCardSize() { return 5; }
  static getConfigElement() { return document.createElement("taskmate-reward-progress-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Reward Goal" };
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") return this._renderDesigned(design);

    const entity = this.hass.states[this.config.entity];
    if (!entity) return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    if (entity.state === "unavailable" || entity.state === "unknown") return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('reward_progress.unavailable')}</div></div></ha-card>`;

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const rewards = attrs.rewards || [];
    const children = attrs.children || [];
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t("common.points");

    // Pick reward
    let reward = this.config.reward_id
      ? rewards.find(r => r.id === this.config.reward_id)
      : rewards[0];

    if (!reward) return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:gift-outline"></ha-icon><div>${this._t('reward_progress.no_rewards')}</div></div></ha-card>`;

    // Which children to show
    let showChildren = children;
    if (this.config.child_id) showChildren = children.filter(c => c.id === this.config.child_id);
    if (reward.assigned_to?.length) showChildren = showChildren.filter(c => reward.assigned_to.includes(c.id));
    if (!showChildren.length) showChildren = children;

    const isJackpot = reward.is_jackpot;
    const isSoldOut = reward.is_sold_out === true;
    const isExpired = reward.is_expired === true;
    const daysUntilExpiry = (typeof reward.days_until_expiry === 'number')
      ? reward.days_until_expiry
      : null;
    let availabilityLabel = '';
    let availabilityClass = '';
    if (isExpired) {
      availabilityLabel = this._t('rewards.expired');
      availabilityClass = 'badge-expired';
    } else if (isSoldOut) {
      availabilityLabel = this._t('rewards.sold_out');
      availabilityClass = 'badge-sold-out';
    } else if (typeof reward.quantity === 'number' && reward.quantity > 0 && reward.quantity <= 3) {
      availabilityLabel = this._t('rewards.only_n_left', { count: reward.quantity });
      availabilityClass = 'badge-low-stock';
    } else if (typeof daysUntilExpiry === 'number' && daysUntilExpiry >= 0 && daysUntilExpiry <= 7) {
      availabilityLabel = daysUntilExpiry === 0
        ? this._t('rewards.expires_today')
        : (daysUntilExpiry === 1
            ? this._t('rewards.expires_in_days', { count: daysUntilExpiry })
            : this._t('rewards.expires_in_days_plural', { count: daysUntilExpiry }));
      availabilityClass = 'badge-expiring-soon';
    }

    const headerColor = _safeColor(this.config.header_color, '');
    const headerStyle = headerColor
      ? `--taskmate-header-bg: ${headerColor};`
      : '';

    return html`
      <ha-card>
        ${headerStyle ? html`<style>:host { ${headerStyle} }</style>` : ''}
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:trophy-outline"></ha-icon>
            <span class="header-title">${this.config.title || this._t('reward_progress.default_title')}</span>
          </div>
        </div>
        <div class="card-content">
          <div class="reward-hero">
            <div class="reward-icon-wrap">
              <ha-icon icon="${reward.icon || 'mdi:gift'}"></ha-icon>
            </div>
            <div class="reward-name">${reward.name}</div>
            ${reward.description ? html`<div class="reward-description">${reward.description}</div>` : ''}
            ${availabilityLabel ? html`
              <div class="availability-badge ${availabilityClass}">${availabilityLabel}</div>
            ` : ''}
            ${isJackpot ? html`
              <div class="jackpot-badge">
                <ha-icon icon="mdi:star-shooting"></ha-icon>
                ${this._t('reward_progress.jackpot_reward')}
              </div>
            ` : ''}
          </div>

          ${isJackpot
            ? this._renderJackpot(reward, showChildren, pointsIcon, pointsName)
            : html`
              <div class="children-section">
                ${showChildren.map(child => this._renderChildProgress(child, reward, pointsIcon, pointsName))}
              </div>
            `}
        </div>
      </ha-card>
    `;
  }

  _renderChildProgress(child, reward, pointsIcon, pointsName) {
    const cost = reward.calculated_costs?.[child.id] ?? reward.cost;
    const have = child.points || 0;
    const pct = Math.min(100, Math.round((have / cost) * 100));
    const canAfford = have >= cost;
    const close = pct >= 70;
    const cls = canAfford ? "complete" : close ? "close" : "far";
    const pctCls = canAfford ? "affordable" : close ? "close" : "far";

    return html`
      <div class="child-progress-block">
        <div class="child-progress-header">
          <div class="child-progress-left">
            <div class="child-avatar">
              <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
            </div>
            <div>
              <div class="child-progress-name">${child.name}</div>
              <div class="child-points-label">${have} ${pointsName}</div>
            </div>
          </div>
          <div class="child-progress-cost">
            <div class="cost-label">${this._t('common.goal')}</div>
            <div class="cost-value">
              <ha-icon icon="${pointsIcon}"></ha-icon>
              ${cost}
            </div>
          </div>
        </div>

        <div class="big-progress-wrap">
          <div class="big-progress-bar">
            <div class="big-progress-fill ${cls}" style="width: ${pct}%"></div>
          </div>
          <div class="progress-stat-row">
            <span class="progress-have">${have} / ${cost} ${pointsName}</span>
            ${canAfford
              ? html`<span class="progress-need">${this._t('reward_progress.ready_to_claim_emoji')}</span>`
              : html`<span class="progress-need">${this._t('reward_progress.more_needed', { amount: cost - have })}</span>`}
            <span class="progress-pct ${pctCls}">${pct}%</span>
          </div>
        </div>

        ${canAfford ? html`
          <div class="can-afford-badge">
            <ha-icon icon="mdi:check-circle"></ha-icon>
            ${this._t('reward_progress.ready_to_claim')}
          </div>
        ` : ''}
      </div>
    `;
  }

  _renderJackpot(reward, children, pointsIcon, pointsName) {
    const cost = reward.calculated_costs
      ? Object.values(reward.calculated_costs)[0] ?? reward.cost
      : reward.cost;

    const totalHave = children.reduce((s, c) => s + (c.points || 0), 0);
    const pct = Math.min(100, Math.round((totalHave / cost) * 100));
    const canAfford = totalHave >= cost;
    const close = pct >= 70;
    const cls = canAfford ? "complete" : close ? "close" : "far";
    const pctCls = canAfford ? "affordable" : close ? "close" : "far";

    return html`
      <div class="children-section">
        <div class="child-progress-block">
          <div class="jackpot-pool">
            <div class="jackpot-pool-title">${this._t('reward_progress.combined_points_pool')}</div>
            <div class="jackpot-contributors">
              ${children.map(child => html`
                <div class="jackpot-contributor">
                  <div class="mini-avatar">
                    <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
                  </div>
                  <span>${child.name}: ${child.points}</span>
                </div>
              `)}
            </div>
          </div>

          <div class="child-progress-header" style="margin-top:4px">
            <div>
              <div class="child-progress-name">${this._t('reward_progress.total_pool')}</div>
              <div class="child-points-label">${totalHave} ${pointsName} ${this._t('reward_progress.combined')}</div>
            </div>
            <div class="child-progress-cost">
              <div class="cost-label">${this._t('common.goal')}</div>
              <div class="cost-value">
                <ha-icon icon="${pointsIcon}"></ha-icon>
                ${cost}
              </div>
            </div>
          </div>

          <div class="big-progress-wrap">
            <div class="big-progress-bar">
              <div class="big-progress-fill ${cls}" style="width: ${pct}%"></div>
            </div>
            <div class="progress-stat-row">
              <span class="progress-have">${totalHave} / ${cost} ${pointsName}</span>
              ${canAfford
                ? html`<span class="progress-need">${this._t('reward_progress.ready')}</span>`
                : html`<span class="progress-need">${this._t('reward_progress.more_needed', { amount: cost - totalHave })}</span>`}
              <span class="progress-pct ${pctCls}">${pct}%</span>
            </div>
          </div>

          ${canAfford ? html`
            <div class="can-afford-badge">
              <ha-icon icon="mdi:check-circle"></ha-icon>
              ${this._t('reward_progress.ready_to_claim')}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns (§card-reward-progress). Wall display
     for ONE reward, FIXED cost only.
  ══════════════════════════════════════════════════════════════════════ */

  _designTone(i) { return `var(--tmd-c${(i % 6) + 1})`; }

  _av(child, tone, size) {
    const a = (child && child.avatar) || "";
    const inner = a.startsWith("mdi:")
      ? html`<ha-icon icon="${a}"></ha-icon>`
      : a
        ? html`<img src="${a}" alt="${child.name}">`
        : ((child && child.name) || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
    return html`<div class="av" style="--av:${size}px;--ac:${tone}">${inner}</div>`;
  }

  _renderDesigned(design) {
    const hd = _safeColor(this.config.header_color, '#00897b');
    const wrap = (body, icon) => html`
      <ha-card class="tmd" style="--hd:${hd}">
        <div class="tmd-hd">
          <span class="ic">🎯</span>
          <span class="tt">${this.config.title || this._t('reward_progress.default_title')}<small>${this._t('common.goal')}</small></span>
        </div>
        <div class="tmd-bd">${body}</div>
      </ha-card>`;

    const entity = this.hass.states[this.config.entity];
    if (!entity) return wrap(html`<div class="tmd-empty">${this._t('common.entity_not_found', { entity: this.config.entity })}</div>`);
    if (entity.state === "unavailable" || entity.state === "unknown")
      return wrap(html`<div class="tmd-empty">${this._t('reward_progress.unavailable')}</div>`);

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const rewards = attrs.rewards || [];
    const children = attrs.children || [];
    const pointsName = attrs.points_name || this._t("common.points");

    let reward = this.config.reward_id
      ? rewards.find(r => r.id === this.config.reward_id)
      : rewards[0];
    if (!reward) return wrap(html`<div class="tmd-empty">${this._t('reward_progress.no_rewards')}</div>`);

    let showChildren = children;
    if (this.config.child_id) showChildren = children.filter(c => c.id === this.config.child_id);
    if (reward.assigned_to?.length) showChildren = showChildren.filter(c => reward.assigned_to.includes(c.id));
    if (!showChildren.length) showChildren = children;

    const isJackpot = reward.is_jackpot;
    let cost, have, contributors;
    if (isJackpot) {
      cost = reward.calculated_costs ? (Object.values(reward.calculated_costs)[0] ?? reward.cost) : reward.cost;
      have = showChildren.reduce((s, c) => s + (c.points || 0), 0);
      contributors = showChildren.map((c, i) => ({ child: c, points: c.points || 0, tone: this._designTone(i) }));
    } else {
      const ref = showChildren[0];
      cost = (ref && reward.calculated_costs?.[ref.id]) ?? reward.cost;
      contributors = showChildren.map((c, i) => ({
        child: c, points: c.points || 0, tone: this._designTone(i),
        cost: reward.calculated_costs?.[c.id] ?? reward.cost,
      }));
      have = contributors.length === 1 ? contributors[0].points
        : contributors.reduce((s, c) => s + c.points, 0);
      if (contributors.length === 1) cost = contributors[0].cost;
    }
    const pct = cost > 0 ? Math.min(100, Math.round((have / cost) * 100)) : 0;
    const remaining = Math.max(0, cost - have);

    // Availability badge — same precedence as the classic render.
    const isSoldOut = reward.is_sold_out === true;
    const isExpired = reward.is_expired === true;
    const daysUntilExpiry = (typeof reward.days_until_expiry === 'number') ? reward.days_until_expiry : null;
    let availabilityLabel = '';
    let availabilityTone = '';
    if (isExpired) {
      availabilityLabel = this._t('rewards.expired');
      availabilityTone = 'dim';
    } else if (isSoldOut) {
      availabilityLabel = this._t('rewards.sold_out');
      availabilityTone = 'dim';
    } else if (typeof reward.quantity === 'number' && reward.quantity > 0 && reward.quantity <= 3) {
      availabilityLabel = this._t('rewards.only_n_left', { count: reward.quantity });
      availabilityTone = 'bad';
    } else if (typeof daysUntilExpiry === 'number' && daysUntilExpiry >= 0 && daysUntilExpiry <= 7) {
      availabilityLabel = daysUntilExpiry === 0
        ? this._t('rewards.expires_today')
        : (daysUntilExpiry === 1
            ? this._t('rewards.expires_in_days', { count: daysUntilExpiry })
            : this._t('rewards.expires_in_days_plural', { count: daysUntilExpiry }));
      availabilityTone = 'warn';
    }

    return wrap(html`${this._designBody(reward, design, cost, have, pct, remaining, contributors, pointsName, availabilityLabel, availabilityTone)}`);
  }

  _designBody(reward, design, cost, have, pct, remaining, contributors, pointsName, availabilityLabel, availabilityTone) {
    const icon = reward.icon || "mdi:gift";
    const isIcon = typeof icon === "string" && icon.startsWith("mdi:");
    const hero = isIcon
      ? html`<div class="rp-hero-icon"><ha-icon icon="${icon}"></ha-icon></div>`
      : html`<div class="rp-hero-emoji">${icon}</div>`;

    return html`
      <div class="rp-wrap">
        ${hero}
        <div class="big rp-name">${reward.name}</div>
        ${reward.description ? html`<div class="muted rp-desc">${reward.description}</div>` : ''}
        ${reward.is_jackpot ? html`<div class="chip rp-jackpot">🎰 ${this._t('reward_progress.jackpot_reward')}</div>` : ''}
        ${availabilityLabel ? html`<div class="chip rp-avail rp-avail-${availabilityTone}">${availabilityLabel}</div>` : ''}
        <div class="chip rp-cost">⭐ ${cost} ${pointsName}</div>
        <div class="bar rp-bar"><i style="width:${pct}%;${pct >= 100 ? 'background:var(--tmd-good)' : ''}"></i></div>
        ${design === "cleanpro"
          ? html`<div class="row rp-stat">
              <div class="big rp-pct">${pct}%</div>
              <div class="rp-stat-r">
                <div class="num rp-frac">${have} / ${cost}</div>
                <div class="muted rp-need">${this._t('reward_progress.more_needed', { amount: remaining })}</div>
              </div>
            </div>`
          : html`
            <div class="big rp-pct rp-pct-c">${pct}%</div>
            <div class="rp-need rp-need-c">${remaining > 0
              ? this._t('reward_progress.more_needed', { amount: remaining })
              : this._t('reward_progress.ready_to_claim')}</div>`}

        <div class="grid rp-kids" style="--n:${contributors.length}">
          ${contributors.map((c) => html`
            <div class="rp-kid" style="--ac:${c.tone}">
              ${this._av(c.child, c.tone, 36)}
              <div class="big rp-kid-pts">${c.points}<span>⭐</span></div>
              <div class="rp-kid-name">${c.child.name}</div>
              ${design === "cleanpro" && !reward.is_jackpot && c.cost > 0
                ? html`<div class="bar rp-kid-bar"><i style="width:${Math.min(100, Math.round((c.points / c.cost) * 100))}%;background:${c.tone}"></i></div>` : ''}
            </div>`)}
        </div>
      </div>`;
  }
}

class TaskMateRewardProgressCardEditor extends LitElement {
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
      .colour-field { display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; border: 1px solid var(--outline-color, var(--divider-color, #e0e0e0)); border-radius: 4px; background: var(--mdc-text-field-fill-color, var(--card-background-color)); }
      .colour-field-label { font-size: 0.82rem; color: var(--primary-color); font-weight: 500; }
      .colour-field-body { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
      .colour-swatch-wrapper { position: relative; width: 36px; height: 36px; border-radius: 50%; overflow: hidden; cursor: pointer; border: 2px solid var(--divider-color, #e0e0e0); flex-shrink: 0; }
      .colour-swatch-wrapper input[type="color"] { position: absolute; inset: 0; opacity: 0; cursor: pointer; border: 0; padding: 0; }
      .colour-swatch-preview { position: absolute; inset: 0; pointer-events: none; }
      .colour-hex { font-family: var(--code-font-family, monospace); font-size: 0.85rem; color: var(--secondary-text-color); min-width: 70px; }
      .colour-presets { display: flex; gap: 6px; flex-wrap: wrap; }
      .preset-swatch { width: 22px; height: 22px; border-radius: 50%; cursor: pointer; border: 2px solid var(--divider-color, #e0e0e0); transition: transform 0.1s; padding: 0; }
      .preset-swatch:hover { transform: scale(1.15); }
      .preset-swatch.active { border-color: var(--primary-text-color); box-shadow: 0 0 0 2px var(--primary-color); }
      .colour-reset { font-size: 0.78rem; color: var(--secondary-text-color); background: none; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; padding: 4px 10px; cursor: pointer; margin-left: auto; }
      .colour-helper { color: var(--secondary-text-color); font-size: 0.82rem; line-height: 1.3; }
    `;
  }

  setConfig(config) { this.config = config; }

  _buildSchema() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity)) || (this.config?.entity ? this.hass?.states?.[this.config.entity]?.attributes : null) || {};
    const rewards = attrs.rewards || [];
    const children = attrs.children || [];
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'reward_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('reward_progress.editor.first_available') },
              ...rewards.map((r) => ({ value: r.id, label: r.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('reward_progress.editor.child_filter_all') },
              ...children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
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
      entity: this._t('common.editor.overview_entity'),
      title: this._t('common.editor.card_title'),
      reward_id: this._t('reward_progress.editor.reward_to_display'),
      child_id: this._t('common.editor.filter_by_child'),
      card_design: this._t('common.design.field_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      reward_id: this._t('reward_progress.editor.reward_helper'),
      child_id: this._t('reward_progress.editor.child_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      reward_id: this.config.reward_id || '',
      child_id: this.config.child_id || '',
      card_design: this.config.card_design || 'global',
    };
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._buildSchema()}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}
      ></ha-form>
      ${this._renderColourPicker('header_color', '')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = ['#7d3c98', '#e67e22', '#27ae60', '#3498db', '#f1c40f', '#e74c3c', '#34495e'];
    const isActive = (c) => current && c.toLowerCase() === current.toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${this._t('common.editor.header_colour')}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current || '#7d3c98'}
              @input=${(e) => this._update(key, e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current || '#7d3c98'}"></span>
          </label>
          <span class="colour-hex">${current || this._t('common.default')}</span>
          <div class="colour-presets">
            ${presets.map((p) => html`
              <button class="preset-swatch ${isActive(p) ? 'active' : ''}"
                style="background:${p}"
                title=${p}
                @click=${(e) => { e.preventDefault(); this._update(key, p); }}
              ></button>
            `)}
          </div>
          <button class="colour-reset"
            @click=${(e) => { e.preventDefault(); this._update(key, ''); }}
          >${this._t('common.reset')}</button>
        </div>
        <div class="colour-helper">${this._t('common.editor.header_colour_helper')}</div>
      </div>
    `;
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === '' || value === null || value === undefined) delete newConfig[key];
      else if (key === 'card_design' && value === 'global') delete newConfig[key];
      else newConfig[key] = value;
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _update(key, value) {
    const cfg = { ...this.config, [key]: value };
    if (!value) delete cfg[key];
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: cfg }, bubbles: true, composed: true }));
  }
}

customElements.define("taskmate-reward-progress-card", TaskMateRewardProgressCard);
customElements.define("taskmate-reward-progress-card-editor", TaskMateRewardProgressCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-reward-progress-card",
  name: "TaskMate Reward Progress",
  description: "Full-screen motivational reward progress display",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-reward-progress-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE REWARD PROGRESS CARD %c v" + _tmVersion + " ",
  "background:#03a9f4;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
