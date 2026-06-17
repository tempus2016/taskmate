/**
 * TaskMate Parent Dashboard Card
 * Unified parent view: all children's today progress, pending approvals
 * with inline approve/reject, pending reward claims, and quick point adjustments.
 *
 * Version: 1.0.0
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateParentDashboardCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _loading: { type: Object },
      _activeSection: { type: String },
      _expanded: { type: Object },
    };
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

  constructor() {
    super();
    this._loading = {};
    this._activeSection = "overview";
    this._expanded = {};
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-card { overflow: hidden; }

      /* ── Header ── */
      .card-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #c0392b);
        color: white; gap: 12px;
      }

      .header-content { display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1; }
      .header-icon { --mdc-icon-size: 26px; opacity: 0.9; flex-shrink: 0; }
      .header-title { font-size: 1.1rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

      .pending-badge {
        background: #e74c3c; color: white;
        border-radius: 12px; padding: 3px 10px;
        font-size: 0.82rem; font-weight: 700;
        display: flex; align-items: center; gap: 4px;
        flex-shrink: 0;
        animation: badge-pulse 2s ease-in-out infinite;
      }

      .pending-badge ha-icon { --mdc-icon-size: 14px; }

      @keyframes badge-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(231,76,60,0.4); }
        50% { box-shadow: 0 0 0 5px rgba(231,76,60,0); }
      }

      /* ── Tab nav ── */
      .tab-nav {
        display: flex;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
        background: var(--secondary-background-color, #f5f5f5);
      }

      .tab-btn {
        flex: 1; padding: 10px 8px;
        background: none; border: none;
        font-size: 0.78rem; font-weight: 600;
        color: var(--secondary-text-color);
        cursor: pointer;
        border-bottom: 2px solid transparent;
        transition: color 0.15s, border-color 0.15s;
        display: flex; align-items: center; justify-content: center; gap: 5px;
        position: relative;
      }

      .tab-btn ha-icon { --mdc-icon-size: 16px; }

      .tab-btn.active {
        color: var(--primary-color, #3498db);
        border-bottom-color: var(--primary-color, #3498db);
      }

      .tab-badge {
        background: #e74c3c; color: white;
        border-radius: 8px; padding: 1px 5px;
        font-size: 0.65rem; font-weight: 700;
        line-height: 1.4;
      }

      /* ── Content ── */
      .tab-content { padding: 14px; display: flex; flex-direction: column; gap: 10px; }

      /* ── Child overview tiles ── */
      .child-tile {
        display: flex; align-items: center; gap: 12px;
        padding: 12px 14px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 12px;
      }

      .child-avatar {
        width: 42px; height: 42px; min-width: 42px;
        border-radius: 50%;
        background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
      }

      .child-avatar ha-icon { --mdc-icon-size: 26px; color: white; }

      .child-tile-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }

      .child-tile-header {
        display: flex; align-items: center; justify-content: space-between; gap: 8px;
      }

      .child-tile-name {
        font-size: 0.95rem; font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }

      .points-pill {
        display: flex; align-items: center; gap: 3px;
        background: rgba(241,196,15,0.15);
        color: #e67e22; border-radius: 10px;
        padding: 2px 8px; font-size: 0.8rem; font-weight: 700;
        flex-shrink: 0;
      }

      .points-pill ha-icon { --mdc-icon-size: 13px; color: #f1c40f; }

      .progress-row { display: flex; align-items: center; gap: 8px; }

      .progress-bar {
        flex: 1; height: 7px;
        background: var(--divider-color, #e0e0e0);
        border-radius: 4px; overflow: hidden;
      }

      .progress-fill {
        height: 100%; border-radius: 4px;
        transition: width 0.4s ease;
      }

      .progress-fill.complete { background: linear-gradient(90deg, #27ae60, #2ecc71); }
      .progress-fill.partial { background: linear-gradient(90deg, #3498db, #2980b9); }
      .progress-fill.none { width: 0 !important; }

      .progress-label {
        font-size: 0.75rem; font-weight: 600;
        color: var(--secondary-text-color);
        white-space: nowrap; min-width: 32px; text-align: right;
      }

      /* ── Approval items ── */
      .approval-item {
        display: flex; align-items: center; gap: 10px;
        padding: 12px 14px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 12px;
        transition: opacity 0.2s;
      }

      .approval-item.loading { opacity: 0.5; pointer-events: none; }

      .approval-child-avatar {
        width: 38px; height: 38px; min-width: 38px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        display: flex; align-items: center; justify-content: center;
      }

      .approval-child-avatar ha-icon { --mdc-icon-size: 22px; color: white; }

      .approval-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }

      .approval-chore {
        font-size: 0.9rem; font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }

      .approval-meta {
        font-size: 0.75rem; color: var(--secondary-text-color);
        display: flex; align-items: center; gap: 6px;
      }

      .approval-points {
        display: flex; align-items: center; gap: 2px;
        font-weight: 600; color: #e67e22;
      }

      .approval-points ha-icon { --mdc-icon-size: 12px; color: #f1c40f; }

      .approval-actions { display: flex; gap: 6px; flex-shrink: 0; }

      .btn-approve, .btn-reject {
        width: 34px; height: 34px;
        border-radius: 50%; border: none; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        transition: transform 0.1s, box-shadow 0.1s;
        flex-shrink: 0;
      }

      .btn-approve {
        background: linear-gradient(135deg, #27ae60, #2ecc71);
        color: white; box-shadow: 0 2px 8px rgba(46,204,113,0.3);
      }

      .btn-reject {
        background: linear-gradient(135deg, #c0392b, #e74c3c);
        color: white; box-shadow: 0 2px 8px rgba(231,76,60,0.3);
      }

      .btn-approve:hover { transform: scale(1.1); }
      .btn-reject:hover { transform: scale(1.1); }
      .btn-approve ha-icon, .btn-reject ha-icon { --mdc-icon-size: 18px; }

      /* ── Reward claim items ── */
      .claim-item {
        display: flex; align-items: center; gap: 10px;
        padding: 12px 14px;
        background: var(--card-background-color, #fff);
        border: 1px solid rgba(155,89,182,0.3);
        border-radius: 12px;
        background: rgba(155,89,182,0.04);
        transition: opacity 0.2s;
      }

      .claim-item.loading { opacity: 0.5; pointer-events: none; }

      .claim-icon-wrap {
        width: 38px; height: 38px; min-width: 38px;
        border-radius: 50%;
        background: linear-gradient(135deg, #9b59b6, #8e44ad);
        display: flex; align-items: center; justify-content: center;
      }

      .claim-icon-wrap ha-icon { --mdc-icon-size: 22px; color: white; }

      .claim-info { flex: 1; min-width: 0; }

      .claim-reward-name {
        font-size: 0.9rem; font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }

      .claim-meta {
        font-size: 0.75rem; color: var(--secondary-text-color); margin-top: 2px;
      }

      /* ── Quick points ── */
      .quick-points-row {
        display: flex; align-items: center; gap: 10px;
        padding: 12px 14px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 12px;
      }

      .qp-avatar {
        width: 38px; height: 38px; min-width: 38px;
        border-radius: 50%;
        background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        display: flex; align-items: center; justify-content: center;
      }

      .qp-avatar ha-icon { --mdc-icon-size: 22px; color: white; }

      .qp-name {
        flex: 1; font-size: 0.9rem; font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }

      .qp-points {
        font-size: 1rem; font-weight: 700;
        color: #9b59b6; white-space: nowrap;
        display: flex; align-items: center; gap: 3px;
      }

      .qp-points ha-icon { --mdc-icon-size: 14px; color: #f1c40f; }

      .qp-actions { display: flex; gap: 6px; }

      .btn-add, .btn-remove {
        width: 32px; height: 32px;
        border-radius: 50%; border: none; cursor: pointer;
        display: flex; align-items: center; justify-content: center;
        transition: transform 0.1s;
        flex-shrink: 0;
      }

      .btn-add {
        background: linear-gradient(135deg, #27ae60, #2ecc71);
        color: white; box-shadow: 0 2px 6px rgba(46,204,113,0.3);
      }

      .btn-remove {
        background: linear-gradient(135deg, #c0392b, #e74c3c);
        color: white; box-shadow: 0 2px 6px rgba(231,76,60,0.3);
      }

      .btn-add:hover, .btn-remove:hover { transform: scale(1.1); }
      .btn-add ha-icon, .btn-remove ha-icon { --mdc-icon-size: 16px; }

      /* ── Complete on behalf (admin) ── */
      .tm-outstanding { margin-top: 8px; border-top: 1px dashed var(--divider-color, #e0e0e0); padding-top: 8px; }
      .tm-outstanding-hdr { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.6; margin-bottom: 6px; }
      .tm-outstanding-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
      .tm-outstanding-row + .tm-outstanding-row { border-top: 1px solid var(--divider-color, #eee); }
      .tm-outstanding-name { flex: 1; font-size: 0.9rem; }
      .tm-outstanding-pts { opacity: 0.6; font-size: 0.8rem; display: inline-flex; align-items: center; gap: 2px; }
      .btn-complete-behalf { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 4px; border: none; cursor: pointer; background: #2e9e5b; color: #fff; font: 600 0.75rem/1 inherit; padding: 6px 10px; border-radius: 8px; }
      .btn-complete-behalf:hover { background: #27894e; }
      .btn-complete-behalf:active { transform: scale(0.96); }
      .btn-complete-behalf[disabled] { opacity: 0.5; pointer-events: none; }
      .child-tile.tm-expandable .child-tile-main { cursor: pointer; }
      .tm-all-done { font-size: 0.85rem; opacity: 0.6; font-style: italic; padding: 4px 0; }

      /* ── Empty state ── */
      .empty-section {
        display: flex; flex-direction: column; align-items: center;
        padding: 24px 16px; text-align: center; gap: 8px;
        color: var(--secondary-text-color);
      }

      .empty-section ha-icon { --mdc-icon-size: 40px; opacity: 0.35; }
      .empty-section span { font-size: 0.9rem; }

      .timed-sessions-section {
        padding: 8px 0; margin-bottom: 8px;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .timed-session-row {
        display: flex; align-items: center; gap: 8px;
        padding: 6px 0; font-size: 0.9rem;
      }
      .timed-session-row ha-icon { --mdc-icon-size: 18px; }
      .paused-tag {
        font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
        color: #e67e22; background: rgba(230, 126, 34, 0.12);
        padding: 2px 6px; border-radius: 4px;
      }

      .error-state {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 40px 20px;
        color: var(--error-color, #f44336); text-align: center;
      }

      .error-state ha-icon { --mdc-icon-size: 48px; margin-bottom: 12px; opacity: 0.5; }

      @media (max-width: 480px) {
        .card-header { padding: 12px 14px; }
        .tab-btn { font-size: 0.72rem; padding: 8px 6px; }
        .tab-content { padding: 10px; gap: 8px; }
        .approval-item, .claim-item, .quick-points-row, .child-tile { padding: 10px 12px; }
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Please define an entity");
    this.config = {
      title: "Parent Dashboard",
      quick_points_amount: 5,
      show_claims: true,
            header_color: '#c0392b',
    ...config,
    };
  }

  getCardSize() { return 6; }
  static getConfigElement() { return document.createElement("taskmate-parent-dashboard-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Parent Dashboard" };
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    if (entity.state === "unavailable" || entity.state === "unknown") return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const chores = attrs.chores || [];
    const completions = attrs.todays_completions || [];
    // Pending approvals come from the full pending list (not filtered to
    // today) so a completion left pending from a previous day still shows an
    // approve button after a recurring chore resets. `completions` stays
    // today-only for the overview tab's activity display.
    const pendingCompletions = attrs.chore_completions || completions.filter(c => !c.approved);
    const pendingRewardClaims = attrs.pending_reward_claims || [];
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t('common.points');
    const totalPending = pendingCompletions.length + pendingRewardClaims.length;

    const rotationChores = chores.filter(c => ['alternating', 'random', 'balanced'].includes(c.assignment_mode || 'everyone'));

    const tabs = [
      { id: "overview", label: this._t('dashboard.tab_overview'), icon: "mdi:view-dashboard" },
      { id: "approvals", label: this._t('dashboard.tab_approvals'), icon: "mdi:check-circle", count: pendingCompletions.length },
      { id: "points", label: this._t('dashboard.tab_points'), icon: "mdi:star-plus" },
    ];

    if (rotationChores.length > 0) {
      tabs.splice(1, 0, { id: "rotation", label: this._t('dashboard.tab_rotation', {}, 'Rotation'), icon: "mdi:rotate-3d-variant" });
    }

    if (this.config.show_claims) {
      const insertAt = tabs.findIndex(t => t.id === "points");
      tabs.splice(insertAt, 0, { id: "claims", label: this._t('dashboard.tab_claims'), icon: "mdi:gift", count: pendingRewardClaims.length });
    }

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#c0392b'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:shield-account"></ha-icon>
            <span class="header-title">${this.config.title || this._t('dashboard.default_title')}</span>
          </div>
          ${totalPending > 0 ? html`
            <div class="pending-badge">
              <ha-icon icon="mdi:clock-alert"></ha-icon>
              ${totalPending}
            </div>
          ` : ''}
        </div>

        <div class="tab-nav">
          ${tabs.map(tab => html`
            <button
              class="tab-btn ${this._activeSection === tab.id ? 'active' : ''}"
              @click="${() => { this._activeSection = tab.id; this.requestUpdate(); }}"
            >
              <ha-icon icon="${tab.icon}"></ha-icon>
              ${tab.label}
              ${tab.count ? html`<span class="tab-badge">${tab.count}</span>` : ''}
            </button>
          `)}
        </div>

        <div class="tab-content">
          ${this._activeSection === "overview" ? this._renderOverview(children, chores, completions, pointsIcon, pointsName) : ''}
          ${this._activeSection === "rotation" ? this._renderRotation(rotationChores, children, attrs) : ''}
          ${this._activeSection === "approvals" ? this._renderApprovals(pendingCompletions, children, chores, pointsIcon) : ''}
          ${this._activeSection === "claims" ? this._renderClaims(pendingRewardClaims, pointsIcon) : ''}
          ${this._activeSection === "points" ? this._renderPoints(children, pointsIcon, pointsName) : ''}
        </div>
      </ha-card>
    `;
  }

  _renderOverview(children, chores, completions, pointsIcon, pointsName) {
    if (!children.length) return html`<div class="empty-section"><ha-icon icon="mdi:account-group"></ha-icon><span>${this._t('dashboard.empty_no_children')}</span></div>`;

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity)) || {};
    const todayDow = attrs.today_day_of_week ||
      new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();
    const availability = attrs.chore_availability || {};

    const timedSessions = attrs.active_timed_sessions || [];
    const childById = Object.fromEntries(children.map(c => [c.id, c]));
    const choreById = Object.fromEntries(chores.map(c => [c.id, c]));

    return html`
      ${timedSessions.length > 0 ? html`
        <div class="timed-sessions-section">
          ${timedSessions.map(s => {
            const sChild = childById[s.child_id];
            const sChore = choreById[s.chore_id];
            if (!sChild || !sChore) return '';
            let elapsed = s.total_seconds_today || 0;
            if (s.state === 'running' && s.current_segment_start) {
              elapsed += Math.max(0, Math.floor((Date.now() - new Date(s.current_segment_start).getTime()) / 1000));
            }
            const mins = Math.floor(elapsed / 60);
            const secs = elapsed % 60;
            return html`
              <div class="timed-session-row">
                <ha-icon icon="mdi:timer-outline" style="color: ${s.state === 'running' ? '#2ecc71' : '#e67e22'};"></ha-icon>
                <span><strong>${sChild.name}</strong> — ${sChore.name} (${String(mins).padStart(2,'0')}:${String(secs).padStart(2,'0')})</span>
                ${s.state === 'paused' ? html`<span class="paused-tag">${this._t('dashboard.paused_tag')}</span>` : ''}
              </div>
            `;
          })}
        </div>
      ` : ''}
      ${children.map(child => {
        const childChores = chores.filter(c => {
          // Skip disabled chores (one-shot completed or expired)
          if (c.enabled === false) return false;
          if ((c.disabled_for || []).includes(child.id)) return false;

          const at = c.assigned_to || [];
          const assigned = at.length === 0 || at.includes(child.id);
          if (!assigned) return false;
          const perChild = availability[c.id];
          // One-shot: use is_available check (same as recurring)
          if (c.schedule_mode === 'one_shot') {
            if (perChild && perChild[child.id] === false) return false;
          }
          // Mode A: due days check
          if (c.schedule_mode === 'specific_days') {
            const dueDays = Array.isArray(c.due_days) ? c.due_days : [];
            if (dueDays.length > 0 && !dueDays.includes(todayDow)) return false;
          }
          // Mode B: recurrence availability check
          if (c.schedule_mode === 'recurring') {
            if (perChild && perChild[child.id] === false) return false;
          }
          return true;
        });
        const childChoreIds = new Set(childChores.map(c => c.id));
        const approved = completions.filter(c => c.child_id === child.id && c.approved && childChoreIds.has(c.chore_id)).length;
        const total = childChores.length;
        const pct = total > 0 ? Math.min(100, (approved / total) * 100) : 0;
        const isComplete = total > 0 && approved >= total;
        const cls = isComplete ? "complete" : pct > 0 ? "partial" : "none";

        const isAdmin = !!(this.hass && this.hass.user && this.hass.user.is_admin);
        const outstanding = childChores.filter(c => {
          const doneToday = completions.filter(
            x => x.child_id === child.id && x.chore_id === c.id && !x.bonus_subtask_id
          ).length;
          return doneToday < (c.daily_limit || 1);
        });
        const isOpen = !!this._expanded[child.id];

        return html`
          <div class="child-tile ${isAdmin ? 'tm-expandable' : ''}">
            <div class="child-avatar">
              <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
            </div>
            <div class="child-tile-main"
              @click="${isAdmin ? () => { this._expanded = { ...this._expanded, [child.id]: !isOpen }; this.requestUpdate(); } : null}">
              <div class="child-tile-header">
                <span class="child-tile-name">${child.name}</span>
                <span class="points-pill">
                  <ha-icon icon="${pointsIcon}"></ha-icon>
                  ${child.points}
                </span>
              </div>
              <div class="progress-row">
                <div class="progress-bar">
                  <div class="progress-fill ${cls}" style="width: ${pct}%"></div>
                </div>
                <span class="progress-label">${approved}/${total}</span>
              </div>
              ${isAdmin && isOpen ? html`
                <div class="tm-outstanding" @click="${(e) => e.stopPropagation()}">
                  <div class="tm-outstanding-hdr">${this._t('common.complete_on_behalf_heading')}</div>
                  ${outstanding.length === 0 ? html`
                    <div class="tm-all-done">${this._t('common.complete_on_behalf_all_done')}</div>
                  ` : outstanding.map(c => {
                    const key = `behalf_${child.id}_${c.id}`;
                    const loading = !!this._loading[key];
                    return html`
                      <div class="tm-outstanding-row">
                        <span class="tm-outstanding-name">${c.name}</span>
                        <span class="tm-outstanding-pts">
                          <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:14px;"></ha-icon>${c.points}
                        </span>
                        <button class="btn-complete-behalf" ?disabled="${loading}"
                          title="${this._t('common.complete_on_behalf_tooltip', { name: child.name })}"
                          @click="${() => this._handleCompleteOnBehalf(c.id, child.id)}">
                          <ha-icon icon="mdi:check" style="--mdc-icon-size:16px;"></ha-icon>
                          ${this._t('common.complete_on_behalf')}
                        </button>
                      </div>
                    `;
                  })}
                </div>
              ` : ''}
            </div>
          </div>
        `;
      })}
    `;
  }

  _renderRotation(rotationChores, children, attrs) {
    if (!rotationChores.length) {
      return html`
        <div class="empty-section">
          <ha-icon icon="mdi:rotate-3d-variant"></ha-icon>
          <span>${this._t('dashboard.empty_rotation', {}, 'No rotating chores configured')}</span>
        </div>
      `;
    }
    const childById = Object.fromEntries((children || []).map(c => [c.id, c]));
    const groups = attrs.task_groups || [];
    const groupByChoreId = {};
    for (const g of groups) {
      for (const cid of (g.chore_ids || [])) {
        groupByChoreId[cid] = g;
      }
    }
    const unknown = this._t('dashboard.rotation_unassigned', {}, 'Nobody');
    return html`
      ${rotationChores.map(chore => {
        const currentChildId = chore.assignment_current_child_id || '';
        const currentChild = childById[currentChildId];
        const pool = (chore.assigned_to && chore.assigned_to.length) ? chore.assigned_to : (children || []).map(c => c.id);
        const poolSize = pool.length;
        const isSticky = groupByChoreId[chore.id] && groupByChoreId[chore.id].policy === 'sticky';
        const isStickyFollower = isSticky && groupByChoreId[chore.id].chore_ids[0] !== chore.id;
        const skipDisabled = poolSize <= 1 || isStickyFollower;
        const group = groupByChoreId[chore.id];
        const key = `skip_${chore.id}`;
        const loading = !!this._loading[key];
        return html`
          <div class="approval-item ${loading ? 'loading' : ''}">
            <div class="approval-child-avatar" style="background: linear-gradient(135deg, #16a085, #1abc9c);">
              <ha-icon icon="${currentChild?.avatar || 'mdi:rotate-3d-variant'}"></ha-icon>
            </div>
            <div class="approval-info">
              <span class="approval-chore">${chore.name}</span>
              <span class="approval-meta">
                <ha-icon icon="mdi:account" style="--mdc-icon-size: 14px;"></ha-icon>
                ${currentChild?.name || unknown}
                · <span>${chore.assignment_mode}</span>
                ${group ? html`· <span>${group.policy === 'sticky' ? '🔗' : '🔀'} ${group.name}</span>` : ''}
              </span>
            </div>
            <div class="approval-actions">
              <button
                class="btn-reject"
                title="${this._t('dashboard.rotation_skip_hint', {}, 'Skip current child and move to the next in rotation (today only)')}"
                ?disabled="${skipDisabled}"
                style="${skipDisabled ? 'opacity:0.4; cursor: not-allowed;' : ''}"
                @click="${() => this._handleSkip(chore.id)}"
              >
                <ha-icon icon="mdi:skip-next"></ha-icon>
              </button>
            </div>
          </div>
        `;
      })}
    `;
  }

  _renderApprovals(pending, children, chores, pointsIcon) {
    if (!pending.length) return html`
      <div class="empty-section">
        <ha-icon icon="mdi:check-all" style="color: #2ecc71;"></ha-icon>
        <span>${this._t('dashboard.empty_approvals')}</span>
      </div>
    `;

    const childMap = {};
    children.forEach(c => { childMap[c.id] = c; });
    const choreMap = {};
    chores.forEach(c => { choreMap[c.id] = c; });

    return html`
      ${pending.map(comp => {
        const child = childMap[comp.child_id];
        const chore = choreMap[comp.chore_id];
        const isLoading = this._loading[comp.completion_id];
        const time = new Date(comp.completed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

        return html`
          <div class="approval-item ${isLoading ? 'loading' : ''}">
            <div class="approval-child-avatar">
              <ha-icon icon="${child?.avatar || 'mdi:account-circle'}"></ha-icon>
            </div>
            <div class="approval-info">
              <div class="approval-chore">${comp.chore_name || chore?.name || this._t('common.unknown')}</div>
              <div class="approval-meta">
                <span>${child?.name || this._t('common.unknown')}</span>
                <span>•</span>
                <span>${time}</span>
                <span class="approval-points">
                  <ha-icon icon="${pointsIcon}"></ha-icon>
                  +${comp.points || chore?.points || 0}
                </span>
              </div>
            </div>
            <div class="approval-actions">
              <button class="btn-approve" @click="${() => this._handleApprove(comp.completion_id)}" title="${this._t('common.approve')}" aria-label="${this._t('common.approve')}">
                <ha-icon icon="mdi:check-bold"></ha-icon>
              </button>
              <button class="btn-reject" @click="${() => this._handleReject(comp.completion_id)}" title="${this._t('common.reject')}" aria-label="${this._t('common.reject')}">
                <ha-icon icon="mdi:close-thick"></ha-icon>
              </button>
            </div>
          </div>
        `;
      })}
    `;
  }

  _renderClaims(claims, pointsIcon) {
    if (!claims.length) return html`
      <div class="empty-section">
        <ha-icon icon="mdi:gift-outline" style="color: #9b59b6;"></ha-icon>
        <span>${this._t('dashboard.empty_claims')}</span>
      </div>
    `;

    return html`
      ${claims.map(claim => {
        const isLoading = this._loading[claim.claim_id];
        const time = new Date(claim.claimed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        return html`
          <div class="claim-item ${isLoading ? 'loading' : ''}">
            <div class="claim-icon-wrap">
              <ha-icon icon="${claim.reward_icon || 'mdi:gift'}"></ha-icon>
            </div>
            <div class="claim-info">
              <div class="claim-reward-name">${claim.reward_name}</div>
              <div class="claim-meta">
                ${claim.child_name} • ${time} •
                <span style="display:inline-flex;align-items:center;gap:2px;color:#e67e22;font-weight:600;">
                  <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:11px;color:#f1c40f;"></ha-icon>
                  ${claim.cost}
                </span>
              </div>
            </div>
            <div class="approval-actions">
              <button class="btn-approve" @click="${() => this._handleApproveReward(claim.claim_id)}" title="${this._t('common.approve')}" aria-label="${this._t('common.approve')}">
                <ha-icon icon="mdi:check-bold"></ha-icon>
              </button>
              <button class="btn-reject" @click="${() => this._handleRejectReward(claim.claim_id)}" title="${this._t('common.reject')}" aria-label="${this._t('common.reject')}">
                <ha-icon icon="mdi:close-thick"></ha-icon>
              </button>
            </div>
          </div>
        `;
      })}
    `;
  }

  _renderPoints(children, pointsIcon, pointsName) {
    const amount = this.config.quick_points_amount || 5;

    return html`
      ${children.map(child => html`
        <div class="quick-points-row">
          <div class="qp-avatar">
            <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
          </div>
          <span class="qp-name">${child.name}</span>
          <span class="qp-points">
            <ha-icon icon="${pointsIcon}"></ha-icon>
            ${child.points}
          </span>
          <div class="qp-actions">
            <button class="btn-remove" @click="${() => this._handlePoints(child.id, -amount)}" title="${this._t('dashboard.btn_remove_points_title', { amount, pointsName })}" aria-label="${this._t('dashboard.btn_remove_points_title', { amount, pointsName })}">
              <ha-icon icon="mdi:minus"></ha-icon>
            </button>
            <button class="btn-add" @click="${() => this._handlePoints(child.id, amount)}" title="${this._t('dashboard.btn_add_points_title', { amount, pointsName })}" aria-label="${this._t('dashboard.btn_add_points_title', { amount, pointsName })}">
              <ha-icon icon="mdi:plus"></ha-icon>
            </button>
          </div>
        </div>
      `)}
    `;
  }

  _notifyServiceError(service, error, notificationId) {
    console.error(`Failed to call ${service}:`, error);
    if (this.hass && this.hass.callService) {
      this.hass.callService("persistent_notification", "create", {
        title: this._t('approvals.error_title'),
        message: this._t('approvals.error_failed_service', {
          service: service.replace(/_/g, " "),
          message: error && error.message ? error.message : String(error),
        }),
        notification_id: notificationId,
      });
    }
  }

  async _handleApprove(completionId) {
    if (this._loading[completionId]) return;
    this._loading = { ...this._loading, [completionId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "approve_chore", { completion_id: completionId });
    } catch (e) {
      this._notifyServiceError("approve_chore", e, `taskmate_dashboard_approve_${completionId}`);
    } finally {
      this._loading = { ...this._loading, [completionId]: false };
      this.requestUpdate();
    }
  }

  async _handleReject(completionId) {
    if (this._loading[completionId]) return;
    this._loading = { ...this._loading, [completionId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "reject_chore", { completion_id: completionId });
    } catch (e) {
      this._notifyServiceError("reject_chore", e, `taskmate_dashboard_reject_${completionId}`);
    } finally {
      this._loading = { ...this._loading, [completionId]: false };
      this.requestUpdate();
    }
  }

  async _handleApproveReward(claimId) {
    if (this._loading[claimId]) return;
    this._loading = { ...this._loading, [claimId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "approve_reward", { claim_id: claimId });
    } catch (e) {
      this._notifyServiceError("approve_reward", e, `taskmate_dashboard_approve_reward_${claimId}`);
    } finally {
      this._loading = { ...this._loading, [claimId]: false };
      this.requestUpdate();
    }
  }

  async _handleRejectReward(claimId) {
    if (this._loading[claimId]) return;
    this._loading = { ...this._loading, [claimId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "reject_reward", { claim_id: claimId });
    } catch (e) {
      this._notifyServiceError("reject_reward", e, `taskmate_dashboard_reject_reward_${claimId}`);
    } finally {
      this._loading = { ...this._loading, [claimId]: false };
      this.requestUpdate();
    }
  }

  async _handleSkip(choreId) {
    const key = `skip_${choreId}`;
    this._loading = { ...this._loading, [key]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "skip_chore", { chore_id: choreId });
    } catch (e) {
      this._notifyServiceError("skip_chore", e, `taskmate_dashboard_skip_${choreId}`);
    } finally {
      this._loading = { ...this._loading, [key]: false };
      this.requestUpdate();
    }
  }

  async _handlePoints(childId, delta) {
    const key = `${childId}_${delta}`;
    this._loading = { ...this._loading, [key]: true };
    this.requestUpdate();
    const service = delta > 0 ? "add_points" : "remove_points";
    try {
      await this.hass.callService("taskmate", service, {
        child_id: childId,
        points: Math.abs(delta),
      });
    } catch (e) {
      this._notifyServiceError(service, e, `taskmate_dashboard_points_${key}`);
    } finally {
      this._loading = { ...this._loading, [key]: false };
      this.requestUpdate();
    }
  }

  async _handleCompleteOnBehalf(choreId, childId) {
    const key = `behalf_${childId}_${choreId}`;
    if (this._loading[key]) return;
    this._loading = { ...this._loading, [key]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "complete_chore", {
        chore_id: choreId,
        child_id: childId,
        as_parent: true,
      });
    } catch (e) {
      this._notifyServiceError("complete_chore", e, `taskmate_dashboard_behalf_${key}`);
    } finally {
      this._loading = { ...this._loading, [key]: false };
      this.requestUpdate();
    }
  }
}

class TaskMateParentDashboardCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
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

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _buildSchema() {
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      { name: 'quick_points_amount', selector: { number: { min: 1, max: 100, mode: 'box' } } },
      { name: 'show_claims', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('dashboard.editor.entity_label'),
      title: this._t('dashboard.editor.title_label'),
      quick_points_amount: this._t('dashboard.editor.quick_points_label'),
      show_claims: this._t('dashboard.editor.show_claims'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('dashboard.editor.entity_helper'),
      quick_points_amount: this._t('dashboard.editor.quick_points_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      quick_points_amount: this.config.quick_points_amount || 5,
      show_claims: this.config.show_claims !== false,
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
      ${this._renderColourPicker('header_color', '#c0392b')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, '#e67e22', '#27ae60', '#3498db', '#9b59b6', '#f1c40f', '#34495e'];
    const isActive = (c) => c.toLowerCase() === current.toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${this._t('common.editor.header_colour')}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current}
              @input=${(e) => this._update(key, e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current}"></span>
          </label>
          <span class="colour-hex">${current}</span>
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
            @click=${(e) => { e.preventDefault(); this._update(key, defaultValue); }}
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
      if (value === '' || value === null || value === undefined) {
        delete newConfig[key];
      } else if (key === 'show_claims' && value === true) {
        delete newConfig[key];
      } else if (key === 'quick_points_amount' && value === 5) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _update(key, value) {
    const cfg = { ...this.config, [key]: value };
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: cfg }, bubbles: true, composed: true }));
  }
}

customElements.define("taskmate-parent-dashboard-card", TaskMateParentDashboardCard);
customElements.define("taskmate-parent-dashboard-card-editor", TaskMateParentDashboardCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-parent-dashboard-card",
  name: "TaskMate Parent Dashboard",
  description: "Unified parent view with approvals, child progress, and quick point controls",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-parent-dashboard-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE PARENT DASHBOARD CARD %c v" + _tmVersion + " ",
  "background:#c0392b;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
