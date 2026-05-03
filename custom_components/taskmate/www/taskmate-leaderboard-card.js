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

  shouldUpdate(changedProps) {
    if (changedProps.has("hass")) {
      return window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity);
    }
    return true;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
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

      .tie-line .tie-label {
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
      title: "",
      sort_by: "points",      // "points" | "streak" | "weekly" | "career"
      show_streak: true,
      show_weekly: true,
      show_career: true,
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
    if (!entity) return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    if (entity.state === "unavailable" || entity.state === "unknown") return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = [...(attrs.children || [])];
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t('common.points');

    if (children.length === 0) return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:account-group"></ha-icon><div>${this._t('common.no_children')}</div></div></ha-card>`;

    // Build weekly points from recent_completions
    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const weeklyPoints = this._buildWeeklyPoints(attrs, tz);

    // Sort children
    const sortBy = this.config.sort_by || "points";
    const sorted = [...children].sort((a, b) => {
      if (sortBy === "streak") return (b.current_streak || 0) - (a.current_streak || 0);
      if (sortBy === "weekly") return (weeklyPoints[b.id] || 0) - (weeklyPoints[a.id] || 0);
      if (sortBy === "career") return (b.career_score || 0) - (a.career_score || 0);
      return (b.points || 0) - (a.points || 0);
    });

    const sortLabels = { points: this._t('leaderboard.sort_all_time_points'), streak: this._t('leaderboard.sort_current_streak'), weekly: this._t('leaderboard.sort_this_week'), career: this._t('leaderboard.sort_career_score') };
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
            <span class="header-title">${this.config.title || this._t('leaderboard.default_title')}</span>
          </div>
          <span class="period-badge">${periodLabel}</span>
        </div>
        <div class="card-content">
          ${sorted.map((child, idx) => {
            const prevChild = idx > 0 ? sorted[idx - 1] : null;
            const isTie = prevChild && this._getScore(child, prevChild, sortBy, weeklyPoints);
            return html`
              ${isTie ? html`<div class="tie-line"><span class="tie-label">${this._t('leaderboard.tie')}</span></div>` : ''}
              ${this._renderRankRow(child, idx, sortBy, weeklyPoints, pointsIcon, pointsName)}
            `;
          })}
        </div>
        <div class="card-footer">
          ${this._t('leaderboard.ranked_by', { period: periodLabel.toLowerCase() })}
        </div>
      </ha-card>
    `;
  }

  _getScore(a, b, sortBy, weeklyPoints) {
    if (sortBy === "streak") return (a.current_streak || 0) === (b.current_streak || 0);
    if (sortBy === "weekly") return (weeklyPoints[a.id] || 0) === (weeklyPoints[b.id] || 0);
    if (sortBy === "career") return (a.career_score || 0) === (b.career_score || 0);
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
      scoreLabel = this._t('common.day_streak');
    } else if (sortBy === "weekly") {
      scoreValue = weeklyPoints[child.id] || 0;
      scoreLabel = this._t('common.this_week');
    } else if (sortBy === "career") {
      scoreValue = child.career_score || 0;
      scoreLabel = this._t('leaderboard.career_score');
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
                ${this._t('common.d_streak', { count: child.current_streak || 0 })}
              </span>
            ` : ''}
            ${this.config.show_weekly !== false && sortBy !== "weekly" ? html`
              <span class="stat-chip">
                <ha-icon icon="mdi:calendar-week" style="color: #3498db;"></ha-icon>
                ${weeklyPoints[child.id] || 0} ${this._t('common.this_week')}
              </span>
            ` : ''}
            ${sortBy !== "points" ? html`
              <span class="stat-chip">
                <ha-icon icon="${pointsIcon}" style="color: #f1c40f;"></ha-icon>
                ${child.points || 0} ${this._t('common.total')}
              </span>
            ` : ''}
            ${this.config.show_career !== false && sortBy !== "career" ? html`
              <span class="stat-chip">
                <ha-icon icon="mdi:trophy-variant" style="color: #27ae60;"></ha-icon>
                ${child.career_score || 0} ${this._t('leaderboard.career_label')}
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
            <span class="header-title">${this.config.title || this._t('leaderboard.default_title')}</span>
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
                  ${this._t('common.d_streak', { count: child.current_streak || 0 })}
                </span>
              </div>
            </div>
            <div class="rank-score" style="color:#f1c40f;">
              <div class="score-value">${child.points || 0}</div>
              <div class="score-label">${pointsName}</div>
            </div>
          </div>

          <div class="solo-header">${this._t('leaderboard.personal_bests')}</div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="mdi:fire" style="color:#e67e22;"></ha-icon>
            <span class="pb-label">${this._t('leaderboard.best_streak')}</span>
            <span class="pb-value">${this._t('leaderboard.best_streak_value', { count: bestStreak })}</span>
          </div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="mdi:checkbox-multiple-marked" style="color:#3498db;"></ha-icon>
            <span class="pb-label">${this._t('leaderboard.total_chores_completed')}</span>
            <span class="pb-value">${totalChores}</span>
          </div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="mdi:calendar-week" style="color:#9b59b6;"></ha-icon>
            <span class="pb-label">${this._t('leaderboard.points_this_week')}</span>
            <span class="pb-value">${weekly}</span>
          </div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="${pointsIcon}" style="color:#f1c40f;"></ha-icon>
            <span class="pb-label">${this._t('leaderboard.total_points_earned')}</span>
            <span class="pb-value">${child.total_points_earned || child.points || 0}</span>
          </div>
          <div class="personal-best-row">
            <ha-icon class="pb-icon" icon="mdi:trophy-variant" style="color:#27ae60;"></ha-icon>
            <span class="pb-label">${this._t('leaderboard.career_score')}</span>
            <span class="pb-value">${child.career_score || 0}</span>
          </div>
        </div>
      </ha-card>
    `;
  }

  _buildWeeklyPoints(attrs, tz) {
    const result = {};
    const completions = attrs.recent_completions || attrs.todays_completions || [];
    const choreMap = {};
    (attrs.chores || []).forEach(ch => { choreMap[ch.id] = ch.points || 0; });

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
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'sort_by',
        selector: {
          select: {
            options: [
              { value: 'points', label: this._t('leaderboard.editor.sort_option_points') },
              { value: 'streak', label: this._t('leaderboard.editor.sort_option_streak') },
              { value: 'weekly', label: this._t('leaderboard.editor.sort_option_weekly') },
              { value: 'career', label: this._t('leaderboard.editor.sort_option_career') },
            ],
            mode: 'dropdown',
          },
        },
      },
      { name: 'show_streak', selector: { boolean: {} } },
      { name: 'show_weekly', selector: { boolean: {} } },
      { name: 'show_career', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('leaderboard.editor.entity_label'),
      title: this._t('leaderboard.editor.title_label'),
      sort_by: this._t('leaderboard.editor.rank_by_label'),
      show_streak: this._t('leaderboard.editor.show_streak'),
      show_weekly: this._t('leaderboard.editor.show_weekly'),
      show_career: this._t('leaderboard.editor.show_career'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('leaderboard.editor.entity_helper'),
      sort_by: this._t('leaderboard.editor.rank_by_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      sort_by: this.config.sort_by || 'points',
      show_streak: this.config.show_streak !== false,
      show_weekly: this.config.show_weekly !== false,
      show_career: this.config.show_career !== false,
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
      ${this._renderColourPicker('header_color', '#b7950b')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, '#e67e22', '#27ae60', '#3498db', '#9b59b6', '#e74c3c', '#34495e'];
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
      } else if ((key === 'show_streak' || key === 'show_weekly' || key === 'show_career') && value === true) {
        delete newConfig[key];
      } else if (key === 'sort_by' && value === 'points') {
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

customElements.define("taskmate-leaderboard-card", TaskMateLeaderboardCard);
customElements.define("taskmate-leaderboard-card-editor", TaskMateLeaderboardCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-leaderboard-card",
  name: "TaskMate Leaderboard",
  description: "Multi-child competitive ranking by points, streak, or weekly activity",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-leaderboard-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE LEADERBOARD CARD %c v" + _tmVersion + " ",
  "background:#b7950b;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
