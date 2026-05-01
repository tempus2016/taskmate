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

const DEFAULT_HEADER = "";

const CHILD_COLOURS = [
  "#e74c3c", "#3498db", "#27ae60", "#f39c12",
  "#9b59b6", "#1abc9c", "#e67e22", "#2980b9",
];

const RANK_MEDAL = ["\u{1F947}", "\u{1F948}", "\u{1F949}"];

/* ─── Utility helpers ──────────────────────────────────────────────────── */

function getChildren(state) {
  return state.attributes.children || [];
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
        color: var(--text-primary-color, #fff);
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
        color: var(--text-primary-color, #fff);
        flex-shrink: 0;
        overflow: hidden;
      }
      .avatar ha-icon {
        --mdc-icon-size: 32px;
        color: var(--text-primary-color, #fff);
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
        box-shadow: var(--ha-card-box-shadow, none);
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
        box-shadow: var(--ha-card-box-shadow, none);
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
      .child-tile:hover { box-shadow: var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.1)); }
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
        box-shadow: var(--ha-card-box-shadow, none);
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
    const c = this.config.header_color;
    return c ? `background: ${c};` : `background: var(--primary-color, #03a9f4);`;
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
          <div class="points-number" style="color:${this.config.header_color || 'var(--primary-color, #03a9f4)'}">
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
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, '#e67e22', '#27ae60', '#3498db', '#f1c40f', '#e74c3c', '#34495e'];
    const isActive = (c) => c.toLowerCase() === current.toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${this._t('common.editor.header_colour')}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current}
              @input=${(e) => this._set(key, e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current}"></span>
          </label>
          <span class="colour-hex">${current}</span>
          <div class="colour-presets">
            ${presets.map((p) => html`
              <button class="preset-swatch ${isActive(p) ? 'active' : ''}"
                style="background:${p}"
                title=${p}
                @click=${(e) => { e.preventDefault(); this._set(key, p); }}
              ></button>
            `)}
          </div>
          <button class="colour-reset"
            @click=${(e) => { e.preventDefault(); this._set(key, defaultValue); }}
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
      } else if (key === 'mode' && value === 'single') {
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
