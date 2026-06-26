/**
 * TaskMate Activity Feed Card
 * Scrollable timeline of recent events — completions, approvals, points, rewards.
 *
 * Version: 1.2.0
 * Last Updated: 2026-06-21
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateActivityCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _filter: { type: String, state: true },
      _confirm: { type: Object, state: true },
      _loading: { type: Object, state: true },
    };
  }

  constructor() {
    super();
    this._filter = "all";
    this._confirm = null;
    this._loading = {};
  }

  // Reason prefixes for *derived* (automatic) transactions, which can't be
  // undone in isolation — mirrors the backend deny-list in coord_points.py.
  // Everything else (penalty, bonus, gift, manual add/remove) is reversible.
  static get _UNDO_DENY_PREFIXES() {
    return [
      "Weekend bonus", "Streak milestone bonus", "Perfect week bonus",
      "Allocated to pool:", "Pool refund", "Points decay",
      "Savings interest", "Badge",
    ];
  }

  _txnReversible(reason) {
    const r = reason || "";
    return !TaskMateActivityCard._UNDO_DENY_PREFIXES.some(p => r.startsWith(p));
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

  // Transaction reasons are stored in English in the DB (e.g. "Penalty: Messy room").
  // Map known prefixes to translation keys so they render in the user's language.
  _translateReason(reason) {
    if (!reason) return reason;
    const prefixMap = [
      ['Allocated to pool:', 'activity.reason_allocated_to_pool'],
      ['Pool refund (reward expired):', 'activity.reason_pool_refund_expired'],
      ['Pool refund (reward sold out):', 'activity.reason_pool_refund_sold_out'],
      ['Pool refund (reward cost reduced):', 'activity.reason_pool_refund_cost_reduced'],
      ['Pool refund (reward deleted):', 'activity.reason_pool_refund_deleted'],
      ['Penalty:', 'activity.reason_penalty'],
      ['Bonus:', 'activity.reason_bonus'],
    ];
    for (const [prefix, key] of prefixMap) {
      if (reason.startsWith(prefix)) {
        const name = reason.slice(prefix.length).trim();
        return this._t(key, { name });
      }
    }
    if (reason.startsWith('Perfect week bonus!')) {
      return this._t('activity.reason_perfect_week');
    }
    const weekendMatch = reason.match(/^Weekend bonus \(×(\d+)\)$/);
    if (weekendMatch) {
      return this._t('activity.reason_weekend_bonus', { multiplier: weekendMatch[1] });
    }
    const streakMatch = reason.match(/^Streak milestone bonus \((\d+) day streak!\)$/);
    if (streakMatch) {
      return this._t('activity.reason_streak_milestone', { days: streakMatch[1] });
    }
    return reason;
  }

  static get styles() {
    const base = css`
      :host {
        display: block;
        --act-purple: #9b59b6;
        --act-green: #2ecc71;
        --act-orange: #e67e22;
        --act-blue: #3498db;
        --act-red: #e74c3c;
        --act-gold: #f1c40f;

        --tm-stripe-approved: #16a34a;
        --tm-stripe-pending:  #f59e0b;
        --tm-stripe-rejected: #ef4444;
        --tm-stripe-penalty:  #ef4444;
        --tm-stripe-reward:   #6d3df0;
        --tm-stripe-bonus:    #16a34a;
        --tm-stripe-neutral:  var(--divider-color, #e0e0e0);
      }

      ha-card { overflow: hidden; }

      /* ── Coloured header banner ─────────────────────────── */
      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #2471a3);
        color: #ffffff;
      }
      .header-content { display: flex; align-items: center; gap: 10px; min-width: 0; }
      .header-icon-chip {
        width: 28px; height: 28px;
        border-radius: 8px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 255, 255, 0.18);
        color: #ffffff;
        flex-shrink: 0;
      }
      .header-icon-chip ha-icon { --mdc-icon-size: 18px; }
      .header-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #ffffff;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .header-meta {
        font-size: 0.78rem;
        color: rgba(255, 255, 255, 0.85);
        margin-left: 2px;
        white-space: nowrap;
      }

      /* ── Filter chips ──────────────────────────────────── */
      .filter-bar {
        display: flex;
        gap: 6px;
        padding: 8px 12px;
        background: var(--card-background-color, #fff);
        border-bottom: 1px solid var(--divider-color, #ececf2);
        overflow-x: auto;
        scrollbar-width: none;
      }
      .filter-bar::-webkit-scrollbar { display: none; }
      .filter-chip {
        flex: 0 0 auto;
        font: inherit;
        font-size: 0.74rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid var(--divider-color, #ececf2);
        background: var(--secondary-background-color, transparent);
        color: var(--secondary-text-color);
        cursor: pointer;
        transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        white-space: nowrap;
      }
      .filter-chip:hover {
        background: var(--secondary-background-color, rgba(0,0,0,0.03));
        color: var(--primary-text-color);
      }
      .filter-chip.active {
        background: var(--primary-text-color);
        color: var(--card-background-color, #fff);
        border-color: var(--primary-text-color);
      }
      .filter-chip ha-icon { --mdc-icon-size: 14px; }

      /* ── Feed container ────────────────────────────────── */
      .feed-container {
        max-height: 350px;
        overflow-y: auto;
        padding: 0;
        background: var(--card-background-color, #fff);
      }

      /* Sticky date label */
      .date-label {
        position: sticky;
        top: 0;
        z-index: 2;
        font-size: 0.7rem;
        font-weight: 700;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 9px 14px 7px;
        background: var(--secondary-background-color, #f6f4fb);
        border-bottom: 1px solid var(--divider-color, #ececf2);
        border-top: 1px solid var(--divider-color, #ececf2);
      }
      .date-label:first-child { border-top: 0; }
      .date-label .date-suffix {
        text-transform: none;
        letter-spacing: 0.2px;
        font-weight: 500;
        opacity: 0.75;
        margin-left: 4px;
      }

      /* ── Activity item ─────────────────────────────────── */
      .activity-item {
        display: flex;
        align-items: stretch;
        gap: 0;
        border-bottom: 1px solid var(--divider-color, #f0f0f0);
        position: relative;
        background: var(--card-background-color, #fff);
      }
      .activity-item:last-child { border-bottom: none; }

      .event-stripe {
        width: 4px;
        flex-shrink: 0;
        background: var(--tm-stripe-neutral);
      }
      .activity-item.t-approved   .event-stripe { background: var(--tm-stripe-approved); }
      .activity-item.t-pending    .event-stripe { background: var(--tm-stripe-pending); }
      .activity-item.t-rejected   .event-stripe { background: var(--tm-stripe-rejected); }
      .activity-item.t-penalty    .event-stripe { background: var(--tm-stripe-penalty); }
      .activity-item.t-reward     .event-stripe { background: var(--tm-stripe-reward); }
      .activity-item.t-bonus      .event-stripe { background: var(--tm-stripe-bonus); }

      .activity-row {
        flex: 1;
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
      }

      .activity-icon {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        font-weight: 700;
      }
      .activity-icon ha-icon { --mdc-icon-size: 16px; }

      .activity-icon.t-approved {
        background: rgba(22,163,74,0.13);
        color: #16a34a;
      }
      .activity-icon.t-pending {
        background: rgba(245,158,11,0.15);
        color: #c2740a;
      }
      .activity-icon.t-rejected {
        background: rgba(239,68,68,0.13);
        color: #dc2626;
      }
      .activity-icon.t-penalty {
        background: rgba(239,68,68,0.13);
        color: #dc2626;
      }
      .activity-icon.t-reward {
        background: rgba(109,61,240,0.13);
        color: #6d3df0;
      }
      .activity-icon.t-bonus {
        background: rgba(22,163,74,0.13);
        color: #16a34a;
      }

      .activity-body { flex: 1; min-width: 0; }

      .activity-title {
        font-size: 0.88rem;
        line-height: 1.3;
        color: var(--primary-text-color);
      }
      .activity-title strong {
        font-weight: 700;
        color: var(--primary-text-color);
      }
      .activity-title .reason {
        color: var(--secondary-text-color);
        font-style: normal;
      }

      .activity-meta {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-top: 2px;
        font-size: 0.72rem;
        color: var(--secondary-text-color);
        flex-wrap: wrap;
      }
      .activity-time { color: var(--secondary-text-color); }
      .activity-ago::before {
        content: "·";
        margin-right: 4px;
        opacity: 0.6;
      }

      /* Status pill — kept only for non-default states (pending, rejected). */
      .activity-status {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.66rem;
        font-weight: 700;
        padding: 1px 7px;
        border-radius: 999px;
        text-transform: uppercase;
        letter-spacing: 0.4px;
      }
      .activity-status.pending {
        background: rgba(245,158,11,0.16);
        color: #b45309;
      }
      .activity-status.rejected {
        background: rgba(239,68,68,0.14);
        color: #b91c1c;
      }

      /* Right-aligned signed points pill */
      .points-pill {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.95rem;
        font-weight: 800;
        line-height: 1;
        white-space: nowrap;
        flex-shrink: 0;
        color: var(--primary-text-color);
      }
      .points-pill ha-icon { --mdc-icon-size: 14px; opacity: 0.9; }
      .points-pill.gain    { color: #16a34a; }
      .points-pill.spend   { color: #6d3df0; }
      .points-pill.loss    { color: #dc2626; }
      .points-pill.muted   { color: var(--secondary-text-color); }

      /* ── Empty / error states ──────────────────────────── */
      .empty-state, .error-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 36px 20px;
        color: var(--secondary-text-color);
        text-align: center;
      }
      .error-state { color: var(--error-color, #f44336); }
      .empty-state ha-icon, .error-state ha-icon {
        --mdc-icon-size: 44px;
        margin-bottom: 12px;
        opacity: 0.45;
      }
      .empty-state .message { font-size: 0.95rem; color: var(--primary-text-color); font-weight: 600; }
      .empty-state .submessage { font-size: 0.8rem; margin-top: 4px; }

      .feed-end {
        padding: 14px;
        text-align: center;
        color: var(--secondary-text-color);
        font-size: 0.72rem;
        border-top: 1px dashed var(--divider-color, #ececf2);
        opacity: 0.7;
      }

      /* ── Undo button ───────────────────────────────────── */
      .undo-btn {
        flex-shrink: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        margin-left: 2px;
        border-radius: 50%;
        border: 1px solid var(--divider-color, #e0e0e0);
        background: transparent;
        color: var(--secondary-text-color);
        cursor: pointer;
        transition: background 0.12s ease, color 0.12s ease;
      }
      .undo-btn:hover {
        background: var(--secondary-background-color, rgba(0,0,0,0.05));
        color: var(--primary-text-color);
      }
      .undo-btn[disabled] { opacity: 0.4; cursor: default; }
      .undo-btn ha-icon { --mdc-icon-size: 16px; }

      .undo-confirm-body { font-size: 0.95rem; line-height: 1.4; color: var(--primary-text-color); }
      .undo-confirm-go { --mdc-theme-primary: var(--error-color, #d9534f); }

      /* ── Designed styles (playroom / console / cleanpro) ── */
      .tmd-filters { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 13px; }
      .tmd-filters .chip { cursor: pointer; }
      .tmd-undo { padding: 4px 11px; }
      .act-line { font-weight: 700; font-size: 13.5px; line-height: 1.35; }
      .act-line .reason { font-weight: 400; color: var(--tmd-dim); }
      .act-ago { font-size: 11.5px; }
      .act-rel { opacity: 0.8; }

      /* Playroom — bubbly nodes */
      .act-pl { gap: 11px; }
      .act-pl-row { gap: 11px; }
      .act-pl-av { font-size: 18px; }
      .act-pl-bub { flex: 1; min-width: 0; background: var(--tmd-surface-2); border-radius: 16px; padding: 10px 12px; }
      .act-pl-foot { justify-content: space-between; margin-top: 5px; gap: 8px; }

      /* Console — log feel, mono timestamps */
      .act-cn { gap: 0; }
      .act-cn-row { gap: 10px; padding: 9px 2px; border-bottom: 1px solid var(--tmd-border); }
      .act-cn-row:last-child { border-bottom: none; }
      .act-cn-mid { flex: 1; min-width: 0; font-size: 12.5px; font-weight: 600; }
      .act-cn-time { font-size: 11px; flex-shrink: 0; text-align: right; line-height: 1.3; white-space: nowrap; }

      /* Clean Pro — connecting rail */
      .act-cp-rail { position: relative; padding-left: 26px; }
      .act-cp-line { position: absolute; left: 11px; top: 6px; bottom: 6px; width: 2px; background: var(--tmd-border); }
      .act-cp { gap: 14px; }
      .act-cp-node { position: relative; }
      .act-cp-dot { position: absolute; left: -26px; top: 0; width: 22px; height: 22px; border-radius: 50%;
        background: color-mix(in srgb, var(--ac, var(--tmd-accent)) 18%, transparent); color: var(--ac, var(--tmd-accent));
        display: grid; place-items: center; font-size: 11px; line-height: 1; box-shadow: 0 0 0 3px var(--tmd-surface); }
      .act-cp-head { justify-content: space-between; align-items: flex-start; gap: 10px; }
      /* Coloured event stripe (honours accent_stripes) — vertically centred with the row */
      .act-stripe { width: 4px; border-radius: 4px; flex: none; align-self: stretch; }
      .act-pl-row, .act-cn-row { align-items: center; }
      /* Vertical scroll (parity with classic) — extend to the card edge so the
         scrollbar sits at the edge, not floating inset by the body padding. */
      .act-pl, .act-cn, .act-cp-rail { max-height: 360px; overflow-y: auto;
        margin-right: -15px; padding-right: 8px; }

      /* Undo confirm overlay (works in classic + designed; no mwc dependency) */
      .undo-ov { position: fixed; inset: 0; z-index: 99; display: grid; place-items: center;
        background: rgba(0,0,0,0.45); padding: 16px; }
      .undo-modal { background: var(--card-background-color, #fff); color: var(--primary-text-color);
        border-radius: 16px; padding: 18px 18px 14px; max-width: 340px; width: 100%;
        box-shadow: 0 16px 48px rgba(0,0,0,0.35); }
      .undo-modal-title { font-weight: 800; font-size: 1.05rem; margin-bottom: 8px; }
      .undo-modal-body { font-size: 0.92rem; color: var(--secondary-text-color); line-height: 1.45; }
      .undo-modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
      .undo-modal-btn { font: inherit; font-weight: 700; border: 0; cursor: pointer;
        padding: 9px 16px; border-radius: 10px; }
      .undo-modal-btn.cancel { background: var(--secondary-background-color, #ececec); color: var(--primary-text-color); }
      .undo-modal-btn.go { background: var(--error-color, #e74c3c); color: #fff; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Please define an entity");
    this.config = {
      title: "",
      max_items: 30,
      child_id: null,
      header_color: '#2471a3',
      show_filter_chips: true,
      accent_stripes: true,
      show_relative_time: true,
      show_undo: true,
      ...config,
    };
  }

  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("taskmate-activity-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Activity" };
  }

  _setFilter(filter) {
    if (this._filter === filter) return;
    this._filter = filter;
  }

  _eventBucket(item) {
    const t = item.type || "chore";
    if (t === "points_added" || t === "points_removed") return "adjustments";
    if (t === "reward" || t === "reward_claimed" || t === "reward_approved") return "rewards";
    return "chores";
  }

  _classifyItem(item) {
    const t = item.type || "chore";
    if (t === "points_added") {
      const reason = item.reason || "";
      if (reason.startsWith("Bonus:") || reason.startsWith("Perfect week bonus") ||
          reason.startsWith("Weekend bonus") || reason.startsWith("Streak milestone bonus")) {
        return "bonus";
      }
      return "approved";
    }
    if (t === "points_removed") {
      const reason = item.reason || "";
      if (reason.startsWith("Penalty:")) return "penalty";
      return "reward";
    }
    if (t === "reward_claimed") return item.approved ? "reward" : "pending";
    if (t === "reward_approved") return "reward";
    if (t === "reward") return "reward";
    if (item.rejected) return "rejected";
    if (item.approved) return "approved";
    return "pending";
  }

  // Shared data prep used by both the classic and designed render paths.
  _buildEvents(entity) {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const pointsIcon = attrs.points_icon || "mdi:star";
    const children = attrs.children || [];
    const chores = attrs.chores || [];

    const childNames = {};
    children.forEach(ch => { childNames[ch.id] = ch.name; });
    const chorePointsMap = {};
    chores.forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });

    let completions = [...(attrs.recent_completions || attrs.todays_completions || [])];
    const seen = new Set();
    completions = completions.filter(comp => {
      if (seen.has(comp.completion_id)) return false;
      seen.add(comp.completion_id);
      return true;
    });

    const transactions = (attrs.recent_transactions || []).map(t => ({
      ...t,
      completed_at: t.created_at,
    }));

    let allEvents = [...completions, ...transactions];

    if (this.config.child_id) {
      allEvents = allEvents.filter(e => e.child_id === this.config.child_id);
    }

    allEvents.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at));

    const maxItems = this.config.max_items || 30;
    const unfiltered = allEvents.slice(0, maxItems);

    const filteredEvents = this._filter === "all"
      ? unfiltered
      : unfiltered.filter(e => this._eventBucket(e) === this._filter);

    return { childNames, chorePointsMap, pointsIcon, unfiltered, filteredEvents };
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") return this._renderDesigned(design);

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;
    }

    const { childNames, chorePointsMap, pointsIcon, unfiltered, filteredEvents } = this._buildEvents(entity);

    const title = this.config.title || this._t('activity.default_title');
    const headerColor = _safeColor(this.config.header_color, '#2471a3');

    if (unfiltered.length === 0) {
      return html`
        <ha-card>
          <style>:host { --taskmate-header-bg: ${headerColor}; }</style>
          ${this._renderHeader(title, 0)}
          <div class="empty-state">
            <ha-icon icon="mdi:timeline-clock-outline"></ha-icon>
            <div class="message">${this._t('activity.no_activity_yet')}</div>
            <div class="submessage">${this._t('activity.completed_chores_will_appear')}</div>
          </div>
        </ha-card>
      `;
    }

    const groups = this._groupByDay(filteredEvents);

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${headerColor}; }</style>
        ${this._renderHeader(title, filteredEvents.length, unfiltered.length)}
        ${this.config.show_filter_chips !== false ? this._renderFilterBar() : ''}
        <div class="feed-container">
          ${filteredEvents.length === 0 ? html`
            <div class="empty-state">
              <ha-icon icon="mdi:filter-variant-remove"></ha-icon>
              <div class="message">${this._t('activity.no_events_for_filter')}</div>
              <div class="submessage">${this._t('activity.try_different_filter')}</div>
            </div>
          ` : html`
            ${groups.map(([label, suffix, items]) => html`
              <div class="date-label">${label}${suffix ? html`<span class="date-suffix">· ${suffix}</span>` : ''}</div>
              ${items.map(item => this._renderItem(item, childNames, pointsIcon, chorePointsMap))}
            `)}
            <div class="feed-end">${this._t('activity.feed_end')}</div>
          `}
        </div>
        ${this._renderConfirmDialog()}
      </ha-card>
    `;
  }

  _renderHeader(title, count) {
    return html`
      <div class="card-header">
        <div class="header-content">
          <span class="header-icon-chip"><ha-icon icon="mdi:timeline-clock"></ha-icon></span>
          <span class="header-title">${title}</span>
          <span class="header-meta">· ${this._t('activity.events_count', { count })}</span>
        </div>
      </div>
    `;
  }

  _renderFilterBar() {
    const chips = [
      { id: "all",         label: this._t('activity.filter_all'),         icon: null },
      { id: "chores",      label: this._t('activity.filter_chores'),      icon: "mdi:checkbox-marked-circle-outline" },
      { id: "rewards",     label: this._t('activity.filter_rewards'),     icon: "mdi:gift-outline" },
      { id: "adjustments", label: this._t('activity.filter_adjustments'), icon: "mdi:plus-minus-variant" },
    ];
    return html`
      <div class="filter-bar" role="tablist" aria-label="${this._t('activity.filter_aria_label')}">
        ${chips.map(c => html`
          <button
            type="button"
            class="filter-chip ${this._filter === c.id ? 'active' : ''}"
            role="tab"
            aria-selected="${this._filter === c.id}"
            @click=${() => this._setFilter(c.id)}
          >
            ${c.icon ? html`<ha-icon icon="${c.icon}"></ha-icon>` : ''}
            ${c.label}
          </button>
        `)}
      </div>
    `;
  }

  _renderItem(item, childNames, pointsIcon, chorePointsMap) {
    const childName = childNames[item.child_id] || item.child_name || this._t('activity.unknown_child');
    const type = item.type || "chore";
    const time = this._formatTime(new Date(item.completed_at));
    const ago = this._formatAgo(new Date(item.completed_at));
    const klass = this._classifyItem(item);

    // ── Manual points transactions ────────────────────────
    if (type === "points_added" || type === "points_removed") {
      const isAdd = type === "points_added";
      const pts = Math.abs(item.points || 0);
      const reason = item.reason || '';
      const isPenalty = reason.startsWith('Penalty:');
      const isPoolAllocation = reason.startsWith('Allocated to pool:');
      const isSpend = !isAdd && !isPenalty && isPoolAllocation;
      const verb = isAdd ? this._t('activity.received')
                 : isSpend ? this._t('activity.spent')
                 : this._t('activity.lost');
      const pillClass = isAdd ? 'gain' : (isSpend ? 'spend' : 'loss');
      const icon = isAdd ? 'mdi:star-plus' : (isPenalty ? 'mdi:minus-circle' : 'mdi:star-minus');
      const displayReason = this._translateReason(item.reason);

      return html`
        <div class="activity-item t-${klass}">
          ${this.config.accent_stripes !== false ? html`<div class="event-stripe"></div>` : ''}
          <div class="activity-row">
            <div class="activity-icon t-${klass}">
              <ha-icon icon="${icon}"></ha-icon>
            </div>
            <div class="activity-body">
              <div class="activity-title">
                <strong>${childName}</strong>
                ${' '}${verb}${' '}<strong>${pts}</strong>
                ${item.reason ? html` <span class="reason">— ${displayReason}</span>` : ` ${this._t('activity.points_manually')}`}
              </div>
              <div class="activity-meta">
                <span class="activity-time">${time}</span>
                ${this.config.show_relative_time !== false ? html`<span class="activity-ago">${ago}</span>` : ''}
              </div>
            </div>
            <span class="points-pill ${pillClass}">
              ${isAdd ? '+' : '−'}${pts}
              <ha-icon icon="${pointsIcon}"></ha-icon>
            </span>
            ${this._txnReversible(reason)
              ? this._renderUndoButton('txn', item.transaction_id, displayReason || reason, childName, pts)
              : ''}
          </div>
        </div>
      `;
    }

    // ── Reward claim events ───────────────────────────────
    if (type === "reward_claimed" || type === "reward_approved") {
      const pts = Math.abs(item.points || 0);
      const isPending = type === "reward_claimed" && !item.approved;
      const pillClass = isPending ? 'muted' : 'spend';
      const itemKlass = isPending ? 'pending' : 'reward';

      return html`
        <div class="activity-item t-${itemKlass}">
          ${this.config.accent_stripes !== false ? html`<div class="event-stripe"></div>` : ''}
          <div class="activity-row">
            <div class="activity-icon t-${itemKlass}">
              <ha-icon icon="${isPending ? 'mdi:gift-outline' : 'mdi:gift'}"></ha-icon>
            </div>
            <div class="activity-body">
              <div class="activity-title">
                <strong>${childName}</strong>
                ${isPending ? ` ${this._t('activity.claimed')}` : ` ${this._t('activity.redeemed')}`}
                <strong>${item.reward_name || this._t('activity.a_reward')}</strong>
                ${isPending ? html` <span class="activity-status pending">${this._t('activity.awaiting_approval')}</span>` : ''}
              </div>
              <div class="activity-meta">
                <span class="activity-time">${time}</span>
                ${this.config.show_relative_time !== false ? html`<span class="activity-ago">${ago}</span>` : ''}
              </div>
            </div>
            ${pts ? html`
              <span class="points-pill ${pillClass}">
                −${pts}
                <ha-icon icon="${pointsIcon}"></ha-icon>
              </span>
            ` : ''}
          </div>
        </div>
      `;
    }

    // ── Chore completions ─────────────────────────────────
    const status = item.approved ? "approved" : item.rejected ? "rejected" : "pending";
    const iconMap = {
      approved: 'mdi:checkbox-marked-circle',
      pending:  'mdi:clock-outline',
      rejected: 'mdi:close-circle',
    };
    const pillClass = status === 'approved' ? 'gain' : status === 'rejected' ? 'loss' : 'muted';
    const choreName = item.chore_name || this._t('activity.a_chore');
    const pts = item.points !== undefined ? item.points : (chorePointsMap?.[item.chore_id] || 0);

    return html`
      <div class="activity-item t-${status}">
        <div class="event-stripe"></div>
        <div class="activity-row">
          <div class="activity-icon t-${status}">
            <ha-icon icon="${iconMap[status]}"></ha-icon>
          </div>
          <div class="activity-body">
            <div class="activity-title">
              <strong>${childName}</strong> · ${choreName}
              ${status !== 'approved' ? html`
                <span class="activity-status ${status}">${this._t('common.' + status)}</span>
              ` : ''}
            </div>
            <div class="activity-meta">
              <span class="activity-time">${time}</span>
              <span class="activity-ago">${ago}</span>
            </div>
          </div>
          ${pts ? html`
            <span class="points-pill ${pillClass}">
              +${pts}
              <ha-icon icon="${pointsIcon}"></ha-icon>
            </span>
          ` : ''}
          ${status === 'approved'
            ? this._renderUndoButton('chore', item.completion_id, choreName, childName, pts)
            : ''}
        </div>
      </div>
    `;
  }

  // ── Undo affordance ──────────────────────────────────────
  // kind: 'chore' (undo an approval → pending) or 'txn' (reverse a points txn).
  _renderUndoButton(kind, id, detail, child, points) {
    if (!id || this.config.show_undo === false) return '';
    const loading = !!this._loading[id];
    const message = kind === 'chore'
      ? this._t('activity.undo_confirm_chore', { detail, child, points })
      : this._t('activity.undo_confirm_txn', { detail, child, points });
    return html`
      <button
        class="undo-btn"
        type="button"
        title=${this._t('activity.undo')}
        aria-label=${this._t('activity.undo')}
        ?disabled=${loading}
        @click=${() => { this._confirm = { kind, id, message }; }}
      >
        <ha-icon icon="mdi:undo-variant"></ha-icon>
      </button>
    `;
  }

  _renderConfirmDialog() {
    if (!this._confirm) return '';
    // Self-contained overlay (not ha-dialog/mwc-button, which can render without
    // visible action buttons if those components aren't loaded on the page).
    return html`
      <div class="undo-ov" @click=${(e) => { if (e.target.classList.contains('undo-ov')) this._confirm = null; }}>
        <div class="undo-modal" role="dialog" aria-modal="true">
          <div class="undo-modal-title">${this._t('activity.undo_confirm_title')}</div>
          <div class="undo-modal-body">${this._confirm.message}</div>
          <div class="undo-modal-actions">
            <button class="undo-modal-btn cancel" @click=${() => { this._confirm = null; }}>
              ${this._t('common.cancel')}
            </button>
            <button class="undo-modal-btn go" @click=${() => this._doUndo()}>
              ↩ ${this._t('activity.undo')}
            </button>
          </div>
        </div>
      </div>
    `;
  }

  async _doUndo() {
    const pending = this._confirm;
    this._confirm = null;
    if (!pending) return;
    const { kind, id } = pending;
    if (this._loading[id]) return;
    this._loading = { ...this._loading, [id]: true };
    this.requestUpdate();
    try {
      if (kind === 'chore') {
        await this.hass.callService('taskmate', 'undo_chore_approval', { completion_id: id });
      } else {
        await this.hass.callService('taskmate', 'undo_transaction', { transaction_id: id });
      }
    } catch (error) {
      console.error('TaskMate undo failed:', error);
      if (this.hass.callService) {
        this.hass.callService('persistent_notification', 'create', {
          title: this._t('activity.undo_error_title'),
          message: this._t('activity.undo_error_body', { message: error.message }),
          notification_id: `taskmate_undo_error_${id}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [id]: false };
    }
  }

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns/frag/17-activity.html
  ══════════════════════════════════════════════════════════════════════ */

  // Normalise a raw event into a descriptor the designed renderers consume.
  // Preserves the SAME undo affordance/handler used by the classic path.
  _describeEvent(item, childNames, pointsIcon, chorePointsMap) {
    const childName = childNames[item.child_id] || item.child_name || this._t('activity.unknown_child');
    const type = item.type || "chore";
    const ago = this._formatAgo(new Date(item.completed_at)) || this._formatTime(new Date(item.completed_at));
    const time = this._formatTime(new Date(item.completed_at));

    if (type === "points_added" || type === "points_removed") {
      const isAdd = type === "points_added";
      const pts = Math.abs(item.points || 0);
      const reason = item.reason || '';
      const isPenalty = reason.startsWith('Penalty:');
      const isPoolAllocation = reason.startsWith('Allocated to pool:');
      const isSpend = !isAdd && !isPenalty && isPoolAllocation;
      const displayReason = this._translateReason(item.reason);
      const verb = isAdd ? this._t('activity.received') : isSpend ? this._t('activity.spent') : this._t('activity.lost');
      const sign = isAdd ? '+' : '−';
      const tone = isAdd ? 'good' : (isSpend ? 'accent' : 'bad');
      const emoji = isAdd ? '⭐' : (isPenalty ? '⚠️' : '➖');
      return {
        childName, tone, emoji, sign, pts,
        text: html`<strong>${childName}</strong> ${verb} <strong>${pts}</strong>${item.reason ? html` <span class="reason">— ${displayReason}</span>` : ''}`,
        plain: `${childName} ${verb} ${pts}`,
        ago, time,
        ptsClass: isAdd ? 'good' : (isSpend ? 'accent' : 'bad'),
        undo: this._txnReversible(reason)
          ? { kind: 'txn', id: item.transaction_id, detail: displayReason || reason, child: childName, points: pts }
          : null,
      };
    }

    if (type === "reward_claimed" || type === "reward_approved") {
      const pts = Math.abs(item.points || 0);
      const isPending = type === "reward_claimed" && !item.approved;
      const rewardName = item.reward_name || this._t('activity.a_reward');
      return {
        childName, tone: 'accent', emoji: '🎁', sign: '−', pts,
        text: html`<strong>${childName}</strong> ${isPending ? this._t('activity.claimed') : this._t('activity.redeemed')} <strong>${rewardName}</strong>`,
        plain: `${childName} · ${rewardName}`,
        ago, time,
        ptsClass: 'accent',
        undo: null,
      };
    }

    // Chore completion
    const status = item.approved ? "approved" : item.rejected ? "rejected" : "pending";
    const choreName = item.chore_name || this._t('activity.a_chore');
    const pts = item.points !== undefined ? item.points : (chorePointsMap?.[item.chore_id] || 0);
    const tone = status === 'approved' ? 'good' : status === 'rejected' ? 'bad' : 'warn';
    const emoji = status === 'approved' ? '✅' : status === 'rejected' ? '❌' : '⏳';
    return {
      childName, tone, emoji, sign: '+', pts,
      text: html`<strong>${childName}</strong> ${this._t('activity.completed')} ${choreName}`,
      plain: `${childName} · ${choreName}`,
      ago, time,
      ptsClass: status === 'approved' ? 'good' : status === 'rejected' ? 'bad' : 'muted',
      undo: status === 'approved'
        ? { kind: 'chore', id: item.completion_id, detail: choreName, child: childName, points: pts }
        : null,
    };
  }

  _designUndoBtn(undo, label) {
    if (!undo || !undo.id || this.config.show_undo === false) return '';
    const loading = !!this._loading[undo.id];
    const message = undo.kind === 'chore'
      ? this._t('activity.undo_confirm_chore', { detail: undo.detail, child: undo.child, points: undo.points })
      : this._t('activity.undo_confirm_txn', { detail: undo.detail, child: undo.child, points: undo.points });
    return html`<button class="btn ghost sm tmd-undo" ?disabled=${loading}
      @click=${() => { this._confirm = { kind: undo.kind, id: undo.id, message }; }}>↩ ${label}</button>`;
  }

  _designFilterChips() {
    const chips = [
      { id: "all", label: this._t('activity.filter_all') },
      { id: "chores", label: this._t('activity.filter_chores') },
      { id: "rewards", label: this._t('activity.filter_rewards') },
      { id: "adjustments", label: this._t('activity.filter_adjustments') },
    ];
    return html`
      <div class="tmd-filters">
        ${chips.map(c => html`
          <button class="chip ${this._filter === c.id ? 'soft' : ''}"
            @click=${() => this._setFilter(c.id)}>${c.label}</button>`)}
      </div>`;
  }

  _renderDesigned(design) {
    const entity = this.hass.states[this.config.entity];
    const hd = _safeColor(this.config.header_color, '#16a085');
    const title = this.config.title || this._t('activity.default_title');

    const header = (sub, pill) => html`
      <div class="tmd-hd">
        <span class="ic">📜</span>
        <span class="tt">${title}${sub ? html`<small>${sub}</small>` : ''}</span>
        ${pill ? html`<span class="pill">${pill}</span>` : ''}
      </div>`;

    if (!entity) {
      return html`<ha-card class="tmd" style="--hd:${hd}">${header()}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card class="tmd" style="--hd:${hd}">${header()}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.unavailable')}</div></div></ha-card>`;
    }

    const { childNames, chorePointsMap, pointsIcon, unfiltered, filteredEvents } = this._buildEvents(entity);

    if (unfiltered.length === 0) {
      return html`<ha-card class="tmd" style="--hd:${hd}">${header(this._t('activity.recent_events'))}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('activity.no_activity_yet')}</div></div></ha-card>`;
    }

    const rows = filteredEvents.map(e => this._describeEvent(e, childNames, pointsIcon, chorePointsMap));

    const sub = design === 'console' ? 'LIVE · STREAM' : this._t('activity.recent_events');
    const pill = design === 'console' ? this._t('activity.events_count', { count: filteredEvents.length }) : '';
    const body = html`
      ${this.config.show_filter_chips !== false ? this._designFilterChips() : ''}
      ${filteredEvents.length === 0
        ? html`<div class="tmd-empty">${this._t('activity.no_events_for_filter')}</div>`
        : design === 'console' ? this._designConsole(rows)
        : design === 'cleanpro' ? this._designCleanpro(rows)
        : this._designPlayroom(rows)}`;

    return html`<ha-card class="tmd" style="--hd:${hd}">
      ${header(sub, pill)}
      <div class="tmd-bd">${body}</div>
      ${this._renderConfirmDialog()}
    </ha-card>`;
  }

  // Always show the absolute time; when show_relative_time is on, show the
  // relative "x ago" ALONGSIDE it (matches the classic activity-meta row).
  _timeMeta(r) {
    return this.config.show_relative_time !== false
      ? html`${r.time} <span class="act-rel">· ${r.ago}</span>`
      : html`${r.time}`;
  }
  _stripe(r) {
    return this.config.accent_stripes !== false
      ? html`<div class="act-stripe" style="background:var(--tmd-${r.tone})"></div>` : '';
  }

  _designPlayroom(rows) {
    return html`
      <div class="grid act-pl">
        ${rows.map(r => html`
          <div class="row act-pl-row" style="--ac:var(--tmd-${r.tone})">
            ${this._stripe(r)}
            <div class="av act-pl-av" style="--av:38px;--ac:var(--tmd-${r.tone})">${r.emoji}</div>
            <div class="act-pl-bub">
              <div class="act-line">${r.text} <span class="num" style="color:var(--tmd-${r.ptsClass})">${r.sign}${r.pts}</span></div>
              <div class="row act-pl-foot">
                <span class="muted act-ago">${this._timeMeta(r)}</span>
                ${this._designUndoBtn(r.undo, this._t('activity.undo'))}
              </div>
            </div>
          </div>`)}
      </div>`;
  }

  _designConsole(rows) {
    return html`
      <div class="grid act-cn">
        ${rows.map(r => html`
          <div class="row act-cn-row" style="--ac:var(--tmd-${r.tone})">
            ${this._stripe(r)}
            <div class="av" style="--av:26px;--ac:var(--tmd-${r.tone})">${r.emoji}</div>
            <div class="act-cn-mid">${r.plain} <span class="num" style="color:var(--tmd-${r.ptsClass})">${r.sign}${r.pts}</span></div>
            ${this._designUndoBtn(r.undo, this._t('activity.undo'))}
            <div class="num muted act-cn-time">${this._timeMeta(r)}</div>
          </div>`)}
      </div>`;
  }

  _designCleanpro(rows) {
    // Clean Pro conveys event colour through the timeline dot; honour
    // accent_stripes by neutralising the dot when stripes are disabled.
    const stripes = this.config.accent_stripes !== false;
    return html`
      <div class="act-cp-rail">
        <div class="act-cp-line"></div>
        <div class="grid act-cp">
          ${rows.map(r => html`
            <div class="act-cp-node">
              <div class="act-cp-dot" style="--ac:${stripes ? `var(--tmd-${r.tone})` : 'var(--tmd-dim)'}">${r.emoji}</div>
              <div class="row act-cp-head">
                <div>
                  <div class="act-line">${r.text} <span style="color:var(--tmd-${r.ptsClass});font-weight:700">${r.sign}${r.pts}</span></div>
                  <div class="muted act-ago">${this._timeMeta(r)}</div>
                </div>
                ${this._designUndoBtn(r.undo, this._t('activity.undo'))}
              </div>
            </div>`)}
        </div>
      </div>`;
  }

  _groupByDay(items) {
    // Returns an array of [primaryLabel, dateSuffix, items]
    // primaryLabel: "Today" / "Yesterday" / weekday-short, dateSuffix: e.g. "Mon 13 May"
    const groups = new Map();
    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const now = new Date();
    const nowKey = now.toLocaleDateString("en-CA", { timeZone: tz });
    const yesterday = new Date(now); yesterday.setDate(yesterday.getDate() - 1);
    const yKey = yesterday.toLocaleDateString("en-CA", { timeZone: tz });

    items.forEach(item => {
      const date = new Date(item.completed_at);
      const key = date.toLocaleDateString("en-CA", { timeZone: tz });

      let primary;
      let suffix;
      if (key === nowKey) {
        primary = this._t('common.today');
        suffix = date.toLocaleDateString(undefined, { timeZone: tz, weekday: "short", day: "numeric", month: "short" });
      } else if (key === yKey) {
        primary = this._t('common.yesterday');
        suffix = date.toLocaleDateString(undefined, { timeZone: tz, weekday: "short", day: "numeric", month: "short" });
      } else {
        primary = date.toLocaleDateString(undefined, { timeZone: tz, weekday: "short" });
        suffix = date.toLocaleDateString(undefined, { timeZone: tz, day: "numeric", month: "short" });
      }

      const groupKey = key;
      if (!groups.has(groupKey)) groups.set(groupKey, { primary, suffix, items: [] });
      groups.get(groupKey).items.push(item);
    });

    return [...groups.values()].map(g => [g.primary, g.suffix, g.items]);
  }

  _formatTime(date) {
    return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }

  // "2h ago" / "5m ago" / "3d ago" — short relative label.
  _formatAgo(date) {
    const diffMs = Date.now() - date.getTime();
    if (diffMs < 0) return "";
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return this._t('activity.just_now');
    if (mins < 60) return this._t('activity.minutes_ago', { count: mins });
    const hours = Math.floor(mins / 60);
    if (hours < 24) return this._t('activity.hours_ago', { count: hours });
    const days = Math.floor(hours / 24);
    if (days < 30) return this._t('activity.days_ago', { count: days });
    return "";
  }
}

// Card Editor
class TaskMateActivityCardEditor extends LitElement {
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
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const children = entity?.attributes?.children || [];
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '__all__', label: this._t('common.editor.filter_by_child_all') },
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
      { name: 'max_items', selector: { number: { min: 5, max: 200, mode: 'box' } } },
      { name: 'show_filter_chips', selector: { boolean: {} } },
      { name: 'accent_stripes', selector: { boolean: {} } },
      { name: 'show_relative_time', selector: { boolean: {} } },
      { name: 'show_undo', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      title: this._t('common.editor.card_title'),
      card_design: this._t('common.design.field_label'),
      child_id: this._t('common.editor.filter_by_child'),
      max_items: this._t('activity.editor.max_items'),
      show_filter_chips: this._t('activity.editor.show_filter_chips'),
      accent_stripes: this._t('activity.editor.accent_stripes'),
      show_relative_time: this._t('activity.editor.show_relative_time'),
      show_undo: this._t('activity.editor.show_undo'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('activity.editor.filter_child_helper'),
      max_items: this._t('activity.editor.max_items_helper'),
      show_filter_chips: this._t('activity.editor.show_filter_chips_helper'),
      accent_stripes: this._t('activity.editor.accent_stripes_helper'),
      show_relative_time: this._t('activity.editor.show_relative_time_helper'),
      show_undo: this._t('activity.editor.show_undo_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      card_design: this.config.card_design || 'global',
      child_id: this.config.child_id || '__all__',
      max_items: this.config.max_items || 30,
      show_filter_chips: this.config.show_filter_chips !== false,
      accent_stripes: this.config.accent_stripes !== false,
      show_relative_time: this.config.show_relative_time !== false,
      show_undo: this.config.show_undo !== false,
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
      ${this._renderColourPicker('header_color', '#2471a3')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    const current = this.config[key] || defaultValue;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current,
      label: this._t('common.editor.header_colour'),
      helper: this._t('common.editor.header_colour_helper'),
      resetLabel: this._t('common.reset'),
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    // Booleans whose default is `true` — drop them from config when true to keep YAML minimal.
    const trueDefaultBooleans = new Set(['show_filter_chips', 'accent_stripes', 'show_relative_time']);
    for (const [key, value] of Object.entries(newValues)) {
      if (
        value === '' || value === null || value === undefined
        || (key === 'child_id' && value === '__all__')
      ) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (key === 'max_items' && value === 30) {
        delete newConfig[key];
      } else if (trueDefaultBooleans.has(key) && value === true) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

customElements.define("taskmate-activity-card", TaskMateActivityCard);
customElements.define("taskmate-activity-card-editor", TaskMateActivityCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-activity-card",
  name: "TaskMate Activity Feed",
  description: "Timeline of recent chore completions and reward claims",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-activity-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE ACTIVITY CARD %c v" + _tmVersion + " ",
  "background:#2471a3;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
