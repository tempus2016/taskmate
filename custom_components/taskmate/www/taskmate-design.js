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

  // Token blocks mirror docs/design/redesigns/taskmate-redesigns.html
  // (.dir-a / .dir-b / .dir-c) with the --tmd- prefix.
  const TOKENS = `
@import url('https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&family=Nunito:wght@400;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700;800&family=Manrope:wght@500;600;700;800&display=swap');

[data-tm-design="playroom"]{
  --tmd-bg:#FFF7EC;--tmd-surface:#FFFFFF;--tmd-surface-2:#FFF0DB;--tmd-border:#F0DFC4;
  --tmd-text:#3A2E26;--tmd-dim:#9C8676;
  --tmd-accent:#7C5CE6;--tmd-accent2:#FFC23C;--tmd-good:#36C58E;--tmd-warn:#FFB020;--tmd-bad:#FF6B6B;--tmd-gold:#FFC23C;
  --tmd-radius:22px;--tmd-radius-sm:14px;--tmd-shadow:0 10px 24px rgba(123,92,230,.12);--tmd-hd-text:#fff;
  --tmd-font-display:"Baloo 2",cursive;--tmd-font-body:"Nunito",sans-serif;--tmd-font-mono:"Baloo 2",cursive;
  --tmd-c1:#FF6B6B;--tmd-c2:#4ECDC4;--tmd-c3:#FFB020;--tmd-c4:#6C8DFF;--tmd-c5:#C77DFF;--tmd-c6:#45D483;
}
[data-tm-design="console"]{
  --tmd-bg:#0E1320;--tmd-surface:#161D2E;--tmd-surface-2:#1E2740;--tmd-border:#2A3550;
  --tmd-text:#EAF0FF;--tmd-dim:#8A97B8;
  --tmd-accent:#3DDBFF;--tmd-accent2:#FF4D9D;--tmd-good:#4BE08B;--tmd-warn:#FFCB45;--tmd-bad:#FF5A7A;--tmd-gold:#FFCB45;
  --tmd-radius:12px;--tmd-radius-sm:8px;--tmd-shadow:0 10px 28px rgba(0,0,0,.5);--tmd-hd-text:#06101c;
  --tmd-font-display:"Space Grotesk",sans-serif;--tmd-font-body:"Inter",sans-serif;--tmd-font-mono:"JetBrains Mono",monospace;
  --tmd-c1:#3DDBFF;--tmd-c2:#FF4D9D;--tmd-c3:#FFCB45;--tmd-c4:#7C5CFF;--tmd-c5:#4BE08B;--tmd-c6:#FF8A3D;
}
[data-tm-design="cleanpro"]{
  --tmd-bg:#F6F7F9;--tmd-surface:#FFFFFF;--tmd-surface-2:#F1F3F6;--tmd-border:#E5E8EC;
  --tmd-text:#1A2230;--tmd-dim:#6B7585;
  --tmd-accent:#4F6BED;--tmd-accent2:#0FB5A8;--tmd-good:#16A36B;--tmd-warn:#E0A100;--tmd-bad:#DC4C4C;--tmd-gold:#E0A100;
  --tmd-radius:14px;--tmd-radius-sm:9px;--tmd-shadow:0 1px 2px rgba(16,24,40,.06),0 8px 18px rgba(16,24,40,.06);--tmd-hd-text:#fff;
  --tmd-font-display:"Manrope",sans-serif;--tmd-font-body:"Inter",sans-serif;--tmd-font-mono:"Inter",sans-serif;
  --tmd-c1:#4F6BED;--tmd-c2:#0FB5A8;--tmd-c3:#E0A100;--tmd-c4:#7A5AF0;--tmd-c5:#E0567A;--tmd-c6:#2BA84A;
}`;

  if (!document.getElementById("taskmate-design-tokens")) {
    const styleEl = document.createElement("style");
    styleEl.id = "taskmate-design-tokens";
    styleEl.textContent = TOKENS;
    document.head.appendChild(styleEl);
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

  window.__taskmate_design = { IDS, resolve, editorOptions };
})();
