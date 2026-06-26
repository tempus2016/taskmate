/**
 * TaskMate Points Display Card
 * A kid-friendly display card showing how many points a child (or all children) has.
 *
 * Modes:
 *   single      — One child, large animated point total. Great for a child's own dashboard.
 *   multi       — Grid showing every child with their own score. Good for family TV display.
 *   cumulative  — Combined family total with individual breakdowns below.
 *
 * Config options:
 *   entity         — sensor.taskmate_overview (required)
 *   mode           — single | multi | cumulative  (default: single)
 *   child_id       — required for single mode
 *   title          — optional header title override
 *   show_streak    — show streak badge (default: true)
 *   show_weekly    — show this week's points alongside all-time (default: true)
 *   show_rank      — show rank medal in multi/cumulative modes (default: true)
 *   animate        — animate number on load (default: true)
 *   header_color   — hex colour for the card header (default: #9b59b6)
 *   primary_display — current_points | career_score  (default: current_points)
 *
 * Version: 1.0.0
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css  = LitElement.prototype.css;

const DEFAULT_HEADER = "#9b59b6";

const CHILD_COLOURS = [
  "#e74c3c", "#3498db", "#27ae60", "#f39c12",
  "#9b59b6", "#1abc9c", "#e67e22", "#2980b9",
];

const RANK_MEDAL = ["\u{1F947}", "\u{1F948}", "\u{1F949}"];

/* ─── Utility helpers ──────────────────────────────────────────────────── */

function getChildren(state) {
  return state.attributes.children || [];
}

function weeklyPoints(child, tz) {
  const todayKey = new Date().toLocaleDateString("en-CA", { timeZone: tz });
  const today = new Date(todayKey + "T12:00:00"); // noon avoids DST edge cases
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const mondayKey = monday.toLocaleDateString("en-CA");

  const history = child.history || [];
  return history
    .filter(e => e.approved
      && new Date(e.timestamp).toLocaleDateString("en-CA", { timeZone: tz }) >= mondayKey)
    .reduce((s, e) => s + (e.points || 0), 0);
}

function childAvatar(child, colour) {
  const av = child.avatar || "mdi:account-circle";
  const isIcon = av.startsWith("mdi:");
  const initials = (child.name || "?")
    .split(" ")
    .map(w => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return html`
    <div class="avatar" style="background:${colour}">
      ${isIcon
        ? html`<ha-icon icon="${av}"></ha-icon>`
        : av
          ? html`<img src="${av}" alt="${child.name}">`
          : initials}
    </div>`;
}

/* ─── Main card ────────────────────────────────────────────────────────── */

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMatePointsDisplayCard extends LitElement {

  static get properties() {
    return {
      hass:   { type: Object },
      config: { type: Object },
      _animated: { type: Object },
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

  constructor() {
    super();
    this._animated = {};
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  static get styles() {
    const base = css`
      :host { display: block; }
      ha-card { overflow: hidden; font-family: inherit; }

      /* ── Header ── */
      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        color: white;
        gap: 10px;
      }
      .header-left {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
        flex: 1;
      }
      .header-icon { --mdc-icon-size: 26px; opacity: 0.9; flex-shrink: 0; }
      .card-title {
        font-size: 1.1rem;
        font-weight: 700;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        letter-spacing: 0.01em;
      }
      .mode-badge {
        background: rgba(255,255,255,0.2);
        border-radius: 10px;
        padding: 3px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: capitalize;
        flex-shrink: 0;
      }

      /* ── Shared body ── */
      .card-body { padding: 20px 18px 22px; }

      /* ── Avatar ── */
      .avatar {
        width: 56px;
        height: 56px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.3rem;
        font-weight: 800;
        color: white;
        flex-shrink: 0;
        overflow: hidden;
      }
      .avatar ha-icon {
        --mdc-icon-size: 32px;
        color: white;
      }
      .avatar img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        border-radius: 50%;
      }

      /* ══════════════════════════════════════════
         SINGLE MODE
      ══════════════════════════════════════════ */
      .single-wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 18px;
        text-align: center;
      }
      .single-identity {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
      }
      .single-wrap .avatar {
        width: 80px;
        height: 80px;
        font-size: 1.8rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
      }
      .single-wrap .avatar ha-icon {
        --mdc-icon-size: 48px;
      }
      .child-name {
        font-size: 1.25rem;
        font-weight: 700;
        color: var(--primary-text-color);
      }

      /* Big points number */
      .big-points {
        display: flex;
        flex-direction: column;
        align-items: center;
        background: var(--card-background-color, #fff);
        border: 2px solid var(--divider-color, #e0e0e0);
        border-radius: 24px;
        padding: 22px 40px;
        width: 100%;
        box-sizing: border-box;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        position: relative;
        overflow: hidden;
      }
      .big-points::before {
        content: "\u2B50";
        font-size: 7rem;
        position: absolute;
        right: -12px;
        bottom: -18px;
        opacity: 0.06;
        line-height: 1;
        pointer-events: none;
      }
      .points-label {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--secondary-text-color);
        margin-bottom: 4px;
      }
      .points-number {
        font-size: 4.5rem;
        font-weight: 900;
        line-height: 1;
        letter-spacing: -0.02em;
        color: var(--primary-text-color);
        transition: color 0.3s;
      }
      .points-star {
        font-size: 2rem;
        animation: star-spin 3s linear infinite;
        display: inline-block;
        margin-right: 6px;
        vertical-align: middle;
      }
      @keyframes star-spin {
        0% { transform: rotate(0deg) scale(1); }
        50% { transform: rotate(180deg) scale(1.15); }
        100% { transform: rotate(360deg) scale(1); }
      }

      /* Secondary metric line */
      .secondary-info {
        font-size: 0.88rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        margin-top: 8px;
      }
      .secondary-info .secondary-value {
        font-weight: 700;
        color: var(--primary-text-color);
      }

      /* Stats row under big number */
      .stats-row {
        display: flex;
        gap: 14px;
        width: 100%;
        justify-content: center;
        flex-wrap: wrap;
      }
      .stat-pill {
        display: flex;
        align-items: center;
        gap: 6px;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 20px;
        padding: 7px 14px;
        font-size: 0.88rem;
        font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap;
      }
      .stat-pill ha-icon { --mdc-icon-size: 17px; opacity: 0.75; }
      .stat-pill .pill-label {
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--secondary-text-color);
      }


      /* ══════════════════════════════════════════
         MULTI MODE
      ══════════════════════════════════════════ */
      .multi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 14px;
      }
      .child-tile {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 10px;
        padding: 18px 12px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 18px;
        text-align: center;
        position: relative;
        transition: box-shadow 0.2s;
        overflow: hidden;
      }
      .child-tile:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
      .child-tile .rank-badge {
        position: absolute;
        top: 8px;
        right: 10px;
        font-size: 1.1rem;
        line-height: 1;
      }
      .child-tile .avatar {
        width: 56px;
        height: 56px;
        font-size: 1.2rem;
      }
      .child-tile .child-name {
        font-size: 1rem;
        font-weight: 700;
      }
      .child-tile .tile-points {
        font-size: 2.4rem;
        font-weight: 900;
        line-height: 1;
        letter-spacing: -0.02em;
      }
      .child-tile .tile-star {
        font-size: 1rem;
        vertical-align: middle;
        margin-right: 2px;
        display: inline-block;
        animation: star-spin 4s linear infinite;
      }
      .child-tile .tile-label {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--secondary-text-color);
      }
      .child-tile .tile-weekly {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--secondary-text-color);
      }
      .child-tile .streak-chip {
        display: flex;
        align-items: center;
        gap: 3px;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 12px;
        padding: 3px 8px;
        font-size: 0.75rem;
        font-weight: 700;
      }

      /* Top-child accent bar */
      .child-tile.top-child::after {
        content: "";
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 4px;
        border-radius: 0 0 18px 18px;
      }

      /* ══════════════════════════════════════════
         CUMULATIVE MODE
      ══════════════════════════════════════════ */
      .cumulative-wrap {
        display: flex;
        flex-direction: column;
        gap: 18px;
      }
      .cumulative-total {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        padding: 22px;
        background: var(--card-background-color, #fff);
        border: 2px solid var(--divider-color, #e0e0e0);
        border-radius: 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        position: relative;
        overflow: hidden;
      }
      .cumulative-total::before {
        content: "\u{1F31F}";
        font-size: 6rem;
        position: absolute;
        right: -10px;
        bottom: -14px;
        opacity: 0.07;
        pointer-events: none;
      }
      .cumulative-total .points-label { margin-bottom: 6px; }
      .cumulative-total .points-number { font-size: 3.8rem; }
      .family-label {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        margin-top: 4px;
      }
      .divider-label {
        text-align: center;
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--secondary-text-color);
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .divider-label::before,
      .divider-label::after {
        content: "";
        flex: 1;
        height: 1px;
        background: var(--divider-color, #e0e0e0);
      }

      .cumul-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 14px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 14px;
      }
      .cumul-row .child-name {
        font-size: 1rem;
        font-weight: 700;
        flex: 1;
        min-width: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .cumul-row .cumul-points {
        font-size: 1.5rem;
        font-weight: 900;
        color: var(--primary-text-color);
        flex-shrink: 0;
      }
      .cumul-row .cumul-star {
        font-size: 0.85rem;
        animation: star-spin 5s linear infinite;
        display: inline-block;
        margin-right: 2px;
      }
      .cumul-bar-wrap {
        width: 100%;
        background: var(--secondary-background-color, #f0f0f0);
        border-radius: 6px;
        height: 6px;
        overflow: hidden;
        margin-top: 4px;
      }
      .cumul-bar-fill {
        height: 100%;
        border-radius: 6px;
        transition: width 1s cubic-bezier(.4,0,.2,1);
      }
      .cumul-row-inner {
        flex: 1;
        min-width: 0;
      }

      /* ── Empty state ── */
      .empty-state {
        text-align: center;
        padding: 32px 16px;
        color: var(--secondary-text-color);
        font-size: 0.9rem;
      }
      .empty-state ha-icon { --mdc-icon-size: 40px; opacity: 0.35; display: block; margin: 0 auto 10px; }

      /* Shared .tmd kit + design tokens are provided by taskmate-design.js styles(). */

      /* Points Display — Playroom */
      .pl-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 11px; }
      .pl-tile { background: var(--tmd-surface-2); border-radius: 18px; padding: 22px 12px 15px; text-align: center;
                 position: relative; display: flex; flex-direction: column; align-items: center; gap: 6px; }
      .pl-medal { position: absolute; top: 9px; left: 11px; font-size: 16px; line-height: 1; }
      .pl-pts { font-family: var(--tmd-font-display); font-weight: 800; font-size: 1.85rem; line-height: 1;
                color: var(--tmd-accent); }
      .pl-pts span { font-size: 0.9rem; margin-left: 2px; }
      .pl-name { font-weight: 800; font-size: 0.95rem; }
      .pl-chips { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }

      /* Points Display — Console */
      .cn-list { display: flex; flex-direction: column; gap: 9px; }
      .cn-row { display: flex; align-items: center; gap: 10px; background: var(--tmd-surface-2);
                border: 1px solid var(--tmd-border); border-radius: 10px; padding: 11px; }
      .cn-rank { font-size: 20px; width: 34px; color: var(--tmd-dim); }
      .cn-mid { flex: 1; min-width: 0; }
      .cn-name { font-weight: 700; margin-bottom: 6px; }
      .cn-right { text-align: right; }
      .cn-pts { font-size: 22px; }
      .cn-sub { font-size: 10px; }

      /* Points Display — Clean Pro */
      .cp-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 4px; }
      .cp-tile { text-align: center; padding: 8px 6px; display: flex; flex-direction: column;
                 align-items: center; gap: 6px; }
      .cp-pts { font-size: 1.6rem; }
      .cp-name { font-size: 0.82rem; font-weight: 600; }
      .cp-rank { background: transparent; }
      .cp-chips { display: flex; flex-wrap: wrap; gap: 5px; justify-content: center; }
      .cp-total { justify-content: space-between; }

      /* Points Display — Cumulative (designed) */
      .cumul-total-d { text-align: center; padding: 8px 0 14px; }
      .cumul-big { font-size: 2.3rem; color: var(--tmd-accent); margin-top: 2px; }
      .cumul-big-star { font-size: 1rem; }
      .cumul-list { display: flex; flex-direction: column; gap: 10px; }
      .cumul-row-d { display: flex; align-items: center; gap: 11px; background: var(--tmd-surface-2);
                     border: 1px solid var(--tmd-border); border-radius: 14px; padding: 11px; }
      .cumul-mid { flex: 1; min-width: 0; }
      .cumul-head { justify-content: space-between; margin-bottom: 6px; }
      .cumul-name { font-weight: 700; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("TaskMate Points Display: 'entity' is required.");
    this.config = {
      mode: "single",
      primary_display: "current_points",
      show_streak: true,
      show_weekly: true,
      show_rank: true,
      animate: true,
      header_color: DEFAULT_HEADER,
      ...config,
    };
  }

  static getConfigElement() {
    return document.createElement("taskmate-points-display-card-editor");
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", mode: "multi" };
  }

  getCardSize() { return 3; }

  /* ── Data helpers ───────────────────────────────────────────────────── */

  _stateObj() {
    return this.hass?.states?.[this.config.entity];
  }

  _allChildren() {
    const s = this._stateObj();
    return s ? getChildren(s) : [];
  }

  _isCareerMode() {
    return this.config.primary_display === "career_score";
  }

  _primaryValue(child) {
    return this._isCareerMode() ? (child.career_score || 0) : (child.points || 0);
  }

  _secondaryValue(child) {
    return this._isCareerMode() ? (child.points || 0) : (child.career_score || 0);
  }

  _primaryLabel() {
    return this._isCareerMode()
      ? this._t("points_display.career_score_label")
      : this._t("points_display.total_points");
  }

  _secondaryLabel() {
    return this._isCareerMode()
      ? this._t("points_display.current_points_label")
      : this._t("points_display.career_score_label");
  }

  _rankedChildren() {
    return [...this._allChildren()].sort((a, b) => this._primaryValue(b) - this._primaryValue(a));
  }

  _singleChild() {
    const cid = this.config.child_id;
    return this._allChildren().find(c => c.id === cid) || null;
  }

  /* ── Render helpers ─────────────────────────────────────────────────── */

  _headerStyle() {
    return `background: ${_safeColor(this.config.header_color, DEFAULT_HEADER)};`;
  }

  _defaultTitle() {
    const mode = this.config.mode || "single";
    if (mode === "single") {
      const c = this._singleChild();
      return c ? this._t("points_display.single_title", { name: c.name }) : this._t("points_display.default_title");
    }
    if (mode === "cumulative") return this._t("points_display.family_title");
    return this._t("points_display.board_title");
  }

  /* ── Single mode ────────────────────────────────────────────────────── */

  _renderSingle() {
    const child = this._singleChild();
    if (!child) {
      return html`<div class="empty-state">
        <ha-icon icon="mdi:account-question"></ha-icon>
        ${this._t("points_display.empty_no_child")}<br>
        ${this._t("points_display.empty_set_child_id")}
      </div>`;
    }

    const children = this._allChildren();
    const colour   = CHILD_COLOURS[children.indexOf(child) % CHILD_COLOURS.length];
    const primary  = this._primaryValue(child);
    const secondary = this._secondaryValue(child);
    const tz       = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const weekly   = weeklyPoints(child, tz);
    const streak   = child.streak || 0;
    const rank     = this._rankedChildren().findIndex(c => c.id === child.id) + 1;

    return html`
      <div class="single-wrap">
        <div class="single-identity">
          ${childAvatar(child, colour)}
          <div class="child-name">${child.name}</div>
        </div>

        <div class="big-points">
          <div class="points-label">${this._primaryLabel()}</div>
          <div class="points-number" style="color:${colour}">
            <span class="points-star">\u2B50</span>${primary.toLocaleString()}
          </div>
          <div class="secondary-info">
            ${this._secondaryLabel()}: <span class="secondary-value">${secondary.toLocaleString()}</span>
          </div>
        </div>

        <div class="stats-row">
          ${this.config.show_weekly ? html`
            <div class="stat-pill">
              <ha-icon icon="mdi:calendar-week"></ha-icon>
              <div>
                <div>${this._t("points_display.weekly_pts", { count: weekly })}</div>
                <div class="pill-label">${this._t("points_display.this_week")}</div>
              </div>
            </div>` : ""}
          ${this.config.show_streak ? html`
            <div class="stat-pill">
              <ha-icon icon="mdi:fire"></ha-icon>
              <div>
                <div>${streak === 1
                  ? this._t("points_display.streak_day", { count: streak })
                  : this._t("points_display.streak_days", { count: streak })}</div>
                <div class="pill-label">${this._t("points_display.streak")}</div>
              </div>
            </div>` : ""}
          ${this.config.show_rank && children.length > 1 ? html`
            <div class="stat-pill">
              <ha-icon icon="mdi:trophy"></ha-icon>
              <div>
                <div>${rank <= 3 ? RANK_MEDAL[rank - 1] : `#${rank}`}</div>
                <div class="pill-label">${this._t("points_display.rank")}</div>
              </div>
            </div>` : ""}
        </div>
      </div>`;
  }

  /* ── Multi mode ─────────────────────────────────────────────────────── */

  _renderMulti() {
    const ranked = this._rankedChildren();
    if (!ranked.length) {
      return html`<div class="empty-state">
        <ha-icon icon="mdi:account-group"></ha-icon>
        ${this._t("points_display.empty_no_children")}
      </div>`;
    }

    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;

    return html`
      <div class="multi-grid">
        ${ranked.map((child, idx) => {
          const colour    = CHILD_COLOURS[this._allChildren().indexOf(child) % CHILD_COLOURS.length];
          const primary   = this._primaryValue(child);
          const secondary = this._secondaryValue(child);
          const weekly    = weeklyPoints(child, tz);
          const streak    = child.streak || 0;
          const isTop     = idx === 0;
          return html`
            <div class="child-tile ${isTop ? "top-child" : ""}"
                 style="${isTop ? `border-color:${colour};` : ""}">
              ${isTop ? html`<div class="rank-badge">\u{1F947}</div>` :
                idx < 3 && this.config.show_rank ? html`<div class="rank-badge">${RANK_MEDAL[idx]}</div>` : ""}
              ${childAvatar(child, colour)}
              <div class="child-name">${child.name}</div>
              <div class="tile-points" style="color:${colour}">
                <span class="tile-star">\u2B50</span>${primary.toLocaleString()}
              </div>
              <div class="tile-label">${this._isCareerMode()
                ? this._t("points_display.career_score_label")
                : this._t("points_display.points_label")}</div>
              <div class="secondary-info">
                ${this._secondaryLabel()}: <span class="secondary-value">${secondary.toLocaleString()}</span>
              </div>
              ${this.config.show_weekly ? html`
                <div class="tile-weekly">${this._t("points_display.weekly_plus", { count: weekly })}</div>` : ""}
              ${this.config.show_streak ? html`
                <div class="streak-chip">\u{1F525} ${streak}</div>` : ""}
              ${isTop ? html`<div style="position:absolute;bottom:0;left:0;right:0;height:4px;background:${colour};border-radius:0 0 18px 18px;"></div>` : ""}
            </div>`;
        })}
      </div>`;
  }

  /* ── Cumulative mode ────────────────────────────────────────────────── */

  _renderCumulative() {
    const ranked = this._rankedChildren();
    if (!ranked.length) {
      return html`<div class="empty-state">
        <ha-icon icon="mdi:account-group"></ha-icon>
        ${this._t("points_display.empty_no_children")}
      </div>`;
    }

    const total     = ranked.reduce((s, c) => s + this._primaryValue(c), 0);
    const secTotal  = ranked.reduce((s, c) => s + this._secondaryValue(c), 0);

    return html`
      <div class="cumulative-wrap">
        <div class="cumulative-total">
          <div class="points-label">${this._t("points_display.combined_family_total")}</div>
          <div class="points-number" style="color:${_safeColor(this.config.header_color, DEFAULT_HEADER)}">
            <span class="points-star">\u{1F31F}</span>${total.toLocaleString()}
          </div>
          <div class="secondary-info">
            ${this._secondaryLabel()}: <span class="secondary-value">${secTotal.toLocaleString()}</span>
          </div>
          <div class="family-label">${this._t("points_display.family_subtitle", { count: ranked.length })}</div>
        </div>

        <div class="divider-label">${this._t("points_display.individual_scores")}</div>

        ${ranked.map((child, idx) => {
          const colour    = CHILD_COLOURS[this._allChildren().indexOf(child) % CHILD_COLOURS.length];
          const primary   = this._primaryValue(child);
          const secondary = this._secondaryValue(child);
          const pct       = total > 0 ? Math.round((primary / total) * 100) : 0;
          return html`
            <div class="cumul-row">
              ${childAvatar(child, colour)}
              <div class="cumul-row-inner">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px;">
                  <span class="child-name">${child.name}</span>
                  <span class="cumul-points" style="color:${colour}">
                    <span class="cumul-star">\u2B50</span>${primary.toLocaleString()}
                  </span>
                </div>
                <div class="secondary-info" style="margin-top:0;margin-bottom:4px;">
                  ${this._secondaryLabel()}: <span class="secondary-value">${secondary.toLocaleString()}</span>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                  <div class="cumul-bar-wrap" style="flex:1;">
                    <div class="cumul-bar-fill" style="width:${pct}%;background:${colour};"></div>
                  </div>
                  <span style="font-size:0.75rem;font-weight:600;color:var(--secondary-text-color);flex-shrink:0;">${pct}%</span>
                </div>
              </div>
              ${this.config.show_rank && idx < 3 ? html`
                <div style="font-size:1.4rem;flex-shrink:0;">${RANK_MEDAL[idx]}</div>` : ""}
            </div>`;
        })}
      </div>`;
  }

  /* ── Main render ────────────────────────────────────────────────────── */

  render() {
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") return this._renderDesigned(design);

    const mode  = this.config.mode || "single";
    const title = this.config.title || this._defaultTitle();

    const modeLabel = {
      single: this._t("points_display.mode_single"),
      multi: this._t("points_display.mode_multi"),
      cumulative: this._t("points_display.mode_cumulative"),
    }[mode] || mode;

    const modeIcon  = { single: "mdi:star-circle", multi: "mdi:account-group", cumulative: "mdi:sigma" }[mode] || "mdi:star";

    let body;
    if (mode === "multi")       body = this._renderMulti();
    else if (mode === "cumulative") body = this._renderCumulative();
    else                         body = this._renderSingle();

    return html`
      <ha-card>
        <div class="card-header" style="${this._headerStyle()}">
          <div class="header-left">
            <ha-icon class="header-icon" icon="${modeIcon}"></ha-icon>
            <span class="card-title">${title}</span>
          </div>
          <div class="mode-badge">${modeLabel}</div>
        </div>
        <div class="card-body">${body}</div>
      </ha-card>`;
  }

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns (§card-points-display).
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

  _renderDesigned(design) {
    const mode  = this.config.mode || "single";
    const title = this.config.title || this._defaultTitle();
    const hd    = _safeColor(this.config.header_color, DEFAULT_HEADER);
    const tz    = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;

    let ranked = this._rankedChildren();
    if (mode === "single") {
      const c = this._singleChild();
      ranked = c ? [c] : [];
    }

    const header = html`
      <div class="tmd-hd">
        <span class="ic">⭐</span>
        <span class="tt">${title}</span>
        ${mode === "multi" ? html`<span class="pill">${this._t("points_display.mode_multi")}</span>` : ""}
      </div>`;

    if (!ranked.length) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${header}
        <div class="tmd-bd"><div class="tmd-empty">${this._t("points_display.empty_no_children")}</div></div>
      </ha-card>`;
    }

    const rows = ranked.map((child) => ({
      child,
      tone:   this._designTone(this._allChildren().indexOf(child)),
      points: this._primaryValue(child),
      weekly: weeklyPoints(child, tz),
      // Overview summary exposes current_streak (child.streak doesn't exist).
      streak: child.current_streak ?? child.streak ?? 0,
      pct:    0,
    }));
    const total = rows.reduce((s, r) => s + r.points, 0);
    rows.forEach((r) => { r.pct = total > 0 ? Math.round((r.points / total) * 100) : 0; });
    rows.forEach((r, i) => { r.rank = i; });

    const body =
      mode === "cumulative" ? this._cumulBody(rows, total) :
      design === "playroom" ? this._designPlayroom(rows) :
      design === "console"  ? this._designConsole(rows) :
                              this._designCleanpro(rows, total);

    return html`<ha-card class="tmd" style="--hd:${hd}">${header}<div class="tmd-bd">${body}</div></ha-card>`;
  }

  _designPlayroom(rows) {
    const showRank = this.config.show_rank !== false;
    const showWeekly = this.config.show_weekly !== false;
    const showStreak = this.config.show_streak !== false;
    return html`
      <div class="pl-grid">
        ${rows.map((r) => html`
          <div class="pl-tile" style="--ac:${r.tone}">
            ${showRank && r.rank < 3 ? html`<div class="pl-medal">${RANK_MEDAL[r.rank]}</div>` : ""}
            ${this._av(r.child, r.tone, 52)}
            <div class="pl-pts">${r.points.toLocaleString()}<span>⭐</span></div>
            <div class="pl-name">${r.child.name}</div>
            ${showWeekly || (showStreak && r.streak) ? html`
              <div class="pl-chips">
                ${showWeekly ? html`<div class="chip soft">${this._t("points_display.weekly_plus", { count: r.weekly })}</div>` : ""}
                ${showStreak && r.streak ? html`<div class="chip soft">\u{1F525} ${r.streak}</div>` : ""}
              </div>` : ""}
          </div>`)}
      </div>`;
  }

  _designConsole(rows) {
    const max = Math.max(...rows.map((r) => r.points), 1);
    const showRank = this.config.show_rank !== false;
    const showWeekly = this.config.show_weekly !== false;
    const showStreak = this.config.show_streak !== false;
    return html`
      <div class="cn-list">
        ${rows.map((r) => html`
          <div class="cn-row" style="--ac:${r.tone}">
            ${showRank ? html`<div class="num cn-rank ${r.rank === 0 ? "lead" : ""}">#${r.rank + 1}</div>` : ""}
            ${this._av(r.child, r.tone, 38)}
            <div class="cn-mid">
              <div class="cn-name">${r.child.name}</div>
              <div class="bar"><i style="width:${Math.round((r.points / max) * 100)}%"></i></div>
            </div>
            <div class="cn-right">
              <div class="num cn-pts ${r.rank === 0 ? "lead" : ""}">${r.points.toLocaleString()}</div>
              <div class="cn-sub muted">XP${showWeekly ? html` · +${r.weekly}` : ""}${showStreak && r.streak ? html` · \u{1F525}${r.streak}` : ""}</div>
            </div>
          </div>`)}
      </div>`;
  }

  _designCleanpro(rows, total) {
    const showRank = this.config.show_rank !== false;
    const showWeekly = this.config.show_weekly !== false;
    const showStreak = this.config.show_streak !== false;
    return html`
      <div class="cp-grid">
        ${rows.map((r) => html`
          <div class="cp-tile" style="--ac:${r.tone}">
            ${this._av(r.child, r.tone, 46)}
            <div class="big cp-pts">${r.points.toLocaleString()}</div>
            <div class="cp-name">${r.child.name}</div>
            <div class="cp-chips">
              ${showRank ? html`<div class="chip cp-rank">${r.rank === 0
                ? html`<span class="lead-dot">●</span> ` : ""}#${r.rank + 1}</div>` : ""}
              ${showWeekly ? html`<div class="chip cp-rank">+${r.weekly}</div>` : ""}
              ${showStreak && r.streak ? html`<div class="chip cp-rank">\u{1F525} ${r.streak}</div>` : ""}
            </div>
          </div>`)}
      </div>
      ${rows.length > 1 ? html`
        <div class="divide"></div>
        <div class="row cp-total">
          <span class="muted">${this._t("points_display.combined_family_total")}</span>
          <span class="num">${total.toLocaleString()} ${this._t("points_display.points_label")}</span>
        </div>` : ""}`;
  }

  _cumulBody(rows, total) {
    return html`
      <div class="cumul-total-d">
        <div class="muted">${this._t("points_display.combined_family_total")}</div>
        <div class="big cumul-big">${total.toLocaleString()} <span class="cumul-big-star">⭐</span></div>
      </div>
      <div class="cumul-list">
        ${rows.map((r) => html`
          <div class="cumul-row-d" style="--ac:${r.tone}">
            ${this._av(r.child, r.tone, 40)}
            <div class="cumul-mid">
              <div class="row cumul-head">
                <span class="cumul-name">${r.child.name}</span>
                <span class="num">${r.points.toLocaleString()}</span>
              </div>
              <div class="bar"><i style="width:${r.pct}%"></i></div>
            </div>
          </div>`)}
      </div>`;
  }
}

customElements.define("taskmate-points-display-card", TaskMatePointsDisplayCard);


/* ═══════════════════════════════════════════════════════════════════════
   UI EDITOR
═══════════════════════════════════════════════════════════════════════ */

class TaskMatePointsDisplayCardEditor extends LitElement {

  static get properties() {
    return {
      hass:   { type: Object },
      config: { type: Object },
      _children: { type: Array },
    };
  }

  constructor() {
    super();
    this._children = [];
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  static get styles() {
    return css`
      :host { display: block; padding: 8px 0; }
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

  setConfig(config) {
    this.config = config;
  }

  updated(changed) {
    if (changed.has('hass') && this.hass && this.config?.entity) {
      this._loadChildren();
    }
  }

  _loadChildren() {
    const state = this.hass?.states?.[this.config.entity];
    if (!state) { this._children = []; return; }
    this._children = getChildren(state);
  }

  _buildSchema() {
    const mode = this.config.mode || 'single';
    const schema = [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'mode',
        selector: {
          select: {
            options: [
              { value: 'single', label: this._t('points_display.editor.mode_single') },
              { value: 'multi', label: this._t('points_display.editor.mode_multi') },
              { value: 'cumulative', label: this._t('points_display.editor.mode_cumulative') },
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
      {
        name: 'primary_display',
        selector: {
          select: {
            options: [
              { value: 'current_points', label: this._t('points_display.editor.primary_current_points') },
              { value: 'career_score', label: this._t('points_display.editor.primary_career_score') },
            ],
            mode: 'dropdown',
          },
        },
      },
    ];

    if (mode === 'single') {
      schema.push({
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('points_display.editor.select_child') },
              ...this._children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: 'dropdown',
          },
        },
      });
    }

    schema.push({ name: 'show_weekly', selector: { boolean: {} } });
    schema.push({ name: 'show_streak', selector: { boolean: {} } });
    if (mode !== 'single') {
      schema.push({ name: 'show_rank', selector: { boolean: {} } });
    }
    return schema;
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('points_display.editor.entity_label'),
      title: this._t('common.editor.card_title'),
      mode: this._t('points_display.editor.mode_label'),
      card_design: this._t('common.design.field_label'),
      primary_display: this._t('points_display.editor.primary_display'),
      child_id: this._t('points_display.editor.child_label'),
      show_weekly: this._t('points_display.editor.show_weekly'),
      show_streak: this._t('points_display.editor.show_streak'),
      show_rank: this._t('points_display.editor.show_rank'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = () => '';

  render() {
    if (!this.config) return html``;
    const mode = this.config.mode || 'single';
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      mode,
      card_design: this.config.card_design || 'global',
      primary_display: this.config.primary_display || 'current_points',
      child_id: this.config.child_id || '',
      show_weekly: this.config.show_weekly !== false,
      show_streak: this.config.show_streak !== false,
      show_rank: this.config.show_rank !== false,
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
      ${this._renderColourPicker('header_color', DEFAULT_HEADER)}
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
      onInput: (v) => this._update(key, v),
      onPreset: (v) => this._update(key, v),
      onReset: () => this._update(key, defaultValue),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === '' || value === null || value === undefined) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (key === 'mode' && value === 'single') {
        delete newConfig[key];
      } else if (key === 'primary_display' && value === 'current_points') {
        delete newConfig[key];
      } else if ((key === 'show_weekly' || key === 'show_streak' || key === 'show_rank') && value === true) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this._fire(newConfig);
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config },
      bubbles: true,
      composed: true,
    }));
  }

  _set(key, value) {
    this._fire({ ...this.config, [key]: value });
  }
}

customElements.define("taskmate-points-display-card-editor", TaskMatePointsDisplayCardEditor);

/* ── Registration ─────────────────────────────────────────────────────── */

window.customCards = window.customCards || [];
window.customCards.push({
  type:        "taskmate-points-display-card",
  name:        "TaskMate \u2014 Points Display",
  description: "Kid-friendly display of points. Supports single child, all children, or combined family total.",
  preview:     true,
  configElement: "taskmate-points-display-card-editor",
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-points-display-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE POINTS DISPLAY CARD %c v" + _tmVersion + " ",
  "background:#566573;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
