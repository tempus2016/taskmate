/**
 * TaskMate Weekly Summary Card
 * Current week at a glance: days completed, points per day as a bar chart,
 * rewards claimed this week, and a per-child breakdown.
 *
 * Version: 1.0.0
 * Last Updated: 2026-03-18
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateWeeklyCard extends LitElement {
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
        --wk-purple: #9b59b6;
        --wk-green: #2ecc71;
        --wk-orange: #e67e22;
        --wk-blue: #3498db;
        --wk-gold: #f1c40f;
        --wk-red: #e74c3c;
      }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #27ae60);
        color: white;
      }

      .header-content { display: flex; align-items: center; gap: 10px; }
      .header-icon { --mdc-icon-size: 28px; opacity: 0.9; }
      .header-title { font-size: 1.2rem; font-weight: 600; }
      .week-label {
        background: rgba(255,255,255,0.2);
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
      }

      .card-content {
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      /* Summary stats row */
      .stats-row {
        display: flex;
        gap: 10px;
      }

      .stat-card {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        padding: 12px 8px;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 12px;
      }

      .stat-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: var(--primary-text-color);
        line-height: 1;
      }

      .stat-value.green { color: var(--wk-green); }
      .stat-value.orange { color: var(--wk-orange); }
      .stat-value.purple { color: var(--wk-purple); }

      .stat-label {
        font-size: 0.68rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.4px;
        text-align: center;
      }

      /* Daily bar chart */
      .chart-section { }

      .section-label {
        font-size: 0.75rem;
        font-weight: 700;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 10px;
      }

      .bar-chart {
        display: flex;
        align-items: flex-end;
        gap: 6px;
        height: 80px;
      }

      .bar-col {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        height: 100%;
        justify-content: flex-end;
      }

      .bar-value {
        font-size: 0.68rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        min-height: 14px;
      }

      .bar-fill {
        width: 100%;
        border-radius: 4px 4px 0 0;
        min-height: 3px;
        transition: height 0.4s ease;
      }

      .bar-fill.today {
        background: linear-gradient(180deg, var(--wk-green) 0%, #27ae60 100%);
      }

      .bar-fill.past {
        background: linear-gradient(180deg, var(--wk-blue) 0%, #2980b9 100%);
      }

      .bar-fill.future {
        background: var(--divider-color, #e8e8e8);
      }

      .bar-fill.zero {
        background: var(--divider-color, #e8e8e8);
        min-height: 3px !important;
        height: 3px !important;
      }

      .bar-day {
        font-size: 0.7rem;
        font-weight: 600;
        color: var(--secondary-text-color);
      }

      .bar-day.today {
        color: var(--wk-green);
        font-weight: 800;
      }

      /* Per-child breakdown */
      .children-section { }

      .child-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 0;
        border-bottom: 1px solid var(--divider-color, #f0f0f0);
      }

      .child-row:last-child { border-bottom: none; }

      .child-avatar {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--wk-purple), #a569bd);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .child-avatar ha-icon { --mdc-icon-size: 20px; color: white; }

      .child-info { flex: 1; min-width: 0; }

      .child-name {
        font-weight: 600;
        font-size: 0.9rem;
        color: var(--primary-text-color);
      }

      .child-week-stats {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 2px;
        font-size: 0.78rem;
        color: var(--secondary-text-color);
        flex-wrap: wrap;
      }

      .child-week-stats span { display: flex; align-items: center; gap: 3px; }
      .child-week-stats ha-icon { --mdc-icon-size: 13px; }

      .week-progress-bar {
        flex: 1;
        height: 6px;
        background: var(--divider-color, #e0e0e0);
        border-radius: 3px;
        overflow: hidden;
        min-width: 40px;
      }

      .week-progress-fill {
        height: 100%;
        border-radius: 3px;
        background: linear-gradient(90deg, var(--wk-green), #27ae60);
      }

      /* Error / empty */
      .error-state, .empty-state {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 40px 20px;
        color: var(--secondary-text-color); text-align: center;
      }

      .error-state { color: var(--error-color, #f44336); }
      .error-state ha-icon, .empty-state ha-icon { --mdc-icon-size: 48px; margin-bottom: 12px; opacity: 0.5; }
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Please define an entity");
    this.config = {
      title: "This Week",
      child_id: null,
            header_color: '#27ae60',
    ...config,
    };
  }

  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("taskmate-weekly-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "This Week" };
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

    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    let children = entity.attributes.children || [];
    const chores = entity.attributes.chores || [];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Stars";

    // Use recent_completions (last 50 all-time) for full week view
    let allCompletions = [...(entity.attributes.recent_completions || entity.attributes.todays_completions || [])];
    const seen = new Set();
    allCompletions = allCompletions.filter(comp => {
      if (seen.has(comp.completion_id)) return false;
      seen.add(comp.completion_id); return true;
    });

    if (this.config.child_id) {
      children = children.filter(c => c.id === this.config.child_id);
      allCompletions = allCompletions.filter(c => c.child_id === this.config.child_id);
    }

    // Build week dates (Mon–Sun or Sun–Sat based on HA locale)
    const weekDays = this._getWeekDays(tz);
    const todayKey = new Date().toLocaleDateString("en-CA", { timeZone: tz });

    // Group completions by day
    const completionsByDay = {};
    allCompletions.forEach(c => {
      if (!c.completed_at) return;
      const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
      if (!completionsByDay[day]) completionsByDay[day] = [];
      completionsByDay[day].push(c);
    });

    // Only show completions within this week
    const weekCompletions = allCompletions.filter(c => {
      if (!c.completed_at) return false;
      const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
      return weekDays.some(d => d.key === day);
    });

    // Build chore points lookup — completions don't carry points directly
    const chorePointsMap = {};
    chores.forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });

    // Only count approved completions for all stats
    const approvedWeekCompletions = weekCompletions.filter(c => c.approved);

    const weekPoints = approvedWeekCompletions
      .reduce((sum, c) => sum + (c.points !== undefined ? c.points : (chorePointsMap[c.chore_id] || 0)), 0);
    const weekChores = approvedWeekCompletions.length;
    const daysActive = new Set(approvedWeekCompletions.map(c =>
      new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz })
    )).size;

    // Bar chart also uses approved completions only
    const approvedCompletionsByDay = {};
    approvedWeekCompletions.forEach(c => {
      if (!c.completed_at) return;
      const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
      if (!approvedCompletionsByDay[day]) approvedCompletionsByDay[day] = [];
      approvedCompletionsByDay[day].push(c);
    });

    // Max completions in a day for chart scale
    const maxPerDay = Math.max(1, ...weekDays.map(d => (approvedCompletionsByDay[d.key] || []).length));
    const weekLabel = this._getWeekLabel(weekDays, tz);

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#27ae60'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:calendar-week"></ha-icon>
            <span class="header-title">${this.config.title}</span>
          </div>
          <span class="week-label">${weekLabel}</span>
        </div>

        <div class="card-content">
          <!-- Summary stats -->
          <div class="stats-row">
            <div class="stat-card">
              <span class="stat-value green">${weekChores}</span>
              <span class="stat-label">Chores</span>
            </div>
            <div class="stat-card">
              <span class="stat-value orange">${weekPoints}</span>
              <span class="stat-label">${pointsName}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value purple">${daysActive}/7</span>
              <span class="stat-label">Days Active</span>
            </div>
          </div>

          <!-- Daily bar chart -->
          <div class="chart-section">
            <div class="section-label">Chores Per Day</div>
            <div class="bar-chart">
              ${weekDays.map(day => {
                const count = (approvedCompletionsByDay[day.key] || []).length;
                const isToday = day.key === todayKey;
                const isFuture = day.key > todayKey;
                const heightPct = isFuture ? 0 : Math.round((count / maxPerDay) * 60);
                const barClass = isFuture ? "future" : isToday ? "today" : count === 0 ? "zero" : "past";
                return html`
                  <div class="bar-col">
                    <span class="bar-value">${!isFuture && count > 0 ? count : ''}</span>
                    <div class="bar-fill ${barClass}" style="height: ${isFuture ? 3 : Math.max(3, heightPct)}px"></div>
                    <span class="bar-day ${isToday ? 'today' : ''}">${day.short}</span>
                  </div>
                `;
              })}
            </div>
          </div>

          <!-- Per-child breakdown -->
          ${children.length > 0 ? html`
            <div class="children-section">
              <div class="section-label">Children This Week</div>
              ${children.map(child => {
                // Only count approved completions for all per-child stats
                const childApprovedCompletions = approvedWeekCompletions.filter(c => c.child_id === child.id);
                const childPoints = childApprovedCompletions
                  .reduce((s, comp) => s + (comp.points !== undefined ? comp.points : (chorePointsMap[comp.chore_id] || 0)), 0);
                const childChoreCount = childApprovedCompletions.length;
                const childDaysActive = new Set(childApprovedCompletions.map(c =>
                  new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz })
                )).size;

                // Avatar now included directly in children array from the overview sensor
                const avatar = child.avatar || "mdi:account-circle";

                const pct = Math.min((childDaysActive / 7) * 100, 100);

                return html`
                  <div class="child-row">
                    <div class="child-avatar"><ha-icon icon="${avatar}"></ha-icon></div>
                    <div class="child-info">
                      <div class="child-name">${child.name}</div>
                      <div class="child-week-stats">
                        <span><ha-icon icon="mdi:checkbox-marked-circle" style="color:var(--wk-green)"></ha-icon>${childChoreCount} chores</span>
                        <span><ha-icon icon="${pointsIcon}" style="color:var(--wk-gold)"></ha-icon>${childPoints} ${pointsName}</span>
                        <span><ha-icon icon="mdi:calendar-check" style="color:var(--wk-blue)"></ha-icon>${childDaysActive}/7 days</span>
                      </div>
                    </div>
                    <div class="week-progress-bar" title="${childDaysActive} of 7 days active">
                      <div class="week-progress-fill" style="width: ${pct}%"></div>
                    </div>
                  </div>
                `;
              })}
            </div>
          ` : ''}
        </div>
      </ha-card>
    `;
  }

  _getWeekDays(tz) {
    const today = new Date();
    const todayDay = today.getDay(); // 0=Sun
    // Start week on Monday
    const mondayOffset = (todayDay === 0 ? -6 : 1 - todayDay);
    const monday = new Date(today);
    monday.setDate(today.getDate() + mondayOffset);

    const days = [];
    const shortNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      days.push({
        key: d.toLocaleDateString("en-CA", { timeZone: tz }),
        short: shortNames[i],
        date: d,
      });
    }
    return days;
  }

  _getWeekLabel(weekDays, tz) {
    const first = weekDays[0].date;
    const last = weekDays[6].date;
    const fmt = { month: "short", day: "numeric" };
    return `${first.toLocaleDateString(undefined, fmt)} – ${last.toLocaleDateString(undefined, fmt)}`;
  }
}

// Card Editor
class TaskMateWeeklyCardEditor extends LitElement {
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
        placeholder="This Week"
      ></ha-textfield>
      <div class="form-row">
        <label class="form-label">Filter by Child (optional)</label>
        <select class="form-select" @change="${e => this._updateConfig('child_id', e.target.value || null)}">
          <option value="" ?selected="${!this.config.child_id}">All Children</option>
          ${children.map(c => html`<option value="${c.id}" ?selected="${this.config.child_id === c.id}">${c.name}</option>`)}
        </select>
        <span class="form-helper">Show weekly summary for a specific child only</span>
      </div>
        <span class="field-helper">Card header background colour</span>
      </div>
      <div class="field-row">
        <label class="field-label">Header Colour</label>
        <div style="display:flex;align-items:center;gap:10px;">
          <input
            type="color"
            .value=${this.config.header_color || '#27ae60'}
            @input=${e => this._updateConfig('header_color', e.target.value)}
            style="width:48px;height:36px;padding:2px;border:1px solid var(--divider-color,#e0e0e0);border-radius:6px;cursor:pointer;"
          />
          <span style="font-size:13px;color:var(--secondary-text-color);">${this.config.header_color || '#27ae60'}</span>
          <button
            style="font-size:11px;color:var(--secondary-text-color);background:none;border:1px solid var(--divider-color,#e0e0e0);border-radius:4px;padding:3px 8px;cursor:pointer;"
            @click=${() => this._updateConfig('header_color', '#27ae60')}
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

customElements.define("taskmate-weekly-card", TaskMateWeeklyCard);
customElements.define("taskmate-weekly-card-editor", TaskMateWeeklyCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-weekly-card",
  name: "TaskMate Weekly Summary",
  description: "Week at a glance — chores, points, and daily bar chart",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-weekly-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE WEEKLY CARD %c v" + _tmVersion + " ",
  "background:#27ae60;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
