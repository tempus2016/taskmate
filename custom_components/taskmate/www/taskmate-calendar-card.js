/**
 * TaskMate Calendar Card
 * One-day view of the chores assigned to each child. Each child gets a
 * section with the chores scheduled for the selected day, colour-coded
 * by completion state. Prev/Next/Today buttons step through days.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const DAY_NAMES = [
  "monday", "tuesday", "wednesday", "thursday",
  "friday", "saturday", "sunday",
];

const WINDOW_DAYS = {
  every_2_days: 2,
  weekly: 7,
  every_2_weeks: 14,
  monthly: 30,
  every_3_months: 90,
  every_6_months: 180,
};

function ymd(date, tz) {
  return date.toLocaleDateString("en-CA", { timeZone: tz });
}

function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function diffDays(a, b) {
  const ms = 24 * 60 * 60 * 1000;
  return Math.round((a.getTime() - b.getTime()) / ms);
}

class TaskMateCalendarCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _dayOffset: { type: Number, state: true },
    };
  }

  constructor() {
    super();
    this._dayOffset = 0;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        --cal-green: #2ecc71;
        --cal-amber: #f39c12;
        --cal-grey: #bdc3c7;
        --cal-blue: #3498db;
      }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #3498db);
        color: white;
      }

      .header-content { display: flex; align-items: center; gap: 10px; }
      .header-icon { --mdc-icon-size: 28px; opacity: 0.9; }
      .header-title { font-size: 1.2rem; font-weight: 600; }

      .day-nav {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .day-nav button {
        background: rgba(255,255,255,0.2);
        border: none;
        color: white;
        border-radius: 8px;
        padding: 4px 8px;
        cursor: pointer;
        font-size: 0.8rem;
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      .day-nav button:hover { background: rgba(255,255,255,0.3); }
      .day-nav ha-icon { --mdc-icon-size: 18px; }
      .day-label {
        background: rgba(255,255,255,0.2);
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
        white-space: nowrap;
      }

      .card-content {
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      .child-block {
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 12px;
        padding: 10px 12px;
      }

      .child-head {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
      }

      .child-avatar {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: linear-gradient(135deg, #9b59b6, #a569bd);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }
      .child-avatar ha-icon { --mdc-icon-size: 20px; color: white; }

      .child-name {
        font-weight: 700;
        font-size: 0.95rem;
        color: var(--primary-text-color);
        flex: 1;
      }

      .child-summary {
        font-size: 0.75rem;
        color: var(--secondary-text-color);
        font-weight: 500;
      }

      .chore-list {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .chore-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        background: var(--card-background-color, white);
        border-radius: 8px;
        border-left: 4px solid var(--cal-grey);
      }
      .chore-row.approved { border-left-color: var(--cal-green); }
      .chore-row.pending  { border-left-color: var(--cal-amber); }
      .chore-row.rotating { opacity: 0.6; font-style: italic; }

      .chore-icon { --mdc-icon-size: 18px; color: var(--secondary-text-color); }
      .chore-icon.approved { color: var(--cal-green); }
      .chore-icon.pending  { color: var(--cal-amber); }

      .chore-name {
        flex: 1;
        font-size: 0.88rem;
        color: var(--primary-text-color);
      }

      .chore-points {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.78rem;
        color: var(--secondary-text-color);
        font-weight: 600;
      }
      .chore-points ha-icon { --mdc-icon-size: 14px; color: #f1c40f; }

      .no-chores {
        padding: 8px 10px;
        font-size: 0.82rem;
        color: var(--secondary-text-color);
        font-style: italic;
      }

      .legend {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        padding: 4px 4px 0;
        font-size: 0.72rem;
        color: var(--secondary-text-color);
      }
      .legend-item { display: flex; align-items: center; gap: 4px; }
      .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
      .dot.approved { background: var(--cal-green); }
      .dot.pending  { background: var(--cal-amber); }
      .dot.due      { background: var(--cal-grey); }

      .error-state, .empty-state {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 40px 20px;
        color: var(--secondary-text-color); text-align: center;
      }
      .error-state { color: var(--error-color, #f44336); }
      .error-state ha-icon, .empty-state ha-icon {
        --mdc-icon-size: 48px; margin-bottom: 12px; opacity: 0.5;
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error(this._t("calendar.error.entity_required"));
    this.config = {
      title: null,
      child_id: null,
      header_color: "#3498db",
      ...config,
    };
  }

  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("taskmate-calendar-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Task Calendar" };
  }

  _shiftDay(delta) { this._dayOffset = (this._dayOffset || 0) + delta; }
  _resetDay() { this._dayOffset = 0; }

  _getSelectedDay(tz) {
    const today = new Date();
    const selected = addDays(today, this._dayOffset || 0);
    const dow = selected.getDay(); // 0 = Sunday
    const dayNameIdx = dow === 0 ? 6 : dow - 1;
    return {
      key: ymd(selected, tz),
      dow: DAY_NAMES[dayNameIdx],
      date: selected,
      todayKey: ymd(today, tz),
    };
  }

  _isChoreScheduledOn(chore, dayDow, dayDate, todayKey, tz) {
    if (chore.enabled === false) return false;

    const scheduleMode = chore.schedule_mode || "specific_days";
    const createdDate = chore.created_date || "";

    if (scheduleMode === "one_shot") {
      if (!createdDate) return false;
      return createdDate === ymd(dayDate, tz);
    }

    if (createdDate) {
      try {
        const created = new Date(createdDate + "T00:00:00");
        if (dayDate < new Date(created.toDateString())) return false;
      } catch (e) { /* ignore */ }
    }

    if (scheduleMode === "specific_days") {
      const dueDays = Array.isArray(chore.due_days) ? chore.due_days : [];
      if (dueDays.length === 0) return true;
      return dueDays.includes(dayDow);
    }

    if (scheduleMode === "recurring") {
      const recurrence = chore.recurrence || "weekly";
      const recurrenceDay = (chore.recurrence_day || "").toLowerCase();
      const recurrenceStart = chore.recurrence_start || "";

      if (recurrenceDay && (recurrence === "weekly" || recurrence === "every_2_weeks")) {
        if (recurrenceDay !== dayDow) return false;
        if (recurrence === "every_2_weeks" && recurrenceStart) {
          try {
            const anchor = new Date(recurrenceStart + "T00:00:00");
            const diff = diffDays(dayDate, anchor);
            if (diff < 0) return false;
            if (Math.floor(diff / 7) % 2 !== 0) return false;
          } catch (e) { /* ignore */ }
        }
        return true;
      }

      if (recurrence === "every_2_days" && recurrenceStart) {
        try {
          const anchor = new Date(recurrenceStart + "T00:00:00");
          const diff = diffDays(dayDate, anchor);
          if (diff < 0) return false;
          return diff % 2 === 0;
        } catch (e) { return false; }
      }

      if (recurrence === "monthly" && recurrenceStart) {
        try {
          const anchor = new Date(recurrenceStart + "T00:00:00");
          if (dayDate < anchor) return false;
          return dayDate.getDate() === anchor.getDate();
        } catch (e) { return false; }
      }

      const windowDays = WINDOW_DAYS[recurrence] || 7;
      if (windowDays === 7 || windowDays === 14) {
        const todayDow = new Date(todayKey + "T00:00:00").getDay();
        const todayIdx = todayDow === 0 ? 6 : todayDow - 1;
        return dayDow === DAY_NAMES[todayIdx];
      }
      return false;
    }

    return false;
  }

  _isAssignedTo(chore, childId) {
    const assignedTo = Array.isArray(chore.assigned_to) ? chore.assigned_to : [];
    if (assignedTo.length === 0) return true;
    return assignedTo.includes(childId);
  }

  _rotationRenderMode(chore, childId, dayKey, todayKey) {
    const mode = chore.assignment_mode || "everyone";
    if (mode === "everyone") return "active";
    const current = chore.assignment_current_child_id || "";
    if (dayKey === todayKey) {
      return current === childId ? "active" : "hidden";
    }
    return "rotating";
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`
        <ha-card>
          <div class="error-state">
            <ha-icon icon="mdi:alert-circle"></ha-icon>
            <div>${this._t("common.entity_not_found", { entity: this.config.entity })}</div>
          </div>
        </ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`
        <ha-card>
          <div class="error-state">
            <ha-icon icon="mdi:alert-circle"></ha-icon>
            <div>${this._t("common.unavailable")}</div>
          </div>
        </ha-card>`;
    }

    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    let children = entity.attributes.children || [];
    const chores = entity.attributes.chores || [];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";

    if (this.config.child_id) {
      children = children.filter((c) => c.id === this.config.child_id);
    }

    if (children.length === 0) {
      return html`
        <ha-card>
          <div class="empty-state">
            <ha-icon icon="mdi:account-off"></ha-icon>
            <div>${this._t("common.no_children")}</div>
          </div>
        </ha-card>`;
    }

    const day = this._getSelectedDay(tz);

    const rawCompletions = entity.attributes.recent_completions
      || entity.attributes.todays_completions
      || [];
    const seen = new Set();
    const dayCompletions = [];
    rawCompletions.forEach((c) => {
      const id = c.completion_id || `${c.chore_id}:${c.child_id}:${c.completed_at}`;
      if (seen.has(id)) return;
      seen.add(id);
      if (!c.completed_at) return;
      if (ymd(new Date(c.completed_at), tz) !== day.key) return;
      dayCompletions.push(c);
    });

    const dayLabel = day.date.toLocaleDateString(undefined, {
      weekday: "long", month: "short", day: "numeric",
    });
    const isToday = day.key === day.todayKey;

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || "#3498db"}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:calendar-account"></ha-icon>
            <span class="header-title">${this.config.title || this._t("calendar.default_title")}</span>
          </div>
          <div class="day-nav">
            <button @click=${() => this._shiftDay(-1)} title=${this._t("calendar.prev_day")}>
              <ha-icon icon="mdi:chevron-left"></ha-icon>
            </button>
            <span class="day-label">${isToday ? this._t("common.today") : dayLabel}</span>
            <button @click=${() => this._shiftDay(1)} title=${this._t("calendar.next_day")}>
              <ha-icon icon="mdi:chevron-right"></ha-icon>
            </button>
            ${!isToday ? html`
              <button @click=${() => this._resetDay()} title=${this._t("common.today")}>
                <ha-icon icon="mdi:calendar-today"></ha-icon>
              </button>
            ` : ""}
          </div>
        </div>

        <div class="card-content">
          ${children.map((child) => this._renderChildBlock(child, day, chores, dayCompletions, pointsIcon, tz))}

          <div class="legend">
            <span class="legend-item"><span class="dot approved"></span>${this._t("common.approved")}</span>
            <span class="legend-item"><span class="dot pending"></span>${this._t("common.pending")}</span>
            <span class="legend-item"><span class="dot due"></span>${this._t("calendar.legend_due")}</span>
          </div>
        </div>
      </ha-card>
    `;
  }

  _renderChildBlock(child, day, chores, dayCompletions, pointsIcon, tz) {
    const rows = [];
    let dueCount = 0;
    let doneCount = 0;

    chores.forEach((chore) => {
      if (!this._isAssignedTo(chore, child.id)) return;

      const disabledFor = Array.isArray(chore.disabled_for) ? chore.disabled_for : [];
      if (disabledFor.includes(child.id)) return;

      if (!this._isChoreScheduledOn(chore, day.dow, day.date, day.todayKey, tz)) return;

      const rotation = this._rotationRenderMode(chore, child.id, day.key, day.todayKey);
      if (rotation === "hidden") return;

      const comp = dayCompletions.find(
        (c) => c.chore_id === chore.id && c.child_id === child.id,
      );
      let state = "due";
      let stateIcon = "mdi:circle-outline";
      if (comp) {
        if (comp.approved) { state = "approved"; stateIcon = "mdi:check-circle"; doneCount++; }
        else { state = "pending"; stateIcon = "mdi:clock-outline"; }
      }
      dueCount++;

      const rotatingClass = rotation === "rotating" ? " rotating" : "";
      const title = `${chore.name}${rotation === "rotating" ? ` · ${this._t("calendar.rotating")}` : ""}`;

      rows.push(html`
        <div class="chore-row ${state}${rotatingClass}" title=${title}>
          <ha-icon class="chore-icon ${state}" icon="${stateIcon}"></ha-icon>
          <span class="chore-name">${chore.name}</span>
          <span class="chore-points">
            <ha-icon icon="${pointsIcon}"></ha-icon>${chore.points}
          </span>
        </div>
      `);
    });

    const summary = dueCount === 0
      ? this._t("calendar.no_chores_today")
      : this._t("calendar.child_summary", { done: doneCount, total: dueCount });

    return html`
      <div class="child-block">
        <div class="child-head">
          <div class="child-avatar">
            <ha-icon icon="${child.avatar || "mdi:account-circle"}"></ha-icon>
          </div>
          <span class="child-name">${child.name}</span>
          <span class="child-summary">${summary}</span>
        </div>
        <div class="chore-list">
          ${rows.length > 0 ? rows : html`<div class="no-chores">${this._t("calendar.no_chores_today")}</div>`}
        </div>
      </div>
    `;
  }
}

// Card Editor
class TaskMateCalendarCardEditor extends LitElement {
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
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t("common.editor.overview_entity"),
      title: this._t("calendar.editor.title"),
      child_id: this._t("common.editor.filter_by_child"),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t("common.editor.overview_entity_helper"),
      child_id: this._t("calendar.editor.child_helper"),
    };
    return helpers[entry.name] ?? "";
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "",
      title: this.config.title || "",
      child_id: this.config.child_id || "__all__",
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
      ${this._renderColourPicker("header_color", "#3498db")}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, "#27ae60", "#e67e22", "#9b59b6", "#f1c40f", "#e74c3c", "#34495e"];
    const isActive = (c) => c.toLowerCase() === current.toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${this._t("common.editor.header_colour")}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current}
              @input=${(e) => this._updateConfig(key, e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current}"></span>
          </label>
          <span class="colour-hex">${current}</span>
          <div class="colour-presets">
            ${presets.map((p) => html`
              <button class="preset-swatch ${isActive(p) ? "active" : ""}"
                style="background:${p}"
                title=${p}
                @click=${(e) => { e.preventDefault(); this._updateConfig(key, p); }}
              ></button>
            `)}
          </div>
          <button class="colour-reset"
            @click=${(e) => { e.preventDefault(); this._updateConfig(key, defaultValue); }}
          >${this._t("common.reset")}</button>
        </div>
        <div class="colour-helper">${this._t("common.editor.header_colour_helper")}</div>
      </div>
    `;
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (
        value === "" || value === null || value === undefined
        || (key === "child_id" && value === "__all__")
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

customElements.define("taskmate-calendar-card", TaskMateCalendarCard);
customElements.define("taskmate-calendar-card-editor", TaskMateCalendarCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-calendar-card",
  name: "TaskMate Calendar",
  description: "One-day view of chores assigned to each child",
  preview: true,
});

const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-calendar-card.js"]'))
    .map((s) => s.src.split("?")[1]).find(Boolean) || "",
).get("v") || "?";
console.info(
  "%c TASKMATE CALENDAR CARD %c v" + _tmVersion + " ",
  "background:#3498db;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;",
);
