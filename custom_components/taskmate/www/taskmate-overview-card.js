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
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;
    }

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const chores = attrs.chores || [];
    const completions = [...(attrs.todays_completions || [])];
    const chorePointsMap = {};
    chores.forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || "Stars";

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
      return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:account-group"></ha-icon><div>${this._t('common.no_children')}</div></div></ha-card>`;
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
              ${this._t('overview.pending_count', { count: pendingApprovals })}
            </div>
          ` : ''}
        </div>

        <div class="card-content">
          ${children.map(child => this._renderChildTile(child, chores, completions, pointsIcon, pointsName))}
        </div>

        <div class="summary-footer">
          <div class="summary-stat">
            <span class="summary-stat-value">${children.length}</span>
            <span class="summary-stat-label">${this._t('overview.footer_children')}</span>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-stat">
            <span class="summary-stat-value">${totalCompletedToday}</span>
            <span class="summary-stat-label">${this._t('overview.footer_done_today')}</span>
          </div>
          <div class="summary-divider"></div>
          <div class="summary-stat">
            <span class="summary-stat-value">${totalPoints}</span>
            <span class="summary-stat-label">${this._t('overview.footer_total_points', { pointsName })}</span>
          </div>
          ${pendingApprovals > 0 ? html`
            <div class="summary-divider"></div>
            <div class="summary-stat">
              <span class="summary-stat-value" style="color: var(--ov-red);">${pendingApprovals}</span>
              <span class="summary-stat-label">${this._t('common.pending')}</span>
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }

  _renderChildTile(child, chores, completions, pointsIcon, pointsName) {
    // Avatar now included directly in children array from the overview sensor
    const avatar = child.avatar || "mdi:account-circle";

    // Get today's day of week from sensor (e.g. "monday")
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity)) || {};
    const todayDow = attrs.today_day_of_week ||
      new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();
    const availability = attrs.chore_availability || {};

    // Chores assigned to this child, due today, and available (recurrence window open)
    const childChores = chores.filter(c => {
      // Assignment check
      const at = Array.isArray(c.assigned_to) ? c.assigned_to.map(String) : [];
      const assigned = at.length === 0 || at.includes(String(child.id));
      if (!assigned) return false;

      // Mode A: due days check
      if (c.schedule_mode !== 'recurring') {
        const dueDays = Array.isArray(c.due_days) ? c.due_days : [];
        if (dueDays.length > 0 && !dueDays.includes(todayDow)) return false;
      }

      // Mode B: recurrence availability check
      if (c.schedule_mode === 'recurring') {
        const perChild = availability[c.id];
        if (perChild && perChild[child.id] === false) return false;
      }

      return true;
    });

    // All completions today for this child
    const childCompletions = completions.filter(c => c.child_id === child.id);
    // Only approved completions count, and only for chores relevant today
    const childChoreIds = new Set(childChores.map(c => c.id));
    const childApprovedCompletions = childCompletions.filter(c => c.approved && childChoreIds.has(c.chore_id));
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
            <div style="font-size:0.8rem;color:var(--secondary-text-color);opacity:0.7;">${this._t('common.no_chores_today')}</div>
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
      { name: 'approvals_entity', selector: { entity: { domain: 'sensor' } } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('overview.editor.entity_label'),
      title: this._t('overview.editor.title_label'),
      approvals_entity: this._t('overview.editor.approvals_entity_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('overview.editor.entity_helper'),
      approvals_entity: this._t('overview.editor.approvals_entity_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      approvals_entity: this.config.approvals_entity || '',
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
      ${this._renderColourPicker('header_color', '#8e44ad')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, '#e67e22', '#27ae60', '#3498db', '#f1c40f', '#e74c3c', '#34495e'];
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
      if (value === '' || value === null || value === undefined) delete newConfig[key];
      else newConfig[key] = value;
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (!value) delete newConfig[key];
    this.dispatchEvent(new CustomEvent('config-changed', {
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

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-overview-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE OVERVIEW CARD %c v" + _tmVersion + " ",
  "background:#8e44ad;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
