/**
 * TaskMate Streak & Achievement Card
 * Shows each child's consecutive day streak and milestone badges.
 * Streaks are calculated client-side from completion data.
 *
 * Version: 1.0.0
 * Last Updated: 2026-03-18
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateStreakCard extends LitElement {
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
        --str-purple: #9b59b6;
        --str-gold: #f1c40f;
        --str-orange: #e67e22;
        --str-green: #2ecc71;
        --str-red: #e74c3c;
        --str-fire: #ff6b35;
      }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #e74c3c);
        color: white;
      }

      .header-content { display: flex; align-items: center; gap: 10px; }
      .header-icon { --mdc-icon-size: 28px; opacity: 0.9; }
      .header-title { font-size: 1.2rem; font-weight: 600; }

      .card-content {
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 14px;
      }

      /* Child streak tile */
      .streak-tile {
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 14px;
        overflow: hidden;
      }

      .streak-header {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 14px 16px 10px;
      }

      .child-avatar {
        width: 42px;
        height: 42px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--str-purple) 0%, #a569bd 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .child-avatar ha-icon { --mdc-icon-size: 26px; color: white; }

      .streak-info { flex: 1; }
      .child-name {
        font-weight: 600;
        font-size: 1rem;
        color: var(--primary-text-color);
      }

      .streak-count-row {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-top: 2px;
      }

      .streak-number {
        font-size: 1.5rem;
        font-weight: 800;
        line-height: 1;
      }

      .streak-number.hot { color: var(--str-fire); }
      .streak-number.warm { color: var(--str-orange); }
      .streak-number.cold { color: var(--secondary-text-color); }

      .streak-label {
        font-size: 0.8rem;
        color: var(--secondary-text-color);
        font-weight: 500;
      }

      .streak-emoji { font-size: 1.4rem; }

      /* Streak bar - visual days */
      .streak-days {
        display: flex;
        gap: 4px;
        padding: 0 16px 14px;
        flex-wrap: wrap;
      }

      .day-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        transition: transform 0.2s ease;
      }

      .day-dot.active { background: var(--str-fire); }
      .day-dot.today-active { background: var(--str-green); transform: scale(1.3); }
      .day-dot.inactive { background: var(--divider-color, #e0e0e0); }

      /* Achievements */
      .achievements-section {
        padding: 0 16px 14px;
        border-top: 1px solid var(--divider-color, #f0f0f0);
        padding-top: 10px;
      }

      .achievements-label {
        font-size: 0.72rem;
        font-weight: 700;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
      }

      .badges {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .badge {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 3px;
        padding: 8px 10px;
        border-radius: 10px;
        background: var(--secondary-background-color, #f5f5f5);
        min-width: 56px;
        transition: transform 0.15s ease;
      }

      .badge:hover { transform: scale(1.05); }

      .badge.earned {
        background: linear-gradient(135deg, rgba(241,196,15,0.2), rgba(230,126,34,0.2));
        border: 1px solid rgba(241,196,15,0.4);
      }

      .badge.locked { opacity: 0.35; filter: grayscale(1); }

      .badge-emoji { font-size: 1.5rem; }
      .badge-name {
        font-size: 0.65rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        text-align: center;
        line-height: 1.2;
      }

      .badge.earned .badge-name { color: var(--str-orange); }

      /* Empty / error */
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
      title: "Streaks & Achievements",
      child_id: null,
      streak_days_shown: 14,
            header_color: '#e74c3c',
    ...config,
    };
  }

  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("taskmate-streak-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Streaks & Achievements" };
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

    let children = entity.attributes.children || [];
    // Use recent_completions (all-time history, last 50) for streak/achievement calculation
    const completions = [...(entity.attributes.recent_completions || entity.attributes.todays_completions || [])];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const chores = entity.attributes.chores || [];

    if (this.config.child_id) {
      children = children.filter(c => c.id === this.config.child_id);
    }

    if (children.length === 0) {
      return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:account-group"></ha-icon><div>No children found</div></div></ha-card>`;
    }

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#e74c3c'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:fire"></ha-icon>
            <span class="header-title">${this.config.title}</span>
          </div>
        </div>
        <div class="card-content">
          ${children.map(child => this._renderStreakTile(child, completions, chores, pointsIcon, entity))}
        </div>
      </ha-card>
    `;
  }

  _renderStreakTile(child, completions, chores, pointsIcon, entity_ref) {
    const childCompletions = completions.filter(c => c.child_id === child.id);
    // Use backend-calculated streak if available, fall back to client calculation
    const streak = child.current_streak !== undefined
      ? child.current_streak
      : this._calculateStreak(childCompletions, chores, child.id);
    const daysShown = this.config.streak_days_shown || 14;
    const dayDots = this._buildDayDots(childCompletions, chores, child.id, daysShown);
    const achievements = this._getAchievements(child, childCompletions, streak, entity_ref);

    // Avatar now included directly in children array from the overview sensor
    const avatar = child.avatar || "mdi:account-circle";

    const streakClass = streak >= 7 ? "hot" : streak >= 3 ? "warm" : "cold";
    const streakEmoji = streak >= 14 ? "🔥🔥" : streak >= 7 ? "🔥" : streak >= 3 ? "⚡" : streak >= 1 ? "✨" : "💤";

    return html`
      <div class="streak-tile">
        <div class="streak-header">
          <div class="child-avatar"><ha-icon icon="${avatar}"></ha-icon></div>
          <div class="streak-info">
            <div class="child-name">${child.name}</div>
            <div class="streak-count-row">
              <span class="streak-number ${streakClass}">${streak}</span>
              <span class="streak-label">day streak</span>
              <span class="streak-emoji">${streakEmoji}</span>
            </div>
          </div>
        </div>

        <div class="streak-days">
          ${dayDots.map(dot => html`
            <div class="day-dot ${dot.cssClass}" title="${dot.label}"></div>
          `)}
        </div>

        ${achievements.length > 0 ? html`
          <div class="achievements-section">
            <div class="achievements-label">Achievements</div>
            <div class="badges">
              ${achievements.map(a => html`
                <div class="badge ${a.earned ? 'earned' : 'locked'}" title="${a.description}">
                  <span class="badge-emoji">${a.emoji}</span>
                  <span class="badge-name">${a.name}</span>
                </div>
              `)}
            </div>
          </div>
        ` : ''}
      </div>
    `;
  }

  _calculateStreak(completions, chores, childId) {
    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;

    // Build set of unique days with at least one completion
    const daysWithCompletion = new Set();
    completions.forEach(c => {
      if (!c.completed_at) return;
      const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
      daysWithCompletion.add(day);
    });

    // Walk backwards from today counting consecutive days
    let streak = 0;
    const today = new Date();
    for (let i = 0; i < 365; i++) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toLocaleDateString("en-CA", { timeZone: tz });
      if (daysWithCompletion.has(key)) {
        streak++;
      } else {
        break;
      }
    }
    return streak;
  }

  _buildDayDots(completions, chores, childId, days) {
    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const daysWithCompletion = new Set();
    completions.forEach(c => {
      if (!c.completed_at) return;
      const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
      daysWithCompletion.add(day);
    });

    const dots = [];
    const today = new Date();
    const todayKey = today.toLocaleDateString("en-CA", { timeZone: tz });

    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toLocaleDateString("en-CA", { timeZone: tz });
      const active = daysWithCompletion.has(key);
      const isToday = key === todayKey;
      dots.push({
        cssClass: active ? (isToday ? "today-active" : "active") : "inactive",
        label: d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }),
      });
    }
    return dots;
  }

  _getAchievements(child, completions, streak, entity_ref) {
    // Prefer backend-tracked totals over client-visible completions
    const totalCompletions = child.total_chores_completed !== undefined
      ? child.total_chores_completed
      : (entity_ref?.attributes?.total_completions_all_time || completions.filter(comp => comp.child_id === child.id).length);
    const totalPoints = (child.total_points_earned !== undefined ? child.total_points_earned : child.points) || 0;
    const bestStreak = child.best_streak || streak || 0;

    const milestones = [
      { id: "first", name: "First!", emoji: "🌟", description: "Complete your first chore", earned: totalCompletions >= 1 },
      { id: "ten", name: "10 Done", emoji: "🏅", description: "Complete 10 chores", earned: totalCompletions >= 10 },
      { id: "fifty", name: "50 Done", emoji: "🥈", description: "Complete 50 chores", earned: totalCompletions >= 50 },
      { id: "hundred", name: "100 Done", emoji: "🥇", description: "Complete 100 chores", earned: totalCompletions >= 100 },
      { id: "streak3", name: "3 Days", emoji: "⚡", description: "3 day streak", earned: bestStreak >= 3 },
      { id: "streak7", name: "Week!", emoji: "🔥", description: "7 day streak", earned: bestStreak >= 7 },
      { id: "streak14", name: "2 Weeks", emoji: "🔥🔥", description: "14 day streak", earned: bestStreak >= 14 },
      { id: "streak30", name: "Month!", emoji: "💎", description: "30 day streak", earned: bestStreak >= 30 },
      { id: "points50", name: "50 ⭐", emoji: "🎯", description: "Earn 50 points total", earned: totalPoints >= 50 },
      { id: "points100", name: "100 ⭐", emoji: "💰", description: "Earn 100 points total", earned: totalPoints >= 100 },
    ];

    // Show earned ones + next locked milestone
    const earned = milestones.filter(m => m.earned);
    const nextLocked = milestones.find(m => !m.earned);
    return nextLocked ? [...earned, nextLocked] : earned;
  }
}

// Card Editor
class TaskMateStreakCardEditor extends LitElement {
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
        placeholder="Streaks & Achievements"
      ></ha-textfield>
      <div class="form-row">
        <label class="form-label">Filter by Child (optional)</label>
        <select class="form-select" @change="${e => this._updateConfig('child_id', e.target.value || null)}">
          <option value="" ?selected="${!this.config.child_id}">All Children</option>
          ${children.map(c => html`<option value="${c.id}" ?selected="${this.config.child_id === c.id}">${c.name}</option>`)}
        </select>
        <span class="form-helper">Show streak for a specific child only</span>
      </div>
      <ha-textfield
        label="Days Shown in Bar"
        type="number"
        .value="${String(this.config.streak_days_shown || 14)}"
        @change="${e => this._updateConfig('streak_days_shown', parseInt(e.target.value) || 14)}"
        helper="How many days of dots to show (default: 14)"
        helperPersistent
      ></ha-textfield>
        <span class="field-helper">Card header background colour</span>
      </div>
      <div class="field-row">
        <label class="field-label">Header Colour</label>
        <div style="display:flex;align-items:center;gap:10px;">
          <input
            type="color"
            .value=${this.config.header_color || '#e74c3c'}
            @input=${e => this._updateConfig('header_color', e.target.value)}
            style="width:48px;height:36px;padding:2px;border:1px solid var(--divider-color,#e0e0e0);border-radius:6px;cursor:pointer;"
          />
          <span style="font-size:13px;color:var(--secondary-text-color);">${this.config.header_color || '#e74c3c'}</span>
          <button
            style="font-size:11px;color:var(--secondary-text-color);background:none;border:1px solid var(--divider-color,#e0e0e0);border-radius:4px;padding:3px 8px;cursor:pointer;"
            @click=${() => this._updateConfig('header_color', '#e74c3c')}
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

customElements.define("taskmate-streak-card", TaskMateStreakCard);
customElements.define("taskmate-streak-card-editor", TaskMateStreakCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-streak-card",
  name: "TaskMate Streaks & Achievements",
  description: "Consecutive day streaks and milestone badges for each child",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-streak-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE STREAK CARD %c v" + _tmVersion + " ",
  "background:#e74c3c;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
