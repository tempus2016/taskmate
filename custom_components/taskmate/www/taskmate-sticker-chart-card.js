/**
 * TaskMate Sticker Chart Card
 *
 * The fridge-door sticker chart as a whole dashboard view, driven entirely by
 * TaskMate. Parents keep managing chores, points and rewards in the TaskMate
 * panel; this card is only the child's side of it:
 *
 *   summary   "Today: 3 / 7 jobs done", a sticker per point earned, the
 *             child's photo, and blocks filling towards the chosen reward
 *   tiles     one sticker per chore due today — tap to complete (through the
 *             same button entity / service TaskMate's child card uses), hold
 *             to undo (TaskMate only lets a parent do that)
 *   goal      the reward being saved for, and a claim button once it's earned;
 *             with `goal: week` the stickers and blocks count this week's
 *             jobs instead (stars since Monday out of all the week offers)
 *
 * One column per child, side by side, or a single child with `child_id`.
 *
 * Data comes from the TaskMate sensors through window.__taskmate_attrs, so
 * nothing here needs keeping in step by hand:
 *   points / photo  → overview sensor children[] (photo = the child's picture entity)
 *   chores          → chores sensor, filtered to today for each child
 *   done / pending  → today's completions (approved vs awaiting approval)
 *   goal            → a reward's cost (per-child cost when one is set)
 */

// HA's Lit base class, found through an element built on it: the class that
// owns the html tag helper is LitElement itself. Dashboards always define hui-masonry-view;
// the TaskMate admin panel also shows this card (to log past days) and has no
// dashboard views, so fall back to elements every HA page defines.
const LIT_HOST_TAGS = ["hui-masonry-view", "hui-view", "home-assistant-main", "ha-card"];

const findLitBase = () => {
  for (const tag of LIT_HOST_TAGS) {
    let C = customElements.get(tag);
    while (C && C.prototype && !Object.prototype.hasOwnProperty.call(C.prototype, "html")) {
      C = Object.getPrototypeOf(C);
    }
    if (C && C.prototype) return C;
  }
  return null;
};

// A slow tablet can evaluate this module before HA has registered any element
// of its own. Failing here would abort the module, so the card would never be
// defined for that page load ("Custom element doesn't exist") — a race a fast
// desktop wins and a Fire tablet can lose. Wait for one to appear instead.
let litBase = findLitBase();
if (!litBase) {
  await Promise.race([
    ...LIT_HOST_TAGS.map(tag => customElements.whenDefined(tag)),
    new Promise(resolve => setTimeout(resolve, 15000)),
  ]);
  litBase = findLitBase();
}
if (!litBase) throw new Error("TaskMate Sticker Chart: Home Assistant's Lit base class was not found");
const LitElement = litBase;

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// The sticker alphabet, cycled as points accumulate so a long row stays
// interesting instead of being forty identical stars.
const STICKERS = [
  "⭐", "🌟", "🦄", "🌈", "🐶", "🍭", "🚀", "🦖",
  "🐱", "🍓", "🎈", "🦋", "🐬", "🍦", "🎨", "🐸",
];

// Tile colours, assigned by position so a chart keeps its look day to day.
const GRADIENTS = [
  "linear-gradient(135deg,#4facfe,#00f2fe)",
  "linear-gradient(135deg,#a18cd1,#fbc2eb)",
  "linear-gradient(135deg,#f6d365,#fda085)",
  "linear-gradient(135deg,#84fab0,#8fd3f4)",
  "linear-gradient(135deg,#a8e063,#56ab2f)",
  "linear-gradient(135deg,#ff9a9e,#fad0c4)",
  "linear-gradient(135deg,#e0c3fc,#8ec5fc)",
  "linear-gradient(135deg,#fccb90,#d57eeb)",
  "linear-gradient(135deg,#96e6a1,#d4fc79)",
  "linear-gradient(135deg,#fbc2eb,#a6c1ee)",
];

// Keyword → sticker for chores whose name carries no emoji of its own.
// Starting a chore's name with an emoji in TaskMate always wins over this.
const CHORE_EMOJI = [
  [/(teeth|tooth|brush)/, "🦷"], [/(toilet|potty|wee|poo)/, "🚽"],
  [/(pants|knickers)/, "🩲"], [/(pyjama|pajama|jammies)/, "🌙"],
  [/(shoe|trainer)/, "👟"], [/(coat|jacket)/, "🧥"],
  [/(dress|clothes|uniform)/, "👚"], [/(bed)/, "🛏️"],
  [/(breakfast|lunch|dinner|eat)/, "🥣"], [/(bag)/, "🎒"],
  [/(story)/, "📖"], [/(read|book|homework|study|spelling)/, "📚"],
  [/(hand)/, "🧼"], [/(shower|bath)/, "🛁"],
  [/(kind|shar|nice|love)/, "💖"], [/(please|thank|manner)/, "🙏"],
  [/(hoover|vacuum)/, "🧹"], [/(tidy|clean|sweep)/, "🧸"],
  [/(laundry|washing|fold)/, "🧺"], [/(bin|rubbish|trash|recycl)/, "🗑️"],
  [/(dish|plate|table)/, "🍽️"], [/(dog|cat|pet|feed)/, "🐶"],
  [/(plant|water|garden)/, "🪴"], [/(music|piano|practi)/, "🎵"],
  [/(run|exercise|sport|swim)/, "🏃"],
];

// Emoji at the very start of a name: "🦷 Brush teeth" → ["🦷", "Brush teeth"].
const LEADING_EMOJI = /^(\p{Extended_Pictographic}(?:\u{FE0F}|\u{200D}\p{Extended_Pictographic}|[\u{1F3FB}-\u{1F3FF}])*)\s*/u;

const PERIOD_ORDER = { morning: 0, afternoon: 1, evening: 2, anytime: 3 };

// A 500-point reward would otherwise paint 500 emoji into the page; past
// these the row is summarised and each block stands for several stars. 40 stickers
// is about three rows, which keeps the jobs on screen on a tablet.
const MAX_STICKERS = 40;
const MAX_BLOCKS = 60;

const HOLD_MS = 600;       // press-and-hold that means "undo"
const OPTIMISTIC_MS = 20000;
const CONFIRM_MS = 4000;   // second tap on the claim button must land in this window

class TaskMateStickerChartCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      // A past day's completions, when `config.date` is set (the admin
      // panel's "Log a past job"); today's come from the sensors instead.
      dayCompletions: { type: Array },
      _optimistic: { state: true },
      _confirming: { state: true },
      _celebrating: { state: true },
      _confetti: { state: true },
    };
  }

  constructor() {
    super();
    this._optimistic = {};   // "child:chore" -> { childId, choreId, base, count, at }
    this._confirming = "";   // child id whose claim button is armed
    this._celebrating = null; // { day: bool, name, points } while the pop-up shows
    this._confetti = [];
    this._busy = new Set();
    this._holdTimer = null;
    this._held = false;
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass")) {
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
    }
    return true;
  }

  /**
   * Drop an optimistic tick once Home Assistant has caught up with it.
   *
   * It must go the moment the real completion lands, not merely be ignored:
   * a stale entry would resurrect the "done" look as soon as the count dropped
   * again — after an undo, or a parent rejecting it in the panel.
   */
  willUpdate(changedProps) {
    if (!(changedProps.has("hass") || changedProps.has("dayCompletions"))) return;
    if (!Object.keys(this._optimistic).length) return;
    const attrs = this._attrs();
    if (!attrs) return;
    const completions = this._completions(attrs);
    const chores = new Map((attrs.chores || []).map(c => [c.id, c]));
    const next = {};
    for (const [key, opt] of Object.entries(this._optimistic)) {
      const chore = chores.get(opt.choreId);
      const landed = chore ? this._mine(opt.childId, chore, completions).length : Infinity;
      if (landed < opt.base + opt.count && Date.now() - opt.at < OPTIMISTIC_MS) next[key] = opt;
    }
    this._optimistic = next;
  }

  /**
   * This child's completions of a chore today. "__parent__" is a parent
   * dismissing it for the whole pool, so it counts for whoever is looking —
   * except first-come, which is a race the child didn't win.
   */
  _mine(childId, chore, completions) {
    const firstCome = (chore.assignment_mode || "everyone") === "first_come";
    return completions.filter(c => c.chore_id === chore.id
      && (String(c.child_id) === String(childId) || (c.child_id === "__parent__" && !firstCome)));
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  setConfig(config) {
    if (!config.entity) throw new Error(this._t("sticker_chart.error.entity_required"));
    this.config = { ...config };
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  static getConfigElement() { return document.createElement("taskmate-sticker-chart-card-editor"); }

  getCardSize() { return 12; }

  static get styles() {
    const base = css`
      :host { display: block; }
      ha-card {
        background: none; box-shadow: none; border: none; overflow: visible;
        --panel-bg: var(--ha-card-background, var(--card-background-color, rgba(0,0,0,0.35)));
        --panel-radius: var(--ha-card-border-radius, 22px);
      }

      .cols {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
        align-items: start;
      }
      .col { display: flex; flex-direction: column; gap: 10px; min-width: 0; }

      .panel {
        background: var(--panel-bg);
        border-radius: var(--panel-radius);
        box-shadow: var(--ha-card-box-shadow, none);
        border: var(--ha-card-border-width, 0) solid var(--ha-card-border-color, transparent);
        backdrop-filter: var(--ha-card-backdrop-filter, none);
        -webkit-backdrop-filter: var(--ha-card-backdrop-filter, none);
      }

      /* -- Heading -- */
      .heading {
        display: flex; align-items: center; gap: 8px;
        padding: 2px 4px 0;
        color: var(--primary-text-color);
        font-size: 1.05rem; font-weight: 500;
      }
      .heading ha-icon { --mdc-icon-size: 20px; }
      .heading .title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .score {
        display: inline-flex; align-items: center; gap: 4px;
        font-size: 0.9rem; font-weight: 600; color: var(--secondary-text-color);
      }
      .score ha-icon { --mdc-icon-size: 16px; color: var(--tone, #3498db); }

      /* -- Summary -- */
      .summary { padding: 16px; }
      .top-row { display: flex; align-items: flex-start; gap: 14px; }
      .top-main { flex: 1; min-width: 0; }
      .today {
        font-size: 1rem; font-weight: 700;
        color: var(--primary-text-color); margin-bottom: 10px;
      }
      .face {
        width: 112px; height: 112px; min-width: 112px;
        border-radius: 50%; overflow: hidden;
        display: flex; align-items: center; justify-content: center;
        background: rgba(127,127,127,0.18);
        flex: none;
      }
      .face ha-icon { --mdc-icon-size: 60px; color: var(--primary-color); }
      .stickers {
        font-size: 26px; line-height: 1.3;
        word-break: break-all;
      }
      .stickers-none, .muted {
        font-size: 0.92rem; font-weight: 600; color: var(--secondary-text-color);
      }
      .overflow { font-size: 0.85rem; font-weight: 800; color: var(--secondary-text-color); margin-left: 4px; }
      .goal-line {
        margin-top: 14px;
        font-size: 0.92rem; font-weight: 700; color: var(--primary-text-color);
      }
      .blocks { display: flex; flex-wrap: wrap; gap: 3px; margin-top: 6px; }
      .blocks i {
        width: 16px; height: 16px; border-radius: 3px;
        background: #d9d9d9; box-shadow: inset 0 -2px 0 rgba(0,0,0,0.12);
      }
      .blocks i.on { background: #36b43a; box-shadow: inset 0 -2px 0 rgba(0,0,0,0.22); }
      .blocks-key { margin-top: 4px; font-size: 0.75rem; font-weight: 600; color: var(--secondary-text-color); }
      .reached {
        margin-top: 12px; font-size: 1.1rem; font-weight: 800;
        color: var(--primary-text-color);
      }

      /* -- Tiles -- */
      .tiles {
        display: grid;
        grid-template-columns: repeat(var(--cols, 4), minmax(0, 1fr));
        gap: 8px;
      }
      .tile {
        position: relative;
        aspect-ratio: 1 / 1.05;
        border-radius: 22px;
        border: 3px dashed rgba(255,255,255,0.28);
        background: rgba(255,255,255,0.07);
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: 6px; padding: 8px 4px;
        color: var(--secondary-text-color);
        font: inherit; cursor: pointer;
        transition: transform 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;
        -webkit-tap-highlight-color: transparent;
        user-select: none; -webkit-user-select: none;
        touch-action: manipulation;
        min-width: 0;
      }
      /* Older tablet browsers (some Fire OS builds) have no aspect-ratio, which
         would leave a tile only as tall as its label. Keep it tappable. */
      @supports not (aspect-ratio: 1 / 1) {
        .tile { min-height: 96px; }
      }
      .tile:focus-visible { outline: 3px solid var(--primary-color); outline-offset: 2px; }
      .tile:active { transform: scale(0.96); }
      .glyph {
        font-size: 36px; line-height: 1;
        filter: grayscale(1) opacity(0.5);
      }
      .glyph img {
        width: 58px; height: 58px; min-width: 0; min-height: 0;
        object-fit: cover; border-radius: 12px; display: block;
      }
      .label {
        font-size: 12px; font-weight: 700; line-height: 1.2;
        text-align: center; padding: 0 2px;
        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
        overflow: hidden; overflow-wrap: anywhere;
      }
      .tile.done {
        background: var(--grad);
        border: 3px solid rgba(255,255,255,0.95);
        transform: rotate(-2deg) scale(1.03);
        box-shadow: 0 8px 20px rgba(0,0,0,0.35);
        color: #fff;
      }
      .tile.done:active { transform: rotate(-2deg) scale(0.99); }
      .tile.done .glyph { filter: none; animation: pop 0.45s cubic-bezier(.2,1.6,.4,1); }
      .tile.done .label { text-shadow: 0 1px 2px rgba(0,0,0,0.45); }
      .tile.partial {
        border-color: rgba(255,193,7,0.85);
        background: linear-gradient(90deg, rgba(255,193,7,0.32) var(--pct, 0%), rgba(255,255,255,0.07) var(--pct, 0%));
      }
      .tile.partial .glyph { filter: grayscale(0.3) opacity(0.9); }
      .tile.pending { border-style: solid; border-color: rgba(255,193,7,0.85); background: rgba(255,193,7,0.14); }
      .tile.pending .glyph { filter: grayscale(0.2) opacity(0.85); }
      .count, .flag {
        position: absolute; top: 6px; right: 8px;
        font-size: 11px; font-weight: 800; padding: 2px 7px; border-radius: 999px;
        background: rgba(0,0,0,0.35); color: #fff;
      }
      .flag { right: auto; left: 8px; }
      .tile.done .count { background: rgba(255,255,255,0.9); color: #111; }
      .none-today { padding: 22px 16px; text-align: center; }

      /* -- Goal + claim -- */
      .goal-tile {
        display: flex; align-items: center; gap: 14px;
        padding: 16px 18px; width: 50%; box-sizing: border-box;
      }
      .goal-tile ha-icon { --mdc-icon-size: 26px; color: #f1c40f; }
      .goal-tile .gt-title { font-weight: 600; color: var(--primary-text-color); }
      .goal-tile .gt-sub { font-size: 0.8rem; color: var(--secondary-text-color); }
      .claim {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: 8px; padding: 18px 16px; width: 100%; box-sizing: border-box;
        font: inherit; font-weight: 600; color: var(--primary-text-color);
        cursor: pointer; border: none;
      }
      .claim ha-icon { --mdc-icon-size: 44px; }
      .claim[disabled] { cursor: default; opacity: 0.6; }
      .claim.armed { outline: 3px solid #f1c40f; outline-offset: -3px; }

      .error {
        display: flex; flex-direction: column; align-items: center; gap: 8px;
        padding: 28px 16px; text-align: center; color: var(--error-color, #f44336);
      }
      .error ha-icon { --mdc-icon-size: 40px; opacity: 0.6; }

      /* -- Celebration: the TaskMate child card's own pop-up and confetti -- */
      .celebration-overlay {
        position: fixed; inset: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex; align-items: center; justify-content: center;
        z-index: 9999;
        animation: fade-in 0.3s ease;
      }
      .celebration-content {
        background: var(--card-background-color, #fff);
        border-radius: 30px;
        padding: 40px 50px;
        text-align: center;
        animation: pop-in 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        position: relative; overflow: hidden;
        max-width: calc(100vw - 40px); box-sizing: border-box;
      }
      .celebration-content.day { padding: 48px 56px; }
      .celebration-stars {
        font-size: 4rem; margin-bottom: 16px;
        animation: star-bounce 0.6s ease infinite;
      }
      .celebration-title { font-size: 2.5rem; font-weight: bold; color: #9b59b6; margin-bottom: 8px; }
      .celebration-content.day .celebration-title { font-size: 2.8rem; }
      .celebration-message { font-size: 1.3rem; color: var(--secondary-text-color); margin-bottom: 16px; }
      .celebration-points {
        font-size: 1.8rem; font-weight: bold; color: #e67e22;
        display: flex; align-items: center; justify-content: center; gap: 8px;
      }
      .celebration-points ha-icon { --mdc-icon-size: 28px; color: #f1c40f; }
      .confetti-container {
        position: fixed; inset: 0;
        pointer-events: none; z-index: 10000; overflow: hidden;
      }
      .confetti { position: absolute; top: 0; width: 10px; height: 10px; animation: confetti-fall 3s linear forwards; }
      @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
      @keyframes pop-in { from { transform: scale(0); opacity: 0; } to { transform: scale(1); opacity: 1; } }
      @keyframes star-bounce {
        0%, 100% { transform: scale(1) rotate(0deg); }
        50% { transform: scale(1.2) rotate(10deg); }
      }
      @keyframes confetti-fall {
        0% { transform: translateY(-100px) rotate(0deg); opacity: 1; }
        100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
      }
      @media (max-width: 420px) {
        .celebration-content { padding: 28px 24px; }
        .celebration-title { font-size: 1.9rem; }
      }

      @keyframes pop {
        0% { transform: scale(.4) rotate(-20deg); }
        70% { transform: scale(1.35) rotate(6deg); }
        100% { transform: scale(1) rotate(0); }
      }
      @media (prefers-reduced-motion: reduce) {
        .tile, .tile.done .glyph { animation: none; transition: none; }
      }
      @media (max-width: 420px) {
        .face { width: 76px; height: 76px; min-width: 76px; }
        .face ha-icon { --mdc-icon-size: 42px; }
        .stickers { font-size: 21px; }
        .glyph { font-size: 30px; }
        .goal-tile { width: 100%; }
      }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  // -- Data --------------------------------------------------------------------

  _attrs() {
    const entity = this.hass && this.hass.states[this.config.entity];
    if (!entity) return null;
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || entity.attributes || {};
  }

  _children(attrs) {
    const all = attrs.children || [];
    const wanted = this.config.child_id;
    if (!wanted) return all;
    return all.filter(c => c.id === wanted || c.name === wanted);
  }

  /** Per-child cost when the reward has one, else its list price. */
  _cost(reward, child) {
    const perChild = reward.calculated_costs || {};
    const value = perChild[child.id] !== undefined ? perChild[child.id] : reward.cost;
    return Math.max(0, Number(value) || 0);
  }

  /**
   * The reward being saved up for.
   *
   * A configured reward wins. Otherwise the cheapest reward the child cannot
   * afford yet, so there is always something to aim at; if they can afford
   * everything, the dearest, so the chart reads full.
   */
  _reward(rewards, child) {
    const list = (rewards || []).filter(r => {
      const assigned = r.assigned_to || [];
      return assigned.length === 0 || assigned.includes(child.id);
    });
    if (this.config.reward_id) return list.find(r => r.id === this.config.reward_id) || null;
    const claimable = list.filter(r => r.is_available !== false);
    if (!claimable.length) return null;
    const points = Math.max(0, Number(child.points) || 0);
    const ahead = claimable.filter(r => this._cost(r, child) > points);
    return ahead.length
      ? ahead.reduce((a, b) => (this._cost(b, child) < this._cost(a, child) ? b : a))
      : claimable.reduce((a, b) => (this._cost(b, child) > this._cost(a, child) ? b : a));
  }

  /**
   * Today's chores for one child, each with its completion state.
   *
   * Mirrors the TaskMate child card with every period shown at once — the
   * sticker chart is the whole day on one screen:
   *   - enabled, not disabled for this child, assigned to them (or everyone)
   *   - rotation chores only for today's active child; first-come for the pool
   *   - specific-days chores only on their days (the backend leaves that to cards)
   *   - the backend's availability matrix for everything else (vacation,
   *     recurrence windows, visibility and weather gates)
   * A chore already done today stays on the chart even when the matrix has
   * since switched it off, so a finished sticker never vanishes.
   */
  // -- Past-day mode (`config.date`, used by the admin panel) --------------------

  /** The past day being shown, as a local Date at midday, or null for today. */
  _pastDay() {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(this.config?.date || "");
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), 12) : null;
  }

  /** The completions the tiles are drawn from: the chosen day's, or today's. */
  _completions(attrs) {
    const list = this._pastDay() ? (this.dayCompletions || []) : (attrs.todays_completions || []);
    return list.filter(c => !c.bonus_subtask_id);
  }

  _todaysChores(child, attrs) {
    const childId = String(child.id);
    const past = this._pastDay();
    const todayDow = past
      ? past.toLocaleDateString("en-US", { weekday: "long" }).toLowerCase()
      : attrs.today_day_of_week || new Date().toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();
    // The availability matrix describes today only, so a past day skips it.
    const availability = past ? {} : (attrs.chore_availability || {});
    const completions = this._completions(attrs);
    const order = (child.chore_order || []).map(String);

    const rows = [];
    for (const chore of attrs.chores || []) {
      if (chore.enabled === false) continue;
      if ((chore.disabled_for || []).map(String).includes(childId)) continue;
      const assigned = (Array.isArray(chore.assigned_to) ? chore.assigned_to : []).map(String);
      if (assigned.length && !assigned.includes(childId)) continue;

      const mode = chore.assignment_mode || "everyone";
      // Whose turn a rotation chore was can't be reconstructed for a past
      // day, and TaskMate refuses to log one, so it isn't offered.
      if (past && mode !== "everyone") continue;
      if (mode !== "everyone" && mode !== "first_come") {
        const active = chore.assignment_current_child_id ? String(chore.assignment_current_child_id) : "";
        if (active !== childId) continue;
      }

      if (chore.schedule_mode === "specific_days") {
        const days = Array.isArray(chore.due_days) ? chore.due_days : [];
        if (days.length && !days.includes(todayDow)) continue;
      }

      const mine = this._mine(childId, chore, completions);
      const perChild = availability[chore.id];
      if (perChild && perChild[childId] === false && mine.length === 0) continue;

      const limit = mode === "first_come" ? 1 : Math.max(1, Number(chore.daily_limit) || 1);
      const approved = mine.filter(c => c.approved).length;

      const key = `${childId}:${chore.id}`;
      const opt = this._optimistic[key];
      const extra = opt && mine.length < opt.base + opt.count && Date.now() - opt.at < OPTIMISTIC_MS
        ? opt.base + opt.count - mine.length : 0;
      const total = Math.min(limit, mine.length + extra);

      let state = "todo";
      if (approved >= limit) state = "done";
      else if (total >= limit) {
        // Optimistic ticks only count as done where no grown-up has to approve;
        // TaskMate omits requires_approval from the payload when it is true.
        state = extra > 0 && approved + extra >= limit && (past || chore.requires_approval === false) ? "done" : "pending";
      }
      else if (total > 0) state = "partial";

      rows.push({ chore, key, limit, total, approved, state, mine });
    }

    const pos = (r) => {
      const i = order.indexOf(String(r.chore.id));
      return i === -1 ? Number.MAX_SAFE_INTEGER : i;
    };
    rows.sort((a, b) =>
      pos(a) - pos(b)
      || (PERIOD_ORDER[a.chore.time_category] ?? 9) - (PERIOD_ORDER[b.chore.time_category] ?? 9)
      || String(a.chore.name || "").localeCompare(String(b.chore.name || "")));
    return rows;
  }

  _glyph(chore) {
    const name = String(chore.name || "").trim();
    const lead = name.match(LEADING_EMOJI);
    const label = lead ? name.slice(lead[0].length) || name : name;
    if (chore.image_url) {
      return { label, glyph: html`<img src="${chore.image_url}" alt="" loading="lazy">` };
    }
    if (lead) return { label, glyph: lead[1] };
    const n = name.toLowerCase();
    for (const [re, e] of CHORE_EMOJI) if (re.test(n)) return { label, glyph: e };
    return { label, glyph: "⭐" };
  }

  // -- Actions -----------------------------------------------------------------

  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message }, bubbles: true, composed: true,
    }));
  }

  async _complete(child, row) {
    if (row.total >= row.limit || this._busy.has(row.key)) return;
    const pastDate = this._pastDay() ? this.config.date : "";
    // A grown-up logging a past day is the reviewer, so no photo is needed.
    if (row.chore.require_photo && !pastDate) {
      this._toast(this._t("sticker_chart.needs_photo"));
      return;
    }
    this._busy.add(row.key);
    const lastOfDay = this._finishesDay(child, row);
    const prev = this._optimistic[row.key];
    this._optimistic = {
      ...this._optimistic,
      [row.key]: {
        childId: child.id, choreId: row.chore.id, base: row.mine.length,
        count: (prev && Date.now() - prev.at < OPTIMISTIC_MS ? prev.count : 0) + 1, at: Date.now(),
      },
    };
    try {
      const button = !pastDate && window.__taskmate_find_button
        && window.__taskmate_find_button(this.hass, child.id, "complete", row.chore.id);
      if (pastDate) {
        await this.hass.callService("taskmate", "complete_chore", {
          chore_id: row.chore.id, child_id: child.id, as_parent: true, completed_date: pastDate,
        });
        this._dayChanged();
      } else if (button) {
        await this.hass.callService("button", "press", { entity_id: button });
      } else {
        await this.hass.callService("taskmate", "complete_chore", {
          chore_id: row.chore.id, child_id: child.id,
        });
      }
      this._playSound(row.chore.completion_sound || this.config.default_sound || "coin");
      this._celebrate(child, row, lastOfDay);
    } catch (err) {
      const next = { ...this._optimistic };
      delete next[row.key];
      this._optimistic = next;
      this._failed(err, child);
    } finally {
      this._busy.delete(row.key);
    }
  }

  /**
   * Explain a refusal rather than showing HA's raw error.
   *
   * A child in TaskMate can be linked to one HA user, and then only that user
   * (or a grown-up) may tick their jobs. A shared family tablet signed in as
   * somebody else gets "Unauthorized" from the button entity / service, which
   * means nothing to whoever is standing at the fridge.
   */
  _failed(err, child) {
    const msg = String(err?.message || err || "");
    this._toast(/unauthori|not authorized|admin|permission|forbidden/i.test(msg)
      ? this._t("sticker_chart.not_allowed", { name: child?.name || "" })
      : this._t("sticker_chart.complete_failed", { error: msg }));
  }

  async _undo(row) {
    if (this.config.allow_undo === false) return;
    const own = row.mine.filter(c => c.child_id !== "__parent__" && c.completion_id);
    const latest = own[own.length - 1];
    if (!latest) return;
    if (this._optimistic[row.key]) {
      const next = { ...this._optimistic };
      delete next[row.key];
      this._optimistic = next;
    }
    try {
      await this.hass.callService("taskmate", "reject_chore", { completion_id: latest.completion_id });
      if (this._pastDay()) this._dayChanged();
      this._playSound(this.config.undo_sound || "undo");
      this._toast(this._t("sticker_chart.undone"));
    } catch (err) {
      const msg = String(err?.message || err || "");
      this._toast(/admin|parent|unauthori|permission/i.test(msg)
        ? this._t("sticker_chart.undo_denied")
        : this._t("sticker_chart.complete_failed", { error: msg }));
    }
  }

  async _claim(child, reward) {
    if (this._confirming !== child.id) {
      this._confirming = child.id;
      clearTimeout(this._confirmTimer);
      this._confirmTimer = setTimeout(() => { this._confirming = ""; }, CONFIRM_MS);
      return;
    }
    this._confirming = "";
    clearTimeout(this._confirmTimer);
    try {
      const button = window.__taskmate_find_button
        && window.__taskmate_find_button(this.hass, child.id, "claim", reward.id);
      if (button) {
        await this.hass.callService("button", "press", { entity_id: button });
      } else {
        await this.hass.callService("taskmate", "claim_reward", { reward_id: reward.id, child_id: child.id });
      }
      this._toast(this._t("sticker_chart.claimed", { reward: reward.name, name: child.name }));
    } catch (err) {
      this._failed(err, child);
    }
  }

  // Press-and-hold means undo; a short press means complete. Pointer events
  // cover mouse and touch alike, and the context menu a long touch would
  // otherwise raise is suppressed so the hold reads as one gesture.
  _down(row) {
    this._held = false;
    clearTimeout(this._holdTimer);
    this._holdTimer = setTimeout(() => {
      this._held = true;
      this._undo(row);
    }, HOLD_MS);
  }

  _up(child, row) {
    clearTimeout(this._holdTimer);
    if (this._held) { this._held = false; return; }
    this._complete(child, row);
  }

  _cancel() { clearTimeout(this._holdTimer); }

  /** A past day's completions changed: the host re-fetches `dayCompletions`. */
  _dayChanged() {
    this.dispatchEvent(new CustomEvent("taskmate-day-changed", {
      detail: { date: this.config.date }, bubbles: true, composed: true,
    }));
  }

  /** TaskMate's shared sound engine, the same one the child card plays through. */
  _playSound(name) {
    const engine = window.__taskmate_sounds;
    if (!engine || this.config.sound === false) return;
    engine.play(name, (this._attrs() || {}).custom_sounds || []);
  }

  /**
   * Will this tap finish every job on today's chart?
   *
   * Only when it completes this chore outright — no approval to wait for —
   * and every other job is already done. Judged before the tap lands, from
   * the same rows the tiles are drawn from.
   */
  _finishesDay(child, row) {
    if ((!this._pastDay() && row.chore.requires_approval !== false) || row.total + 1 < row.limit) return false;
    const rows = this._todaysChores(child, this._attrs() || {});
    return rows.length > 0 && rows.every(r => r.key === row.key || r.state === "done");
  }

  /**
   * The child card's completion moment: a dimmed-screen pop-up with the
   * points just earned and falling confetti. Finishing the whole day gets a
   * bigger version, the way the old sticker chart's "all done" pop-up did.
   */
  _celebrate(child, row, day) {
    if (this.config.celebrate === false) return;
    const latest = row.mine[row.mine.length - 1];
    const points = latest && latest.points != null ? latest.points : (row.chore.points || 0);
    this._celebrating = { day, name: child.name, points };
    this._confetti = Array.from({ length: day ? 140 : 50 }, () => ({
      x: Math.random() * 100,
      delay: Math.random() * (day ? 1.2 : 0.5),
      size: Math.random() * 8 + 6,
      round: Math.random() > 0.5,
    }));
    clearTimeout(this._celebrateTimer);
    clearTimeout(this._confettiTimer);
    this._celebrateTimer = setTimeout(() => { this._celebrating = null; }, day ? 6000 : 2500);
    this._confettiTimer = setTimeout(() => { this._confetti = []; }, day ? 5000 : 3500);
  }

  _renderCelebration(attrs) {
    const c = this._celebrating;
    const close = () => { this._celebrating = null; };
    return html`
      <div class="celebration-overlay" @click=${close}>
        <div class="celebration-content ${c.day ? "day" : ""}" @click=${(e) => e.stopPropagation()}>
          ${c.day ? html`
            <div class="celebration-stars">🏆🎉⭐🎉🏆</div>
            <div class="celebration-title">${this._t("sticker_chart.all_done", { name: c.name })}</div>
            <div class="celebration-message">${this._t("sticker_chart.day_done_message")}</div>
          ` : html`
            <div class="celebration-stars">&#127775;&#127775;&#127775;</div>
            <div class="celebration-title">${this._t("child.celebration_title")}</div>
            <div class="celebration-message">${this._t("child.celebration_message")}</div>
          `}
          <div class="celebration-points">
            <ha-icon icon="${attrs.points_icon || "mdi:star"}"></ha-icon>
            +${c.points}
          </div>
        </div>
      </div>`;
  }

  _renderConfetti() {
    const colors = ["#ff6b9d", "#9b59b6", "#3498db", "#2ecc71", "#f1c40f", "#e67e22"];
    return html`
      <div class="confetti-container">
        ${this._confetti.map((p, i) => html`
          <div class="confetti"
               style="left:${p.x}%;animation-delay:${p.delay}s;background:${colors[i % colors.length]};border-radius:${p.round ? "50%" : "0"};width:${p.size}px;height:${p.size}px"></div>`)}
      </div>`;
  }

  _key(e, child, row) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      this._complete(child, row);
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this._holdTimer);
    clearTimeout(this._confirmTimer);
    clearTimeout(this._celebrateTimer);
    clearTimeout(this._confettiTimer);
  }

  // -- Render ------------------------------------------------------------------

  _face(child) {
    const face = window.__taskmate_child_visual(child);
    if (face.kind === "image") return html`<img class="tm-face-img" src="${face.url}" alt="" loading="lazy">`;
    return html`<ha-icon icon="${face.kind === "icon" ? face.icon : "mdi:account-circle"}"></ha-icon>`;
  }

  _renderTile(child, row, index) {
    const { label, glyph } = this._glyph(row.chore);
    const grad = GRADIENTS[index % GRADIENTS.length];
    const pct = Math.round((100 * Math.min(row.total, row.limit)) / row.limit);
    const stateLabel = this._t(`sticker_chart.state.${row.state}`);
    return html`
      <button class="tile ${row.state}"
              style="--grad:${grad};--pct:${pct}%"
              aria-label="${label}: ${stateLabel}"
              @pointerdown=${() => this._down(row)}
              @pointerup=${() => this._up(child, row)}
              @pointerleave=${() => this._cancel()}
              @pointercancel=${() => this._cancel()}
              @contextmenu=${(e) => e.preventDefault()}
              @keydown=${(e) => this._key(e, child, row)}>
        ${row.limit > 1 ? html`<span class="count">${Math.min(row.total, row.limit)}/${row.limit}</span>` : ""}
        ${row.chore.require_photo && row.state === "todo" ? html`<span class="flag">📷</span>` : ""}
        ${row.state === "pending" ? html`<span class="flag">⏳</span>` : ""}
        <span class="glyph">${glyph}</span>
        <span class="label">${label}</span>
      </button>`;
  }

  // One block per star up to MAX_BLOCKS. Past that each block stands for
  // several stars, so a big week looks the same as a small one (a separate
  // plain bar made two children's charts look unlike each other). A block
  // lights only once all its stars are earned, and the last one when the
  // goal is reached, so the row is never fuller than the count above it.
  _renderBlocks(points, goal, unit) {
    const per = Math.max(1, Math.ceil(goal / MAX_BLOCKS));
    const total = Math.ceil(goal / per);
    const on = points >= goal ? total : Math.floor(Math.max(0, points) / per);
    return html`<div class="blocks" role="img" aria-label="${Math.min(points, goal)} / ${goal}">${
      Array.from({ length: total }, (_, i) => html`<i class="${i < on ? "on" : ""}"></i>`)}</div>
      ${per > 1 ? html`<div class="blocks-key">${this._t("sticker_chart.block_key", { count: per, unit })}</div>` : ""}`;
  }

  _renderChild(child, index, attrs) {
    const unit = attrs.points_name || this._t("common.stars");
    const points = Math.max(0, Number(child.points) || 0);
    const reward = this._reward(attrs.rewards, child);
    const goal = reward ? this._cost(reward, child) : 0;
    const reached = goal > 0 && points >= goal;

    // What the stickers and blocks count towards: the reward's cost against
    // the child's balance, or this week's jobs — every star on offer since
    // Monday against the stars earned since then, so extra stars can't pile
    // up unseen past the goal.
    const weekly = this.config.goal === "week";
    const target = weekly ? Math.max(0, Number(child.week_points_available) || 0) : goal;
    const progress = weekly ? Math.max(0, Number(child.week_points_earned) || 0) : points;
    const earned = target > 0 ? Math.min(progress, target) : progress;
    const full = target > 0 && progress >= target;
    const shown = Math.min(earned, MAX_STICKERS);

    const rows = this._todaysChores(child, attrs);
    const done = rows.filter(r => r.state === "done").length;
    const allDone = rows.length > 0 && done === rows.length;

    const tone = `var(--tmd-c${(index % 6) + 1}, ${index % 2 ? "#e84393" : "#3498db"})`;
    const title = this.config.title || this._t("sticker_chart.default_title", { name: child.name });

    const pendingClaim = reward && (attrs.pending_reward_claims || [])
      .some(c => c.child_id === child.id && c.reward_id === reward.id);

    // A past day (the admin panel's "Log a past job"): just that day's jobs,
    // done and not done, ticked the same way. The running totals and the
    // reward belong to today, so they are left off.
    const past = this._pastDay();
    if (past) {
      const day = past.toLocaleDateString(this.hass?.locale?.language || this.hass?.language || undefined,
        { weekday: "long", day: "numeric", month: "short" });
      return html`
        <div class="col" style="--tone:${tone}">
          <div class="heading">
            <ha-icon icon="mdi:calendar-check"></ha-icon>
            <span class="title">${child.name}</span>
            <span class="score"><ha-icon icon="${attrs.points_icon || "mdi:star"}"></ha-icon>${points}</span>
          </div>
          <div class="panel summary">
            <div class="today">
              ${this._t("sticker_chart.day_count", { day, done, total: rows.length })}
              ${allDone ? html` 🏆` : ""}
            </div>
          </div>
          ${rows.length ? html`
            <div class="tiles" style="--cols:${Math.max(2, Math.min(6, Number(this.config.columns) || 4))}">
              ${rows.map((row, i) => this._renderTile(child, row, i))}
            </div>` : html`
            <div class="panel none-today muted">${this._t("sticker_chart.no_jobs_day", { day })}</div>`}
        </div>`;
    }

    return html`
      <div class="col" style="--tone:${tone}">
        <div class="heading">
          <ha-icon icon="mdi:star-face"></ha-icon>
          <span class="title">${title}</span>
          <span class="score"><ha-icon icon="${attrs.points_icon || "mdi:star"}"></ha-icon>${points}</span>
        </div>

        <div class="panel summary">
          <div class="top-row">
            <div class="top-main">
              ${this.config.show_today === false ? "" : html`
                <div class="today">
                  ${this._t("sticker_chart.today", { done, total: rows.length })}
                  ${allDone ? html` 🏆 ${this._t("sticker_chart.all_done", { name: child.name })}` : ""}
                </div>`}
              <div class="stickers" role="img"
                   aria-label="${this._t("sticker_chart.stickers_alt", { count: earned, points: unit })}">
                ${earned === 0
                  ? html`<span class="stickers-none">${this._t("sticker_chart.no_stickers")}</span>`
                  : html`${Array.from({ length: shown }, (_, i) => STICKERS[i % STICKERS.length]).join("")}${
                      earned > shown ? html`<span class="overflow">+${earned - shown}</span>` : ""}`}
              </div>
            </div>
            <div class="face">${this._face(child)}</div>
          </div>

          ${weekly ? (target > 0 ? html`
            <div class="goal-line">${this._t("sticker_chart.week_goal", { points: earned, goal: target, unit })}</div>
            ${this._renderBlocks(progress, target, unit)}
            ${full ? html`<div class="reached">🌟 ${this._t("sticker_chart.week_perfect")} 🌟</div>` : ""}
          ` : "") : goal > 0 ? html`
            <div class="goal-line">${this._t("sticker_chart.goal", { points: earned, goal, unit })}</div>
            ${this._renderBlocks(points, goal, unit)}
            ${reached ? html`<div class="reached">🎉 ${this._t("sticker_chart.goal_reached")} 🎉</div>` : ""}
          ` : html`<div class="goal-line muted">${this._t("sticker_chart.no_reward")}</div>`}
        </div>

        ${rows.length ? html`
          <div class="tiles" style="--cols:${Math.max(2, Math.min(6, Number(this.config.columns) || 4))}">
            ${rows.map((row, i) => this._renderTile(child, row, i))}
          </div>` : html`
          <div class="panel none-today muted">${this._t("sticker_chart.no_jobs_today")}</div>`}

        ${reward ? html`
          <div class="panel goal-tile">
            <ha-icon icon="mdi:trophy"></ha-icon>
            <div>
              <div class="gt-title">${this._t("sticker_chart.goal_tile")}</div>
              <div class="gt-sub">${reward.name} · ${goal} ${unit}</div>
            </div>
          </div>

          ${this.config.show_claim === false ? "" : html`
            <button class="panel claim ${this._confirming === child.id ? "armed" : ""}"
                    ?disabled=${!reached || pendingClaim}
                    @click=${() => this._claim(child, reward)}>
              <ha-icon icon="mdi:gift"></ha-icon>
              <span>${pendingClaim
                ? this._t("sticker_chart.claim_pending")
                : !reached
                  ? this._t("sticker_chart.claim_short", { count: goal - points, unit })
                  : this._confirming === child.id
                    ? this._t("sticker_chart.claim_confirm", { reward: reward.name })
                    : html`🎁 ${this._t("sticker_chart.claim", { reward: reward.name })}`}</span>
            </button>`}
        ` : ""}
      </div>`;
  }

  render() {
    if (!this.hass || !this.config) return html``;
    if (window.__taskmate_design) {
      window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity);
    }
    const attrs = this._attrs();
    if (!attrs) {
      return html`<ha-card><div class="panel error">
        <ha-icon icon="mdi:alert-circle"></ha-icon>
        <div>${this._t("common.entity_not_found", { entity: this.config.entity })}</div>
      </div></ha-card>`;
    }
    const children = this._children(attrs);
    if (!children.length) {
      return html`<ha-card><div class="panel error">
        <ha-icon icon="mdi:account-question"></ha-icon>
        <div>${this._t("sticker_chart.no_child")}</div>
      </div></ha-card>`;
    }
    return html`
      <ha-card>
        <div class="cols">
          ${children.map((child, i) => this._renderChild(child, i, attrs))}
        </div>
        ${this._celebrating ? this._renderCelebration(attrs) : ""}
        ${this._confetti.length ? this._renderConfetti() : ""}
      </ha-card>`;
  }
}

class TaskMateStickerChartCardEditor extends LitElement {
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
    `;
  }

  setConfig(config) { this.config = config; }

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || (this.config?.entity ? this.hass?.states?.[this.config.entity]?.attributes : null)
      || {};
  }

  _buildSchema() {
    const attrs = this._attrs();
    const children = attrs.children || [];
    const rewards = attrs.rewards || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      {
        name: "child_id",
        selector: {
          select: {
            options: [
              { value: "", label: this._t("sticker_chart.editor.child_all") },
              ...children.map(c => ({ value: c.id, label: c.name })),
            ],
            mode: "dropdown",
          },
        },
      },
      {
        name: "reward_id",
        selector: {
          select: {
            options: [
              { value: "", label: this._t("sticker_chart.editor.reward_auto") },
              ...rewards.map(r => ({ value: r.id, label: `${r.name} (${r.cost})` })),
            ],
            mode: "dropdown",
          },
        },
      },
      {
        name: "goal",
        selector: {
          select: {
            options: [
              { value: "reward", label: this._t("sticker_chart.editor.goal_reward") },
              { value: "week", label: this._t("sticker_chart.editor.goal_week") },
            ],
            mode: "dropdown",
          },
        },
      },
      { name: "title", selector: { text: {} } },
      { name: "columns", selector: { number: { min: 2, max: 6, mode: "slider" } } },
      { name: "show_today", selector: { boolean: {} } },
      { name: "show_claim", selector: { boolean: {} } },
      { name: "allow_undo", selector: { boolean: {} } },
      { name: "sound", selector: { boolean: {} } },
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
      child_id: this._t("sticker_chart.editor.child"),
      reward_id: this._t("sticker_chart.editor.reward"),
      goal: this._t("sticker_chart.editor.goal"),
      title: this._t("sticker_chart.editor.title"),
      columns: this._t("sticker_chart.editor.columns"),
      show_today: this._t("sticker_chart.editor.show_today"),
      show_claim: this._t("sticker_chart.editor.show_claim"),
      allow_undo: this._t("sticker_chart.editor.allow_undo"),
      sound: this._t("sticker_chart.editor.sound"),
      card_design: this._t("common.design.field_label"),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t("common.editor.overview_entity_helper"),
      reward_id: this._t("sticker_chart.editor.reward_helper"),
      goal: this._t("sticker_chart.editor.goal_helper"),
      title: this._t("sticker_chart.editor.title_helper"),
      show_today: this._t("sticker_chart.editor.show_today_helper"),
      show_claim: this._t("sticker_chart.editor.show_claim_helper"),
      allow_undo: this._t("sticker_chart.editor.allow_undo_helper"),
    };
    return helpers[entry.name] ?? "";
  };

  // Booleans that default to true are only written when switched off, and the
  // default column count is omitted, so a card's YAML stays minimal.
  _valueChanged(e) {
    e.stopPropagation();
    const defaultsOn = new Set(["show_today", "show_claim", "allow_undo", "sound"]);
    const newConfig = {};
    for (const [key, value] of Object.entries(e.detail.value)) {
      if (value === "" || value === null || value === undefined) continue;
      if (key === "card_design" && value === "global") continue;
      if (key === "goal" && value === "reward") continue;
      if (defaultsOn.has(key) && value === true) continue;
      if (key === "columns" && Number(value) === 4) continue;
      newConfig[key] = value;
    }
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  render() {
    if (!this.hass || !this.config) return html``;
    const data = { goal: "reward", show_today: true, show_claim: true, allow_undo: true, sound: true, columns: 4, ...this.config };
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._buildSchema()}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._valueChanged}
      ></ha-form>
    `;
  }
}

// A version bump can briefly leave two copies of this module in one page (the
// old ?v= URL and the new one). Defining a name twice throws, which would take
// the editor down with the card, so each define is guarded.
if (!customElements.get("taskmate-sticker-chart-card")) {
  customElements.define("taskmate-sticker-chart-card", TaskMateStickerChartCard);
}
if (!customElements.get("taskmate-sticker-chart-card-editor")) {
  customElements.define("taskmate-sticker-chart-card-editor", TaskMateStickerChartCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some(c => c.type === "taskmate-sticker-chart-card")) window.customCards.push({
  type: "taskmate-sticker-chart-card",
  name: "TaskMate Sticker Chart",
  description: "The kids' sticker chart: today's chores as stickers to tap, stars filling towards a reward",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-sticker-chart-card", "overview"),
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-sticker-chart-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE STICKER CHART CARD %c v" + _tmVersion + " ",
  "background:#8e44ad;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
