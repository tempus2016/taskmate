/**
 * TaskMate Raffle Card
 *
 * Children spend points on raffle tickets — one ticket, one chance — and at the
 * draw time one winner is picked for the prize. With a child_id the card is
 * that child's: buy tickets, see your chance. Without one it is the family
 * view (a wall tablet): everyone's tickets, no buying.
 *
 * When a raffle is drawn while the card is on screen (or within the last ten
 * minutes, the first time this browser sees it) the names spin and land on
 * the winner. Each draw is revealed once per browser.
 *
 * Reads the `raffles` attribute the rewards sensor publishes, through the
 * attribute resolver. Single layout consuming the design tokens directly,
 * like the bounty card; layout classes carry an rf- prefix.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const _ltrNums = (s) => (window.__taskmate_design && window.__taskmate_design.ltrNums ? window.__taskmate_design.ltrNums(s) : s);
const DEFAULT_ACCENT = "#8e44ad";
const REWARDS_ENTITY = "sensor.taskmate_rewards";
const CHILD_COLOURS = ["#ff6b9d", "#3498db", "#1abc9c", "#e67e22", "#9b59b6", "#2ecc71"];
const REVEAL_WINDOW_MS = 10 * 60 * 1000;
const SEEN_KEY = "taskmate_raffle_seen";

class TaskMateRaffleCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _qty: { type: Object },
      _busy: { type: Boolean },
      _error: { type: String },
      _reveal: { type: Object },
    };
  }

  constructor() {
    super();
    this._qty = {};
    this._busy = false;
    this._error = "";
    this._reveal = null;
    this._tick = null;
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("You need to define an entity");
    this.config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  static getConfigElement() {
    return document.createElement("taskmate-raffle-card-editor");
  }

  getCardSize() {
    return 5;
  }

  connectedCallback() {
    super.connectedCallback();
    // The countdown ticks client-side; once a minute is plenty for "2d 4h".
    this._tick = setInterval(() => this.requestUpdate(), 30000);
    // HA's masonry layout detaches and re-attaches cards while it lays a view
    // out, which cancelled the spin's timer mid-reveal: pick it back up.
    if (this._reveal && !this._reveal.done) {
      clearTimeout(this._revealTimer);
      this._revealTimer = setTimeout(() => this._spin(), 60);
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this._tick);
    this._tick = null;
    clearTimeout(this._revealTimer);
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass") && changedProps.size === 1) {
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
    }
    return true;
  }

  updated() {
    this._maybeReveal();
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
  }

  _raffles() {
    const list = this._attrs().raffles || this.hass?.states?.[REWARDS_ENTITY]?.attributes?.raffles;
    return Array.isArray(list) ? list : [];
  }

  _children() {
    return this._attrs().children || [];
  }

  _child() {
    const id = this.config.child_id;
    return id ? this._children().find(c => String(c.id) === String(id)) : null;
  }

  _childName(id) {
    const c = this._children().find(ch => String(ch.id) === String(id));
    return c ? c.name : "?";
  }

  _pointsIcon() {
    return this._attrs().points_icon || "mdi:star";
  }

  _applyDesign() {
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--rf-accent", _safeColor(configured, DEFAULT_ACCENT));
    } else {
      this.style.removeProperty("--rf-accent");
    }
    return design;
  }

  _avatar(childId, size = 26) {
    const children = this._children();
    const idx = Math.max(0, children.findIndex(c => String(c.id) === String(childId)));
    const name = this._childName(childId);
    const colour = `var(--tmd-c${(idx % 6) + 1}, ${CHILD_COLOURS[idx % CHILD_COLOURS.length]})`;
    const child = children.find(c => String(c.id) === String(childId));
    const face = child && window.__taskmate_child_visual ? window.__taskmate_child_visual(child) : null;
    const inner = face && face.kind === "image" ? html`<img src="${face.url}" alt="">` : name.charAt(0).toUpperCase();
    return html`<span class="rf-av" style="--rf-ac:${colour};--rf-s:${size}px" title="${name}">${inner}</span>`;
  }

  _until(iso) {
    const ms = Date.parse(iso || "") - Date.now();
    if (!Number.isFinite(ms)) return "";
    if (ms <= 0) return this._t("raffle.drawing_now");
    const min = Math.round(ms / 60000);
    const d = Math.floor(min / 1440);
    const h = Math.floor((min % 1440) / 60);
    const m = min % 60;
    if (d) return this._t("raffle.draw_in_days", { d, h });
    if (h) return this._t("raffle.draw_in_hours", { h, m });
    return this._t("raffle.draw_in_minutes", { m: Math.max(1, m) });
  }

  // ── buying ──────────────────────────────────────────────────────────────

  _qtyFor(r) {
    return Math.max(1, Number(this._qty[r.id]) || 1);
  }

  _maxBuy(r, child) {
    const held = Number((r.tickets || {})[child.id] || 0);
    const byCap = r.max ? Math.max(0, r.max - held) : 100;
    const balance = Number(child.spendable_balance ?? child.points) || 0;
    const byPoints = r.cost ? Math.floor(balance / r.cost) : 0;
    return Math.max(0, Math.min(byCap, byPoints, 100));
  }

  _setQty(r, n, child) {
    const max = Math.max(1, this._maxBuy(r, child));
    this._qty = { ...this._qty, [r.id]: Math.max(1, Math.min(max, n)) };
  }

  async _buy(r, child) {
    if (this._busy) return;
    const tickets = Math.min(this._qtyFor(r), this._maxBuy(r, child));
    if (tickets < 1) return;
    this._busy = true;
    this._error = "";
    try {
      await this.hass.callService("taskmate", "buy_raffle_tickets", { raffle_id: r.id, child_id: child.id, tickets });
      this._qty = { ...this._qty, [r.id]: 1 };
    } catch (err) {
      this._error = String(err?.message || err);
    } finally {
      this._busy = false;
    }
  }

  // ── the reveal ──────────────────────────────────────────────────────────

  _seen() {
    try { return JSON.parse(localStorage.getItem(SEEN_KEY) || "[]"); } catch (_e) { return []; }
  }

  _markSeen(id) {
    const seen = [...new Set([...this._seen(), id])].slice(-40);
    try { localStorage.setItem(SEEN_KEY, JSON.stringify(seen)); } catch (_e) { /* private mode */ }
  }

  _maybeReveal() {
    if (this._reveal || this.config.show_reveal === false) return;
    const seen = this._seen();
    const r = this._raffles().find(x => x.status === "drawn" && x.winner_id && !seen.includes(x.id)
      && Date.now() - Date.parse(x.drawn_at || "") < REVEAL_WINDOW_MS);
    if (!r) return;
    this._markSeen(r.id);
    // One name per ticket, so the spin shows the odds; capped so a big draw stays short.
    const pool = [];
    for (const [cid, n] of Object.entries(r.tickets || {})) {
      for (let i = 0; i < Math.min(n, 12); i++) pool.push(cid);
    }
    this._reveal = { raffle: r, pool: pool.length ? pool : [r.winner_id], shown: pool[0] || r.winner_id, done: false, step: 0 };
    this._spin();
  }

  _spin() {
    const rv = this._reveal;
    if (!rv) return;
    const steps = 26;
    if (rv.step >= steps) {
      this._reveal = { ...rv, shown: rv.raffle.winner_id, done: true };
      return;
    }
    const next = rv.step === steps - 1 ? rv.raffle.winner_id : rv.pool[(rv.step * 7 + 3) % rv.pool.length];
    this._reveal = { ...rv, shown: next, step: rv.step + 1 };
    // Slows down towards the end, like a wheel.
    this._revealTimer = setTimeout(() => this._spin(), 60 + rv.step * rv.step * 0.7);
  }

  _renderReveal() {
    const rv = this._reveal;
    if (!rv) return "";
    const close = () => { this._reveal = null; };
    const mine = this.config.child_id && String(rv.raffle.winner_id) === String(this.config.child_id);
    return html`
      <div class="rf-scrim" @click=${e => { if (e.target === e.currentTarget && rv.done) close(); }}>
        <div class="rf-reveal ${rv.done ? "done" : ""}" role="dialog" aria-modal="true" aria-live="polite">
          <div class="rf-rv-title">🎟️ ${rv.raffle.name}</div>
          <div class="rf-rv-prize">${rv.raffle.prize}</div>
          <div class="rf-rv-wheel">
            ${this._avatar(rv.shown, 64)}
            <div class="rf-rv-name">${this._childName(rv.shown)}</div>
          </div>
          ${rv.done ? html`
            <div class="rf-rv-win">${mine ? this._t("raffle.you_won") : this._t("raffle.winner_is", { name: this._childName(rv.raffle.winner_id) })}</div>
            <button class="rf-btn" @click=${close}>${this._t("raffle.ok")}</button>` : html`<div class="rf-rv-drum">${this._t("raffle.drawing")}</div>`}
        </div>
      </div>`;
  }

  // ── render ──────────────────────────────────────────────────────────────

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const title = this.config.title || this._t("raffle.title");
    const child = this._child();
    if (this.config.child_id && !child) {
      return html`<ha-card>${this._header(title, null)}<div class="rf-empty">${this._t("raffle.no_child")}</div></ha-card>`;
    }
    const raffles = this._raffles().filter(r => !child || !(r.assigned_to || []).length || r.assigned_to.includes(child.id));
    const open = raffles.filter(r => r.status === "open");
    const done = raffles.filter(r => r.status !== "open");
    return html`
      <ha-card>
        ${this._header(title, open.length)}
        <div class="rf-content">
          ${open.length ? open.map(r => this._row(r, child)) : html`<div class="rf-empty">${this._t("raffle.empty")}</div>`}
          ${done.length ? html`<div class="rf-sec">${this._t("raffle.recent")}</div>${done.map(r => this._row(r, child))}` : ""}
          ${this._error ? html`<div class="rf-err" role="alert">${this._error}</div>` : ""}
        </div>
        ${this._renderReveal()}
      </ha-card>`;
  }

  _header(title, openCount) {
    return html`
      <div class="rf-hd">
        <ha-icon class="rf-hd-icon" icon="mdi:ticket-confirmation-outline"></ha-icon>
        <div class="rf-hd-text">
          <div class="rf-hd-title">${title}</div>
          <div class="rf-hd-sub">${this._t("raffle.subtitle")}</div>
        </div>
        ${openCount ? html`<span class="rf-hd-pill">${this._t("raffle.open_count", { count: openCount })}</span>` : ""}
      </div>`;
  }

  _row(r, child) {
    const tickets = r.tickets || {};
    const total = Number(r.total) || 0;
    const mine = child ? Number(tickets[child.id] || 0) : 0;
    const holders = Object.entries(tickets).sort((a, b) => b[1] - a[1]);
    const chance = child && total ? Math.round((mine / total) * 100) : 0;
    const isOpen = r.status === "open";
    return html`
      <div class="rf-row ${isOpen ? "" : "closed"} ${r.winner_id && child && String(r.winner_id) === String(child.id) ? "won" : ""}">
        <div class="rf-ic"><ha-icon icon="${r.icon || "mdi:ticket-confirmation"}"></ha-icon></div>
        <div class="rf-body">
          <div class="rf-name">${r.name}</div>
          ${r.prize ? html`<div class="rf-prize">🏆 ${r.prize}</div>` : ""}
          <div class="rf-meta">
            <span class="rf-chip"><ha-icon icon="${this._pointsIcon()}"></ha-icon>${this._t("raffle.per_ticket", { cost: r.cost })}</span>
            ${isOpen ? html`<span class="rf-chip">⏳ ${this._until(r.draw_at)}</span>` : ""}
            ${r.max ? html`<span class="rf-chip">${this._t("raffle.max_each", { max: r.max })}</span>` : ""}
          </div>
          ${holders.length ? html`
            <div class="rf-holders" aria-label="${this._t("raffle.tickets_total", { count: total })}">
              ${holders.map(([cid, n]) => html`<span class="rf-holder">${this._avatar(cid, 22)}<b>${n}</b></span>`)}
              <span class="rf-total">${this._t("raffle.tickets_total", { count: total })}</span>
            </div>` : html`<div class="rf-none">${isOpen ? this._t("raffle.no_tickets_yet") : this._t("raffle.nobody_entered")}</div>`}
          ${!isOpen && r.status === "drawn" && r.winner_id ? html`
            <div class="rf-winner">${this._avatar(r.winner_id, 22)} ${this._t("raffle.winner_is", { name: this._childName(r.winner_id) })}</div>` : ""}
          ${r.status === "cancelled" ? html`<div class="rf-none">${this._t("raffle.called_off")}</div>` : ""}
          ${isOpen && child ? this._buyRow(r, child, mine, chance) : ""}
        </div>
      </div>`;
  }

  _buyRow(r, child, mine, chance) {
    const max = this._maxBuy(r, child);
    const n = Math.min(this._qtyFor(r), Math.max(1, max));
    const closing = Date.parse(r.draw_at || "") <= Date.now();
    return html`
      <div class="rf-mine">
        ${mine ? _ltrNums(this._t("raffle.your_tickets", { count: mine, chance })) : this._t("raffle.no_tickets_mine")}
      </div>
      <div class="rf-buy">
        <button class="rf-step" aria-label="−" ?disabled=${n <= 1 || this._busy} @click=${() => this._setQty(r, n - 1, child)}>−</button>
        <span class="rf-n">${n}</span>
        <button class="rf-step" aria-label="+" ?disabled=${n >= max || this._busy} @click=${() => this._setQty(r, n + 1, child)}>+</button>
        <button class="rf-btn" ?disabled=${max < 1 || this._busy || closing} @click=${() => this._buy(r, child)}>
          ${max < 1 ? (r.max && mine >= r.max ? this._t("raffle.cap_reached") : this._t("raffle.not_enough")) : this._t("raffle.buy", { count: n, cost: n * r.cost })}
        </button>
      </div>`;
  }

  static get styles() {
    const base = css`
      :host { display: block; --rf-accent: var(--tmd-accent, #8e44ad); }
      ha-card {
        position: relative; overflow: hidden;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px));
        font-family: var(--tmd-font-body, inherit);
      }
      .rf-hd { display: flex; align-items: center; gap: 12px; padding: 14px 18px; background: var(--rf-accent); color: var(--tmd-hd-text, #fff); }
      :host([data-tm-design="playroom"]) .rf-hd { background: linear-gradient(135deg, var(--rf-accent), color-mix(in srgb, var(--rf-accent) 72%, #fff)); }
      .rf-hd-icon { --mdc-icon-size: 30px; flex: none; }
      .rf-hd-text { flex: 1; min-width: 0; }
      .rf-hd-title { font-family: var(--tmd-font-display, inherit); font-size: 1.3rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .rf-hd-sub { font-size: .8rem; opacity: .85; }
      .rf-hd-pill { flex: none; background: rgba(255,255,255,.2); padding: 4px 12px; border-radius: 16px; font-size: .9rem; white-space: nowrap; }
      .rf-content { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
      .rf-empty { text-align: center; padding: 26px 12px; color: var(--tmd-dim, var(--secondary-text-color)); }
      .rf-sec { font-size: .8rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--tmd-dim, var(--secondary-text-color)); margin: 4px 2px -4px; }
      .rf-row { display: flex; gap: 14px; padding: 14px; border: 1px solid var(--tmd-border, var(--divider-color, #e0e0e0)); border-radius: var(--tmd-radius-sm, 14px);
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff))); }
      .rf-row.closed { opacity: .8; }
      .rf-row.won { border: 2px solid #f5b301; background: color-mix(in srgb, #f5b301 10%, transparent); opacity: 1; }
      .rf-ic { width: 46px; height: 46px; flex: none; border-radius: 14px; display: grid; place-items: center; background: color-mix(in srgb, var(--rf-accent) 16%, transparent); color: var(--rf-accent); }
      .rf-ic ha-icon { --mdc-icon-size: 28px; }
      .rf-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
      .rf-name { font-weight: 700; font-size: 1.05rem; }
      .rf-prize { font-weight: 600; color: var(--tmd-text, var(--primary-text-color)); }
      .rf-meta { display: flex; gap: 6px; flex-wrap: wrap; }
      .rf-chip { display: inline-flex; align-items: center; gap: 4px; font-size: .78rem; padding: 2px 8px; border-radius: 999px;
        background: var(--tmd-surface-2, rgba(127,127,127,.12)); color: var(--tmd-dim, var(--secondary-text-color)); }
      .rf-chip ha-icon { --mdc-icon-size: 14px; color: #f5b301; }
      .rf-holders { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
      .rf-holder { display: inline-flex; align-items: center; gap: 4px; font-size: .85rem; }
      .rf-total { font-size: .8rem; color: var(--tmd-dim, var(--secondary-text-color)); margin-inline-start: auto; }
      .rf-none { font-size: .85rem; color: var(--tmd-dim, var(--secondary-text-color)); }
      .rf-winner { display: flex; align-items: center; gap: 6px; font-weight: 700; }
      .rf-mine { font-size: .85rem; font-weight: 600; }
      .rf-buy { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
      .rf-step { width: 34px; height: 34px; border-radius: 50%; border: 0; font-size: 1.2rem; font-weight: 800; cursor: pointer;
        background: var(--tmd-surface-2, rgba(127,127,127,.14)); color: var(--tmd-text, var(--primary-text-color)); }
      .rf-step:disabled { opacity: .35; cursor: default; }
      .rf-n { min-width: 2ch; text-align: center; font-weight: 800; font-size: 1.1rem; }
      .rf-btn { border: 0; border-radius: var(--tmd-radius-sm, 999px); padding: 8px 14px; font: inherit; font-weight: 700; cursor: pointer;
        background: var(--rf-accent); color: #fff; }
      .rf-btn:disabled { opacity: .45; cursor: default; }
      .rf-av { width: var(--rf-s); height: var(--rf-s); border-radius: 50%; display: inline-grid; place-items: center; overflow: hidden; flex: none;
        background: var(--rf-ac); color: #fff; font-weight: 800; font-size: calc(var(--rf-s) * .45); }
      .rf-av img { width: 100%; height: 100%; object-fit: cover; }
      .rf-err { color: var(--tmd-bad, var(--error-color, #c62828)); font-size: .85rem; }
      .rf-scrim { position: fixed; inset: 0; z-index: 9; background: rgba(20,14,40,.72); display: grid; place-items: center; }
      .rf-reveal { width: min(360px, 88vw); padding: 22px; border-radius: 22px; text-align: center; display: flex; flex-direction: column; gap: 10px; align-items: center;
        background: var(--tmd-surface, var(--card-background-color, #fff)); color: var(--tmd-text, var(--primary-text-color)); box-shadow: 0 12px 40px rgba(0,0,0,.4); }
      .rf-rv-title { font-weight: 800; font-size: 1.2rem; }
      .rf-rv-prize { color: var(--tmd-dim, var(--secondary-text-color)); }
      .rf-rv-wheel { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 14px 24px; border-radius: 18px;
        background: color-mix(in srgb, var(--rf-accent) 12%, transparent); min-width: 160px; }
      .rf-rv-name { font-size: 1.5rem; font-weight: 800; }
      .rf-reveal.done .rf-rv-wheel { background: color-mix(in srgb, #f5b301 22%, transparent); animation: rf-pop .5s ease-out; }
      .rf-rv-win { font-size: 1.15rem; font-weight: 800; }
      .rf-rv-drum { font-size: .9rem; color: var(--tmd-dim, var(--secondary-text-color)); }
      @keyframes rf-pop { 0% { transform: scale(.85); } 70% { transform: scale(1.08); } 100% { transform: scale(1); } }
      @media (prefers-reduced-motion: reduce) { .rf-reveal.done .rf-rv-wheel { animation: none; } }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

class TaskMateRaffleCardEditor extends LitElement {
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
      {
        name: "child_id",
        selector: {
          select: {
            options: [{ value: "", label: this._t("raffle.editor.family_view") }, ...children.map(c => ({ value: c.id, label: c.name }))],
            mode: "dropdown",
          },
        },
      },
      { name: "title", selector: { text: {} } },
      { name: "show_reveal", selector: { boolean: {} } },
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
    child_id: this._t("raffle.editor.child"),
    title: this._t("common.editor.card_title"),
    show_reveal: this._t("raffle.editor.show_reveal"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  _computeHelper = (entry) => ({
    entity: this._t("common.editor.overview_entity_helper"),
    child_id: this._t("raffle.editor.child_helper"),
  }[entry.name] ?? "");

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
      show_reveal: this.config.show_reveal !== false,
      card_design: this.config.card_design || "global",
    };
    return html`
      <ha-form .hass=${this.hass} .data=${data} .schema=${this._buildSchema()}
        .computeLabel=${this._computeLabel} .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}></ha-form>
      ${this._renderColourPicker("header_color", DEFAULT_ACCENT)}`;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current: this.config[key] || defaultValue,
      label: this._t("common.editor.header_colour"),
      helper: this._t("common.editor.header_colour_helper"),
      resetLabel: this._t("common.reset"),
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === "" || value === null || value === undefined || (key === "card_design" && value === "global")
        || (key === "show_reveal" && value === true)) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this._fire(newConfig);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this._fire(newConfig);
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  static get styles() {
    return css`:host { display: block; } ha-form { display: block; margin-bottom: 16px; }`;
  }
}

customElements.define("taskmate-raffle-card", TaskMateRaffleCard);
customElements.define("taskmate-raffle-card-editor", TaskMateRaffleCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-raffle-card",
  name: "TaskMate Raffles",
  description: "Children buy raffle tickets with points; one is drawn for a prize",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest ? window.__taskmate_suggest(hass, entityId, "taskmate-raffle-card", "overview") : undefined,
});
