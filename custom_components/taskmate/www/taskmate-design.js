/**
 * TaskMate shared design layer.
 *
 * Injects design-token CSS (custom properties) keyed by [data-tm-design],
 * and exposes helpers for cards to resolve the active design + build the
 * editor dropdown. CSS custom properties inherit across shadow-DOM
 * boundaries, so a card only needs to set data-tm-design on its host and
 * consume var(--tmd-*) inside its shadow styles.
 *
 * Designs:
 *   classic  — current look; no tokens (cards fall back to HA theme vars)
 *   playroom — warm, rounded, picture-book
 *   console  — dark gamified HUD
 *   cleanpro — calm productivity / SaaS
 *
 * Mirrors window.__taskmate_localize: exposed globally, no ES module imports.
 */
(function () {
  const IDS = ["classic", "playroom", "console", "cleanpro"];

  // Fonts must be loaded at the document level (an @import inside a shadow
  // stylesheet is honoured, but loading once globally avoids N duplicate fetches).
  const FONT_IMPORT =
    "@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=Nunito:wght@400;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700;800&family=Manrope:wght@500;600;700;800&display=swap');";

  // Design tokens. IMPORTANT: these are :host-scoped so they can be applied
  // INSIDE each card's shadow root. A document-level [data-tm-design] rule
  // cannot reach a card host nested in HA's shadow trees, but :host() matches
  // the host carrying the attribute wherever it lives. Custom properties then
  // inherit down into the card's shadow DOM. Tokens mirror
  // docs/design/redesigns/taskmate-redesigns.html (.dir-a / .dir-b / .dir-c).
  const TOKENS = `
:host([data-tm-design="playroom"]),[data-tm-design="playroom"]{
  --tmd-bg:#FFF7EC;--tmd-surface:#FFFFFF;--tmd-surface-2:#FFF0DB;--tmd-border:#F0DFC4;
  --tmd-text:#3A2E26;--tmd-dim:#9C8676;
  --tmd-accent:#7C5CE6;--tmd-accent2:#FFC23C;--tmd-good:#36C58E;--tmd-warn:#FFB020;--tmd-bad:#FF6B6B;--tmd-gold:#FFC23C;
  --tmd-radius:22px;--tmd-radius-sm:14px;--tmd-shadow:0 10px 24px rgba(123,92,230,.12);--tmd-hd-text:#fff;
  --tmd-font-display:"Baloo 2",cursive;--tmd-font-body:"Nunito",sans-serif;--tmd-font-mono:"Baloo 2",cursive;
  --tmd-c1:#FF6B6B;--tmd-c2:#4ECDC4;--tmd-c3:#FFB020;--tmd-c4:#6C8DFF;--tmd-c5:#C77DFF;--tmd-c6:#45D483;
}
:host([data-tm-design="console"]),[data-tm-design="console"]{
  --tmd-bg:#EEF2F8;--tmd-surface:#FFFFFF;--tmd-surface-2:#E9EEF5;--tmd-border:#D3DCE7;
  --tmd-text:#0F1B2D;--tmd-dim:#5C6B80;
  --tmd-accent:#0E9BC4;--tmd-accent2:#E0357F;--tmd-good:#1AA06A;--tmd-warn:#C98800;--tmd-bad:#E0476A;--tmd-gold:#C98800;
  --tmd-radius:12px;--tmd-radius-sm:8px;--tmd-shadow:0 6px 18px rgba(18,32,52,.12);--tmd-hd-text:#fff;
  --tmd-font-display:"Space Grotesk",sans-serif;--tmd-font-body:"Inter",sans-serif;--tmd-font-mono:"JetBrains Mono",monospace;
  --tmd-c1:#0E9BC4;--tmd-c2:#E0357F;--tmd-c3:#C98800;--tmd-c4:#6A4BE0;--tmd-c5:#1AA06A;--tmd-c6:#E0703D;
}
:host([data-tm-design="cleanpro"]),[data-tm-design="cleanpro"]{
  --tmd-bg:#F6F7F9;--tmd-surface:#FFFFFF;--tmd-surface-2:#F1F3F6;--tmd-border:#E5E8EC;
  --tmd-text:#1A2230;--tmd-dim:#6B7585;
  --tmd-accent:#4F6BED;--tmd-accent2:#0FB5A8;--tmd-good:#16A36B;--tmd-warn:#E0A100;--tmd-bad:#DC4C4C;--tmd-gold:#E0A100;
  --tmd-radius:14px;--tmd-radius-sm:9px;--tmd-shadow:0 1px 2px rgba(16,24,40,.06),0 8px 18px rgba(16,24,40,.06);--tmd-hd-text:#fff;
  --tmd-font-display:"Manrope",sans-serif;--tmd-font-body:"Inter",sans-serif;--tmd-font-mono:"Inter",sans-serif;
  --tmd-c1:#4F6BED;--tmd-c2:#0FB5A8;--tmd-c3:#E0A100;--tmd-c4:#7A5AF0;--tmd-c5:#E0567A;--tmd-c6:#2BA84A;
}

/* ── Dark-mode variants ──────────────────────────────────────────────────
   Cards stamp data-tm-dark on the host when HA is in dark mode. Each design has
   a light base (above) and a dark override here, so all three follow HA's
   light/dark setting. */
:host([data-tm-design="console"][data-tm-dark]),[data-tm-design="console"][data-tm-dark]{
  --tmd-bg:#0E1320;--tmd-surface:#161D2E;--tmd-surface-2:#1E2740;--tmd-border:#2A3550;
  --tmd-text:#EAF0FF;--tmd-dim:#8A97B8;
  --tmd-accent:#3DDBFF;--tmd-accent2:#FF4D9D;--tmd-good:#4BE08B;--tmd-warn:#FFCB45;--tmd-bad:#FF5A7A;--tmd-gold:#FFCB45;
  --tmd-shadow:0 10px 28px rgba(0,0,0,.5);
  --tmd-c1:#3DDBFF;--tmd-c2:#FF4D9D;--tmd-c3:#FFCB45;--tmd-c4:#7C5CFF;--tmd-c5:#4BE08B;--tmd-c6:#FF8A3D;
}
:host([data-tm-design="playroom"][data-tm-dark]),[data-tm-design="playroom"][data-tm-dark]{
  --tmd-bg:#241A2B;--tmd-surface:#2C2235;--tmd-surface-2:#382B43;--tmd-border:#473754;
  --tmd-text:#F6ECEF;--tmd-dim:#B6A3B4;--tmd-accent:#A88BFF;
  --tmd-shadow:0 10px 24px rgba(0,0,0,.45);
}
:host([data-tm-design="cleanpro"][data-tm-dark]),[data-tm-design="cleanpro"][data-tm-dark]{
  --tmd-bg:#0F141A;--tmd-surface:#181D25;--tmd-surface-2:#212733;--tmd-border:#2C3340;
  --tmd-text:#E6EAF1;--tmd-dim:#97A1B0;--tmd-accent:#6E86F5;--tmd-accent2:#1FC7B8;
  --tmd-shadow:0 1px 2px rgba(0,0,0,.4),0 8px 18px rgba(0,0,0,.35);
}`;

  // Shared component kit, themed by the tokens above. Every designed card
  // consumes these via __taskmate_design.styles() and adds only its own layout
  // classes. Headers stay FULL-COLOUR (var(--hd)) in every style per house rule.
  const KIT = `
.tmd{overflow:hidden;font-family:var(--tmd-font-body);color:var(--tmd-text);background:var(--tmd-surface);border-radius:var(--tmd-radius);box-shadow:var(--tmd-shadow)}
.tmd-hd{display:flex;align-items:center;gap:11px;padding:13px 15px;background:var(--hd,var(--tmd-accent));color:#fff}
:host([data-tm-design="playroom"]) .tmd-hd{background:linear-gradient(135deg,var(--hd,var(--tmd-accent)),color-mix(in srgb,var(--hd,var(--tmd-accent)) 72%,#fff))}
.tmd-hd .ic{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;background:rgba(255,255,255,.22);font-size:17px;flex:none}
.tmd-hd .tt{font-family:var(--tmd-font-display);font-weight:800;font-size:16px;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tmd-hd .tt small{display:block;font-family:var(--tmd-font-body);font-weight:600;font-size:11px;opacity:.85;margin-top:1px}
.tmd-hd .pill{margin-left:auto;font-size:11px;font-weight:800;padding:4px 9px;border-radius:999px;background:rgba(255,255,255,.25);text-transform:capitalize}
.tmd-hd .cnt{margin-left:auto;min-width:22px;height:22px;padding:0 6px;border-radius:999px;background:var(--tmd-bad);color:#fff;font-size:12px;font-weight:800;display:grid;place-items:center}
.tmd-bd{padding:15px}
.tmd-empty{text-align:center;padding:26px 12px;color:var(--tmd-dim);font-size:.9rem}
.av{width:var(--av,42px);height:var(--av,42px);border-radius:50%;flex:none;display:grid;place-items:center;font-family:var(--tmd-font-display);font-weight:800;color:#fff;font-size:calc(var(--av,42px)*.4);line-height:1;text-align:center;background:var(--ac,var(--tmd-accent));box-shadow:0 2px 6px rgba(0,0,0,.18);overflow:hidden}
:host([data-tm-design="console"]) .av{box-shadow:0 0 0 1px color-mix(in srgb,var(--ac,var(--tmd-accent)) 70%,transparent),0 0 14px color-mix(in srgb,var(--ac,var(--tmd-accent)) 35%,transparent)}
.av ha-icon{--mdc-icon-size:calc(var(--av,42px)*.55);color:#fff}
.av img{width:100%;height:100%;object-fit:cover;border-radius:50%}
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:700;padding:4px 9px;border-radius:999px;background:var(--tmd-surface-2);color:var(--tmd-text);border:1px solid var(--tmd-border)}
.chip.soft{background:color-mix(in srgb,var(--tmd-accent) 14%,transparent);border-color:transparent;color:var(--tmd-accent)}
.num{font-family:var(--tmd-font-mono);font-weight:800;letter-spacing:-.01em}
.big{font-family:var(--tmd-font-display);font-weight:800;line-height:1}
.bar{height:10px;border-radius:999px;background:var(--tmd-surface-2);overflow:hidden;border:1px solid var(--tmd-border)}
.bar>i{display:block;height:100%;border-radius:999px;background:var(--tmd-accent)}
:host([data-tm-design="console"]) .bar>i{background:linear-gradient(90deg,var(--tmd-accent),var(--tmd-accent2));box-shadow:0 0 12px color-mix(in srgb,var(--tmd-accent) 60%,transparent)}
.row{display:flex;align-items:center;gap:10px}
.muted{color:var(--tmd-dim)}
.divide{height:1px;background:var(--tmd-border);margin:12px 0}
.lead{color:var(--tmd-accent)}
.lead-dot{color:var(--tmd-gold)}
.btn{font:inherit;font-family:var(--tmd-font-display);font-weight:800;font-size:13.5px;line-height:1;border:0;cursor:pointer;padding:9px 14px;border-radius:var(--tmd-radius-sm);background:var(--tmd-accent);color:#fff;display:inline-flex;align-items:center;justify-content:center;gap:6px}
:host([data-tm-design="console"]) .btn{color:#06101c;background:linear-gradient(135deg,var(--tmd-accent),color-mix(in srgb,var(--tmd-accent) 60%,var(--tmd-accent2)));box-shadow:0 0 14px color-mix(in srgb,var(--tmd-accent) 45%,transparent)}
.btn.ghost{background:var(--tmd-surface-2);color:var(--tmd-text);border:1px solid var(--tmd-border)}
:host([data-tm-design="console"]) .btn.ghost{box-shadow:none}
.btn.good{background:var(--tmd-good);color:#06301f}
.btn.bad{background:var(--tmd-bad);color:#3a0d0d}
.btn.round{border-radius:50%;width:38px;height:38px;padding:0;justify-content:center;font-size:18px}
.btn.sm{padding:6px 10px;font-size:12.5px}
.stat{background:var(--tmd-surface-2);border:1px solid var(--tmd-border);border-radius:var(--tmd-radius-sm);padding:10px 11px}
.stat .k{font-size:11px;font-weight:700;color:var(--tmd-dim);text-transform:uppercase;letter-spacing:.04em}
.stat .v{font-family:var(--tmd-font-display);font-weight:800;font-size:20px;margin-top:2px}
.grid{display:grid;gap:10px}`;

  if (!document.getElementById("taskmate-design-fonts")) {
    const styleEl = document.createElement("style");
    styleEl.id = "taskmate-design-fonts";
    styleEl.textContent = FONT_IMPORT;
    document.head.appendChild(styleEl);
  }

  /**
   * The design tokens as a Lit CSSResult, for a card to include in its own
   * `static get styles()` so the :host token rules live inside the card's
   * shadow root (where they actually apply). Built lazily so the Lit `css`
   * tag — borrowed from HA's own card base — is resolved after HA has loaded.
   */
  let _tokenStyles = null;
  function styles() {
    if (_tokenStyles) return _tokenStyles;
    const base = customElements.get("hui-masonry-view") || customElements.get("hui-view");
    if (!base) return null;
    const css = Object.getPrototypeOf(base).prototype.css;
    if (!css) return null;
    const cssText = TOKENS + "\n" + KIT;
    const arr = [cssText];
    arr.raw = [cssText]; // satisfy css() implementations that read strings.raw
    try { _tokenStyles = css(arr); } catch (_e) { _tokenStyles = null; }
    return _tokenStyles;
  }

  /**
   * Global default design. Read the card's own entity first (the overview
   * sensor exposes card_design at top level); otherwise scan TaskMate sensors
   * so the default resolves even for cards bound to child-specific entities.
   */
  function _globalDesign(hass, entity) {
    if (!hass || !hass.states) return "classic";
    const own = hass.states[entity] && hass.states[entity].attributes;
    if (own && IDS.includes(own.card_design)) return own.card_design;
    for (const eid in hass.states) {
      if (eid.indexOf("sensor.taskmate") !== 0) continue;
      const a = hass.states[eid].attributes;
      if (a && IDS.includes(a.card_design)) return a.card_design;
    }
    return "classic";
  }

  /**
   * Resolve the active design for a card.
   * Precedence: per-card config.card_design → global default → classic.
   */
  function resolve(hass, config, entity) {
    const perCard = config && config.card_design;
    if (perCard && perCard !== "global" && IDS.includes(perCard)) return perCard;
    return _globalDesign(hass, entity);
  }

  // Relative luminance (0..1) of a CSS colour string, or null if unparseable.
  function _luminance(c) {
    if (!c) return null;
    c = c.trim();
    let r, g, b;
    let m = c.match(/^#([0-9a-f]{3})$/i);
    if (m) { const h = m[1]; r = parseInt(h[0] + h[0], 16); g = parseInt(h[1] + h[1], 16); b = parseInt(h[2] + h[2], 16); }
    else if ((m = c.match(/^#([0-9a-f]{6})$/i))) { r = parseInt(m[1].slice(0, 2), 16); g = parseInt(m[1].slice(2, 4), 16); b = parseInt(m[1].slice(4, 6), 16); }
    else if ((m = c.match(/rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)/i))) { r = +m[1]; g = +m[2]; b = +m[3]; }
    else return null;
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  }

  /**
   * Is the card currently in dark mode? Order:
   * 1. an explicitly-selected dark theme (hass.themes.darkMode)
   * 2. the ACTUAL rendered background brightness (covers the default theme
   *    following the OS, custom themes, etc.) read from the card's own scope
   * 3. the OS preference as a last resort.
   * `el` is the card host; its inherited --card/--primary-background-color
   * reflects whatever theme is live around it.
   */
  function isDark(hass, el) {
    if (hass && hass.themes && hass.themes.darkMode) return true;
    if (el && typeof getComputedStyle === "function") {
      try {
        const cs = getComputedStyle(el);
        const bg = (cs.getPropertyValue("--card-background-color")
          || cs.getPropertyValue("--primary-background-color")
          || cs.backgroundColor || "").trim();
        const lum = _luminance(bg);
        if (lum !== null) return lum < 0.5;
      } catch (_e) { /* ignore */ }
    }
    return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  /**
   * Resolve the design AND stamp the host element: data-tm-design + (in dark
   * mode) data-tm-dark. Cards call this once at the top of render() and branch
   * on the returned id. Returns "classic" when no design applies.
   */
  function apply(el, hass, config, entity) {
    const design = resolve(hass, config, entity);
    if (el) {
      el.setAttribute("data-tm-design", design);
      el.toggleAttribute("data-tm-dark", design !== "classic" && isDark(hass, el));
    }
    return design;
  }

  /** ha-form select options for a per-card design override (includes "use global"). */
  function editorOptions(t) {
    const label = (k, fallback) => (t ? t("common.design." + k) : fallback);
    return [
      { value: "global",   label: label("use_global", "Use global default") },
      { value: "classic",  label: label("classic", "Classic") },
      { value: "playroom", label: label("playroom", "Playroom") },
      { value: "console",  label: label("console", "Console") },
      { value: "cleanpro", label: label("cleanpro", "Clean Pro") },
    ];
  }

  // Raw token + kit CSS for non-Lit consumers (e.g. the admin panel, which
  // renders to light DOM). Inject into a <style> and set data-tm-design on a
  // wrapper element; the [data-tm-design] selector variant applies there.
  const cssText = TOKENS + "\n" + KIT;

  // ── Shared header-colour picker (QUAL-3) ───────────────────────────────
  // The same ~30-line colour-picker editor block was copy-pasted into 17 card
  // editors. They render it via a thin `_renderColourPicker` wrapper that calls
  // this helper, passing their own update method as onInput/onPreset/onReset.
  const _DEFAULT_COLOUR_PRESETS = ["#e67e22", "#27ae60", "#9b59b6", "#f1c40f", "#e74c3c", "#34495e"];

  function colourPicker(opts) {
    const base = customElements.get("hui-masonry-view") || customElements.get("hui-view");
    const html = base ? Object.getPrototypeOf(base).prototype.html : null;
    if (!html) return "";
    const { defaultValue, current, label, helper, resetLabel, onInput, onPreset, onReset } = opts;
    const presets = [defaultValue, ...(opts.presets || _DEFAULT_COLOUR_PRESETS)];
    const isActive = (c) => String(c).toLowerCase() === String(current).toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${label}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current} @input=${(e) => onInput(e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current}"></span>
          </label>
          <span class="colour-hex">${current}</span>
          <div class="colour-presets">
            ${presets.map((p) => html`
              <button class="preset-swatch ${isActive(p) ? "active" : ""}"
                style="background:${p}" title=${p}
                @click=${(e) => { e.preventDefault(); onPreset(p); }}></button>
            `)}
          </div>
          <button class="colour-reset"
            @click=${(e) => { e.preventDefault(); onReset(); }}>${resetLabel}</button>
        </div>
        <div class="colour-helper">${helper}</div>
      </div>
    `;
  }

  window.__taskmate_design = { IDS, resolve, isDark, apply, editorOptions, styles, cssText, tokensCSS: TOKENS, colourPicker };
})();
