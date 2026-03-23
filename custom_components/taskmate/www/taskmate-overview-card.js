/**
 * TaskMate Overview Card
 * At-a-glance parent dashboard showing all children's points,
 * today's chore completion progress, and pending approvals.
 *
 * Version: 1.0.0
 * Last Updated: 2026-03-18
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateOverviewCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        --ov-purple: #9b59b6;
        --ov-purple-light: #a569bd;
        --ov-gold: #f1c40f;
        --ov-green: #2ecc71;
        --ov-orange: #e67e22;
        --ov-red: #e74c3c;
        --ov-blue: #3498db;
      }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #8e44ad);
        color: white;
      }

      .header-content { display: flex; align-items: center; gap: 10px; }
      .header-icon { --mdc-icon-size: 28px; opacity: 0.9; }
      .header-title { font-size: 1.2rem; font-weight: 600; }

      .pending-badge {
        background: var(--ov-red);
        color: white;
        border-radius: 12px;
        padding: 3px 10px;
        font-size: 0.85rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 4px;
        animation: badge-pulse 2s ease-in-out infinite;
      }

      @keyframes badge-pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(231,76,60,0.4); }
        50% { box-shadow: 0 0 0 5px rgba(231,76,60,0); }
      }

      .pending-badge ha-icon { --mdc-icon-size: 14px; }

      .card-content {
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }

      /* Child tile */
      .child-tile {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 14px 16px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 14px;
        transition: box-shadow 0.2s ease;
      }

      .child-tile:hover {
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
      }

      .child-avatar {
        width: 46px;
        height: 46px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--ov-purple) 0%, var(--ov-purple-light) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .child-avatar ha-icon { --mdc-icon-size: 28px; color: white; }

      .child-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }

      .child-name-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }

      .child-name {
        font-weight: 600;
        font-size: 1.05rem;
        color: var(--primary-text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .points-pill {
        display: flex;
        align-items: center;
        gap: 4px;
        background: rgba(241,196,15,0.15);
        color: var(--ov-orange);
        border-radius: 10px;
        padding: 3px 8px;
        font-size: 0.85rem;
        font-weight: 700;
        flex-shrink: 0;
      }

      .points-pill ha-icon { --mdc-icon-size: 14px; color: var(--ov-gold); }

      .pending-points-pill {
        display: flex;
        align-items: center;
        gap: 3px;
        background: rgba(230,126,34,0.12);
        color: var(--ov-orange);
        border-radius: 10px;
        padding: 2px 7px;
        font-size: 0.78rem;
        font-weight: 600;
        flex-shrink: 0;
        opacity: 0.85;
      }

      .pending-points-pill ha-icon { --mdc-icon-size: 12px; }

      /* Chore progress bar */
      .progress-row {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .progress-bar-bg {
        flex: 1;
        height: 8px;
        background: var(--divider-color, #e0e0e0);
        border-radius: 4px;
        overflow: hidden;
      }

      .progress-bar-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.4s ease;
      }

      .progress-bar-fill.complete {
        background: linear-gradient(90deg, var(--ov-green), #27ae60);
      }

      .progress-bar-fill.partial {
        background: linear-gradient(90deg, var(--ov-blue), #2980b9);
      }

      .progress-bar-fill.none {
        background: var(--divider-color, #e0e0e0);
        width: 0 !important;
      }

      .progress-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        white-space: nowrap;
        min-width: 36px;
        text-align: right;
      }

      .progress-label.complete { color: var(--ov-green); }

      /* Approval item in tile */
      .approvals-chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: rgba(231,76,60,0.12);
        color: var(--ov-red);
        border-radius: 10px;
        padding: 2px 8px;
        font-size: 0.78rem;
        font-weight: 600;
      }

      .approvals-chip ha-icon { --mdc-icon-size: 13px; }

      /* Footer summary row */
      .summary-footer {
        display: flex;
        align-items: center;
        justify-content: space-around;
        padding: 10px 16px;
        background: var(--secondary-background-color, #f5f5f5);
        border-top: 1px solid var(--divider-color, #e0e0e0);
        gap: 8px;
      }

      .summary-stat {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
      }

      .summary-stat-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--primary-text-color);
      }

      .summary-stat-label {
        font-size: 0.7rem;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .summary-divider {
        width: 1px;
        height: 32px;
        background: var(--divider-color, #e0e0e0);
      }

      /* States */
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
      .error-state ha-icon, .empty-state ha-icon { --mdc-icon-size: 48px; margin-bottom: 12px; }
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Please define an entity");
    this.config = {
      title: "TaskMate",
      approvals_entity: null,
            header_color: '#8e44ad',
    ...config,
    };
  }

  getCardSize() { return 3; }
  static getConfigElement() { return document.createElement("taskmate-overview-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "TaskMate" };
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>Entity not found: ${this.config.entity}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>TaskMate is unavailable</div></div></ha-card>`;
    }

    const children = entity.attributes.children || [];
    const chores = entity.attributes.chores || [];
    const completions = [...(entity.attributes.todays_completions || [])];
    const chorePointsMap = {};
    chores.forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Stars";

    // Pending approvals — from approvals entity if configured, else from completions
    let pendingApprovals = 0;
    if (this.config.approvals_entity) {
      const appEntity = this.hass.states[this.config.approvals_entity];
      pendingApprovals = appEntity?.attributes?.chore_completions?.length || 0;
    } else {
      pendingApprovals = completions.filter(c => !c.approved).length;
    }

    // Total points across all children
    const totalPoints = children.reduce((sum, c) => sum + (c.points || 0), 0);
    // Only count approved completions
    const totalCompletedToday = completions.filter(c => c.approved).length;

    if (children.length === 0) {
      return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:account-group"></ha-icon><div>No children found</div></div></ha-card>`;
    }

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#8e44ad'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:home-heart"></ha-icon>
            <span class="header-title">${this.config.title}</span>
          </div>
          ${pendingApprovals > 0 ? html`
            <div class="pending-badge">
              <ha-icon icon="mdi:clock-alert"></ha-icon>
              ${pendingApprovals} pending
            </div>
          ` : ''}
        </div>

        <div class="card-content">
          ${children.map(child => this._renderChildTile(child, chores, completions, pointsIcon, pointsName))}
        </div>

        <div class="summary-footer">
          <div class="summary-stat">
            <span class="summary-stat-value">${children.length}</span>
            <span class="summary-stat-label">Children</span>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-stat">
            <span class="summary-stat-value">${totalCompletedToday}</span>
            <span class="summary-stat-label">Done Today</span>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-stat">
            <span class="summary-stat-value">${totalPoints}</span>
            <span class="summary-stat-label">Total ${pointsName}</span>
          </div>
          ${pendingApprovals > 0 ? html`
            <div class="summary-divider"></div>
            <div class="summary-stat">
              <span class="summary-stat-value" style="color: var(--ov-red);">${pendingApprovals}</span>
              <span class="summary-stat-label">Pending</span>
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }

  _renderChildTile(child, chores, completions, pointsIcon, pointsName) {
    // Avatar now included directly in children array from the overview sensor
    const avatar = child.avatar || "mdi:account-circle";

    // Chores assigned to this child
    const childChores = chores.filter(c => {
      const at = Array.isArray(c.assigned_to) ? c.assigned_to.map(String) : [];
      return at.length === 0 || at.includes(String(child.id));
    });

    // All completions today for this child
    const childCompletions = completions.filter(c => c.child_id === child.id);
    // Only approved completions count toward progress
    const childApprovedCompletions = childCompletions.filter(c => c.approved);
    const completedCount = childApprovedCompletions.length;
    const totalChores = childChores.length;
    const percentage = totalChores > 0 ? Math.min((completedCount / totalChores) * 100, 100) : 0;
    const isComplete = totalChores > 0 && completedCount >= totalChores;

    // Pending approvals for this child
    const childPending = childCompletions.filter(c => !c.approved).length;

    return html`
      <div class="child-tile">
        <div class="child-avatar">
          <ha-icon icon="${avatar}"></ha-icon>
        </div>
        <div class="child-main">
          <div class="child-name-row">
            <span class="child-name">${child.name}</span>
            <div style="display:flex;gap:5px;align-items:center;flex-shrink:0;">
              ${child.pending_points > 0 ? html`
                <span class="pending-points-pill">
                  <ha-icon icon="mdi:timer-sand"></ha-icon>+${child.pending_points}
                </span>
              ` : ''}
              <span class="points-pill">
                <ha-icon icon="${pointsIcon}"></ha-icon>
                ${child.points}
              </span>
              ${childPending > 0 ? html`
                <span class="approvals-chip">
                  <ha-icon icon="mdi:clock-alert"></ha-icon>${childPending}
                </span>
              ` : ''}
            </div>
          </div>
          ${totalChores > 0 ? html`
            <div class="progress-row">
              <div class="progress-bar-bg">
                <div
                  class="progress-bar-fill ${isComplete ? 'complete' : percentage > 0 ? 'partial' : 'none'}"
                  style="width: ${percentage}%"
                ></div>
              </div>
              <span class="progress-label ${isComplete ? 'complete' : ''}">
                ${completedCount}/${totalChores}
              </span>
            </div>
          ` : html`
            <div style="font-size:0.8rem;color:var(--secondary-text-color);opacity:0.7;">No chores today</div>
          `}
        </div>
      </div>
    `;
  }
}

// Card Editor
class TaskMateOverviewCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-textfield { width: 100%; margin-bottom: 16px; }
    `;
  }

  setConfig(config) { this.config = config; }

  render() {
    if (!this.hass || !this.config) return html``;
    return html`
      <ha-textfield
        label="Overview Entity"
        .value="${this.config.entity || ""}"
        @change="${e => this._updateConfig('entity', e.target.value)}"
        helper="The TaskMate overview sensor entity"
        helperPersistent
        placeholder="sensor.taskmate_overview"
      ></ha-textfield>
      <ha-textfield
        label="Title"
        .value="${this.config.title || ""}"
        @change="${e => this._updateConfig('title', e.target.value)}"
        placeholder="TaskMate"
      ></ha-textfield>
      <ha-textfield
        label="Approvals Entity (optional)"
        .value="${this.config.approvals_entity || ""}"
        @change="${e => this._updateConfig('approvals_entity', e.target.value)}"
        helper="sensor.pending_approvals — for accurate pending count"
        helperPersistent
        placeholder="sensor.pending_approvals"
      ></ha-textfield>
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

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (!value) delete newConfig[key];
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

customElements.define("taskmate-overview-card", TaskMateOverviewCard);
customElements.define("taskmate-overview-card-editor", TaskMateOverviewCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-overview-card",
  name: "TaskMate Overview",
  description: "At-a-glance parent dashboard for all children",
  preview: true,
});

console.info(
  "%c TASKMATE-OVERVIEW-CARD %c v1.0.0 ",
  "background: #9b59b6; color: white; font-weight: bold; border-radius: 4px 0 0 4px;",
  "background: #2ecc71; color: white; font-weight: bold; border-radius: 0 4px 4px 0;"
);
