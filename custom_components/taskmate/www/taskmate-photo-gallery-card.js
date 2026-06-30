/**
 * TaskMate Photo Gallery Card
 * A history grid of chore-evidence photos. Reads the activity sensor's
 * `photo_gallery` attribute and renders thumbnails. A card's <img> can't send a
 * bearer token, so each photo path is signed via the `auth/sign_path` WS command
 * before use.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMatePhotoGalleryCard extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object }, _signed: { state: true } };
  }

  constructor() {
    super();
    this._signed = {};        // photo_url -> signed path
    this._inflight = new Set();
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error("A TaskMate activity entity is required");
    }
    this.config = config;
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_activity" };
  }

  getCardSize() {
    return 4;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  // Open the shared in-page lightbox; fall through to the href if it's absent.
  _openPhoto(e, url, caption) {
    if (window.__taskmate_lightbox) {
      e.preventDefault();
      window.__taskmate_lightbox(url, caption, this._t("common.close"));
    }
  }

  _gallery() {
    const entity = this.hass && this.hass.states[this.config.entity];
    const items = (entity && entity.attributes && entity.attributes.photo_gallery) || [];
    return this.config.max ? items.slice(0, Number(this.config.max)) : items;
  }

  async _ensureSigned(items) {
    for (const it of items) {
      const url = it.photo_url;
      if (!url || this._signed[url] || this._inflight.has(url)) continue;
      this._inflight.add(url);
      try {
        const res = await this.hass.callWS({ type: "auth/sign_path", path: url, expires: 3600 });
        if (res && res.path) {
          this._signed = { ...this._signed, [url]: res.path };
        }
      } catch (e) {
        // Leave unsigned; the tile shows a placeholder.
        console.warn("taskmate: sign_path failed", e);
      } finally {
        this._inflight.delete(url);
      }
    }
  }

  updated() {
    this._ensureSigned(this._gallery());
  }

  render() {
    if (!this.hass || !this.config) return html``;
    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="empty"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t("common.entity_not_found", { entity: this.config.entity })}</div></div></ha-card>`;
    }
    const items = this._gallery();
    return html`
      <ha-card>
        <style>:host { --tm-gallery-header: ${_safeColor(this.config.header_color, "#5d6d7e")}; }</style>
        <div class="card-header" style="background: var(--tm-gallery-header);">
          <ha-icon icon="mdi:image-multiple"></ha-icon>
          <span>${this.config.title || this._t("gallery.default_title")}</span>
        </div>
        ${items.length === 0
          ? html`<div class="empty"><ha-icon icon="mdi:camera-off"></ha-icon><div>${this._t("gallery.empty")}</div></div>`
          : html`
            <div class="grid">
              ${items.map((it) => this._tile(it))}
            </div>`}
      </ha-card>
    `;
  }

  _tile(it) {
    const src = this._signed[it.photo_url];
    const when = this._formatDate(it.completed_at);
    return html`
      <div class="tile" title="${it.chore_name} — ${it.child_name}">
        ${src
          ? html`<a href="${src}" target="_blank" rel="noopener"
              @click="${(e) => this._openPhoto(e, src, [it.chore_name, it.child_name, when].filter(Boolean).join(" · "))}"><img src="${src}" alt="${it.chore_name}" loading="lazy"></a>`
          : html`<div class="ph"><ha-icon icon="mdi:image"></ha-icon></div>`}
        <div class="cap">
          <span class="who">${it.child_name}</span>
          <span class="what">${it.chore_name}</span>
          <span class="when">${when}${it.approved ? "" : " · " + this._t("gallery.pending")}</span>
        </div>
      </div>
    `;
  }

  _formatDate(iso) {
    if (!iso) return "";
    const tz = (this.hass && this.hass.config && this.hass.config.time_zone) || undefined;
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { timeZone: tz, month: "short", day: "numeric" });
  }

  static get styles() {
    return css`
      ha-card { overflow: hidden; }
      .card-header {
        display: flex; align-items: center; gap: 8px;
        padding: 12px 16px; color: #fff; font-weight: 600;
      }
      .grid {
        display: grid; gap: 10px; padding: 14px;
        grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
      }
      .tile { display: flex; flex-direction: column; border-radius: 8px; overflow: hidden; background: var(--secondary-background-color, #f5f5f5); }
      .tile img, .tile .ph {
        width: 100%; aspect-ratio: 1 / 1; object-fit: cover; display: block;
      }
      .tile .ph { display: flex; align-items: center; justify-content: center; color: var(--secondary-text-color); }
      .cap { padding: 6px 8px; display: flex; flex-direction: column; gap: 1px; font-size: 0.72rem; }
      .cap .who { font-weight: 600; }
      .cap .what { color: var(--primary-text-color); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .cap .when { color: var(--secondary-text-color); }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 32px 16px; color: var(--secondary-text-color); }
    `;
  }
}

customElements.define("taskmate-photo-gallery-card", TaskMatePhotoGalleryCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-photo-gallery-card",
  name: "TaskMate Photo Gallery",
  description: "History grid of chore-evidence photos",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-photo-gallery-card", "activity"),
});
