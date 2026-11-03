/**
 * TaskMate kid onboarding tour — shared by the Child card and the Kiosk.
 *
 * A first-run walkthrough that spotlights REAL elements on the real card: a
 * dark scrim with a cut-out round the element, and a tooltip beside it. The
 * card underneath stays live, so a child can tap the very button the tour is
 * pointing at.
 *
 * The card owns the "which element is step N" question (it passes a resolver,
 * because each design draws its own markup); this module owns everything
 * else: whether to start, which steps survive, where the tooltip goes, the
 * read-aloud button, keyboard handling and the per-browser flag.
 *
 * Old-iPad rules (#1126): the scrim is ONE box-shadow on the cut-out, there
 * is no animation and no backdrop-filter, and the layout is measured only when
 * the step changes or the card itself changes size — never on a timer, even
 * though the kiosk re-renders every second.
 *
 * Exposed as window.__taskmate_tour (pure helpers, unit-tested in node) plus
 * the <taskmate-tour> element. No ES module imports, like the other shared
 * layers.
 */
(function () {
  const g = typeof window !== "undefined" ? window : globalThis;
  if (g.__taskmate_tour) return;

  const STEPS = ["hello", "tick", "points", "streak", "rewards"];
  const PRE_READER_STEPS = ["pre_tick", "pre_points", "pre_rewards"];
  const FLAG_PREFIX = "taskmate_tour_";

  /** Should a card start the tour for this child right now? */
  function shouldStart(opts) {
    const o = opts || {};
    const child = o.child;
    if (!child || child.is_adult) return false;
    if (o.config && o.config.show_tour === false) return false;
    // The overview carries `tour` only while the setting is on, and each
    // child's `tour_done` only then too: missing means "not offered".
    if (!o.attrs || !o.attrs.tour) return false;
    if (child.tour_done !== false) return false;
    if (o.localFlag) return false;
    // A grown-up's own phone (a TaskMate parent account) never gets a kid's
    // tour — they would only dismiss it on the child's behalf.
    const ids = o.attrs.parent_user_ids;
    if (o.userId && Array.isArray(ids) && ids.indexOf(o.userId) !== -1) return false;
    return true;
  }

  /** The step keys to show: the variant's list, minus steps with nothing to point at. */
  function selectSteps(preReader, has) {
    const list = preReader ? PRE_READER_STEPS : STEPS;
    return list.filter((k) => !!has(k));
  }

  /**
   * Where the tooltip goes, in the overlay box's own coordinates.
   *   anchor: {top,left,width,height} or null; tip: {width,height};
   *   box: {width,height}. Prefers below, then above, else overlaps the
   *   bottom of the anchor as best it can; never leaves the box.
   */
  function place(anchor, tip, box, gap) {
    const pad = 8;
    const gp = gap == null ? 12 : gap;
    const w = Math.min(tip.width, Math.max(0, box.width - pad * 2));
    const h = tip.height;
    if (!anchor) {
      return {
        side: "center",
        width: w,
        top: Math.max(pad, Math.round((box.height - h) / 2)),
        left: Math.round((box.width - w) / 2), /* rtl-ok: physical box coordinates, from getBoundingClientRect */
        arrow: null,
      };
    }
    const centre = anchor.left + anchor.width / 2;
    const left = Math.round(Math.max(pad, Math.min(box.width - w - pad, centre - w / 2)));
    const arrow = Math.round(Math.max(18, Math.min(w - 18, centre - left)));
    const below = anchor.top + anchor.height + gp;
    const above = anchor.top - gp - h;
    if (below + h <= box.height - pad) return { side: "below", width: w, top: Math.round(below), left, arrow };
    if (above >= pad) return { side: "above", width: w, top: Math.round(above), left, arrow };
    // Neither fits (a short card): sit as low as possible without leaving
    // the box, and drop the arrow — it would point at the wrong thing.
    const top = Math.max(pad, Math.min(box.height - h - pad, below));
    return { side: "over", width: w, top: Math.round(top), left, arrow: null };
  }

  function _store() {
    try {
      return g.localStorage || null;
    } catch (e) {
      return null;
    }
  }

  /** This browser's record for a child: {status, step} or null. */
  function readFlag(childId) {
    const s = _store();
    if (!s || !childId) return null;
    try {
      const raw = s.getItem(FLAG_PREFIX + childId);
      if (!raw) return null;
      const v = JSON.parse(raw);
      return v && (v.status === "done" || v.status === "skipped") ? v : null;
    } catch (e) {
      return null;
    }
  }

  function writeFlag(childId, status, step) {
    const s = _store();
    if (!s || !childId) return;
    try {
      s.setItem(FLAG_PREFIX + childId, JSON.stringify({ status, step: step || 1 }));
    } catch (e) {
      /* private mode / full: the backend record still counts */
    }
  }

  function clearFlag(childId) {
    const s = _store();
    if (!s || !childId) return;
    try {
      s.removeItem(FLAG_PREFIX + childId);
    } catch (e) {
      /* nothing to do */
    }
  }

  /**
   * Reconcile this browser's flag with the server for one child, and say
   * whether the flag still blocks the tour. The flag only bridges the gap
   * until the server has the answer: once `tour_done` is true it's dropped,
   * so a grown-up's "Show again" works on this tablet too. While the server
   * still says false, the write is retried (once per page) — it was offline.
   */
  const _retried = {};
  function syncFlag(hass, child) {
    if (!child || !child.id) return null;
    const flag = readFlag(child.id);
    if (!flag) return null;
    if (child.tour_done === true || child.tour_done === undefined) {
      clearFlag(child.id);
      return null;
    }
    if (!_retried[child.id] && hass && typeof hass.callWS === "function") {
      _retried[child.id] = true;
      mark(hass, child.id, flag.status, flag.step);
    }
    return flag;
  }

  function mark(hass, childId, status, step) {
    if (!hass || typeof hass.callWS !== "function") return Promise.resolve(null);
    return hass
      .callWS({ type: "taskmate/tour/mark", child_id: String(childId), status, step: Math.max(1, Math.min(5, step || 1)) })
      .catch((err) => {
        console.warn("TaskMate: couldn't save the tour", err);
        return null;
      });
  }

  function speak(hass, childId, step) {
    if (!hass || typeof hass.callWS !== "function") return Promise.resolve(null);
    const language = (hass.locale && hass.locale.language) || hass.language || "";
    return hass
      .callWS({ type: "taskmate/tour/speak", child_id: String(childId), step, language })
      .catch((err) => {
        console.warn("TaskMate: couldn't read the tour step aloud", err);
        return null;
      });
  }

  // Big pictures for the pre-reader variant. The points step draws the
  // family's own points icon instead of an emoji.
  const PRE_EMOJI = { pre_tick: "👆", pre_rewards: "🎁" };

  // z-index 3: above the card's own rows (none of which set one), but under
  // Home Assistant's fixed app toolbar (z-index 4) and its dialogs. The card
  // isn't a stacking context, so a higher value painted the scrim over the
  // toolbar once the dashboard scrolled the card up underneath it.
  const STYLE = `
    :host { position: absolute; inset: 0; z-index: 3; pointer-events: none; overflow: hidden; border-radius: inherit; display: block; }
    :host([data-paused]) { display: none; }
    .hole { position: absolute; border-radius: 12px; pointer-events: none;
      box-shadow: 0 0 0 9999px rgba(10, 20, 40, .72); outline: 3px solid #ffd54f; outline-offset: 0; }
    .hole.none { top: 0; left: 0; width: 0; height: 0; outline: none; } /* rtl-ok: an empty box at the origin */
    :host([data-design="accessible"]) .hole { outline: 4px solid #fff;
      box-shadow: 0 0 0 4px #fff, 0 0 0 8px #000, 0 0 0 9999px rgba(0, 0, 0, .82); }
    .tip { position: absolute; pointer-events: auto; box-sizing: border-box; background: #fff; color: #212121;
      border-radius: 14px; padding: 14px 16px; box-shadow: 0 10px 30px rgba(0, 0, 0, .35);
      font-family: var(--tmd-font-body, var(--paper-font-body1_-_font-family, inherit)); outline: none; }
    /* Focus lands on the tooltip itself (so Enter/Esc work at once); its own
       ring would just frame the whole box — the buttons carry the rings. */
    .tip:focus, .tip:focus-visible { outline: none; }
    .arrow { position: absolute; width: 16px; height: 16px; background: inherit; transform: rotate(45deg); margin-left: -8px; } /* rtl-ok: centred on a physical x set from the anchor's rect */
    .tip.below .arrow { top: -8px; }
    .tip.above .arrow { bottom: -8px; }
    h2 { font-size: 16px; line-height: 1.25; margin: 0 0 4px; font-weight: 700; font-family: var(--tmd-font-display, inherit); }
    p { margin: 0 0 12px; font-size: 14px; line-height: 1.4; color: #444; }
    .foot { display: flex; align-items: center; gap: 8px; }
    .grow { flex: 1; }
    .dots { display: flex; gap: 5px; align-items: center; }
    .dots i { width: 7px; height: 7px; border-radius: 50%; background: #cfd8dc; display: inline-block; }
    .dots i.on { background: #03a9f4; width: 18px; border-radius: 4px; }
    button { font: inherit; cursor: pointer; border-radius: 8px; min-height: 36px; padding: 6px 14px; font-size: 14px; font-weight: 600; }
    .next { background: #03a9f4; color: #fff; border: 1px solid #03a9f4; }
    .skip { background: transparent; color: #555; border: 1px solid #d0d4d8; }
    .spk { width: 36px; padding: 0; border-radius: 50%; background: #fff; border: 1px solid #d0d4d8; font-size: 16px; line-height: 1; }
    button:focus-visible { outline: 3px solid #03a9f4; outline-offset: 2px; }
    /* Pre-reader: one big picture, one short line, one big OK. */
    .tip.pre { text-align: center; border-radius: 18px; padding: 18px 20px; }
    .pre .em { font-size: 56px; line-height: 1; display: block; }
    .pre .em ha-icon { --mdc-icon-size: 60px; color: #f9a825; }
    .pre h2 { font-size: 22px; font-weight: 800; margin: 8px 0 2px; }
    .pre p { font-size: 15px; color: #666; margin: 0 0 12px; }
    .pre .foot { justify-content: center; gap: 12px; }
    .pre .spk { width: 52px; min-height: 52px; font-size: 24px; }
    .pre .next { font-size: 18px; min-height: 52px; padding: 10px 26px; border-radius: 12px; }
    .pre .dots { justify-content: center; margin-top: 12px; }
    /* Dark themes: a dark tooltip, same layout. */
    :host([data-dark]) .tip { background: #23262b; color: #f1f3f5; box-shadow: 0 10px 30px rgba(0, 0, 0, .6); }
    :host([data-dark]) p { color: #c5cad1; }
    :host([data-dark]) .skip { color: #d6dae0; border-color: #4a4f57; }
    :host([data-dark]) .spk { background: #2d3138; border-color: #4a4f57; color: #fff; }
    :host([data-dark]) .dots i { background: #4a4f57; }
    :host([data-dark]) .dots i.on { background: #4fc3f7; }
    /* Accessible design: black on white, thick rings, bigger type. */
    :host([data-design="accessible"]) .tip { background: #fff; color: #000; border: 3px solid #000; }
    :host([data-design="accessible"]) p { color: #000; font-size: 16px; }
    :host([data-design="accessible"]) h2 { font-size: 19px; }
    :host([data-design="accessible"]) .next { background: #000; border-color: #000; color: #fff; }
    :host([data-design="accessible"]) .skip, :host([data-design="accessible"]) .spk { color: #000; border: 2px solid #000; background: #fff; }
    :host([data-design="accessible"]) .dots i { background: #fff; border: 2px solid #000; width: 8px; height: 8px; }
    :host([data-design="accessible"]) .dots i.on { background: #000; width: 18px; }
    :host([data-design="accessible"]) button:focus-visible { outline: 4px solid #ffbf00; }
    :host([data-design="accessible"]) .tip:focus-visible { box-shadow: 0 0 0 4px #ffbf00, 0 10px 30px rgba(0, 0, 0, .35); }
  `;

  function _esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  const HTMLEl = g.HTMLElement || function () {};

  /**
   * <taskmate-tour>. Set `.opts` (every render is fine — it only re-measures
   * when the step changes or the card changes size):
   *   resolve:   (key) => Element|null — the card's anchor for a step; steps
   *              with no anchor when the tour starts are left out
   *   t:         (key, params) => string — the card's translator
   *   params:    { name, points_name } for the step text
   *   pointsIcon, preReader, speak (show the speaker), autoRead,
   *   design, dark, paused (hide while the card celebrates; resumes on the same step),
   *   onSpeak(key), onFinish(status, stepNumber), onActivity()
   */
  class TaskMateTour extends HTMLEl {
    constructor() {
      super();
      this._opts = null;
      this._i = 0;
      this._built = false;
      this._raf = 0;
      this._spoken = -1;
      this._onResize = () => this._schedule();
      this._onKey = (e) => this._keydown(e);
    }

    set opts(v) {
      const first = !this._opts;
      this._opts = v || null;
      if (!this._opts) return;
      if (this._opts.design) this.setAttribute("data-design", this._opts.design);
      else this.removeAttribute("data-design");
      if (this._opts.dark) this.setAttribute("data-dark", "");
      else this.removeAttribute("data-dark");
      // A celebration on the card steps the tour aside (kept on its step),
      // so the "AWESOME!" popup is never shown dimmed under the scrim.
      const paused = !!this._opts.paused;
      if (paused !== this.hasAttribute("data-paused")) {
        if (paused) this.setAttribute("data-paused", "");
        else {
          this.removeAttribute("data-paused");
          this._schedule();
        }
      }
      if (first && this.isConnected) this._start();
    }

    get opts() {
      return this._opts;
    }

    connectedCallback() {
      if (!this.shadowRoot) this.attachShadow({ mode: "open" });
      // The overlay is positioned against the card. Child cards already make
      // ha-card a containing block; make sure, without touching an existing value.
      const parent = this.parentElement;
      if (parent && g.getComputedStyle && g.getComputedStyle(parent).position === "static") {
        parent.style.position = "relative";
        this._fixedParent = parent;
      }
      if (typeof g.ResizeObserver === "function") {
        this._ro = new g.ResizeObserver(this._onResize);
        this._ro.observe(this);
      }
      if (g.addEventListener) g.addEventListener("resize", this._onResize);
      if (this._opts) this._start();
    }

    disconnectedCallback() {
      if (this._ro) this._ro.disconnect();
      this._ro = null;
      if (g.removeEventListener) g.removeEventListener("resize", this._onResize);
      if (this._raf && g.cancelAnimationFrame) g.cancelAnimationFrame(this._raf);
      this._raf = 0;
      if (this._fixedParent) {
        this._fixedParent.style.position = "";
        this._fixedParent = null;
      }
      if (this._grownEl) {
        this._grownEl.style.minHeight = this._grewParent || "";
        this._grownEl = null;
      }
      this._grewParent = undefined;
      this._built = false;
    }

    _start() {
      if (this._built || !this.shadowRoot) return;
      this._built = true;
      this._i = 0;
      // One frame later the card's own rows are on the page, so the step
      // list can be cut down to the steps with something to point at.
      const raf = g.requestAnimationFrame || ((fn) => setTimeout(fn, 16));
      raf(() => {
        if (!this._built || !this._opts) return;
        const o = this._opts;
        this._list = selectSteps(!!o.preReader, (k) => (o.resolve ? o.resolve(k) : null));
        if (this._list.length) this._paint(true);
      });
    }

    _steps() {
      return this._list || [];
    }

    _schedule() {
      if (!this._built || this._raf) return;
      const raf = g.requestAnimationFrame || ((fn) => setTimeout(fn, 16));
      this._raf = raf(() => {
        this._raf = 0;
        this._layout(false);
      });
    }

    _paint(focus) {
      const o = this._opts;
      const steps = this._steps();
      const key = steps[this._i];
      if (!o || !key) return;
      const t = o.t || ((k) => k);
      const params = o.params || {};
      const title = t(`notify.tour_${key}_title`, params);
      const body = t(`notify.tour_${key}_body`, params);
      const last = this._i === steps.length - 1;
      const dots = steps.map((_, n) => `<i class="${n === this._i ? "on" : ""}"></i>`).join("");
      const stepOf = t("tour.step_of", { n: this._i + 1, total: steps.length });
      const spk = o.speak
        ? `<button type="button" class="spk" data-a="speak" aria-label="${_esc(t("tour.read_aloud"))}" title="${_esc(t("tour.read_aloud"))}">🔊</button>`
        : "";
      let inner;
      if (o.preReader) {
        const pic = key === "pre_points"
          ? `<ha-icon icon="${_esc(o.pointsIcon || "mdi:star")}"></ha-icon>`
          : _esc(PRE_EMOJI[key] || "👆");
        inner = `
          <span class="em" aria-hidden="true">${pic}</span>
          <h2 id="tt">${_esc(title)}</h2>
          <p>${_esc(body)}</p>
          <div class="foot">${spk}<button type="button" class="next" data-a="next">${_esc(t("tour.ok"))} 👍</button></div>
          <div class="dots" role="img" aria-label="${_esc(stepOf)}">${dots}</div>`;
      } else {
        inner = `
          <h2 id="tt">${_esc(title)}</h2>
          <p>${_esc(body)}</p>
          <div class="foot">
            <div class="dots" role="img" aria-label="${_esc(stepOf)}">${dots}</div>
            <span class="grow"></span>
            ${spk}
            <button type="button" class="skip" data-a="skip">${_esc(t("tour.skip"))}</button>
            <button type="button" class="next" data-a="next">${_esc(last ? t("tour.done") : t("tour.next"))}</button>
          </div>`;
      }
      this.shadowRoot.innerHTML = `<style>${STYLE}</style>
        <div class="hole"></div>
        <div class="tip ${o.preReader ? "pre" : ""}" role="dialog" aria-modal="false" aria-labelledby="tt"
             aria-label="${_esc(t("tour.label"))}" tabindex="-1"><span class="arrow"></span>${inner}</div>`;
      const tip = this.shadowRoot.querySelector(".tip");
      tip.addEventListener("click", (e) => this._click(e));
      tip.addEventListener("keydown", this._onKey);
      this._layout(true);
      if (focus && tip.focus) {
        try {
          tip.focus({ preventScroll: true });
        } catch (e) {
          tip.focus();
        }
      }
      // Pre-reader children hear each step without a tap, when allowed.
      if (o.preReader && o.autoRead && o.speak && this._spoken !== this._i) {
        this._spoken = this._i;
        if (o.onSpeak) o.onSpeak(key);
      }
    }

    _layout(scroll) {
      const o = this._opts;
      const root = this.shadowRoot;
      if (!o || !root) return;
      const tip = root.querySelector(".tip");
      const hole = root.querySelector(".hole");
      if (!tip || !hole) return;
      const key = this._steps()[this._i];
      const el = o.resolve ? o.resolve(key) : null;
      if (scroll && el && el.scrollIntoView) {
        try {
          el.scrollIntoView({ block: "nearest" });
        } catch (e) {
          /* old engines without options */
        }
      }
      const r0 = this.getBoundingClientRect();
      const box = { top: r0.top, left: r0.left, width: r0.width, height: r0.height }; /* rtl-ok: physical rect */
      let anchor = null;
      if (el && el.getBoundingClientRect) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.height > 0) {
          const p = 4;
          anchor = {
            top: Math.max(0, r.top - box.top - p),
            left: Math.max(0, r.left - box.left - p), /* rtl-ok: physical rect maths */
            width: Math.min(box.width, r.width + p * 2),
            height: r.height + p * 2,
          };
        }
      }
      if (anchor) {
        hole.className = "hole";
        hole.style.cssText = `top:${anchor.top}px;left:${anchor.left}px;width:${anchor.width}px;height:${anchor.height}px`; /* rtl-ok: physical rect */
      } else {
        // Nothing to point at any more (the row just went): a plain scrim.
        hole.className = "hole none";
        hole.style.cssText = "";
      }
      const maxW = o.preReader ? 320 : 300;
      tip.style.width = `${Math.min(maxW, Math.max(0, box.width - 16))}px`;
      const tipH = tip.offsetHeight || 160;
      // A short card (one row of picture tiles) can't hold the tooltip beside
      // its anchor. Grow the card just enough, once per step — the overlay is
      // clipped to the card, so this is the only way not to cover the anchor.
      const parent = this.parentElement;
      if (anchor && parent && parent.style) {
        const need = Math.ceil(anchor.top + anchor.height + 12 + tipH + 12);
        const fitsAbove = anchor.top - 12 - tipH >= 8;
        if (!fitsAbove && need > box.height && need - box.height < 600) {
          if (!this._grownEl) {
            this._grewParent = parent.style.minHeight || "";
            this._grownEl = parent;
          }
          parent.style.minHeight = `${need}px`;
          box.height = Math.max(box.height, need);
        }
      }
      const pos = place(anchor, { width: maxW, height: tipH }, { width: box.width, height: box.height });
      tip.className = `tip ${o.preReader ? "pre" : ""} ${pos.side}`;
      tip.style.top = `${pos.top}px`;
      tip.style.left = `${pos.left}px`;
      tip.style.width = `${pos.width}px`;
      const arrow = tip.querySelector(".arrow");
      if (arrow) {
        arrow.style.display = pos.arrow == null ? "none" : "";
        if (pos.arrow != null) arrow.style.left = `${pos.arrow}px`;
      }
      if (scroll && tip.scrollIntoView) {
        try {
          tip.scrollIntoView({ block: "nearest" });
        } catch (e) {
          /* ignore */
        }
      }
    }

    _click(e) {
      const btn = e.target && e.target.closest ? e.target.closest("button[data-a]") : null;
      if (!btn) return;
      e.stopPropagation();
      this._act(btn.dataset.a);
    }

    _keydown(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        this._act("skip");
      } else if (e.key === "Enter" && !(e.target && e.target.tagName === "BUTTON")) {
        e.preventDefault();
        this._act("next");
      }
    }

    _act(what) {
      const o = this._opts;
      if (!o) return;
      if (o.onActivity) o.onActivity();
      const steps = this._steps();
      if (what === "speak") {
        if (o.onSpeak) o.onSpeak(steps[this._i]);
        return;
      }
      if (what === "skip") {
        if (o.onFinish) o.onFinish("skipped", this._i + 1);
        return;
      }
      if (this._i >= steps.length - 1) {
        if (o.onFinish) o.onFinish("done", steps.length);
        return;
      }
      this._i += 1;
      this._paint(true);
    }
  }

  if (g.customElements && !g.customElements.get("taskmate-tour")) {
    g.customElements.define("taskmate-tour", TaskMateTour);
  }

  g.__taskmate_tour = {
    STEPS,
    PRE_READER_STEPS,
    shouldStart,
    selectSteps,
    place,
    readFlag,
    writeFlag,
    clearFlag,
    syncFlag,
    mark,
    speak,
  };
})();
