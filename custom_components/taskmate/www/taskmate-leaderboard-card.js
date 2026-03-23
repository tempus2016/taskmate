/**
 * TaskMate Leaderboard Card
 * Competitive multi-child ranking showing points, streaks, and weekly activity.
 * Adapts gracefully for single-child households (shows personal bests instead).
 *
 * Version: 1.0.0
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const RANK_COLOURS = ["#f1c40f", "#bdc3c7", "#cd7f32", "#9b59b6", "#3498db"];
const RANK_LABELS = ["🥇", "🥈", "🥉", "4th", "5th"];

class TaskMateLeaderboardCard extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-card { overflow: hidden; }

      .card-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #b7950b);
        color: white; gap: 12px;
      }

      .header-content { display: flex; align-items: center; gap: 10px; min-width: 0; }
      .header-icon { --mdc-icon-size: 26px; opacity: 0.9; flex-shrink: 0; }
      .header-title { font-size: 1.1rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

      .period-badge {
        background: rgba(255,255,255,0.15);
        border-radius: 10px;
        padding: 3px 10px;
        font-size: 0.78rem;
        font-weight: 600;
        flex-shrink: 0;
      }

      .card-content { padding: 14px; display: flex; flex-direction: column; gap: 10px; }

      /* Rank row */
      .rank-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 14px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 14px;
        transition: box-shadow 0.2s;
        position: relative;
        overflow: hidden;
      }

      .rank-row:hover { box-shadow: 0 3px 12px rgba(0,0,0,0.08); }

      .rank-row.first {
        border-color: #f1c40f;
        background: linear-gradient(135deg, rgba(241,196,15,0.06) 0%, var(--card-background-color, #fff) 100%);
      }

      .rank-row.second {
        border-color: #bdc3c7;
        background: linear-gradient(135deg, rgba(189,195,199,0.06) 0%, var(--card-background-color, #fff) 100%);
      }

      .rank-row.third {
        border-color: #cd7f32;
        background: linear-gradient(135deg, rgba(205,127,50,0.06) 0%, var(--card-background-color, #fff) 100%);
      }

      .rank-badge {
        font-size: 1.6rem;
        line-height: 1;
        flex-shrink: 0;
        width: 36px;
        text-align: center;
      }

      .rank-number {
        font-size: 1rem;
        font-weight: 700;
        color: var(--secondary-text-color);
        text-align: center;
        width: 36px;
        flex-shrink: 0;
      }

      .child-avatar {
        width: 44px; height: 44px; min-width: 44px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0;
      }

      .child-avatar ha-icon { --mdc-icon-size: 26px; color: white; }

      .rank-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }

      .rank-name {
        font-size: 1rem; font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }

      .rank-stats {
        display: flex; align-items: center; flex-wrap: wrap;
        gap: 8px; font-size: 0.78rem; color: var(--secondary-text-color);
      }

      .stat-chip {
        display: flex; align-items: center; gap: 3px;
        font-size: 0.75rem; color: var(--secondary-text-color);
      }

      .stat-chip ha-icon { --mdc-icon-size: 13px; }

      .rank-score {
        text-align: right; flex-shrink: 0;
        display: flex; flex-direction: column; align-items: flex-end; gap: 2px;
      }

      .score-value {
        font-size: 1.4rem; font-weight: 800;
        line-height: 1;
      }

      .score-label {
        font-size: 0.65rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.06em;
        color: var(--secondary-text-color);
      }

      /* Tie indicator */
      .tie-line {
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--divider-color, #e0e0e0), transparent);
        margin: -4px 0;
        position: relative;
      }

      .tie-line::after {
        content: 'TIE';
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        background: var(--secondary-background-color, #f5f5f5);
        padding: 0 6px;
        font-size: 0.65rem; font-weight: 700;
        color: var(--secondary-text-color);
        letter-spacing: 0.1em;
      }

      /* Solo mode (1 child) */
      .solo-header {
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 0 4px;
        margin-bottom: 4px;
      }

      .personal-best-row {
        display: flex; align-items: center; gap: 10px;
        padding: 10px 14px;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 10px;
      }

      .pb-icon { --mdc-icon-size: 20px; }
      .pb-label { flex: 1; font-size: 0.88rem; color: var(--primary-text-color); }
      .pb-value { font-size: 0.95rem; font-weight: 700; color: var(--primary-text-color); }

      /* Footer */
      .card-footer {
        padding: 10px 18px;
        background: var(--secondary-background-color, #f5f5f5);
        border-top: 1px solid var(--divider-color, #e0e0e0);
        display: flex; justify-content: center;
        font-size: 0.78rem; color: var(--secondary-text-color);
      }

      /* Error / empty */
      .error-state, .empty-state {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 40px 20px;
        color: var(--secondary-text-color); text-align: center;
      }
      .error-state { color: var(--error-color, #f44336); }
      .error-state ha-icon, .empty-state ha-icon { --mdc-icon-size: 48px; margin-bottom: 12px; opacity: 0.5; }

      @media (max-width: 480px) {
        .card-content { padding: 10px; gap: 8px; }
        .rank-row { padding: 10px 12px; gap: 10px; }
        .rank-badge { font-size: 1.3rem; width: 28px; }
        .child-avatar { width: 38px; height: 38px; min-width: 38px; }
        .child-avatar ha-icon { --mdc-icon-size: 22px; }
        .rank-name { font-size: 0.95rem; }
        .score-value { font-size: 1.2rem; }
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Please define an entity");
    this.config = {
      title: "Leaderboard",
      sort_by: "points",      // "points" | "streak" | "weekly"
      show_streak: true,
      show_weekly: true,
            header_color: '#b7950b',
    ...config,
    };
  }

  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("taskmate-leaderboard-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Leaderboard" };
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>Entity not found: ${this.config.entity}</div></div></ha-card>`;
    if (entity.state === "unavailable" || entity.state === "unknown") return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>TaskMate unavailable</div></div></ha-card>`;

    const children = [...(entity.attributes.children || [])];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Points";

    if (children.length === 0) return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:account-group"></ha-icon><div>No children found</div></div></ha-card>`;

    // Build weekly points from recent_completions
    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const weeklyPoints = this._buildWeeklyPoints(entity, tz);

    // Sort children
    const sortBy = this.config.sort_by || "points";
    const sorted = [...children].sort((a, b) => {
      if (sortBy === "streak") return (b.current_streak || 0) - (a.current_streak || 0);
      if (sortBy === "weekly") return (weeklyPoints[b.id] || 0) - (weeklyPoints[a.id] || 0);
      return (b.points || 0) - (a.points || 0);
    });

    const sortLabels = { points: "All-time Points", streak: "Current Streak", weekly: "This Week" };
    const periodLabel = sortLabels[sortBy] || sortLabels.points;

    // Solo mode
    if (children.length === 1) {
      return this._renderSolo(sorted[0], weeklyPoints, pointsIcon, pointsName, periodLabel);
    }

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#b7950b'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:trophy"></ha-icon>
            <span class="header-title">${this.config.title}</span>
          </div>
          <span class="period-badge">${periodLabel}</span>
        </div>
        <div class="card-content">
          ${sorted.map((child, idx) => {
            const prevChild = idx > 0 ? sorted[idx - 1] : null;
            const isTie = prevChild && this._getScore(child, prevChild, sortBy, weeklyPoints);
            return html`
              ${isTie ? html`<div class="tie-line"></div>` : ''}
              ${this._renderRankRow(child, idx, sortBy, weeklyPoints, pointsIcon, pointsName)}
            `;
          })}
        </div>
        <div class="card-footer">
          Ranked by ${periodLabel.toLowerCase()}
        </div>
      </ha-card>
    `;
  }

  _getScore(a, b, sortBy, weeklyPoints) {
    if (sortBy === "streak") return (a.current_streak || 0) === (b.current_streak || 0);
    if (sortBy === "weekly") return (weeklyPoints[a.id] || 0) === (weeklyPoints[b.id] || 0);
    return (a.points || 0) === (b.points || 0);
  }

  _renderRankRow(child, idx, sortBy, weeklyPoints, pointsIcon, pointsName) {
    const rankClass = idx === 0 ? "first" : idx === 1 ? "second" : idx === 2 ? "third" : "";
    const avatarColour = RANK_COLOURS[idx % RANK_COLOURS.length];
    const rankEmoji = idx < 3 ? RANK_LABELS[idx] : null;
    const rankNum = idx + 1;

    let scoreValue, scoreLabel;
    if (sortBy === "streak") {
      scoreValue = child.current_streak || 0;
      scoreLabel = "day streak";
    } else if (sortBy === "weekly") {
      scoreValue = weeklyPoints[child.id] || 0;
      scoreLabel = "this week";
    } else {
      scoreValue = child.points || 0;
      scoreLabel = pointsName;
    }

    return html`
      <div class="rank-row ${rankClass}">
        ${rankEmoji
          ? html`<div class="rank-badge">${rankEmoji}</div>`
          : html`<div class="rank-number">${rankNum}</div>`}

        <div class="child-avatar" style="background: linear-gradient(135deg, ${avatarColour} 0%, ${avatarColour}cc 100%);">
          <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
        </div>

        <div class="rank-info">
          <div class="rank-name">${child.name}</div>
          <div class="rank-stats">
            ${this.config.show_streak !== false && sortBy !== "streak" ? html`
              <span class="stat-chip">
                <ha-icon icon="mdi:fire" style="color: #e67e22;"></ha-icon>
                ${child.current_streak || 0}d streak
              </span>
            ` : ''}
            ${this.config.show_weekly !== false && sortBy !== "weekly" ? html`
              <span class="stat-chip">
                <ha-icon icon="mdi:calendar-week" style="color: #3498db;"></ha-icon>
                ${weeklyPoints[child.id] || 0} this week
              </span>
            ` : ''}
            ${sortBy !== "points" ? html`
              <span class="stat-chip">
                <ha-icon icon="${pointsIcon}" style="color: #f1c40f;"></ha-icon>
                ${child.points || 0} total
              </span>
            ` : ''}
          </div>
        </div>

        <div class="rank-score" style="color: ${avatarColour};">
          <div class="score-value">${scoreValue}</div>
          <div class="score-label">${scoreLabel}</div>
        </div>
      </div>
    `;
  }

  _renderSolo(child, weeklyPoints, pointsIcon, pointsName, periodLabel) {
    const entity = this.hass.states[this.config.entity];
    const totalChores = child.total_chores_completed || 0;
    const bestStreak = child.best_streak || 0;
    const weekly = weeklyPoints[child.id] || 0;

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#b7950b'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:trophy"></ha-icon>
            <span class="header-title">${this.config.title}</span>
          </div>
        </div>
        <div class="card-content">
          <div class="rank-row first">
            <div class="rank-badge">🥇</div>
            <div class="child-avatar" style="background: linear-gradient(135deg, #f1c40f 0%, #e67e22 100%);">
              <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
            </div>
            <div class="rank-info">
              <div class="rank-name">${child.name}</div>
              <div class="rank-stats">
                <span class="stat-chip">
                  <ha-icon icon="mdi:fire" style="color:#e67e22;"></ha-icon>
                  ${child.current_streak || 0}d streak
                </span>
              </div>
            </div>
            <div class="rank-score" style="color:#f1c40f;">
              <div class="score-value">${child.points || 0}</div>
              <div class="score-label">${pointsName}</div>
            </div>
          </div>

          <div class="solo-header">Personal Bests</div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="mdi:fire" style="color:#e67e22;"></ha-icon>
            <span class="pb-label">Best streak</span>
            <span class="pb-value">${bestStreak} days</span>
          </div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="mdi:checkbox-multiple-marked" style="color:#3498db;"></ha-icon>
            <span class="pb-label">Total chores completed</span>
            <span class="pb-value">${totalChores}</span>
          </div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="mdi:calendar-week" style="color:#9b59b6;"></ha-icon>
            <span class="pb-label">Points this week</span>
            <span class="pb-value">${weekly}</span>
          </div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="${pointsIcon}" style="color:#f1c40f;"></ha-icon>
            <span class="pb-label">Total points earned</span>
            <span class="pb-value">${child.total_points_earned || child.points || 0}</span>
          </div>
        </div>
      </ha-card>
    `;
  }

  _buildWeeklyPoints(entity, tz) {
    const result = {};
    const completions = entity.attributes.recent_completions || entity.attributes.todays_completions || [];
    const choreMap = {};
    (entity.attributes.chores || []).forEach(ch => { choreMap[ch.id] = ch.points || 0; });

    const today = new Date();
    const weekDays = new Set();
    for (let i = 6; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      weekDays.add(d.toLocaleDateString("en-CA", { timeZone: tz }));
    }

    completions
      .filter(c => c.approved)
      .forEach(c => {
        const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
        if (weekDays.has(day)) {
          result[c.child_id] = (result[c.child_id] || 0) +
            (c.points !== undefined ? c.points : (choreMap[c.chore_id] || 0));
        }
      });

    return result;
  }
}

class TaskMateLeaderboardCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  static get styles() {
    return css`
      :host { display: block; padding: 4px 0; }
      ha-textfield { width: 100%; margin-bottom: 8px; }
      .field-row { margin-bottom: 16px; }
      .field-label { display: block; font-size: 12px; font-weight: 500; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; padding: 0 4px; }
      .field-select { display: block; width: 100%; padding: 10px 12px; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; background: var(--card-background-color, #fff); color: var(--primary-text-color); font-size: 14px; box-sizing: border-box; cursor: pointer; appearance: auto; }
      .field-select:focus { outline: none; border-color: var(--primary-color); border-width: 2px; }
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
        placeholder="Leaderboard"
      ></ha-textfield>

      <div class="field-row">
        <label class="field-label">Rank by</label>
        <select class="field-select" @change="${e => this._update('sort_by', e.target.value)}">
          <option value="points" ?selected="${(this.config.sort_by || 'points') === 'points'}">All-time Points</option>
          <option value="streak" ?selected="${this.config.sort_by === 'streak'}">Current Streak</option>
          <option value="weekly" ?selected="${this.config.sort_by === 'weekly'}">This Week's Points</option>
        </select>
        <span class="field-helper">What to rank children by</span>
      </div>

      <label class="check-row">
        <input type="checkbox"
          ?checked="${this.config.show_streak !== false}"
          
          @change="${e => this._update('show_streak', e.target.checked)}"
        />
        <span class="check-label">Show streak in sub-stats</span>
      </label>

      <label class="check-row">
        <input type="checkbox"
          ?checked="${this.config.show_weekly !== false}"
          
          @change="${e => this._update('show_weekly', e.target.checked)}"
        />
        <span class="check-label">Show weekly points in sub-stats</span>
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

customElements.define("taskmate-leaderboard-card", TaskMateLeaderboardCard);
customElements.define("taskmate-leaderboard-card-editor", TaskMateLeaderboardCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-leaderboard-card",
  name: "TaskMate Leaderboard",
  description: "Multi-child competitive ranking by points, streak, or weekly activity",
  preview: true,
});

console.info("%c TASKMATE-LEADERBOARD-CARD %c v1.0.0 ", "background:#2c3e50;color:white;font-weight:bold;border-radius:4px 0 0 4px;", "background:#f1c40f;color:#333;font-weight:bold;border-radius:0 4px 4px 0;");
