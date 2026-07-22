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

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateOverviewCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _loading: { type: Object },
      _expanded: { type: Object },
    };
  }

  constructor() {
    super();
    this._loading = {};
    this._expanded = {};
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

      /* Complete on behalf (admin) */
      .tm-outstanding { margin-top: 8px; border-top: 1px dashed var(--divider-color, #e0e0e0); padding-top: 8px; }
      .tm-outstanding-hdr { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.6; margin-bottom: 6px; }
      .tm-outstanding-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; }
      .tm-outstanding-row + .tm-outstanding-row { border-top: 1px solid var(--divider-color, #eee); }
      .tm-outstanding-name { flex: 1; font-size: 0.9rem; }
      .tm-outstanding-pts { opacity: 0.6; font-size: 0.8rem; display: inline-flex; align-items: center; gap: 2px; }
      .btn-complete-behalf { flex: 0 0 auto; display: inline-flex; align-items: center; gap: 4px; border: none; cursor: pointer; background: #2e9e5b; color: #fff; font: 600 0.75rem/1 inherit; padding: 6px 10px; border-radius: 8px; }
      .btn-complete-behalf:hover { background: #27894e; }
      .btn-complete-behalf:active { transform: scale(0.96); }
      .btn-complete-behalf[disabled] { opacity: 0.5; pointer-events: none; }
      .child-main.tm-expandable { cursor: pointer; }
      .tm-all-done { font-size: 0.85rem; opacity: 0.6; font-style: italic; padding: 4px 0; }

      /* Shared .tmd kit + design tokens are provided by taskmate-design.js styles(). */

      /* Overview — pending-approvals callout */
      .ov-alert { display: flex; align-items: center; gap: 11px; border-radius: 16px; padding: 11px 13px; margin-bottom: 12px;
                  background: color-mix(in srgb, var(--tmd-bad) 16%, transparent); }
      .ov-alert.cn { border: 1px solid var(--tmd-bad); border-radius: 8px; padding: 10px 12px;
                     background: color-mix(in srgb, var(--tmd-bad) 18%, transparent); }
      .ov-alert.cp { border: 1px solid color-mix(in srgb, var(--tmd-bad) 35%, transparent); border-radius: var(--tmd-radius-sm);
                     padding: 10px 12px; background: color-mix(in srgb, var(--tmd-bad) 9%, transparent); }
      .ov-alert .emoji { font-size: 22px; line-height: 1; flex: none; }
      .ov-alert .mid { flex: 1; min-width: 0; }
      .ov-alert .ttl { font-weight: 800; color: var(--tmd-bad); }
      .ov-alert.cn .ttl { font-family: var(--tmd-font-mono); font-size: 13px; }
      .ov-alert.cp .ttl { font-weight: 600; }
      .ov-alert .sub { font-size: 12px; }
      .ov-alert.cn .sub { font-family: var(--tmd-font-mono); font-size: 10px; }
      .ov-alert .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--tmd-bad); flex: none; }

      /* Overview — children grid */
      .ov-kids { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; max-height: 360px; overflow-y: auto; }
      @media (max-width: 480px) { .ov-kids { grid-template-columns: repeat(2, 1fr); } }
      .ov-kid { text-align: center; padding: 11px; border-radius: 16px; background: var(--tmd-surface-2); position: relative; }
      .ov-kid.tm-clickable { cursor: pointer; }
      .ov-kid-flags { position: absolute; top: 6px; right: 7px; display: flex; gap: 4px; }
      .ov-kid-flag { font-size: 9.5px; font-weight: 800; padding: 1px 5px; border-radius: 999px; line-height: 1.5; }
      .ov-kid-flag.pend { background: color-mix(in srgb, var(--tmd-warn) 22%, transparent); color: var(--tmd-warn); }
      .ov-kid-flag.wait { background: color-mix(in srgb, var(--tmd-bad) 20%, transparent); color: var(--tmd-bad); }
      .ov-behalf { margin-top: 10px; text-align: left; background: var(--tmd-surface-2); border-radius: var(--tmd-radius-sm); padding: 9px 11px; }
      .ov-behalf-hdr { font-size: 10px; text-transform: uppercase; letter-spacing: .04em; color: var(--tmd-dim); margin-bottom: 6px; }
      .ov-behalf-done { font-size: 12px; font-style: italic; color: var(--tmd-dim); padding: 3px 0; }
      .ov-behalf-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
      .ov-behalf-row + .ov-behalf-row { border-top: 1px solid var(--tmd-border); }
      .ov-behalf-name { flex: 1; font-size: 12.5px; font-weight: 600; min-width: 0; }
      .ov-behalf .btn.good.sm { padding: 4px 9px; }
      .ov-kid.cn { border: 1px solid var(--tmd-border); border-radius: 10px; }
      .ov-kid.cp { border: 1px solid var(--tmd-border); border-radius: var(--tmd-radius-sm); }
      .ov-kid .pts { font-family: var(--tmd-font-display); font-weight: 800; font-size: 20px; line-height: 1; color: var(--tmd-accent); }
      .ov-kid .pts.num { font-family: var(--tmd-font-mono); font-size: 18px; }
      .ov-kid .nm { font-weight: 800; font-size: 12.5px; margin-top: 3px; }
      .ov-kid .nm.cn { font-family: var(--tmd-font-mono); font-size: 9px; color: var(--tmd-dim); letter-spacing: .06em; font-weight: 600; }
      .ov-kid .nm.cp { font-weight: 600; font-size: 12px; color: var(--tmd-dim); }
      .ov-kid .bar { margin-top: 7px; }
      .ov-kid.cn .bar { height: 7px; }
      .ov-kid.cp .bar { height: 6px; }

      /* Overview — today summary */
      .ov-today { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-top: 12px;
                  border-radius: 16px; padding: 11px 13px; background: var(--tmd-surface-2); }
      .ov-today.cn { border: 1px solid var(--tmd-border); border-radius: 10px; }
      .ov-today.cp { background: transparent; padding: 0; margin-top: 0; }
      .ov-today .lbl { font-weight: 800; }
      .ov-today.cn .lbl { font-family: var(--tmd-font-mono); font-size: 11px; letter-spacing: .06em; color: var(--tmd-dim); font-weight: 600; }
      .ov-today.cp .lbl { font-weight: 600; font-size: 12.5px; color: var(--tmd-dim); }
      .ov-today .val { font-family: var(--tmd-font-display); font-weight: 800; font-size: 18px; color: var(--tmd-accent); }
      .ov-today.cn .val { font-family: var(--tmd-font-mono); color: var(--tmd-accent2); }
      .ov-today.cp .val { font-family: var(--tmd-font-mono); font-size: 15px; font-weight: 700; color: var(--tmd-text); }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
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

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") return this._renderDesigned(design, entity);

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const chores = attrs.chores || [];
    const completions = [...(attrs.todays_completions || [])];
    const chorePointsMap = {};
    chores.forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t("common.stars");

    // Pending approvals — from approvals entity if configured, else from the
    // full pending list (resolved via companion) so the count keeps including
    // completions left pending from a previous day; fall back to today's
    // completions only on older backends.
    let pendingApprovals;
    if (this.config.approvals_entity) {
      const appEntity = this.hass.states[this.config.approvals_entity];
      pendingApprovals = appEntity?.attributes?.chore_completions?.length || 0;
    } else {
      pendingApprovals = (attrs.chore_completions || completions.filter(c => !c.approved)).length;
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
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, '#8e44ad')}; }</style>
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

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns/frag/13-overview.html.
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

  /** Per-child today progress, mirroring the classic tile filtering exactly. */
  _childProgress(child, chores, completions, attrs) {
    const childChores = this._childChoresToday(child, chores, attrs);
    const childChoreIds = new Set(childChores.map(c => c.id));
    const childCompletions = completions.filter(c => c.child_id === child.id);
    const completed = childCompletions.filter(c => c.approved && childChoreIds.has(c.chore_id)).length;
    const total = childChores.length;
    const pct = total > 0 ? Math.min(Math.round((completed / total) * 100), 100) : 0;
    return { completed, total, pct };
  }

  _renderDesigned(design, entity) {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const chores = attrs.chores || [];
    const completions = [...(attrs.todays_completions || [])];
    const hd = _safeColor(this.config.header_color, "#8e44ad");

    if (children.length === 0) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${this._ovHeader(design)}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.no_children')}</div></div>
      </ha-card>`;
    }

    let pendingApprovals;
    if (this.config.approvals_entity) {
      const appEntity = this.hass.states[this.config.approvals_entity];
      pendingApprovals = appEntity?.attributes?.chore_completions?.length || 0;
    } else {
      pendingApprovals = (attrs.chore_completions || completions.filter(c => !c.approved)).length;
    }

    const isParent = window.__taskmate_is_parent(this.hass);

    // Aggregate today's progress across all children
    let doneTotal = 0;
    let choreTotal = 0;
    const kids = children.map((child, i) => {
      const p = this._childProgress(child, chores, completions, attrs);
      doneTotal += p.completed;
      choreTotal += p.total;
      // Outstanding chores for the admin "complete on behalf" affordance (mirrors classic tile).
      const childChores = this._childChoresToday(child, chores, attrs);
      const outstanding = childChores.filter(c => {
        const doneToday = completions.filter(
          x => x.child_id === child.id && x.chore_id === c.id && !x.bonus_subtask_id
        ).length;
        return doneToday < (c.daily_limit || 1);
      });
      const childPending = completions.filter(c => c.child_id === child.id && !c.approved).length;
      return {
        child, points: child.points || 0, pct: p.pct, tone: this._designTone(i),
        pendingPoints: child.pending_points || 0, childPending, outstanding,
      };
    });
    const overallPct = choreTotal > 0 ? Math.round((doneTotal / choreTotal) * 100) : 0;
    const pointsIcon = attrs.points_icon || "mdi:star";

    return html`<ha-card class="tmd" style="--hd:${hd}">
      ${this._ovHeader(design, pendingApprovals)}
      <div class="tmd-bd">
        ${pendingApprovals > 0 ? this._ovAlert(design, pendingApprovals) : ""}
        <div class="ov-kids">
          ${kids.map((k) => this._ovKid(design, k, isParent, pointsIcon))}
        </div>
        ${isParent ? kids.filter(k => this._expanded[k.child.id]).map(k => this._ovBehalf(k, pointsIcon)) : ""}
        ${this._ovToday(design, doneTotal, choreTotal, overallPct)}
      </div>
    </ha-card>`;
  }

  /** Chores assigned to + due/available for a child today — shared by classic tile and designed kid. */
  _childChoresToday(child, chores, attrs) {
    const todayDow = attrs.today_day_of_week ||
      new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();
    const availability = attrs.chore_availability || {};
    return chores.filter(c => {
      const at = Array.isArray(c.assigned_to) ? c.assigned_to.map(String) : [];
      const assigned = at.length === 0 || at.includes(String(child.id));
      if (!assigned) return false;
      if (c.schedule_mode !== 'recurring') {
        const dueDays = Array.isArray(c.due_days) ? c.due_days : [];
        if (dueDays.length > 0 && !dueDays.includes(todayDow)) return false;
      }
      if (c.schedule_mode === 'recurring') {
        const perChild = availability[c.id];
        if (perChild && perChild[child.id] === false) return false;
      }
      return true;
    });
  }

  _ovHeader(design, pending) {
    const icon = design === "playroom" ? "👀" : design === "console" ? "◉" : "◳";
    const sub = design === "console"
      ? this._t("overview.designed.sub_console")
      : design === "cleanpro"
        ? this._t("overview.designed.sub_cleanpro")
        : this._t("overview.designed.sub_playroom");
    return html`
      <div class="tmd-hd">
        <span class="ic">${icon}</span>
        <span class="tt">${this.config.title}<small>${sub}</small></span>
        ${design === "console" && pending > 0
          ? html`<span class="cnt">${pending}</span>` : ""}
      </div>`;
  }

  _ovAlert(design, pending) {
    if (design === "console") {
      return html`
        <div class="ov-alert cn">
          <span class="emoji">⚠</span>
          <div class="mid">
            <div class="ttl num">${this._t("overview.designed.pending_review", { count: pending })}</div>
            <div class="sub muted num">${this._t("overview.designed.action_required")}</div>
          </div>
        </div>`;
    }
    if (design === "cleanpro") {
      return html`
        <div class="ov-alert cp">
          <span class="dot"></span>
          <div class="mid"><span class="ttl">${this._t("overview.designed.approvals_waiting", { count: pending })}</span></div>
          <button class="btn sm" style="background:var(--tmd-bad)">${this._t("overview.designed.review")}</button>
        </div>`;
    }
    return html`
      <div class="ov-alert">
        <span class="emoji">🔔</span>
        <div class="mid">
          <div class="ttl">${this._t("overview.designed.waiting_for_you", { count: pending })}</div>
          <div class="sub muted">${this._t("overview.designed.tap_to_check")}</div>
        </div>
        <span class="cnt">${pending}</span>
      </div>`;
  }

  _ovKid(design, k, isParent, pointsIcon) {
    const cls = design === "console" ? "cn" : design === "cleanpro" ? "cp" : "";
    const nameUpper = design === "console" ? `${k.child.name.toUpperCase()} · ${k.pct}%` : k.child.name;
    const isOpen = !!this._expanded[k.child.id];
    const expandable = isParent;
    return html`
      <div class="ov-kid ${cls} ${expandable ? 'tm-clickable' : ''}" style="--ac:${k.tone}"
        @click="${expandable ? () => { this._expanded = { ...this._expanded, [k.child.id]: !isOpen }; this.requestUpdate(); } : null}">
        ${(k.pendingPoints > 0 || k.childPending > 0) ? html`
          <div class="ov-kid-flags">
            ${k.pendingPoints > 0 ? html`<span class="ov-kid-flag pend">⏳+${k.pendingPoints}</span>` : ""}
            ${k.childPending > 0 ? html`<span class="ov-kid-flag wait">${k.childPending}</span>` : ""}
          </div>` : ""}
        ${this._av(k.child, k.tone, design === "console" ? 34 : design === "cleanpro" ? 38 : 42)}
        <div class="pts ${design === "console" ? "num" : ""}">${k.points.toLocaleString()}</div>
        <div class="nm ${cls}">${nameUpper}</div>
        <div class="bar"><i style="width:${k.pct}%"></i></div>
      </div>`;
  }

  /** Admin "complete on behalf" panel — same handler as the classic tile. */
  _ovBehalf(k, pointsIcon) {
    return html`
      <div class="ov-behalf" @click="${(e) => e.stopPropagation()}">
        <div class="ov-behalf-hdr">${this._t('common.complete_on_behalf_heading')} · ${k.child.name}</div>
        ${k.outstanding.length === 0 ? html`
          <div class="ov-behalf-done">${this._t('common.complete_on_behalf_all_done')}</div>
        ` : k.outstanding.map(c => {
          const key = `behalf_${k.child.id}_${c.id}`;
          const loading = !!(this._loading && this._loading[key]);
          return html`
            <div class="ov-behalf-row">
              <span class="ov-behalf-name">${c.name}</span>
              <span class="muted num">${c.points}</span>
              <button class="btn good sm" ?disabled="${loading}"
                title="${this._t('common.complete_on_behalf_tooltip', { name: k.child.name })}"
                @click="${() => this._handleCompleteOnBehalf(c.id, k.child.id)}">✓</button>
            </div>`;
        })}
      </div>`;
  }

  _ovToday(design, done, total, pct) {
    const cls = design === "console" ? "cn" : design === "cleanpro" ? "cp" : "";
    if (design === "cleanpro") {
      return html`
        <div class="divide"></div>
        <div class="ov-today cp">
          <span class="lbl">${this._t("overview.designed.todays_progress")}</span>
          <span class="val num">${this._t("overview.designed.progress_detail", { done, total, pct })}</span>
        </div>`;
    }
    const lbl = design === "console"
      ? this._t("overview.designed.daily_completion")
      : html`🌟 ${this._t("overview.designed.todays_progress")}`;
    return html`
      <div class="ov-today ${cls}">
        <span class="lbl">${lbl}</span>
        <span class="val">${done} / ${total}</span>
      </div>`;
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

    const isParent = window.__taskmate_is_parent(this.hass);
    const outstanding = childChores.filter(c => {
      const doneToday = completions.filter(
        x => x.child_id === child.id && x.chore_id === c.id && !x.bonus_subtask_id
      ).length;
      return doneToday < (c.daily_limit || 1);
    });
    const isOpen = !!this._expanded[child.id];

    return html`
      <div class="child-tile">
        <div class="child-avatar">
          <ha-icon icon="${avatar}"></ha-icon>
        </div>
        <div class="child-main ${isParent ? 'tm-expandable' : ''}"
          @click="${isParent ? () => { this._expanded = { ...this._expanded, [child.id]: !isOpen }; this.requestUpdate(); } : null}">
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
          ${isParent && isOpen ? html`
            <div class="tm-outstanding" @click="${(e) => e.stopPropagation()}">
              <div class="tm-outstanding-hdr">${this._t('common.complete_on_behalf_heading')}</div>
              ${outstanding.length === 0 ? html`
                <div class="tm-all-done">${this._t('common.complete_on_behalf_all_done')}</div>
              ` : outstanding.map(c => {
                const key = `behalf_${child.id}_${c.id}`;
                const loading = !!(this._loading && this._loading[key]);
                return html`
                  <div class="tm-outstanding-row">
                    <span class="tm-outstanding-name">${c.name}</span>
                    <span class="tm-outstanding-pts">
                      <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:14px;"></ha-icon>${c.points}
                    </span>
                    <button class="btn-complete-behalf" ?disabled="${loading}"
                      title="${this._t('common.complete_on_behalf_tooltip', { name: child.name })}"
                      @click="${() => this._handleCompleteOnBehalf(c.id, child.id)}">
                      <ha-icon icon="mdi:check" style="--mdc-icon-size:16px;"></ha-icon>
                      ${this._t('common.complete_on_behalf')}
                    </button>
                  </div>
                `;
              })}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }

  async _handleCompleteOnBehalf(choreId, childId) {
    const key = `behalf_${childId}_${choreId}`;
    if (this._loading[key]) return;
    this._loading = { ...this._loading, [key]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "complete_chore", {
        chore_id: choreId,
        child_id: childId,
        as_parent: true,
      });
    } catch (e) {
      if (this.hass && this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: this._t('common.error'),
          message: String(e && e.message ? e.message : e),
          notification_id: `taskmate_overview_behalf_${key}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [key]: false };
      this.requestUpdate();
    }
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
      entity: this._t('overview.editor.entity_label'),
      title: this._t('overview.editor.title_label'),
      approvals_entity: this._t('overview.editor.approvals_entity_label'),
      card_design: this._t('common.design.field_label'),
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
      ${this._renderColourPicker('header_color', '#8e44ad')}
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
      if (value === '' || value === null || value === undefined) delete newConfig[key];
      else if (key === 'card_design' && value === 'global') delete newConfig[key];
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
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-overview-card", "overview"),
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
