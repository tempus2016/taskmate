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

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateWeeklyCard extends LitElement {
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

      /* Shared .tmd kit + design tokens are provided by taskmate-design.js styles(). */

      /* Weekly — designed stat grid (playroom/console/cleanpro) */
      .wk-d-stats { display: grid; gap: 9px; }
      .wk-d-stats.g4 { grid-template-columns: 1fr 1fr 1fr 1fr; }
      .wk-d-stats.g2 { grid-template-columns: 1fr 1fr; }
      .wk-pl-stat { background: var(--tmd-surface-2); border-radius: 16px; padding: 11px; text-align: center; }
      .wk-pl-stat .v { font-family: var(--tmd-font-display); font-weight: 800; font-size: 24px; line-height: 1; color: var(--tmd-accent); }
      .wk-pl-stat .k { font-size: 11px; font-weight: 800; margin-top: 4px; }

      /* Weekly — chart wrap */
      .wk-chart-pl { background: var(--tmd-surface-2); border-radius: 18px; padding: 13px; margin-top: 11px; }
      .wk-chart-cn { background: var(--tmd-surface-2); border: 1px solid var(--tmd-border); border-radius: 8px; padding: 12px; margin-top: 9px; }
      .wk-chart-cp { margin-top: 14px; }
      .wk-chart-title { font-weight: 800; font-size: 13px; margin-bottom: 10px; }
      .wk-chart-title.cn { font-family: var(--tmd-font-mono); font-size: 11px; margin-bottom: 10px; color: var(--tmd-dim); text-transform: uppercase; letter-spacing: .04em; }
      .wk-chart-title.cp { font-size: 12px; margin-bottom: 10px; color: var(--tmd-dim); font-weight: 600; }
      .wk-bars { display: flex; align-items: flex-end; gap: 7px; }
      .wk-bars.cn { gap: 6px; height: 92px; }
      .wk-bars.pl { gap: 7px; height: 96px; }
      .wk-bars.cp { gap: 8px; height: 84px; }
      .wk-bcol { flex: 1; text-align: center; display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
      .wk-bcol .lbl { font-size: 10px; font-weight: 800; margin-top: 5px; }
      .wk-bcol .lbl.cn { font-family: var(--tmd-font-mono); font-size: 9px; color: var(--tmd-dim); font-weight: 600; }
      .wk-bcol .lbl.cp { font-size: 10px; color: var(--tmd-dim); font-weight: 600; }
      .wk-bcol .val { font-size: 9px; font-weight: 700; color: var(--tmd-dim); min-height: 12px; }
      .wk-fill { border-radius: 8px 8px 4px 4px; min-height: 3px; background: var(--tmd-accent); }
      .wk-fill.today { background: var(--tmd-good); }
      .wk-fill.cn { border-radius: 3px; background: linear-gradient(180deg, var(--tmd-accent), color-mix(in srgb, var(--tmd-accent) 50%, var(--tmd-accent2))); box-shadow: 0 0 10px color-mix(in srgb, var(--tmd-accent) 50%, transparent); }
      .wk-fill.cn.today { background: linear-gradient(180deg, var(--tmd-accent2), var(--tmd-accent)); box-shadow: 0 0 14px color-mix(in srgb, var(--tmd-accent2) 60%, transparent); }
      .wk-fill.cp { border-radius: 4px; background: var(--tmd-accent); }
      .wk-fill.cp.today { background: var(--tmd-accent2); }

      /* Weekly — per-child rows */
      .wk-kids { display: grid; gap: 8px; margin-top: 11px; }
      .wk-kids .name { flex: 1; min-width: 0; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .wk-kids.cp .name { font-weight: 600; font-size: 13px; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) throw new Error(this._t('weekly.error.entity_required'));
    this.config = {
      title: null,
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

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";

    const entity = this.hass.states[this.config.entity];
    if (design !== "classic") return this._renderDesigned(design, entity);

    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;
    }

    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    let children = attrs.children || [];
    const chores = attrs.chores || [];
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t("common.stars");

    // Use recent_completions (last 50 all-time) for full week view
    let allCompletions = [...(attrs.recent_completions || attrs.todays_completions || [])];
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
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, '#27ae60')}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:calendar-week"></ha-icon>
            <span class="header-title">${this.config.title || this._t('weekly.default_title')}</span>
          </div>
          <span class="week-label">${weekLabel}</span>
        </div>

        <div class="card-content">
          <!-- Summary stats -->
          <div class="stats-row">
            <div class="stat-card">
              <span class="stat-value green">${weekChores}</span>
              <span class="stat-label">${this._t('weekly.stat_chores')}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value orange">${weekPoints}</span>
              <span class="stat-label">${pointsName}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value purple">${daysActive}/7</span>
              <span class="stat-label">${this._t('weekly.stat_days_active')}</span>
            </div>
          </div>

          <!-- Daily bar chart -->
          <div class="chart-section">
            <div class="section-label">${this._t('weekly.section_chores_per_day')}</div>
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
              <div class="section-label">${this._t('weekly.section_children_this_week')}</div>
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
                        <span><ha-icon icon="mdi:checkbox-marked-circle" style="color:var(--wk-green)"></ha-icon>${this._t('weekly.child_chores', { count: childChoreCount })}</span>
                        <span><ha-icon icon="${pointsIcon}" style="color:var(--wk-gold)"></ha-icon>${childPoints} ${pointsName}</span>
                        <span><ha-icon icon="mdi:calendar-check" style="color:var(--wk-blue)"></ha-icon>${this._t('weekly.child_days', { count: childDaysActive })}</span>
                      </div>
                    </div>
                    <div class="week-progress-bar" title="${this._t('weekly.child_days_active_title', { count: childDaysActive })}">
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

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns/frag/10-weekly.html.
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

  _weekData(entity, tz) {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    let children = attrs.children || [];
    const chores = attrs.chores || [];
    const pointsName = attrs.points_name || this._t("common.stars");
    const rewardsClaimed = (attrs.rewards_claimed || attrs.recent_rewards || []);

    let allCompletions = [...(attrs.recent_completions || attrs.todays_completions || [])];
    const seen = new Set();
    allCompletions = allCompletions.filter(comp => {
      if (seen.has(comp.completion_id)) return false;
      seen.add(comp.completion_id); return true;
    });

    if (this.config.child_id) {
      children = children.filter(c => c.id === this.config.child_id);
      allCompletions = allCompletions.filter(c => c.child_id === this.config.child_id);
    }

    const weekDays = this._getWeekDays(tz);
    const todayKey = new Date().toLocaleDateString("en-CA", { timeZone: tz });

    const chorePointsMap = {};
    chores.forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });

    const weekCompletions = allCompletions.filter(c => {
      if (!c.completed_at) return false;
      const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
      return weekDays.some(d => d.key === day);
    });
    const approved = weekCompletions.filter(c => c.approved);
    const ptsOf = (c) => (c.points !== undefined ? c.points : (chorePointsMap[c.chore_id] || 0));

    const weekPoints = approved.reduce((s, c) => s + ptsOf(c), 0);
    const weekChores = approved.length;
    const daysActive = new Set(approved.map(c =>
      new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz })
    )).size;

    // Rewards claimed this week
    let weekRewards = 0;
    rewardsClaimed.forEach(r => {
      const ts = r.claimed_at || r.timestamp || r.completed_at;
      if (!ts) return;
      const day = new Date(ts).toLocaleDateString("en-CA", { timeZone: tz });
      if (this.config.child_id && r.child_id && r.child_id !== this.config.child_id) return;
      if (weekDays.some(d => d.key === day)) weekRewards += 1;
    });

    // Points per day for the chart
    const pointsByDay = {};
    approved.forEach(c => {
      const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
      pointsByDay[day] = (pointsByDay[day] || 0) + ptsOf(c);
    });
    const maxPts = Math.max(1, ...weekDays.map(d => pointsByDay[d.key] || 0));

    // Per-child weekly totals
    const kids = children.map(child => {
      const cc = approved.filter(c => c.child_id === child.id);
      return { child, points: cc.reduce((s, c) => s + ptsOf(c), 0) };
    }).sort((a, b) => b.points - a.points);

    return { weekDays, todayKey, pointsByDay, maxPts, weekPoints, weekChores, daysActive, weekRewards, pointsName, kids };
  }

  _renderDesigned(design, entity) {
    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const hd = _safeColor(this.config.header_color, "#27ae60");

    if (!entity) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        <div class="tmd-hd"><span class="ic">📅</span><span class="tt">${this.config.title || this._t("weekly.default_title")}</span></div>
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div>
      </ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        <div class="tmd-hd"><span class="ic">📅</span><span class="tt">${this.config.title || this._t("weekly.default_title")}</span></div>
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.unavailable')}</div></div>
      </ha-card>`;
    }

    const d = this._weekData(entity, tz);
    const weekLabel = this._getWeekLabel(d.weekDays, tz);
    const title = this.config.title || this._t("weekly.default_title");

    const icon = design === "playroom" ? "📅" : design === "console" ? "▦" : "▤";
    const header = html`
      <div class="tmd-hd">
        <span class="ic">${icon}</span>
        <span class="tt">${title}<small>${weekLabel}</small></span>
        ${design === "console"
          ? html`<span class="pill">${d.weekPoints} ${d.pointsName}</span>` : ""}
      </div>`;

    const stats = [
      { k: this._t("weekly.stat_days_active"), v: `${d.daysActive}/7` },
      { k: d.pointsName, v: d.weekPoints },
      { k: this._t("weekly.stat_rewards"), v: d.weekRewards },
      { k: this._t("weekly.stat_chores"), v: d.weekChores },
    ];

    const cnLike = design !== "playroom"; // console + cleanpro use the .stat kit tile
    const statsBlock = cnLike
      ? html`<div class="wk-d-stats g4">
          ${stats.map(s => html`
            <div class="stat">
              <div class="k">${s.k}</div>
              <div class="v ${design === "console" ? "num" : ""}"
                style="${design === "console" ? "color:var(--tmd-accent)" : ""}">${s.v}</div>
            </div>`)}
        </div>`
      : html`<div class="wk-d-stats g2">
          ${stats.map(s => html`
            <div class="wk-pl-stat"><div class="v">${s.v}</div><div class="k">${s.k}</div></div>`)}
        </div>`;

    const chart = this._wkChart(design, d);
    const kids = this._wkKids(design, d);

    return html`<ha-card class="tmd" style="--hd:${hd}">
      ${header}
      <div class="tmd-bd">
        ${statsBlock}
        ${chart}
        ${kids}
      </div>
    </ha-card>`;
  }

  _wkChart(design, d) {
    const wrapClass = design === "playroom" ? "wk-chart-pl" : design === "console" ? "wk-chart-cn" : "wk-chart-cp";
    const titleClass = design === "playroom" ? "" : design === "console" ? "cn" : "cp";
    const barsClass = design === "playroom" ? "pl" : design === "console" ? "cn" : "cp";
    const lblMode = design === "console" ? "cn" : design === "cleanpro" ? "cp" : "";
    return html`
      <div class="${wrapClass}">
        <div class="wk-chart-title ${titleClass}">${this._t("weekly.section_points_per_day")}</div>
        <div class="wk-bars ${barsClass}">
          ${d.weekDays.map(day => {
            const pts = d.pointsByDay[day.key] || 0;
            const isToday = day.key === d.todayKey;
            const isFuture = day.key > d.todayKey;
            const pct = isFuture ? 0 : Math.round((pts / d.maxPts) * 100);
            const h = isFuture ? 3 : Math.max(pts > 0 ? 8 : 3, pct);
            return html`
              <div class="wk-bcol">
                ${design === "playroom" ? html`<span class="val">${!isFuture && pts > 0 ? pts : ""}</span>` : ""}
                <div class="wk-fill ${barsClass} ${isToday ? "today" : ""}" style="height:${h}%"></div>
                <span class="lbl ${lblMode}">${design === "console" ? day.short.toUpperCase() : day.short}</span>
              </div>`;
          })}
        </div>
      </div>`;
  }

  _wkKids(design, d) {
    if (!d.kids.length) return "";
    const wrapClass = design === "cleanpro" ? "wk-kids cp" : "wk-kids";
    const valColor = design === "cleanpro" ? "var(--tmd-good)" : "var(--tmd-accent)";
    const av = design === "playroom" ? 34 : design === "console" ? 30 : 28;
    return html`
      ${design === "cleanpro" ? html`<div class="divide"></div>` : ""}
      <div class="${wrapClass}">
        ${d.kids.map((r, i) => {
          const tone = this._designTone(i);
          return html`
            <div class="row" style="--ac:${tone}">
              ${this._av(r.child, tone, av)}
              <div class="name">${r.child.name}</div>
              ${design === "playroom"
                ? html`<div class="chip soft">+${r.points} ⭐</div>`
                : html`<div class="num" style="color:${valColor}">+${r.points}</div>`}
            </div>`;
        })}
      </div>`;
  }

  _getWeekDays(tz) {
    const todayKey = new Date().toLocaleDateString("en-CA", { timeZone: tz });
    const today = new Date(todayKey + "T12:00:00"); // noon avoids DST edge cases
    const todayDay = today.getDay(); // 0=Sun
    // Start week on Monday
    const mondayOffset = (todayDay === 0 ? -6 : 1 - todayDay);
    const monday = new Date(today);
    monday.setDate(today.getDate() + mondayOffset);

    const days = [];
    const shortNames = [
      this._t('weekly.day_mon'), this._t('weekly.day_tue'), this._t('weekly.day_wed'),
      this._t('weekly.day_thu'), this._t('weekly.day_fri'), this._t('weekly.day_sat'),
      this._t('weekly.day_sun'),
    ];
    for (let i = 0; i < 7; i++) {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      days.push({
        key: d.toLocaleDateString("en-CA"),
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
      title: this._t('weekly.editor.title'),
      child_id: this._t('common.editor.filter_by_child'),
      card_design: this._t('common.design.field_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('weekly.editor.child_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      child_id: this.config.child_id || '__all__',
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
      ${this._renderColourPicker('header_color', '#27ae60')}
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
        || (key === 'card_design' && value === 'global')
      ) {
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
    if (value === null || value === '' || value === undefined) delete newConfig[key];
    this.dispatchEvent(new CustomEvent('config-changed', {
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
