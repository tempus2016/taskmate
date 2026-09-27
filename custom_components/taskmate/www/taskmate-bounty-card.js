/**
 * TaskMate Bounty Board Card (#931)
 *
 * One-off jobs a parent posts for a fixed number of points. The child this
 * card belongs to sees the bounties they may claim, claims one (it's theirs
 * for the claim lock), marks it done — with a photo when the bounty asks for
 * one — and it goes through the normal approval queue. A sibling's claim shows
 * dimmed with the time until it returns to the board; bounties the child can't
 * claim are hidden.
 *
 * Reads the `bounties` attribute of sensor.taskmate_bounties through the
 * attribute resolver, and `children` from the overview entity.
 *
 * Single layout, so it consumes the design tokens directly (like the routine
 * card) rather than carrying a second _renderDesigned() template. Every
 * --tmd-* reference has the card's original value as its fallback, so classic
 * — which defines no tokens — keeps the wireframe look. Layout classes carry a
 * bb- prefix: the shared design kit defines its own .btn / .bar / .av / .chip.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const DEFAULT_ACCENT = "#e67e22";
const BOUNTIES_ENTITY = "sensor.taskmate_bounties";
// Child avatar colours by position; a design's own palette wins when it has one.
const CHILD_COLOURS = ["#ff6b9d", "#3498db", "#1abc9c", "#e67e22", "#9b59b6", "#2ecc71"];

class TaskMateBountyCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _dialog: { type: Object },
      _busy: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._dialog = null;
    this._busy = false;
    this._tick = null;
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("You need to define an entity");
    if (!config.child_id) throw new Error("You need to define a child_id");
    this.config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", child_id: "" };
  }

  static getConfigElement() {
    return document.createElement("taskmate-bounty-card-editor");
  }

  getCardSize() {
    return 6;
  }

  connectedCallback() {
    super.connectedCallback();
    // Countdowns tick client-side from the server's timestamps. Re-render once
    // a second only while something on the board is actually counting down.
    this._tick = setInterval(() => {
      if (this._hasCountdown()) this.requestUpdate();
    }, 1000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearInterval(this._tick);
    this._tick = null;
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass") && changedProps.size === 1) {
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
    }
    return true;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
  }

  _bounties() {
    const attrs = this._attrs();
    const list = attrs.bounties || this.hass?.states?.[BOUNTIES_ENTITY]?.attributes?.bounties;
    return Array.isArray(list) ? list : [];
  }

  _children() {
    return this._attrs().children || [];
  }

  _child() {
    return this._children().find(c => String(c.id) === String(this.config.child_id));
  }

  _childName(id) {
    const c = this._children().find(ch => String(ch.id) === String(id));
    return c ? c.name : "?";
  }

  _eligible(b, childId) {
    return !Array.isArray(b.eligible) || b.eligible.length === 0 || b.eligible.map(String).includes(String(childId));
  }

  _hasCountdown() {
    return this._bounties().some(b => b.status === "claimed" || (b.status === "open" && b.expires_at));
  }

  /**
   * Resolve the design, stamp data-tm-design on the host (so the :host-scoped
   * token block applies inside this shadow root) and settle the header colour.
   * The colour is an inline host property: a <style> in the template is
   * ordered before adoptedStyleSheets and would lose to the :host default.
   */
  _applyDesign() {
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--bb-accent", _safeColor(configured, DEFAULT_ACCENT));
    } else {
      this.style.removeProperty("--bb-accent");
    }
    return design;
  }

  _fmtDur(ms) {
    const sec = Math.max(0, Math.round(ms / 1000));
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (d) return this._t("bounty.dur_days", { d, h });
    if (h) return this._t("bounty.dur_hours", { h, m: String(m).padStart(2, "0") });
    return this._t("bounty.dur_minutes", { m, s: String(s).padStart(2, "0") });
  }

  _msUntil(iso, now) {
    const t = Date.parse(iso || "");
    return Number.isFinite(t) ? t - now : null;
  }

  _avatar(childId, size = 22) {
    const children = this._children();
    const idx = Math.max(0, children.findIndex(c => String(c.id) === String(childId)));
    const name = this._childName(childId);
    const colour = `var(--tmd-c${(idx % 6) + 1}, ${CHILD_COLOURS[idx % CHILD_COLOURS.length]})`;
    return html`<span class="bb-av" style="--bb-ac:${colour};--bb-s:${size}px" title="${name}">${name.charAt(0).toUpperCase()}</span>`;
  }

  // ── actions ─────────────────────────────────────────────────────────────

  async _call(service, data) {
    if (this._busy) return false;
    this._busy = true;
    try {
      await this.hass.callService("taskmate", service, data);
      return true;
    } catch (err) {
      this.dispatchEvent(new CustomEvent("hass-notification", {
        detail: { message: String(err?.message || err) }, bubbles: true, composed: true,
      }));
      return false;
    } finally {
      this._busy = false;
      this.requestUpdate();
    }
  }

  async _claim(b) {
    const ok = await this._call("claim_bounty", { bounty_id: b.id, child_id: this.config.child_id });
    if (ok) this._dialog = null;
  }

  async _giveBack(b) {
    await this._call("give_back_bounty", { bounty_id: b.id, child_id: this.config.child_id });
  }

  async _done(b) {
    if (b.require_photo) {
      this._dialog = { kind: "photo", id: b.id };
      return;
    }
    const ok = await this._call("complete_bounty", { bounty_id: b.id, child_id: this.config.child_id });
    if (ok) this._dialog = { kind: "yay", id: b.id };
  }

  async _undo(b) {
    await this._call("undo_chore", { completion_id: b.completion_id });
  }

  _pickPhoto() {
    const input = this.renderRoot && this.renderRoot.querySelector("#bb-photo");
    if (input) input.click();
  }

  /** Shrink the picked photo to a ≤1280px JPEG, upload it, then submit. */
  async _photoPicked(e, b) {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file) return;
    this._dialog = { kind: "photo", id: b.id, uploading: true };
    try {
      const blob = await this._shrink(file);
      const photoUrl = await this._upload(blob);
      this._dialog = null;
      const ok = await this._call("complete_bounty", {
        bounty_id: b.id, child_id: this.config.child_id, photo_url: photoUrl,
      });
      if (ok) this._dialog = { kind: "yay", id: b.id };
    } catch (_err) {
      this._dialog = { kind: "photo", id: b.id, error: this._t("child.photo_upload_failed") };
    }
  }

  _shrink(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => {
        const max = 1280;
        let { width, height } = img;
        if (width > max || height > max) {
          const scale = Math.min(max / width, max / height);
          width = Math.round(width * scale);
          height = Math.round(height * scale);
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        canvas.getContext("2d").drawImage(img, 0, 0, width, height);
        URL.revokeObjectURL(url);
        canvas.toBlob(blob => (blob ? resolve(blob) : reject(new Error("no blob"))), "image/jpeg", 0.8);
      };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("bad image")); };
      img.src = url;
    });
  }

  async _upload(blob) {
    // Bearer-authenticated POST, refreshing a stale access token once on 401 —
    // the same upload the child card's photo chores use.
    const post = () => {
      const token = this.hass?.auth?.data?.access_token;
      const fd = new FormData();
      fd.append("file", blob, "evidence.jpg");
      return fetch("/api/taskmate/photo", {
        method: "POST", headers: token ? { Authorization: `Bearer ${token}` } : {}, body: fd,
      });
    };
    if (this.hass?.auth?.expired && this.hass.auth.refreshAccessToken) {
      try { await this.hass.auth.refreshAccessToken(); } catch (_e) { /* retried below */ }
    }
    let resp = await post();
    if (resp.status === 401 && this.hass?.auth?.refreshAccessToken) {
      await this.hass.auth.refreshAccessToken();
      resp = await post();
    }
    if (!resp.ok) throw new Error(`upload failed (${resp.status})`);
    const { photo_url: photoUrl } = await resp.json();
    if (!photoUrl) throw new Error("no photo_url");
    return photoUrl;
  }

  // ── render ──────────────────────────────────────────────────────────────

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const child = this._child();
    const title = this.config.title || this._t("bounty.title");
    if (!child) {
      return html`<ha-card>${this._header(title, null)}<div class="bb-empty">${this._t("bounty.no_child")}</div></ha-card>`;
    }
    const me = String(child.id);
    const now = Date.now();
    const all = this._bounties();
    const myClaim = all.find(b => b.status === "claimed" && String(b.claimed_by) === me);
    // Hidden unless the child may claim it — or it's theirs.
    const visible = all.filter(b => this._eligible(b, me) || String(b.claimed_by || "") === me);
    const active = visible.filter(b => b.status !== "completed");
    const recent = visible.filter(b => b.status === "completed");
    const openCount = visible.filter(b => b.status === "open").length;
    const dialogBounty = this._dialog && all.find(b => b.id === this._dialog.id);

    return html`
      <ha-card>
        ${this._header(title, openCount)}
        <div class="bb-content">
          ${active.length
            ? active.map(b => this._row(b, me, now, !!myClaim))
            : html`<div class="bb-empty">${this._t("bounty.empty")}</div>`}
          ${recent.length ? html`
            <div class="bb-sec">${this._t("bounty.recent")}</div>
            ${recent.map(b => this._row(b, me, now, !!myClaim))}
          ` : ""}
        </div>
        ${dialogBounty ? this._renderDialog(dialogBounty) : ""}
      </ha-card>
    `;
  }

  _header(title, openCount) {
    return html`
      <div class="bb-hd">
        <ha-icon class="bb-hd-icon" icon="mdi:flag-outline"></ha-icon>
        <div class="bb-hd-text">
          <div class="bb-hd-title">${title}</div>
          <div class="bb-hd-sub">${this._t("bounty.subtitle")}</div>
        </div>
        ${openCount !== null ? html`<span class="bb-hd-pill">${this._t("bounty.open_count", { count: openCount })}</span>` : ""}
      </div>
    `;
  }

  _row(b, me, now, holdingClaim) {
    const mine = String(b.claimed_by || "") === me;
    const eligibleIds = Array.isArray(b.eligible) && b.eligible.length ? b.eligible : this._children().map(c => c.id);
    const expLeft = b.expires_at ? this._msUntil(b.expires_at, now) : null;
    const showMeta = b.status === "open" || b.status === "claimed";
    let cls = "";
    let body = "";

    if (b.status === "open") {
      body = html`
        <div class="bb-act">
          <button class="bb-btn bb-claim" ?disabled=${holdingClaim || this._busy}
                  @click=${() => { this._dialog = { kind: "claim", id: b.id }; }}>
            <ha-icon icon="mdi:hand-back-right-outline"></ha-icon>${this._t("bounty.claim")}
          </button>
          <span class="bb-hint">${holdingClaim
            ? this._t("bounty.finish_first")
            : this._t("bounty.claim_hint", { hours: b.claim_hours })}</span>
        </div>`;
    } else if (b.status === "claimed" && mine) {
      cls = "mine";
      const left = this._msUntil(b.claim_until, now) ?? 0;
      const span = (Date.parse(b.claim_until || "") - Date.parse(b.claimed_at || "")) || (b.claim_hours * 3600e3);
      const frac = Math.max(0, Math.min(1, left / span));
      body = html`
        <div class="bb-claim-line"><ha-icon icon="mdi:timer-sand"></ha-icon>${this._t("bounty.claimed_by_you", { time: this._fmtDur(left) })}</div>
        <div class="bb-lock"><i style="width:${(frac * 100).toFixed(1)}%"></i></div>
        <div class="bb-act">
          <button class="bb-btn bb-done" ?disabled=${this._busy} @click=${() => this._done(b)}>
            <ha-icon icon="mdi:check"></ha-icon>${this._t("bounty.done")}
          </button>
          <button class="bb-btn bb-text" ?disabled=${this._busy} @click=${() => this._giveBack(b)}>${this._t("bounty.give_back")}</button>
        </div>`;
    } else if (b.status === "claimed") {
      cls = "locked";
      const left = this._msUntil(b.claim_until, now) ?? 0;
      body = html`
        <div class="bb-sib">${this._avatar(b.claimed_by, 20)}
          <span><b>${this._t("bounty.sibling_on_it", { name: this._childName(b.claimed_by) })}</b> — ${this._t("bounty.sibling_back_in", { time: this._fmtDur(left) })}</span>
        </div>`;
    } else if (b.status === "pending" && mine) {
      body = html`
        <div class="bb-act">
          <span class="bb-tag warn bb-wait"><ha-icon icon="mdi:timer-sand"></ha-icon>${this._t("bounty.waiting", { points: b.points })}</span>
          ${b.undo && b.completion_id ? html`
            <button class="bb-btn bb-text" ?disabled=${this._busy} @click=${() => this._undo(b)}>
              <ha-icon icon="mdi:undo-variant"></ha-icon>${this._t("bounty.undo")}
            </button>` : ""}
        </div>`;
    } else if (b.status === "pending") {
      cls = "locked";
      body = html`<div class="bb-sib">${this._avatar(b.claimed_by, 20)}<span>${this._t("bounty.sibling_checking", { name: this._childName(b.claimed_by) })}</span></div>`;
    } else if (b.status === "completed") {
      body = mine
        ? html`<div class="bb-act"><span class="bb-tag good"><ha-icon icon="mdi:check"></ha-icon>${this._t("bounty.you_earned", { points: b.points_awarded ?? b.points })}</span></div>`
        : html`<div class="bb-sib">${this._avatar(b.claimed_by, 20)}<span>${this._t("bounty.done_by", { name: this._childName(b.claimed_by) })}</span></div>`;
    }

    return html`
      <div class="bb-row ${cls}">
        <div class="bb-cost"><b>${b.points}</b><small>★ ${this._t("bounty.pts")}</small></div>
        <div class="bb-main">
          <div class="bb-title-row">
            <span class="bb-ic"><ha-icon icon="${b.icon || "mdi:flag-outline"}"></ha-icon></span>
            <div class="bb-title">${b.title}</div>
          </div>
          ${b.description ? html`<div class="bb-desc">${b.description}</div>` : ""}
          <div class="bb-meta">
            ${showMeta ? (expLeft !== null
              ? html`<span class="bb-tag ${expLeft < 6 * 3600e3 ? "warn" : ""}"><ha-icon icon="mdi:clock-outline"></ha-icon>${this._t("bounty.left", { time: this._fmtDur(expLeft) })}</span>`
              : html`<span class="bb-tag"><ha-icon icon="mdi:clock-outline"></ha-icon>${this._t("bounty.no_expiry")}</span>`) : ""}
            <span class="bb-stack">${eligibleIds.map(id => this._avatar(id, 22))}</span>
            ${b.require_photo ? html`<span class="bb-tag purple"><ha-icon icon="mdi:camera-outline"></ha-icon>${this._t("bounty.photo_tag")}</span>` : ""}
          </div>
          ${body}
        </div>
      </div>
    `;
  }

  _renderDialog(b) {
    const d = this._dialog;
    const close = () => { this._dialog = null; };
    let inner = "";
    if (d.kind === "claim") {
      inner = html`
        <div class="bb-dlg" style="--bb-dlg:var(--bb-accent)">
          <div class="bb-big-ic"><ha-icon icon="${b.icon || "mdi:flag-outline"}"></ha-icon></div>
          <h3>${this._t("bounty.claim_title", { title: b.title })}</h3>
          <p>${this._t("bounty.claim_body", { hours: b.claim_hours })}</p>
          <div class="bb-dlg-acts">
            <button class="bb-btn bb-ghost" @click=${close}>${this._t("bounty.not_now")}</button>
            <button class="bb-btn bb-claim" ?disabled=${this._busy} @click=${() => this._claim(b)}>${this._t("bounty.claim_it", { points: b.points })}</button>
          </div>
        </div>`;
    } else if (d.kind === "photo") {
      inner = html`
        <div class="bb-dlg" style="--bb-dlg:#9b59b6">
          <h3>${this._t("bounty.photo_title")}</h3>
          <p>${this._t("bounty.photo_body", { title: b.title })}</p>
          <div class="bb-photo-ph"><ha-icon icon="mdi:camera-outline"></ha-icon></div>
          ${d.error ? html`<p class="bb-err">${d.error}</p>` : ""}
          <input id="bb-photo" type="file" accept="image/*" capture="environment" hidden
                 @change=${e => this._photoPicked(e, b)}>
          <div class="bb-dlg-acts">
            <button class="bb-btn bb-ghost" @click=${close}>${this._t("bounty.cancel")}</button>
            <button class="bb-btn bb-done" ?disabled=${!!d.uploading || this._busy} @click=${() => this._pickPhoto()}>
              <ha-icon icon="mdi:camera-outline"></ha-icon>${d.uploading ? this._t("bounty.uploading") : this._t("bounty.take_photo")}
            </button>
          </div>
        </div>`;
    } else if (d.kind === "yay") {
      inner = html`
        <div class="bb-dlg" style="--bb-dlg:var(--tmd-good, #2ecc71)">
          <div class="bb-big-ic"><ha-icon icon="mdi:check"></ha-icon></div>
          <h3>${this._t("bounty.yay_title")}</h3>
          <p>${this._t("bounty.yay_body", { title: b.title, points: b.points })}</p>
          <div class="bb-dlg-acts"><button class="bb-btn bb-done" @click=${close}>${this._t("bounty.ok")}</button></div>
        </div>`;
    }
    return html`<div class="bb-scrim" @click=${e => { if (e.target === e.currentTarget) close(); }}>${inner}</div>`;
  }

  static get styles() {
    const base = css`
      :host { display: block; --bb-accent: var(--tmd-accent, #e67e22); }
      ha-card {
        position: relative;
        overflow: hidden;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px));
        font-family: var(--tmd-font-body, inherit);
      }
      .bb-hd {
        display: flex; align-items: center; gap: 12px;
        padding: 14px 18px;
        background: var(--bb-accent);
        color: var(--tmd-hd-text, #fff);
      }
      :host([data-tm-design="playroom"]) .bb-hd {
        background: linear-gradient(135deg, var(--bb-accent), color-mix(in srgb, var(--bb-accent) 72%, #fff));
      }
      .bb-hd-icon { --mdc-icon-size: 30px; flex: none; opacity: .95; }
      .bb-hd-text { flex: 1; min-width: 0; }
      .bb-hd-title {
        font-family: var(--tmd-font-display, inherit);
        font-size: 1.3rem; font-weight: 600;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .bb-hd-sub { font-size: .8rem; opacity: .85; margin-top: 1px; }
      .bb-hd-pill {
        flex: none; white-space: nowrap;
        background: rgba(255, 255, 255, .2);
        padding: 4px 12px; border-radius: 16px;
        font-size: .9rem; font-weight: 500;
      }
      .bb-content { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
      .bb-empty {
        text-align: center; padding: 30px 12px;
        color: var(--tmd-dim, var(--secondary-text-color));
      }
      .bb-sec {
        font-size: .8rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
        color: var(--tmd-dim, var(--secondary-text-color));
        margin: 4px 2px -4px;
      }

      .bb-row {
        display: flex; gap: 14px; align-items: flex-start;
        padding: 14px;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        border: 1px solid var(--tmd-border, var(--divider-color, #e0e0e0));
        border-radius: var(--tmd-radius-sm, 14px);
      }
      .bb-row.mine {
        border: 2px solid var(--tmd-warn, #e67e22);
        background: color-mix(in srgb, var(--tmd-warn, #e67e22) 8%, var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff))));
      }
      .bb-row.locked { opacity: .62; }
      .bb-cost {
        flex: none; min-width: 66px; padding: 10px 6px;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        border-radius: var(--tmd-radius-sm, 12px);
        background: linear-gradient(135deg, var(--tmd-gold, #f1c40f), color-mix(in srgb, var(--tmd-gold, #f39c12) 80%, #e67e22));
        color: #fff;
        box-shadow: 0 2px 8px rgba(241, 196, 15, .25);
      }
      .bb-cost b {
        font-family: var(--tmd-font-display, inherit);
        font-size: 1.35rem; line-height: 1; text-shadow: 0 1px 2px rgba(0, 0, 0, .2);
      }
      .bb-cost small { font-size: .62rem; font-weight: 700; letter-spacing: .5px; margin-top: 3px; opacity: .95; }
      :host([data-tm-design="accessible"]) .bb-cost { color: #111; box-shadow: none; border: 2px solid var(--tmd-border, #111); }
      :host([data-tm-design="accessible"]) .bb-cost b { text-shadow: none; }
      .bb-main { flex: 1; min-width: 0; }
      .bb-title-row { display: flex; align-items: center; gap: 10px; }
      .bb-ic {
        flex: none; width: 30px; height: 30px; border-radius: 9px;
        display: grid; place-items: center;
        background: var(--tmd-surface-2, var(--secondary-background-color, rgba(127, 127, 127, .1)));
        color: var(--bb-accent);
      }
      .bb-ic ha-icon { --mdc-icon-size: 18px; }
      .bb-title {
        flex: 1; min-width: 0;
        font-family: var(--tmd-font-display, inherit);
        font-size: 1.1rem; font-weight: 700; line-height: 1.25;
        overflow-wrap: anywhere;
      }
      .bb-desc { font-size: .88rem; color: var(--tmd-dim, var(--secondary-text-color)); margin-top: 4px; }
      .bb-meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 6px; }
      .bb-tag {
        display: inline-flex; align-items: center; gap: 4px;
        font-size: .72rem; font-weight: 700;
        padding: 2px 9px; border-radius: 999px; white-space: nowrap;
        background: var(--tmd-surface-2, rgba(127, 127, 127, .12));
        color: var(--tmd-dim, var(--secondary-text-color));
        border: 1px solid var(--tmd-border, transparent);
      }
      .bb-tag ha-icon { --mdc-icon-size: 13px; }
      .bb-tag.warn { background: color-mix(in srgb, var(--tmd-warn, #f39c12) 16%, transparent); color: var(--tmd-warn, #d68910); }
      .bb-tag.good { background: color-mix(in srgb, var(--tmd-good, #2ecc71) 16%, transparent); color: var(--tmd-good, #239b56); font-size: .8rem; padding: 4px 10px; }
      .bb-tag.purple { background: rgba(155, 89, 182, .18); color: #8e44ad; }
      .bb-tag.bb-wait { font-size: .8rem; padding: 5px 10px; white-space: normal; border-radius: 10px; }
      :host([data-tm-dark]) .bb-tag.purple { color: #c39bd3; }
      .bb-stack { display: inline-flex; }
      .bb-stack .bb-av + .bb-av { margin-left: -8px; }
      .bb-av {
        width: var(--bb-s, 22px); height: var(--bb-s, 22px); flex: none;
        border-radius: 50%;
        background: var(--bb-ac, #9b59b6); color: #fff;
        display: inline-grid; place-items: center;
        font-weight: 700; font-size: calc(var(--bb-s, 22px) * .45); line-height: 1;
        border: 2px solid var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        box-sizing: border-box;
      }
      .bb-act { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 10px; }
      .bb-hint { font-size: 12px; color: var(--tmd-dim, var(--secondary-text-color)); }
      .bb-claim-line {
        display: flex; align-items: center; gap: 6px; margin-top: 8px;
        font-size: .9rem; font-weight: 600; color: var(--tmd-warn, #d68910);
      }
      .bb-claim-line ha-icon { --mdc-icon-size: 16px; }
      .bb-lock {
        height: 6px; margin-top: 8px; overflow: hidden; border-radius: 3px;
        background: var(--tmd-surface-2, var(--divider-color, #e5e7eb));
        border: 1px solid var(--tmd-border, transparent);
        box-sizing: border-box;
      }
      .bb-lock > i { display: block; height: 100%; background: var(--tmd-warn, #e67e22); transition: width .9s linear; }
      .bb-sib {
        display: flex; align-items: flex-start; gap: 8px; margin-top: 8px;
        font-size: .88rem; line-height: 1.35;
        color: var(--tmd-dim, var(--secondary-text-color));
      }
      .bb-sib b { color: var(--tmd-text, var(--primary-text-color)); }

      .bb-btn {
        display: inline-flex; align-items: center; justify-content: center; gap: 6px;
        border: 0; cursor: pointer;
        border-radius: var(--tmd-radius-sm, 10px);
        padding: 9px 16px; min-height: 36px;
        font: inherit; font-family: var(--tmd-font-display, inherit);
        font-size: .92rem; font-weight: 600; color: #fff;
      }
      .bb-btn ha-icon { --mdc-icon-size: 17px; }
      .bb-btn[disabled] { opacity: .45; cursor: default; }
      .bb-claim { background: var(--tmd-warn, #e67e22); padding: 6px 12px; font-size: .85rem; }
      :host([data-tm-design]:not([data-tm-design="classic"])) .bb-claim { color: #2b1700; }
      .bb-done { background: var(--tmd-good, linear-gradient(135deg, #2ecc71, #27ae60)); }
      :host([data-tm-design]:not([data-tm-design="classic"])) .bb-done { color: #06301f; }
      .bb-text { background: transparent; color: var(--tmd-dim, var(--secondary-text-color)); padding: 9px 8px; }
      .bb-ghost {
        background: transparent; color: var(--tmd-text, var(--primary-text-color));
        border: 1px solid var(--tmd-border, var(--divider-color, #ccc));
      }

      .bb-scrim {
        position: absolute; inset: 0; z-index: 5;
        display: flex; align-items: center; justify-content: center;
        padding: 16px; background: rgba(0, 0, 0, .55);
        border-radius: inherit;
      }
      .bb-dlg {
        width: 100%; max-width: 340px; box-sizing: border-box;
        padding: 22px; text-align: center;
        background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: 20px;
        border: 1px solid var(--tmd-border, transparent);
        box-shadow: 0 12px 40px rgba(0, 0, 0, .5);
      }
      .bb-dlg h3 { margin: 0 0 6px; font-size: 1.2rem; font-family: var(--tmd-font-display, inherit); }
      .bb-dlg p { margin: 0 0 16px; color: var(--tmd-dim, var(--secondary-text-color)); }
      .bb-big-ic {
        width: 64px; height: 64px; margin: 0 auto 10px; border-radius: 50%;
        display: grid; place-items: center;
        background: color-mix(in srgb, var(--bb-dlg, #e67e22) 22%, transparent);
        color: var(--bb-dlg, #e67e22);
      }
      .bb-big-ic ha-icon { --mdc-icon-size: 34px; }
      .bb-photo-ph {
        height: 130px; margin-bottom: 14px; border-radius: 14px;
        display: grid; place-items: center;
        background: repeating-linear-gradient(45deg, var(--tmd-surface-2, rgba(127, 127, 127, .14)) 0 12px, transparent 12px 24px);
        color: var(--tmd-dim, var(--secondary-text-color));
      }
      .bb-photo-ph ha-icon { --mdc-icon-size: 40px; }
      .bb-err { color: var(--tmd-bad, var(--error-color, #c62828)) !important; }
      .bb-dlg-acts { display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }
    `;
    // The token block is :host-scoped, so it only takes effect when included
    // in THIS card's styles — a document-level rule cannot cross into the
    // shadow root.
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

class TaskMateBountyCardEditor extends LitElement {
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
    const children = attrs.children || [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      {
        name: "child_id",
        selector: {
          select: { options: children.map(c => ({ value: c.id, label: c.name })), mode: "dropdown" },
        },
      },
      { name: "title", selector: { text: {} } },
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
    child_id: this._t("bounty.editor.child"),
    title: this._t("common.editor.card_title"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  _computeHelper = (entry) => ({
    entity: this._t("common.editor.overview_entity_helper"),
    child_id: this._t("bounty.editor.child_helper"),
  }[entry.name] ?? "");

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
      card_design: this.config.card_design || "global",
    };
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._buildSchema()}
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

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      // "global" is the absence of a per-card override, not a value to store.
      if (value === "" || value === null || value === undefined || (key === "card_design" && value === "global")) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
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
      .colour-reset { font-size: 0.78rem; color: var(--secondary-text-color); background: none; border: 1px solid var(--divider-color, #e0e0e0); border-radius: 4px; padding: 4px 10px; cursor: pointer; margin-left: auto; }
      .colour-helper { color: var(--secondary-text-color); font-size: 0.82rem; line-height: 1.3; }
    `;
  }
}

customElements.define("taskmate-bounty-card", TaskMateBountyCard);
customElements.define("taskmate-bounty-card-editor", TaskMateBountyCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-bounty-card",
  name: "TaskMate Bounty Board",
  description: "One-off jobs any child can claim, finish and get approved",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-bounty-card", "overview"),
});
