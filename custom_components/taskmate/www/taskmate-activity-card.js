/**
 * TaskMate Activity Feed Card
 * Scrollable timeline of recent events — completions, approvals, points, rewards.
 *
 * Version: 1.0.0
 * Last Updated: 2026-03-18
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
    };
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
      }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #2471a3);
        color: white;
      }

      .header-content { display: flex; align-items: center; gap: 10px; }
      .header-icon { --mdc-icon-size: 28px; opacity: 0.9; }
      .header-title { font-size: 1.2rem; font-weight: 600; }
      .event-count {
        background: rgba(255,255,255,0.2);
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
      }

      .feed-container {
        max-height: 480px;
        overflow-y: auto;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 0;
      }

      /* Date group header */
      .date-group { margin-bottom: 4px; }

      .date-label {
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.8px;
        padding: 8px 4px 4px;
      }

      /* Activity item */
      .activity-item {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 10px 4px;
        border-bottom: 1px solid var(--divider-color, #f0f0f0);
        position: relative;
      }

      .activity-item:last-child { border-bottom: none; }

      .activity-icon {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        margin-top: 2px;
      }

      .activity-icon ha-icon { --mdc-icon-size: 18px; color: white; }

      .activity-icon.chore { background: var(--act-blue); }
      .activity-icon.approved { background: var(--act-green); }
      .activity-icon.rejected { background: var(--act-red); }
      .activity-icon.points_added { background: var(--act-green); }
      .activity-icon.points_removed { background: var(--act-red); }
      .activity-icon.reward { background: var(--act-purple); }
      .activity-icon.reward_claimed { background: var(--act-orange); }
      .activity-icon.reward_approved { background: var(--act-purple); }
      .activity-icon.pending { background: var(--act-orange); }

      .activity-reason {
        font-size: 0.78rem;
        color: var(--secondary-text-color);
        font-style: italic;
        margin-top: 2px;
      }

      .activity-body { flex: 1; min-width: 0; }

      .activity-title {
        font-size: 0.9rem;
        font-weight: 500;
        color: var(--primary-text-color);
        line-height: 1.3;
      }

      .activity-title strong { color: var(--act-purple); }

      .activity-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 3px;
        flex-wrap: wrap;
      }

      .activity-time {
        font-size: 0.75rem;
        color: var(--secondary-text-color);
      }

      .activity-points {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--act-orange);
      }

      .activity-points ha-icon { --mdc-icon-size: 12px; color: var(--act-gold); }

      .activity-status {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.72rem;
        font-weight: 600;
        padding: 1px 6px;
        border-radius: 8px;
      }

      .activity-status.pending {
        background: rgba(230,126,34,0.15);
        color: var(--act-orange);
      }

      .activity-status.approved {
        background: rgba(46,204,113,0.15);
        color: var(--act-green);
      }

      .activity-status.rejected {
        background: rgba(231,76,60,0.15);
        color: var(--act-red);
      }

      /* Empty / error */
      .empty-state, .error-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        color: var(--secondary-text-color);
        text-align: center;
      }

      .error-state { color: var(--error-color, #f44336); }
      .empty-state ha-icon, .error-state ha-icon { --mdc-icon-size: 48px; margin-bottom: 12px; opacity: 0.5; }
      .empty-state .message { font-size: 1rem; color: var(--primary-text-color); }
      .empty-state .submessage { font-size: 0.85rem; margin-top: 4px; }
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Please define an entity");
    this.config = {
      title: "Activity",
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

  render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>Entity not found: ${this.config.entity}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>TaskMate is unavailable</div></div></ha-card>`;
    }

    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const children = entity.attributes.children || [];
    const chores = entity.attributes.chores || [];

    // Build lookup maps
    const childNames = {};
    children.forEach(ch => { childNames[ch.id] = ch.name; });
    const chorePointsMap = {};
    chores.forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });
    const choreNamesMap = {};
    chores.forEach(ch => { choreNamesMap[ch.id] = ch.name; });

    // Use recent_completions (last 50 all-time) if available, fall back to today only
    let completions = [...(entity.attributes.recent_completions || entity.attributes.todays_completions || [])];

    // Deduplicate by completion_id
    const seen = new Set();
    completions = completions.filter(comp => {
      if (seen.has(comp.completion_id)) return false;
      seen.add(comp.completion_id);
      return true;
    });

    // Merge in manual points transactions
    const transactions = (entity.attributes.recent_transactions || []).map(t => ({
      ...t,
      // Normalise to a single timestamp field for sorting
      completed_at: t.created_at,
    }));

    let allEvents = [...completions, ...transactions];

    // Filter by child if configured
    if (this.config.child_id) {
      allEvents = allEvents.filter(e => e.child_id === this.config.child_id);
    }

    // Sort by timestamp descending
    allEvents.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at));

    // Limit
    const maxItems = this.config.max_items || 30;
    const events = allEvents.slice(0, maxItems);

    if (events.length === 0) {
      return html`
        <ha-card>
          <div class="card-header">
            <div class="header-content">
              <ha-icon class="header-icon" icon="mdi:timeline-clock"></ha-icon>
              <span class="header-title">${this.config.title}</span>
            </div>
          </div>
          <div class="empty-state">
            <ha-icon icon="mdi:timeline-clock-outline"></ha-icon>
            <div class="message">No activity yet</div>
            <div class="submessage">Completed chores will appear here</div>
          </div>
        </ha-card>
      `;
    }

    // Group by day
    const groups = this._groupByDay(events);

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#2471a3'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:timeline-clock"></ha-icon>
            <span class="header-title">${this.config.title}</span>
          </div>
          <span class="event-count">${events.length} events</span>
        </div>
        <div class="feed-container">
          ${groups.map(([dayLabel, items]) => html`
            <div class="date-group">
              <div class="date-label">${dayLabel}</div>
              ${items.map(item => this._renderItem(item, childNames, pointsIcon, chorePointsMap))}
            </div>
          `)}
        </div>
      </ha-card>
    `;
  }

  _renderItem(item, childNames, pointsIcon, chorePointsMap) {
    const childName = childNames[item.child_id] || item.child_name || "Unknown";
    const type = item.type || "chore";
    const time = this._formatTime(new Date(item.completed_at));

    // Points transactions
    if (type === "points_added" || type === "points_removed") {
      const isAdd = type === "points_added";
      const pts = Math.abs(item.points || 0);
      return html`
        <div class="activity-item">
          <div class="activity-icon ${type}">
            <ha-icon icon="${isAdd ? 'mdi:star-plus' : 'mdi:star-minus'}"></ha-icon>
          </div>
          <div class="activity-body">
            <div class="activity-title">
              <strong>${childName}</strong>
              ${isAdd ? ' received' : ' lost'}
              <strong> ${pts}</strong>
              ${item.reason ? html` — <em>${item.reason}</em>` : ' points manually'}
            </div>
            <div class="activity-meta">
              <span class="activity-time">${time}</span>
              <span class="activity-points" style="${isAdd ? '' : 'color: var(--act-red);'}">
                <ha-icon icon="${pointsIcon}"></ha-icon>
                ${isAdd ? '+' : '-'}${pts}
              </span>
            </div>
          </div>
        </div>
      `;
    }

    // Reward claim events
    if (type === "reward_claimed" || type === "reward_approved") {
      const pts = Math.abs(item.points || 0);
      const isPending = type === "reward_claimed" && !item.approved;
      return html`
        <div class="activity-item">
          <div class="activity-icon ${type}">
            <ha-icon icon="${isPending ? 'mdi:gift-outline' : 'mdi:gift'}"></ha-icon>
          </div>
          <div class="activity-body">
            <div class="activity-title">
              <strong>${childName}</strong>
              ${isPending ? ' claimed' : ' redeemed'}
              <strong> ${item.reward_name || 'a reward'}</strong>
            </div>
            <div class="activity-meta">
              <span class="activity-time">${time}</span>
              ${pts ? html`
                <span class="activity-points" style="color: var(--act-red);">
                  <ha-icon icon="${pointsIcon}"></ha-icon>
                  -${pts}
                </span>
              ` : ''}
              <span class="activity-status ${isPending ? 'pending' : 'approved'}">
                ${isPending ? 'awaiting approval' : 'approved'}
              </span>
            </div>
          </div>
        </div>
      `;
    }

    // Chore completions and rewards
    const status = item.approved ? "approved" : item.rejected ? "rejected" : "pending";
    const iconMap = {
      chore: { icon: "mdi:checkbox-marked-circle", cls: status === "approved" ? "approved" : status === "rejected" ? "rejected" : "chore" },
      reward: { icon: "mdi:gift", cls: "reward" },
    };
    const { icon, cls } = iconMap[type] || iconMap.chore;

    const choreName = item.chore_name || (chorePointsMap && item.chore_id ? '' : 'a chore');
    const titleMap = {
      chore: html`<strong>${childName}</strong> completed <strong>${choreName || 'a chore'}</strong>`,
      reward: html`<strong>${childName}</strong> claimed <strong>${item.reward_name || 'a reward'}</strong>`,
    };

    const pts = item.points !== undefined ? item.points : (chorePointsMap?.[item.chore_id] || 0);

    return html`
      <div class="activity-item">
        <div class="activity-icon ${cls}">
          <ha-icon icon="${icon}"></ha-icon>
        </div>
        <div class="activity-body">
          <div class="activity-title">${titleMap[type] || titleMap.chore}</div>
          <div class="activity-meta">
            <span class="activity-time">${time}</span>
            ${pts ? html`
              <span class="activity-points">
                <ha-icon icon="${pointsIcon}"></ha-icon>
                +${pts}
              </span>
            ` : ''}
            ${type === 'chore' ? html`
              <span class="activity-status ${status}">${status}</span>
            ` : ''}
          </div>
        </div>
      </div>
    `;
  }

  _groupByDay(items) {
    const groups = new Map();
    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const now = new Date();

    items.forEach(item => {
      const date = new Date(item.completed_at);
      const key = date.toLocaleDateString("en-CA", { timeZone: tz });
      const nowKey = now.toLocaleDateString("en-CA", { timeZone: tz });
      const yesterday = new Date(now); yesterday.setDate(yesterday.getDate() - 1);
      const yKey = yesterday.toLocaleDateString("en-CA", { timeZone: tz });

      let label;
      if (key === nowKey) label = "Today";
      else if (key === yKey) label = "Yesterday";
      else label = date.toLocaleDateString(undefined, { timeZone: tz, month: "short", day: "numeric", weekday: "short" });

      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(item);
    });

    return [...groups.entries()];
  }

  _formatTime(date) {
    return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
}

// Card Editor
class TaskMateActivityCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-textfield { width: 100%; margin-bottom: 16px; }
      .form-row { margin-bottom: 16px; }
      .form-label {
        display: block; font-size: 0.85rem; font-weight: 500;
        color: var(--primary-text-color); margin-bottom: 6px; padding: 0 2px;
      }
      .form-select {
        width: 100%; padding: 10px 12px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 1rem; box-sizing: border-box; cursor: pointer; appearance: auto;
      }
      .form-select:focus { outline: none; border-color: var(--primary-color); }
      .form-helper { display: block; font-size: 0.78rem; color: var(--secondary-text-color); margin-top: 4px; padding: 0 2px; }
    `;
  }

  setConfig(config) { this.config = config; }

  render() {
    if (!this.hass || !this.config) return html``;
    const entity = this.config.entity ? this.hass.states[this.config.entity] : null;
    const children = entity?.attributes?.children || [];

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
        placeholder="Activity"
      ></ha-textfield>
      <div class="form-row">
        <label class="form-label">Filter by Child (optional)</label>
        <select class="form-select" @change="${e => this._updateConfig('child_id', e.target.value || null)}">
          <option value="" ?selected="${!this.config.child_id}">All Children</option>
          ${children.map(c => html`<option value="${c.id}" ?selected="${this.config.child_id === c.id}">${c.name}</option>`)}
        </select>
        <span class="form-helper">Only show activity for this child</span>
      </div>
      <ha-textfield
        label="Max Items"
        type="number"
        .value="${String(this.config.max_items || 30)}"
        @change="${e => this._updateConfig('max_items', parseInt(e.target.value) || 30)}"
        helper="Maximum number of events to show (default: 30)"
        helperPersistent
      ></ha-textfield>
        <span class="field-helper">Card header background colour</span>
      </div>
      <div class="field-row">
        <label class="field-label">Header Colour</label>
        <div style="display:flex;align-items:center;gap:10px;">
          <input
            type="color"
            .value=${this.config.header_color || '#2471a3'}
            @input=${e => this._updateConfig('header_color', e.target.value)}
            style="width:48px;height:36px;padding:2px;border:1px solid var(--divider-color,#e0e0e0);border-radius:6px;cursor:pointer;"
          />
          <span style="font-size:13px;color:var(--secondary-text-color);">${this.config.header_color || '#2471a3'}</span>
          <button
            style="font-size:11px;color:var(--secondary-text-color);background:none;border:1px solid var(--divider-color,#e0e0e0);border-radius:4px;padding:3px 8px;cursor:pointer;"
            @click=${() => this._updateConfig('header_color', '#2471a3')}
          >Reset</button>
        </div>
        <span class="field-helper">Card header background colour</span>
      </div>
    `;
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

console.info(
  "%c TASKMATE-ACTIVITY-CARD %c v1.0.0 ",
  "background: #3498db; color: white; font-weight: bold; border-radius: 4px 0 0 4px;",
  "background: #2ecc71; color: white; font-weight: bold; border-radius: 0 4px 4px 0;"
);
