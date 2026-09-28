/**
 * TaskMate Recap Card (#929)
 * A "Wrapped"-style story of a child's finished period: chores done, points
 * earned, top chore, longest streak, best day, badges and rewards, and how it
 * compared with the period before. Tap the right of a slide to go on, the
 * left to go back. "Older" lists every kept recap; the finale saves a
 * shareable summary as a PNG, drawn in the browser.
 *
 * Recaps are fetched over the websocket (taskmate/recaps/*) rather than read
 * from a sensor attribute — a year of them would blow the 16 KB cap.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

const RECAP_FREQUENCIES = ["weekly", "monthly", "every_3_months", "every_6_months", "every_9_months", "yearly"];
// Longest first: several recaps on one day open with the longest period.
const FREQ_RANK = { yearly: 0, every_9_months: 1, every_6_months: 2, every_3_months: 3, monthly: 4, weekly: 5, preview: 6 };
const SEEN_KEY = "taskmate_recap_seen";
// A recap older than this isn't flagged NEW on a device that never opened it.
const NEW_WINDOW_DAYS = 30;
const REFETCH_MS = 5 * 60 * 1000;
const AUTOPLAY_MS = 6000;

// Slide gradients (classic). Other designs re-map --s1/--s2 in CSS.
const SLIDE_COLOURS = {
  intro: ["#ff6b9d", "#9b59b6"],
  chores: ["#3498db", "#1abc9c"],
  points: ["#f5b700", "#e67e22"],
  top: ["#2ecc71", "#16a085"],
  streak: ["#e74c3c", "#e67e22"],
  best: ["#8e44ad", "#3498db"],
  badges: ["#16a085", "#8e44ad"],
  cmp: ["#34495e", "#1f2b38"],
  fin: ["#ff6b9d", "#f39c12"],
};

/** "2026-09-01" → a Date at UTC midnight, so formatting never shifts a day. */
function _day(iso) {
  const [y, m, d] = String(iso || "").split("-").map(Number);
  return new Date(Date.UTC(y || 1970, (m || 1) - 1, d || 1));
}

function _loadSeen() {
  try { return JSON.parse(window.localStorage.getItem(SEEN_KEY) || "{}") || {}; } catch (e) { return {}; }
}

class TaskMateRecapCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _list: { state: true },
      _recap: { state: true },
      _idx: { state: true },
      _sheet: { state: true },
      _filter: { state: true },
      _error: { state: true },
      _toast: { state: true },
    };
  }

  constructor() {
    super();
    this._list = null;
    this._recap = null;
    this._idx = 0;
    this._sheet = false;
    this._filter = "all";
    this._error = "";
    this._toast = "";
    this._cache = new Map();
    this._lastFetch = 0;
    this._loadedFor = null;
  }

  shouldUpdate(changedProps) {
    if (changedProps.size === 1 && changedProps.has("hass")) {
      this._maybeRefetch();
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
    }
    return true;
  }

  connectedCallback() {
    super.connectedCallback();
    this._armAutoplay();
    if (this.hass && this.config) this._maybeRefetch(true);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this._autoplay);
    this._autoplay = null;
    clearTimeout(this._toastTimer);
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  // Count strings have a `<key>_singular` twin. Which form a number takes follows
  // the language of the strings (French and Brazilian Portuguese also say "0 tâche"),
  // not a bare `=== 1`. Intl's "pt" is Brazilian; HA's "pt" is European.
  _tn(key, count, params) {
    const lang = this.hass?.language === "pt" ? "pt-PT" : this.hass?.language || "en";
    let one;
    try { one = new Intl.PluralRules(lang).select(Number(count)) === "one"; } catch { one = Number(count) === 1; }
    return this._t(one ? `${key}_singular` : key, params);
  }

  setConfig(config) {
    this.config = {
      entity: "sensor.taskmate_overview",
      title: null,
      child_id: null,
      header_color: "#9b59b6",
      default_frequency: null,
      autoplay: false,
      ...config,
    };
    this._loadedFor = null;
    this._armAutoplay();
  }

  getCardSize() { return 9; }
  static getConfigElement() { return document.createElement("taskmate-recap-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  // ── data ────────────────────────────────────────────────────────────────

  _maybeRefetch(force = false) {
    const childId = this.config?.child_id;
    if (!this.hass || !childId) return;
    const stale = Date.now() - this._lastFetch > REFETCH_MS;
    if (force || this._loadedFor !== childId || stale) this._load();
  }

  async _load() {
    const childId = this.config.child_id;
    const fresh = this._loadedFor !== childId;
    this._loadedFor = childId;
    this._lastFetch = Date.now();
    try {
      const res = await this.hass.callWS({ type: "taskmate/recaps/list", child_id: childId });
      this._list = res;
      this._error = "";
      if (fresh || !this._recap || !(res.recaps || []).some((r) => r.id === this._recap.id)) {
        const first = this._pickFirst(res.recaps || []);
        if (first) await this._open(first.id);
        else this._recap = null;
      }
    } catch (err) {
      this._error = (err && (err.message || err.code)) || String(err);
    }
  }

  _pickFirst(recaps) {
    const unseen = recaps.filter((r) => this._isNew(r));
    if (unseen.length) {
      // Newest period first; several on the same day → the longest period.
      return [...unseen].sort((a, b) =>
        (b.end || "").localeCompare(a.end || "") || (FREQ_RANK[a.frequency] ?? 9) - (FREQ_RANK[b.frequency] ?? 9))[0];
    }
    const want = this.config.default_frequency;
    if (want) {
      const match = recaps.find((r) => r.frequency === want);
      if (match) return match;
    }
    return recaps.find((r) => !r.preview) || recaps[0] || null;
  }

  async _open(id) {
    let recap = this._cache.get(id);
    if (!recap) {
      try {
        const res = await this.hass.callWS({ type: "taskmate/recaps/get", child_id: this.config.child_id, recap_id: id });
        recap = res.recap;
        this._cache.set(id, recap);
      } catch (err) {
        this._error = (err && (err.message || err.code)) || String(err);
        return;
      }
    }
    this._recap = recap;
    this._idx = 0;
    this._markSeen(id);
  }

  _seenIds() {
    const all = _loadSeen();
    return new Set(all[this.config?.child_id] || []);
  }

  _markSeen(id) {
    const all = _loadSeen();
    const key = this.config.child_id;
    const ids = (all[key] || []).filter((x) => x !== id);
    ids.push(id);
    all[key] = ids.slice(-200);
    try { window.localStorage.setItem(SEEN_KEY, JSON.stringify(all)); } catch (e) { /* private mode */ }
  }

  _isNew(summary) {
    if (!summary || this._seenIds().has(summary.id)) return false;
    const created = Date.parse(summary.created_at || "");
    return !Number.isNaN(created) && Date.now() - created < NEW_WINDOW_DAYS * 86400000;
  }

  // ── labels ──────────────────────────────────────────────────────────────

  _lang() {
    return this.hass?.locale?.language || this.hass?.language || undefined;
  }

  _fmt(iso, opts) {
    try {
      return new Intl.DateTimeFormat(this._lang(), { timeZone: "UTC", ...opts }).format(_day(iso));
    } catch (e) {
      return iso;
    }
  }

  _range(startIso, endIso, opts) {
    try {
      const f = new Intl.DateTimeFormat(this._lang(), { timeZone: "UTC", ...opts });
      return f.formatRange ? f.formatRange(_day(startIso), _day(endIso)) : `${f.format(_day(startIso))} – ${f.format(_day(endIso))}`;
    } catch (e) {
      return `${startIso} – ${endIso}`;
    }
  }

  _num(n) {
    try { return Number(n || 0).toLocaleString(this._lang()); } catch (e) { return String(n || 0); }
  }

  /** "August 2026", "15 – 21 Sep 2026", "Apr – Jun 2026", "2026". */
  _periodLabel(r) {
    if (!r) return "";
    switch (r.frequency) {
      case "monthly": return this._fmt(r.start, { month: "long", year: "numeric" });
      case "yearly": return this._fmt(r.start, { year: "numeric" });
      case "weekly":
      case "preview": return this._range(r.start, r.end, { day: "numeric", month: "short", year: "numeric" });
      default: return this._range(r.start, r.end, { month: "short", year: "numeric" });
    }
  }

  /** The short name used inside sentences: "week", "August", "Apr – Jun", "2026". */
  _periodShort(r) {
    switch (r.frequency) {
      case "weekly": return this._t("recap.word.weekly");
      case "preview": return this._t("recap.last_30_days");
      case "monthly": return this._fmt(r.start, { month: "long" });
      case "yearly": return this._fmt(r.start, { year: "numeric" });
      default: return this._range(r.start, r.end, { month: "short" });
    }
  }

  _freqName(freq) { return this._t(`recap.freq.${freq}`); }

  _child() {
    const entity = this.hass?.states?.[this.config.entity];
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity?.attributes || {};
    return (attrs.children || []).find((c) => c.id === this.config.child_id) || null;
  }

  _pointsName() {
    const entity = this.hass?.states?.[this.config.entity];
    return entity?.attributes?.points_name || this._t("common.stars");
  }

  _pointsIcon() {
    const entity = this.hass?.states?.[this.config.entity];
    return entity?.attributes?.points_icon || "mdi:star";
  }

  // ── render ──────────────────────────────────────────────────────────────

  render() {
    if (!this.hass || !this.config) return html``;
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    const hd = _safeColor(this.config.header_color, "#9b59b6");
    // Every design shares one body: only the header shell differs, so a
    // feature added to the story can't go missing from some styles.
    const body = this._renderBody();
    if (design === "classic") {
      return html`<ha-card class="rc-card" style="--hd:${hd}">${this._classicHeader()}${body}</ha-card>`;
    }
    return html`<ha-card class="tmd rc-card" style="--hd:${hd}">${this._designHeader()}${body}</ha-card>`;
  }

  _title() {
    const child = this._child();
    return this.config.title || this._t("recap.default_title", { name: child?.name || "" });
  }

  _subtitle() {
    const r = this._recap;
    if (!r) return "";
    return `${this._periodLabel(r)} · ${this._freqName(r.frequency)}`;
  }

  _classicHeader() {
    return html`
      <div class="card-header">
        <div class="header-content">
          <ha-icon class="header-icon" icon="mdi:creation"></ha-icon>
          <div class="header-text">
            <div class="header-title">${this._title()}</div>
            ${this._recap ? html`<div class="header-sub">${this._subtitle()}</div>` : ""}
          </div>
        </div>
        ${this._olderPill("header-pill")}
      </div>`;
  }

  _designHeader() {
    const sub = this._subtitle();
    return html`
      <div class="tmd-hd">
        <span class="ic"><ha-icon icon="mdi:creation"></ha-icon></span>
        <span class="tt">${this._title()}${sub ? html`<small>${sub}</small>` : ""}</span>
        ${this._olderPill("pill rc-older")}
      </div>`;
  }

  _olderPill(cls) {
    const recaps = this._list?.recaps || [];
    if (!recaps.length) return "";
    const unseen = recaps.filter((r) => this._isNew(r) && r.id !== this._recap?.id).length;
    return html`
      <button class="${cls}" @click=${(e) => this._openSheet(e)} aria-haspopup="dialog">
        ${unseen ? html`<span class="newdot">${unseen}</span>` : ""}${this._t("recap.older")}
        <ha-icon icon="mdi:chevron-down"></ha-icon>
      </button>`;
  }

  _renderBody() {
    if (!this.config.child_id) {
      return html`<div class="rc-body"><div class="rc-empty">${this._t("recap.choose_child")}</div></div>`;
    }
    if (this._error && !this._recap) {
      return html`<div class="rc-body"><div class="rc-empty">${this._t("recap.load_failed", { error: this._error })}</div></div>`;
    }
    if (!this._list) {
      return html`<div class="rc-body"><div class="rc-empty">${this._t("recap.loading")}</div></div>`;
    }
    if (!this._recap) {
      return html`<div class="rc-body">${this._renderEmpty()}</div>`;
    }
    return html`
      <div class="rc-body">
        ${this._renderStory(this._recap)}
        ${this._sheet ? this._renderSheet() : ""}
        ${this._toast ? html`<div class="rc-toast" role="status">${this._toast}</div>` : ""}
      </div>`;
  }

  _renderEmpty() {
    const upcoming = (this._list?.upcoming || [])[0];
    const child = this._child();
    const text = upcoming
      ? this._t("recap.empty", { date: this._fmt(upcoming.ready_on, { day: "numeric", month: "long" }) })
      : this._t("recap.empty_off", { name: child?.name || "" });
    return html`<div class="rc-empty"><ha-icon icon="mdi:creation"></ha-icon><div>${text}</div></div>`;
  }

  _slides(r) {
    const s = ["intro", "chores"];
    if (r.points) s.push("points");
    if (r.top_chore) s.push("top");
    if (r.streak && r.streak.days) s.push("streak");
    if (r.best_day) s.push("best");
    if ((r.badges || []).length || (r.rewards || []).length) s.push("badges");
    if (r.previous) s.push("cmp");
    s.push("fin");
    return s;
  }

  _renderStory(r) {
    const slides = this._slides(r);
    const idx = Math.min(this._idx, slides.length - 1);
    const kind = slides[idx];
    const [s1, s2] = SLIDE_COLOURS[kind];
    const child = this._child();
    const last = idx === slides.length - 1;
    return html`
      <div class="story" data-k="${kind}" style="--s1:${s1};--s2:${s2}" tabindex="0"
           role="group" aria-roledescription="slide"
           aria-label="${this._t("recap.slide_counter", { index: idx + 1, total: slides.length })}"
           @keydown=${(e) => this._onKey(e)}>
        <div class="blob b1"></div><div class="blob b2"></div>
        <div class="segs">${slides.map((_, j) => html`<i class="${j <= idx ? "done" : ""}"></i>`)}</div>
        <div class="story-who">
          ${this._avatar(child)}
          <span>${child?.name || ""}</span>
          <span class="p">· ${this._periodLabel(r)}${r.preview ? html` · ${this._t("recap.preview_tag")}` : ""}</span>
        </div>
        <div class="slide">${this._slide(kind, r)}</div>
        <div class="tapzone prev" @click=${(e) => this._prev(e)}></div>
        <div class="tapzone next" @click=${(e) => this._next(e)}></div>
        ${idx > 0 ? html`<button class="story-nav l" @click=${(e) => this._prev(e)} aria-label="${this._t("recap.prev")}"><ha-icon class="tm-rtl-flip" icon="mdi:chevron-left"></ha-icon></button>` : ""}
        ${!last ? html`<button class="story-nav r" @click=${(e) => this._next(e)} aria-label="${this._t("recap.next")}"><ha-icon class="tm-rtl-flip" icon="mdi:chevron-right"></ha-icon></button>` : ""}
        <div class="story-foot">${idx + 1} / ${slides.length}${!last ? html` · ${this._t("recap.tap_to_continue")}` : ""}</div>
      </div>`;
  }

  _avatar(child) {
    const a = child?.avatar || "";
    const inner = a.startsWith("mdi:")
      ? html`<ha-icon icon="${a}"></ha-icon>`
      : /^(https?:|\/)/.test(a)
        ? html`<img src="${a}" alt="">`
        : (child?.name || "?").slice(0, 1).toUpperCase();
    return html`<span class="who-av">${inner}</span>`;
  }

  _slide(kind, r) {
    // "week", "month", "three months", "year": the word a sentence needs.
    const word = this._t(`recap.word.${r.frequency}`);
    switch (kind) {
      case "intro": return this._slideIntro(r, word);
      case "chores": return this._slideChores(r, word);
      case "points": return this._slidePoints(r);
      case "top": return this._slideTop(r);
      case "streak": return this._slideStreak(r);
      case "best": return this._slideBest(r);
      case "badges": return this._slideBadges(r);
      case "cmp": return this._slideCompare(r, word);
      default: return this._slideFinale(r, word);
    }
  }

  _slideIntro(r, word) {
    const child = this._child();
    return html`
      <div class="glyph"><ha-icon icon="mdi:creation"></ha-icon></div>
      <div class="kick">${this._periodLabel(r)}</div>
      <div class="big title">${this._t("recap.title", { name: child?.name || "", period: this._periodShort(r) })}</div>
      <div class="say">${this._t("recap.slide.intro_say", { period: word })}</div>
      <div class="say tap"><ha-icon icon="mdi:gesture-tap"></ha-icon> ${this._t("recap.slide.tap_to_start")}</div>`;
  }

  _slideChores(r, word) {
    const bars = r.bars || [];
    const max = Math.max(1, ...bars.map((b) => b[1]));
    const perDay = r.days ? r.chores / r.days : 0;
    let say = "";
    if (!r.chores) say = this._t("recap.slide.no_chores", { period: word });
    else if (perDay >= 1) say = this._t("recap.slide.per_day", { count: this._num(Math.round(perDay)) });
    else if (r.days >= 14) say = this._t("recap.slide.per_week", { count: this._num(Math.max(1, Math.round(r.chores / (r.days / 7)))) });
    return html`
      <div class="kick">${this._t("recap.slide.you_finished")}</div>
      <div class="huge">${this._num(r.chores)}</div>
      <div class="unit">${this._tn("recap.slide.chores_unit", r.chores)}</div>
      ${say ? html`<div class="say">${say}</div>` : ""}
      ${bars.length > 1 ? html`
        <div class="minibars">
          ${bars.map((b, i) => html`
            <div class="${b[1] === max && b[1] > 0 ? "hi" : ""}">
              <b style="height:${Math.round((b[1] / max) * 56) + 4}px"></b>${this._barLabel(r, b, i)}
            </div>`)}
        </div>` : ""}`;
  }

  _barLabel(r, bar, i) {
    if (r.frequency === "weekly") return this._fmt(bar[0], { weekday: "narrow" });
    if (r.frequency === "monthly" || r.frequency === "preview") return this._t("recap.week_short", { n: i + 1 });
    if (r.frequency === "yearly" || r.frequency === "every_9_months") return this._fmt(bar[0], { month: "narrow" });
    return this._fmt(bar[0], { month: "short" });
  }

  _slidePoints(r) {
    return html`
      <div class="kick">${this._t("recap.slide.you_earned")}</div>
      <div class="huge">${this._num(r.points)}<ha-icon class="pts-ic" icon="${this._pointsIcon()}"></ha-icon></div>
      <div class="unit">${this._pointsName()}</div>
      <div class="pchips">
        <span>${this._t("recap.slide.from_chores", { count: this._num(r.chore_points) })}</span>
        ${r.bonus_points ? html`<span>${this._t("recap.slide.bonus", { count: this._num(r.bonus_points) })}</span>` : ""}
      </div>`;
  }

  _slideTop(r) {
    const top = r.top_chore;
    const icon = top.icon && top.icon.startsWith("mdi:") ? top.icon : "mdi:broom";
    return html`
      <div class="kick">${this._t("recap.slide.top_chore")}</div>
      <div class="glyph"><ha-icon icon="${icon}"></ha-icon></div>
      <div class="big">${top.name}</div>
      <div class="say"><b class="times">${this._tn("recap.slide.times", top.count, { count: this._num(top.count) })}</b></div>`;
  }

  _slideStreak(r) {
    const st = r.streak;
    const range = st.start === st.end
      ? this._fmt(st.start, { day: "numeric", month: "long" })
      : this._range(st.start, st.end, { day: "numeric", month: "long" });
    return html`
      <div class="kick">${this._t("recap.slide.longest_streak")}</div>
      <div class="glyph round"><ha-icon icon="mdi:fire"></ha-icon></div>
      <div class="huge">${this._num(st.days)}</div>
      <div class="unit">${this._tn("recap.slide.days_in_a_row", st.days)}</div>
      <div class="say">${range}</div>`;
  }

  _slideBest(r) {
    const best = r.best_day;
    const ws = Number.isInteger(r.week_start) ? r.week_start : 0;
    const dow = r.dow || [0, 0, 0, 0, 0, 0, 0];
    const order = [0, 1, 2, 3, 4, 5, 6].map((i) => (i + ws) % 7);
    const dmax = Math.max(1, ...dow);
    const top = dow.indexOf(Math.max(...dow));
    // 2024-01-01 was a Monday: offset it to name any weekday index (0 = Monday).
    const dayIso = (i) => `2024-01-0${i + 1}`;
    return html`
      <div class="kick">${this._t("recap.slide.best_day")}</div>
      <div class="big">${this._fmt(best.date, { weekday: "long", day: "numeric", month: "long" })}</div>
      <div class="say">${this._tn("recap.slide.best_day_say", best.chores, { chores: this._num(best.chores), points: this._num(best.points), points_name: this._pointsName() })}</div>
      <div class="dow">
        ${order.map((i) => html`
          <div class="${i === top ? "hi" : ""}"><b style="height:${Math.round((dow[i] / dmax) * 50) + 4}px"></b>${this._fmt(dayIso(i), { weekday: "narrow" })}</div>`)}
      </div>
      <div class="say small">${this._t("recap.slide.best_weekday", { weekday: this._fmt(dayIso(top), { weekday: "long" }) })}</div>`;
  }

  _slideBadges(r) {
    const badges = r.badges || [];
    const rewards = r.rewards || [];
    return html`
      ${badges.length ? html`
        <div class="kick">${this._t("recap.slide.unlocked")}</div>
        <div class="medals">
          ${badges.slice(0, 3).map((b) => html`
            <div class="medal"><div class="m"><ha-icon icon="${(b.icon || "").startsWith("mdi:") ? b.icon : "mdi:medal"}"></ha-icon></div>${b.name}</div>`)}
        </div>
        ${badges.length > 3 ? html`<div class="say small">${this._t("recap.slide.more", { count: badges.length - 3 })}</div>` : ""}` : ""}
      ${rewards.slice(0, 3).map((w) => html`
        <div class="rc-rw">
          <ha-icon icon="${(w.icon || "").startsWith("mdi:") ? w.icon : "mdi:gift"}"></ha-icon>
          <div class="grow"><b>${w.name}</b><br><span class="muted-w">${this._t("recap.slide.treated")}</span></div>
          <b class="rc-rw-cost">${this._num(w.cost)}<ha-icon icon="${this._pointsIcon()}"></ha-icon></b>
        </div>`)}`;
  }

  _slideCompare(r, word) {
    const p = r.previous;
    const streak = r.streak?.days || 0;
    const rows = [
      [this._t("recap.cmp.chores"), r.chores, p.chores],
      [this._t("recap.cmp.points", { points_name: this._pointsName() }), r.points, p.points],
      [this._t("recap.cmp.streak"), streak, p.streak],
      [this._t("recap.cmp.days_active"), r.days_active, p.days_active],
    ];
    const prevLabel = r.frequency === "weekly"
      ? this._t("recap.prev_week")
      : this._periodShort({ ...r, start: p.start, end: p.end });
    const up = r.chores >= p.chores;
    return html`
      <div class="kick">${this._t("recap.slide.compared", { period: prevLabel })}</div>
      <div class="big mid">${up ? this._t("recap.slide.levelled_up") : this._t("recap.slide.quieter", { period: word })}</div>
      <div class="cmp">
        ${rows.map(([label, now, was]) => {
          const d = now - was;
          const pct = was ? Math.round((Math.abs(d) / was) * 100) : null;
          return html`
            <div class="cmp-row">
              <div>${label}<span class="was">${this._t("recap.cmp.was", { value: this._num(was) })}</span></div>
              <div class="v">${this._num(now)}</div>
              <span class="delta ${d >= 0 ? "up" : "dn"}">
                <ha-icon icon="${d >= 0 ? "mdi:arrow-up" : "mdi:arrow-down"}"></ha-icon>${pct === null ? this._num(Math.abs(d)) : `${pct}%`}
              </span>
            </div>`;
        })}
      </div>`;
  }

  _shareStats(r) {
    return [
      [this._num(r.chores), this._tn("recap.share.chores", r.chores)],
      [this._num(r.points), this._pointsName()],
      [this._num(r.streak?.days || 0), this._tn("recap.share.streak", r.streak?.days || 0)],
      [r.top_chore?.name || "—", this._t("recap.share.top")],
    ];
  }

  _slideFinale(r, word) {
    const child = this._child();
    const stats = this._shareStats(r);
    return html`
      <div class="big mid">${this._t("recap.slide.finale", { period: word, name: child?.name || "" })}</div>
      <div class="share-tile">
        <div class="share-hd">${this._t("recap.title", { name: child?.name || "", period: this._periodShort(r) })} · ${this._periodLabel(r)}</div>
        <div class="g">
          ${stats.map(([v, k], i) => html`<div><b class="${i === 3 ? "txt" : ""}">${v}</b>${k}</div>`)}
        </div>
        <div class="brand"><ha-icon icon="mdi:check-bold"></ha-icon> TaskMate</div>
      </div>
      <div class="fin-acts">
        <button class="rc-btn" @click=${(e) => this._saveImage(e)}><ha-icon icon="mdi:download"></ha-icon> ${this._t("recap.save_image")}</button>
        <button class="rc-btn ghost" @click=${(e) => this._replay(e)}><ha-icon icon="mdi:replay"></ha-icon> ${this._t("recap.again")}</button>
      </div>`;
  }

  _renderSheet() {
    const recaps = this._list?.recaps || [];
    const freqs = ["all", ...new Set(recaps.map((r) => r.frequency))];
    const list = recaps.filter((r) => this._filter === "all" || r.frequency === this._filter);
    const child = this._child();
    const upcoming = (this._list?.upcoming || [])[0];
    return html`
      <div class="sheet-scrim" @click=${(e) => this._closeSheet(e)}>
        <div class="sheet" role="dialog" aria-modal="true" @click=${(e) => e.stopPropagation()}>
          <div class="grab"></div>
          <h4><ha-icon icon="mdi:calendar-month"></ha-icon> ${this._t("recap.sheet_title", { name: child?.name || "" })}
            <button class="x-btn" @click=${(e) => this._closeSheet(e)} aria-label="${this._t("common.close")}"><ha-icon icon="mdi:close"></ha-icon></button>
          </h4>
          ${freqs.length > 2 ? html`
            <div class="freq-tabs">
              ${freqs.map((f) => html`
                <button class="rc-chip ${f === this._filter ? "on" : ""}" @click=${() => { this._filter = f; }}>
                  ${f === "all" ? this._t("common.all") : this._freqName(f)}
                </button>`)}
            </div>` : ""}
          ${list.map((x) => html`
            <button class="per ${x.id === this._recap?.id ? "cur" : ""}" @click=${() => this._pick(x.id)}>
              <span class="ic"><ha-icon icon="${x.frequency === "weekly" ? "mdi:calendar-week" : x.frequency === "yearly" ? "mdi:trophy" : "mdi:creation"}"></ha-icon></span>
              <span class="grow">
                <span class="t">${this._periodLabel(x)}</span>
                <span class="s">${this._freqName(x.frequency)} · ${this._tn("recap.chores_count", x.chores, { count: this._num(x.chores) })} · ${this._num(x.points)} ${this._pointsName()}</span>
              </span>
              ${this._isNew(x) && x.id !== this._recap?.id ? html`<span class="newdot">${this._t("recap.new")}</span>` : ""}
              <ha-icon class="tm-rtl-flip" icon="mdi:chevron-right"></ha-icon>
            </button>`)}
          ${upcoming ? html`
            <div class="per locked">
              <span class="ic"><ha-icon icon="mdi:lock-outline"></ha-icon></span>
              <span class="grow">
                <span class="t">${this._periodLabel(upcoming)}</span>
                <span class="s">${this._t("recap.ready_on", { date: this._fmt(upcoming.ready_on, { day: "numeric", month: "long" }) })}</span>
              </span>
            </div>` : ""}
        </div>
      </div>`;
  }

  // ── interaction ─────────────────────────────────────────────────────────

  _slideCount() { return this._recap ? this._slides(this._recap).length : 0; }

  _next(e) {
    if (e) e.stopPropagation();
    if (this._idx < this._slideCount() - 1) this._idx += 1;
    this._armAutoplay();
  }

  _prev(e) {
    if (e) e.stopPropagation();
    if (this._idx > 0) this._idx -= 1;
    this._armAutoplay();
  }

  _replay(e) {
    if (e) e.stopPropagation();
    this._idx = 0;
    this._armAutoplay();
  }

  _onKey(e) {
    // The story reads in the layout's direction, so in RTL left is forward (#979).
    const rtl = this.getAttribute("dir") === "rtl";
    if (e.key === (rtl ? "ArrowLeft" : "ArrowRight")) { e.preventDefault(); this._next(); }
    else if (e.key === (rtl ? "ArrowRight" : "ArrowLeft")) { e.preventDefault(); this._prev(); }
  }

  _openSheet(e) {
    if (e) e.stopPropagation();
    this._sheet = true;
  }

  _closeSheet(e) {
    if (e) e.stopPropagation();
    this._sheet = false;
  }

  async _pick(id) {
    this._sheet = false;
    await this._open(id);
    this._armAutoplay();
  }

  _armAutoplay() {
    clearInterval(this._autoplay);
    this._autoplay = null;
    if (!this.config?.autoplay || !this.isConnected) return;
    this._autoplay = setInterval(() => {
      if (this._sheet || !this._recap) return;
      if (this._idx < this._slideCount() - 1) this._idx += 1;
    }, AUTOPLAY_MS);
  }

  _showToast(msg) {
    this._toast = msg;
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => { this._toast = ""; }, 2400);
  }

  /** Draw the finale's summary tile onto a canvas and hand it over as a PNG. */
  async _saveImage(e) {
    if (e) e.stopPropagation();
    const r = this._recap;
    if (!r) return;
    const child = this._child();
    const name = child?.name || "";
    const W = 1080, H = 1350;
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) { this._showToast(this._t("recap.save_failed")); return; }
    const face = getComputedStyle(this).fontFamily || "system-ui, sans-serif";
    const grad = ctx.createLinearGradient(0, 0, W * 0.6, H);
    grad.addColorStop(0, SLIDE_COLOURS.fin[0]);
    grad.addColorStop(1, SLIDE_COLOURS.fin[1]);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "rgba(255,255,255,.12)";
    ctx.beginPath(); ctx.arc(W - 60, 80, 300, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(80, H - 60, 260, 0, Math.PI * 2); ctx.fill();

    const fit = (text, max, size, weight) => {
      let s = size;
      do { ctx.font = `${weight} ${s}px ${face}`; s -= 2; } while (ctx.measureText(text).width > max && s > 18);
    };
    ctx.fillStyle = "#fff";
    ctx.textAlign = "center";
    const word = this._periodShort(r);
    const title = this._t("recap.title", { name, period: word });
    fit(title, W - 140, 84, 800);
    ctx.fillText(title, W / 2, 250);
    fit(this._periodLabel(r), W - 140, 44, 600);
    ctx.globalAlpha = 0.9;
    ctx.fillText(this._periodLabel(r), W / 2, 320);
    ctx.globalAlpha = 1;

    const stats = this._shareStats(r);
    const gx = 110, gy = 420, gw = (W - 2 * gx - 40) / 2, gh = 300;
    stats.forEach(([v, k], i) => {
      const x = gx + (i % 2) * (gw + 40), y = gy + Math.floor(i / 2) * (gh + 40);
      ctx.fillStyle = "rgba(255,255,255,.18)";
      if (ctx.roundRect) { ctx.beginPath(); ctx.roundRect(x, y, gw, gh, 36); ctx.fill(); } else ctx.fillRect(x, y, gw, gh);
      ctx.fillStyle = "#fff";
      ctx.textAlign = "left";
      fit(String(v), gw - 80, i === 3 ? 64 : 120, 800);
      ctx.fillText(String(v), x + 40, y + (i === 3 ? 150 : 170));
      fit(k, gw - 80, 40, 600);
      ctx.globalAlpha = 0.9;
      ctx.fillText(k, x + 40, y + 240);
      ctx.globalAlpha = 1;
    });
    ctx.textAlign = "center";
    ctx.font = `700 40px ${face}`;
    ctx.globalAlpha = 0.85;
    ctx.fillText("✓ TaskMate", W / 2, H - 90);
    ctx.globalAlpha = 1;

    const slug = (name || "recap").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "recap";
    const file = `${slug}-recap-${r.start}.png`;
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    if (!blob) { this._showToast(this._t("recap.save_failed")); return; }
    try {
      const shareFile = typeof File === "function" ? new File([blob], file, { type: "image/png" }) : null;
      // The companion app has no downloads folder: offer the share sheet there.
      if (shareFile && navigator.canShare && navigator.canShare({ files: [shareFile] })) {
        await navigator.share({ files: [shareFile], title });
        return;
      }
    } catch (err) {
      if (err && err.name === "AbortError") return;
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = file;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    this._showToast(this._t("recap.saved", { file }));
  }

  static get styles() {
    const base = css`
      :host { display: block; }
      ha-card { overflow: hidden; position: relative; }

      /* Classic header — full-colour banner */
      .card-header {
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        padding: 14px 18px; background: var(--hd, #9b59b6); color: #fff; min-width: 0;
      }
      .header-content { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
      .header-icon { --mdc-icon-size: 28px; opacity: 0.95; flex: none; }
      .header-text { min-width: 0; }
      .header-title { font-size: 1.25rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .header-sub { font-size: 0.8rem; color: rgba(255, 255, 255, 0.85); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .header-pill, .rc-older {
        display: inline-flex; align-items: center; gap: 5px; flex: none; cursor: pointer;
        background: rgba(255, 255, 255, 0.2); color: #fff; border: 0; border-radius: 16px;
        padding-block: 4px; padding-inline: 12px 10px; font: inherit; font-size: 0.88rem; font-weight: 600;
      }
      .header-pill ha-icon, .rc-older ha-icon { --mdc-icon-size: 16px; }
      .tmd-hd .ic ha-icon { --mdc-icon-size: 18px; }
      .newdot {
        font-size: 10px; font-weight: 800; color: #fff; background: var(--tmd-bad, #e74c3c);
        border-radius: 999px; padding: 1px 7px; letter-spacing: 0.04em; line-height: 1.5;
      }

      .rc-body { padding: 12px; position: relative; }
      .rc-empty {
        display: flex; flex-direction: column; align-items: center; gap: 10px; text-align: center;
        padding: 36px 16px; color: var(--tmd-dim, var(--secondary-text-color));
      }
      .rc-empty ha-icon { --mdc-icon-size: 40px; opacity: 0.6; }

      /* The story */
      .story {
        position: relative; aspect-ratio: 2 / 3; max-height: 560px; min-height: 440px; width: 100%;
        border-radius: var(--tmd-radius, 16px); overflow: hidden; color: #fff; outline: none;
        background: linear-gradient(160deg, var(--s1), var(--s2));
        user-select: none; -webkit-user-select: none;
        font-family: var(--tmd-font-body, inherit);
        transition: background 0.3s ease;
      }
      .story:focus-visible { box-shadow: 0 0 0 3px var(--primary-color, #03a9f4); }
      .blob { position: absolute; border-radius: 50%; background: rgba(255, 255, 255, 0.1); pointer-events: none; }
      .b1 { width: 240px; height: 240px; top: -80px; inset-inline-end: -80px; }
      .b2 { width: 210px; height: 210px; bottom: -70px; inset-inline-start: -70px; }
      .segs { position: absolute; top: 10px; inset-inline-start: 12px; inset-inline-end: 12px; display: flex; gap: 4px; z-index: 3; }
      .segs i { flex: 1; height: 3px; border-radius: 2px; background: rgba(255, 255, 255, 0.35); display: block; }
      .segs i.done { background: #fff; }
      .story-who {
        position: absolute; top: 22px; inset-inline-start: 12px; inset-inline-end: 12px; display: flex; align-items: center; gap: 8px;
        z-index: 3; font-size: 13px; font-weight: 600; min-width: 0;
      }
      .story-who .p { opacity: 0.85; font-weight: 400; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .who-av {
        width: 26px; height: 26px; flex: none; border-radius: 50%; display: grid; place-items: center; overflow: hidden;
        background: rgba(255, 255, 255, 0.25); border: 2px solid rgba(255, 255, 255, 0.6); font-weight: 800; font-size: 12px;
      }
      .who-av ha-icon { --mdc-icon-size: 16px; }
      .who-av img { width: 100%; height: 100%; object-fit: cover; }
      .tapzone { position: absolute; top: 0; bottom: 0; z-index: 2; cursor: pointer; }
      .tapzone.prev { inset-inline-start: 0; width: 33%; }
      .tapzone.next { inset-inline-end: 0; width: 67%; }
      .story-nav {
        position: absolute; top: 50%; transform: translateY(-50%); z-index: 4; width: 34px; height: 34px;
        border-radius: 50%; border: 0; background: rgba(0, 0, 0, 0.22); color: #fff; display: grid; place-items: center; cursor: pointer; padding: 0;
      }
      .story-nav ha-icon { --mdc-icon-size: 20px; }
      .story-nav.l { inset-inline-start: 8px; }
      .story-nav.r { inset-inline-end: 8px; }
      .story-foot {
        position: absolute; bottom: 12px; inset-inline-start: 0; inset-inline-end: 0; text-align: center; font-size: 12px; opacity: 0.8; z-index: 3;
      }
      .slide {
        position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
        text-align: center; padding: 70px 44px 44px; z-index: 1; box-sizing: border-box;
      }
      .kick { font-size: 15px; font-weight: 600; opacity: 0.9; letter-spacing: 0.02em; }
      .huge {
        font-family: var(--tmd-font-display, inherit); font-size: clamp(64px, 20vw, 92px); font-weight: 800; line-height: 1;
        letter-spacing: -3px; margin: 6px 0 2px; display: flex; align-items: center; gap: 8px;
      }
      .huge .pts-ic { --mdc-icon-size: 56px; }
      .big {
        font-family: var(--tmd-font-display, inherit); font-size: 30px; font-weight: 800; line-height: 1.1;
        letter-spacing: -0.5px; margin: 6px 0; overflow-wrap: anywhere;
      }
      .big.title { font-size: 38px; }
      .big.mid { font-size: 25px; }
      .unit { font-size: 22px; font-weight: 700; }
      .say { font-size: 15px; opacity: 0.92; margin-top: 10px; max-width: 280px; line-height: 1.4; }
      .say.small { font-size: 13px; }
      .say.tap { margin-top: 30px; display: flex; align-items: center; gap: 6px; font-weight: 600; }
      .times { font-size: 22px; }
      .glyph {
        width: 96px; height: 96px; border-radius: 28px; background: rgba(255, 255, 255, 0.2); display: grid; place-items: center;
        margin: 12px 0; transform: rotate(-6deg); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
      }
      .glyph.round { border-radius: 50%; }
      .glyph ha-icon { --mdc-icon-size: 54px; }
      .minibars { display: flex; align-items: flex-end; justify-content: center; gap: 6px; height: 80px; margin-top: 22px; width: 100%; }
      .minibars div { flex: 0 1 22px; min-width: 0; }
      .minibars div, .dow div { display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 10px; opacity: 0.95; }
      .minibars b { display: block; width: 100%; border-radius: 5px 5px 2px 2px; background: rgba(255, 255, 255, 0.55); }
      .minibars .hi b, .dow .hi b { background: #fff; }
      .dow { display: flex; gap: 5px; margin-top: 18px; align-items: flex-end; height: 70px; }
      .dow b { display: block; width: 24px; border-radius: 5px; background: rgba(255, 255, 255, 0.35); }
      .pchips { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; margin-top: 16px; }
      .pchips span { background: rgba(255, 255, 255, 0.2); border-radius: 999px; padding: 4px 11px; font-size: 12.5px; font-weight: 600; }
      .medals { display: flex; gap: 14px; justify-content: center; margin: 10px 0 4px; flex-wrap: wrap; }
      .medal { display: flex; flex-direction: column; align-items: center; gap: 6px; width: 86px; font-size: 12px; font-weight: 600; }
      .medal .m {
        width: 62px; height: 62px; border-radius: 50%; background: rgba(255, 255, 255, 0.22); display: grid; place-items: center;
        border: 3px solid rgba(255, 255, 255, 0.55);
      }
      .medal .m ha-icon { --mdc-icon-size: 30px; }
      .rc-rw {
        margin-top: 12px; background: rgba(255, 255, 255, 0.16); border-radius: 14px; padding: 10px 14px; display: flex;
        align-items: center; gap: 10px; text-align: start; font-size: 13px; width: 100%; max-width: 280px; box-sizing: border-box;
      }
      .rc-rw .grow { flex: 1; min-width: 0; }
      .rc-rw-cost { display: inline-flex; align-items: center; gap: 2px; white-space: nowrap; }
      .rc-rw-cost ha-icon { --mdc-icon-size: 14px; }
      .muted-w { opacity: 0.85; }
      .cmp { width: 100%; max-width: 300px; margin-top: 14px; display: flex; flex-direction: column; gap: 8px; }
      .cmp-row {
        display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; background: rgba(255, 255, 255, 0.08);
        border-radius: 12px; padding: 10px 12px; text-align: start; font-size: 13px;
      }
      .cmp-row .v { font-weight: 800; font-size: 17px; }
      .was { font-size: 11px; opacity: 0.7; display: block; font-weight: 400; }
      .delta { display: inline-flex; align-items: center; gap: 2px; font-weight: 800; font-size: 12px; padding: 3px 8px; border-radius: 999px; }
      .delta ha-icon { --mdc-icon-size: 12px; }
      .delta.up { background: rgba(46, 204, 113, 0.25); color: #7dffb0; }
      .delta.dn { background: rgba(255, 120, 110, 0.22); color: #ffb3ab; }
      .share-tile { width: 100%; max-width: 280px; background: rgba(0, 0, 0, 0.18); border-radius: 18px; padding: 14px; margin: 8px 0 14px; box-sizing: border-box; }
      .share-hd { font-size: 12px; font-weight: 700; margin-bottom: 8px; opacity: 0.9; }
      .share-tile .g { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
      .share-tile .g div { background: rgba(255, 255, 255, 0.14); border-radius: 12px; padding: 8px; font-size: 11px; opacity: 0.95; min-width: 0; }
      .share-tile .g b { display: block; font-size: 22px; font-weight: 800; }
      .share-tile .g b.txt { font-size: 14px; line-height: 1.9; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .brand { display: flex; align-items: center; gap: 6px; justify-content: center; font-size: 11px; opacity: 0.8; margin-top: 10px; }
      .brand ha-icon { --mdc-icon-size: 12px; }
      .fin-acts { display: flex; gap: 8px; position: relative; z-index: 5; flex-wrap: wrap; justify-content: center; }
      .rc-btn {
        display: inline-flex; align-items: center; gap: 6px; border: 0; border-radius: var(--tmd-radius-sm, 10px); padding: 9px 16px;
        font: inherit; font-size: 0.92rem; font-weight: 700; cursor: pointer; background: #fff; color: #8e44ad;
      }
      .rc-btn ha-icon { --mdc-icon-size: 18px; }
      .rc-btn.ghost { background: rgba(255, 255, 255, 0.15); color: #fff; border: 1px solid rgba(255, 255, 255, 0.4); }

      /* Older ▾ sheet */
      .sheet-scrim {
        position: absolute; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 10; display: flex; align-items: flex-end;
        border-radius: inherit;
      }
      .sheet {
        background: var(--tmd-surface, var(--card-background-color, #fff)); color: var(--tmd-text, var(--primary-text-color));
        width: 100%; border-radius: 18px 18px 0 0; max-height: 82%; overflow-y: auto; padding: 8px 0 12px;
        box-shadow: 0 -10px 30px rgba(0, 0, 0, 0.35); font-family: var(--tmd-font-body, inherit);
      }
      .grab { width: 40px; height: 4px; border-radius: 2px; background: var(--tmd-border, var(--divider-color, #999)); margin: 4px auto 8px; }
      .sheet h4 { margin: 0; padding-block: 6px 10px; padding-inline: 18px 12px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
      .sheet h4 ha-icon { --mdc-icon-size: 18px; }
      .x-btn { margin-inline-start: auto; background: none; border: 0; color: inherit; cursor: pointer; padding: 4px; display: grid; place-items: center; }
      .freq-tabs { display: flex; gap: 6px; padding: 0 16px 10px; flex-wrap: wrap; }
      .rc-chip {
        font: inherit; font-size: 12.5px; font-weight: 600; padding: 5px 12px; border-radius: 999px; cursor: pointer;
        background: var(--tmd-surface-2, color-mix(in srgb, var(--primary-text-color, #212121) 7%, transparent)); color: var(--tmd-dim, var(--secondary-text-color));
        border: 1px solid var(--tmd-border, var(--divider-color, #ddd));
      }
      .rc-chip.on { background: color-mix(in srgb, var(--hd) 16%, transparent); color: var(--tmd-text, var(--primary-text-color)); border-color: var(--hd); }
      .per {
        display: flex; align-items: center; gap: 12px; padding: 11px 18px; cursor: pointer; width: 100%; text-align: start;
        border: 0; border-top: 1px solid var(--tmd-border, var(--divider-color, #e0e0e0)); background: none; color: inherit; font: inherit;
        box-sizing: border-box;
      }
      .per:hover { background: var(--tmd-surface-2, var(--secondary-background-color, rgba(0, 0, 0, 0.04))); }
      .per.cur { background: color-mix(in srgb, var(--hd) 10%, transparent); }
      .per.locked { cursor: default; opacity: 0.7; }
      .per .ic {
        width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; flex: none;
        background: color-mix(in srgb, var(--hd) 22%, transparent); color: var(--hd);
      }
      .per .ic ha-icon { --mdc-icon-size: 18px; }
      .per .grow { flex: 1; min-width: 0; display: flex; flex-direction: column; }
      .per .t { font-weight: 600; }
      .per .s { font-size: 12px; color: var(--tmd-dim, var(--secondary-text-color)); }
      .per > ha-icon { --mdc-icon-size: 16px; opacity: 0.6; }
      .rc-toast {
        position: absolute; left: 50%; bottom: 24px; transform: translateX(-50%); background: #323232; color: #fff; /* rtl-ok: centred with translate(-50%), symmetric */
        padding: 10px 16px; border-radius: 8px; font-size: 13px; z-index: 20; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
        max-width: 90%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }

      /* ── Per-design treatments of the story (the body is shared) ───────── */
      :host([data-tm-design="playroom"]) .story { border-radius: 26px; }
      :host([data-tm-design="playroom"]) .glyph { border-radius: 32px; }
      :host([data-tm-design="console"]) .story {
        background: radial-gradient(120% 80% at 100% 0%, color-mix(in srgb, var(--s1) 55%, transparent), transparent 60%),
          linear-gradient(160deg, #0e1320, color-mix(in srgb, var(--s2) 45%, #0e1320));
        border: 1px solid color-mix(in srgb, var(--s1) 55%, #2a3550);
      }
      :host([data-tm-design="console"]) .huge { text-shadow: 0 0 24px color-mix(in srgb, var(--s1) 70%, transparent); }
      :host([data-tm-design="console"]) .rc-btn:not(.ghost) { background: var(--s1); color: #06101c; }
      :host([data-tm-design="cleanpro"]) .story {
        background: linear-gradient(160deg, color-mix(in srgb, var(--s1) 82%, #1a2230), color-mix(in srgb, var(--s2) 82%, #1a2230));
      }
      :host([data-tm-design="graphite"]) .story {
        background: linear-gradient(160deg, color-mix(in srgb, var(--hd) 88%, #000), color-mix(in srgb, var(--hd) 55%, #000));
      }
      :host([data-tm-design="graphite"]) .blob { display: none; }
      :host([data-tm-design="graphite"]) .glyph { transform: none; border-radius: 50%; box-shadow: none; }
      :host([data-tm-design="graphite"]) .huge,
      :host([data-tm-design="graphite"]) .big { font-weight: 600; letter-spacing: -1px; font-variant-numeric: tabular-nums; }
      :host([data-tm-design="graphite"]) .rc-btn:not(.ghost) { color: #1d1d1f; }
      :host([data-tm-design="graphite"]) .rc-chip.on { background: transparent; }
      /* Accessible: solid near-black, heavy border, no decorative motion. */
      :host([data-tm-design="accessible"]) .story {
        background: #0a0a0a; border: 3px solid var(--s1); transition: none;
      }
      :host([data-tm-design="accessible"]) .blob { display: none; }
      :host([data-tm-design="accessible"]) .glyph { transform: none; background: #1c1c1c; border: 2px solid #f5f5f5; }
      :host([data-tm-design="accessible"]) .say,
      :host([data-tm-design="accessible"]) .kick,
      :host([data-tm-design="accessible"]) .story-foot,
      :host([data-tm-design="accessible"]) .was { opacity: 1; }
      :host([data-tm-design="accessible"]) .segs i { background: #6b6b6b; }
      :host([data-tm-design="accessible"]) .segs i.done { background: #f5f5f5; }
      :host([data-tm-design="accessible"]) .minibars b, :host([data-tm-design="accessible"]) .dow b { background: #8a8a8a; }
      :host([data-tm-design="accessible"]) .minibars .hi b, :host([data-tm-design="accessible"]) .dow .hi b { background: #f0e442; }
      :host([data-tm-design="accessible"]) .delta.up { background: #009e73; color: #fff; }
      :host([data-tm-design="accessible"]) .delta.dn { background: #d55e00; color: #fff; }
      :host([data-tm-design="accessible"]) .rc-btn:not(.ghost) { background: #f5f5f5; color: #0a0a0a; }
      :host([data-tm-design="accessible"]) .story-nav { background: #f5f5f5; color: #0a0a0a; }

      @media (prefers-reduced-motion: reduce) {
        .story { transition: none; }
      }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

// Card Editor
class TaskMateRecapCardEditor extends LitElement {
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
      .colour-reset { font-size: 0.78rem; color: var(--secondary-text-color); background: none; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; padding: 4px 10px; cursor: pointer; margin-inline-start: auto; }
      .colour-helper { color: var(--secondary-text-color); font-size: 0.82rem; line-height: 1.3; }
    `;
  }

  setConfig(config) { this.config = config; }

  _buildSchema() {
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const children = entity?.attributes?.children || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      {
        name: "child_id",
        selector: {
          select: {
            options: children.map((c) => ({ value: c.id, label: c.name })),
            mode: "dropdown",
          },
        },
      },
      { name: "title", selector: { text: {} } },
      {
        name: "default_frequency",
        selector: {
          select: {
            options: [
              { value: "__newest__", label: this._t("recap.editor.newest") },
              ...RECAP_FREQUENCIES.map((f) => ({ value: f, label: this._t(`recap.freq.${f}`) })),
            ],
            mode: "dropdown",
          },
        },
      },
      { name: "autoplay", selector: { boolean: {} } },
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

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t("common.editor.overview_entity"),
      child_id: this._t("recap.editor.child"),
      title: this._t("common.editor.card_title"),
      default_frequency: this._t("recap.editor.default_frequency"),
      autoplay: this._t("recap.editor.autoplay"),
      card_design: this._t("common.design.field_label"),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t("common.editor.overview_entity_helper"),
      child_id: this._t("recap.editor.child_helper"),
      default_frequency: this._t("recap.editor.default_frequency_helper"),
      autoplay: this._t("recap.editor.autoplay_helper"),
    };
    return helpers[entry.name] ?? "";
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
      default_frequency: this.config.default_frequency || "__newest__",
      autoplay: this.config.autoplay === true,
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
      ${this._renderColourPicker("header_color", "#9b59b6")}
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
      if (
        value === "" || value === null || value === undefined
        || (key === "default_frequency" && value === "__newest__")
        || (key === "card_design" && value === "global")
        || (key === "autoplay" && value === false)
      ) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent("config-changed", {
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

customElements.define("taskmate-recap-card", TaskMateRecapCard);
customElements.define("taskmate-recap-card-editor", TaskMateRecapCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-recap-card",
  name: "TaskMate Recap",
  description: "A Wrapped-style story of a child's week, month or year",
  preview: false,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-recap-card", "overview"),
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-recap-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE RECAP CARD %c v" + _tmVersion + " ",
  "background:#9b59b6;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
