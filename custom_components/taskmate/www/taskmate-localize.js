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
      return data;
    } catch {
      // Cache the failure so we don't retry on every render cycle
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
    str = key;
  }

  // Trigger background loads for any language not yet in cache
  for (const candidate of candidates) {
    if (!(candidate in _cache)) _loadLocale(candidate);
  }
  if (!(_FALLBACK in _cache)) _loadLocale(_FALLBACK);

  // Replace {placeholder} tokens
  if (params && typeof str === 'string') {
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
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

// Expose globally so cards can access without ES module imports
// (HA custom cards are loaded as classic scripts, not ES modules)
window.__taskmate_localize = localize;
window.__taskmate_loadTranslations = loadTranslations;
