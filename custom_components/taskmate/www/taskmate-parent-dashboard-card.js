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
    };
  }

  constructor() {
    super();
    this._loading = {};
    this._activeSection = "overview";
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

      /* ── Empty state ── */
      .empty-section {
        display: flex; flex-direction: column; align-items: center;
        padding: 24px 16px; text-align: center; gap: 8px;
        color: var(--secondary-text-color);
      }

      .empty-section ha-icon { --mdc-icon-size: 40px; opacity: 0.35; }
      .empty-section span { font-size: 0.9rem; }

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
    if (!entity) return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>Entity not found: ${this.config.entity}</div></div></ha-card>`;
    if (entity.state === "unavailable" || entity.state === "unknown") return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>TaskMate unavailable</div></div></ha-card>`;

    const children = entity.attributes.children || [];
    const chores = entity.attributes.chores || [];
    const completions = entity.attributes.todays_completions || [];
    const pendingCompletions = completions.filter(c => !c.approved);
    const pendingRewardClaims = entity.attributes.pending_reward_claims || [];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Points";
    const totalPending = pendingCompletions.length + pendingRewardClaims.length;

    const tabs = [
      { id: "overview", label: "Overview", icon: "mdi:view-dashboard" },
      { id: "approvals", label: "Approvals", icon: "mdi:check-circle", count: pendingCompletions.length },
      { id: "points", label: "Points", icon: "mdi:star-plus" },
    ];

    if (this.config.show_claims) {
      tabs.splice(2, 0, { id: "claims", label: "Claims", icon: "mdi:gift", count: pendingRewardClaims.length });
    }

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#c0392b'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:shield-account"></ha-icon>
            <span class="header-title">${this.config.title}</span>
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
          ${this._activeSection === "approvals" ? this._renderApprovals(pendingCompletions, children, chores, pointsIcon) : ''}
          ${this._activeSection === "claims" ? this._renderClaims(pendingRewardClaims, pointsIcon) : ''}
          ${this._activeSection === "points" ? this._renderPoints(children, pointsIcon, pointsName) : ''}
        </div>
      </ha-card>
    `;
  }

  _renderOverview(children, chores, completions, pointsIcon, pointsName) {
    if (!children.length) return html`<div class="empty-section"><ha-icon icon="mdi:account-group"></ha-icon><span>No children found</span></div>`;

    return html`
      ${children.map(child => {
        const childChores = chores.filter(c => {
          const at = c.assigned_to || [];
          return at.length === 0 || at.includes(child.id);
        });
        const approved = completions.filter(c => c.child_id === child.id && c.approved).length;
        const total = childChores.length;
        const pct = total > 0 ? Math.min(100, (approved / total) * 100) : 0;
        const isComplete = total > 0 && approved >= total;
        const cls = isComplete ? "complete" : pct > 0 ? "partial" : "none";

        return html`
          <div class="child-tile">
            <div class="child-avatar">
              <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
            </div>
            <div class="child-tile-main">
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
        <span>All caught up! No pending approvals.</span>
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
              <div class="approval-chore">${comp.chore_name || chore?.name || 'Unknown chore'}</div>
              <div class="approval-meta">
                <span>${child?.name || 'Unknown'}</span>
                <span>•</span>
                <span>${time}</span>
                <span class="approval-points">
                  <ha-icon icon="${pointsIcon}"></ha-icon>
                  +${comp.points || chore?.points || 0}
                </span>
              </div>
            </div>
            <div class="approval-actions">
              <button class="btn-approve" @click="${() => this._handleApprove(comp.completion_id)}" title="Approve">
                <ha-icon icon="mdi:check-bold"></ha-icon>
              </button>
              <button class="btn-reject" @click="${() => this._handleReject(comp.completion_id)}" title="Reject">
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
        <span>No pending reward claims.</span>
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
              <button class="btn-approve" @click="${() => this._handleApproveReward(claim.claim_id)}" title="Approve">
                <ha-icon icon="mdi:check-bold"></ha-icon>
              </button>
              <button class="btn-reject" @click="${() => this._handleRejectReward(claim.claim_id)}" title="Reject">
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
            <button class="btn-remove" @click="${() => this._handlePoints(child.id, -amount)}" title="Remove ${amount} ${pointsName}">
              <ha-icon icon="mdi:minus"></ha-icon>
            </button>
            <button class="btn-add" @click="${() => this._handlePoints(child.id, amount)}" title="Add ${amount} ${pointsName}">
              <ha-icon icon="mdi:plus"></ha-icon>
            </button>
          </div>
        </div>
      `)}
    `;
  }

  async _handleApprove(completionId) {
    this._loading = { ...this._loading, [completionId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "approve_chore", { completion_id: completionId });
    } catch (e) {
      console.error("Failed to approve chore:", e);
    } finally {
      this._loading = { ...this._loading, [completionId]: false };
      this.requestUpdate();
    }
  }

  async _handleReject(completionId) {
    this._loading = { ...this._loading, [completionId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "reject_chore", { completion_id: completionId });
    } catch (e) {
      console.error("Failed to reject chore:", e);
    } finally {
      this._loading = { ...this._loading, [completionId]: false };
      this.requestUpdate();
    }
  }

  async _handleApproveReward(claimId) {
    this._loading = { ...this._loading, [claimId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "approve_reward", { claim_id: claimId });
    } catch (e) {
      console.error("Failed to approve reward:", e);
    } finally {
      this._loading = { ...this._loading, [claimId]: false };
      this.requestUpdate();
    }
  }

  async _handleRejectReward(claimId) {
    this._loading = { ...this._loading, [claimId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "reject_reward", { claim_id: claimId });
    } catch (e) {
      console.error("Failed to reject reward:", e);
    } finally {
      this._loading = { ...this._loading, [claimId]: false };
      this.requestUpdate();
    }
  }

  async _handlePoints(childId, delta) {
    const key = `${childId}_${delta}`;
    this._loading = { ...this._loading, [key]: true };
    this.requestUpdate();
    try {
      const service = delta > 0 ? "add_points" : "remove_points";
      await this.hass.callService("taskmate", service, {
        child_id: childId,
        points: Math.abs(delta),
      });
    } catch (e) {
      console.error("Failed to adjust points:", e);
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
      :host { display: block; padding: 4px 0; }
      ha-textfield { width: 100%; margin-bottom: 8px; }
      .field-row { margin-bottom: 16px; }
      .field-label { display: block; font-size: 12px; font-weight: 500; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; padding: 0 4px; }
      .field-helper { display: block; font-size: 11px; color: var(--secondary-text-color); margin-top: 5px; padding: 0 4px; }
      .check-row { display: flex; align-items: center; gap: 12px; padding: 10px 12px; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; background: var(--card-background-color, #fff); cursor: pointer; user-select: none; margin-bottom: 8px; }
      .check-row input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; flex-shrink: 0; accent-color: var(--primary-color); margin: 0; }
      .check-label { font-size: 14px; color: var(--primary-text-color); flex: 1; }
    `;
  }

  setConfig(config) { this.config = config; }

  render() {
    if (!this.hass || !this.config) return html``;
    return html`
      <ha-textfield
        label="Overview Entity"
        .value="${this.config.entity || ''}"
        @change="${e => this._update('entity', e.target.value)}"
        helper="The TaskMate overview sensor"
        helperPersistent
        placeholder="sensor.taskmate_overview"
      ></ha-textfield>

      <ha-textfield
        label="Card Title"
        .value="${this.config.title || ''}"
        @change="${e => this._update('title', e.target.value)}"
        placeholder="Parent Dashboard"
      ></ha-textfield>

      <ha-textfield
        label="Quick Points Amount"
        type="number"
        .value="${String(this.config.quick_points_amount || 5)}"
        @change="${e => this._update('quick_points_amount', parseInt(e.target.value) || 5)}"
        helper="How many points the +/- buttons add or remove"
        helperPersistent
      ></ha-textfield>

      <label class="check-row">
        <input type="checkbox"
          ?checked="${this.config.show_claims !== false}"
          
          @change="${e => this._update('show_claims', e.target.checked)}"
        />
        <span class="check-label">Show Reward Claims tab</span>
      </label>
      <div class="field-row">
        <label class="field-label">Header Colour</label>
        <div style="display:flex;align-items:center;gap:10px;">
          <input
            type="color"
            .value="${this.config.header_color ||  + default_colour + }"
            @input="${e => this._updateConfig('header_color', e.target.value)}"
            style="width:48px;height:36px;padding:2px;border:1px solid var(--divider-color,#e0e0e0);border-radius:6px;cursor:pointer;"
          />
          <span style="font-size:13px;color:var(--secondary-text-color);">
            ${this.config.header_color ||  + default_colour + }
          </span>
          <button
            style="font-size:11px;color:var(--secondary-text-color);background:none;border:1px solid var(--divider-color,#e0e0e0);border-radius:4px;padding:3px 8px;cursor:pointer;"
            @click="${() => this._updateConfig('header_color',  + default_colour + )}"
          >Reset</button>
        </div>
        <span class="field-helper">Card header background colour</span>
      </div>
    `;
  }

  _update(key, value) {
    const cfg = { ...this.config, [key]: value };
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
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

console.info("%c TASKMATE-PARENT-DASHBOARD-CARD %c v1.0.0 ", "background:#2c3e50;color:white;font-weight:bold;border-radius:4px 0 0 4px;", "background:#e74c3c;color:white;font-weight:bold;border-radius:0 4px 4px 0;");
