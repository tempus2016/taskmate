/**
 * TaskMate Wishlist Card (#932)
 *
 * One child's wishlist: things they want, what they have saved towards each,
 * and what the family has pledged. The child adds a wish (it waits for a
 * grown-up), moves points in, takes their own savings back out, and asks to
 * redeem once it's funded — which becomes an ordinary reward claim for the
 * parent. Pledges are entered by a parent in the admin panel.
 *
 * Reads the overview sensor (children, points name/icon) plus the child's own
 * wishlist sensor, found by its `wishlist_child_id` attribute. Pictures are
 * stored images, signed per viewer through auth/sign_path before use.
 *
 * Single layout, so it consumes the design tokens directly (like the family
 * goal card) rather than carrying a second _renderDesigned() template. Every
 * --tmd-* reference has the card's original value as its fallback, so classic
 * — which defines no tokens — renders as designed. Layout classes carry a
 * wl- prefix because the shared design kit defines its own .btn / .bar.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const DEFAULT_ACCENT = "#e91e63";
const IMAGE_PREFIX = "/api/taskmate/image/";
const TARGET_STEP = 10;
const MAX_TARGET = 100000;

/**
 * A wish link is typed by a child. Only an absolute http(s) URL is ever
 * rendered as a link — never javascript:, data: or a relative path — even
 * though the backend already refuses anything else.
 */
function safeLink(value) {
  if (typeof value !== "string" || !value) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return { href: url.href, host: url.hostname.replace(/^www\./, "") };
  } catch (_e) {
    return null;
  }
}

class TaskMateWishlistCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _sheet: { state: true },
      _signed: { state: true },
    };
  }

  constructor() {
    super();
    this._sheet = null;
    this._signed = {};
    this._inflight = new Set();
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("A TaskMate overview entity is required");
    }
    this.config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  static getConfigElement() {
    return document.createElement("taskmate-wishlist-card-editor");
  }

  getCardSize() {
    return 5;
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass")) {
      const old = changedProps.get("hass");
      const wlId = this._wishlistEntityId();
      if (old && wlId && old.states && this.hass.states[wlId] !== old.states[wlId]) return true;
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(old, this.hass, this.config && this.config.entity)
        : true;
    }
    return true;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  /**
   * Resolve the active design, stamp data-tm-design on the host, and set the
   * accent. The accent is an inline host property, not a template <style>: a
   * shadow tree's <style> is ordered before adoptedStyleSheets, so it would
   * lose to the :host default in static styles().
   */
  _applyDesign() {
    if (window.__taskmate_design) {
      window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity);
    }
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--wl-accent", _safeColor(configured, DEFAULT_ACCENT));
    } else {
      this.style.removeProperty("--wl-accent");
    }
  }

  // ── data ────────────────────────────────────────────────────────────────
  /** The child's own wishlist sensor, found by the child id it carries. */
  _wishlistEntityId() {
    const childId = this.config && this.config.child_id;
    if (!childId || !this.hass || !this.hass.states) return null;
    const cached = this._wlEntityId;
    const cachedState = cached && this.hass.states[cached];
    if (cachedState && cachedState.attributes && cachedState.attributes.wishlist_child_id === childId) return cached;
    this._wlEntityId = null;
    for (const [id, st] of Object.entries(this.hass.states)) {
      if (id.startsWith("sensor.") && st && st.attributes && st.attributes.wishlist_child_id === childId) {
        this._wlEntityId = id;
        break;
      }
    }
    return this._wlEntityId;
  }

  _wishlist() {
    const id = this._wishlistEntityId();
    const st = id && this.hass.states[id];
    const attrs = (st && st.attributes) || {};
    return {
      wishes: Array.isArray(attrs.wishes) ? attrs.wishes : [],
      max: Number(attrs.wish_max_open) || 5,
    };
  }

  _pledged(w) {
    return Number(w.pledged) || 0;
  }

  _remaining(w) {
    return Math.max(0, (Number(w.target) || 0) - (Number(w.saved) || 0) - this._pledged(w));
  }

  _funded(w) {
    return (Number(w.target) || 0) > 0 && this._remaining(w) === 0;
  }

  // ── pictures ────────────────────────────────────────────────────────────
  async _ensureSigned(wishes) {
    for (const w of wishes) {
      const url = w.image_url;
      // Only our own stored images are signed; nothing else is ever handed to
      // auth/sign_path or rendered as a picture.
      if (typeof url !== "string" || !url.startsWith(IMAGE_PREFIX)) continue;
      if (this._signed[url] || this._inflight.has(url)) continue;
      this._inflight.add(url);
      try {
        const res = await this.hass.callWS({ type: "auth/sign_path", path: url, expires: 3600 });
        if (res && res.path) this._signed = { ...this._signed, [url]: res.path };
      } catch (e) {
        console.warn("taskmate: sign_path failed", e);
      } finally {
        this._inflight.delete(url);
      }
    }
  }

  updated() {
    if (this.hass && this.config) this._ensureSigned(this._wishlist().wishes);
  }

  // ── actions ─────────────────────────────────────────────────────────────
  async _call(service, data) {
    this._sheet = this._sheet ? { ...this._sheet, busy: true, error: "" } : null;
    try {
      await this.hass.callService("taskmate", service, { child_id: this.config.child_id, ...data });
      this._closeSheet();
      return true;
    } catch (err) {
      const message = (err && err.message) || String(err);
      if (this._sheet) {
        this._sheet = { ...this._sheet, busy: false, error: this._t("wishlist.error", { error: message }) };
      } else {
        this._flash = this._t("wishlist.error", { error: message });
        this.requestUpdate();
      }
      return false;
    }
  }

  _openSheet(sheet) {
    this._flash = "";
    this._sheet = { busy: false, error: "", ...sheet };
  }

  _closeSheet() {
    if (this._sheet && this._sheet.previewUrl) URL.revokeObjectURL(this._sheet.previewUrl);
    this._sheet = null;
  }

  _openAdd() {
    this._openSheet({ kind: "add", name: "", target: 50, link: "" });
  }

  _openMove(w, spendable) {
    const max = Math.min(spendable, this._remaining(w));
    this._openSheet({ kind: "move", id: w.id, amount: Math.min(max, 50) });
  }

  _openTake(w) {
    this._openSheet({ kind: "take", id: w.id, amount: Number(w.saved) || 0 });
  }

  _setSheet(patch) {
    this._sheet = { ...this._sheet, ...patch, error: "" };
  }

  _stepTarget(delta) {
    const next = Math.min(MAX_TARGET, Math.max(1, (Number(this._sheet.target) || 0) + delta));
    this._setSheet({ target: next });
  }

  _pickPicture() {
    const input = this.renderRoot && this.renderRoot.querySelector("#wl-file");
    if (input) {
      input.value = "";
      input.click();
    }
  }

  /** Downscale to a small JPEG in the browser: the server keeps it as-is. */
  _onPicture(e) {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file || !this._sheet) return;
    if (!file.type || !file.type.startsWith("image/")) {
      this._sheet = { ...this._sheet, error: this._t("wishlist.picture_not_image") };
      return;
    }
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const max = 512;
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
      canvas.toBlob((blob) => {
        if (!this._sheet) return;
        if (!blob) {
          this._sheet = { ...this._sheet, error: this._t("wishlist.picture_failed") };
          return;
        }
        if (this._sheet.previewUrl) URL.revokeObjectURL(this._sheet.previewUrl);
        this._sheet = { ...this._sheet, blob, previewUrl: URL.createObjectURL(blob), error: "" };
      }, "image/jpeg", 0.82);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      if (this._sheet) this._sheet = { ...this._sheet, error: this._t("wishlist.picture_failed") };
    };
    img.src = url;
  }

  /** Post the picture to the photo endpoint (open to children); the wish takes it over. */
  async _uploadPicture(blob) {
    const post = () => {
      const token = this.hass && this.hass.auth && this.hass.auth.data && this.hass.auth.data.access_token;
      const fd = new FormData();
      fd.append("file", blob, "wish.jpg");
      return fetch("/api/taskmate/photo", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
    };
    if (this.hass.auth && this.hass.auth.expired && this.hass.auth.refreshAccessToken) {
      try { await this.hass.auth.refreshAccessToken(); } catch (_e) { /* surfaced below */ }
    }
    let resp = await post();
    if (resp.status === 401 && this.hass.auth && this.hass.auth.refreshAccessToken) {
      await this.hass.auth.refreshAccessToken();
      resp = await post();
    }
    if (!resp.ok) throw new Error(`upload failed (${resp.status})`);
    const body = await resp.json();
    if (!body || !body.photo_url) throw new Error("no photo_url");
    return body.photo_url;
  }

  async _submitAdd() {
    const s = this._sheet;
    const name = (s.name || "").trim();
    if (!name) return;
    const link = (s.link || "").trim();
    if (link && !safeLink(link)) {
      this._sheet = { ...s, error: this._t("wishlist.link_invalid") };
      return;
    }
    const data = { name, target: Number(s.target) || 1 };
    if (link) data.link = link;
    if (s.blob) {
      this._sheet = { ...s, busy: true, error: "" };
      try {
        data.photo_url = await this._uploadPicture(s.blob);
      } catch (_e) {
        this._sheet = { ...this._sheet, busy: false, error: this._t("wishlist.picture_failed") };
        return;
      }
    }
    await this._call("add_wish", data);
  }

  // ── render ──────────────────────────────────────────────────────────────
  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="wl-empty"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t("common.entity_not_found", { entity: this.config.entity })}</div></div></ha-card>`;
    }
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = Array.isArray(attrs.children) ? attrs.children : [];
    const child = children.find((c) => c.id === this.config.child_id);
    if (!this.config.child_id || !child) {
      return html`<ha-card><div class="wl-empty"><ha-icon icon="mdi:heart-outline"></ha-icon><div>${this._t("wishlist.pick_child")}</div></div></ha-card>`;
    }
    const pointsIcon = attrs.points_icon || "mdi:star";
    const spendable = Number(child.spendable_balance != null ? child.spendable_balance : child.points) || 0;
    const { wishes, max } = this._wishlist();
    const open = wishes.filter((w) => w.status === "pending" || w.status === "active" || w.status === "redeem_requested");
    const reserved = wishes
      .filter((w) => w.status === "active" || w.status === "redeem_requested")
      .reduce((sum, w) => sum + (Number(w.saved) || 0), 0);
    const atLimit = open.length >= max;
    // Declined wishes sink to the bottom; the rest keep the order they were made in.
    const ordered = [...wishes.filter((w) => w.status !== "declined"), ...wishes.filter((w) => w.status === "declined")];
    const title = this.config.title || this._t("wishlist.title", { name: child.name });

    return html`
      <ha-card class="${this._sheet ? "wl-has-sheet" : ""}">
        <div class="wl-header">
          <div class="wl-hd-left">
            <ha-icon class="wl-hd-icon" icon="mdi:heart"></ha-icon>
            <div class="wl-hd-text">
              <div class="wl-hd-title">${title}</div>
              <div class="wl-hd-sub">${this._t("wishlist.subtitle")}</div>
            </div>
          </div>
          <button class="wl-hd-pill" ?disabled=${atLimit}
            title="${atLimit ? this._t("wishlist.limit_reached", { max }) : this._t("wishlist.add")}"
            @click=${() => this._openAdd()}>
            <ha-icon icon="mdi:plus"></ha-icon>${this._t("wishlist.add")}
          </button>
        </div>
        <div class="wl-balance">
          <ha-icon icon="mdi:piggy-bank-outline"></ha-icon>
          <span>${this._t("wishlist.can_spend")}</span>
          <b class="wl-amount"><ha-icon icon="${pointsIcon}"></ha-icon>${spendable}</b>
          <span class="wl-reserved">${this._t("wishlist.saved_in_wishes", { points: reserved })}</span>
        </div>
        ${this._flash ? html`<div class="wl-flash" role="alert">${this._flash}</div>` : ""}
        <div class="wl-content">
          ${ordered.length === 0
            ? html`<div class="wl-empty wl-empty-list"><ha-icon icon="mdi:gift-outline"></ha-icon><div>${this._t("wishlist.empty")}</div></div>`
            : ordered.map((w) => this._renderWish(w, spendable))}
        </div>
        ${this._sheet ? this._renderSheet(wishes, spendable, pointsIcon) : ""}
      </ha-card>
    `;
  }

  _renderThumb(w) {
    const src = this._signed[w.image_url];
    return src
      ? html`<img class="wl-thumb" src="${src}" alt="" loading="lazy">`
      : html`<div class="wl-thumb wl-thumb-ph"><ha-icon icon="mdi:gift"></ha-icon></div>`;
  }

  _renderWish(w, spendable) {
    const target = Number(w.target) || 0;
    const saved = Number(w.saved) || 0;
    const pledged = this._pledged(w);
    const remaining = this._remaining(w);
    const funded = this._funded(w);
    const link = safeLink(w.link);
    const showProgress = w.status === "active" || w.status === "redeem_requested";
    const cls = w.status === "pending" ? "pending"
      : w.status === "declined" ? "declined"
      : (funded || w.status === "redeem_requested") ? "funded" : "";
    const pct = (n) => (target > 0 ? Math.max(0, Math.min(100, (n / target) * 100)) : 0);

    return html`
      <div class="wl-wish ${cls}" data-wish="${w.id}">
        <div class="wl-wish-top">
          ${this._renderThumb(w)}
          <div class="wl-grow">
            <div class="wl-wish-name">${w.name}</div>
            <div class="wl-wish-meta">
              <span class="wl-tag"><ha-icon icon="mdi:flag-checkered"></ha-icon>${this._t("wishlist.target_tag", { points: target })}</span>
              ${link ? html`<a class="wl-link" href="${link.href}" target="_blank" rel="noopener noreferrer"
                  title="${this._t("wishlist.open_link")}"><ha-icon icon="mdi:link-variant"></ha-icon>${link.host}</a>` : ""}
            </div>
          </div>
        </div>
        ${showProgress ? html`
          <div class="wl-split" role="img" aria-label="${this._t("wishlist.progress_label", { total: Math.min(target, saved + pledged), target })}">
            <i class="wl-me" style="width:${pct(saved)}%"></i>
            <i class="wl-fam" style="width:${pct(Math.min(pledged, Math.max(0, target - saved)))}%"></i>
          </div>
          <div class="wl-legend">
            <span><span class="wl-sw wl-sw-me"></span>${this._t("wishlist.legend_me", { points: saved })}</span>
            <span><span class="wl-sw wl-sw-fam"></span>${this._t("wishlist.legend_family", { points: pledged })}</span>
            <span class="wl-tot">${Math.min(target, saved + pledged)} / ${target}</span>
          </div>
          ${Array.isArray(w.pledges) && w.pledges.length ? html`
            <div class="wl-pledges">
              ${w.pledges.map((p) => html`<span class="wl-pl"><ha-icon icon="mdi:heart"></ha-icon>${p.name} +${p.points}</span>`)}
            </div>` : ""}
        ` : ""}
        <div class="wl-acts">${this._renderActions(w, spendable, remaining, funded)}</div>
      </div>
    `;
  }

  _renderActions(w, spendable, remaining, funded) {
    if (w.status === "pending") {
      return html`
        <span class="wl-status warn"><ha-icon icon="mdi:timer-sand"></ha-icon>${this._t("wishlist.status_pending")}</span>
        <button class="wl-btn text" @click=${() => this._call("withdraw_wish", { wish_id: w.id })}>${this._t("wishlist.withdraw")}</button>`;
    }
    if (w.status === "declined") {
      return html`
        <span class="wl-status bad"><ha-icon icon="mdi:close-circle-outline"></ha-icon>${this._t("wishlist.status_declined")}</span>
        ${w.decline_reason ? html`<span class="wl-reason">${w.decline_reason}</span>` : ""}
        <button class="wl-btn text" @click=${() => this._call("withdraw_wish", { wish_id: w.id })}>${this._t("wishlist.dismiss")}</button>`;
    }
    if (w.status === "redeem_requested") {
      return html`<span class="wl-status good"><ha-icon icon="mdi:gift"></ha-icon>${this._t("wishlist.status_redeem_requested")}</span>`;
    }
    const takeBack = (Number(w.saved) || 0) > 0
      ? html`<button class="wl-btn text" @click=${() => this._openTake(w)}>${this._t("wishlist.take_back")}</button>`
      : "";
    if (funded) {
      return html`
        <div class="wl-funded"><ha-icon icon="mdi:trophy"></ha-icon>${this._t("wishlist.fully_funded")}</div>
        <button class="wl-btn green" @click=${() => this._openSheet({ kind: "redeem", id: w.id })}>
          <ha-icon icon="mdi:gift"></ha-icon>${this._t("wishlist.ask_redeem")}</button>
        ${takeBack}`;
    }
    return html`
      <button class="wl-btn accent" ?disabled=${spendable < 1} @click=${() => this._openMove(w, spendable)}>
        <ha-icon icon="mdi:piggy-bank-outline"></ha-icon>${this._t("wishlist.move_points")}</button>
      <span class="wl-to-go">${this._t("wishlist.to_go", { points: remaining })}</span>
      <span class="wl-grow"></span>
      ${takeBack}`;
  }

  _renderSheet(wishes, spendable, pointsIcon) {
    const s = this._sheet;
    const wish = s.id ? wishes.find((w) => w.id === s.id) : null;
    let body = "";
    if (s.kind === "add") body = this._renderAddSheet(s);
    else if (!wish) return "";
    else if (s.kind === "move") body = this._renderAmountSheet(s, wish, Math.min(spendable, this._remaining(wish)), pointsIcon, "move", spendable);
    else if (s.kind === "take") body = this._renderAmountSheet(s, wish, Number(wish.saved) || 0, pointsIcon, "take", spendable);
    else if (s.kind === "redeem") body = this._renderRedeemSheet(s, wish);
    return html`
      <div class="wl-scrim" @click=${(e) => { if (e.target === e.currentTarget && !s.busy) this._closeSheet(); }}>
        <div class="wl-sheet" role="dialog" aria-modal="true">
          <div class="wl-grab"></div>
          ${body}
          ${s.error ? html`<div class="wl-error" role="alert">${s.error}</div>` : ""}
        </div>
      </div>`;
  }

  _renderAddSheet(s) {
    return html`
      <h3><ha-icon icon="mdi:star-shooting-outline"></ha-icon>${this._t("wishlist.add_title")}</h3>
      <label class="wl-field">
        <span class="wl-label">${this._t("wishlist.field_name")}</span>
        <input class="wl-input" type="text" maxlength="60" .value=${s.name}
          @input=${(e) => this._setSheet({ name: e.target.value })}>
      </label>
      <div class="wl-field">
        <span class="wl-label">${this._t("wishlist.field_target")}</span>
        <div class="wl-row">
          <div class="wl-stepper">
            <button aria-label="−" @click=${() => this._stepTarget(-TARGET_STEP)}>−</button>
            <input type="number" min="1" max="${MAX_TARGET}" .value=${String(s.target)}
              @input=${(e) => this._setSheet({ target: Math.max(1, Math.min(MAX_TARGET, parseInt(e.target.value, 10) || 1)) })}>
            <button aria-label="+" @click=${() => this._stepTarget(TARGET_STEP)}>+</button>
          </div>
          <span class="wl-hint">${this._t("wishlist.target_hint")}</span>
        </div>
      </div>
      <label class="wl-field">
        <span class="wl-label">${this._t("wishlist.field_link")} <span class="wl-hint">${this._t("wishlist.optional")}</span></span>
        <input class="wl-input" type="url" maxlength="500" placeholder="https://…" .value=${s.link}
          @input=${(e) => this._setSheet({ link: e.target.value })}>
      </label>
      <div class="wl-field">
        <span class="wl-label">${this._t("wishlist.field_picture")} <span class="wl-hint">${this._t("wishlist.optional")}</span></span>
        <input id="wl-file" type="file" accept="image/*" hidden @change=${(e) => this._onPicture(e)}>
        <button class="wl-drop" @click=${() => this._pickPicture()}>
          ${s.previewUrl
            ? html`<img src="${s.previewUrl}" alt=""><span>${this._t("wishlist.picture_change")}</span>`
            : html`<ha-icon icon="mdi:image-plus"></ha-icon><span>${this._t("wishlist.picture_pick")}</span>`}
        </button>
      </div>
      <div class="wl-sheet-acts">
        <button class="wl-btn ghost" ?disabled=${s.busy} @click=${() => this._closeSheet()}>${this._t("common.cancel")}</button>
        <button class="wl-btn accent" ?disabled=${s.busy || !(s.name || "").trim()} @click=${() => this._submitAdd()}>${this._t("wishlist.send")}</button>
      </div>`;
  }

  _renderAmountSheet(s, wish, max, pointsIcon, mode, spendable) {
    const amount = Math.max(0, Math.min(Number(s.amount) || 0, max));
    const isMove = mode === "move";
    const chips = [10, 25, 50].filter((n) => n < max);
    const service = isMove ? "move_points_to_wish" : "take_points_from_wish";
    return html`
      <h3><ha-icon class=${isMove ? "" : "tm-rtl-flip"} icon="${isMove ? "mdi:piggy-bank-outline" : "mdi:undo-variant"}"></ha-icon>${this._t(isMove ? "wishlist.move_title" : "wishlist.take_title", { name: wish.name })}</h3>
      <div class="wl-big-amt">${amount}<ha-icon icon="${pointsIcon}"></ha-icon></div>
      <input class="wl-range" type="range" min="0" max="${max}" step="1" .value=${String(amount)}
        @input=${(e) => this._setSheet({ amount: Number(e.target.value) })}>
      <div class="wl-range-info">
        <span>0</span>
        <span>${isMove
          ? this._t("wishlist.move_info", { balance: spendable, needed: this._remaining(wish) })
          : this._t("wishlist.take_info", { saved: Number(wish.saved) || 0 })}</span>
        <span>${max}</span>
      </div>
      <div class="wl-chips">
        ${chips.map((n) => html`<button class="wl-chip ${amount === n ? "on" : ""}" @click=${() => this._setSheet({ amount: n })}>+${n}</button>`)}
        <button class="wl-chip ${amount === max ? "on" : ""}" @click=${() => this._setSheet({ amount: max })}>
          ${this._t(isMove ? "wishlist.all_i_need" : "wishlist.take_all", { points: max })}</button>
      </div>
      <div class="wl-sheet-acts">
        <button class="wl-btn ghost" ?disabled=${s.busy} @click=${() => this._closeSheet()}>${this._t("common.cancel")}</button>
        <button class="wl-btn accent" ?disabled=${s.busy || amount < 1}
          @click=${() => this._call(service, { wish_id: wish.id, points: amount })}>
          ${this._t(isMove ? "wishlist.move_confirm" : "wishlist.take_confirm", { points: amount })}</button>
      </div>`;
  }

  _renderRedeemSheet(s, wish) {
    return html`
      <div class="wl-redeem">
        <div class="wl-big-ic"><ha-icon icon="mdi:gift"></ha-icon></div>
        <h3>${this._t("wishlist.redeem_title", { name: wish.name })}</h3>
        <p>${this._t("wishlist.redeem_body")}</p>
        <div class="wl-sheet-acts center">
          <button class="wl-btn ghost" ?disabled=${s.busy} @click=${() => this._closeSheet()}>${this._t("wishlist.not_yet")}</button>
          <button class="wl-btn green" ?disabled=${s.busy}
            @click=${() => this._call("request_wish_redeem", { wish_id: wish.id })}>${this._t("wishlist.yes_please")}</button>
        </div>
      </div>`;
  }

  static get styles() {
    const base = css`
      :host {
        display: block;
        --wl-accent: var(--tmd-accent, #e91e63);
        --wl-good: var(--tmd-good, #2ecc71);
        --wl-gold: var(--tmd-gold, #f1c40f);
        --wl-text: var(--tmd-text, var(--primary-text-color));
        --wl-dim: var(--tmd-dim, var(--secondary-text-color));
        --wl-surface: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        --wl-surface-2: var(--tmd-surface-2, var(--secondary-background-color, #f5f5f5));
        --wl-border: var(--tmd-border, var(--divider-color, #e0e0e0));
        --wl-me: var(--wl-accent);
        --wl-link: var(--tmd-accent, var(--primary-color, #03a9f4));
      }
      /* Graphite keeps colour for meaning only: its accent is a neutral that
         all but vanishes on its own dark surfaces, so the child's share, links
         and the main button follow the text colour instead (as its kit does). */
      :host([data-tm-design="graphite"]) {
        --wl-me: var(--tmd-text);
        --wl-link: var(--tmd-text);
      }
      :host([data-tm-design="graphite"]) .wl-btn.accent { background: var(--tmd-text); color: var(--tmd-surface); }
      ha-card {
        position: relative;
        overflow: hidden;
        background: var(--wl-surface);
        color: var(--wl-text);
        border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px));
        font-family: var(--tmd-font-body, inherit);
      }
      ha-card.wl-has-sheet { min-height: 560px; }
      button { font-family: inherit; }
      ha-icon { --mdc-icon-size: 18px; }

      .wl-header {
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        padding: 14px 18px; background: var(--wl-accent); color: var(--tmd-hd-text, #fff);
      }
      .wl-hd-left { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
      .wl-hd-icon { --mdc-icon-size: 30px; flex: none; opacity: .95; }
      .wl-hd-text { min-width: 0; }
      .wl-hd-title {
        font-size: 1.3rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        font-family: var(--tmd-font-display, inherit);
      }
      .wl-hd-sub { font-size: .8rem; opacity: .85; margin-top: 1px; }
      .wl-hd-pill {
        display: inline-flex; align-items: center; gap: 5px; flex: none; cursor: pointer;
        background: rgba(255, 255, 255, .2); color: inherit; border: 0;
        padding: 5px 12px; border-radius: 16px; font-size: .9rem; font-weight: 500; white-space: nowrap;
      }
      .wl-hd-pill[disabled] { opacity: .5; cursor: default; }

      .wl-balance {
        display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
        padding: 10px 16px; font-size: .92rem;
        background: color-mix(in srgb, var(--wl-accent) 10%, var(--wl-surface));
        border-bottom: 1px solid var(--wl-border);
      }
      .wl-balance > ha-icon { color: var(--wl-accent); }
      .wl-amount { display: inline-flex; align-items: center; gap: 3px; font-size: 1.05rem; color: var(--wl-gold); }
      .wl-reserved { margin-inline-start: auto; font-size: .78rem; color: var(--wl-dim); }
      .wl-flash { margin: 10px 16px 0; font-size: .85rem; color: var(--tmd-bad, #e74c3c); }

      .wl-content { padding: 16px; display: flex; flex-direction: column; gap: 12px; }
      .wl-empty {
        display: flex; flex-direction: column; align-items: center; gap: 8px; text-align: center;
        padding: 28px 16px; color: var(--wl-dim);
      }
      .wl-empty ha-icon { --mdc-icon-size: 32px; }
      .wl-empty-list { padding: 18px 8px; }

      .wl-wish {
        background: var(--wl-surface-2); border: 1px solid var(--wl-border);
        border-radius: var(--tmd-radius-sm, 14px); overflow: hidden;
      }
      .wl-wish.pending { border-style: dashed; opacity: .88; }
      .wl-wish.declined { opacity: .8; }
      .wl-wish.funded {
        border: 2px solid var(--wl-good);
        background: color-mix(in srgb, var(--wl-good) 8%, var(--wl-surface-2));
      }
      .wl-wish-top { display: flex; gap: 12px; padding: 12px; }
      .wl-thumb {
        width: 72px; height: 72px; flex: none; border-radius: var(--tmd-radius-sm, 12px);
        object-fit: cover; display: block;
      }
      .wl-thumb-ph {
        display: grid; place-items: center; color: rgba(255, 255, 255, .92);
        background: linear-gradient(135deg, var(--wl-accent), color-mix(in srgb, var(--wl-accent) 45%, #3498db));
      }
      .wl-thumb-ph ha-icon { --mdc-icon-size: 34px; }
      .wl-grow { flex: 1; min-width: 0; }
      .wl-wish-name {
        font-size: 1.1rem; font-weight: 700; line-height: 1.25; overflow-wrap: anywhere;
        font-family: var(--tmd-font-display, inherit);
      }
      .wl-wish-meta { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; align-items: center; }
      .wl-tag, .wl-link {
        display: inline-flex; align-items: center; gap: 4px; font-size: .75rem; font-weight: 600;
        padding: 2px 9px; border-radius: 999px; white-space: nowrap;
      }
      .wl-tag { background: color-mix(in srgb, var(--wl-text) 8%, transparent); color: var(--wl-dim); }
      .wl-tag ha-icon, .wl-link ha-icon { --mdc-icon-size: 13px; }
      .wl-link {
        color: var(--wl-link); text-decoration: none;
        background: color-mix(in srgb, var(--wl-link) 14%, transparent);
        max-width: 100%; overflow: hidden; text-overflow: ellipsis;
      }

      .wl-split {
        margin: 0 12px; height: 16px; border-radius: 8px; overflow: hidden; display: flex;
        background: color-mix(in srgb, var(--wl-text) 12%, transparent);
        border: 2px solid color-mix(in srgb, var(--wl-text) 8%, transparent);
      }
      .wl-split i { display: block; height: 100%; }
      .wl-me { background: var(--wl-me); }
      .wl-fam { background: repeating-linear-gradient(135deg, var(--wl-gold) 0 6px, #f39c12 6px 12px); }
      .wl-legend {
        display: flex; gap: 12px; flex-wrap: wrap; align-items: center;
        padding: 6px 12px 0; font-size: .8rem; color: var(--wl-dim);
      }
      .wl-sw { width: 10px; height: 10px; border-radius: 3px; display: inline-block; margin-inline-end: 4px; vertical-align: -1px; }
      .wl-sw-me { background: var(--wl-me); }
      .wl-sw-fam { background: var(--wl-gold); }
      .wl-tot { margin-inline-start: auto; color: var(--wl-text); font-weight: 700; font-variant-numeric: tabular-nums; }
      .wl-pledges { padding: 8px 12px 0; display: flex; flex-wrap: wrap; gap: 6px; }
      .wl-pl {
        display: inline-flex; align-items: center; gap: 5px; font-size: .78rem; border-radius: 999px; padding: 3px 9px;
        background: color-mix(in srgb, var(--wl-gold) 16%, transparent); color: var(--wl-text);
      }
      .wl-pl ha-icon { --mdc-icon-size: 13px; color: #ff6b9d; }

      .wl-acts { display: flex; gap: 8px; padding: 10px 12px 12px; flex-wrap: wrap; align-items: center; }
      .wl-status {
        display: inline-flex; align-items: center; gap: 5px; font-size: .8rem; font-weight: 700;
        padding: 4px 10px; border-radius: 10px; line-height: 1.3;
      }
      .wl-status.warn { background: color-mix(in srgb, var(--tmd-warn, #f39c12) 18%, transparent); color: var(--tmd-warn, #d68910); }
      .wl-status.good { background: color-mix(in srgb, var(--wl-good) 18%, transparent); color: var(--wl-good); }
      .wl-status.bad { background: color-mix(in srgb, var(--tmd-bad, #e74c3c) 16%, transparent); color: var(--tmd-bad, #e74c3c); }
      .wl-reason { font-size: .82rem; color: var(--wl-dim); font-style: italic; overflow-wrap: anywhere; }
      .wl-funded {
        display: flex; align-items: center; gap: 6px; flex: 1 0 auto;
        font-weight: 700; color: var(--wl-good); white-space: nowrap;
      }
      .wl-funded ha-icon { --mdc-icon-size: 20px; }
      .wl-to-go { font-size: .8rem; color: var(--wl-dim); }

      .wl-btn {
        display: inline-flex; align-items: center; justify-content: center; gap: 6px; cursor: pointer;
        border: 0; border-radius: var(--tmd-radius-sm, 10px); padding: 8px 14px;
        font-size: .88rem; font-weight: 600; color: #fff; background: var(--wl-accent);
      }
      .wl-btn.accent { background: var(--wl-accent); color: var(--tmd-hd-text, #fff); }
      .wl-btn.green { background: var(--wl-good); color: #fff; }
      .wl-btn.ghost { background: transparent; color: var(--wl-text); border: 1px solid var(--wl-border); }
      .wl-btn.text { background: transparent; color: var(--wl-dim); padding: 8px 6px; }
      .wl-btn[disabled] { opacity: .45; cursor: default; }

      .wl-scrim {
        position: absolute; inset: 0; z-index: 5; display: flex; align-items: flex-end;
        background: rgba(0, 0, 0, .5);
      }
      .wl-sheet {
        width: 100%; box-sizing: border-box; max-height: 96%; overflow-y: auto;
        background: var(--wl-surface); color: var(--wl-text);
        border-radius: 18px 18px 0 0; padding: 8px 16px 16px;
        box-shadow: 0 -10px 30px rgba(0, 0, 0, .35);
        border-top: 1px solid var(--wl-border);
      }
      .wl-grab { width: 40px; height: 4px; border-radius: 2px; background: var(--wl-border); margin: 4px auto 10px; }
      .wl-sheet h3 {
        margin: 0 0 12px; font-size: 1.15rem; display: flex; align-items: center; gap: 8px;
        font-family: var(--tmd-font-display, inherit);
      }
      .wl-sheet h3 ha-icon { --mdc-icon-size: 22px; color: var(--wl-accent); }
      .wl-field { display: block; margin-bottom: 14px; }
      .wl-label { display: block; font-size: .8rem; font-weight: 600; margin-bottom: 6px; }
      .wl-hint { font-size: .75rem; color: var(--wl-dim); font-weight: 400; }
      .wl-input {
        width: 100%; box-sizing: border-box; padding: 10px 12px; font: inherit; font-size: .95rem;
        color: var(--wl-text); background: var(--wl-surface-2);
        border: 1px solid var(--wl-border); border-radius: var(--tmd-radius-sm, 8px);
      }
      .wl-input:focus { outline: 2px solid var(--wl-accent); outline-offset: 1px; }
      .wl-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
      .wl-stepper {
        display: inline-flex; align-items: center; overflow: hidden;
        border: 1px solid var(--wl-border); border-radius: var(--tmd-radius-sm, 8px);
      }
      .wl-stepper button {
        width: 36px; height: 36px; border: 0; cursor: pointer; font-size: 18px;
        background: var(--wl-surface-2); color: var(--wl-text);
      }
      .wl-stepper input {
        width: 72px; height: 36px; border: 0; text-align: center; font: inherit; font-weight: 700;
        background: var(--wl-surface); color: var(--wl-text); -moz-appearance: textfield;
      }
      .wl-stepper input::-webkit-inner-spin-button { -webkit-appearance: none; }
      .wl-drop {
        width: 100%; display: flex; flex-direction: column; align-items: center; gap: 6px; cursor: pointer;
        border: 2px dashed var(--wl-border); border-radius: var(--tmd-radius-sm, 12px);
        padding: 14px; background: transparent; color: var(--wl-dim); font-size: .85rem;
      }
      .wl-drop ha-icon { --mdc-icon-size: 28px; }
      .wl-drop img { width: 96px; height: 96px; object-fit: cover; border-radius: 10px; }
      .wl-sheet-acts { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
      .wl-sheet-acts.center { justify-content: center; }
      .wl-big-amt {
        font-size: 44px; font-weight: 800; display: flex; align-items: center; justify-content: center; gap: 6px;
        color: var(--wl-gold); margin: 4px 0; font-variant-numeric: tabular-nums;
      }
      .wl-big-amt ha-icon { --mdc-icon-size: 34px; }
      .wl-range { width: 100%; accent-color: var(--wl-accent); }
      .wl-range-info {
        display: flex; justify-content: space-between; gap: 8px; font-size: .75rem; color: var(--wl-dim);
        margin: 4px 0 12px; text-align: center;
      }
      .wl-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
      .wl-chip {
        cursor: pointer; font: inherit; font-size: .8rem; font-weight: 600; padding: 5px 12px; border-radius: 999px;
        background: var(--wl-surface-2); color: var(--wl-text); border: 1px solid var(--wl-border);
      }
      .wl-chip.on { border-color: var(--wl-accent); color: var(--wl-accent); }
      .wl-redeem { text-align: center; padding-top: 4px; }
      .wl-redeem h3 { justify-content: center; }
      .wl-redeem p { margin: 0 0 16px; color: var(--wl-dim); }
      .wl-big-ic {
        width: 64px; height: 64px; border-radius: 50%; display: grid; place-items: center; margin: 0 auto 10px;
        background: color-mix(in srgb, var(--wl-good) 20%, transparent); color: var(--wl-good);
      }
      .wl-big-ic ha-icon { --mdc-icon-size: 34px; }
      .wl-error { margin-top: 10px; font-size: .85rem; color: var(--tmd-bad, #e74c3c); }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

// ── Card editor ────────────────────────────────────────────────────────────
class TaskMateWishlistCardEditor extends LitElement {
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

  _buildSchema() {
    const entity = this.config && this.config.entity ? this.hass && this.hass.states && this.hass.states[this.config.entity] : null;
    const attrs = window.__taskmate_attrs && this.config && this.config.entity
      ? window.__taskmate_attrs(this.hass, this.config.entity)
      : (entity && entity.attributes) || {};
    const children = Array.isArray(attrs.children) ? attrs.children : [];
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      {
        name: "child_id",
        selector: {
          select: { options: children.map((c) => ({ value: c.id, label: c.name })), mode: "dropdown" },
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

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t("common.editor.overview_entity"),
      child_id: this._t("wishlist.editor.child"),
      title: this._t("common.editor.card_title"),
      card_design: this._t("common.design.field_label"),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t("common.editor.overview_entity_helper"),
      child_id: this._t("wishlist.editor.child_helper"),
      title: this._t("wishlist.editor.title_helper"),
    };
    return helpers[entry.name] ?? "";
  };

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
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue,
      current: this.config[key] || defaultValue,
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
      if (value === "" || value === null || value === undefined || (key === "card_design" && value === "global")) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

customElements.define("taskmate-wishlist-card", TaskMateWishlistCard);
customElements.define("taskmate-wishlist-card-editor", TaskMateWishlistCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-wishlist-card",
  name: "TaskMate Wishlist",
  description: "A child's wishlist: save towards things they want, with family pledges",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-wishlist-card", "overview"),
});
