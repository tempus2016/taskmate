/**
 * TaskMate i18n Module
 * Lightweight translation loader for TaskMate custom cards.
 *
 * Usage in a card:
 *   // loaded via window.__taskmate_localize (registered globally)
 *
 *   localize(this.hass, 'common.today')           → "Today"
 *   localize(this.hass, 'common.points_received',
 *     { count: 5, name: 'Stars' })                → "5 Stars received"
 *
 * Strings are split into bundles (cards, editor, panel), generated from
 * locales/<lang>.json by scripts/split_locales.py into locales/<lang>/<bundle>.json.
 * A lookup works out the key's bundle from its name and loads just that bundle
 * for the user's language, so a dashboard never downloads the admin panel's or
 * the card editors' strings. Each bundle already carries the fallback wording
 * (pt-BR → pt → en-GB), so one file per bundle is all a page needs.
 *
 * Language resolution: pt-BR → pt-BR; de-CH → de; an unshipped language → en-GB.
 */

const _BASE = '/taskmate/locales';

// BEGIN locale-bundles — scripts/split_locales.py reads this block: keep it valid JSON.
const _BUNDLES = {
  "langs": ["da", "de", "en", "en-GB", "fr", "nb", "nl", "nn", "pl", "pt", "pt-BR"],
  "fallback": "en-GB",
  "bundles": ["cards", "editor", "panel"],
  "default": "cards",
  "rules": [
    ["contains", ".editor.", "editor"],
    ["prefix", "notify.tour_", "cards"],
    ["prefix", "panel.", "panel"],
    ["prefix", "wizard.", "panel"],
    ["prefix", "library.", "panel"],
    ["prefix", "planner.", "panel"],
    ["prefix", "notify.", "panel"],
    ["prefix", "notification.", "panel"]
  ]
};
// END locale-bundles

const _FALLBACK = _BUNDLES.fallback;

// Cache-bust with the integration version this module was loaded with (the
// ?v= on its own URL), so the browser can keep a bundle until the next update.
// Without one (a hand-added resource), never cache, as before.
const _VERSION = (() => {
  try {
    return new URL(import.meta.url).searchParams.get('v') || String(Date.now());
  } catch {
    return String(Date.now());
  }
})();

const _cache = {};          // "lang/bundle" → { key: value }  (null = tried and failed)
const _pending = {};        // "lang/bundle" → Promise
let _lastLang = null;       // the language of the most recent lookup

/** Which bundle a key lives in — the first matching rule wins. */
function _bundleFor(key) {
  for (const [kind, needle, bundle] of _BUNDLES.rules) {
    if (kind === 'prefix' ? key.startsWith(needle) : key.includes(needle)) return bundle;
  }
  return _BUNDLES.default;
}

/**
 * The shipped language to load for a Home Assistant language code:
 * "pt-BR" → "pt-BR", "de-CH" → "de", "es" → "en-GB".
 */
function _resolveLang(lang) {
  if (!lang) return _FALLBACK;
  if (_BUNDLES.langs.includes(lang)) return lang;
  const base = String(lang).split('-')[0];
  return _BUNDLES.langs.includes(base) ? base : _FALLBACK;
}

function _langOf(hass) {
  return _resolveLang((hass && hass.language) || _lastLang || _FALLBACK);
}

/**
 * Load one bundle for one language. Returns the cached result if available.
 * Caches failures (as null) so we don't retry on every render; a failed
 * language falls back to the same bundle in en-GB.
 */
async function _loadBundle(lang, bundle) {
  const id = `${lang}/${bundle}`;
  if (id in _cache) return _cache[id];
  if (_pending[id]) return _pending[id];

  _pending[id] = (async () => {
    try {
      const resp = await fetch(`${_BASE}/${lang}/${bundle}.json?v=${encodeURIComponent(_VERSION)}`);
      if (!resp.ok) throw new Error(resp.status);
      const data = await resp.json();
      _cache[id] = data;
      _refreshTaskMateCards();
      return data;
    } catch {
      _cache[id] = null;
      if (lang !== _FALLBACK) return _loadBundle(_FALLBACK, bundle);
      return null;
    } finally {
      delete _pending[id];
    }
  })();

  return _pending[id];
}

/**
 * Synchronous lookup — returns the translated string or the fallback.
 * Triggers async load in the background if the bundle isn't cached yet.
 *
 * @param {object} hass - Home Assistant hass object (for hass.language)
 * @param {string} key  - Dot-notation key, e.g. 'common.today'
 * @param {object} [params] - Replacement params, e.g. { count: 5 }
 * @returns {string}
 */
function localize(hass, key, params) {
  if (hass && hass.language) _lastLang = hass.language;
  const lang = _langOf(hass);
  const bundle = _bundleFor(String(key));
  const id = `${lang}/${bundle}`;

  let str = undefined;
  if (!(id in _cache)) {
    _loadBundle(lang, bundle);
  } else {
    // A language whose bundle failed to load reads the en-GB copy instead.
    const data = _cache[id] || _cache[`${_FALLBACK}/${bundle}`];
    if (data && typeof data[key] === 'string') str = data[key];
  }
  if (str === undefined) {
    // Missing translation: only echo the key back when it's a plain identifier.
    // A key carrying HTML-significant characters is not a real key — it's caller
    // data concatenated into the lookup (e.g. `panel.assign_${value}_short`) —
    // so refuse to reflect it, since some call sites render _t() output as HTML.
    str = /^[\w.-]+$/.test(key) ? key : "";
  }

  // Replace {placeholder} tokens. Use a replacer function so a value containing
  // "$&", "$1" etc. is inserted literally rather than interpreted as a
  // replacement pattern.
  if (params && typeof str === 'string') {
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), () => String(v));
    }
  }

  return str;
}

/**
 * Pre-load bundles so translations are ready before first render.
 * Cards don't need to call this — a lookup loads its own bundle — but the card
 * editors and the admin panel use it to fetch their bundle up front.
 *
 * @param {object} [hass] - Home Assistant hass object; without one, the
 *   language of the most recent lookup is used.
 * @param {string[]} [bundles] - which bundles, default ["cards"].
 * @returns {Promise<void>}
 */
async function loadTranslations(hass, bundles = [_BUNDLES.default]) {
  if (hass && hass.language) _lastLang = hass.language;
  const lang = _langOf(hass);
  await Promise.all(bundles.map(b => _loadBundle(lang, b)));
}

// Walk the DOM across shadow roots and trigger a re-render on TaskMate cards.
// Called after a bundle loads so cards pick up the new translations. The admin
// panel is not a Lit element, so it listens for the window event instead.
function _refreshTaskMateCards() {
  try {
    window.dispatchEvent(new CustomEvent('taskmate-locale-loaded'));
  } catch (_e) { /* ignore */ }
  const stack = [document];
  while (stack.length) {
    const node = stack.pop();
    if (!node) continue;
    if (node.tagName && node.tagName.startsWith('TASKMATE-')) {
      if (typeof node.requestUpdate === 'function') {
        try { node.requestUpdate(); } catch (_e) { /* ignore */ }
      }
    }
    if (node.shadowRoot) stack.push(node.shadowRoot);
    const children = node.children;
    if (children) {
      for (let i = 0; i < children.length; i++) stack.push(children[i]);
    }
  }
}

const _DAY_KEYS = [
  'weekly.day_mon', 'weekly.day_tue', 'weekly.day_wed', 'weekly.day_thu',
  'weekly.day_fri', 'weekly.day_sat', 'weekly.day_sun',
];

/**
 * Human summary of a reward's time lock (#857), e.g. "Fri, Sat · 18:00–21:00".
 * Returns "" when nothing is restricted, so callers can skip the badge.
 *
 * @param {object} lock - { days: number[], from: string, until: string }
 * @param {function} t - the caller's translate function (key, params) => string
 */
function timeLockLabel(lock, t) {
  if (!lock) return '';
  const days = (lock.days || []).map(Number).filter(n => Number.isInteger(n) && n >= 0 && n <= 6).sort((a, b) => a - b);
  const parts = [];
  // All seven days selected is the same as no day restriction — don't spell it out.
  if (days.length && days.length < 7) parts.push(days.map(d => t(_DAY_KEYS[d])).join(', '));
  const from = lock.from || '';
  const until = lock.until || '';
  if (from && until && from !== until) parts.push(`${from}–${until}`);
  return parts.join(' · ');
}

/**
 * A badge's name in the user's language. Built-in badges reach the cards from
 * the sensors with their English names ("First Reward", "1000 Points"); the
 * translations live under badge.name_<suffix>. A parent's own badges keep the
 * name they were given. Takes either id spelling (badge_id on a child's badges
 * sensor, id elsewhere).
 */
function badgeName(hass, badge, pointsName) {
  if (!badge) return '';
  const raw = badge.badge_id != null ? badge.badge_id : badge.id;
  const id = raw != null ? String(raw) : '';
  const name = badge.name || '';
  if (!id.startsWith('builtin.')) return name;
  const key = 'badge.name_' + id.slice('builtin.'.length);
  // The points badges say the family's own name for points ("1,000 Stars").
  const t = localize(hass, key, { points_name: pointsName || familyPointsName(hass), count: badgeCount(hass, id) });
  return t && t !== key ? t : name;
}

/**
 * The number in a built-in badge's id ("builtin.1000_points" → 1000), written
 * the way HA writes numbers (its number format setting, once the shared
 * number helper is loaded), for the {count} in the badge's name (#771).
 */
function badgeCount(hass, id) {
  const m = /^builtin\.(\d+)_/.exec(String(id || ''));
  if (!m) return '';
  const n = Number(m[1]);
  return window.__taskmate_numbers && window.__taskmate_numbers.format
    ? window.__taskmate_numbers.format(hass, n) : String(n);
}

/**
 * The family's name for points, from the overview sensor (found under its
 * default id or, if renamed, as the state carrying the companion map), else
 * the translated "Points". Cached per hass.states object.
 */
let _pnCache = { states: null, value: '' };
function familyPointsName(hass) {
  const states = hass && hass.states;
  if (!states) return localize(hass, 'common.points');
  if (_pnCache.states !== states) {
    let ov = states['sensor.taskmate_overview'];
    if (!(ov && ov.attributes && ov.attributes.points_name)) {
      ov = Object.values(states).find((s) => s && s.attributes && s.attributes.companion_entities && s.attributes.points_name);
    }
    _pnCache = { states, value: (ov && ov.attributes && ov.attributes.points_name) || '' };
  }
  return _pnCache.value || localize(hass, 'common.points');
}

// Expose globally so cards can access without ES module imports
window.__taskmate_badge_name = badgeName;
window.__taskmate_badge_count = badgeCount;
window.__taskmate_time_lock_label = timeLockLabel;
window.__taskmate_localize = localize;
window.__taskmate_loadTranslations = loadTranslations;

// Start fetching the cards bundle straight away, in the language Home
// Assistant is most likely to report, so the first card render has its words
// rather than flashing raw keys. If the guess is wrong, the first lookup loads
// the right language. On the admin panel's own page, start its bundle too.
function _guessLang() {
  try {
    const picked = window.localStorage && window.localStorage.getItem('selectedLanguage');
    if (picked) return JSON.parse(picked);
  } catch (_e) { /* ignore */ }
  return (document.documentElement && document.documentElement.lang) || navigator.language || _FALLBACK;
}
try {
  const guess = _resolveLang(_guessLang());
  _loadBundle(guess, _BUNDLES.default);
  if (window.location && window.location.pathname.startsWith('/taskmate-admin')) _loadBundle(guess, 'panel');
} catch (_e) { /* ignore */ }
