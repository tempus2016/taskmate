/**
 * TaskMate Heatmap Card
 *
 * A calendar grid of the last six weeks for each child: one square a day,
 * darker green for busier days. Reads `completion_heatmap` (from the activity
 * sensor, merged into the overview by the attribute resolver): the chores
 * done per child per day, oldest first, ending on `end`.
 *
 * With a `child_id` it is that child's grid; without one, every child's.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const DAY_MS = 86400000;

class TaskMateHeatmapCard extends LitElement {
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

  static get styles() {
    const base = css`
      :host { display: block; }
      ha-card { overflow: hidden; }
      .card-header {
        display: flex; align-items: center; gap: 10px;
        padding: 14px 18px; background: var(--taskmate-header-bg, #2e7d32); color: white;
      }
      .header-icon { --mdc-icon-size: 26px; opacity: .9; }
      .header-title { font-size: 1.2rem; font-weight: 600; }
      .card-content { padding: 14px; display: flex; flex-direction: column; gap: 16px; }
      .hm-child { display: flex; flex-direction: column; gap: 6px; }
      .hm-name { font-weight: 600; color: var(--primary-text-color); display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
      .hm-sub { font-weight: 400; font-size: .8rem; color: var(--secondary-text-color); }
      .hm-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; max-width: 320px; }
      .hm-wd { font-size: .68rem; text-align: center; color: var(--secondary-text-color); }
      .hm-grid i, .hm-legend i { display: block; aspect-ratio: 1; border-radius: 4px; background: var(--hm-0, var(--secondary-background-color, #ebedf0)); }
      .hm-grid i.pad { background: transparent; }
      .hm-grid i.today { box-shadow: 0 0 0 2px var(--primary-text-color, #333) inset; }
      .l1 { background: var(--hm-1, #c6e9c9) !important; }
      .l2 { background: var(--hm-2, #8dd295) !important; }
      .l3 { background: var(--hm-3, #4caf5c) !important; }
      .l4 { background: var(--hm-4, #2b7a37) !important; }
      .hm-legend { display: flex; align-items: center; gap: 4px; font-size: .75rem; color: var(--secondary-text-color); }
      .hm-legend i { width: 12px; height: 12px; display: inline-block; }
      .empty-state { padding: 28px 16px; text-align: center; color: var(--secondary-text-color); }
      :host([data-tm-design]:not([data-tm-design="classic"])) .hm-name { font-family: var(--tmd-font-display); color: var(--tmd-text); }
      :host([data-tm-design]:not([data-tm-design="classic"])) .hm-sub, :host([data-tm-design]:not([data-tm-design="classic"])) .hm-wd, :host([data-tm-design]:not([data-tm-design="classic"])) .hm-legend { color: var(--tmd-dim); }
      :host([data-tm-design]:not([data-tm-design="classic"])) .hm-grid i, :host([data-tm-design]:not([data-tm-design="classic"])) .hm-legend i { --hm-0: var(--tmd-surface-2); }
      :host([data-tm-design]:not([data-tm-design="classic"])) .hm-grid i.today { box-shadow: 0 0 0 2px var(--tmd-text) inset; }
      :host([data-tm-design="playroom"]) .hm-grid i { border-radius: 50%; }
      :host([data-tm-design="console"]) { --hm-1: #1b5e3a; --hm-2: #23864f; --hm-3: #2fb86b; --hm-4: #5cf29a; }
      :host([data-tm-design="accessible"]) { --hm-1: #9ad1a3; --hm-2: #4c9f5a; --hm-3: #1f6b2c; --hm-4: #0b3d14; }
      :host([data-tm-design="accessible"]) .hm-grid i { outline: 1px solid var(--tmd-border); }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) throw new Error(this._t("heatmap.error.entity_required"));
    this.config = { title: null, child_id: null, header_color: "#2e7d32", ...config };
  }

  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("taskmate-heatmap-card-editor"); }
  static getStubConfig() { return { entity: "sensor.taskmate_overview" }; }

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

  /** Weekday header, leading blanks and one cell per day, for a child. */
  _grid(heat, childId) {
    const counts = (heat.children || {})[childId] || [];
    const days = counts.length || 42;
    const end = new Date(`${heat.end || new Date().toISOString().slice(0, 10)}T12:00:00`);
    const start = new Date(end.getTime() - (days - 1) * DAY_MS);
    const lang = this.hass?.locale?.language || undefined;
    const best = Math.max(1, ...counts);
    const cells = [];
    for (let i = 0; i < days; i++) {
      const n = counts[i] || 0;
      const d = new Date(start.getTime() + i * DAY_MS);
      cells.push({
        level: n ? Math.min(4, Math.max(1, Math.ceil((n / best) * 4))) : 0,
        today: i === days - 1,
        title: `${d.toLocaleDateString(lang, { weekday: "short", day: "numeric", month: "short" })}: ${this._t(n === 1 ? "heatmap.cell_one" : "heatmap.cell", { count: n })}`,
      });
    }
    return {
      lead: (start.getDay() + 6) % 7,
      weekdays: Array.from({ length: 7 }, (_, i) => new Date(2024, 0, 1 + i).toLocaleDateString(lang, { weekday: "narrow" })),
      cells,
      total: counts.reduce((a, b) => a + b, 0),
      active: counts.filter(Boolean).length,
      days,
    };
  }

  _renderChild(child, heat, nameCls = "hm-name") {
    const g = this._grid(heat, child.id);
    return html`
      <div class="hm-child">
        <div class="${nameCls}">${child.name}
          <span class="hm-sub">${this._t("heatmap.summary", { total: g.total, active: g.active, days: g.days })}</span></div>
        <div class="hm-grid" role="img" aria-label="${this._t("heatmap.aria", { name: child.name, total: g.total, days: g.days })}">
          ${g.weekdays.map(w => html`<span class="hm-wd">${w}</span>`)}
          ${Array.from({ length: g.lead }, () => html`<i class="pad"></i>`)}
          ${g.cells.map(c => html`<i class="${c.level ? `l${c.level}` : ""} ${c.today ? "today" : ""}" title="${c.title}"></i>`)}
        </div>
      </div>`;
  }

  _legend() {
    return html`<div class="hm-legend">${this._t("heatmap.less")}
      ${[0, 1, 2, 3, 4].map(l => html`<i class="${l ? `l${l}` : ""}"></i>`)}
      ${this._t("heatmap.more")}</div>`;
  }

  _body(attrs) {
    const children = this._children(attrs);
    if (!children.length) return null;
    const heat = attrs.completion_heatmap || { children: {} };
    return html`${children.map(c => this._renderChild(c, heat))}${this._legend()}`;
  }

  /* ── classic ──────────────────────────────────────────────────────── */

  render() {
    if (!this.hass || !this.config) return html``;
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") return this._renderDesigned();

    const entity = this.hass.states[this.config.entity];
    const title = this.config.title || this._t("heatmap.default_title");
    const shell = (content) => html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, "#2e7d32")}; }</style>
        <div class="card-header"><ha-icon class="header-icon" icon="mdi:calendar-check"></ha-icon><span class="header-title">${title}</span></div>
        <div class="card-content">${content}</div>
      </ha-card>`;
    if (!entity) return shell(html`<div class="empty-state">${this._t("common.entity_not_found", { entity: this.config.entity })}</div>`);
    if (entity.state === "unavailable" || entity.state === "unknown") return shell(html`<div class="empty-state">${this._t("common.unavailable")}</div>`);
    return shell(this._body(this._attrs(entity)) || html`<div class="empty-state">${this._t("common.no_children")}</div>`);
  }

  /* ── designed (playroom / console / cleanpro / accessible / graphite) ── */

  _renderDesigned() {
    const entity = this.hass.states[this.config.entity];
    const hd = _safeColor(this.config.header_color, "#2e7d32");
    const head = html`<div class="tmd-hd"><span class="ic">📅</span><span class="tt">${this.config.title || this._t("heatmap.default_title")}</span></div>`;
    let body;
    if (!entity) body = html`<div class="tmd-empty">${this._t("common.entity_not_found", { entity: this.config.entity })}</div>`;
    else if (entity.state === "unavailable" || entity.state === "unknown") body = html`<div class="tmd-empty">${this._t("common.unavailable")}</div>`;
    else body = this._body(this._attrs(entity)) || html`<div class="tmd-empty">${this._t("common.no_children")}</div>`;
    return html`<ha-card class="tmd" style="--hd:${hd}">${head}<div class="tmd-bd"><div class="card-content">${body}</div></div></ha-card>`;
  }
}

class TaskMateHeatmapCardEditor extends LitElement {
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
      { name: "entity", selector: { entity: { domain: "sensor" } } },
      { name: "title", selector: { text: {} } },
      {
        name: "child_id",
        selector: {
          select: {
            options: [
              { value: "__all__", label: this._t("common.editor.filter_by_child_all") },
              ...children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: "dropdown",
          },
        },
      },
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
      show_adults: this._t("common.editor.show_adults"),
      entity: this._t("common.editor.overview_entity"),
      title: this._t("heatmap.editor.title"),
      child_id: this._t("common.editor.filter_by_child"),
      card_design: this._t("common.design.field_label"),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      show_adults: this._t("common.editor.show_adults_helper"),
      entity: this._t("common.editor.overview_entity_helper"),
      child_id: this._t("heatmap.editor.child_helper"),
    };
    return helpers[entry.name] ?? "";
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      title: this.config.title || "",
      child_id: this.config.child_id || "__all__",
      card_design: this.config.card_design || "global",
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
      ${this._renderColourPicker("header_color", "#2e7d32")}
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
      if (
        value === "" || value === null || value === undefined
        || (key === "child_id" && value === "__all__")
        || (key === "card_design" && value === "global")
      ) {
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

customElements.define("taskmate-heatmap-card", TaskMateHeatmapCard);
customElements.define("taskmate-heatmap-card-editor", TaskMateHeatmapCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-heatmap-card",
  name: "TaskMate Heatmap",
  description: "A calendar of the last six weeks for each child — darker green for busier days",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest ? window.__taskmate_suggest(hass, entityId, "taskmate-heatmap-card", "overview") : undefined,
});
