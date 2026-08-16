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

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateStreakCard extends LitElement {
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
    const base = css`
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

      /* ── Designed layouts (playroom / console / cleanpro) ── */
      /* Shared .tmd kit + tokens come from taskmate-design.js styles(). */

      .sk-grid { display: flex; flex-direction: column; gap: 11px; }
      .sk-tile { background: var(--tmd-surface-2); border-radius: 18px; padding: 12px; }
      .sk-name { font-weight: 800; font-size: 14px; }
      .sk-sub { font-size: 12px; }
      .sk-count { font-size: 26px; color: var(--tmd-accent); }
      .sk-dots { display: flex; gap: 5px; flex-wrap: wrap; margin-top: 10px; }
      .sk-dot { width: 15px; height: 15px; border-radius: 50%; background: var(--tmd-border); }
      .sk-dot.on { background: var(--tmd-good); }
      .sk-badges { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }

      /* Console */
      .sk-grid-cn { display: flex; flex-direction: column; gap: 9px; }
      .sk-tile-cn { background: var(--tmd-surface-2); border: 1px solid var(--tmd-border);
                    border-radius: 10px; padding: 11px; }
      .sk-combo-label { font-size: 10px; }
      .sk-combo { font-size: 24px; color: var(--tmd-accent); }
      .sk-segs { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 9px; }
      .sk-seg { flex: 1; height: 8px; border-radius: 2px; background: #0b1424; }
      .sk-seg.on { background: var(--tmd-accent);
                   box-shadow: 0 0 8px color-mix(in srgb, var(--tmd-accent) 70%, transparent); }
      .sk-badges-cn { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 9px; }

      /* Clean Pro */
      .sk-grid-cp { display: flex; flex-direction: column; gap: 13px; }
      .sk-row-cp .num { font-size: 17px; }
      .sk-segs-cp { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 8px; }
      .sk-seg-cp { flex: 1; height: 9px; border-radius: 3px; background: var(--tmd-surface-2); }
      .sk-seg-cp.on { background: var(--tmd-good); }
      .sk-badges-cp { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 9px; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) throw new Error(this._t('streak.error.entity_required'));
    this.config = {
      title: null,
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

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") return this._renderDesigned(design);

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;
    }

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    let children = attrs.children || [];
    // Use recent_completions (all-time history, last 50) for streak/achievement calculation
    const completions = [...(attrs.recent_completions || attrs.todays_completions || [])];
    const pointsIcon = attrs.points_icon || "mdi:star";
    const chores = attrs.chores || [];

    if (this.config.child_id) {
      children = children.filter(c => c.id === this.config.child_id);
    }

    if (children.length === 0) {
      return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:account-group"></ha-icon><div>${this._t('common.no_children')}</div></div></ha-card>`;
    }

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, '#e74c3c')}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:fire"></ha-icon>
            <span class="header-title">${this.config.title || this._t('streak.default_title')}</span>
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
      : this._calculateStreak(childCompletions);
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
              <span class="streak-label">${this._t('streak.day_streak')}</span>
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
            <div class="achievements-label">${this._t('streak.achievements')}</div>
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

  _calculateStreak(completions) {
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
    const todayKey = new Date().toLocaleDateString("en-CA", { timeZone: tz });
    const today = new Date(todayKey + "T12:00:00"); // noon avoids DST edge cases
    for (let i = 0; i < 365; i++) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toLocaleDateString("en-CA");
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
    const todayKey = new Date().toLocaleDateString("en-CA", { timeZone: tz });
    const today = new Date(todayKey + "T12:00:00"); // noon avoids DST edge cases

    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const key = d.toLocaleDateString("en-CA");
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
      { id: "first", name: this._t('streak.achievement.first_name'), emoji: "🌟", description: this._t('streak.achievement.first_desc'), earned: totalCompletions >= 1 },
      { id: "ten", name: this._t('streak.achievement.ten_name'), emoji: "🏅", description: this._t('streak.achievement.ten_desc'), earned: totalCompletions >= 10 },
      { id: "fifty", name: this._t('streak.achievement.fifty_name'), emoji: "🥈", description: this._t('streak.achievement.fifty_desc'), earned: totalCompletions >= 50 },
      { id: "hundred", name: this._t('streak.achievement.hundred_name'), emoji: "🥇", description: this._t('streak.achievement.hundred_desc'), earned: totalCompletions >= 100 },
      { id: "streak3", name: this._t('streak.achievement.streak3_name'), emoji: "⚡", description: this._t('streak.achievement.streak3_desc'), earned: bestStreak >= 3 },
      { id: "streak7", name: this._t('streak.achievement.streak7_name'), emoji: "🔥", description: this._t('streak.achievement.streak7_desc'), earned: bestStreak >= 7 },
      { id: "streak14", name: this._t('streak.achievement.streak14_name'), emoji: "🔥🔥", description: this._t('streak.achievement.streak14_desc'), earned: bestStreak >= 14 },
      { id: "streak30", name: this._t('streak.achievement.streak30_name'), emoji: "💎", description: this._t('streak.achievement.streak30_desc'), earned: bestStreak >= 30 },
      { id: "points50", name: this._t('streak.achievement.points50_name'), emoji: "🎯", description: this._t('streak.achievement.points50_desc'), earned: totalPoints >= 50 },
      { id: "points100", name: this._t('streak.achievement.points100_name'), emoji: "💰", description: this._t('streak.achievement.points100_desc'), earned: totalPoints >= 100 },
    ];

    // Show earned ones + next locked milestone
    const earned = milestones.filter(m => m.earned);
    const nextLocked = milestones.find(m => !m.earned);
    return nextLocked ? [...earned, nextLocked] : earned;
  }

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns/frag/05-streak.html.
  ══════════════════════════════════════════════════════════════════════ */

  _designTone(i) { return `var(--tmd-c${(i % 6) + 1})`; }

  _av(child, tone, size) {
    const a = child.avatar || "";
    const inner = a.startsWith("mdi:")
      ? html`<ha-icon icon="${a}"></ha-icon>`
      : a
        ? html`<img src="${a}" alt="${child.name}">`
        : (child.name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
    return html`<div class="av" style="--av:${size}px;--ac:${tone}">${inner}</div>`;
  }

  _streakEmoji(streak) {
    return streak >= 14 ? "🔥🔥" : streak >= 7 ? "🔥" : streak >= 3 ? "⚡" : streak >= 1 ? "✨" : "💤";
  }

  _designHeader(hd, design, onFire) {
    const title = this.config.title || this._t('streak.default_title');
    const sub =
      design === "playroom" ? this._t('streak.day_streak') :
      design === "console"  ? this._t('streak.achievements') :
                              "";
    return html`
      <div class="tmd-hd">
        <span class="ic">🔥</span>
        <span class="tt">${title}${sub ? html`<small>${sub}</small>` : ""}</span>
        ${design === "console" && onFire
          ? html`<span class="pill">${this._t('common.d_streak', { count: onFire })}</span>` : ""}
      </div>`;
  }

  _streakData(child, completions, chores, entity_ref) {
    const childCompletions = completions.filter(c => c.child_id === child.id);
    const streak = child.current_streak !== undefined
      ? child.current_streak
      : this._calculateStreak(childCompletions);
    const daysShown = this.config.streak_days_shown || 14;
    const dayDots = this._buildDayDots(childCompletions, chores, child.id, daysShown);
    const achievements = this._getAchievements(child, childCompletions, streak, entity_ref);
    return { streak, dayDots, achievements };
  }

  _renderDesigned(design) {
    const entity = this.hass.states[this.config.entity];
    const hd = _safeColor(this.config.header_color, '#e74c3c');

    if (!entity) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${this._designHeader(hd, design, 0)}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div>
      </ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${this._designHeader(hd, design, 0)}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.unavailable')}</div></div>
      </ha-card>`;
    }

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    let children = attrs.children || [];
    const completions = [...(attrs.recent_completions || attrs.todays_completions || [])];
    const chores = attrs.chores || [];

    if (this.config.child_id) {
      children = children.filter(c => c.id === this.config.child_id);
    }

    const rows = children.map((child, idx) => ({
      child,
      tone: this._designTone(idx),
      ...this._streakData(child, completions, chores, entity),
    }));

    const onFire = rows.filter(r => r.streak >= 7).length;
    const header = this._designHeader(hd, design, onFire);

    if (rows.length === 0) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${header}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.no_children')}</div></div>
      </ha-card>`;
    }

    const body =
      design === "playroom" ? this._skPlayroom(rows) :
      design === "console"  ? this._skConsole(rows) :
                              this._skCleanpro(rows);

    return html`<ha-card class="tmd" style="--hd:${hd}">${header}<div class="tmd-bd">${body}</div></ha-card>`;
  }

  _earnedBadges(achievements) {
    return achievements.filter(a => a.earned);
  }

  // Classic shows earned badges PLUS the next locked milestone. _getAchievements
  // already returns exactly that set, so the designed badge rows render it whole,
  // dimming the locked entry to match the classic .badge.locked treatment.
  _designBadges(achievements, wrapClass, locked) {
    if (!achievements.length) return "";
    return html`
      <div class="${wrapClass}">
        ${achievements.map((a) => html`
          <span class="chip ${a.earned ? (locked.soft ? "soft" : "") : "locked"}"
            title="${a.description}"
            style="${a.earned ? "" : "opacity:0.45;filter:grayscale(1)"}">
            ${locked.dot && a.earned ? html`<span style="color:var(--tmd-accent)">●</span> ` : html`${a.emoji} `}${a.name}
          </span>`)}
      </div>`;
  }

  _skPlayroom(rows) {
    return html`
      <div class="sk-grid">
        ${rows.map((r) => html`
          <div class="sk-tile" style="--ac:${r.tone}">
            <div class="row">
              ${this._av(r.child, r.tone, 42)}
              <div style="flex:1;min-width:0">
                <div class="sk-name">${r.child.name}</div>
                <div class="muted sk-sub">${this._t('streak.day_streak')}</div>
              </div>
              <div class="big sk-count">${r.streak} ${this._streakEmoji(r.streak)}</div>
            </div>
            <div class="sk-dots">
              ${r.dayDots.map((d) => html`<i class="sk-dot ${d.cssClass !== "inactive" ? "on" : ""}" title="${d.label}"></i>`)}
            </div>
            ${this._designBadges(r.achievements, "sk-badges", { soft: true })}
          </div>`)}
      </div>`;
  }

  _skConsole(rows) {
    return html`
      <div class="sk-grid-cn">
        ${rows.map((r) => html`
          <div class="sk-tile-cn" style="--ac:${r.tone}">
            <div class="row">
              ${this._av(r.child, r.tone, 36)}
              <div style="flex:1;min-width:0">
                <div style="font-weight:700">${r.child.name}</div>
                <div class="muted sk-combo-label">${this._t('streak.achievements')}</div>
              </div>
              <div class="num sk-combo">x${r.streak} ${this._streakEmoji(r.streak)}</div>
            </div>
            <div class="sk-segs">
              ${r.dayDots.map((d) => html`<i class="sk-seg ${d.cssClass !== "inactive" ? "on" : ""}"></i>`)}
            </div>
            ${this._designBadges(r.achievements, "sk-badges-cn", {})}
          </div>`)}
      </div>`;
  }

  _skCleanpro(rows) {
    const tone = (streak) => streak >= 7 ? "var(--tmd-good)" : streak >= 3 ? "var(--tmd-warn)" : "var(--tmd-dim)";
    return html`
      <div class="sk-grid-cp">
        ${rows.map((r, i) => html`
          ${i > 0 ? html`<div class="divide" style="margin:0"></div>` : ""}
          <div class="sk-row-cp" style="--ac:${r.tone}">
            <div class="row">
              ${this._av(r.child, r.tone, 34)}
              <div style="flex:1;min-width:0"><div style="font-weight:600">${r.child.name}</div></div>
              <div class="num" style="color:${tone(r.streak)}">${this._streakEmoji(r.streak)} ${this._t('common.d_streak', { count: r.streak })}</div>
            </div>
            <div class="sk-segs-cp">
              ${r.dayDots.map((d) => html`<i class="sk-seg-cp ${d.cssClass !== "inactive" ? "on" : ""}"></i>`)}
            </div>
            ${this._designBadges(r.achievements, "sk-badges-cp", { dot: true })}
          </div>`)}
      </div>`;
  }
}

// Card Editor
class TaskMateStreakCardEditor extends LitElement {
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
      { name: 'streak_days_shown', selector: { number: { min: 1, max: 100, mode: 'box' } } },
      {
        name: 'card_design',
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: 'global', label: 'Use global default' }],
            mode: 'dropdown',
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      title: this._t('streak.editor.title'),
      child_id: this._t('common.editor.filter_by_child'),
      streak_days_shown: this._t('streak.editor.days_shown'),
      card_design: this._t('common.design.field_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('streak.editor.child_helper'),
      streak_days_shown: this._t('streak.editor.days_shown_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      child_id: this.config.child_id || '__all__',
      streak_days_shown: this.config.streak_days_shown || 14,
      card_design: this.config.card_design || 'global',
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
      ${this._renderColourPicker('header_color', '#e74c3c')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    const current = this.config[key] || defaultValue;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current,
      label: this._t('common.editor.header_colour'),
      helper: this._t('common.editor.header_colour_helper'),
      resetLabel: this._t('common.reset'),
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
    });
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
      } else if (key === 'streak_days_shown' && value === 14) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
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

customElements.define("taskmate-streak-card", TaskMateStreakCard);
customElements.define("taskmate-streak-card-editor", TaskMateStreakCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-streak-card",
  name: "TaskMate Streaks & Achievements",
  description: "Consecutive day streaks and milestone badges for each child",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-streak-card", "overview"),
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
