/**
 * TaskMate Trophy Cabinet Card
 *
 * The whole family's achievements on shelves: leaderboard season wins,
 * personal bests, badges, finished quests, perfect weeks and (optionally)
 * legendary pets. Each trophy carries the colour dot of the child who earned
 * it, or a two-tone "whole family" dot when every child shown has it.
 * Anything earned in the last `new_days` days is tagged New, and a spotlight
 * strip names the most recent trophy.
 *
 * Read-only. Everything comes from data the other cards already use:
 *   - season_champions                   (overview)
 *   - children[].personal_bests           (overview)
 *   - children[].quests[].last_completed  (overview)
 *   - children[].awarded_perfect_weeks    (overview)
 *   - children[].pet                      (overview)
 *   - each child's badges sensor, found through the overview's badge_entities
 *     map (#1018) — never a hard-coded entity id.
 *
 * Single layout: it consumes the design tokens directly, and every --tmd-*
 * reference carries the classic value as its fallback, so classic (which
 * defines no tokens) renders the card's own look. Narrow cards (phones, a
 * narrow column) get three tiles per plank, short labels and no spotlight.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

const DEFAULT_ACCENT = "#8d6e63";
const SHELVES = ["seasons", "bests", "badges", "quests", "perfect_weeks", "pets"];
const DEFAULT_SHELVES = ["seasons", "bests", "badges", "quests", "perfect_weeks"];
const DEFAULT_PER_SHELF = 5;
const DEFAULT_NEW_DAYS = 7;
// Below this width the card switches to its narrow layout.
const NARROW_PX = 480;
const NARROW_TILES = 3;

// The classic palette by position, used when a child has no colour of their own.
const CHILD_FALLBACK = ["#e53935", "#1e88e5", "#43a047", "#8e24aa", "#fb8c00", "#00acc1"];

const BEST_EMOJI = {
  longest_streak: "🔥",
  best_day_points: "⭐",
  best_week_points: "📅",
  best_day_chores: "⚡",
  best_single_award: "🏆",
};
const BEST_KEYS = Object.keys(BEST_EMOJI);
const UNIT_KEYS = {
  longest_streak: "trophy.best_value_longest_streak",
  best_day_chores: "trophy.best_value_best_day_chores",
};

const PET_EMOJI = { dragon: "🐉", cat: "🐱", dog: "🐶", bunny: "🐰", dino: "🦖", unicorn: "🦄" };

const pad2 = (n) => String(n).padStart(2, "0");

/** A Date's local calendar day as YYYY-MM-DD. */
function dayKey(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/**
 * Any date the sensors publish — "2026-10-26", "2026-10" or a full ISO
 * timestamp — as a local YYYY-MM-DD, or "" when there isn't one.
 */
function toDay(value) {
  if (!value) return "";
  const s = String(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const d = new Date(s);
  return isNaN(d) ? "" : dayKey(d);
}

/** Whole days from `day` (YYYY-MM-DD) to `today` (YYYY-MM-DD). */
function daysBetween(day, today) {
  const [y1, m1, d1] = day.split("-").map(Number);
  const [y2, m2, d2] = today.split("-").map(Number);
  return Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86400000);
}

/** The day a monthly season was won: the first of the following month. */
function seasonWonOn(month) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(month || ""));
  if (!m) return "";
  const y = Number(m[1]);
  const mo = Number(m[2]);
  return mo === 12 ? `${y + 1}-01-01` : `${y}-${pad2(mo + 1)}-01`;
}

/** The Sunday that closes a perfect week keyed by its Monday. */
function weekEnds(monday) {
  const day = toDay(monday);
  if (!day) return "";
  const [y, m, d] = day.split("-").map(Number);
  return dayKey(new Date(y, m - 1, d + 6));
}

class TaskMateTrophyCabinetCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _expanded: { type: Object },
      _narrow: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._expanded = {};
    this._narrow = false;
    this._ro = null;
  }

  connectedCallback() {
    super.connectedCallback();
    if (typeof ResizeObserver === "function" && !this._ro) {
      this._ro = new ResizeObserver((entries) => {
        const w = entries[0] && entries[0].contentRect ? entries[0].contentRect.width : 0;
        const narrow = w > 0 && w < NARROW_PX;
        if (narrow !== this._narrow) this._narrow = narrow;
      });
      this._ro.observe(this);
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._ro) {
      this._ro.disconnect();
      this._ro = null;
    }
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass")) {
      const old = changedProps.get("hass");
      const base = window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(old, this.hass, this.config?.entity)
        : true;
      if (base || !old || !old.states || !this.hass) return true;
      // Badges live on per-child sensors the shared guard doesn't watch.
      return this._badgeEntityIds().some((id) => old.states[id] !== this.hass.states[id])
        || changedProps.size > 1;
    }
    return true;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error(this._t("trophy.error.entity_required"));
    this.config = { ...config };
    this._expanded = {};
  }

  getCardSize() { return 6; }
  static getConfigElement() { return document.createElement("taskmate-trophy-cabinet-card-editor"); }
  static getStubConfig() { return { entity: "sensor.taskmate_overview" }; }

  /* ── config ───────────────────────────────────────────────────────── */

  _shelfList() {
    const raw = Array.isArray(this.config.shelves) ? this.config.shelves : DEFAULT_SHELVES;
    const out = [];
    for (const s of raw) if (SHELVES.includes(s) && !out.includes(s)) out.push(s);
    return out;
  }

  _perShelf() {
    const n = parseInt(this.config.badges_per_shelf, 10);
    return Number.isFinite(n) && n > 0 ? n : DEFAULT_PER_SHELF;
  }

  _newDays() {
    const n = parseInt(this.config.new_days, 10);
    return Number.isFinite(n) && n >= 0 ? n : DEFAULT_NEW_DAYS;
  }

  /** Today as a local YYYY-MM-DD (a method so tests can pin it). */
  _today() { return dayKey(new Date()); }

  /* ── data ─────────────────────────────────────────────────────────── */

  _attrs() {
    const entity = this.hass?.states?.[this.config.entity];
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || (entity && entity.attributes) || {};
  }

  /** The children on the shelves: the picked ones, else the family without grown-ups. */
  _kids(attrs) {
    const all = Array.isArray(attrs.children) ? attrs.children : [];
    const picked = Array.isArray(this.config.children) ? this.config.children.map(String) : [];
    if (picked.length) return all.filter((c) => picked.includes(String(c.id)));
    return window.__taskmate_family_children
      ? window.__taskmate_family_children(all, this.config)
      : all.filter((c) => !c.is_adult);
  }

  _kidTone(attrs, child) {
    const d = window.__taskmate_design;
    const design = d && d.active ? d.active(this) : "classic";
    const own = child.color && d && d.childColour ? d.childColour(child.color, design) : "";
    if (own) return own;
    const all = attrs.children || [];
    const i = Math.max(0, all.findIndex((k) => String(k.id) === String(child.id)));
    return `var(--tmd-c${(i % 6) + 1}, ${CHILD_FALLBACK[i % CHILD_FALLBACK.length]})`;
  }

  _badgesEntity(child) {
    if (!this.hass || !child) return null;
    const mapped = window.__taskmate_badges_state && window.__taskmate_badges_state(this.hass, child.id);
    if (mapped) return mapped;
    const slug = String(child.name || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    return (slug && this.hass.states?.[`sensor.taskmate_${slug}_badges`]) || null;
  }

  _badgeEntityIds() {
    if (!this.hass || !this.config) return [];
    const ids = [];
    for (const child of this._kids(this._attrs())) {
      const st = this._badgesEntity(child);
      if (st && st.entity_id) ids.push(st.entity_id);
    }
    return ids;
  }

  _fmtMonth(month, short) {
    const m = /^(\d{4})-(\d{2})$/.exec(String(month || ""));
    if (!m) return String(month || "");
    const d = new Date(Number(m[1]), Number(m[2]) - 1, 15);
    const lang = this.hass?.locale?.language || this.hass?.language || undefined;
    return d.toLocaleDateString(lang, short ? { month: "short" } : { month: "long", year: "numeric" });
  }

  _fmtDay(day, withYear) {
    if (!day) return "";
    const [y, m, d] = day.split("-").map(Number);
    const lang = this.hass?.locale?.language || this.hass?.language || undefined;
    return new Date(y, m - 1, d).toLocaleDateString(lang, withYear
      ? { month: "short", year: "numeric" }
      : { day: "numeric", month: "short" });
  }

  /**
   * Every trophy, shelf by shelf. Each shelf is { key, items } with items
   * newest first (undated ones last), and empty shelves left out. An item is
   * { id, shelf, emoji?, icon?, name, short, value, who: [childId], family,
   *   date: "YYYY-MM-DD" | "", fresh, gold, spot: {key, params} }.
   */
  _collect(attrs, kids) {
    const today = this._today();
    const newDays = this._newDays();
    const pointsName = attrs.points_name || this._t("common.points");
    const byId = new Map(kids.map((k) => [String(k.id), k]));
    const isFresh = (day) => {
      if (!day || newDays <= 0) return false;
      const age = daysBetween(day, today);
      return age >= 0 && age < newDays;
    };
    const everyone = (who) => kids.length > 1 && kids.every((k) => who.includes(String(k.id)));
    const shelves = [];

    for (const key of this._shelfList()) {
      let items = [];
      if (key === "seasons") {
        for (const c of Array.isArray(attrs.season_champions) ? attrs.season_champions : []) {
          if (!c || !byId.has(String(c.child_id))) continue;
          const date = seasonWonOn(c.month);
          items.push({
            id: `season:${c.month}`, emoji: "🥇", gold: true,
            name: this._fmtMonth(c.month, false), short: this._fmtMonth(c.month, true),
            value: c.points != null ? `${c.points} ${pointsName}` : "",
            who: [String(c.child_id)], date,
            spot: { key: "trophy.spot_season", params: { season: this._fmtMonth(c.month, false) } },
          });
        }
      } else if (key === "bests") {
        for (const kid of kids) {
          const bests = kid.personal_bests || {};
          const today_ = new Set(Array.isArray(bests.new_today) ? bests.new_today : []);
          for (const rk of BEST_KEYS) {
            const rec = bests[rk];
            if (!rec || !(Number(rec.value) > 0)) continue;
            const label = this._t(`bests.record_${rk}`, { points_name: pointsName });
            // Streaks count days and chores count chores; the rest are points.
            const value = UNIT_KEYS[rk]
              ? this._t(UNIT_KEYS[rk], { value: rec.value })
              : `${rec.value} ${pointsName}`;
            items.push({
              id: `best:${kid.id}:${rk}`, emoji: BEST_EMOJI[rk],
              name: label, short: value, value,
              who: [String(kid.id)], date: toDay(rec.date), forceFresh: today_.has(rk),
              spot: { key: "trophy.spot_best", params: { record: label } },
            });
          }
        }
      } else if (key === "badges") {
        const group = new Map();
        for (const kid of kids) {
          const st = this._badgesEntity(kid);
          const earned = (st && st.attributes && Array.isArray(st.attributes.earned)) ? st.attributes.earned : [];
          for (const b of earned) {
            const bid = window.__taskmate_badge_id ? window.__taskmate_badge_id(b) : String(b.badge_id ?? b.id ?? b.name);
            const day = toDay(b.earned_at);
            const g = group.get(bid) || {
              id: `badge:${bid}`, icon: b.icon || "mdi:medal", name: b.name || "", who: [], date: "",
              tier: b.tier || "",
            };
            if (!g.who.includes(String(kid.id))) g.who.push(String(kid.id));
            if (day && (!g.date || day > g.date)) g.date = day;
            group.set(bid, g);
          }
        }
        items = [...group.values()].map((g) => ({
          ...g, short: g.name, value: "",
          spot: { key: "trophy.spot_badge", params: { badge: g.name } },
        }));
      } else if (key === "quests") {
        const group = new Map();
        for (const kid of kids) {
          for (const q of Array.isArray(kid.quests) ? kid.quests : []) {
            if (!(Number(q.times_completed) > 0)) continue;
            const qid = String(q.quest_id);
            const day = toDay(q.last_completed);
            const g = group.get(qid) || {
              id: `quest:${qid}`, icon: q.icon || "mdi:map-marker-path", name: q.name || "", who: [], date: "", times: 0,
            };
            if (!g.who.includes(String(kid.id))) g.who.push(String(kid.id));
            if (day && (!g.date || day > g.date)) g.date = day;
            g.times = Math.max(g.times, Number(q.times_completed) || 0);
            group.set(qid, g);
          }
        }
        items = [...group.values()].map((g) => ({
          ...g, short: g.name, value: g.times > 1 ? `×${g.times}` : "",
          spot: { key: "trophy.spot_quest", params: { quest: g.name } },
        }));
      } else if (key === "perfect_weeks") {
        for (const kid of kids) {
          const weeks = (Array.isArray(kid.awarded_perfect_weeks) ? kid.awarded_perfect_weeks : []).filter(Boolean);
          if (!weeks.length) continue;
          const last = weeks.map(String).sort().pop();
          const ends = weekEnds(last);
          const date = ends && ends > today ? today : ends;
          items.push({
            id: `pw:${kid.id}`, emoji: "🗓️",
            name: this._t("trophy.perfect_weeks", { count: weeks.length }),
            short: `×${weeks.length}`, value: "",
            who: [String(kid.id)], date,
            spot: { key: "trophy.spot_perfect_week", params: {} },
          });
        }
      } else if (key === "pets") {
        for (const kid of kids) {
          const pet = kid.pet;
          if (!pet || !pet.adopted) continue;
          const all = [];
          if (pet.legendary) all.push({ species: pet.species, name: pet.name });
          for (const f of Array.isArray(pet.family) ? pet.family : []) if (f && f.legendary) all.push(f);
          all.forEach((p, i) => {
            const label = p.name || this._t(`pet.species_${p.species}`);
            items.push({
              id: `pet:${kid.id}:${i}`, emoji: PET_EMOJI[p.species] || "🐾", gold: true,
              name: label, short: label, value: "",
              who: [String(kid.id)], date: "", spot: null,
            });
          });
        }
      }

      for (const it of items) {
        it.shelf = key;
        it.family = everyone(it.who);
        it.fresh = !!it.forceFresh || isFresh(it.date);
        delete it.forceFresh;
      }
      // Newest first; undated last; a stable order otherwise.
      items = items
        .map((it, i) => ({ it, i }))
        .sort((a, b) => (b.it.date || "").localeCompare(a.it.date || "") || a.i - b.i)
        .map((x) => x.it);
      if (items.length) shelves.push({ key, items });
    }
    return shelves;
  }

  /** The most recent dated trophy across every shelf, or null. */
  _latest(shelves) {
    let best = null;
    for (const s of shelves) {
      for (const it of s.items) {
        if (!it.date || !it.spot) continue;
        if (!best || it.date > best.date) best = it;
      }
    }
    return best;
  }

  /** "Since Jun 2026": the oldest dated trophy. */
  _oldest(shelves) {
    let day = "";
    for (const s of shelves) for (const it of s.items) if (it.date && (!day || it.date < day)) day = it.date;
    return day;
  }

  _whoNames(it, kidsById) {
    if (it.family) return this._t("trophy.whole_family");
    return it.who.map((id) => (kidsById.get(id) || {}).name || "").filter(Boolean).join(" & ");
  }

  /**
   * A short mark per child for the dots on a narrow card, where the names
   * are dropped: the first letter, or the first two when two children
   * share a first letter. Some palettes (graphite) have near-identical
   * hues, so the dot alone cannot tell children apart.
   */
  _initials(kids) {
    const first = (k, n) => Array.from(String(k.name || "").trim()).slice(0, n).join("").toLocaleUpperCase();
    const counts = new Map();
    for (const k of kids) counts.set(first(k, 1), (counts.get(first(k, 1)) || 0) + 1);
    return new Map(kids.map((k) => {
      const one = first(k, 1);
      const two = Array.from(String(k.name || "").trim()).slice(0, 2).join("");
      return [String(k.id), counts.get(one) > 1 ? one + two.slice(one.length).toLocaleLowerCase() : one];
    }));
  }

  _dot(bg, mark) {
    return mark
      ? html`<i class="tc-dot tc-dot-mk" style="background:${bg}" aria-hidden="true">${mark}</i>`
      : html`<i class="tc-dot" style="background:${bg}"></i>`;
  }

  _familyDot(kids, tones, narrow) {
    const bg = this._familyFill(kids, tones);
    return narrow
      ? html`<i class="tc-dot tc-dot-mk" style="background:${bg}" aria-hidden="true"><ha-icon icon="mdi:account-group"></ha-icon></i>`
      : html`<i class="tc-dot" style="background:${bg}"></i>`;
  }

  /* ── render ───────────────────────────────────────────────────────── */

  _applyDesign() {
    if (window.__taskmate_design) {
      window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity);
    }
    const hd = _safeColor(this.config.header_color, DEFAULT_ACCENT);
    if (this.style && this.style.setProperty) this.style.setProperty("--tc-hd", hd);
  }

  _toggle(key) {
    this._expanded = { ...this._expanded, [key]: !this._expanded[key] };
  }

  _header(title, sub, pill) {
    return html`
      <div class="tc-hd">
        <span class="tc-hd-ic" aria-hidden="true">🏆</span>
        <div class="tc-hd-tt">
          <div class="tc-hd-title">${title}</div>
          ${sub ? html`<div class="tc-hd-sub">${sub}</div>` : ""}
        </div>
        ${pill ? html`<span class="tc-hd-pill">${pill}</span>` : ""}
      </div>`;
  }

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const title = this.config.title || this._t("trophy.default_title");
    const entity = this.hass.states[this.config.entity];
    if (!entity || entity.state === "unavailable" || entity.state === "unknown") {
      const msg = !entity
        ? this._t("common.entity_not_found", { entity: this.config.entity })
        : this._t("common.unavailable");
      return html`<ha-card class="tc">${this._header(title, "", "")}
        <div class="tc-empty"><div class="tc-empty-ic">⚠️</div><div>${msg}</div></div></ha-card>`;
    }

    const attrs = this._attrs();
    const kids = this._kids(attrs);
    const shelves = this._collect(attrs, kids);
    const kidsById = new Map(kids.map((k) => [String(k.id), k]));
    const tones = new Map(kids.map((k) => [String(k.id), this._kidTone(attrs, k)]));
    const narrow = this._narrow;
    const marks = narrow ? this._initials(kids) : new Map();

    if (!shelves.length) {
      return html`<ha-card class="tc">${this._header(title, "", "")}
        <div class="tc-empty"><div class="tc-empty-ic">🏆</div>
          <div class="tc-empty-tt">${this._t("trophy.empty_title")}</div>
          <div>${this._t("trophy.empty")}</div></div></ha-card>`;
    }

    const total = shelves.reduce((n, s) => n + s.items.length, 0);
    const fresh = shelves.reduce((n, s) => n + s.items.filter((i) => i.fresh).length, 0);
    const sub = [this._t(total === 1 ? "trophy.count_one" : "trophy.count", { count: total }), fresh ? this._t("trophy.new_count", { count: fresh }) : ""]
      .filter(Boolean).join(" · ");
    const oldest = this._oldest(shelves);
    const pill = !narrow && oldest ? this._t("trophy.since", { date: this._fmtDay(oldest, true) }) : "";
    const latest = this.config.show_spotlight !== false && !narrow ? this._latest(shelves) : null;

    // The legend lists only the children who have something on a shelf.
    const present = new Set();
    let anyFamily = false;
    for (const s of shelves) for (const it of s.items) {
      if (it.family) anyFamily = true;
      else it.who.forEach((id) => present.add(id));
    }
    if (anyFamily) kids.forEach((k) => present.add(String(k.id)));
    const legendKids = kids.filter((k) => present.has(String(k.id)));

    return html`
      <ha-card class="tc ${narrow ? "narrow" : ""}">
        ${this._header(title, sub, pill)}
        ${latest ? this._spotlight(latest, kidsById) : ""}
        ${legendKids.length > 1 || anyFamily ? html`
          <div class="tc-legend">
            ${legendKids.map((k) => html`<span>${this._dot(tones.get(String(k.id)), marks.get(String(k.id)))}${k.name}</span>`)}
            ${anyFamily ? html`<span>${this._familyDot(kids, tones, narrow)}${this._t("trophy.whole_family")}</span>` : ""}
          </div>` : ""}
        ${shelves.map((s) => this._shelf(s, kids, kidsById, tones, narrow, marks))}
      </ha-card>`;
  }

  _familyFill(kids, tones) {
    const cols = kids.map((k) => tones.get(String(k.id)));
    if (cols.length <= 1) return cols[0] || "#888";
    const step = 100 / cols.length;
    return `linear-gradient(90deg, ${cols.map((c, i) => `${c} ${i * step}% ${(i + 1) * step}%`).join(", ")})`;
  }

  _spotlight(it, kidsById) {
    const who = it.family ? this._t("trophy.whole_family_subject") : this._whoNames(it, kidsById);
    const line = this._t(it.spot.key, { name: who, ...it.spot.params });
    const detail = [this._fmtDay(it.date, false), it.value].filter(Boolean).join(" · ");
    return html`
      <div class="tc-spot">
        <div class="tc-spot-em" aria-hidden="true">${this._glyph(it)}</div>
        <div class="tc-spot-tx">
          <div class="tc-spot-line"><span class="tc-spot-k">${this._t("trophy.latest")}</span> ${line}</div>
          <div class="tc-spot-sub">${detail}</div>
        </div>
      </div>`;
  }

  _glyph(it) {
    if (it.emoji) return it.emoji;
    const icon = it.icon || "";
    return icon.startsWith("mdi:") ? html`<ha-icon icon="${icon}"></ha-icon>` : icon || "🏅";
  }

  _shelf(shelf, kids, kidsById, tones, narrow, marks) {
    const open = !!this._expanded[shelf.key];
    const cap = narrow ? NARROW_TILES : this._perShelf();
    // Wide: `cap` tiles then a "N more" tile; narrow: the "more" tile takes
    // the last of its three places. A shelf the "more" tile would only swap
    // one trophy for is shown whole.
    const fits = narrow ? cap : cap + 1;
    const over = shelf.items.length > fits;
    const shown = open || !over ? shelf.items : shelf.items.slice(0, narrow ? cap - 1 : cap);
    const hidden = shelf.items.length - shown.length;
    const label = this._t(`trophy.shelf_${shelf.key}`);
    return html`
      <section class="tc-shelf">
        <button class="tc-shelf-hd" type="button" aria-expanded="${open ? "true" : "false"}"
          ?disabled=${!over} @click=${() => this._toggle(shelf.key)}>
          <span class="tc-shelf-name">${label}</span>
          <span class="tc-shelf-n">${shelf.items.length}</span>
          ${over ? html`<ha-icon class="tc-chev" icon="${open ? "mdi:chevron-up" : "mdi:chevron-down"}"></ha-icon>` : ""}
        </button>
        <div class="tc-plank">
          ${shown.map((it) => this._tile(it, kids, kidsById, tones, narrow, marks))}
          ${hidden > 0 ? html`
            <button class="tc-tile tc-more" type="button" @click=${() => this._toggle(shelf.key)}>
              <div class="tc-em" aria-hidden="true">➕</div>
              <div class="tc-nm">${this._t("trophy.more", { count: hidden })}</div>
              ${narrow ? "" : html`<div class="tc-who">${this._t("trophy.tap_to_see")}</div>`}
            </button>` : ""}
          ${open && over ? html`
            <button class="tc-tile tc-more" type="button" @click=${() => this._toggle(shelf.key)}>
              <div class="tc-em" aria-hidden="true">➖</div>
              <div class="tc-nm">${this._t("trophy.show_less")}</div>
            </button>` : ""}
        </div>
      </section>`;
  }

  _tile(it, kids, kidsById, tones, narrow, marks) {
    const names = this._whoNames(it, kidsById);
    // Narrow cards drop the names, so each dot carries the child's initial.
    const dots = it.family
      ? this._familyDot(kids, tones, narrow)
      : it.who.map((id) => this._dot(tones.get(id), marks && marks.get(id)));
    // Season wins and quests carry their month, the rest the child's name.
    let whoText = "";
    if (!narrow) {
      if (it.shelf === "seasons") whoText = names;
      else if (it.shelf === "quests") whoText = [it.family || it.who.length > 1 ? "" : names, it.date ? this._fmtMonth(it.date.slice(0, 7), true) : ""].filter(Boolean).join(" · ") || names;
      else if (it.who.length === 1 || it.family) whoText = names;
    }
    const tip = [it.name, it.value, names, it.date ? this._fmtDay(it.date, false) : ""].filter(Boolean).join(" · ");
    const showValue = !narrow && it.value && it.shelf !== "seasons";
    return html`
      <div class="tc-tile ${it.gold ? "gold" : ""} ${it.fresh ? "new" : ""} ${it.tier ? `tier-${it.tier}` : ""}" title="${tip}" role="img" aria-label="${tip}">
        ${it.fresh ? html`<span class="tc-new">${this._t("trophy.new_tag")}</span>` : ""}
        <div class="tc-em" aria-hidden="true">${this._glyph(it)}</div>
        <div class="tc-nm">${narrow ? it.short : it.name}</div>
        ${showValue ? html`<div class="tc-val">${it.value}</div>` : ""}
        <div class="tc-who">${dots}${whoText ? html`<span>${whoText}</span>` : ""}</div>
      </div>`;
  }

  static get styles() {
    const base = css`
      :host { display: block; --tc-hd: #8d6e63; }
      ha-card.tc {
        overflow: hidden;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px));
        font-family: var(--tmd-font-body, inherit);
      }
      :host([data-tm-design]:not([data-tm-design="classic"])) ha-card.tc { box-shadow: var(--tmd-shadow, none); }
      :host([data-tm-design="graphite"]) ha-card.tc { border: 1px solid var(--tmd-border); box-shadow: none; }

      .tc-hd { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: var(--tc-hd); color: #fff; }
      :host([data-tm-design="playroom"]) .tc-hd { background: linear-gradient(135deg, var(--tc-hd), color-mix(in srgb, var(--tc-hd) 72%, #fff)); }
      .tc-hd-ic { width: 36px; height: 36px; border-radius: 50%; background: rgba(255,255,255,.22); display: grid; place-items: center; font-size: 18px; flex: none; }
      :host([data-tm-design="playroom"]) .tc-hd-ic, :host([data-tm-design="console"]) .tc-hd-ic { border-radius: 9px; }
      .tc-hd-tt { flex: 1; min-width: 0; }
      .tc-hd-title { font-family: var(--tmd-font-display, inherit); font-size: 1.1rem; font-weight: 700; line-height: 1.15;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      :host([data-tm-design="graphite"]) .tc-hd-title { font-weight: 600; letter-spacing: -.4px; }
      .tc-hd-sub { font-size: .78rem; opacity: .9; margin-top: 1px; }
      .tc-hd-pill { background: rgba(255,255,255,.22); border-radius: 999px; padding: 4px 10px; font-size: .8rem; font-weight: 600; white-space: nowrap; flex: none; }
      :host([data-tm-design="graphite"]) .tc-hd-pill { background: transparent; padding: 0; font-weight: 500; }

      .tc-spot { display: flex; gap: 14px; align-items: center; padding: 12px 16px;
        background: linear-gradient(90deg, rgba(255,152,0,.14), rgba(255,152,0,0));
        border-bottom: 1px solid var(--tmd-border, var(--divider-color, #eee)); }
      :host([data-tm-design="graphite"]) .tc-spot { background: var(--tmd-surface-2); }
      :host([data-tm-design="accessible"]) .tc-spot { background: var(--tmd-surface-2); border-bottom-width: 2px; }
      .tc-spot-em { font-size: 40px; line-height: 1; flex: none; }
      .tc-spot-em ha-icon { --mdc-icon-size: 40px; color: var(--tmd-gold, #f9a825); }
      .tc-spot-tx { min-width: 0; }
      .tc-spot-line { font-family: var(--tmd-font-display, inherit); font-weight: 700; font-size: .98rem; }
      .tc-spot-k { color: var(--tmd-warn, #e65100); }
      :host([data-tm-design="graphite"]) .tc-spot-k { color: var(--tmd-dim); }
      :host([data-tm-design="accessible"]) .tc-spot-k { color: var(--tmd-text); text-decoration: underline; }
      .tc-spot-sub { font-size: .8rem; color: var(--tmd-dim, var(--secondary-text-color)); margin-top: 2px; }

      .tc-legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .78rem; color: var(--tmd-dim, var(--secondary-text-color)); padding: 10px 16px 0; }
      .tc-legend span { display: inline-flex; gap: 5px; align-items: center; }

      .tc-shelf { padding: 12px 16px 4px; }
      /* min-height keeps the collapse toggle a comfortable tap target. */
      .tc-shelf-hd { all: unset; box-sizing: border-box; display: flex; align-items: center; gap: 8px; margin: 0 0 4px; cursor: pointer;
        min-height: 32px; width: 100%;
        font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; font-weight: 700; color: var(--tmd-dim, var(--secondary-text-color));
        font-family: var(--tmd-font-display, inherit); border-radius: 6px; }
      .tc-shelf-hd[disabled] { cursor: default; }
      .tc-shelf-hd:focus-visible { outline: 2px solid var(--tmd-accent, var(--primary-color)); outline-offset: 2px; }
      .tc-shelf-n { background: var(--tmd-surface-2, var(--secondary-background-color, #eceff1)); color: var(--tmd-text, var(--primary-text-color));
        border-radius: 999px; padding: 1px 8px; font-size: .7rem; letter-spacing: 0; }
      .tc-chev { --mdc-icon-size: 18px; }

      .tc-plank { display: grid; grid-template-columns: repeat(auto-fill, minmax(118px, 1fr)); gap: 10px; padding: 0 0 10px;
        border-bottom: 6px solid var(--tmd-border, rgba(161,136,127,.5)); border-radius: 0 0 3px 3px; margin-bottom: 8px; }
      :host([data-tm-design="console"]) .tc-plank { border-bottom-color: color-mix(in srgb, var(--tmd-accent) 45%, var(--tmd-border)); }
      :host([data-tm-design="accessible"]) .tc-plank { border-bottom: 4px solid var(--tmd-border); }
      .narrow .tc-plank { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }

      .tc-tile { position: relative; box-sizing: border-box; text-align: center; padding: 10px 8px 8px; min-width: 0;
        background: var(--tmd-surface, var(--card-background-color, #fff));
        border: 1px solid var(--tmd-border, var(--divider-color, #eee)); border-radius: var(--tmd-radius-sm, 12px);
        color: var(--tmd-text, var(--primary-text-color)); font: inherit; }
      .tc-tile.gold { background: linear-gradient(180deg, rgba(255,193,7,.16), rgba(255,193,7,0) 80%), var(--tmd-surface, var(--card-background-color, #fff)); }
      :host([data-tm-design="playroom"]) .tc-tile { border: 0; background: var(--tmd-surface-2); border-radius: 16px; }
      :host([data-tm-design="playroom"]) .tc-tile.gold { background: linear-gradient(180deg, rgba(255,194,60,.35), var(--tmd-surface-2) 80%); }
      :host([data-tm-design="console"]) .tc-tile { background: var(--tmd-surface-2); }
      :host([data-tm-design="console"]) .tc-tile.new { box-shadow: 0 0 12px color-mix(in srgb, var(--tmd-accent) 45%, transparent); border-color: var(--tmd-accent); }
      :host([data-tm-design="cleanpro"]) .tc-tile.gold { background: var(--tmd-surface-2); }
      :host([data-tm-design="graphite"]) .tc-tile, :host([data-tm-design="graphite"]) .tc-tile.gold { background: transparent; }
      :host([data-tm-design="accessible"]) .tc-tile { border-width: 2px; }
      :host([data-tm-design="accessible"]) .tc-tile.gold { background: var(--tmd-surface); }
      .tc-em { font-size: 34px; line-height: 1.15; }
      .tc-em ha-icon { --mdc-icon-size: 34px; color: var(--tmd-accent, var(--primary-color)); }
      .tc-tile.tier-bronze .tc-em ha-icon { color: #b8732f; }
      .tc-tile.tier-silver .tc-em ha-icon { color: #8a9bab; }
      .tc-tile.tier-gold .tc-em ha-icon { color: #e0a100; }
      .tc-tile.tier-platinum .tc-em ha-icon { color: #26a6b8; }
      :host([data-tm-design="graphite"]) .tc-em ha-icon { color: var(--tmd-text); }
      :host([data-tm-design="accessible"]) .tc-em ha-icon { color: var(--tmd-text) !important; }
      .tc-nm { font-family: var(--tmd-font-display, inherit); font-size: .8rem; font-weight: 700; margin-top: 4px; line-height: 1.2;
        overflow-wrap: anywhere; }
      .tc-val { font-size: .8rem; font-weight: 600; margin-top: 1px; }
      .tc-who { display: flex; justify-content: center; align-items: center; gap: 4px; flex-wrap: wrap;
        font-size: .7rem; color: var(--tmd-dim, var(--secondary-text-color)); margin-top: 4px; min-height: 10px; }
      .tc-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; flex: none; }
      :host([data-tm-design="accessible"]) .tc-dot { box-shadow: 0 0 0 1px var(--tmd-text); }
      .tc-dot-mk { width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center;
        font-style: normal; font-family: var(--tmd-font-display, inherit); font-size: 10px; font-weight: 800; line-height: 1;
        letter-spacing: 0; color: #fff; text-shadow: 0 0 2px rgba(0,0,0,.8), 0 1px 1px rgba(0,0,0,.6);
        box-shadow: 0 0 0 1px rgba(0,0,0,.18); }
      .tc-dot-mk ha-icon { --mdc-icon-size: 12px; color: #fff; filter: drop-shadow(0 0 1px rgba(0,0,0,.8)); display: inline-flex; }
      .tc-new { position: absolute; top: -7px; inset-inline-end: -4px; background: var(--tmd-warn, #ff9800); color: #fff;
        font-size: 9px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; border-radius: 6px; padding: 2px 5px; }
      :host([data-tm-design="accessible"]) .tc-new { background: var(--tmd-text); color: var(--tmd-surface); }
      :host([data-tm-design="graphite"]) .tc-new { background: var(--tmd-text); color: var(--tmd-surface); }
      .tc-more { cursor: pointer; opacity: .7; }
      .tc-more:hover, .tc-more:focus-visible { opacity: 1; }
      .tc-more:focus-visible { outline: 2px solid var(--tmd-accent, var(--primary-color)); outline-offset: 2px; }

      .tc-empty { text-align: center; padding: 28px 16px; color: var(--tmd-dim, var(--secondary-text-color)); font-size: .9rem; }
      .tc-empty-ic { font-size: 40px; margin-bottom: 6px; }
      .tc-empty-tt { font-family: var(--tmd-font-display, inherit); font-weight: 700; color: var(--tmd-text, var(--primary-text-color)); margin-bottom: 2px; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

class TaskMateTrophyCabinetCardEditor extends LitElement {
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
    const children = (attrs.children || []).filter((c) => !c.is_adult);
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      { name: "title", selector: { text: {} } },
      {
        name: "shelves",
        selector: {
          select: {
            multiple: true, mode: "list",
            options: SHELVES.map((s) => ({ value: s, label: this._t(`trophy.shelf_${s}`) })),
          },
        },
      },
      {
        name: "children",
        selector: { select: { multiple: true, mode: "list", options: children.map((c) => ({ value: c.id, label: c.name })) } },
      },
      { name: "badges_per_shelf", selector: { number: { min: 1, max: 30, mode: "box" } } },
      { name: "new_days", selector: { number: { min: 0, max: 60, mode: "box" } } },
      { name: "show_spotlight", selector: { boolean: {} } },
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
    title: this._t("trophy.editor.title"),
    shelves: this._t("trophy.editor.shelves"),
    children: this._t("trophy.editor.children"),
    badges_per_shelf: this._t("trophy.editor.per_shelf"),
    new_days: this._t("trophy.editor.new_days"),
    show_spotlight: this._t("trophy.editor.show_spotlight"),
    show_adults: this._t("common.editor.show_adults"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  _computeHelper = (entry) => ({
    entity: this._t("common.editor.overview_entity_helper"),
    shelves: this._t("trophy.editor.shelves_helper"),
    children: this._t("trophy.editor.children_helper"),
    badges_per_shelf: this._t("trophy.editor.per_shelf_helper"),
    new_days: this._t("trophy.editor.new_days_helper"),
    show_adults: this._t("common.editor.show_adults_helper"),
  }[entry.name] ?? "");

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      title: this.config.title || "",
      shelves: Array.isArray(this.config.shelves) ? this.config.shelves : DEFAULT_SHELVES,
      children: Array.isArray(this.config.children) ? this.config.children : [],
      badges_per_shelf: this.config.badges_per_shelf ?? DEFAULT_PER_SHELF,
      new_days: this.config.new_days ?? DEFAULT_NEW_DAYS,
      show_spotlight: this.config.show_spotlight !== false,
      card_design: this.config.card_design || "global",
    };
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${this.config.show_adults === true ? { ...data, show_adults: true } : data}
        .schema=${this._buildSchema().concat(window.__taskmate_adults_field ? window.__taskmate_adults_field(this.hass, this.config) : [])}
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
    if (key === "children") return Array.isArray(value) && value.length === 0;
    if (key === "shelves") {
      return Array.isArray(value) && value.length === DEFAULT_SHELVES.length
        && DEFAULT_SHELVES.every((s, i) => value[i] === s);
    }
    if (key === "badges_per_shelf") return Number(value) === DEFAULT_PER_SHELF;
    if (key === "new_days") return Number(value) === DEFAULT_NEW_DAYS;
    if (key === "show_spotlight") return value === true;
    if (key === "show_adults") return value === false;
    return false;
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (TaskMateTrophyCabinetCardEditor._isDefault(key, value)) delete newConfig[key];
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

customElements.define("taskmate-trophy-cabinet-card", TaskMateTrophyCabinetCard);
customElements.define("taskmate-trophy-cabinet-card-editor", TaskMateTrophyCabinetCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-trophy-cabinet-card",
  name: "TaskMate Trophy Cabinet",
  description: "The whole family's season wins, personal bests, badges, quests and perfect weeks on shelves",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest ? window.__taskmate_suggest(hass, entityId, "taskmate-trophy-cabinet-card", "overview") : undefined,
});
