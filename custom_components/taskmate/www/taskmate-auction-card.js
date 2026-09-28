/**
 * TaskMate Chore Auction Card (#982)
 *
 * A reverse auction on one occurrence of an unpopular chore: the child this
 * card belongs to bids the fewest points they would do it for, lowest bid
 * wins, and the winner gets that occurrence at their price. Bids are sealed —
 * the card shows how many bids are in, the child's own bid, and after closing
 * the winner and the winning price. Never anyone else's amount.
 *
 * The auctions are fetched over the `taskmate/auctions/list` WebSocket
 * command, which applies the linked-child rule and only ever returns this
 * child's own bid. `sensor.taskmate_auctions` carries a public digest (bid
 * counts, results); the card re-fetches whenever that digest moves.
 *
 * Single layout, so it consumes the design tokens directly (like the bounty
 * card) rather than carrying a second _renderDesigned() template. Every
 * --tmd-* reference has the card's original value as its fallback, so classic
 * — which defines no tokens — keeps the wireframe look. Layout classes carry
 * an ac- prefix: the shared design kit defines its own .btn / .bar / .chip.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const DEFAULT_ACCENT = "#5e35b1";
const AUCTIONS_ENTITY = "sensor.taskmate_auctions";
// Child avatar colours by position; a design's own palette wins when it has one.
const CHILD_COLOURS = ["#ff6b9d", "#3498db", "#1abc9c", "#e67e22", "#9b59b6", "#2ecc71"];

class TaskMateAuctionCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _auctions: { type: Array },
      _error: { type: String },
      _sheet: { type: Object },
      _busy: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._auctions = null;
    this._error = "";
    this._sheet = null;
    this._busy = false;
    this._tick = null;
    this._fetchedKey = null;
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("You need to define an entity");
    if (!config.child_id) throw new Error("You need to define a child_id");
    this.config = config;
    this._fetchedKey = null;
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", child_id: "" };
  }

  static getConfigElement() {
    return document.createElement("taskmate-auction-card-editor");
  }

  getCardSize() {
    return 6;
  }

  connectedCallback() {
    super.connectedCallback();
    // Countdowns tick client-side from the server's closing times; re-render
    // once a second only while an auction is actually open.
    this._tick = setInterval(() => {
      if ((this._auctions || []).some(a => a.status === "open")) this.requestUpdate();
    }, 1000);
    this._fetchedKey = null;
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this._tick);
    this._tick = null;
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
    // Re-fetch whenever the public digest moves (a bid came in, one closed).
    const key = this._digestKey();
    if (this.hass && key !== this._fetchedKey) {
      this._fetchedKey = key;
      this._fetch();
    }
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
  }

  _digestKey() {
    const digest = this._attrs().auctions || this.hass?.states?.[AUCTIONS_ENTITY]?.attributes?.auctions || [];
    return `${this.config?.child_id}|${JSON.stringify(digest)}`;
  }

  _children() {
    return this._attrs().children || [];
  }

  _child() {
    return this._children().find(c => String(c.id) === String(this.config.child_id));
  }

  _childName(id) {
    const c = this._children().find(ch => String(ch.id) === String(id));
    return c ? c.name : "?";
  }

  _lang() {
    return this.hass?.locale?.language || this.hass?.language || undefined;
  }

  /** "Saturday 4 October" (long) or "Sat 4 Oct" for an ISO date. */
  _date(iso, long = true) {
    const d = new Date(`${iso}T00:00:00`);
    if (Number.isNaN(d.getTime())) return iso || "";
    return d.toLocaleDateString(this._lang(), long
      ? { weekday: "long", day: "numeric", month: "long" }
      : { weekday: "short", day: "numeric", month: "short" });
  }

  _when(isoInstant) {
    const d = new Date(isoInstant || "");
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleString(this._lang(), { weekday: "short", hour: "2-digit", minute: "2-digit" });
  }

  _fmtDur(ms) {
    const sec = Math.max(0, Math.round(ms / 1000));
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (d) return this._t("bounty.dur_days", { d, h });
    if (h) return this._t("bounty.dur_hours", { h, m: String(m).padStart(2, "0") });
    return this._t("bounty.dur_minutes", { m, s: String(s).padStart(2, "0") });
  }

  _left(a) {
    const t = Date.parse(a.closes_at || "");
    return Number.isFinite(t) ? t - Date.now() : 0;
  }

  _avatar(childId, size = 30) {
    const children = this._children();
    const idx = Math.max(0, children.findIndex(c => String(c.id) === String(childId)));
    const name = this._childName(childId);
    const colour = `var(--tmd-c${(idx % 6) + 1}, ${CHILD_COLOURS[idx % CHILD_COLOURS.length]})`;
    return html`<span class="ac-av" style="--ac-ac:${colour};--ac-s:${size}px" title="${name}">${name.charAt(0).toUpperCase()}</span>`;
  }

  /**
   * Resolve the design, stamp data-tm-design on the host (so the :host-scoped
   * token block applies inside this shadow root) and settle the header colour.
   * The colour is an inline host property: a <style> in the template is
   * ordered before adoptedStyleSheets and would lose to the :host default.
   */
  _applyDesign() {
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--ac-accent", _safeColor(configured, DEFAULT_ACCENT));
    } else {
      this.style.removeProperty("--ac-accent");
    }
    return design;
  }

  // ── data ────────────────────────────────────────────────────────────────

  async _fetch() {
    const conn = this.hass?.connection;
    if (!conn || !this.config?.child_id) return;
    try {
      const res = await conn.sendMessagePromise({ type: "taskmate/auctions/list", child_id: this.config.child_id });
      this._auctions = Array.isArray(res?.auctions) ? res.auctions : [];
      this._error = "";
    } catch (err) {
      this._error = String(err?.message || err?.code || err);
    }
  }

  async _send(msg) {
    if (this._busy) return false;
    this._busy = true;
    try {
      await this.hass.connection.sendMessagePromise(msg);
      await this._fetch();
      return true;
    } catch (err) {
      this.dispatchEvent(new CustomEvent("hass-notification", {
        detail: { message: String(err?.message || err) }, bubbles: true, composed: true,
      }));
      return false;
    } finally {
      this._busy = false;
      this.requestUpdate();
    }
  }

  // ── bidding ─────────────────────────────────────────────────────────────

  _openSheet(a) {
    const start = a.my_bid ?? Math.round((a.min_points + a.max_points) / 2);
    this._sheet = { id: a.id, value: Math.max(a.min_points, Math.min(a.max_points, start)), fresh: true };
  }

  _setBid(value, a) {
    const v = Math.max(0, Math.min(a.max_points, Number(value) || 0));
    this._sheet = { ...this._sheet, value: v, fresh: false };
  }

  _key(k, a) {
    const cur = String(this._sheet.value || "");
    if (k === "c") return this._setBid(0, a);
    if (k === "bs") return this._setBid(Number(cur.slice(0, -1)) || 0, a);
    return this._setBid(Number(this._sheet.fresh ? k : cur + k), a);
  }

  async _seal(a) {
    const ok = await this._send({
      type: "taskmate/auctions/bid", auction_id: a.id, child_id: this.config.child_id, points: this._sheet.value,
    });
    if (ok) this._sheet = null;
  }

  async _withdraw(a) {
    await this._send({ type: "taskmate/auctions/withdraw", auction_id: a.id, child_id: this.config.child_id });
  }

  // ── render ──────────────────────────────────────────────────────────────

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const title = this.config.title || this._t("auction.title");
    const child = this._child();
    if (!child) {
      return html`<ha-card>${this._header(title, null)}<div class="ac-empty">${this._t("auction.no_child")}</div></ha-card>`;
    }
    const all = this._auctions || [];
    const open = all.filter(a => a.status === "open");
    const done = all.filter(a => a.status !== "open");
    const sheetAuction = this._sheet && open.find(a => a.id === this._sheet.id);
    return html`
      <ha-card class="${sheetAuction ? "ac-sheet-open" : ""}">
        ${this._header(title, this._auctions ? open.length : null)}
        <div class="ac-content">
          ${this._error ? html`<div class="ac-empty ac-err">${this._t("auction.load_failed", { error: this._error })}</div>` : ""}
          ${open.length
            ? open.map(a => this._lot(a))
            : (this._auctions && !this._error ? html`<div class="ac-empty">${this._t("auction.empty")}</div>` : "")}
          ${done.length ? html`
            <div class="ac-sec">${this._t("auction.results")}</div>
            ${done.map(a => this._lot(a))}
          ` : ""}
        </div>
        ${sheetAuction ? this._renderSheet(sheetAuction) : ""}
      </ha-card>
    `;
  }

  _header(title, openCount) {
    return html`
      <div class="ac-hd">
        <span class="ac-hd-gavel"><ha-icon icon="mdi:gavel"></ha-icon></span>
        <div class="ac-hd-text">
          <div class="ac-hd-title">${title}</div>
          <div class="ac-hd-sub">${this._t("auction.subtitle")}</div>
        </div>
        ${openCount !== null ? html`<span class="ac-hd-pill">${this._t("auction.open_count", { count: openCount })}</span>` : ""}
      </div>
    `;
  }

  _otherBids(a) {
    const others = Math.max(0, (a.bid_count || 0) - (a.my_bid != null ? 1 : 0));
    if (!others) return this._t("auction.no_other_bids");
    return others === 1 ? this._t("auction.other_bids_one") : this._t("auction.other_bids", { count: others });
  }

  _gauge(a) {
    return html`
      <div class="ac-gauge">
        <div class="ac-gauge-row">
          <span>${a.min_points} ★</span><span class="ac-caps">${this._t("auction.lowest_wins")}</span><span>${this._t("auction.gauge_max", { points: a.max_points })}</span>
        </div>
        <div class="ac-gauge-bar"></div>
        <div class="ac-gauge-hint">${this._t("auction.gauge_hint", { points: a.normal_points })}</div>
      </div>`;
  }

  _lot(a) {
    const me = String(this.config.child_id);
    const head = html`
      <div class="ac-lot-top">
        <span class="ac-lot-ic"><ha-icon icon="${a.icon || "mdi:clipboard-check-outline"}"></ha-icon></span>
        <div class="ac-grow">
          <div class="ac-lot-t">${a.chore_name}</div>
          <div class="ac-lot-when"><ha-icon icon="mdi:calendar-blank-outline"></ha-icon>${this._date(a.occurrence)}</div>
        </div>
        ${a.status === "open" ? html`<span class="ac-tag ac-tag-max">${this._t("auction.up_to", { points: a.max_points })}</span>` : ""}
      </div>`;

    if (a.status === "open") {
      const mine = a.my_bid != null;
      return html`
        <div class="ac-lot">
          ${head}
          ${mine ? html`
            <div class="ac-sealed">
              <span class="ac-env"><ha-icon icon="mdi:email-lock"></ha-icon></span>
              <div class="ac-grow"><small>${this._t("auction.your_bid")}</small><b>${a.my_bid} ★</b></div>
              <button class="ac-btn ac-ghost ac-sm" ?disabled=${this._busy} @click=${() => this._openSheet(a)}>${this._t("auction.change")}</button>
            </div>` : this._gauge(a)}
          <div class="ac-lot-foot">
            <span class="ac-cdown"><ha-icon icon="mdi:timer-sand"></ha-icon>${this._t("auction.closes_in", { time: this._fmtDur(this._left(a)) })}</span>
            <span class="ac-bidcount"><ha-icon icon="mdi:email-outline"></ha-icon>${this._otherBids(a)}</span>
            <span class="ac-grow"></span>
            ${mine
              ? html`<button class="ac-btn ac-text ac-sm" ?disabled=${this._busy} @click=${() => this._withdraw(a)}>${this._t("auction.withdraw")}</button>`
              : html`<button class="ac-btn ac-bid" ?disabled=${this._busy} @click=${() => this._openSheet(a)}><ha-icon icon="mdi:gavel"></ha-icon>${this._t("auction.place_bid")}</button>`}
          </div>
        </div>`;
    }

    const closed = html`<div class="ac-lot-foot"><span class="ac-faint">${this._t("auction.closed_at", { when: this._when(a.closed_at) })}</span></div>`;
    if (!a.winner_id) {
      return html`
        <div class="ac-lot ac-nobid">
          ${head}
          <div class="ac-result ac-nob">
            <span class="ac-ri"><ha-icon icon="mdi:email-outline"></ha-icon></span>
            <div>${this._t("auction.no_bids")}<small>${this._t("auction.no_bids_sub", { chore: a.chore_name, date: this._date(a.occurrence, false) })}</small></div>
          </div>
          ${closed}
        </div>`;
    }
    if (String(a.winner_id) === me) {
      return html`
        <div class="ac-lot ac-won">
          ${head}
          <div class="ac-result ac-win">
            <span class="ac-ri"><ha-icon icon="mdi:trophy"></ha-icon></span>
            <div>${this._t("auction.you_won", { points: a.price })}<small>${this._t("auction.you_won_sub", { date: this._date(a.occurrence, false) })}</small></div>
          </div>
          <div class="ac-won-chore">
            <ha-icon icon="${a.icon || "mdi:clipboard-check-outline"}"></ha-icon>
            <span class="ac-grow ac-won-nm">${a.chore_name}</span>
            <span class="ac-tag ac-tag-won"><ha-icon icon="mdi:gavel"></ha-icon>${this._t("child.won_at_auction")}</span>
            <span class="ac-pts"><ha-icon icon="mdi:star"></ha-icon>${a.price}</span>
          </div>
          <div class="ac-lot-foot"><span class="ac-faint">${this._t("auction.in_your_chores", { date: this._date(a.occurrence, false) })}</span></div>
        </div>`;
    }
    // Lowest bid wins and the earliest breaks a tie, so a losing bid equal to
    // the price lost on timing, not on the amount.
    const winner = this._childName(a.winner_id);
    const sub = a.my_bid == null ? this._t("auction.sibling_won_sub", { points: a.price })
      : Number(a.my_bid) === Number(a.price) ? this._t("auction.tied_sub", { points: a.price, name: winner })
      : this._t("auction.sibling_won_sub_bid", { points: a.price, bid: a.my_bid });
    return html`
      <div class="ac-lot ac-lost">
        ${head}
        <div class="ac-result ac-lose">
          <span class="ac-ri ac-ri-av">${this._avatar(a.winner_id)}</span>
          <div>${this._t("auction.sibling_won", { name: winner })}<small>${sub}</small></div>
        </div>
        ${closed}
      </div>`;
  }

  _renderSheet(a) {
    const v = this._sheet.value;
    const valid = v >= a.min_points && v <= a.max_points;
    const others = Math.max(0, (a.bid_count || 0) - (a.my_bid != null ? 1 : 0));
    const close = () => { this._sheet = null; };
    const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];
    return html`
      <div class="ac-scrim" @click=${e => { if (e.target === e.currentTarget) close(); }}>
        <div class="ac-sheet" role="dialog" aria-modal="true" aria-label="${a.chore_name}">
          <div class="ac-grab"></div>
          <h3>${a.chore_name}</h3>
          <div class="ac-sheet-sub">${this._t("auction.sheet_sub", { date: this._date(a.occurrence), time: this._fmtDur(this._left(a)) })}</div>
          <div class="ac-bigbid">${v} <ha-icon icon="mdi:star"></ha-icon></div>
          <div class="ac-bidlbl">${this._t("auction.bid_label")}</div>
          <input type="range" class="ac-range" min="${a.min_points}" max="${a.max_points}" .value=${String(Math.max(a.min_points, v))}
                 aria-label="${this._t("auction.bid_label")}"
                 @input=${e => this._setBid(e.target.value, a)}>
          <div class="ac-rng-l"><span>${this._t("auction.range_low", { points: a.min_points })}</span><span>${this._t("auction.range_high", { points: a.max_points })}</span></div>
          <div class="ac-keypad">
            ${keys.map(k => html`<button type="button" @click=${() => this._key(k, a)}>${k}</button>`)}
            <button type="button" class="ac-key-clear" @click=${() => this._key("c", a)}>${this._t("auction.clear")}</button>
            <button type="button" @click=${() => this._key("0", a)}>0</button>
            <button type="button" aria-label="${this._t("auction.backspace")}" @click=${() => this._key("bs", a)}><ha-icon class="tm-rtl-flip" icon="mdi:backspace-outline"></ha-icon></button>
          </div>
          <div class="ac-rules">
            <div><ha-icon icon="mdi:lock-outline"></ha-icon><span>${this._t("auction.rule_secret")}${others ? ` ${others === 1 ? this._t("auction.other_bids_one") : this._t("auction.other_bids", { count: others })}.` : ""}</span></div>
            <div><ha-icon icon="mdi:trophy-outline"></ha-icon><span>${this._t("auction.rule_lowest")}</span></div>
            ${a.min_points > 1 ? html`<div><ha-icon icon="mdi:arrow-collapse-down"></ha-icon><span>${this._t("auction.rule_min", { points: a.min_points })}</span></div>` : ""}
            <div><ha-icon icon="mdi:check"></ha-icon><span>${this._t("auction.rule_win", { date: this._date(a.occurrence, false) })}</span></div>
          </div>
          <div class="ac-sheet-acts">
            <button type="button" class="ac-btn ac-ghost" @click=${close}>${this._t("auction.cancel")}</button>
            <button type="button" class="ac-btn ac-bid ac-seal" ?disabled=${!valid || this._busy} @click=${() => this._seal(a)}>
              <ha-icon icon="mdi:email-lock"></ha-icon>${this._t("auction.seal", { points: v })}
            </button>
          </div>
        </div>
      </div>`;
  }

  static get styles() {
    const base = css`
      :host { display: block; --ac-accent: var(--tmd-accent, #5e35b1); --ac-auc: #7e57c2; }
      ha-card {
        position: relative;
        overflow: hidden;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px));
        font-family: var(--tmd-font-body, inherit);
      }
      ha-card.ac-sheet-open { min-height: 700px; }
      .ac-hd {
        display: flex; align-items: center; gap: 12px;
        padding: 14px 18px;
        background: var(--ac-accent);
        color: var(--tmd-hd-text, #fff);
      }
      :host([data-tm-design="playroom"]) .ac-hd {
        background: linear-gradient(135deg, var(--ac-accent), color-mix(in srgb, var(--ac-accent) 72%, #fff));
      }
      .ac-hd-gavel {
        width: 48px; height: 48px; flex: none; border-radius: 14px;
        display: grid; place-items: center;
        background: rgba(255, 255, 255, .18);
      }
      .ac-hd-gavel ha-icon { --mdc-icon-size: 28px; }
      .ac-hd-text { flex: 1; min-width: 0; }
      .ac-hd-title {
        font-family: var(--tmd-font-display, inherit);
        font-size: 1.3rem; font-weight: 600;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .ac-hd-sub { font-size: .8rem; opacity: .85; margin-top: 1px; }
      .ac-hd-pill {
        flex: none; white-space: nowrap;
        background: rgba(255, 255, 255, .2);
        padding: 4px 12px; border-radius: 16px;
        font-size: .9rem; font-weight: 500;
      }
      .ac-content { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
      .ac-empty {
        text-align: center; padding: 30px 12px;
        color: var(--tmd-dim, var(--secondary-text-color));
      }
      .ac-err { color: var(--tmd-bad, var(--error-color, #c62828)); padding: 12px; }
      .ac-sec {
        font-size: .8rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
        color: var(--tmd-dim, var(--secondary-text-color));
        margin: 4px 2px -4px;
      }
      .ac-grow { flex: 1; min-width: 0; }
      .ac-faint { font-size: 12px; color: var(--tmd-dim, var(--secondary-text-color)); }

      .ac-lot {
        border-radius: var(--tmd-radius-sm, 18px);
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        border: 2px solid color-mix(in srgb, var(--ac-auc) 45%, var(--tmd-border, var(--divider-color, #e0e0e0)));
        overflow: hidden;
      }
      .ac-lot.ac-won { border-color: var(--tmd-gold, #f1c40f); }
      .ac-lot.ac-lost, .ac-lot.ac-nobid { border-color: var(--tmd-border, var(--divider-color, #e0e0e0)); opacity: .85; }
      .ac-lot-top { display: flex; gap: 12px; padding: 14px 14px 10px; align-items: flex-start; }
      .ac-lot-ic {
        width: 46px; height: 46px; flex: none; border-radius: 14px;
        display: grid; place-items: center; color: #fff;
        background: linear-gradient(135deg, var(--ac-auc), var(--ac-accent));
        box-shadow: 0 3px 10px color-mix(in srgb, var(--ac-accent) 40%, transparent);
      }
      .ac-lot-ic ha-icon { --mdc-icon-size: 24px; }
      :host([data-tm-design="accessible"]) .ac-lot-ic { box-shadow: none; border: 2px solid var(--tmd-border, #111); }
      .ac-lot-t {
        font-family: var(--tmd-font-display, inherit);
        font-size: 1.12rem; font-weight: 700; line-height: 1.25; overflow-wrap: anywhere;
      }
      .ac-lot-when {
        display: flex; align-items: center; gap: 6px; margin-top: 2px;
        font-size: .85rem; color: var(--tmd-dim, var(--secondary-text-color));
      }
      .ac-lot-when ha-icon { --mdc-icon-size: 14px; }
      .ac-tag {
        display: inline-flex; align-items: center; gap: 4px; flex: none;
        font-size: .72rem; font-weight: 700;
        padding: 2px 9px; border-radius: 999px; white-space: nowrap;
        background: var(--tmd-surface-2, rgba(127, 127, 127, .12));
        color: var(--tmd-dim, var(--secondary-text-color));
        border: 1px solid var(--tmd-border, transparent);
      }
      .ac-tag ha-icon { --mdc-icon-size: 12px; }
      .ac-tag-max, .ac-tag-won {
        background: color-mix(in srgb, var(--ac-auc) 16%, transparent);
        color: color-mix(in srgb, var(--ac-auc) 70%, var(--tmd-text, var(--primary-text-color)));
      }

      .ac-gauge {
        margin: 0 14px; padding: 10px 12px; border-radius: 12px;
        background: var(--tmd-surface-2, var(--secondary-background-color, rgba(127, 127, 127, .1)));
        border: 1px solid var(--tmd-border, transparent);
      }
      .ac-gauge-row {
        display: flex; justify-content: space-between; gap: 8px;
        font-size: .75rem; font-weight: 600; letter-spacing: .02em;
        color: var(--tmd-dim, var(--secondary-text-color));
      }
      .ac-caps { text-transform: uppercase; }
      .ac-gauge-bar {
        height: 10px; border-radius: 5px; margin: 6px 0;
        background: linear-gradient(90deg, var(--tmd-good, #2ecc71), var(--tmd-gold, #f1c40f) 60%, var(--tmd-warn, #e67e22));
      }
      /* Low (green) sits at the reading start, beside the minimum label. */
      :host([dir="rtl"]) .ac-gauge-bar { transform: scaleX(-1); }
      .ac-gauge-hint { font-size: .78rem; text-align: center; color: var(--tmd-dim, var(--secondary-text-color)); }

      .ac-sealed {
        margin: 0 14px; padding: 12px;
        display: flex; gap: 12px; align-items: center;
        border-radius: 14px;
        background: color-mix(in srgb, var(--ac-auc) 14%, transparent);
        border: 1px dashed color-mix(in srgb, var(--ac-auc) 60%, transparent);
      }
      .ac-env { width: 44px; height: 40px; flex: none; display: grid; place-items: center; color: var(--ac-auc); }
      .ac-env ha-icon { --mdc-icon-size: 36px; }
      .ac-sealed small { display: block; font-size: .78rem; color: var(--tmd-dim, var(--secondary-text-color)); }
      .ac-sealed b { font-size: 1.4rem; font-family: var(--tmd-font-display, inherit); }

      .ac-lot-foot { display: flex; align-items: center; gap: 10px; padding: 12px 14px; flex-wrap: wrap; }
      .ac-cdown {
        display: inline-flex; align-items: center; gap: 6px;
        font-weight: 700; font-size: .9rem; font-variant-numeric: tabular-nums;
        color: color-mix(in srgb, var(--ac-auc) 75%, var(--tmd-text, var(--primary-text-color)));
      }
      .ac-cdown ha-icon { --mdc-icon-size: 16px; }
      .ac-bidcount {
        display: inline-flex; align-items: center; gap: 5px;
        font-size: .8rem; color: var(--tmd-dim, var(--secondary-text-color));
      }
      .ac-bidcount ha-icon { --mdc-icon-size: 14px; }

      .ac-result {
        margin: 0 14px; padding: 12px 14px; border-radius: 14px;
        display: flex; gap: 12px; align-items: center; font-weight: 600;
      }
      .ac-result small { display: block; font-weight: 500; font-size: .82rem; opacity: .85; margin-top: 2px; }
      .ac-win { background: linear-gradient(135deg, var(--tmd-gold, #f1c40f), #f39c12); color: #3b2a00; }
      .ac-lose, .ac-nob {
        background: var(--tmd-surface-2, var(--secondary-background-color, rgba(127, 127, 127, .1)));
        border: 1px solid var(--tmd-border, transparent);
      }
      .ac-nob { color: var(--tmd-dim, var(--secondary-text-color)); }
      .ac-ri {
        width: 42px; height: 42px; flex: none; border-radius: 50%;
        display: grid; place-items: center; background: rgba(255, 255, 255, .35);
      }
      .ac-ri-av { background: transparent; }
      .ac-won-chore {
        margin: 10px 14px 0; padding: 10px 12px;
        display: flex; align-items: center; gap: 10px;
        border-radius: 16px;
        border: 3px solid var(--tmd-gold, #f1c40f);
        background: color-mix(in srgb, var(--tmd-gold, #f1c40f) 8%, transparent);
      }
      .ac-won-nm { font-weight: 700; }
      .ac-pts {
        display: inline-flex; align-items: center; gap: 4px;
        font-weight: 700; color: var(--tmd-warn, #e67e22);
      }
      .ac-pts ha-icon { --mdc-icon-size: 16px; }
      .ac-av {
        width: var(--ac-s, 30px); height: var(--ac-s, 30px); flex: none;
        border-radius: 50%;
        background: var(--ac-ac, #9b59b6); color: #fff;
        display: inline-grid; place-items: center;
        font-weight: 700; font-size: calc(var(--ac-s, 30px) * .42); line-height: 1;
        box-sizing: border-box;
      }

      .ac-btn {
        display: inline-flex; align-items: center; justify-content: center; gap: 6px;
        border: 0; cursor: pointer;
        border-radius: var(--tmd-radius-sm, 10px);
        padding: 9px 16px; min-height: 36px;
        font: inherit; font-family: var(--tmd-font-display, inherit);
        font-size: .92rem; font-weight: 600; color: #fff; white-space: nowrap;
      }
      .ac-btn ha-icon { --mdc-icon-size: 17px; }
      .ac-btn[disabled] { opacity: .45; cursor: default; }
      .ac-sm { padding: 6px 12px; min-height: 30px; font-size: .82rem; }
      .ac-bid { background: linear-gradient(135deg, var(--ac-auc), var(--ac-accent)); }
      .ac-text { background: transparent; color: var(--tmd-dim, var(--secondary-text-color)); }
      .ac-ghost {
        background: transparent; color: var(--tmd-text, var(--primary-text-color));
        border: 1px solid var(--tmd-border, var(--divider-color, #ccc));
      }

      .ac-scrim {
        position: absolute; inset: 0; z-index: 5;
        display: flex; align-items: flex-end;
        background: rgba(0, 0, 0, .6);
        border-radius: inherit;
      }
      .ac-sheet {
        width: 100%; box-sizing: border-box;
        padding: 10px 18px 20px;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: 26px 26px 0 0;
        border: 1px solid var(--tmd-border, transparent);
        box-shadow: 0 -10px 40px rgba(0, 0, 0, .45);
      }
      .ac-grab {
        width: 40px; height: 5px; border-radius: 3px; margin: 0 auto 10px;
        background: var(--tmd-border, var(--divider-color, #9aa3ad));
      }
      .ac-sheet h3 { margin: 0; font-size: 1.1rem; text-align: center; font-family: var(--tmd-font-display, inherit); }
      .ac-sheet-sub { text-align: center; font-size: .85rem; margin: 2px 0 8px; color: var(--tmd-dim, var(--secondary-text-color)); }
      .ac-bigbid {
        display: flex; align-items: center; justify-content: center; gap: 8px;
        font-size: 3.2rem; font-weight: 800; line-height: 1;
        margin: 8px 0 2px; font-variant-numeric: tabular-nums;
        font-family: var(--tmd-font-display, inherit);
      }
      .ac-bigbid ha-icon { --mdc-icon-size: 38px; color: var(--tmd-gold, #f1c40f); }
      .ac-bidlbl { text-align: center; font-size: .8rem; margin-bottom: 8px; color: var(--tmd-dim, var(--secondary-text-color)); }
      .ac-range { width: 100%; height: 28px; accent-color: var(--ac-auc); margin: 0; }
      .ac-rng-l {
        display: flex; justify-content: space-between;
        font-size: .72rem; color: var(--tmd-dim, var(--secondary-text-color));
      }
      .ac-keypad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin: 12px 0; }
      .ac-keypad button {
        height: 44px; border-radius: 12px; cursor: pointer;
        display: grid; place-items: center;
        font: inherit; font-size: 1.2rem; font-weight: 600;
        background: var(--tmd-surface-2, var(--secondary-background-color, rgba(127, 127, 127, .12)));
        color: var(--tmd-text, var(--primary-text-color));
        border: 1px solid var(--tmd-border, transparent);
      }
      .ac-keypad .ac-key-clear { font-size: .9rem; color: var(--tmd-dim, var(--secondary-text-color)); }
      .ac-rules {
        font-size: .8rem; line-height: 1.5;
        padding: 10px 12px; margin-bottom: 12px; border-radius: 12px;
        background: var(--tmd-surface-2, var(--secondary-background-color, rgba(127, 127, 127, .1)));
        color: var(--tmd-dim, var(--secondary-text-color));
      }
      .ac-rules div { display: flex; gap: 8px; align-items: flex-start; }
      .ac-rules ha-icon { --mdc-icon-size: 14px; margin-top: 2px; flex: none; color: var(--ac-auc); }
      .ac-sheet-acts { display: flex; gap: 10px; }
      .ac-sheet-acts .ac-ghost { flex: 1; }
      .ac-sheet-acts .ac-seal { flex: 2; }
    `;
    // The token block is :host-scoped, so it only takes effect when included
    // in THIS card's styles — a document-level rule cannot cross into the
    // shadow root.
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

class TaskMateAuctionCardEditor extends LitElement {
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
          select: { options: children.map(c => ({ value: c.id, label: c.name })), mode: "dropdown" },
        },
      },
      { name: "title", selector: { text: {} } },
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
    child_id: this._t("auction.editor.child"),
    title: this._t("common.editor.card_title"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  _computeHelper = (entry) => ({
    entity: this._t("common.editor.overview_entity_helper"),
    child_id: this._t("auction.editor.child_helper"),
  }[entry.name] ?? "");

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
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

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      // "global" is the absence of a per-card override, not a value to store.
      if (value === "" || value === null || value === undefined || (key === "card_design" && value === "global")) {
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

customElements.define("taskmate-auction-card", TaskMateAuctionCard);
customElements.define("taskmate-auction-card-editor", TaskMateAuctionCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-auction-card",
  name: "TaskMate Chore Auction",
  description: "Children bid the fewest points they'd do an unpopular chore for — lowest bid wins",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-auction-card", "overview"),
});
