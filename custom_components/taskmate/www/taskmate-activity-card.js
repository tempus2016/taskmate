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
      }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, var(--primary-color));
        color: var(--text-primary-color, #fff);
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
        max-height: 350px;
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

      .activity-icon ha-icon { --mdc-icon-size: 18px; color: var(--text-primary-color, #fff); }

      .activity-icon.chore { background: var(--primary-color); }
      .activity-icon.approved { background: var(--success-color, #4caf50); }
      .activity-icon.rejected { background: var(--error-color, #db4437); }
      .activity-icon.points_added { background: var(--success-color, #4caf50); }
      .activity-icon.points_removed { background: var(--error-color, #db4437); }
      .activity-icon.reward { background: var(--primary-color); }
      .activity-icon.reward_claimed { background: var(--warning-color, #ff9800); }
      .activity-icon.reward_approved { background: var(--primary-color); }
      .activity-icon.pending { background: var(--warning-color, #ff9800); }

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

      .activity-title strong { color: var(--primary-color); }

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
        color: var(--warning-color, #ff9800);
      }

      .activity-points ha-icon { --mdc-icon-size: 12px; color: var(--warning-color, #ff9800); }

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
        background: rgba(var(--rgb-warning-color, 255,152,0),0.15);
        color: var(--warning-color, #ff9800);
      }

      .activity-status.approved {
        background: rgba(var(--rgb-success-color, 76,175,80),0.15);
        color: var(--success-color, #4caf50);
      }

      .activity-status.rejected {
        background: rgba(var(--rgb-error-color, 219,68,55),0.15);
        color: var(--error-color, #db4437);
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
      title: "",
      max_items: 30,
      child_id: null,
            header_color: null,
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
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;
    }

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const pointsIcon = attrs.points_icon || "mdi:star";
    const children = attrs.children || [];
    const chores = attrs.chores || [];

    // Build lookup maps
    const childNames = {};
    children.forEach(ch => { childNames[ch.id] = ch.name; });
    const chorePointsMap = {};
    chores.forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });
    const choreNamesMap = {};
    chores.forEach(ch => { choreNamesMap[ch.id] = ch.name; });

    // Use recent_completions (last 50 all-time) if available, fall back to today only
    let completions = [...(attrs.recent_completions || attrs.todays_completions || [])];

    // Deduplicate by completion_id
    const seen = new Set();
    completions = completions.filter(comp => {
      if (seen.has(comp.completion_id)) return false;
      seen.add(comp.completion_id);
      return true;
    });

    // Merge in manual points transactions
    const transactions = (attrs.recent_transactions || []).map(t => ({
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
              <span class="header-title">${this.config.title || this._t('activity.default_title')}</span>
            </div>
          </div>
          <div class="empty-state">
            <ha-icon icon="mdi:timeline-clock-outline"></ha-icon>
            <div class="message">${this._t('activity.no_activity_yet')}</div>
            <div class="submessage">${this._t('activity.completed_chores_will_appear')}</div>
          </div>
        </ha-card>
      `;
    }

    // Group by day
    const groups = this._groupByDay(events);

    return html`
      <ha-card>
        ${this.config.header_color ? html`<style>:host { --taskmate-header-bg: ${this.config.header_color}; }</style>` : ''}
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:timeline-clock"></ha-icon>
            <span class="header-title">${this.config.title || this._t('activity.default_title')}</span>
          </div>
          <span class="event-count">${this._t('activity.events_count', { count: events.length })}</span>
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
    const childName = childNames[item.child_id] || item.child_name || this._t('activity.unknown_child');
    const type = item.type || "chore";
    const time = this._formatTime(new Date(item.completed_at));

    // Points transactions
    if (type === "points_added" || type === "points_removed") {
      const isAdd = type === "points_added";
      const pts = Math.abs(item.points || 0);
      // Distinguish "spent" (rewards/pool) from "lost" (penalty) for negative txns
      // so a child sees a celebration of spending instead of a punishment colour.
      const reason = item.reason || '';
      const isPenalty = reason.startsWith('Penalty:');
      const isPoolAllocation = reason.startsWith('Allocated to pool:');
      const isSpend = !isAdd && !isPenalty && isPoolAllocation;
      let verb;
      let pointsColour;
      if (isAdd) {
        verb = this._t('activity.received');
        pointsColour = '';
      } else if (isSpend) {
        verb = this._t('activity.spent');
        pointsColour = 'color: var(--warning-color, #ff9800);';
      } else {
        verb = this._t('activity.lost');
        pointsColour = 'color: var(--error-color, #db4437);';
      }
      const displayReason = this._translateReason(item.reason);
      return html`
        <div class="activity-item">
          <div class="activity-icon ${type}">
            <ha-icon icon="${isAdd ? 'mdi:star-plus' : 'mdi:star-minus'}"></ha-icon>
          </div>
          <div class="activity-body">
            <div class="activity-title">
              <strong>${childName}</strong>
              ${' '}${verb}
              <strong> ${pts}</strong>
              ${item.reason ? html` — <em>${displayReason}</em>` : ` ${this._t('activity.points_manually')}`}
            </div>
            <div class="activity-meta">
              <span class="activity-time">${time}</span>
              <span class="activity-points" style="${pointsColour}">
                <ha-icon icon="${pointsIcon}"></ha-icon>
                ${isAdd ? '+' : '-'}${pts}
              </span>
            </div>
          </div>
        </div>
      `;
    }

    // Reward claim events — these are purchases, not losses, so render in
    // the "spent" colour even though points are deducted.
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
              ${isPending ? ` ${this._t('activity.claimed')}` : ` ${this._t('activity.redeemed')}`}
              <strong> ${item.reward_name || this._t('activity.a_reward')}</strong>
            </div>
            <div class="activity-meta">
              <span class="activity-time">${time}</span>
              ${pts ? html`
                <span class="activity-points" style="color: var(--warning-color, #ff9800);">
                  <ha-icon icon="${pointsIcon}"></ha-icon>
                  -${pts}
                </span>
              ` : ''}
              <span class="activity-status ${isPending ? 'pending' : 'approved'}">
                ${isPending ? this._t('activity.awaiting_approval') : this._t('common.approved')}
              </span>
            </div>
          </div>
        </div>
      `;
    }

    // Chore completions and rewards
    const status = item.approved ? "approved" : item.rejected ? "rejected" : "pending";
    const iconMap = {
      chore: { icon: "mdi:checkbox-marked-circle", cls: status === "approved" ? "approved" : status === "rejected" ? "rejected" : "pending" },
      reward: { icon: "mdi:gift", cls: "reward" },
    };
    const { icon, cls } = iconMap[type] || iconMap.chore;

    const choreName = item.chore_name || (chorePointsMap && item.chore_id ? '' : this._t('activity.a_chore'));
    const titleMap = {
      chore: html`<strong>${childName}</strong> ${this._t('activity.completed')} <strong>${choreName || this._t('activity.a_chore')}</strong>`,
      reward: html`<strong>${childName}</strong> ${this._t('activity.claimed')} <strong>${item.reward_name || this._t('activity.a_reward')}</strong>`,
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
              <span class="activity-status ${status}">${this._t('common.' + status)}</span>
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
      if (key === nowKey) label = this._t('common.today');
      else if (key === yKey) label = this._t('common.yesterday');
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
