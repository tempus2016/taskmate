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
 *   accessible — high contrast, colour-blind safe, dyslexia-friendly type
 *   graphite — corporate/system look; reuses the cleanpro LAYOUT (see
 *              LAYOUT_ALIAS) and restyles it entirely through tokens + kit
 *
 * Mirrors window.__taskmate_localize: exposed globally, no ES module imports.
 */
(function () {
  const IDS = ["classic", "playroom", "console", "cleanpro", "accessible", "graphite"];

  // A design whose markup is another design's. apply() stamps the real id on
  // the host (so the style's CSS applies) but hands cards the layout id, so
  // every existing `design === "cleanpro"` branch picks graphite up too. Without
  // this a new id falls down each card's final `else`, which is playroom in
  // some cards and cleanpro in others — the classic "works on one style,
  // invisible on the rest" bug.
  const LAYOUT_ALIAS = { graphite: "cleanpro" };

  // Fonts must be loaded at the document level (an @font-face inside a shadow
  // stylesheet is honoured, but loading once globally avoids N duplicate
  // fetches). The faces ship with the integration under www/fonts/ and are
  // served from the /taskmate/ static path, so a dashboard view sends nothing
  // to a font CDN and the cards look the same on a tablet with no internet.
  // Latin and Latin-extended subsets only (every TaskMate locale is Latin
  // script); each subset carries its unicode-range so a browser fetches only
  // the file it needs. Variable files cover the weight range the designs use.
  // Licences (SIL OFL) sit beside the files. To refresh a face, replace its
  // .woff2 and keep the name; tests/frontend/taskmate-self-hosted-fonts
  // checks every url() below is shipped and every shipped file is used.
  const FONT_IMPORT =
    "@font-face{font-family:'Baloo 2';font-style:normal;font-weight:500 800;font-display:swap;src:url(/taskmate/fonts/baloo-2-500-800-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}" +
    "@font-face{font-family:'Baloo 2';font-style:normal;font-weight:500 800;font-display:swap;src:url(/taskmate/fonts/baloo-2-500-800-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF;}" +
    "@font-face{font-family:'Nunito';font-style:normal;font-weight:400 900;font-display:swap;src:url(/taskmate/fonts/nunito-400-900-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}" +
    "@font-face{font-family:'Nunito';font-style:normal;font-weight:400 900;font-display:swap;src:url(/taskmate/fonts/nunito-400-900-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF;}" +
    "@font-face{font-family:'Space Grotesk';font-style:normal;font-weight:400 700;font-display:swap;src:url(/taskmate/fonts/space-grotesk-400-700-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}" +
    "@font-face{font-family:'Space Grotesk';font-style:normal;font-weight:400 700;font-display:swap;src:url(/taskmate/fonts/space-grotesk-400-700-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF;}" +
    "@font-face{font-family:'Inter';font-style:normal;font-weight:400 700;font-display:swap;src:url(/taskmate/fonts/inter-400-700-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}" +
    "@font-face{font-family:'Inter';font-style:normal;font-weight:400 700;font-display:swap;src:url(/taskmate/fonts/inter-400-700-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF;}" +
    "@font-face{font-family:'JetBrains Mono';font-style:normal;font-weight:500 800;font-display:swap;src:url(/taskmate/fonts/jetbrains-mono-500-800-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}" +
    "@font-face{font-family:'JetBrains Mono';font-style:normal;font-weight:500 800;font-display:swap;src:url(/taskmate/fonts/jetbrains-mono-500-800-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF;}" +
    "@font-face{font-family:'Manrope';font-style:normal;font-weight:500 800;font-display:swap;src:url(/taskmate/fonts/manrope-500-800-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}" +
    "@font-face{font-family:'Manrope';font-style:normal;font-weight:500 800;font-display:swap;src:url(/taskmate/fonts/manrope-500-800-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF;}" +
    "@font-face{font-family:'Atkinson Hyperlegible';font-style:normal;font-weight:400;font-display:swap;src:url(/taskmate/fonts/atkinson-hyperlegible-400-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}" +
    "@font-face{font-family:'Atkinson Hyperlegible';font-style:normal;font-weight:400;font-display:swap;src:url(/taskmate/fonts/atkinson-hyperlegible-400-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF;}" +
    "@font-face{font-family:'Atkinson Hyperlegible';font-style:normal;font-weight:700;font-display:swap;src:url(/taskmate/fonts/atkinson-hyperlegible-700-latin.woff2) format('woff2');unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD;}" +
    "@font-face{font-family:'Atkinson Hyperlegible';font-style:normal;font-weight:700;font-display:swap;src:url(/taskmate/fonts/atkinson-hyperlegible-700-latin-ext.woff2) format('woff2');unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C4,U+2113,U+2C60-2C7F,U+A720-A7FF;}";

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

:host([data-tm-design="graphite"]),[data-tm-design="graphite"]{
  /* Neutrals carry the card; the only saturated element is the header band
     (per-card header_color). Actions are near-black rather than a coloured
     accent, and colour is reserved for meaning: good / warn / bad. */
  --tmd-bg:#EFEFF2;--tmd-surface:#FFFFFF;--tmd-surface-2:#F5F5F7;--tmd-border:#D2D2D7;
  --tmd-text:#1D1D1F;--tmd-dim:#6E6E73;
  --tmd-accent:#1D1D1F;--tmd-accent2:#6E6E73;--tmd-good:#1D7A4C;--tmd-warn:#B25E00;--tmd-bad:#B3261E;--tmd-gold:#B25E00;
  --tmd-radius:18px;--tmd-radius-sm:12px;--tmd-shadow:none;--tmd-hd-text:#fff;
  /* The system stack resolves to real SF Pro on Apple hardware; Inter (already
     in FONT_IMPORT) is the fallback everywhere else. Figures are kept aligned
     with font-variant-numeric rather than a separate monospace face. */
  --tmd-font-display:-apple-system,BlinkMacSystemFont,"SF Pro Display","Inter",system-ui,sans-serif;
  --tmd-font-body:-apple-system,BlinkMacSystemFont,"SF Pro Text","Inter",system-ui,sans-serif;
  --tmd-font-mono:-apple-system,BlinkMacSystemFont,"SF Pro Text","Inter",system-ui,sans-serif;
  --tmd-c1:#1F5F8B;--tmd-c2:#146356;--tmd-c3:#8A4B12;--tmd-c4:#3E4B8B;--tmd-c5:#6B3D6B;--tmd-c6:#2F4858;
}

/* ── Dark-mode variants ──────────────────────────────────────────────────
   Cards stamp data-tm-dark on the host when HA is in dark mode. Each design has
   a light base (above) and a dark override here, so all three follow HA's
   light/dark setting. */
:host([data-tm-design="accessible"]),[data-tm-design="accessible"]{
  /* Colours are the Okabe-Ito colour-blind-safe palette: distinguishable
     under protanopia, deuteranopia and tritanopia. Text is near-black on
     white (~19:1, comfortably past WCAG AAA) and borders are heavy enough to
     carry meaning without relying on hue. Atkinson Hyperlegible is drawn for
     low vision — its letterforms stay distinct where similar glyphs (I/l/1,
     O/0) usually collapse. */
  --tmd-bg:#FFFFFF;--tmd-surface:#FFFFFF;--tmd-surface-2:#F2F2F2;--tmd-border:#111111;
  --tmd-text:#111111;--tmd-dim:#3D3D3D;
  --tmd-accent:#0072B2;--tmd-accent2:#D55E00;--tmd-good:#009E73;--tmd-warn:#E69F00;--tmd-bad:#D55E00;--tmd-gold:#E69F00;
  --tmd-radius:10px;--tmd-radius-sm:6px;--tmd-shadow:0 0 0 2px #111111;--tmd-hd-text:#fff;
  --tmd-font-display:"Atkinson Hyperlegible",sans-serif;
  --tmd-font-body:"Atkinson Hyperlegible",sans-serif;
  --tmd-font-mono:"Atkinson Hyperlegible",monospace;
  --tmd-c1:#0072B2;--tmd-c2:#D55E00;--tmd-c3:#009E73;--tmd-c4:#CC79A7;--tmd-c5:#56B4E9;--tmd-c6:#E69F00;
}
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
}
:host([data-tm-design="graphite"][data-tm-dark]),[data-tm-design="graphite"][data-tm-dark]{
  /* True black behind elevated sheets. --tmd-accent stays a mid neutral so a
     card with no header_color still has a legible band with white text; the
     button colour is derived from --tmd-text instead, so it inverts properly. */
  --tmd-bg:#000000;--tmd-surface:#1C1C1E;--tmd-surface-2:#2C2C2E;--tmd-border:#38383A;
  --tmd-text:#F5F5F7;--tmd-dim:#98989F;
  --tmd-accent:#3A3A3C;--tmd-accent2:#98989F;--tmd-good:#30A46C;--tmd-warn:#D98324;--tmd-bad:#E5484D;--tmd-gold:#D98324;
  --tmd-shadow:none;
  --tmd-c1:#2C7CB0;--tmd-c2:#1E8C77;--tmd-c3:#B06A26;--tmd-c4:#5B6AC0;--tmd-c5:#945993;--tmd-c6:#4A6B80;
}
:host([data-tm-design="accessible"][data-tm-dark]),[data-tm-design="accessible"][data-tm-dark]{
  /* Pure black would bloom on OLED and is harsh for astigmatism; #0A0A0A with
     near-white text still clears AAA. Hues are the Okabe-Ito light variants,
     which stay distinguishable against a dark ground. */
  --tmd-bg:#0A0A0A;--tmd-surface:#0A0A0A;--tmd-surface-2:#1C1C1C;--tmd-border:#F5F5F5;
  --tmd-text:#F5F5F5;--tmd-dim:#CFCFCF;
  --tmd-accent:#56B4E9;--tmd-accent2:#E69F00;--tmd-good:#009E73;--tmd-warn:#F0E442;--tmd-bad:#E69F00;--tmd-gold:#F0E442;
  --tmd-shadow:0 0 0 2px #F5F5F5;
  --tmd-c1:#56B4E9;--tmd-c2:#E69F00;--tmd-c3:#009E73;--tmd-c4:#CC79A7;--tmd-c5:#F0E442;--tmd-c6:#0072B2;
}`;

  // Shared component kit, themed by the tokens above. Every designed card
  // consumes these via __taskmate_design.styles() and adds only its own layout
  // classes. Headers stay FULL-COLOUR (var(--hd)) in every style per house rule.
  const KIT = `
.tmd{overflow:hidden;font-family:var(--tmd-font-body);color:var(--tmd-text);background:var(--tmd-surface);border-radius:var(--tmd-radius);box-shadow:var(--tmd-shadow)}
.tmd-hd{display:flex;align-items:center;gap:11px;padding:13px 15px;background:var(--hd,var(--tmd-accent));color:#fff}
:host([data-tm-design="playroom"]) .tmd-hd{background:var(--hd,var(--tmd-accent));background:linear-gradient(135deg,var(--hd,var(--tmd-accent)),color-mix(in srgb,var(--hd,var(--tmd-accent)) 72%,#fff))}
.tmd-hd .ic{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;background:rgba(255,255,255,.22);font-size:17px;flex:none}
.tmd-hd .tt{font-family:var(--tmd-font-display);font-weight:800;font-size:16px;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tmd-hd .tt small{display:block;font-family:var(--tmd-font-body);font-weight:600;font-size:11px;opacity:.85;margin-top:1px}
.tmd-hd .pill{margin-inline-start:auto;font-size:11px;font-weight:800;padding:4px 9px;border-radius:999px;background:rgba(255,255,255,.25);text-transform:capitalize}
.tmd-hd .cnt{margin-inline-start:auto;min-width:22px;height:22px;padding:0 6px;border-radius:999px;background:var(--tmd-bad);color:#fff;font-size:12px;font-weight:800;display:grid;place-items:center}
.tmd-bd{padding:15px}
.tmd-empty{text-align:center;padding:26px 12px;color:var(--tmd-dim);font-size:.9rem}
.av{width:var(--av,42px);height:var(--av,42px);border-radius:50%;flex:none;display:grid;place-items:center;font-family:var(--tmd-font-display);font-weight:800;color:#fff;font-size:calc(var(--av,42px)*.4);line-height:1;text-align:center;background:var(--ac,var(--tmd-accent));box-shadow:0 2px 6px rgba(0,0,0,.18);overflow:hidden}
:host([data-tm-design="console"]) .av{box-shadow:0 0 0 1px color-mix(in srgb,var(--ac,var(--tmd-accent)) 70%,transparent),0 0 14px color-mix(in srgb,var(--ac,var(--tmd-accent)) 35%,transparent)}
.av ha-icon{--mdc-icon-size:calc(var(--av,42px)*.55);color:#fff}
.av img{width:100%;height:100%;object-fit:cover;border-radius:50%}
/* A child's photo, for the classic (non-designed) avatar wells.
   Every one of them is a sized, centred circle, so filling it is right; the
   chip variant is for the few places the icon sits inline beside text. */
.tm-face-img{width:100%;height:100%;border-radius:50%;object-fit:cover;display:block}
.tm-face-chip{width:18px;height:18px;border-radius:50%;object-fit:cover;display:block;flex:none}
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
:host([data-tm-design="console"]) .btn{color:#06101c;background:linear-gradient(135deg,var(--tmd-accent),var(--tmd-accent2));background:linear-gradient(135deg,var(--tmd-accent),color-mix(in srgb,var(--tmd-accent) 60%,var(--tmd-accent2)));box-shadow:0 0 14px color-mix(in srgb,var(--tmd-accent) 45%,transparent)}
.btn.ghost{background:var(--tmd-surface-2);color:var(--tmd-text);border:1px solid var(--tmd-border)}
:host([data-tm-design="console"]) .btn.ghost{box-shadow:none}
.btn.good{background:var(--tmd-good);color:#06301f}
.btn.bad{background:var(--tmd-bad);color:#3a0d0d}
.btn.round{border-radius:50%;width:38px;height:38px;padding:0;justify-content:center;font-size:18px}
.btn.sm{padding:6px 10px;font-size:12.5px}
.stat{background:var(--tmd-surface-2);border:1px solid var(--tmd-border);border-radius:var(--tmd-radius-sm);padding:10px 11px}
.stat .k{font-size:11px;font-weight:700;color:var(--tmd-dim);text-transform:uppercase;letter-spacing:.04em}
.stat .v{font-family:var(--tmd-font-display);font-weight:800;font-size:20px;margin-top:2px}
.grid{display:grid;gap:10px}

/* ── Graphite ─────────────────────────────────────────────────────────────
   Graphite has no render path of its own: it borrows the Clean Pro markup
   (LAYOUT_ALIAS) and is defined entirely by the rules below, so all cards
   adopt it at once. Selectors are :host([...]) + class, which out-specifies
   the '.tmd-check .c-num' pattern the cards use for their own design CSS. */
:host([data-tm-design="graphite"]) .tmd{border:1px solid var(--tmd-border);box-shadow:none}
/* The header band stays full colour — it is the one saturated element. */
:host([data-tm-design="graphite"]) .tmd-hd{padding:13px 15px 12px}
:host([data-tm-design="graphite"]) .tmd-hd .tt{font-weight:600;font-size:17px;letter-spacing:-.42px}
:host([data-tm-design="graphite"]) .tmd-hd .tt small{font-weight:400;font-size:13px;opacity:.78;letter-spacing:-.06px;margin-top:2px}
:host([data-tm-design="graphite"]) .tmd-hd .ic{border-radius:50%;background:rgba(255,255,255,.2)}
:host([data-tm-design="graphite"]) .tmd-hd .pill{background:transparent;padding:0;font-weight:500;font-size:15px;letter-spacing:-.2px;text-transform:none}
:host([data-tm-design="graphite"]) .tmd-hd .cnt{background:rgba(255,255,255,.22);font-weight:500;font-variant-numeric:tabular-nums}

/* Actions are near-black on light and near-white on dark. Deriving them from
   --tmd-text (not --tmd-accent) is what makes both directions invert. */
:host([data-tm-design="graphite"]) .btn{background:var(--tmd-text);color:var(--tmd-surface);
  font-family:var(--tmd-font-body);font-weight:500;letter-spacing:-.2px;
  border-radius:9px;box-shadow:none}
:host([data-tm-design="graphite"]) .btn.ghost{background:transparent;color:var(--tmd-text);border:1px solid var(--tmd-border)}
/* "good" marks the primary confirm (Approve / Dismiss). Graphite draws the
   primary action in near-black like every other one; green is reserved for
   reporting a completed state, not for a button. */
:host([data-tm-design="graphite"]) .btn.good{background:var(--tmd-text);color:var(--tmd-surface)}
:host([data-tm-design="graphite"]) .btn.bad{background:transparent;color:var(--tmd-bad)}
:host([data-tm-design="graphite"]) .btn.round{border-radius:50%}

/* Figures hold their column as they tick over. */
:host([data-tm-design="graphite"]) .num,
:host([data-tm-design="graphite"]) .big,
:host([data-tm-design="graphite"]) .stat .v{font-variant-numeric:tabular-nums;font-weight:600;letter-spacing:-.6px}
/* A chip reports a value here; it is not a highlight. */
:host([data-tm-design="graphite"]) .chip{background:transparent;border-color:transparent;color:var(--tmd-dim);
  font-weight:500;font-variant-numeric:tabular-nums}
:host([data-tm-design="graphite"]) .chip.soft{color:var(--tmd-dim)}
/* 4px track rather than a fat rounded pill. */
:host([data-tm-design="graphite"]) .bar{height:4px;border:0;border-radius:2px;background:var(--tmd-border)}
:host([data-tm-design="graphite"]) .bar>i{box-shadow:none}
:host([data-tm-design="graphite"]) .av{box-shadow:none}
:host([data-tm-design="graphite"]) .divide{background:var(--tmd-border)}
/* Stat cells are separated by hairlines, not drawn as nested boxes. */
:host([data-tm-design="graphite"]) .stat{background:transparent;border:0;border-radius:0;padding:0 12px}
:host([data-tm-design="graphite"]) .stat .k{text-transform:none;letter-spacing:-.04px;font-weight:400;font-size:12.5px}

/* Grouped inset list: one hairline container, separators starting past the
   leading control, and the leading badge reduced to a completion mark. */
:host([data-tm-design="graphite"]) .tmd-checklist{border:1px solid var(--tmd-border);border-radius:var(--tmd-radius-sm)}
:host([data-tm-design="graphite"]) .tmd-check{position:relative;padding:9px 12px;min-height:46px;box-sizing:border-box}
:host([data-tm-design="graphite"]) .tmd-check+.tmd-check{border-top:0}
:host([data-tm-design="graphite"]) .tmd-check+.tmd-check::before{content:"";position:absolute;top:0;inset-inline-start:46px;inset-inline-end:0;height:1px;background:var(--tmd-border)}
:host([data-tm-design="graphite"]) .tmd-check .c-num{width:22px;height:22px;border-radius:50%;
  background:transparent;border:1.5px solid var(--tmd-border);color:transparent;font-size:0}
:host([data-tm-design="graphite"]) .tmd-check.done .c-num{background:var(--tmd-good);border-color:var(--tmd-good);color:#fff;font-size:13px}
:host([data-tm-design="graphite"]) .tmd-check .c-name{font-weight:450;font-size:15px;letter-spacing:-.18px}
/* Dimming already says "done"; the strike-through is redundant noise. */
:host([data-tm-design="graphite"]) .tmd-check.done .c-name{text-decoration:none}
:host([data-tm-design="graphite"]) .tmd-check.done{opacity:.52}
/* Meta reads as quiet text, not as a row of coloured pills. */
:host([data-tm-design="graphite"]) .tmd-tag{background:transparent;border-color:transparent;
  color:var(--tmd-dim);font-weight:400;font-size:12.5px;letter-spacing:-.02px;padding:0;text-transform:none}
:host([data-tm-design="graphite"]) .tmd-tag.mandatory{color:var(--tmd-bad)}
:host([data-tm-design="graphite"]) .tmd-tag.photo{color:var(--tmd-dim)}

/* The decorative emoji tile in a card header is the loudest "kids app" tell
   left in the designed markup, and it is chrome rather than user data — the
   child card puts a real avatar here instead, which is kept. */
:host([data-tm-design="graphite"]) .tmd-hd .ic{display:none}
/* Sentence case throughout: tracked-out uppercase labels are not this style. */
:host([data-tm-design="graphite"]) .lbl,
:host([data-tm-design="graphite"]) .ap-group-label,
:host([data-tm-design="graphite"]) .rw-jackpot-label,
:host([data-tm-design="graphite"]) .tmd-badges .lbl{text-transform:none;letter-spacing:-.04px;font-weight:500;font-size:13px;color:var(--tmd-dim)}

/* Badge strip + next-badge: outlines rather than filled colour discs. */
:host([data-tm-design="graphite"]) .tmd-badges,
:host([data-tm-design="graphite"]) .tmd-next-badge{background:transparent;border:1px solid var(--tmd-border);border-radius:var(--tmd-radius-sm)}
:host([data-tm-design="graphite"]) .tmd-badge-mini{background:transparent;border:1px solid var(--tmd-border);box-shadow:none}
/* The glyphs inside these discs are drawn white for a filled tier colour;
   once the fill is gone they have to take the text colour or they vanish. */
:host([data-tm-design="graphite"]) .tmd-badge-mini,
:host([data-tm-design="graphite"]) .tmd-badge-mini ha-icon,
:host([data-tm-design="graphite"]) .tmd-next-badge .ic,
:host([data-tm-design="graphite"]) .tmd-next-badge .ic ha-icon{color:var(--tmd-text)}
:host([data-tm-design="graphite"]) .tmd-next-badge .ic{background:transparent;box-shadow:none}
:host([data-tm-design="graphite"]) .tmd-next-badge .bar{height:4px;border:0;background:var(--tmd-border)}
:host([data-tm-design="graphite"]) .tmd-next-badge .nm{font-weight:500}

/* Points display: tiles become a plain figure block. */
:host([data-tm-design="graphite"]) .cp-tile{background:transparent;border:1px solid var(--tmd-border);border-radius:var(--tmd-radius-sm);box-shadow:none}
:host([data-tm-design="graphite"]) .cp-pts,
:host([data-tm-design="graphite"]) .cp-total{font-variant-numeric:tabular-nums;font-weight:600;letter-spacing:-1.2px}
:host([data-tm-design="graphite"]) .cp-name{font-weight:500;letter-spacing:-.18px}
:host([data-tm-design="graphite"]) .cp-rank,
:host([data-tm-design="graphite"]) .cp-chips .chip{background:transparent;border-color:transparent;color:var(--tmd-dim);font-weight:500}

/* Rewards: a grouped list of fixed costs, not a deck of tinted cards. */
:host([data-tm-design="graphite"]) .rw-list{border:1px solid var(--tmd-border);border-radius:var(--tmd-radius-sm);gap:0}
:host([data-tm-design="graphite"]) .rw-card{background:transparent;border:0;border-radius:0;box-shadow:none}
:host([data-tm-design="graphite"]) .rw-card+.rw-card{border-top:1px solid var(--tmd-border)}
:host([data-tm-design="graphite"]) .rw-name{font-weight:500;letter-spacing:-.18px}
:host([data-tm-design="graphite"]) .rw-cost{font-variant-numeric:tabular-nums;font-weight:500;color:var(--tmd-dim)}
:host([data-tm-design="graphite"]) .rw-emoji{font-size:0}
:host([data-tm-design="graphite"]) .rw-pool-bar{height:4px;border:0;background:var(--tmd-border)}
:host([data-tm-design="graphite"]) .rw-jackpot{background:transparent;border:1px solid var(--tmd-border)}

/* Approvals: one grouped queue; the destructive action is text, not a slab. */
:host([data-tm-design="graphite"]) .ap-cp-item{background:transparent;border:0;border-radius:0;box-shadow:none}
:host([data-tm-design="graphite"]) .ap-cp-item+.ap-cp-item{border-top:1px solid var(--tmd-border)}
:host([data-tm-design="graphite"]) .ap-cp-title{font-weight:500;letter-spacing:-.18px}
:host([data-tm-design="graphite"]) .ap-cp-sub{color:var(--tmd-dim);font-weight:400}
:host([data-tm-design="graphite"]) .ap-cp-photo{border-radius:8px;border:1px solid var(--tmd-border)}
:host([data-tm-design="graphite"]) .ap-gold-soft{background:transparent;color:var(--tmd-dim)}
:host([data-tm-design="graphite"]) .approve-all-btn{background:transparent;color:#fff;border:1px solid rgba(255,255,255,.45);font-weight:500}

/* Leaderboard: rank, name, figure — right-aligned and tabular. */
:host([data-tm-design="graphite"]) .lb-cp-row{background:transparent;border:0;border-radius:0}
:host([data-tm-design="graphite"]) .lb-cp-row+.lb-cp-row{border-top:1px solid var(--tmd-border)}
:host([data-tm-design="graphite"]) .lb-cp-rank{background:transparent;border:0;color:var(--tmd-dim);font-variant-numeric:tabular-nums;font-weight:500}
:host([data-tm-design="graphite"]) .lb-cp-name{font-weight:500;letter-spacing:-.18px}
:host([data-tm-design="graphite"]) .lb-cp-score{font-variant-numeric:tabular-nums;font-weight:600;letter-spacing:-.6px}
:host([data-tm-design="graphite"]) .lb-cp-unit{color:var(--tmd-dim);font-weight:400}
:host([data-tm-design="graphite"]) .lb-cp-row.win{background:transparent}
:host([data-tm-design="graphite"]) .lb-cp-meta ha-icon{--mdc-icon-size:14px;vertical-align:-2px;margin-inline-end:3px;color:var(--tmd-dim)}

/* Overview: hairline-separated stats, then a grouped per-child list. */
:host([data-tm-design="graphite"]) .ov-kids{border:1px solid var(--tmd-border);border-radius:var(--tmd-radius-sm)}
:host([data-tm-design="graphite"]) .ov-kid{background:transparent;border:0;border-radius:0}
:host([data-tm-design="graphite"]) .ov-kid+.ov-kid{border-top:1px solid var(--tmd-border)}
:host([data-tm-design="graphite"]) .ov-kid-flag{background:transparent;border:0;color:var(--tmd-dim);font-weight:400}
:host([data-tm-design="graphite"]) .ov-alert{background:transparent;border:1px solid var(--tmd-border);color:var(--tmd-text)}
:host([data-tm-design="graphite"]) .ov-today .val,
:host([data-tm-design="graphite"]) .pts{font-variant-numeric:tabular-nums;font-weight:600;letter-spacing:-.6px}
:host([data-tm-design="graphite"]) .nm,
:host([data-tm-design="graphite"]) .ttl{font-weight:500;letter-spacing:-.18px}

/* Right-to-left (#979). apply() stamps dir on the host; an icon that points
   along the reading direction (chevron, undo, backspace) carries .tm-rtl-flip
   so it turns round with the layout. Text arrows (→ ↩) swap to their mirrored
   character instead, which leaves LTR markup untouched. Not design-scoped. */
:host([dir="rtl"]) .tm-rtl-flip,[dir="rtl"] .tm-rtl-flip{transform:scaleX(-1)}

/* Celebrations (__taskmate_fx). The card supplies the container and its
   positioning; these style what goes inside it. Not design-scoped. */
.tm-fx-p{position:absolute;top:0;display:block;animation:tm-fx-fall 3s linear forwards}
.tm-fx-emoji{line-height:1;background:none!important}
.tm-fx-snow .tm-fx-p{animation:tm-fx-snow 3.4s ease-in forwards}
.tm-fx-bats .tm-fx-p{animation:tm-fx-bats 2.8s ease-in-out forwards}
.tm-fx-sun .tm-fx-p{animation:tm-fx-snow 3s ease-in forwards}
.tm-fx-fireworks .tm-fx-p{width:9px;height:9px;border-radius:50%;opacity:0;animation:tm-fx-burst 1.3s ease-out forwards}
.tm-fx-stamp-mark,.tm-fx-sticker-mark{position:absolute;inset:0;margin:auto;width:fit-content;height:fit-content;transform:rotate(var(--tilt,-8deg))}
.tm-fx-stamp-mark{padding:10px 26px;border:6px solid #2e9e5b;border-radius:14px;color:#2e9e5b;background:rgba(255,255,255,.88);
  font:900 clamp(2rem,9vw,3.4rem)/1 system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;animation:tm-fx-stamp 1.8s cubic-bezier(.2,1.6,.4,1) forwards}
.tm-fx-sticker-mark{width:min(150px,40vw);height:min(150px,40vw);border-radius:50%;display:grid;place-items:center;font-size:min(88px,24vw);line-height:1;
  background:radial-gradient(circle at 35% 30%,#fff7c2,#ffd23c 60%,#f5a300);border:6px solid #fff;box-shadow:0 10px 28px rgba(0,0,0,.28);animation:tm-fx-peel 2s ease-out forwards}
@keyframes tm-fx-fall{0%{transform:translateY(-100px) rotate(0deg);opacity:1}100%{transform:translateY(100vh) rotate(720deg);opacity:0}}
@keyframes tm-fx-snow{0%{transform:translate(0,-60px) rotate(0deg);opacity:0}10%{opacity:1}100%{transform:translate(40px,100vh) rotate(200deg);opacity:0}}
@keyframes tm-fx-bats{0%{transform:translate(0,60vh) scale(.6);opacity:0}15%{opacity:1}50%{transform:translate(-30px,30vh) scale(1) rotate(-10deg)}100%{transform:translate(30px,-20vh) scale(.8) rotate(10deg);opacity:0}}
@keyframes tm-fx-burst{0%{transform:translate(0,0) scale(1);opacity:1}100%{transform:translate(var(--dx),var(--dy)) scale(.3);opacity:0}}
@keyframes tm-fx-stamp{0%{transform:scale(2.6) rotate(var(--tilt,-8deg));opacity:0}18%{transform:scale(1) rotate(var(--tilt,-8deg));opacity:1}80%{opacity:1}100%{transform:scale(1) rotate(var(--tilt,-8deg));opacity:0}}
@keyframes tm-fx-peel{0%{transform:rotate(-40deg) scale(.2);opacity:0}25%{transform:rotate(var(--tilt,-8deg)) scale(1.08);opacity:1}35%{transform:rotate(var(--tilt,-8deg)) scale(1)}80%{opacity:1}100%{transform:rotate(var(--tilt,-8deg)) scale(1);opacity:0}}
@media (prefers-reduced-motion:reduce){.tm-fx{display:none}}

/* Seasonal themes: the season's emoji pinned to the child's avatar. */
.tm-season-badge{position:absolute;bottom:-4px;inset-inline-start:-4px;width:20px;height:20px;border-radius:50%;display:grid;place-items:center;
  font-size:13px;line-height:1;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.3);pointer-events:none}
/* Graphite dark keeps --tmd-accent a dark grey so header bands stay legible
   with white text; anything that uses the accent as a TEXT colour would then
   vanish on the dark surface, so those take the text colour instead. */
:host([data-tm-design="graphite"][data-tm-dark]) .pts,
:host([data-tm-design="graphite"][data-tm-dark]) .pd-tab-cp.active,
:host([data-tm-design="graphite"][data-tm-dark]) .rp-name,
:host([data-tm-design="graphite"][data-tm-dark]) .rp-pct,
:host([data-tm-design="graphite"][data-tm-dark]) .rp-kid-pts,
:host([data-tm-design="graphite"][data-tm-dark]) .more,
:host([data-tm-design="graphite"][data-tm-dark]) .st-dot{color:var(--tmd-text)!important}
/* Touch screens: small buttons keep their look but get an invisible tap area
   about 40px tall, so a child's finger lands on "Done", "I'm stuck" or a
   filter chip instead of beside it. */
@media (pointer:coarse){
.btn,button.chip,button.tmd-tag,.filter-chip,.photo-badge.tm-help-btn,.cb-chip,.cb-seg button,.mode-btn,.pd-tab-cn,.pc-qchip,.quick-btn,.alloc-btn,.day-nav button,.undo-btn,.wl-hd-pill{position:relative}
.btn::after,button.chip::after,button.tmd-tag::after,.filter-chip::after,.photo-badge.tm-help-btn::after,.cb-chip::after,.cb-seg button::after,.mode-btn::after,.pd-tab-cn::after,.pc-qchip::after,.quick-btn::after,.alloc-btn::after,.day-nav button::after,.undo-btn::after,.wl-hd-pill::after{content:"";position:absolute;inset:-8px 0}
button.tmd-tag::after,.photo-badge.tm-help-btn::after,.mode-btn::after{inset:-12px 0}
.undo-btn::after,.pc-qchip::after,.quick-btn::after,.d-arrow::after{inset:-8px -4px}
.rw-deposit-input,.badges-filter,.deposit-custom input{min-height:36px}
}`;

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
   * Text direction of HA's current language (#979): "rtl" or "ltr". HA marks
   * RTL languages in its translation metadata (the same isRTL flag its own
   * computeRTL reads); for a language it has no metadata for, follow the
   * direction HA already gave the page.
   */
  let _lastDir = "ltr";
  function direction(hass) {
    const lang = hass && hass.language;
    const meta = hass && hass.translationMetadata && hass.translationMetadata.translations;
    const root = typeof document !== "undefined" && document.documentElement;
    if (lang && meta && meta[lang]) _lastDir = meta[lang].isRTL ? "rtl" : "ltr";
    else _lastDir = root && root.dir === "rtl" ? "rtl" : "ltr";
    return _lastDir;
  }

  /**
   * Keep number runs reading left to right inside right-to-left text (#995).
   * "3 / 1", "1,200 / 5,000" and "3-day" are one unit each, but the Unicode
   * bidi algorithm lays their parts out right to left in an RTL paragraph, so
   * "3 / 1" shows as "1 / 3" and "3-Day Streak" as "Day Streak-3". Each run is
   * wrapped in a left-to-right isolate, and a label holding one, or opening
   * with a number ("2 of 5 done", which otherwise reads "of 5 done 2"), is
   * wrapped in a first-strong isolate so it keeps its own reading order (an
   * English label stays English-ordered, a translated RTL one stays RTL). The
   * isolates (U+2066/2068 … U+2069) are invisible, but splitting a text run
   * still nudges glyph positioning by a sub-pixel, so they are only added
   * while the page is right-to-left: the direction last resolved by
   * direction(), which every card calls through apply() at the top of
   * render() and the panel calls in its hass setter (HA has one language per
   * page). In LTR, and for text with no number run that doesn't open with a
   * number, the value comes back untouched. Works on plain strings: Lit text,
   * the panel's HTML strings and translated messages alike.
   *
   * "3-day" mustn't follow a letter or hyphen ("re-3-day" stays as is). That
   * is matched as a captured lead character, not a lookbehind: Safari before
   * 16.4 (iOS 15) can't compile a lookbehind, and the SyntaxError took this
   * whole file down with it, blanking the child card (#1034).
   */
  const _NUM = String.raw`\p{Nd}+(?:[.,\u066B\u066C]\p{Nd}+)*`;
  const _NUM_RUN = new RegExp(String.raw`${_NUM}(?:\s*\/\s*${_NUM})+|(^|[^\p{L}-])(${_NUM}-\p{L}+)`, "gu");
  function ltrNums(text) {
    if (text === null || text === undefined || _lastDir !== "rtl") return text;
    const s = String(text);
    const out = s.replace(_NUM_RUN, (run, lead, word) =>
      word === undefined ? "\u2066" + run + "\u2069" : lead + "\u2066" + word + "\u2069");
    return out === s && !/^\p{Nd}/u.test(s) ? s : "\u2068" + out + "\u2069";
  }

  /**
   * Resolve the design AND stamp the host element: data-tm-design + (in dark
   * mode) data-tm-dark + dir. Cards call this once at the top of render() and
   * branch on the returned id. Returns "classic" when no design applies.
   */
  function apply(el, hass, config, entity) {
    const design = resolve(hass, config, entity);
    if (el) {
      el.setAttribute("data-tm-design", design);
      el.toggleAttribute("data-tm-dark", design !== "classic" && isDark(hass, el));
      el.setAttribute("dir", direction(hass));
    }
    // The host keeps the real id (its CSS keys off it); the card gets the
    // layout id so aliased styles reuse an existing render path.
    return LAYOUT_ALIAS[design] || design;
  }

  /** The real design id stamped on a card host (not the layout alias). */
  function active(el) {
    return (el && el.getAttribute("data-tm-design")) || "classic";
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
      { value: "accessible", label: label("accessible", "Accessible") },
      { value: "graphite", label: label("graphite", "Graphite") },
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

  /**
   * A child's own colour (#1078) made safe for a header with white text.
   * The panel's swatches include light ones (yellow), so the colour is
   * darkened in small steps until white text clears 3:1 (large bold header
   * text), or 4.5:1 under the accessible design. "" when unset or not a hex.
   */
  function _wcagLum(r, g, b) {
    const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  }
  function childColour(color, design) {
    const m = typeof color === "string" && color.match(/^#([0-9a-f]{6})$/i);
    if (!m) return "";
    let [r, g, b] = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
    const need = design === "accessible" ? 4.5 : 3;
    let changed = false;
    for (let i = 0; i < 20 && 1.05 / (_wcagLum(r, g, b) + 0.05) < need; i++) {
      [r, g, b] = [r, g, b].map((c) => Math.round(c * 0.9));
      changed = true;
    }
    if (!changed) return color.toLowerCase();
    return "#" + [r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("");
  }

  window.__taskmate_design = { IDS, resolve, isDark, direction, ltrNums, apply, active, editorOptions, styles, cssText, tokensCSS: TOKENS, colourPicker, childColour };

  // ── Seasonal themes ───────────────────────────────────────────────────────
  // The overview sensor names the season (only while a parent has it on and
  // today is in its window); this is how each one dresses a card. The header
  // stays full colour, just as a gradient. A card opts out with
  // `seasonal: false`.
  const SEASONS = {
    halloween: { emoji: "🎃", grad: "linear-gradient(135deg,#e8590c,#6a1b9a)", effect: "bats" },
    christmas: { emoji: "🎄", grad: "linear-gradient(135deg,#c62828,#2e7d32)", effect: "snow" },
    summer: { emoji: "☀️", grad: "linear-gradient(135deg,#e65100,#0277bd)", effect: "sun" },
  };
  window.__taskmate_season = window.__taskmate_season || function (attrs, config) {
    if (!attrs || (config && config.seasonal === false)) return null;
    const s = SEASONS[attrs.season];
    return s ? Object.assign({ id: attrs.season }, s) : null;
  };

  // ── Celebrations ──────────────────────────────────────────────────────────
  // One engine for the child and kiosk cards' tick-off effect.
  //   pick(style, season) -> the effect: the child's own style when they
  //     chose one, else the season's (bats / snow / sun), else confetti.
  //   spawn(effect) -> { effect, pieces }, or null under reduced motion.
  //   render(html, burst, { tint, label }) -> the pieces, for the card to put
  //     inside its own container (which carries "tm-fx tm-fx-<effect>").
  const FX_STYLES = ["confetti", "stamp", "fireworks", "sticker"];
  const FX_GLYPHS = { bats: ["🦇", "🦇", "🎃"], snow: ["❄️", "❄️", "⛄"], sun: ["☀️", "🌴", "🍦"] };
  const FX_COLOURS = ["#ff6b9d", "#9b59b6", "#3498db", "#2ecc71", "#f1c40f", "#e67e22"];
  function fxReduced() {
    try { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); } catch (e) { return false; }
  }
  function fxPick(style, season) {
    if (style && style !== "confetti" && FX_STYLES.indexOf(style) !== -1) return style;
    return (season && season.effect) || "confetti";
  }
  function fxSpawn(effect) {
    if (fxReduced()) return null;
    const r = Math.random;
    let pieces;
    if (effect === "stamp" || effect === "sticker") {
      pieces = [{ tilt: Math.round(r() * 16 - 12) }];
    } else if (effect === "fireworks") {
      pieces = [];
      for (let b = 0; b < 3; b++) {
        const x = 20 + r() * 60, y = 18 + r() * 40, delay = b * 0.35;
        for (let i = 0; i < 18; i++) {
          const a = (i / 18) * Math.PI * 2, d = 70 + r() * 50;
          pieces.push({ x, y, delay, dx: Math.round(Math.cos(a) * d), dy: Math.round(Math.sin(a) * d) });
        }
      }
    } else {
      pieces = Array.from({ length: FX_GLYPHS[effect] ? 24 : 50 }, () => ({
        x: r() * 100, delay: r() * 0.5, size: r() * 8 + 6, round: r() > 0.5,
      }));
    }
    return { effect, pieces };
  }
  function fxRender(html, burst, opts) {
    if (!burst || !html) return "";
    const o = opts || {};
    // A child's colour tints every other piece.
    const colours = o.tint ? FX_COLOURS.map((c, i) => (i % 2 ? c : o.tint)) : FX_COLOURS;
    const glyphs = FX_GLYPHS[burst.effect];
    if (burst.effect === "stamp") {
      return html`<div class="tm-fx-stamp-mark" style="--tilt:${burst.pieces[0].tilt}deg">${o.label || "✓"}</div>`;
    }
    if (burst.effect === "sticker") {
      return html`<div class="tm-fx-sticker-mark" style="--tilt:${burst.pieces[0].tilt}deg">⭐</div>`;
    }
    if (burst.effect === "fireworks") {
      return burst.pieces.map((p, i) => html`<i class="tm-fx-p" style="inset-inline-start:${p.x}%;top:${p.y}%;--dx:${p.dx}px;--dy:${p.dy}px;animation-delay:${p.delay}s;background:${colours[i % colours.length]}"></i>`);
    }
    if (glyphs) {
      return burst.pieces.map((p, i) => html`<i class="tm-fx-p tm-fx-emoji" style="inset-inline-start:${p.x}%;animation-delay:${p.delay}s;font-size:${Math.round(p.size * 2.4)}px">${glyphs[i % glyphs.length]}</i>`);
    }
    return burst.pieces.map((p, i) => html`<i class="tm-fx-p" style="inset-inline-start:${p.x}%;animation-delay:${p.delay}s;background:${colours[i % colours.length]};border-radius:${p.round ? "50%" : "0"};width:${p.size}px;height:${p.size}px"></i>`);
  }
  window.__taskmate_fx = window.__taskmate_fx || { STYLES: FX_STYLES, pick: fxPick, spawn: fxSpawn, render: fxRender, reduced: fxReduced };

  /**
   * The single place that decides what a chore looks like (#750).
   *
   * Precedence: uploaded picture → MDI icon → the call site's own fallback.
   *
   * Returns a plain descriptor rather than a template, for two reasons: this
   * file has no ES-module imports and no Lit dependency and must keep it that
   * way, and the `icon` case is not uniform across sites — the reorder card
   * renders chore.icon as an <ha-icon> only when it starts with "mdi:" and as
   * raw text otherwise, because the field can hold an emoji. A descriptor lets
   * each site keep its existing icon and fallback handling untouched.
   */
  window.__taskmate_chore_visual = window.__taskmate_chore_visual || function (chore) {
    if (chore && chore.image_url) return { kind: "image", url: chore.image_url };
    if (chore && chore.icon) return { kind: "icon", icon: chore.icon };
    return { kind: "none" };
  };

  /**
   * The same idea for a child's face.
   *
   * Precedence: child's photo → MDI avatar → the call site's fallback.
   *
   * `avatar_image` is resolved server-side from the picture entity chosen for
   * the child in TaskMate (empty when none is), so a card needs no knowledge
   * of person entities. A non-"mdi:" `avatar` is still treated as a picture URL,
   * which is what the points-display and approvals cards already did.
   *
   * Either URL ends up as an <img src>, so only the places a picture can
   * legitimately come from are accepted: TaskMate's and HA's own /api/ images,
   * /local/ and /hacsfiles/ assets, inline data:image/ and https://. Anything
   * else (javascript:, a bare host, a relative path) counts as no picture.
   *
   * Accepts a child object or a bare avatar string, because a few payloads
   * (reward claims, badges) carry only the string.
   */
  const AVATAR_URL_OK = /^(\/api\/|\/local\/|\/hacsfiles\/|data:image\/|https:\/\/)/;
  const avatarUrl = (value) => (typeof value === "string" && AVATAR_URL_OK.test(value) ? value : "");
  window.__taskmate_child_visual = window.__taskmate_child_visual || function (child) {
    const c = typeof child === "string" ? { avatar: child } : child || {};
    const photo = avatarUrl(c.avatar_image);
    if (photo) return { kind: "image", url: photo };
    const av = typeof c.avatar === "string" ? c.avatar : "";
    if (av.startsWith("mdi:")) return { kind: "icon", icon: av };
    const url = avatarUrl(av);
    if (url) return { kind: "image", url };
    return { kind: "none" };
  };

  // ── Card-picker entity suggestions (HA 2026.6+) ────────────────────────────
  // Custom cards may add getEntitySuggestion(hass, entityId) to their
  // window.customCards entry; when a user picks an entity in the card picker,
  // HA shows matching cards in a "Community" section. This shared helper lets
  // every TaskMate card opt in with a one-liner. We identify a TaskMate sensor
  // by its attribute SIGNATURE rather than its entity_id, so suggestions still
  // work after an entity_id rename and across multi-instance setups (e.g.
  // sensor.taskmate_overview_2). getEntitySuggestion runs at pick-time, by
  // which point every card module (and getStubConfig) is defined — so reading
  // this global from a card's registration closure is load-order safe.
  //
  //   role "overview" — the hub sensor (sensor.taskmate_overview): carries
  //                     points_name + the children[] summary. Almost every card
  //                     reads from it.
  //   role "activity" — the activity sensor (sensor.taskmate_activity):
  //                     recent_completions[] + photo_gallery. Used by the photo
  //                     gallery card.
  window.__taskmate_suggest = window.__taskmate_suggest || function (hass, entityId, type, role) {
    if (!entityId || typeof entityId !== "string" || !entityId.startsWith("sensor.")) return null;
    const a = hass && hass.states && hass.states[entityId] && hass.states[entityId].attributes;
    if (!a) return null;
    const isOverview = a.points_name !== undefined && Array.isArray(a.children);
    const isActivity = Array.isArray(a.recent_completions) && a.photo_gallery !== undefined;
    if (!(role === "activity" ? isActivity : isOverview)) return null;
    // Mirror the card's own stub defaults (mode/title/days/…) so a suggested
    // card lands configured exactly as if added manually, just on this entity.
    let stub = {};
    try {
      const el = customElements.get(type);
      if (el && typeof el.getStubConfig === "function") stub = el.getStubConfig() || {};
    } catch (e) { stub = {}; }
    return { config: Object.assign({}, stub, { type: "custom:" + type, entity: entityId }) };
  };

  // ── Birthday "first open today" gate (#924) ───────────────────────────────
  // True the first time it's asked about a child on a given day on this device,
  // false after that — so the birthday confetti plays once per day, not on every
  // hass update or page load. Shared by every card that celebrates, so a child
  // card and a points card on the same dashboard don't both go off. Keyed on
  // HA's time zone so the day rolls over with the backend, not the browser.
  // ── Boost windows ─────────────────────────────────────────────────────────
  // The overview sensor's `boosts` list holds live and upcoming boosts. The
  // cards work out live/upcoming/over from the clock themselves, so a boost
  // starts and ends on screen at the right second even between updates.
  //   __taskmate_boosts(attrs, childId?, nowMs?) -> boosts for that child
  //     (or all), each with status "active" | "upcoming", startsMs, endsMs.
  //   __taskmate_boost_for(boosts, choreId) -> the biggest live multiplier
  //     covering that chore, or 0.
  //   __taskmate_boost_seen(id) / __taskmate_boost_mark(id) -> the "show the
  //     takeover once per device per boost" gate, shared by every card.
  window.__taskmate_boosts = window.__taskmate_boosts || function (attrs, childId, nowMs) {
    const now = nowMs == null ? Date.now() : nowMs;
    const list = (attrs && Array.isArray(attrs.boosts)) ? attrs.boosts : [];
    const out = [];
    for (const b of list) {
      if (!b || !b.id) continue;
      const startsMs = Date.parse(b.starts_at);
      const endsMs = Date.parse(b.ends_at);
      if (isNaN(startsMs) || isNaN(endsMs) || now >= endsMs) continue;
      const kids = Array.isArray(b.child_ids) ? b.child_ids : [];
      if (childId && kids.length && kids.indexOf(childId) === -1) continue;
      out.push(Object.assign({}, b, { status: now < startsMs ? "upcoming" : "active", startsMs: startsMs, endsMs: endsMs }));
    }
    out.sort(function (a, b) { return (a.status === "active" ? 0 : 1) - (b.status === "active" ? 0 : 1) || a.startsMs - b.startsMs; });
    return out;
  };
  window.__taskmate_boost_for = window.__taskmate_boost_for || function (boosts, choreId) {
    let best = 0;
    for (const b of boosts || []) {
      if (b.status !== "active") continue;
      const chores = Array.isArray(b.chore_ids) ? b.chore_ids : [];
      if (chores.length && chores.indexOf(choreId) === -1) continue;
      best = Math.max(best, Number(b.multiplier) || 0);
    }
    return best;
  };
  (function () {
    const KEY = "taskmate_boosts_seen";
    const read = function () {
      try { const v = JSON.parse(window.localStorage.getItem(KEY) || "[]"); return Array.isArray(v) ? v : []; } catch (e) { return []; }
    };
    window.__taskmate_boost_seen = window.__taskmate_boost_seen || function (id) { return read().indexOf(id) !== -1; };
    window.__taskmate_boost_mark = window.__taskmate_boost_mark || function (id) {
      const seen = read();
      if (seen.indexOf(id) === -1) seen.push(id);
      try { window.localStorage.setItem(KEY, JSON.stringify(seen.slice(-40))); } catch (e) { /* private mode: shows again next load */ }
    };
  })();
  // "45:00" / "1:05:00"
  window.__taskmate_clock = window.__taskmate_clock || function (ms) {
    const s = Math.max(0, Math.ceil(ms / 1000));
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const pad = function (n) { return String(n).padStart(2, "0"); };
    return h ? h + ":" + pad(m) + ":" + pad(sec) : pad(m) + ":" + pad(sec);
  };

  window.__taskmate_birthday_once = window.__taskmate_birthday_once || function (hass, childId) {
    if (!childId) return false;
    let day;
    try {
      day = new Date().toLocaleDateString("en-CA", { timeZone: hass?.config?.time_zone || undefined });
    } catch (e) {
      day = new Date().toLocaleDateString("en-CA");
    }
    const KEY = "taskmate_celebrated_day";
    let seen;
    try { seen = JSON.parse(window.localStorage.getItem(KEY) || "{}") || {}; } catch (e) { seen = {}; }
    if (seen[childId] === day) return false;
    seen[childId] = day;
    try { window.localStorage.setItem(KEY, JSON.stringify(seen)); } catch (e) { /* private mode: plays each load */ }
    return true;
  };

  // ── Chore-photo lightbox ───────────────────────────────────────────────────
  // A single shared, design-AGNOSTIC image viewer for evidence photos. It is
  // mounted on document.body (NOT inside any card's shadow root), so it paints
  // above every card, the admin panel, and HA's own stacking contexts no matter
  // how deeply the trigger is nested or whether an ancestor clips overflow.
  // Callers pass an ALREADY safety-checked URL (tmSafePhotoUrl/_safePhotoUrl),
  // an optional caption string, and an optional localised close label. Closes on
  // backdrop click, the ✕ button, or Escape. Deliberately uses no --tmd-* tokens
  // so it looks right under all four design styles.
  window.__taskmate_lightbox = window.__taskmate_lightbox || (function () {
    let overlay = null, imgEl = null, capEl = null, closeBtn = null, lastFocus = null;

    function onKey(e) { if (e.key === "Escape") { e.stopPropagation(); close(); } }

    function close() {
      if (!overlay) return;
      overlay.classList.remove("open");
      document.body.style.overflow = "";
      document.removeEventListener("keydown", onKey, true);
      window.setTimeout(() => { if (overlay) overlay.style.display = "none"; if (imgEl) imgEl.src = ""; }, 180);
      if (lastFocus && typeof lastFocus.focus === "function") { try { lastFocus.focus(); } catch (e) {} }
      lastFocus = null;
    }

    function build() {
      overlay = document.createElement("div");
      overlay.className = "tm-lightbox";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");
      overlay.innerHTML =
        "<style>" +
        ".tm-lightbox{position:fixed;inset:0;z-index:2147483000;display:none;flex-direction:column;" +
        "align-items:center;justify-content:center;gap:14px;box-sizing:border-box;" +
        "padding:max(16px,var(--safe-area-inset-top,env(safe-area-inset-top,0px))) 16px max(16px,var(--safe-area-inset-bottom,env(safe-area-inset-bottom,0px)));" +
        "background:rgba(8,10,14,.86);opacity:0;transition:opacity .18s ease;" +
        "font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;}" +
        ".tm-lightbox.open{opacity:1;}" +
        ".tm-lightbox img{max-width:92vw;max-height:80vh;object-fit:contain;border-radius:10px;" +
        "background:#111;box-shadow:0 18px 60px rgba(0,0,0,.6);}" +
        ".tm-lightbox .tm-lb-cap{color:#f4f6fb;font-size:14px;font-weight:600;text-align:center;" +
        "max-width:92vw;line-height:1.4;text-shadow:0 1px 2px rgba(0,0,0,.6);}" +
        ".tm-lightbox .tm-lb-close{position:absolute;top:14px;inset-inline-end:16px;width:42px;height:42px;border:none;" +
        "border-radius:50%;background:rgba(255,255,255,.14);color:#fff;font-size:22px;line-height:1;" +
        "cursor:pointer;transition:background .15s;}" +
        ".tm-lightbox .tm-lb-close:hover{background:rgba(255,255,255,.28);}" +
        "@media (prefers-reduced-motion:reduce){.tm-lightbox{transition:none;}}" +
        "</style>" +
        "<button class=\"tm-lb-close\" type=\"button\">✕</button>" +
        "<img alt=\"\">" +
        "<div class=\"tm-lb-cap\"></div>";
      document.body.appendChild(overlay);
      imgEl = overlay.querySelector("img");
      capEl = overlay.querySelector(".tm-lb-cap");
      closeBtn = overlay.querySelector(".tm-lb-close");
      closeBtn.addEventListener("click", close);
      // Only a click on the dimmed backdrop itself (not image/caption/button) closes.
      overlay.addEventListener("click", (e) => { if (e.target === overlay) close(); });
    }

    return function (src, caption, closeLabel) {
      if (!src) return;
      if (!overlay) build();
      lastFocus = document.activeElement;
      imgEl.src = src;
      if (caption) { capEl.textContent = caption; capEl.style.display = ""; }
      else { capEl.textContent = ""; capEl.style.display = "none"; }
      closeBtn.setAttribute("aria-label", closeLabel || "Close");
      closeBtn.title = closeLabel || "Close";
      overlay.style.display = "flex";
      void overlay.offsetWidth; // force reflow so the opacity transition runs from 0
      overlay.classList.add("open");
      document.body.style.overflow = "hidden";
      document.addEventListener("keydown", onKey, true);
      closeBtn.focus();
    };
  })();
})();
