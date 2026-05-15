/**
 * TaskMate Activity Feed Card
 * Scrollable timeline of recent events — completions, approvals, points, rewards.
 *
 * Version: 1.1.0
 * Last Updated: 2026-05-15
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateActivityCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _filter: { type: String, state: true },
    };
  }

  constructor() {
    super();
    this._filter = "all";
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
    return css`
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
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Please define an entity");
    this.config = {
      title: "",
      max_items: 30,
      child_id: null,
      header_color: '#2471a3',
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

  render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;
    }

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

    const title = this.config.title || this._t('activity.default_title');
    const headerColor = this.config.header_color || '#2471a3';

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
        ${this._renderFilterBar()}
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
          <div class="event-stripe"></div>
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
                <span class="activity-ago">${ago}</span>
              </div>
            </div>
            <span class="points-pill ${pillClass}">
              ${isAdd ? '+' : '−'}${pts}
              <ha-icon icon="${pointsIcon}"></ha-icon>
            </span>
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
          <div class="event-stripe"></div>
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
                <span class="activity-ago">${ago}</span>
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
        </div>
      </div>
    `;
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
      { name: 'max_items', selector: { number: { min: 5, max: 200, mode: 'box' } } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      title: this._t('common.editor.card_title'),
      child_id: this._t('common.editor.filter_by_child'),
      max_items: this._t('activity.editor.max_items'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('activity.editor.filter_child_helper'),
      max_items: this._t('activity.editor.max_items_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      child_id: this.config.child_id || '__all__',
      max_items: this.config.max_items || 30,
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
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, '#e67e22', '#27ae60', '#9b59b6', '#f1c40f', '#e74c3c', '#34495e'];
    const isActive = (c) => c.toLowerCase() === current.toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${this._t('common.editor.header_colour')}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current}
              @input=${(e) => this._updateConfig(key, e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current}"></span>
          </label>
          <span class="colour-hex">${current}</span>
          <div class="colour-presets">
            ${presets.map((p) => html`
              <button class="preset-swatch ${isActive(p) ? 'active' : ''}"
                style="background:${p}"
                title=${p}
                @click=${(e) => { e.preventDefault(); this._updateConfig(key, p); }}
              ></button>
            `)}
          </div>
          <button class="colour-reset"
            @click=${(e) => { e.preventDefault(); this._updateConfig(key, defaultValue); }}
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
      if (
        value === '' || value === null || value === undefined
        || (key === 'child_id' && value === '__all__')
      ) {
        delete newConfig[key];
      } else if (key === 'max_items' && value === 30) {
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
