/**
 * TaskMate Routine Card (#676)
 *
 * A guided, one-task-at-a-time flow for morning and bedtime routines. The
 * child card is a checklist — good for scanning, poor for a five-year-old
 * being walked through getting ready. This shows a single task at a time with
 * a big Done button, a progress bar, and a celebration at the end.
 *
 * Availability comes from the backend's own chore_availability matrix rather
 * than a re-implementation of the child card's filter, so the weather gate,
 * reactive deadlines, dependencies and rotation are all honoured for free.
 *
 * Version: 1.0.0
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

const TIME_CATEGORIES = ["all", "morning", "afternoon", "evening", "night", "anytime"];

class TaskMateRoutineCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _index: { type: Number },
      _finished: { type: Boolean },
      _busy: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._index = 0;
    this._finished = false;
    this._busy = false;
    // Chores completed during THIS run, so the finish screen can total what
    // was just earned rather than everything the child has done today.
    this._runCompleted = new Map();
    // Tasks the child chose to leave for later. Kept for this run only.
    this._skipped = new Set();
  }

  setConfig(config) {
    if (!config.entity) throw new Error("You need to define an entity");
    if (!config.child_id) throw new Error("You need to define a child_id");
    if (config.time_category && !TIME_CATEGORIES.includes(config.time_category)) {
      throw new Error(`time_category must be one of: ${TIME_CATEGORIES.join(", ")}`);
    }
    this.config = config;
  }

  getCardSize() { return 8; }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", child_id: "", time_category: "morning" };
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

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
  }

  _child() {
    const attrs = this._attrs();
    return (attrs.children || []).find(c => String(c.id) === String(this.config.child_id));
  }

  /**
   * The routine's task list: chores the backend says are available to this
   * child, in the child's configured order, filtered to the card's period.
   * Chores completed during this run stay in the list (so the progress bar
   * doesn't jump around) but are marked done.
   */
  _tasks() {
    const attrs = this._attrs();
    const child = this._child();
    if (!child) return [];

    const childId = String(child.id);
    const availability = attrs.chore_availability || {};
    const period = this.config.time_category || "all";

    const completedToday = new Set(
      (attrs.todays_completions || [])
        .filter(c => String(c.child_id) === childId && !c.bonus_subtask_id)
        .map(c => String(c.chore_id))
    );

    const order = (child.chore_order || []).map(String);
    const list = (attrs.chores || []).filter(chore => {
      const id = String(chore.id);
      // Anything finished in this run stays visible as a completed step.
      if (this._runCompleted.has(id)) return true;
      if (!availability[id] || availability[id][childId] !== true) return false;
      if (completedToday.has(id)) return false;
      if (period !== "all" && chore.time_category !== period) return false;
      return true;
    });

    list.sort((a, b) => {
      const ai = order.indexOf(String(a.id));
      const bi = order.indexOf(String(b.id));
      if (ai !== -1 && bi !== -1) return ai - bi;
      if (ai !== -1) return -1;
      if (bi !== -1) return 1;
      return String(a.name).localeCompare(String(b.name));
    });
    return list;
  }

  _pointsFor(chore) {
    return chore.effective_points ?? chore.points ?? 0;
  }

  async _complete(chore) {
    if (this._busy) return;
    const child = this._child();
    if (!child) return;
    this._busy = true;
    try {
      // Prefer the per-chore button entity so HA state-trigger automations
      // fire, exactly as the child card does. Fall back to the service when
      // the entity isn't registered yet (e.g. right after a restart).
      const buttonEntityId = window.__taskmate_find_button
        && window.__taskmate_find_button(this.hass, child.id, "complete", chore.id);
      if (buttonEntityId) {
        await this.hass.callService("button", "press", { entity_id: buttonEntityId });
      } else {
        await this.hass.callService("taskmate", "complete_chore", {
          chore_id: chore.id, child_id: child.id,
        });
      }
      this._runCompleted.set(String(chore.id), {
        points: this._pointsFor(chore),
        pending: chore.requires_approval !== false,
      });
      // Skipped then done later is not "left for later" — otherwise the finish
      // screen claims tasks are outstanding that the child actually did.
      this._skipped.delete(String(chore.id));
      this._advance();
    } catch (err) {
      // Surface rather than silently stalling the routine on a failed call.
      this.dispatchEvent(new CustomEvent("hass-notification", {
        detail: { message: String(err?.message || err) }, bubbles: true, composed: true,
      }));
    } finally {
      this._busy = false;
      this.requestUpdate();
    }
  }

  _advance() {
    const total = this._tasks().length;
    if (this._index >= total - 1) {
      this._finished = true;
    } else {
      this._index = this._index + 1;
    }
    this.requestUpdate();
  }

  _skip() {
    const tasks = this._tasks();
    const chore = tasks[this._index];
    if (chore) this._skipped.add(String(chore.id));
    this._advance();
  }

  _back() {
    if (this._finished) { this._finished = false; return; }
    if (this._index > 0) this._index = this._index - 1;
    this.requestUpdate();
  }

  _restart() {
    this._index = 0;
    this._finished = false;
    this._runCompleted = new Map();
    this._skipped = new Set();
    this.requestUpdate();
  }

  render() {
    if (!this.hass || !this.config) return html``;
    const child = this._child();
    if (!child) {
      return html`<ha-card><div class="pad error">${this._t("routine.no_child")}</div></ha-card>`;
    }

    const attrs = this._attrs();
    const pointsIcon = attrs.points_icon || "mdi:star";
    const tasks = this._tasks();
    const title = this.config.title || this._t("routine.title", { name: child.name });

    if (!tasks.length) return this._renderEmpty(title);
    if (this._finished) return this._renderFinished(title, tasks, pointsIcon, child);

    // Guard against the list shrinking underneath us (a parent ticking a chore
    // off elsewhere) — clamp rather than render undefined.
    const index = Math.min(this._index, tasks.length - 1);
    const chore = tasks[index];
    const done = this._runCompleted.get(String(chore.id));
    const pct = Math.round((index / tasks.length) * 100);

    return html`
      <ha-card>
        <style>:host { --routine-accent: ${_safeColor(this.config.header_color, "#7c3aed")}; }</style>
        <div class="head">
          <span class="who">${title}</span>
        </div>

        <div class="progress">
          <div class="bar"><i style="width:${pct}%"></i></div>
          <div class="count">${this._t("routine.task_of", { current: index + 1, total: tasks.length })}</div>
        </div>

        <div class="dots">
          ${tasks.map((t, i) => html`
            <span class="dot ${this._runCompleted.has(String(t.id)) ? "done" : ""} ${i === index ? "now" : ""}"></span>
          `)}
        </div>

        <div class="body">
          <div class="icon"><ha-icon icon="${chore.icon || "mdi:checkbox-marked-circle-outline"}"></ha-icon></div>
          <div class="task">${chore.name}</div>
          ${chore.description ? html`<div class="desc">${chore.description}</div>` : ""}
          <div class="points">
            <ha-icon icon="${pointsIcon}"></ha-icon> +${this._pointsFor(chore)}
          </div>
          ${done?.pending ? html`<div class="pending">${this._t("routine.waiting_for_parent")}</div>` : ""}
          ${chore.require_photo ? html`<div class="note">${this._t("routine.photo_note")}</div>` : ""}
        </div>

        <div class="foot">
          ${done
            ? html`<button class="btn btn-done is-done" disabled>
                     ${done.pending ? this._t("routine.sent_for_checking") : this._t("routine.completed")}
                   </button>`
            : html`<button class="btn btn-done" ?disabled=${this._busy}
                           @click=${() => this._complete(chore)}>
                     ${this._t("routine.done")}
                   </button>`}
          <div class="btn-row">
            <button class="btn btn-back" ?disabled=${index === 0} @click=${this._back}>
              ${this._t("routine.back")}
            </button>
            <button class="btn btn-skip" @click=${this._skip}>
              ${done ? this._t("routine.next") : this._t("routine.skip")}
            </button>
          </div>
        </div>
      </ha-card>
    `;
  }

  _renderEmpty(title) {
    return html`
      <ha-card>
        <style>:host { --routine-accent: ${_safeColor(this.config.header_color, "#7c3aed")}; }</style>
        <div class="head"><span class="who">${title}</span></div>
        <div class="empty">
          <ha-icon icon="mdi:check-circle-outline"></ha-icon>
          <h2>${this._t("routine.empty_title")}</h2>
          <p>${this._t("routine.empty_body")}</p>
        </div>
      </ha-card>
    `;
  }

  _renderFinished(title, tasks, pointsIcon, child) {
    let earned = 0;
    let pending = 0;
    for (const entry of this._runCompleted.values()) {
      if (entry.pending) pending += entry.points; else earned += entry.points;
    }
    const skipped = this._skipped.size;

    return html`
      <ha-card>
        <style>:host { --routine-accent: ${_safeColor(this.config.header_color, "#7c3aed")}; }</style>
        <div class="head"><span class="who">${title}</span></div>
        <div class="progress">
          <div class="bar"><i class="full" style="width:100%"></i></div>
          <div class="count">${this._t("routine.all_done_count", { total: tasks.length })}</div>
        </div>
        <div class="finished">
          <div class="cheer">🎉</div>
          <h2>${this._t("routine.finished_title")}</h2>
          <p>${this._t("routine.finished_body", { name: child.name })}</p>
          ${earned > 0 ? html`
            <div class="earned"><ha-icon icon="${pointsIcon}"></ha-icon> ${this._t("routine.earned", { points: earned })}</div>
          ` : ""}
          ${pending > 0 ? html`
            <div class="earned pending-total">${this._t("routine.awaiting_points", { points: pending })}</div>
          ` : ""}
          ${skipped > 0 ? html`
            <p class="skipped">${this._t("routine.skipped_note", { count: skipped })}</p>
          ` : ""}
        </div>
        <div class="foot">
          <button class="btn btn-done" @click=${this._restart}>${this._t("routine.start_again")}</button>
        </div>
      </ha-card>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; --routine-accent: #7c3aed; }
      ha-card {
        overflow: hidden;
        display: flex;
        flex-direction: column;
        min-height: 460px;
      }
      .head {
        background: var(--routine-accent);
        color: #fff;
        padding: 16px 20px;
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .who { font-weight: 800; font-size: 17px; flex: 1; }

      .progress { padding: 14px 20px 0; }
      .bar {
        height: 8px;
        border-radius: 99px;
        background: var(--divider-color, #e5e7eb);
        overflow: hidden;
      }
      .bar > i {
        display: block;
        height: 100%;
        border-radius: 99px;
        background: var(--routine-accent);
        transition: width 0.25s ease;
      }
      .bar > i.full { background: var(--success-color, #16a34a); }
      .count {
        font-size: 12.5px;
        color: var(--secondary-text-color);
        margin-top: 7px;
        font-weight: 600;
      }

      .dots {
        display: flex;
        gap: 6px;
        justify-content: center;
        padding: 10px 20px 0;
        flex-wrap: wrap;
      }
      .dot {
        width: 9px; height: 9px;
        border-radius: 50%;
        background: var(--divider-color, #e5e7eb);
        transition: transform 0.2s ease;
      }
      .dot.done { background: var(--success-color, #16a34a); }
      .dot.now { background: var(--routine-accent); transform: scale(1.35); }

      .body {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        padding: 20px 26px 8px;
        gap: 14px;
      }
      .icon {
        width: 128px; height: 128px;
        border-radius: 34px;
        background: color-mix(in srgb, var(--routine-accent), transparent 88%);
        display: grid;
        place-items: center;
        color: var(--routine-accent);
      }
      .icon ha-icon { --mdc-icon-size: 64px; }
      .task { font-size: 27px; font-weight: 800; line-height: 1.2; }
      .desc { font-size: 14.5px; color: var(--secondary-text-color); line-height: 1.45; }
      .points {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(245, 158, 11, 0.16);
        color: #92400e;
        padding: 5px 13px; border-radius: 99px;
        font-weight: 800; font-size: 14px;
      }
      .points ha-icon { --mdc-icon-size: 17px; }
      .pending {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(249, 115, 22, 0.12);
        color: #9a3412;
        border: 1px solid rgba(249, 115, 22, 0.35);
        padding: 5px 12px; border-radius: 99px;
        font-weight: 700; font-size: 12.5px;
      }
      .note { font-size: 12.5px; color: var(--secondary-text-color); }

      .foot { padding: 14px 20px 20px; display: flex; flex-direction: column; gap: 10px; }
      .btn {
        border: 0; border-radius: 16px;
        font-family: inherit; font-weight: 800;
        width: 100%; cursor: pointer;
      }
      .btn:disabled { cursor: default; }
      .btn-done {
        background: var(--success-color, #16a34a);
        color: #fff; padding: 19px; font-size: 19px;
      }
      .btn-done.is-done { background: var(--disabled-text-color, #9ca3af); }
      .btn-row { display: flex; gap: 10px; }
      .btn-skip {
        background: var(--divider-color, #e5e7eb);
        color: var(--primary-text-color);
        padding: 12px; font-size: 14px; flex: 1;
      }
      .btn-back {
        background: transparent;
        color: var(--secondary-text-color);
        border: 1px solid var(--divider-color, #e5e7eb);
        padding: 12px; font-size: 14px; flex: 0 0 96px;
      }
      .btn-back:disabled { opacity: 0.4; }

      .finished { text-align: center; padding: 34px 26px; flex: 1; }
      .finished .cheer { font-size: 66px; line-height: 1; }
      .finished h2 { font-size: 25px; margin: 12px 0 6px; }
      .finished p { color: var(--secondary-text-color); font-size: 15px; margin: 0 0 6px; }
      .finished .skipped { font-size: 13px; margin-top: 12px; }
      .earned {
        display: inline-flex; gap: 6px; align-items: center; margin-top: 10px;
        background: rgba(22, 163, 74, 0.14); color: #166534;
        padding: 9px 18px; border-radius: 99px;
        font-weight: 800; font-size: 16px;
      }
      .earned.pending-total {
        background: rgba(249, 115, 22, 0.12); color: #9a3412;
        font-size: 14px;
      }

      .empty { text-align: center; padding: 64px 26px; color: var(--secondary-text-color); flex: 1; }
      .empty ha-icon { --mdc-icon-size: 60px; opacity: 0.5; }
      .empty h2 { font-size: 20px; color: var(--primary-text-color); margin: 14px 0 6px; }
      .empty p { font-size: 14.5px; margin: 0; }

      .pad { padding: 24px; }
      .error { color: var(--error-color, #c62828); }

      @media (max-width: 420px) {
        .icon { width: 104px; height: 104px; border-radius: 28px; }
        .icon ha-icon { --mdc-icon-size: 52px; }
        .task { font-size: 23px; }
      }
    `;
  }
}

class TaskMateRoutineCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, _config: { type: Object } };
  }

  setConfig(config) { this._config = { ...config }; }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  render() {
    if (!this._config) return html``;
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this._config.entity)) || {};
    const children = attrs.children || [];
    return html`
      <div class="form">
        <ha-textfield
          label="Entity"
          .value=${this._config.entity || "sensor.taskmate_overview"}
          @input=${e => this._set("entity", e.target.value)}
        ></ha-textfield>

        <ha-select
          label="Child"
          .value=${this._config.child_id || ""}
          @selected=${e => this._set("child_id", e.target.value)}
          @closed=${e => e.stopPropagation()}
        >
          ${children.map(c => html`<mwc-list-item .value=${c.id}>${c.name}</mwc-list-item>`)}
        </ha-select>

        <ha-select
          label="Time of day"
          .value=${this._config.time_category || "all"}
          @selected=${e => this._set("time_category", e.target.value)}
          @closed=${e => e.stopPropagation()}
        >
          ${TIME_CATEGORIES.map(t => html`<mwc-list-item .value=${t}>${t}</mwc-list-item>`)}
        </ha-select>

        <ha-textfield
          label="Title (optional)"
          .value=${this._config.title || ""}
          @input=${e => this._set("title", e.target.value)}
        ></ha-textfield>
      </div>
    `;
  }

  _set(key, value) {
    const newConfig = { ...this._config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this._config = newConfig;
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  static get styles() {
    return css`
      .form { display: flex; flex-direction: column; gap: 14px; padding: 8px 0; }
    `;
  }
}

customElements.define("taskmate-routine-card", TaskMateRoutineCard);
customElements.define("taskmate-routine-card-editor", TaskMateRoutineCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-routine-card",
  name: "TaskMate Routine",
  description: "Guided one-task-at-a-time flow for morning and bedtime routines",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-routine-card", "overview"),
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-routine-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE ROUTINE CARD %c v" + _tmVersion + " ",
  "background:#7c3aed;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
