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
// While the page start-up is still working out which language Home Assistant
// will settle on (see _startPreload), lookups queue their bundle here instead
// of fetching it in a language that is about to change.
let _deciding = false;
let _decision = Promise.resolve();
const _wanted = new Set();

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

const _lastShown = {};      // bundle → the "lang/bundle" a lookup last read from

/**
 * A loaded bundle to read while `lang`'s own is still on its way, or null:
 * the same language's family (en-GB for en), then the language the page was
 * showing until now (switching en → de keeps the English words up until the
 * German arrive, rather than flashing raw keys), then en-GB, then any copy.
 */
function _interim(lang, bundle) {
  const base = String(lang).split('-')[0];
  const loaded = Object.keys(_cache).filter((id) => _cache[id] && id.endsWith(`/${bundle}`));
  const family = loaded.find((id) => id.split('/')[0].split('-')[0] === base);
  const pick = family
    || (_cache[_lastShown[bundle]] ? _lastShown[bundle] : null)
    || (_cache[`${_FALLBACK}/${bundle}`] ? `${_FALLBACK}/${bundle}` : null)
    || loaded[0];
  return pick ? _cache[pick] : null;
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
  _ensureExceptionStrings(hass);
  const lang = _langOf(hass);
  const bundle = _bundleFor(String(key));
  const id = `${lang}/${bundle}`;

  let str = undefined;
  let data;
  if (!(id in _cache)) {
    if (_deciding) _wanted.add(bundle);
    else _loadBundle(lang, bundle);
    // Until it lands, read a copy that is already here — the same language's
    // family (en-GB for en) or en-GB — rather than flashing the raw key.
    data = _interim(lang, bundle);
  } else if (_cache[id]) {
    data = _cache[id];
    _lastShown[bundle] = id;
  } else {
    // A language whose bundle failed to load reads the en-GB copy instead.
    data = _cache[`${_FALLBACK}/${bundle}`];
  }
  if (data && typeof data[key] === 'string') str = data[key];
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
  if (_deciding) await _decision;
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
 * @param {object} [hass] - for HA's time format ("6:00 PM" on a 12-hour
 *   profile); without one, the page's own hass is used, else the times as stored
 */
function timeLockLabel(lock, t, hass) {
  if (!lock) return '';
  const days = (lock.days || []).map(Number).filter(n => Number.isInteger(n) && n >= 0 && n <= 6).sort((a, b) => a - b);
  const parts = [];
  // All seven days selected is the same as no day restriction — don't spell it out.
  if (days.length && days.length < 7) parts.push(days.map(d => t(_DAY_KEYS[d])).join(', '));
  const from = lock.from || '';
  const until = lock.until || '';
  if (from && until && from !== until) {
    let h = hass;
    if (!h) {
      try {
        const ha = typeof document !== 'undefined' && document.querySelector ? document.querySelector('home-assistant') : null;
        h = ha && ha.hass;
      } catch (_e) { h = null; }
    }
    parts.push(h ? `${clock(h, from)}–${clock(h, until)}` : `${from}–${until}`);
  }
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

/**
 * Arguments for toLocaleDateString / toLocaleTimeString / toLocaleString /
 * Intl.DateTimeFormat that follow Home Assistant's language and its date/time
 * settings rather than the browser's (#771): a German HA on an English browser
 * reads "Dienstag, 3. November", not "Tuesday, 3 November".
 *
 *   date.toLocaleDateString(...dateArgs(hass, { weekday: "long" }))
 *   date.toLocaleTimeString(...dateArgs(hass, { hour: "2-digit", minute: "2-digit" }, "time"))
 *
 * - Language: hass.locale.language, else hass.language. HA's "pt" is European
 *   Portuguese, which Intl spells pt-PT ("pt" alone formats as Brazilian).
 * - Time format (hass.locale.time_format): "12" / "24" force the clock for
 *   anything showing a time; "language" keeps the language's own; "system"
 *   uses the browser's locale for it.
 * - Date format (hass.locale.date_format) "system" uses the browser's locale
 *   for a date. DMY / MDY / YMD only reorder numeric dates in HA; TaskMate's
 *   dates spell the month, so the language's own order applies.
 * - Time zone (hass.locale.time_zone) "server" shows times in HA's zone, unless
 *   the caller already chose one. Date-only labels keep the caller's zone: a
 *   local-midnight Date shown in another zone can land on the day before.
 *
 * @param {object} hass
 * @param {object} [opts] - the Intl options the caller wants
 * @param {"time"|"datetime"} [kind] - what the method prints when opts are absent
 * @returns {[string|undefined, object|undefined]}
 */
function dateArgs(hass, opts, kind) {
  const loc = (hass && hass.locale) || {};
  const o = opts ? { ...opts } : {};
  const timeish = kind === 'time' || kind === 'datetime'
    || 'hour' in o || 'minute' in o || 'timeStyle' in o;
  // "Today" / "now" displays (kind "now") follow HA's server zone too, so the
  // panel's date line reads the same day the server does. Stored dates keep
  // the caller's zone: a local-midnight Date in another zone is the day before.
  const nowish = kind === 'now';
  let lang = loc.language || (hass && hass.language) || undefined;
  if (lang === 'pt') lang = 'pt-PT';
  if (timeish ? loc.time_format === 'system' : loc.date_format === 'system') lang = undefined;
  if (timeish) {
    if (loc.time_format === '12' || loc.time_format === '24') {
      delete o.hour12;
      o.hourCycle = loc.time_format === '12' ? 'h12' : 'h23';
    }
  }
  if ((timeish || nowish) && loc.time_zone === 'server' && !o.timeZone && hass && hass.config && hass.config.time_zone) {
    o.timeZone = hass.config.time_zone;
  }
  if (lang) {
    try {
      if (!Intl.DateTimeFormat.supportedLocalesOf([lang]).length) lang = undefined;
    } catch (e) {
      lang = undefined;  // not a valid language tag
    }
  }
  // A 12-hour clock reads "5:00 PM", not "05:00 PM": the leading zero only
  // belongs to a 24-hour clock (as in HA's own time format).
  if (timeish && o.hour === '2-digit') {
    try {
      const cycle = new Intl.DateTimeFormat(lang, { hour: 'numeric', ...o }).resolvedOptions().hourCycle;
      if (cycle === 'h11' || cycle === 'h12') o.hour = 'numeric';
    } catch (e) { /* keep 2-digit */ }
  }
  return [lang, Object.keys(o).length ? o : undefined];
}

/**
 * Arguments for Number#toLocaleString / Intl.NumberFormat that follow Home
 * Assistant's language and number format (hass.locale.number_format), not the
 * browser's (#771): a German HA shows 1.234 points, not 1,234.
 *
 *   "language"       HA's language (the default)
 *   "system"         the browser's locale
 *   "comma_decimal"  1,234.5
 *   "decimal_comma"  1.234,5
 *   "space_comma"    1 234,5
 *   "none"           HA's language, no thousands grouping
 */
const _NUMBER_FORMAT_LOCALE = { comma_decimal: 'en-US', decimal_comma: 'de', space_comma: 'fr' };

function numberArgs(hass, opts) {
  const loc = (hass && hass.locale) || {};
  const o = opts ? { ...opts } : {};
  let lang = loc.language || (hass && hass.language) || undefined;
  if (lang === 'pt') lang = 'pt-PT';
  const fmt = loc.number_format;
  if (fmt === 'system') lang = undefined;
  else if (_NUMBER_FORMAT_LOCALE[fmt]) lang = _NUMBER_FORMAT_LOCALE[fmt];
  else if (fmt === 'none') o.useGrouping = false;
  if (lang) {
    try {
      if (!Intl.NumberFormat.supportedLocalesOf([lang]).length) lang = undefined;
    } catch (e) {
      lang = undefined;  // not a valid language tag
    }
  }
  return [lang, Object.keys(o).length ? o : undefined];
}

/**
 * A number as text in HA's number format. Only real numbers are formatted:
 * a string comes back as given, so text that was already formatted ("1.234"
 * in German) is never re-read as a decimal and formatted twice.
 */
function formatNumber(hass, value, opts) {
  if (value === null || value === undefined) return '';
  if (typeof value !== 'number' || !Number.isFinite(value)) return String(value);
  if (Object.is(value, -0)) value = 0;  // "-0" for a zero-point row reads as a penalty
  try {
    // One minus sign everywhere: the cards write "−15" (U+2212), so a
    // formatted negative uses it too rather than the hyphen "-15".
    return value.toLocaleString(...numberArgs(hass, opts)).replace(/^-/, '\u2212');
  } catch (e) {
    return String(value).replace(/^-/, '\u2212');
  }
}

/**
 * An avatar's name for the picker. The shipped avatars (coord_avatars.py
 * DEFAULT_AVATAR_CATALOG) arrive with their English label; show those in the
 * user's language. A label a parent changed is their own text and is kept.
 */
const _AVATAR_DEFAULT_LABELS = {
  starter: 'Starter', rocket: 'Rocket', robot: 'Robot', ninja: 'Ninja',
  crown: 'Royalty', trophy: 'Champion', fire: 'On Fire', diamond: 'Diamond',
};
function avatarLabel(hass, opt) {
  const label = opt && opt.label ? String(opt.label) : '';
  const id = opt && opt.id;
  if (id && _AVATAR_DEFAULT_LABELS[id] === label) {
    const s = localize(hass, `avatar.label_${id}`);
    if (s && s !== `avatar.label_${id}`) return s;
  }
  return label;
}

/**
 * The text to show for a failed TaskMate call. The backend refuses an action
 * with a translation key (TaskMateError → ServiceValidationError), so show
 * Home Assistant's translation of it in the user's language; otherwise fall
 * back to the message as sent, without HA's "Validation error: " prefix.
 */
let _excLang = null;
function _ensureExceptionStrings(hass) {
  if (!hass || typeof hass.loadBackendTranslation !== 'function') return;
  const lang = hass.language || '';
  if (_excLang === lang) return;
  _excLang = lang;
  try {
    const p = hass.loadBackendTranslation('exceptions', 'taskmate');
    if (p && typeof p.catch === 'function') p.catch(() => { _excLang = null; });
  } catch (e) {
    _excLang = null;
  }
}

function errorText(hass, err) {
  _ensureExceptionStrings(hass);
  const key = err && err.translation_key;
  if (key && (!err.translation_domain || err.translation_domain === 'taskmate')
      && hass && typeof hass.localize === 'function') {
    try {
      const s = hass.localize(`component.taskmate.exceptions.${key}.message`, err.translation_placeholders || {});
      if (s) return s;
    } catch (e) { /* fall through to the sent message */ }
  }
  const msg = err && typeof err === 'object' && 'message' in err ? err.message : err;
  return String(msg == null ? '' : msg).replace(/^Validation error:\s*/, '');
}

/**
 * A whole-number percentage (12 → "12%" / "12 %") in HA's language: the
 * spacing and sign placement follow the locale, as Intl does.
 */
function formatPercent(hass, pct) {
  const n = Number(pct);
  if (!Number.isFinite(n)) return pct == null ? '' : String(pct);
  return formatNumber(hass, n / 100, { style: 'percent', maximumFractionDigits: 0 });
}

/**
 * A wall-clock time ("17:00", as chores, periods and set times store it) in
 * HA's time format: "17:00" on a 24-hour profile, "5:00 PM" on a 12-hour
 * one. Anything that isn't H:MM comes back unchanged.
 */
function clock(hass, hhmm) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(String(hhmm == null ? '' : hhmm).trim());
  if (!m) return hhmm == null ? '' : String(hhmm);
  const d = new Date(Date.UTC(2024, 0, 1, Number(m[1]) % 24, Number(m[2])));
  try {
    return d.toLocaleTimeString(...dateArgs(hass, { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }, 'time'));
  } catch (e) {
    return String(hhmm);
  }
}

/**
 * The hour of the day (0-23) as HA shows it: the server's when HA's time
 * zone setting is "server", the browser's otherwise.
 */
function hourNow(hass, now = new Date()) {
  const loc = (hass && hass.locale) || {};
  const tz = loc.time_zone === 'server' && hass && hass.config && hass.config.time_zone;
  if (!tz) return now.getHours();
  try {
    const h = new Intl.DateTimeFormat('en-US', { timeZone: tz, hour: 'numeric', hourCycle: 'h23' })
      .formatToParts(now).find(p => p.type === 'hour');
    return h ? Number(h.value) % 24 : now.getHours();
  } catch (e) {
    return now.getHours();
  }
}

/**
 * A card's name or description for the Lovelace card picker
 * (window.customCards). Home Assistant reads those each time the picker
 * opens, so each card defines them as getters calling this: the picker then
 * shows them in the signed-in user's language. Falls back to the card's
 * English text when there is no hass yet or no translation for the key.
 *
 * @param {string} key - e.g. 'activity.card_name'
 * @param {string} fallback - the English text
 */
function pickerText(key, fallback) {
  try {
    const ha = document.querySelector('home-assistant');
    const hass = ha && ha.hass;
    if (!hass || !hass.language) return fallback;
    const str = localize(hass, key);
    return str && str !== key ? str : fallback;
  } catch (_e) {
    return fallback;
  }
}

// Expose globally so cards can access without ES module imports
window.__taskmate_badge_name = badgeName;
window.__taskmate_badge_count = badgeCount;
window.__taskmate_dates = { args: dateArgs, clock, hourNow };
window.__taskmate_numbers = { args: numberArgs, format: formatNumber, percent: formatPercent };
window.__taskmate_picker_text = pickerText;
window.__taskmate_time_lock_label = timeLockLabel;
window.__taskmate_localize = localize;
window.__taskmate_error_text = errorText;
window.__taskmate_avatar_label = avatarLabel;
window.__taskmate_loadTranslations = loadTranslations;

// Start fetching the cards bundle (and, on the admin panel's own page, the
// panel bundle) before the first card renders, so it has its words rather than
// flashing raw keys — but only in the language Home Assistant will settle on,
// so a page never downloads a bundle twice (#771: an en-GB server with an "en"
// profile fetched both en-GB/ and en/ copies while HA switched over).
//
// - HA keeps the language it last used in localStorage (selectedLanguage) and
//   starts with it again, so on any visit after the first that is the answer.
// - Otherwise wait for HA's connection and ask what HA itself asks: the
//   profile's language (frontend/get_user_data), else hass.language.
// - Not a Home Assistant page, or nothing within 10 s: the browser's language.
function _storedLang() {
  try {
    const picked = window.localStorage && window.localStorage.getItem('selectedLanguage');
    if (picked) return JSON.parse(picked);
  } catch (_e) { /* ignore */ }
  return null;
}
function _guessLang() {
  // `navigator` may be absent (tests, a worker); never let the guess throw.
  const nav = typeof navigator !== 'undefined' && navigator ? navigator.language : '';
  const doc = typeof document !== 'undefined' && document && document.documentElement;
  return (doc && doc.lang) || nav || _FALLBACK;
}
function _hassNow() {
  try {
    const ha = typeof document.querySelector === 'function' ? document.querySelector('home-assistant') : null;
    return ha && ha.hass && ha.hass.connection && ha.hass.language ? ha.hass : null;
  } catch (_e) {
    return null;
  }
}
async function _settledLang() {
  if (typeof document.querySelector !== 'function' || !document.querySelector('home-assistant')) return _guessLang();
  let hass = _hassNow();
  for (let waited = 0; !hass && waited < 10000; waited += 50) {
    await new Promise((r) => setTimeout(r, 50));
    hass = _hassNow();
  }
  if (!hass) return _guessLang();
  if (hass.selectedLanguage) return hass.selectedLanguage;
  try {
    const res = await hass.connection.sendMessagePromise({ type: 'frontend/get_user_data', key: 'language' });
    if (res && res.value && res.value.language) return res.value.language;
  } catch (_e) { /* ignore */ }
  return (_hassNow() || hass).language;
}
function _startPreload() {
  const bundles = [_BUNDLES.default];
  if (window.location && window.location.pathname.startsWith('/taskmate-admin')) bundles.push('panel');
  const go = (lang) => {
    const resolved = _resolveLang(lang);
    _lastLang = lang;
    for (const b of new Set([...bundles, ..._wanted])) _loadBundle(resolved, b);
    _wanted.clear();
  };
  const stored = _storedLang();
  if (stored) { go(stored); return; }
  _deciding = true;
  _decision = _settledLang()
    .catch(() => _guessLang())
    .then((lang) => { _deciding = false; go(lang); });
}
try {
  _startPreload();
} catch (_e) {
  _deciding = false;
}
