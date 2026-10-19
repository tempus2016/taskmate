/**
 * TaskMate Personal Bests Card (#1099)
 *
 * A child's own records board: longest streak, most points in a day and in a
 * week, most chores in a day and the biggest single award, each with the day
 * it was set. A record beaten today glows for the rest of the day.
 *
 * Reads `children[].personal_bests` from the overview sensor. With a
 * `child_id` it is that child's board; without one it shows every child.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

const RECORDS = [
  { key: "longest_streak", icon: "mdi:fire", emoji: "🔥" },
  { key: "best_day_points", icon: "mdi:star-circle", emoji: "⭐" },
  { key: "best_week_points", icon: "mdi:calendar-star", emoji: "📅" },
  { key: "best_day_chores", icon: "mdi:check-all", emoji: "✅" },
  { key: "best_single_award", icon: "mdi:trophy", emoji: "🏆" },
];

class TaskMatePersonalBestsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
    };
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass")) {
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

  _avatarGlyph(source, fallback = "mdi:account-circle", cls = "pb-face-img") {
    const face = window.__taskmate_child_visual(source);
    return face.kind === "image"
      ? html`<img class="${cls}" src="${face.url}" alt="" loading="lazy">`
      : html`<ha-icon icon="${face.kind === "icon" ? face.icon : fallback}"></ha-icon>`;
  }

  static get styles() {
    const base = css`
      :host { display: block; }
      ha-card { overflow: hidden; }

      .card-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 14px 18px; background: var(--taskmate-header-bg, #d35400); color: white;
      }
      .header-content { display: flex; align-items: center; gap: 10px; }
      .header-icon { --mdc-icon-size: 28px; opacity: 0.9; }
      .header-title { font-size: 1.2rem; font-weight: 600; }
      .header-count { font-size: .85rem; font-weight: 700; background: rgba(255,255,255,.25); border-radius: 999px; padding: 3px 10px; }

      .card-content { padding: 14px; display: flex; flex-direction: column; gap: 14px; }

      .pb-child { border: 1px solid var(--divider-color, #e0e0e0); border-radius: 14px; overflow: hidden;
        background: var(--card-background-color, #fff); }
      .pb-child-head { display: flex; align-items: center; gap: 12px; padding: 12px 14px 8px; }
      .pb-avatar { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, #d35400, #f39c12); color: #fff; flex-shrink: 0; overflow: hidden; }
      .pb-avatar ha-icon { --mdc-icon-size: 26px; color: white; }
      .pb-face-img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }
      .pb-name { font-weight: 600; font-size: 1rem; color: var(--primary-text-color); }
      .pb-sub { font-size: .8rem; color: var(--secondary-text-color); }

      .pb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; padding: 6px 14px 14px; }
      .pb-tile { position: relative; border-radius: 12px; padding: 10px 12px; background: var(--secondary-background-color, #f5f5f5);
        display: flex; flex-direction: column; gap: 2px; min-height: 76px; }
      .pb-tile.new { background: #fff3cd; box-shadow: 0 0 0 2px #f1c40f inset; }
      .pb-tile.empty { opacity: .55; }
      .pb-tile-k { display: flex; align-items: center; gap: 6px; font-size: .72rem; font-weight: 700; letter-spacing: .03em;
        text-transform: uppercase; color: var(--secondary-text-color); min-width: 0; }
      .pb-tile-k .pb-tile-label { flex: 1; min-width: 0; }
      .pb-tile-k ha-icon { --mdc-icon-size: 16px; }
      .pb-tile-v { font-size: 1.5rem; font-weight: 800; color: var(--primary-text-color); line-height: 1.1; }
      .pb-tile-d { font-size: .75rem; color: var(--secondary-text-color); }
      .pb-new-tag { flex: none; font-size: .65rem; font-weight: 800; background: #f1c40f;
        color: #5a4300; border-radius: 999px; padding: 2px 7px; text-transform: uppercase; }

      .empty-state, .error-state { padding: 32px 16px; text-align: center; color: var(--secondary-text-color); }
      .empty-state ha-icon, .error-state ha-icon { --mdc-icon-size: 40px; display: block; margin: 0 auto 8px; opacity: .6; }

      /* Designed layouts (shared kit in taskmate-design.js) */
      .pb-d-child { margin-bottom: 12px; }
      .pb-d-child:last-child { margin-bottom: 0; }
      .pb-d-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
      .pb-d-name { font-family: var(--tmd-font-display); font-weight: 800; font-size: 15px; }
      .pb-d-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; }
      .pb-d-tile { position: relative; border-radius: var(--tmd-radius-sm); padding: 10px 12px; background: var(--tmd-surface-2);
        border: 1px solid var(--tmd-border); min-height: 72px; display: flex; flex-direction: column; gap: 2px; }
      .pb-d-tile.new { border-color: var(--tmd-accent); box-shadow: 0 0 0 1px var(--tmd-accent) inset; }
      .pb-d-tile.empty { opacity: .5; }
      .pb-d-tile .stat { display: contents; }
      .pb-d-date { font-size: 11px; color: var(--tmd-dim); }
      .pb-d-tile .k { display: flex; align-items: flex-start; gap: 4px; }
      .pb-d-tile .k .pb-d-label { flex: 1; min-width: 0; }
      .pb-d-new { flex: none; padding: 2px 7px; font-size: 10px; }
      :host([data-tm-design="playroom"]) .pb-d-tile { border-radius: 16px; border: 0; }
      :host([data-tm-design="playroom"]) .pb-d-tile.new { background: color-mix(in srgb, var(--tmd-accent) 16%, var(--tmd-surface-2)); }
      :host([data-tm-design="console"]) .pb-d-tile.new { box-shadow: 0 0 14px color-mix(in srgb, var(--tmd-accent) 45%, transparent); }
      :host([data-tm-design="console"]) .pb-d-tile .v { font-variant-numeric: tabular-nums; }
      :host([data-tm-design="graphite"]) .pb-d-tile { background: transparent; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) throw new Error(this._t('bests.error.entity_required'));
    this.config = {
      title: null,
      child_id: null,
      header_color: '#d35400',
      ...config,
    };
  }

  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("taskmate-personal-bests-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  /* ── data ─────────────────────────────────────────────────────────── */

  _attrs(entity) {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
  }

  _children(attrs) {
    let children = window.__taskmate_family_children
      ? window.__taskmate_family_children(attrs.children || [], this.config)
      : (attrs.children || []);
    if (this.config.child_id) children = children.filter(c => c.id === this.config.child_id);
    return children;
  }

  /** The five tiles for a child, in a fixed order, empty ones included. */
  _tiles(child, pointsName) {
    const bests = child.personal_bests || {};
    const fresh = new Set(Array.isArray(bests.new_today) ? bests.new_today : []);
    return RECORDS.map((r) => {
      const rec = bests[r.key];
      return {
        ...r,
        label: this._t(`bests.record_${r.key}`, { points_name: pointsName }),
        value: rec ? rec.value : null,
        date: rec && rec.date ? this._fmtDate(rec.date) : "",
        fresh: fresh.has(r.key),
        previous: rec && rec.previous != null ? rec.previous : null,
      };
    });
  }

  _fmtDate(iso) {
    const d = new Date(`${iso}T12:00:00`);
    if (isNaN(d)) return iso;
    return d.toLocaleDateString(this.hass?.locale?.language || undefined, { day: "numeric", month: "short" });
  }

  _freshCount(children) {
    return children.reduce((n, c) => n + ((c.personal_bests && c.personal_bests.new_today) || []).length, 0);
  }

  /* ── classic ──────────────────────────────────────────────────────── */

  render() {
    if (!this.hass || !this.config) return html``;

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") return this._renderDesigned(design);

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.unavailable')}</div></div></ha-card>`;
    }

    const attrs = this._attrs(entity);
    const children = this._children(attrs);
    const pointsName = attrs.points_name || this._t("common.points");
    const fresh = this._freshCount(children);

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, '#d35400')}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:trophy-variant"></ha-icon>
            <span class="header-title">${this.config.title || this._t('bests.default_title')}</span>
          </div>
          ${fresh > 0 ? html`<span class="header-count">${this._t('bests.new_count', { count: fresh })}</span>` : ""}
        </div>
        <div class="card-content">
          ${children.length === 0
            ? html`<div class="empty-state"><ha-icon icon="mdi:account-group"></ha-icon><div>${this._t('common.no_children')}</div></div>`
            : children.map((child) => this._renderChild(child, pointsName))}
        </div>
      </ha-card>
    `;
  }

  _renderChild(child, pointsName) {
    const tiles = this._tiles(child, pointsName);
    const any = tiles.some(t => t.value != null);
    return html`
      <div class="pb-child">
        <div class="pb-child-head">
          <div class="pb-avatar">${this._avatarGlyph(child)}</div>
          <div>
            <div class="pb-name">${child.name}</div>
            <div class="pb-sub">${any ? this._t('bests.subtitle') : this._t('bests.none_yet')}</div>
          </div>
        </div>
        <div class="pb-grid">
          ${tiles.map((t) => html`
            <div class="pb-tile ${t.fresh ? "new" : ""} ${t.value == null ? "empty" : ""}" title="${t.label}">
              <div class="pb-tile-k"><ha-icon icon="${t.icon}"></ha-icon><span class="pb-tile-label">${t.label}</span>${t.fresh ? html`<span class="pb-new-tag">${this._t('bests.new_tag')}</span>` : ""}</div>
              <div class="pb-tile-v">${t.value == null ? "—" : t.value}</div>
              <div class="pb-tile-d">${t.fresh && t.previous != null
                ? this._t('bests.beat_previous', { previous: t.previous })
                : (t.date || (t.value == null ? this._t('bests.not_yet') : ""))}</div>
            </div>`)}
        </div>
      </div>`;
  }

  /* ── designed (playroom / console / cleanpro / accessible / graphite) ── */

  _designTone(i) { return `var(--tmd-c${(i % 6) + 1})`; }

  _av(child, tone, size) {
    const face = window.__taskmate_child_visual(child);
    const inner = face.kind === "icon"
      ? html`<ha-icon icon="${face.icon}"></ha-icon>`
      : face.kind === "image"
        ? html`<img src="${face.url}" alt="${child.name || ''}">`
        : (child.name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
    return html`<div class="av" style="--av:${size}px;--ac:${tone}">${inner}</div>`;
  }

  _designHeader(hd, fresh) {
    const title = this.config.title || this._t('bests.default_title');
    return html`
      <div class="tmd-hd">
        <span class="ic">🏆</span>
        <span class="tt">${title}</span>
        ${fresh > 0 ? html`<span class="pill">${this._t('bests.new_count', { count: fresh })}</span>` : ""}
      </div>`;
  }

  _renderDesigned(design) {
    const entity = this.hass.states[this.config.entity];
    const hd = _safeColor(this.config.header_color, '#d35400');
    if (!entity) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${this._designHeader(hd, 0)}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div>
      </ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${this._designHeader(hd, 0)}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.unavailable')}</div></div>
      </ha-card>`;
    }
    const attrs = this._attrs(entity);
    const children = this._children(attrs);
    const pointsName = attrs.points_name || this._t("common.points");
    const fresh = this._freshCount(children);
    const body = children.length === 0
      ? html`<div class="tmd-empty">${this._t('common.no_children')}</div>`
      : children.map((child, i) => this._designChild(child, i, pointsName, design));
    return html`<ha-card class="tmd" style="--hd:${hd}">${this._designHeader(hd, fresh)}<div class="tmd-bd">${body}</div></ha-card>`;
  }

  _designChild(child, i, pointsName, design) {
    const tone = this._designTone(i);
    const tiles = this._tiles(child, pointsName);
    const any = tiles.some(t => t.value != null);
    const emoji = design === "playroom";
    return html`
      <div class="pb-d-child" style="--ac:${tone}">
        <div class="pb-d-head">
          ${this._av(child, tone, 34)}
          <div style="flex:1;min-width:0">
            <div class="pb-d-name">${child.name}</div>
            <div class="muted" style="font-size:12px">${any ? this._t('bests.subtitle') : this._t('bests.none_yet')}</div>
          </div>
        </div>
        <div class="pb-d-grid">
          ${tiles.map((t) => html`
            <div class="pb-d-tile stat ${t.fresh ? "new" : ""} ${t.value == null ? "empty" : ""}" title="${t.label}">
              <div class="k"><span class="pb-d-label">${emoji ? html`${t.emoji} ` : html`<ha-icon style="--mdc-icon-size:14px;vertical-align:-2px" icon="${t.icon}"></ha-icon> `}${t.label}</span>${t.fresh ? html`<span class="chip soft pb-d-new">${this._t('bests.new_tag')}</span>` : ""}</div>
              <div class="v">${t.value == null ? "—" : t.value}</div>
              <div class="pb-d-date">${t.fresh && t.previous != null
                ? this._t('bests.beat_previous', { previous: t.previous })
                : (t.date || (t.value == null ? this._t('bests.not_yet') : ""))}</div>
            </div>`)}
        </div>
      </div>`;
  }
}

class TaskMatePersonalBestsCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  setConfig(config) { this.config = config; }

  _buildSchema() {
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const children = entity?.attributes?.children || [];
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '__all__', label: this._t('common.editor.filter_by_child_all') },
              ...children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'card_design',
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: 'global', label: 'Use global default' }],
            mode: 'dropdown',
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      show_adults: this._t('common.editor.show_adults'),
      entity: this._t('common.editor.overview_entity'),
      title: this._t('bests.editor.title'),
      child_id: this._t('common.editor.filter_by_child'),
      card_design: this._t('common.design.field_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      show_adults: this._t('common.editor.show_adults_helper'),
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('bests.editor.child_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      child_id: this.config.child_id || '__all__',
      card_design: this.config.card_design || 'global',
    };
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${this.config.show_adults === true ? { ...data, show_adults: true } : data}
        .schema=${this._buildSchema().concat(window.__taskmate_adults_field ? window.__taskmate_adults_field(this.hass, this.config) : [])}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}
      ></ha-form>
      ${this._renderColourPicker('header_color', '#d35400')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    const current = this.config[key] || defaultValue;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current,
      label: this._t('common.editor.header_colour'),
      helper: this._t('common.editor.header_colour_helper'),
      resetLabel: this._t('common.reset'),
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (
        value === '' || value === null || value === undefined
        || (key === 'child_id' && value === '__all__')
        || (key === 'card_design' && value === 'global')
      ) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
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

customElements.define("taskmate-personal-bests-card", TaskMatePersonalBestsCard);
customElements.define("taskmate-personal-bests-card-editor", TaskMatePersonalBestsCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-personal-bests-card",
  name: "TaskMate Personal Bests",
  description: "Each child's own records: longest streak, best day, best week and biggest award",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest ? window.__taskmate_suggest(hass, entityId, "taskmate-personal-bests-card", "overview") : undefined,
});
