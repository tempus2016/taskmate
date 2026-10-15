/**
 * TaskMate Pet Card
 *
 * A child's virtual pet. It hatches from an egg and grows with every chore
 * the child finishes after adopting it, bounces on days they do one, gets
 * sleepy after a missed day, and wears accessories the child unlocks by
 * levelling up (bow, top hat, scarf, crown). Before adoption the card is the
 * adoption form: pick a creature, give it a name.
 *
 * Reads `pet` from the child's entry in the overview sensor's `children`
 * (present only while pets are switched on in the admin panel). Single
 * layout consuming the design tokens, like the bounty card; layout classes
 * carry a pt- prefix.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);
const DEFAULT_ACCENT = "#16a085";
const SPECIES = { dragon: "🐉", cat: "🐱", dog: "🐶", bunny: "🐰", dino: "🦖", unicorn: "🦄" };
const STAGE_SCALE = { egg: 0.8, baby: 0.62, kid: 0.76, teen: 0.9, grown: 1 };
const HEAD = { crown: "👑", top_hat: "🎩" };
const NECK = { scarf: "🧣", bow: "🎀" };

class TaskMatePetCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _species: { type: String },
      _busy: { type: Boolean },
      _error: { type: String },
      _petting: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._species = "dragon";
    this._busy = false;
    this._error = "";
    this._petting = false;
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
    return document.createElement("taskmate-pet-card-editor");
  }

  getCardSize() {
    return 5;
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

  _child() {
    return (this._attrs().children || []).find(c => String(c.id) === String(this.config.child_id));
  }

  _applyDesign() {
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--pt-accent", _safeColor(configured, DEFAULT_ACCENT));
    } else {
      this.style.removeProperty("--pt-accent");
    }
    return design;
  }

  async _adopt(child) {
    const input = this.renderRoot && this.renderRoot.querySelector("#pt-name");
    const name = String((input && input.value) || "").trim();
    if (!name) { this._error = this._t("pet.name_needed"); return; }
    this._busy = true;
    this._error = "";
    try {
      await this.hass.callService("taskmate", "adopt_pet", { child_id: child.id, species: this._species, name });
    } catch (err) {
      this._error = String(err?.message || err);
    } finally {
      this._busy = false;
    }
  }

  _pet() {
    // A tap is a cuddle: a little hop and hearts, nothing saved.
    this._petting = true;
    clearTimeout(this._pettingTimer);
    this._pettingTimer = setTimeout(() => { this._petting = false; }, 900);
  }

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const child = this._child();
    const title = this.config.title || (child && child.pet && child.pet.adopted ? child.pet.name : this._t("pet.title"));
    if (!child) return html`<ha-card>${this._header(title)}<div class="pt-empty">${this._t("pet.no_child")}</div></ha-card>`;
    const pet = child.pet;
    if (!pet) return html`<ha-card>${this._header(title)}<div class="pt-empty">${this._t("pet.off")}</div></ha-card>`;
    return html`<ha-card>${this._header(title, pet)}${pet.adopted ? this._renderPet(child, pet) : this._renderAdopt(child)}</ha-card>`;
  }

  _header(title, pet) {
    return html`
      <div class="pt-hd">
        <ha-icon class="pt-hd-icon" icon="mdi:paw"></ha-icon>
        <div class="pt-hd-text">
          <div class="pt-hd-title">${title}</div>
          ${pet && pet.adopted ? html`<div class="pt-hd-sub">${this._t(`pet.stage_${pet.stage}`, { species: this._t(`pet.species_${pet.species}`) })}</div>` : ""}
        </div>
      </div>`;
  }

  _renderPet(child, pet) {
    const scale = STAGE_SCALE[pet.stage] || 1;
    const acc = pet.accessories || [];
    const head = acc.includes("crown") ? HEAD.crown : acc.includes("top_hat") ? HEAD.top_hat : "";
    const neck = acc.includes("scarf") ? NECK.scarf : acc.includes("bow") ? NECK.bow : "";
    const face = pet.stage === "egg" ? "🥚" : (SPECIES[pet.species] || "🐉");
    const toNext = pet.next_at != null ? pet.next_at - pet.chores : 0;
    const span = pet.next_at != null ? pet.next_at - pet.stage_at : 1;
    const pct = pet.next_at != null ? Math.round(((pet.chores - pet.stage_at) / span) * 100) : 100;
    return html`
      <div class="pt-body">
        <button type="button" class="pt-stage mood-${pet.mood} stage-${pet.stage} ${this._petting ? "petting" : ""}"
                aria-label="${this._t("pet.cuddle", { name: pet.name })}" @click=${() => this._pet()}>
          <span class="pt-creature" style="--pt-scale:${scale}">
            ${head ? html`<span class="pt-head" aria-hidden="true">${head}</span>` : ""}
            <span class="pt-face">${face}</span>
            ${neck ? html`<span class="pt-neck" aria-hidden="true">${neck}</span>` : ""}
          </span>
          ${pet.mood === "sleepy" ? html`<span class="pt-zzz" aria-hidden="true">💤</span>` : ""}
          ${pet.mood === "proud" ? html`<span class="pt-spark" aria-hidden="true">✨</span>` : ""}
          ${this._petting ? html`<span class="pt-hearts" aria-hidden="true">💕</span>` : ""}
        </button>
        <div class="pt-mood">${this._t(`pet.mood_${pet.mood}`, { name: pet.name })}</div>
        <div class="pt-grow">
          <div class="pt-grow-text">${pet.next_at != null
            ? this._t(toNext === 1 ? "pet.grow_one" : "pet.grow_many", { count: toNext })
            : this._t("pet.fully_grown", { name: pet.name })}</div>
          <span class="pt-bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"><i style="width:${pct}%"></i></span>
        </div>
        <div class="pt-acc">
          ${["bow", "top_hat", "scarf", "crown"].map(a => html`
            <span class="pt-acc-item ${acc.includes(a) ? "on" : ""}" title="${this._t(`pet.acc_${a}`)}">
              <span>${{ ...HEAD, ...NECK }[a]}</span>
              <small>${acc.includes(a) ? this._t(`pet.acc_${a}`) : this._t("pet.acc_locked", { level: { bow: 3, top_hat: 8, scarf: 15, crown: 25 }[a] })}</small>
            </span>`)}
        </div>
      </div>`;
  }

  _renderAdopt(child) {
    return html`
      <div class="pt-body">
        <div class="pt-adopt-q">${this._t("pet.adopt_question", { name: child.name })}</div>
        <div class="pt-pick" role="radiogroup" aria-label="${this._t("pet.adopt_question", { name: child.name })}">
          ${Object.entries(SPECIES).map(([id, e]) => html`
            <button type="button" role="radio" aria-checked="${this._species === id}" class="pt-opt ${this._species === id ? "on" : ""}"
                    @click=${() => { this._species = id; }}>
              <span>${e}</span><small>${this._t(`pet.species_${id}`)}</small>
            </button>`)}
        </div>
        <input id="pt-name" class="pt-name" maxlength="24" placeholder="${this._t("pet.name_placeholder")}" aria-label="${this._t("pet.name_placeholder")}">
        ${this._error ? html`<div class="pt-err" role="alert">${this._error}</div>` : ""}
        <button class="pt-btn" ?disabled=${this._busy} @click=${() => this._adopt(child)}>🥚 ${this._t("pet.adopt")}</button>
      </div>`;
  }

  static get styles() {
    const base = css`
      :host { display: block; --pt-accent: var(--tmd-accent, #16a085); }
      ha-card { overflow: hidden; background: var(--tmd-surface, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color)); border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px)); font-family: var(--tmd-font-body, inherit); }
      .pt-hd { display: flex; align-items: center; gap: 12px; padding: 14px 18px; background: var(--pt-accent); color: var(--tmd-hd-text, #fff); }
      :host([data-tm-design="playroom"]) .pt-hd { background: linear-gradient(135deg, var(--pt-accent), color-mix(in srgb, var(--pt-accent) 72%, #fff)); }
      .pt-hd-icon { --mdc-icon-size: 28px; }
      .pt-hd-title { font-family: var(--tmd-font-display, inherit); font-size: 1.3rem; font-weight: 600; }
      .pt-hd-sub { font-size: .85rem; opacity: .9; }
      .pt-empty { padding: 26px; text-align: center; color: var(--tmd-dim, var(--secondary-text-color)); }
      .pt-body { padding: 16px; display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
      .pt-stage { position: relative; width: 190px; height: 170px; border: 0; cursor: pointer; border-radius: 50% 50% 44% 44%;
        background: radial-gradient(circle at 50% 75%, color-mix(in srgb, var(--pt-accent) 22%, transparent), transparent 70%); }
      .pt-creature { position: absolute; inset: 0; display: grid; place-items: center; transform: scale(var(--pt-scale)); transform-origin: 50% 85%; }
      .pt-face { font-size: 110px; line-height: 1; }
      .pt-head { position: absolute; top: -4px; left: 50%; transform: translateX(-50%) rotate(-8deg); font-size: 52px; z-index: 2; } /* rtl-ok: centred horizontally */
      .pt-neck { position: absolute; bottom: 18px; left: 50%; transform: translateX(-50%); font-size: 40px; z-index: 2; } /* rtl-ok: centred horizontally */
      .mood-happy .pt-creature, .mood-proud .pt-creature { animation: pt-bounce 1.6s ease-in-out infinite; }
      .mood-content .pt-creature { animation: pt-sway 3s ease-in-out infinite; }
      .mood-sleepy .pt-face { filter: grayscale(.35) brightness(.92); }
      .stage-egg .pt-creature { animation: pt-wobble 2.2s ease-in-out infinite; }
      .petting .pt-creature { animation: pt-hop .5s ease-out; }
      .pt-zzz { position: absolute; top: 6px; inset-inline-end: 6px; font-size: 32px; animation: pt-float 2.4s ease-in-out infinite; }
      .pt-spark { position: absolute; top: 6px; inset-inline-start: 8px; font-size: 30px; animation: pt-float 1.8s ease-in-out infinite; }
      .pt-hearts { position: absolute; top: 0; left: 50%; transform: translateX(-50%); font-size: 30px; animation: pt-up .9s ease-out forwards; } /* rtl-ok: centred horizontally */
      .pt-mood { font-weight: 700; font-size: 1.05rem; }
      .pt-grow { width: 100%; max-width: 320px; display: flex; flex-direction: column; gap: 6px; }
      .pt-grow-text { font-size: .9rem; color: var(--tmd-dim, var(--secondary-text-color)); }
      .pt-bar { display: block; height: 10px; border-radius: 6px; background: var(--tmd-surface-2, rgba(127,127,127,.15)); overflow: hidden; }
      .pt-bar i { display: block; height: 100%; background: var(--pt-accent); border-radius: 6px; }
      .pt-acc { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
      .pt-acc-item { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 6px 10px; border-radius: 12px; min-width: 64px;
        background: var(--tmd-surface-2, rgba(127,127,127,.1)); opacity: .45; filter: grayscale(1); }
      .pt-acc-item.on { opacity: 1; filter: none; background: color-mix(in srgb, var(--pt-accent) 14%, transparent); }
      .pt-acc-item span { font-size: 24px; }
      .pt-acc-item small { font-size: .7rem; }
      .pt-adopt-q { font-weight: 700; font-size: 1.05rem; }
      .pt-pick { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; width: 100%; max-width: 330px; }
      .pt-opt { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px; border-radius: 14px; cursor: pointer; font: inherit;
        border: 2px solid var(--tmd-border, var(--divider-color, #ddd)); background: var(--tmd-surface, var(--card-background-color, #fff)); color: inherit; }
      .pt-opt span { font-size: 38px; line-height: 1.1; }
      .pt-opt small { font-size: .75rem; }
      .pt-opt.on { border-color: var(--pt-accent); background: color-mix(in srgb, var(--pt-accent) 12%, transparent); }
      .pt-name { width: 100%; max-width: 330px; box-sizing: border-box; padding: 10px 12px; font: inherit; font-size: 1rem; border-radius: 12px;
        border: 2px solid var(--tmd-border, var(--divider-color, #ddd)); background: var(--tmd-surface, var(--card-background-color, #fff)); color: inherit; }
      .pt-btn { border: 0; border-radius: 999px; padding: 10px 22px; font: inherit; font-weight: 800; cursor: pointer; background: var(--pt-accent); color: #fff; }
      .pt-btn:disabled { opacity: .5; }
      .pt-err { color: var(--tmd-bad, var(--error-color, #c62828)); font-size: .85rem; }
      @keyframes pt-bounce { 0%, 100% { transform: scale(var(--pt-scale)) translateY(0); } 50% { transform: scale(var(--pt-scale)) translateY(-10px); } }
      @keyframes pt-sway { 0%, 100% { transform: scale(var(--pt-scale)) rotate(-3deg); } 50% { transform: scale(var(--pt-scale)) rotate(3deg); } }
      @keyframes pt-wobble { 0%, 80%, 100% { transform: scale(var(--pt-scale)) rotate(0); } 85% { transform: scale(var(--pt-scale)) rotate(-8deg); } 92% { transform: scale(var(--pt-scale)) rotate(8deg); } }
      @keyframes pt-hop { 0% { transform: scale(var(--pt-scale)); } 40% { transform: scale(calc(var(--pt-scale) * 1.08)) translateY(-16px); } 100% { transform: scale(var(--pt-scale)); } }
      @keyframes pt-float { 0%, 100% { transform: translateY(0); opacity: .9; } 50% { transform: translateY(-8px); opacity: .6; } }
      @keyframes pt-up { from { transform: translate(-50%, 10px); opacity: 1; } to { transform: translate(-50%, -30px); opacity: 0; } }
      @media (prefers-reduced-motion: reduce) { .pt-creature, .pt-zzz, .pt-spark, .pt-hearts { animation: none !important; } }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

class TaskMatePetCardEditor extends LitElement {
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
      { name: "child_id", selector: { select: { options: children.map(c => ({ value: c.id, label: c.name })), mode: "dropdown" } } },
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
    child_id: this._t("pet.editor.child"),
    title: this._t("common.editor.card_title"),
    card_design: this._t("common.design.field_label"),
  }[entry.name] ?? entry.name);

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      child_id: this.config.child_id || "",
      title: this.config.title || "",
      card_design: this.config.card_design || "global",
    };
    return html`<ha-form .hass=${this.hass} .data=${data} .schema=${this._buildSchema()}
      .computeLabel=${this._computeLabel} @value-changed=${this._formChanged}></ha-form>`;
  }

  _formChanged(e) {
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(e.detail.value || {})) {
      if (value === "" || value === null || value === undefined || (key === "card_design" && value === "global")) delete newConfig[key];
      else newConfig[key] = value;
    }
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: newConfig }, bubbles: true, composed: true }));
  }

  static get styles() {
    return css`:host { display: block; }`;
  }
}

customElements.define("taskmate-pet-card", TaskMatePetCard);
customElements.define("taskmate-pet-card-editor", TaskMatePetCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-pet-card",
  name: "TaskMate Pet",
  description: "A virtual pet that grows as the child does chores",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest ? window.__taskmate_suggest(hass, entityId, "taskmate-pet-card", "overview") : undefined,
});
