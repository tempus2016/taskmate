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
  try {
    const d = JSON.parse(state.attributes.data || "{}");
    return d.children || [];
  } catch { return []; }
}

function weeklyPoints(child) {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  monday.setHours(0, 0, 0, 0);

  const history = child.history || [];
  return history
    .filter(e => e.approved && new Date(e.timestamp) >= monday)
    .reduce((s, e) => s + (e.points || 0), 0);
}

function childAvatar(child, colour) {
  const initials = (child.name || "?")
    .split(" ")
    .map(w => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return html`
    <div class="avatar" style="background:${colour}">
      ${child.avatar
        ? html`<img src="${child.avatar}" alt="${child.name}">`
        : initials}
    </div>`;
}

/* ─── Main card ────────────────────────────────────────────────────────── */

class TaskMatePointsDisplayCard extends LitElement {

  static get properties() {
    return {
      hass:   { type: Object },
      config: { type: Object },
      _animated: { type: Object },
    };
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
    return css`
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
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("TaskMate Points Display: 'entity' is required.");
    this.config = {
      mode: "single",
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

  getCardSize() { return 3; }

  /* ── Data helpers ───────────────────────────────────────────────────── */

  _stateObj() {
    return this.hass?.states?.[this.config.entity];
  }

  _allChildren() {
    const s = this._stateObj();
    return s ? getChildren(s) : [];
  }

  _rankedChildren() {
    return [...this._allChildren()].sort((a, b) => (b.points || 0) - (a.points || 0));
  }

  _singleChild() {
    const cid = this.config.child_id;
    return this._allChildren().find(c => c.id === cid) || null;
  }

  /* ── Render helpers ─────────────────────────────────────────────────── */

  _headerStyle() {
    return `background: ${this.config.header_color || DEFAULT_HEADER};`;
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
    const pts      = child.points || 0;
    const weekly   = weeklyPoints(child);
    const streak   = child.streak || 0;
    const rank     = this._rankedChildren().findIndex(c => c.id === child.id) + 1;

    return html`
      <div class="single-wrap">
        <div class="single-identity">
          ${childAvatar(child, colour)}
          <div class="child-name">${child.name}</div>
        </div>

        <div class="big-points">
          <div class="points-label">${this._t("points_display.total_points")}</div>
          <div class="points-number" style="color:${colour}">
            <span class="points-star">\u2B50</span>${pts.toLocaleString()}
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

    return html`
      <div class="multi-grid">
        ${ranked.map((child, idx) => {
          const colour  = CHILD_COLOURS[this._allChildren().indexOf(child) % CHILD_COLOURS.length];
          const pts     = child.points || 0;
          const weekly  = weeklyPoints(child);
          const streak  = child.streak || 0;
          const isTop   = idx === 0;
          return html`
            <div class="child-tile ${isTop ? "top-child" : ""}"
                 style="${isTop ? `border-color:${colour};` : ""}">
              ${isTop ? html`<div class="rank-badge">\u{1F947}</div>` :
                idx < 3 && this.config.show_rank ? html`<div class="rank-badge">${RANK_MEDAL[idx]}</div>` : ""}
              ${childAvatar(child, colour)}
              <div class="child-name">${child.name}</div>
              <div class="tile-points" style="color:${colour}">
                <span class="tile-star">\u2B50</span>${pts.toLocaleString()}
              </div>
              <div class="tile-label">${this._t("points_display.points_label")}</div>
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

    const total  = ranked.reduce((s, c) => s + (c.points || 0), 0);

    return html`
      <div class="cumulative-wrap">
        <div class="cumulative-total">
          <div class="points-label">${this._t("points_display.combined_family_total")}</div>
          <div class="points-number" style="color:${this.config.header_color || DEFAULT_HEADER}">
            <span class="points-star">\u{1F31F}</span>${total.toLocaleString()}
          </div>
          <div class="family-label">${this._t("points_display.family_subtitle", { count: ranked.length })}</div>
        </div>

        <div class="divider-label">${this._t("points_display.individual_scores")}</div>

        ${ranked.map((child, idx) => {
          const colour = CHILD_COLOURS[this._allChildren().indexOf(child) % CHILD_COLOURS.length];
          const pts    = child.points || 0;
          const pct    = total > 0 ? Math.round((pts / total) * 100) : 0;
          return html`
            <div class="cumul-row">
              ${childAvatar(child, colour)}
              <div class="cumul-row-inner">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px;">
                  <span class="child-name">${child.name}</span>
                  <span class="cumul-points" style="color:${colour}">
                    <span class="cumul-star">\u2B50</span>${pts.toLocaleString()}
                  </span>
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
      .editor-wrap { padding: 16px; display: flex; flex-direction: column; gap: 14px; }

      .field-row { display: flex; flex-direction: column; gap: 4px; }
      .field-label {
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      .segment-row { display: flex; gap: 8px; flex-wrap: wrap; }
      .segment-btn {
        flex: 1;
        min-width: 80px;
        padding: 8px 10px;
        border-radius: 10px;
        border: 2px solid var(--divider-color, #ddd);
        background: var(--card-background-color, #fff);
        cursor: pointer;
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--primary-text-color);
        text-align: center;
        transition: border-color 0.15s, background 0.15s;
      }
      .segment-btn.active {
        border-color: var(--primary-color, #3498db);
        background: var(--primary-color, #3498db);
        color: white;
      }

      select, input[type="text"] {
        width: 100%;
        padding: 9px 12px;
        border-radius: 10px;
        border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 0.9rem;
        box-sizing: border-box;
      }
      select:focus, input[type="text"]:focus {
        outline: none;
        border-color: var(--primary-color, #3498db);
      }

      .toggle-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }
      .toggle-label {
        font-size: 0.88rem;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .colour-row { display: flex; align-items: center; gap: 10px; }
      .colour-swatch {
        width: 36px; height: 36px; border-radius: 8px;
        border: 2px solid var(--divider-color, #ddd);
        flex-shrink: 0;
        cursor: pointer;
        overflow: hidden;
        position: relative;
      }
      .colour-swatch input[type="color"] {
        position: absolute; inset: 0; width: 100%; height: 100%;
        border: none; padding: 0; margin: 0; cursor: pointer; opacity: 0;
      }
      .colour-hex {
        flex: 1; font-size: 0.85rem; font-weight: 600;
        font-family: monospace; padding: 9px 12px;
        border-radius: 10px; border: 1px solid var(--divider-color, #ccc);
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
      }

      .section-header {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--secondary-text-color);
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
        padding-bottom: 6px;
        margin-top: 4px;
      }

      .info-note {
        font-size: 0.8rem;
        color: var(--secondary-text-color);
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 8px;
        padding: 8px 12px;
        line-height: 1.4;
      }
    `;
  }

  setConfig(config) {
    this.config = config;
  }

  updated(changed) {
    if (changed.has("hass") && this.hass && this.config?.entity) {
      this._loadChildren();
    }
  }

  _loadChildren() {
    const state = this.hass?.states?.[this.config.entity];
    if (!state) { this._children = []; return; }
    this._children = getChildren(state);
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config },
      bubbles: true,
      composed: true,
    }));
  }

  _set(key, value) {
    this._fire({ ...this.config, [key]: value });
  }

  _toggle(key) {
    this._set(key, !this.config[key]);
  }

  _onEntityChange(e) { this._set("entity", e.target.value); }
  _onTitleChange(e)  { this._set("title",  e.target.value); }
  _onColourChange(e) { this._set("header_color", e.target.value); }
  _onHexChange(e)    {
    const v = e.target.value;
    if (/^#[0-9a-fA-F]{6}$/.test(v)) this._set("header_color", v);
  }
  _onChildChange(e)  { this._set("child_id", e.target.value); }
  _setMode(m)        { this._set("mode", m); }

  render() {
    if (!this.config) return html``;

    const mode       = this.config.mode       || "single";
    const headerCol  = this.config.header_color || DEFAULT_HEADER;
    const showStreak = this.config.show_streak !== false;
    const showWeekly = this.config.show_weekly !== false;
    const showRank   = this.config.show_rank   !== false;

    return html`
      <div class="editor-wrap">

        <!-- Entity -->
        <div class="field-row">
          <div class="field-label">${this._t("points_display.editor.entity_label")}</div>
          <input type="text" .value="${this.config.entity || ""}"
            placeholder="sensor.taskmate_overview"
            @change="${this._onEntityChange}">
        </div>

        <!-- Display Mode -->
        <div class="section-header">${this._t("points_display.editor.display_mode")}</div>
        <div class="field-row">
          <div class="field-label">${this._t("points_display.editor.mode_label")}</div>
          <div class="segment-row">
            ${["single","multi","cumulative"].map(m => html`
              <button class="segment-btn ${mode === m ? "active" : ""}"
                      @click="${() => this._setMode(m)}">
                ${{ single: this._t("points_display.editor.mode_single"), multi: this._t("points_display.editor.mode_multi"), cumulative: this._t("points_display.editor.mode_cumulative") }[m]}
              </button>`)}
          </div>
        </div>

        ${mode === "single" ? html`
          <div class="field-row">
            <div class="field-label">${this._t("points_display.editor.child_label")}</div>
            ${this._children.length ? html`
              <select .value="${this.config.child_id || ""}" @change="${this._onChildChange}">
                <option value="">${this._t("points_display.editor.select_child")}</option>
                ${this._children.map(c => html`
                  <option value="${c.id}" ?selected="${c.id === this.config.child_id}">${c.name}</option>`)}
              </select>` : html`
              <input type="text" .value="${this.config.child_id || ""}"
                placeholder="${this._t("points_display.editor.child_id_placeholder")}"
                @change="${this._onChildChange}">
              <div class="info-note">${this._t("points_display.editor.child_id_note")}</div>`}
          </div>` : ""}

        <!-- Appearance -->
        <div class="section-header">${this._t("points_display.editor.appearance")}</div>

        <div class="field-row">
          <div class="field-label">${this._t("common.editor.header_colour")}</div>
          <div class="colour-row">
            <div class="colour-swatch" style="background:${headerCol};">
              <input type="color" .value="${headerCol}" @input="${this._onColourChange}">
            </div>
            <input type="text" class="colour-hex" .value="${headerCol}"
              maxlength="7" placeholder="#9b59b6" @change="${this._onHexChange}">
          </div>
        </div>

        <div class="field-row">
          <div class="field-label">${this._t("common.editor.card_title")}</div>
          <input type="text" .value="${this.config.title || ""}"
            placeholder="${this._t("points_display.editor.title_placeholder")}"
            @change="${this._onTitleChange}">
        </div>

        <!-- Stats to show -->
        <div class="section-header">${this._t("points_display.editor.stats_to_show")}</div>

        <div class="toggle-row">
          <span class="toggle-label">${this._t("points_display.editor.show_weekly")}</span>
          <ha-switch ?checked="${showWeekly}" @change="${() => this._toggle("show_weekly")}"></ha-switch>
        </div>
        <div class="toggle-row">
          <span class="toggle-label">${this._t("points_display.editor.show_streak")}</span>
          <ha-switch ?checked="${showStreak}" @change="${() => this._toggle("show_streak")}"></ha-switch>
        </div>
        ${mode !== "single" ? html`
          <div class="toggle-row">
            <span class="toggle-label">${this._t("points_display.editor.show_rank")}</span>
            <ha-switch ?checked="${showRank}" @change="${() => this._toggle("show_rank")}"></ha-switch>
          </div>` : ""}

      </div>`;
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
