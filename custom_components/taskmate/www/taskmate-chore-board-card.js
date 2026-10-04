/**
 * TaskMate Chore Board Card (#1017)
 *
 * The admin panel's Today-page chore board as a dashboard card: rows are the
 * family's time periods, columns are the children, and each cell lists that
 * child's chores for the period with where they stand (done, awaiting
 * approval, to do, missed). A This week toggle swaps in done/total per child
 * for the last seven days.
 *
 * Tapping a chore that is still to do completes it for that child — the same
 * button press / complete_chore call the child card makes — and offers Undo
 * on a short toast. Chores that need the child card's own flow (a photo, a
 * timer, a note or a team join) say so instead of completing.
 *
 * Reads `chore_board` from sensor.taskmate_chore_board, and `children`,
 * `chores`, `time_periods` and `todays_completions` from the overview entity
 * and its companions, all through the attribute resolver.
 *
 * Single layout, so it consumes the design tokens directly (like the bounty
 * card): every --tmd-* reference carries the classic value as its fallback.
 * Layout classes carry a cb- prefix — the shared design kit defines its own
 * .btn / .bar / .av / .chip.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const _ltrNums = (s) => (window.__taskmate_design && window.__taskmate_design.ltrNums ? window.__taskmate_design.ltrNums(s) : s);
const DEFAULT_ACCENT = "#3f51b5";
// Child colours by position; a design's own palette wins when it has one.
const CHILD_COLOURS = ["#ff6b9d", "#3498db", "#1abc9c", "#e67e22", "#9b59b6", "#2ecc71"];
const BUILTIN_PERIODS = ["morning", "afternoon", "evening", "night"];
const STATUSES = ["done", "pending", "todo", "missed"];
const TOAST_MS = 5000;

class TaskMateChoreBoardCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _view: { type: String },
      _toast: { type: Object },
      _busy: { type: Object },
    };
  }

  constructor() {
    super();
    this._view = null;
    this._toast = null;
    this._busy = {};
    // `${chore}|${child}` -> { status, count, board } — a tap's result shown
    // until the board the tap was made on is replaced by a newer one.
    this._optimistic = {};
    this._toastTimer = null;
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("You need to define an entity");
    this.config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  static getConfigElement() {
    return document.createElement("taskmate-chore-board-card-editor");
  }

  getCardSize() {
    return 6;
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this._toastTimer);
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass") && changedProps.size === 1) {
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

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
  }

  /** The children to show, in the family's order; none picked means everyone. */
  _kids(attrs) {
    const all = attrs.children || [];
    const picked = Array.isArray(this.config.children) ? this.config.children.map(String) : [];
    return picked.length ? all.filter(c => picked.includes(String(c.id))) : all;
  }

  _kidIndex(attrs, id) {
    return Math.max(0, (attrs.children || []).findIndex(c => String(c.id) === String(id)));
  }

  _kidColour(attrs, id) {
    const i = this._kidIndex(attrs, id);
    return `var(--tmd-c${(i % 6) + 1}, ${CHILD_COLOURS[i % CHILD_COLOURS.length]})`;
  }

  /** Time periods in the order of the day, then Anytime for everything else. */
  _periods(attrs) {
    const hhmm = (s) => {
      const [h, m] = String(s || "").split(":").map(Number);
      return Number.isFinite(h) ? h + (m || 0) / 60 : 0;
    };
    let periods;
    if (Array.isArray(attrs.time_periods) && attrs.time_periods.length) {
      periods = attrs.time_periods
        .filter(p => p && p.id)
        .map(p => ({ id: p.id, label: p.label || "", icon: p.icon || "mdi:clock-outline", start: hhmm(p.start) }))
        .sort((a, b) => a.start - b.start);
    } else {
      periods = [
        { id: "morning", icon: "mdi:weather-sunset-up" },
        { id: "afternoon", icon: "mdi:weather-sunny" },
        { id: "evening", icon: "mdi:weather-sunset-down" },
        { id: "night", icon: "mdi:weather-night" },
      ];
    }
    const label = p => p.label || (BUILTIN_PERIODS.includes(p.id) ? this._t(`common.${p.id}`) : p.id);
    return [
      ...periods.filter(p => p.id !== "anytime").map(p => ({ id: p.id, icon: p.icon, label: label(p) })),
      { id: "anytime", icon: "mdi:clock-outline", label: this._t("common.anytime") },
    ];
  }

  /** The board, with any tap still waiting for the server laid over it. */
  _boardEntries(board) {
    const entries = (board && board.board && board.board.children) || [];
    return entries.map(e => ({
      ...e,
      chores: (e.chores || []).map(item => {
        const key = `${item.chore_id}|${e.child_id}`;
        const opt = this._optimistic[key];
        if (!opt) return item;
        if (opt.board !== board) {
          delete this._optimistic[key];
          return item;
        }
        return { ...item, status: opt.status, count: opt.count };
      }),
    }));
  }

  /** A chore whose completion needs the child card: a photo, timer, note or team. */
  _needsChildCard(chore) {
    return !!(chore.require_photo || chore.task_type === "timed" || chore.open_ended || chore.team);
  }

  _applyDesign() {
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    // Inline on the host: a <style> in the template is ordered before
    // adoptedStyleSheets and would lose to the :host default.
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--cb-accent", _safeColor(configured, DEFAULT_ACCENT));
    } else {
      this.style.removeProperty("--cb-accent");
    }
    return design;
  }

  // ── actions ─────────────────────────────────────────────────────────────

  _playSound(name) {
    const engine = window.__taskmate_sounds;
    if (engine) engine.play(name, this._attrs().custom_sounds || []);
  }

  _showToast(message, undo = null) {
    clearTimeout(this._toastTimer);
    this._toast = { message, undo };
    this._toastTimer = setTimeout(() => { this._toast = null; }, TOAST_MS);
  }

  async _tap(item, chore, kid, board) {
    if (this.config.tap_to_complete === false) return;
    if (item.status !== "todo" && item.status !== "missed") return;
    if (this._needsChildCard(chore)) {
      this._showToast(this._t("chore_board.finish_on_card", { chore: chore.name, name: kid.name }));
      return;
    }
    const key = `${chore.id}|${kid.id}`;
    if (this._busy[key]) return;
    this._busy = { ...this._busy, [key]: true };
    const count = (Number(item.count) || 0) + 1;
    const limit = Math.max(1, Number(item.limit) || 1);
    const finished = count >= limit;
    const status = !finished ? "todo" : chore.requires_approval === false ? "done" : "pending";
    this._optimistic = { ...this._optimistic, [key]: { status, count, board } };
    try {
      // The button entity first, so automations triggered by it fire — the
      // same order the child card uses.
      const button = window.__taskmate_find_button && window.__taskmate_find_button(this.hass, kid.id, "complete", chore.id);
      if (button) {
        await this.hass.callService("button", "press", { entity_id: button });
      } else {
        await this.hass.callService("taskmate", "complete_chore", { chore_id: chore.id, child_id: kid.id });
      }
      this._playSound(chore.completion_sound || "coin");
      const msg = status === "pending" ? "chore_board.sent_for_approval" : "chore_board.marked_done";
      this._showToast(this._t(msg, { chore: chore.name, name: kid.name }), { chore_id: chore.id, child_id: kid.id });
    } catch (err) {
      const next = { ...this._optimistic };
      delete next[key];
      this._optimistic = next;
      this._showToast(this._t("chore_board.error", { message: String(err?.message || err) }));
    } finally {
      this._busy = { ...this._busy, [key]: false };
    }
  }

  /** Take back the completion the last tap made. */
  async _undo(target) {
    clearTimeout(this._toastTimer);
    this._toast = null;
    const latest = (this._attrs().todays_completions || [])
      .filter(c => c.chore_id === target.chore_id && c.child_id === target.child_id && !c.bonus_subtask_id)
      .sort((a, b) => new Date(b.completed_at || 0) - new Date(a.completed_at || 0))[0];
    const completionId = latest && (latest.completion_id || latest.id);
    if (!completionId) {
      this._showToast(this._t("chore_board.undo_failed"));
      return;
    }
    let service;
    if (this.config?.show_parent_actions !== false
      && window.__taskmate_is_parent && window.__taskmate_is_parent(this.hass)) {
      service = "reject_chore";
    } else {
      // A child's own tick, inside the undo window the server publishes (#918).
      const until = Date.parse(latest.child_undo_until || "");
      if (latest.child_undo_pending === true || (Number.isFinite(until) && until > Date.now())) {
        service = "undo_chore";
      } else {
        this._showToast(this._t("child.undo_not_allowed"));
        return;
      }
    }
    try {
      await this.hass.callService("taskmate", service, { completion_id: completionId });
      const next = { ...this._optimistic };
      delete next[`${target.chore_id}|${target.child_id}`];
      this._optimistic = next;
      this._playSound("undo");
    } catch (err) {
      this._showToast(this._t("chore_board.error", { message: String(err?.message || err) }));
    }
  }

  // ── render ──────────────────────────────────────────────────────────────

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const attrs = this._attrs();
    const title = this.config.title || this._t("chore_board.title");
    const showWeek = this.config.show_week !== false;
    const view = showWeek ? (this._view || (this.config.default_view === "week" ? "week" : "today")) : "today";
    const kids = this._kids(attrs);
    const board = attrs.chore_board;

    let body;
    if (!this.hass.states[this.config.entity]) {
      body = html`<div class="cb-empty">${this._t("common.entity_not_found", { entity: this.config.entity })}</div>`;
    } else if (!board) {
      body = html`<div class="cb-empty">${this._t("chore_board.unavailable")}</div>`;
    } else if (!kids.length) {
      body = html`<div class="cb-empty">${this._t("chore_board.no_children")}</div>`;
    } else if (view === "week") {
      body = this._renderWeek(attrs, kids, board);
    } else {
      body = this._renderToday(attrs, kids, board);
    }

    return html`
      <ha-card>
        <div class="cb-hd">
          <ha-icon class="cb-hd-icon" icon="mdi:view-grid-outline"></ha-icon>
          <div class="cb-hd-title">${title}</div>
          ${showWeek ? html`
            <div class="cb-seg" role="tablist">
              ${["today", "week"].map(v => html`
                <button type="button" role="tab" class="${view === v ? "on" : ""}" aria-selected="${view === v ? "true" : "false"}"
                        @click=${() => { this._view = v; }}>${this._t(v === "week" ? "chore_board.this_week" : "chore_board.today")}</button>`)}
            </div>` : ""}
        </div>
        <div class="cb-body ${this._toast ? "cb-has-toast" : ""}">${body}</div>
        ${this._toast ? html`
          <div class="cb-toast" role="status">
            <span>${this._toast.message}</span>
            ${this._toast.undo ? html`<button type="button" @click=${() => this._undo(this._toast.undo)}>${this._t("chore_board.undo")}</button>` : ""}
          </div>` : ""}
      </ha-card>
    `;
  }

  _avatar(attrs, kid) {
    const a = kid.avatar || "";
    const inner = a.startsWith("mdi:")
      ? html`<ha-icon icon="${a}"></ha-icon>`
      : a ? html`<img src="${a}" alt="">` : (kid.name || "?").charAt(0).toUpperCase();
    return html`<span class="cb-av" style="--cb-kc:${this._kidColour(attrs, kid.id)}">${inner}</span>`;
  }

  /** Each shown child's chores, grouped by time period. */
  _cells(attrs, kids, board, periods) {
    const choreById = Object.fromEntries((attrs.chores || []).map(c => [c.id, c]));
    const known = new Set(periods.map(p => p.id));
    const entries = this._boardEntries(board);
    const cells = {};
    const totals = {};
    for (const kid of kids) {
      const entry = entries.find(e => String(e.child_id) === String(kid.id));
      let done = 0;
      let due = 0;
      for (const item of (entry && entry.chores) || []) {
        const chore = choreById[item.chore_id];
        if (!chore) continue;
        due += 1;
        if (item.status === "done" || item.status === "pending") done += 1;
        const slot = known.has(chore.time_category) ? chore.time_category : "anytime";
        (cells[`${slot}|${kid.id}`] = cells[`${slot}|${kid.id}`] || []).push({ item, chore });
      }
      totals[kid.id] = { done, due };
    }
    return { cells, totals };
  }

  _visibleRows(kids, periods, cells) {
    const finished = list => list.every(({ item }) => item.status === "done" || item.status === "pending");
    return periods.filter(p => {
      const lists = kids.map(k => cells[`${p.id}|${k.id}`] || []);
      if (!lists.some(l => l.length)) return false;
      return !(this.config.hide_done_periods && lists.every(finished));
    });
  }

  _chip(item, chore, kid, board) {
    const statusLabel = this._t(`chore_board.status_${item.status}`);
    const limit = Math.max(1, Number(item.limit) || 1);
    const count = limit > 1 ? html` <small>${_ltrNums(`${item.count || 0}/${limit}`)}</small>` : "";
    const extra = this._needsChildCard(chore)
      ? html`<ha-icon class="cb-x" icon="${chore.require_photo ? "mdi:camera-outline" : chore.task_type === "timed" ? "mdi:timer-sand" : chore.team ? "mdi:account-group-outline" : "mdi:pencil-outline"}"></ha-icon>`
      : "";
    const inner = html`<i class="cb-dot" aria-hidden="true"></i><span class="cb-n">${chore.name}${count}</span>${extra}<span class="cb-sr">${statusLabel}</span>`;
    const tappable = this.config.tap_to_complete !== false && (item.status === "todo" || item.status === "missed");
    const key = `${chore.id}|${kid.id}`;
    return tappable
      ? html`<button type="button" class="cb-chip ${item.status}" title="${chore.name} · ${statusLabel}"
                ?disabled=${!!this._busy[key]} @click=${() => this._tap(item, chore, kid, board)}>${inner}</button>`
      : html`<span class="cb-chip ${item.status}" title="${chore.name} · ${statusLabel}">${inner}</span>`;
  }

  _legend() {
    if (this.config.show_legend === false) return "";
    return html`<div class="cb-legend">${STATUSES.map(s => html`
      <span class="cb-chip ${s}"><i class="cb-dot" aria-hidden="true"></i><span class="cb-n">${this._t(`chore_board.status_${s}`)}</span></span>`)}</div>`;
  }

  _renderToday(attrs, kids, board) {
    const periods = this._periods(attrs);
    const { cells, totals } = this._cells(attrs, kids, board, periods);
    const rows = this._visibleRows(kids, periods, cells);
    const anything = kids.some(k => totals[k.id].due);
    if (!anything) return html`<div class="cb-empty">${this._t("chore_board.empty")}</div>`;
    if (!rows.length) return html`<div class="cb-empty">${this._t("chore_board.all_done")}</div>${this._legend()}`;

    if (kids.length === 1) {
      const kid = kids[0];
      const { done, due } = totals[kid.id];
      return html`
        <div class="cb-list">
          <div class="cb-prog-row">
            ${this._avatar(attrs, kid)}<span class="cb-prog-name">${kid.name}</span>
            <span class="cb-prog-n">${_ltrNums(`${done}/${due}`)}</span>
          </div>
          <div class="cb-prog"><i style="width:${due ? Math.round((done / due) * 100) : 100}%;background:${this._kidColour(attrs, kid.id)}"></i></div>
          ${rows.map(p => html`
            <div class="cb-grp"><ha-icon icon="${p.icon}"></ha-icon>${p.label}</div>
            ${(cells[`${p.id}|${kid.id}`] || []).map(({ item, chore }) => this._chip(item, chore, kid, board))}`)}
        </div>
        ${this._legend()}`;
    }

    return html`
      <div class="cb-wrap">
        <div class="cb-board" style="--cb-cols:${kids.length}">
          <div class="cb-sticky"></div>
          ${kids.map(k => html`
            <div class="cb-kid">${this._avatar(attrs, k)}<span>${k.name}</span>
              <small>${_ltrNums(`${totals[k.id].done}/${totals[k.id].due}`)}</small></div>`)}
          ${rows.map(p => html`
            <div class="cb-slot cb-sticky"><ha-icon icon="${p.icon}"></ha-icon><span>${p.label}</span></div>
            ${kids.map(k => {
              const items = cells[`${p.id}|${k.id}`] || [];
              return html`<div class="cb-cell">${items.length
                ? items.map(({ item, chore }) => this._chip(item, chore, k, board))
                : html`<span class="cb-none">–</span>`}</div>`;
            })}`)}
        </div>
      </div>
      ${this._legend()}`;
  }

  _renderWeek(attrs, kids, board) {
    const history = board.history || {};
    const today = board.board && board.board.date;
    const first = kids.map(k => history[k.id]).find(Boolean) || [];
    const lang = this.hass?.locale?.language || this.hass?.language || undefined;
    const dayName = iso => {
      if (iso === today) return this._t("chore_board.today");
      try {
        return new Date(`${iso}T12:00:00`).toLocaleDateString(lang, { weekday: "short" });
      } catch (_e) {
        return iso;
      }
    };
    const gaps = kids.some(k => (history[k.id] || []).some(d => d.due == null));
    return html`
      <div class="cb-wrap">
        <div class="cb-week" style="--cb-days:${first.length || 7}">
          <div></div>
          ${first.map(d => html`<div class="cb-wh ${d.date === today ? "today" : ""}">${dayName(d.date)}</div>`)}
          ${kids.map(k => html`
            <div class="cb-wk">${this._avatar(attrs, k)}<span>${k.name}</span></div>
            ${(history[k.id] || []).map(d => {
              if (d.due == null) return html`<div class="cb-wc none" title="${this._t("chore_board.not_recorded")}">–</div>`;
              const pct = d.due ? Math.round((d.done / d.due) * 100) : 100;
              return html`<div class="cb-wc" style="--cb-kc:${this._kidColour(attrs, k.id)};--cb-p:${pct}"
                               title="${dayName(d.date)} · ${d.done}/${d.due}">${d.due ? _ltrNums(`${d.done}/${d.due}`) : "–"}</div>`;
            })}`)}
        </div>
      </div>
      ${gaps ? html`<p class="cb-hint">${this._t("chore_board.week_hint")}</p>` : ""}`;
  }

  static get styles() {
    const base = css`
      :host { display: block; --cb-accent: var(--tmd-accent, #3f51b5); }
      ha-card {
        position: relative;
        overflow: hidden;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px));
        font-family: var(--tmd-font-body, inherit);
      }
      .cb-hd {
        display: flex; align-items: center; gap: 10px;
        padding: 12px 16px;
        background: var(--cb-accent);
        color: var(--tmd-hd-text, #fff);
      }
      :host([data-tm-design="playroom"]) .cb-hd {
        background: linear-gradient(135deg, var(--cb-accent), color-mix(in srgb, var(--cb-accent) 72%, #fff));
      }
      .cb-hd-icon { --mdc-icon-size: 26px; flex: none; opacity: .95; }
      .cb-hd-title {
        flex: 1; min-width: 0;
        font-family: var(--tmd-font-display, inherit);
        font-size: 1.2rem; font-weight: 600;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .cb-seg { display: inline-flex; flex: none; background: rgba(255, 255, 255, .18); border-radius: 9px; padding: 2px; gap: 2px; }
      .cb-seg button {
        background: none; border: 0; cursor: pointer;
        color: inherit; opacity: .85;
        font: inherit; font-size: .8rem; font-weight: 500;
        padding: 5px 11px; border-radius: 7px; min-height: 30px;
      }
      .cb-seg button.on { background: #fff; color: var(--cb-accent); opacity: 1; }
      :host([data-tm-design="accessible"]) .cb-seg button.on { color: #111; outline: 2px solid #111; }
      .cb-body { padding: 10px 16px 14px; }
      /* Room for the toast, so it never sits over the last row. */
      .cb-body.cb-has-toast { padding-bottom: 66px; }
      .cb-empty { text-align: center; padding: 28px 12px; color: var(--tmd-dim, var(--secondary-text-color)); }

      .cb-wrap { overflow-x: auto; margin: 0 -4px; padding: 0 4px; }
      .cb-board {
        display: grid; grid-template-columns: 110px repeat(var(--cb-cols), minmax(140px, 1fr));
        font-size: 13px;
      }
      .cb-board > div {
        padding: 8px 10px; min-width: 0;
        border-bottom: 1px solid var(--tmd-border, var(--divider-color, rgba(127, 127, 127, .2)));
      }
      .cb-sticky {
        position: sticky; inset-inline-start: 0; z-index: 1;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
      }
      .cb-kid { display: flex; align-items: center; gap: 7px; font-weight: 600; font-size: 12.5px; }
      .cb-kid span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .cb-kid small {
        margin-inline-start: auto; font-weight: 500; font-variant-numeric: tabular-nums;
        color: var(--tmd-dim, var(--secondary-text-color));
      }
      .cb-slot { display: flex; align-items: center; gap: 6px; font-size: 12.5px; color: var(--tmd-dim, var(--secondary-text-color)); }
      .cb-slot ha-icon { --mdc-icon-size: 16px; flex: none; }
      .cb-cell { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; }
      .cb-none { color: var(--tmd-dim, var(--secondary-text-color)); opacity: .5; }

      .cb-av {
        width: 24px; height: 24px; flex: none; border-radius: 50%; overflow: hidden;
        display: inline-grid; place-items: center;
        background: var(--cb-kc, #9b59b6); color: #fff;
        font-size: 11px; font-weight: 700;
      }
      .cb-av ha-icon { --mdc-icon-size: 16px; }
      .cb-av img { width: 100%; height: 100%; object-fit: cover; }

      .cb-chip {
        display: inline-flex; align-items: center; gap: 7px; max-width: 100%;
        background: none; border: 0; padding: 4px 5px; margin-inline-start: -5px;
        border-radius: 6px; min-height: 28px;
        font: inherit; font-size: 12.5px; color: inherit; text-align: start;
      }
      button.cb-chip { cursor: pointer; }
      button.cb-chip:hover { background: var(--tmd-surface-2, rgba(127, 127, 127, .12)); }
      button.cb-chip[disabled] { opacity: .6; cursor: default; }
      .cb-n { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .cb-n small { color: var(--tmd-dim, var(--secondary-text-color)); }
      .cb-x { --mdc-icon-size: 14px; flex: none; color: var(--tmd-dim, var(--secondary-text-color)); }
      .cb-dot {
        width: 14px; height: 14px; flex: none; border-radius: 50%; box-sizing: border-box;
        border: 2px solid var(--tmd-dim, var(--secondary-text-color));
      }
      .cb-chip.done .cb-dot { background: var(--tmd-good, #2ecc71); border-color: var(--tmd-good, #2ecc71); }
      .cb-chip.done .cb-n { color: var(--tmd-dim, var(--secondary-text-color)); text-decoration: line-through; }
      .cb-chip.pending .cb-dot {
        border-color: var(--tmd-warn, #f39c12);
        background: color-mix(in srgb, var(--tmd-warn, #f39c12) 30%, transparent);
      }
      .cb-chip.missed .cb-dot { border-color: var(--tmd-bad, #e74c3c); }
      .cb-chip.missed .cb-n { color: var(--tmd-bad, #e74c3c); }
      .cb-sr {
        position: absolute; width: 1px; height: 1px; overflow: hidden;
        clip: rect(0 0 0 0); white-space: nowrap;
      }
      .cb-legend {
        display: flex; flex-wrap: wrap; gap: 4px 14px; margin-top: 10px;
        font-size: 12px; color: var(--tmd-dim, var(--secondary-text-color));
      }
      .cb-legend .cb-chip { padding: 0; margin: 0; min-height: 0; font-size: 12px; }
      .cb-legend .cb-chip .cb-n { color: inherit; text-decoration: none; }

      .cb-list { display: flex; flex-direction: column; align-items: stretch; }
      .cb-list .cb-chip { font-size: 14px; min-height: 36px; margin-inline-start: 0; }
      .cb-prog-row { display: flex; align-items: center; gap: 8px; font-weight: 600; }
      .cb-prog-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .cb-prog-n { font-variant-numeric: tabular-nums; color: var(--tmd-dim, var(--secondary-text-color)); }
      .cb-prog {
        height: 6px; border-radius: 3px; overflow: hidden; margin: 8px 0 4px;
        background: var(--tmd-surface-2, var(--divider-color, rgba(127, 127, 127, .2)));
      }
      .cb-prog > i { display: block; height: 100%; }
      .cb-grp {
        display: flex; align-items: center; gap: 6px; margin: 10px 0 2px;
        font-size: 12px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase;
        color: var(--tmd-dim, var(--secondary-text-color));
      }
      .cb-grp ha-icon { --mdc-icon-size: 15px; }

      .cb-week {
        display: grid; grid-template-columns: 100px repeat(var(--cb-days), minmax(38px, 1fr));
        gap: 6px; align-items: center; font-size: 12px;
      }
      .cb-wh { text-align: center; font-weight: 500; color: var(--tmd-dim, var(--secondary-text-color)); }
      .cb-wh.today { color: var(--tmd-text, var(--primary-text-color)); font-weight: 600; }
      .cb-wk { display: flex; align-items: center; gap: 6px; min-width: 0; font-size: 13px; }
      .cb-wk span:last-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .cb-wc {
        height: 32px; border-radius: 7px;
        display: grid; place-items: center;
        font-weight: 600; font-variant-numeric: tabular-nums;
        background: color-mix(in srgb, var(--cb-kc) calc(15% + var(--cb-p) * .7%), var(--tmd-surface-2, rgba(127, 127, 127, .12)));
      }
      .cb-wc.none {
        background: var(--tmd-surface-2, rgba(127, 127, 127, .12));
        color: var(--tmd-dim, var(--secondary-text-color)); font-weight: 400;
      }
      .cb-hint { margin: 10px 0 0; font-size: 12px; color: var(--tmd-dim, var(--secondary-text-color)); }

      .cb-toast {
        position: absolute; inset-inline: 12px; bottom: 12px; z-index: 3;
        display: flex; align-items: center; gap: 12px;
        padding-block: 8px; padding-inline: 14px 8px; border-radius: 8px;
        background: #323232; color: #fff; font-size: 13px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, .4);
      }
      .cb-toast span { flex: 1; min-width: 0; }
      .cb-toast button {
        flex: none; background: none; border: 0; cursor: pointer;
        color: var(--primary-color, #03a9f4); font: inherit; font-weight: 600;
        padding: 6px 10px; min-height: 32px;
      }
      :host([data-tm-design="accessible"]) .cb-toast button { color: #ffd54f; text-decoration: underline; }
    `;
    // The token block is :host-scoped, so it only takes effect when included
    // in THIS card's styles — a document-level rule cannot cross into the
    // shadow root.
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

class TaskMateChoreBoardCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  setConfig(config) { this.config = config; }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _buildSchema() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const children = attrs.children || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      { name: "title", selector: { text: {} } },
      {
        name: "children",
        selector: { select: { multiple: true, mode: "list", options: children.map(c => ({ value: c.id, label: c.name })) } },
      },
      {
        name: "default_view",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "today", label: this._t("chore_board.today") },
              { value: "week", label: this._t("chore_board.this_week") },
            ],
          },
        },
      },
      { name: "show_week", selector: { boolean: {} } },
      { name: "tap_to_complete", selector: { boolean: {} } },
      { name: "show_legend", selector: { boolean: {} } },
      { name: "hide_done_periods", selector: { boolean: {} } },
      { name: "show_parent_actions", selector: { boolean: {} } },
      {
        name: "card_design",
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: "global", label: "Use global default" }],
            mode: "dropdown",
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => ({
    entity: this._t("common.editor.overview_entity"),
    title: this._t("common.editor.card_title"),
    children: this._t("chore_board.editor.children"),
    default_view: this._t("chore_board.editor.default_view"),
    show_week: this._t("chore_board.editor.show_week"),
    tap_to_complete: this._t("chore_board.editor.tap_to_complete"),
    show_legend: this._t("chore_board.editor.show_legend"),
    hide_done_periods: this._t("chore_board.editor.hide_done_periods"),
    show_parent_actions: this._t("common.editor.show_parent_actions"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  _computeHelper = (entry) => ({
    entity: this._t("common.editor.overview_entity_helper"),
    children: this._t("chore_board.editor.children_helper"),
    tap_to_complete: this._t("chore_board.editor.tap_to_complete_helper"),
    hide_done_periods: this._t("chore_board.editor.hide_done_periods_helper"),
    show_parent_actions: this._t("common.editor.show_parent_actions_helper"),
  }[entry.name] ?? "");

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      title: this.config.title || "",
      children: Array.isArray(this.config.children) ? this.config.children : [],
      default_view: this.config.default_view || "today",
      show_week: this.config.show_week !== false,
      tap_to_complete: this.config.tap_to_complete !== false,
      show_legend: this.config.show_legend !== false,
      hide_done_periods: this.config.hide_done_periods === true,
      show_parent_actions: this.config.show_parent_actions !== false,
      card_design: this.config.card_design || "global",
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
      ${this._renderColourPicker("header_color", DEFAULT_ACCENT)}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    const current = this.config[key] || defaultValue;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current,
      label: this._t("common.editor.header_colour"),
      helper: this._t("common.editor.header_colour_helper"),
      resetLabel: this._t("common.reset"),
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
    });
  }

  // Defaults are the absence of a key, so a saved card only carries what was
  // changed from them.
  static _isDefault(key, value) {
    if (value === "" || value === null || value === undefined) return true;
    if (key === "card_design") return value === "global";
    if (key === "default_view") return value === "today";
    if (key === "children") return Array.isArray(value) && value.length === 0;
    if (["show_week", "tap_to_complete", "show_legend", "show_parent_actions"].includes(key)) return value === true;
    if (key === "hide_done_periods") return value === false;
    return false;
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (TaskMateChoreBoardCardEditor._isDefault(key, value)) delete newConfig[key];
      else newConfig[key] = value;
    }
    this._fire(newConfig);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this._fire(newConfig);
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
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
      .colour-reset { font-size: 0.78rem; color: var(--secondary-text-color); background: none; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; padding: 4px 10px; cursor: pointer; margin-inline-start: auto; }
      .colour-helper { color: var(--secondary-text-color); font-size: 0.82rem; line-height: 1.3; }
    `;
  }
}

customElements.define("taskmate-chore-board-card", TaskMateChoreBoardCard);
customElements.define("taskmate-chore-board-card-editor", TaskMateChoreBoardCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-chore-board-card",
  name: "TaskMate Chore Board",
  description: "Every child's chores for today by time of day — tap one to complete it",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-chore-board-card", "overview"),
});
