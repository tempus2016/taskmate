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
 * Language resolution: nb → nb.json → en-GB.json → key
 * The base (fallback) language is en-GB since that is the source locale.
 */

const _cache = {};          // lang → { key: value }  (null = tried and failed)
const _pending = {};        // lang → Promise
const _BASE = '/taskmate/locales';
const _FALLBACK = 'en-GB';  // base language file

/**
 * Load a locale file by language code. Returns cached result if available.
 * Caches failures (as null) so we don't retry on every render.
 */
async function _loadLocale(lang) {
  if (lang in _cache) return _cache[lang];
  if (_pending[lang]) return _pending[lang];

  _pending[lang] = (async () => {
    try {
      const resp = await fetch(`${_BASE}/${lang}.json?v=${Date.now()}`);
      if (!resp.ok) throw new Error(resp.status);
      const data = await resp.json();
      _cache[lang] = data;
      _refreshTaskMateCards();
      return data;
    } catch {
      _cache[lang] = null;
      return null;
    } finally {
      delete _pending[lang];
    }
  })();

  return _pending[lang];
}

/**
 * Resolve language to a list of codes to try (most specific first).
 * e.g. "en-GB" → ["en-GB"]
 *      "nb"    → ["nb"]
 *      "pt-BR" → ["pt-BR", "pt"]
 */
function _langCandidates(lang) {
  const candidates = [lang];
  if (lang.includes('-')) {
    candidates.push(lang.split('-')[0]);
  }
  return candidates;
}

/**
 * Synchronous lookup — returns the translated string or the fallback.
 * Triggers async load in the background if the locale isn't cached yet.
 *
 * @param {object} hass - Home Assistant hass object (for hass.language)
 * @param {string} key  - Dot-notation key, e.g. 'common.today'
 * @param {object} [params] - Replacement params, e.g. { count: 5 }
 * @returns {string}
 */
function localize(hass, key, params) {
  const lang = (hass && hass.language) || _FALLBACK;
  const candidates = _langCandidates(lang);

  // Try each candidate language, then fall back to base language
  let str = undefined;
  for (const candidate of candidates) {
    if (_cache[candidate] && _cache[candidate][key]) {
      str = _cache[candidate][key];
      break;
    }
  }
  if (str === undefined && _cache[_FALLBACK]) {
    str = _cache[_FALLBACK][key];
  }
  if (str === undefined) {
    // Missing translation: only echo the key back when it's a plain identifier.
    // A key carrying HTML-significant characters is not a real key — it's caller
    // data concatenated into the lookup (e.g. `panel.assign_${value}_short`) —
    // so refuse to reflect it, since some call sites render _t() output as HTML.
    str = /^[\w.-]+$/.test(key) ? key : "";
  }

  // Trigger background loads for any language not yet in cache
  for (const candidate of candidates) {
    if (!(candidate in _cache)) _loadLocale(candidate);
  }
  if (!(_FALLBACK in _cache)) _loadLocale(_FALLBACK);

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
 * Pre-load a locale so translations are ready before first render.
 * Call this in connectedCallback() of your card.
 *
 * @param {object} hass - Home Assistant hass object
 * @returns {Promise<void>}
 */
async function loadTranslations(hass) {
  const lang = (hass && hass.language) || _FALLBACK;
  const candidates = _langCandidates(lang);
  await Promise.all([
    _loadLocale(_FALLBACK),
    ...candidates.filter(c => c !== _FALLBACK).map(c => _loadLocale(c)),
  ]);
}

// Walk the DOM across shadow roots and trigger a re-render on TaskMate cards.
// Called after locale files load so cards pick up the new translations.
function _refreshTaskMateCards() {
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
  if (from && until && from !== until) parts.push(`${from}\u2013${until}`);
  return parts.join(' \u00b7 ');
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

// Pre-load the fallback locale so translations are ready as soon as possible.
// Cards that render before this completes will show raw keys momentarily,
// then _loadLocale calls _refreshTaskMateCards to re-render them.
_loadLocale(_FALLBACK);
