/**
 * TaskMate Calendar Card
 * Week-at-a-glance grid showing the chores assigned to each child per day.
 * Rows = children, columns = Mon–Sun. Each cell lists the chores scheduled
 * for that child on that day and colour-codes them by completion state.
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

// 0 = Monday to match chore day keys
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
      _weekOffset: { type: Number, state: true },
    };
  }

  constructor() {
    super();
    this._weekOffset = 0;
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
      .week-nav { display: flex; align-items: center; gap: 4px; }
      .week-nav button {
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
      .week-nav button:hover { background: rgba(255,255,255,0.3); }
      .week-nav ha-icon { --mdc-icon-size: 18px; }
      .week-label {
        background: rgba(255,255,255,0.2);
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 500;
      }

      .card-content { padding: 12px; }

      .grid {
        display: grid;
        grid-template-columns: 110px repeat(7, minmax(0, 1fr));
        gap: 4px;
        font-size: 0.78rem;
      }

      .day-head, .child-head {
        font-size: 0.7rem;
        font-weight: 700;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.4px;
        text-align: center;
        padding: 6px 0;
      }

      .day-head.today {
        color: var(--cal-blue);
        background: rgba(52,152,219,0.1);
        border-radius: 6px;
      }

      .child-head { text-align: left; padding-left: 4px; }

      .child-cell {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 4px;
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 8px;
        min-height: 38px;
      }

      .child-avatar {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: linear-gradient(135deg, #9b59b6, #a569bd);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }
      .child-avatar ha-icon { --mdc-icon-size: 16px; color: white; }
      .child-name {
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .day-cell {
        min-height: 38px;
        border-radius: 8px;
        padding: 4px;
        display: flex;
        flex-direction: column;
        gap: 2px;
        background: var(--secondary-background-color, #f5f5f5);
      }

      .day-cell.today { background: rgba(52,152,219,0.08); }
      .day-cell.empty { opacity: 0.4; }

      .chore-chip {
        display: flex;
        align-items: center;
        gap: 4px;
        padding: 2px 4px;
        border-radius: 4px;
        font-size: 0.7rem;
        line-height: 1.1;
        background: var(--card-background-color, white);
        border: 1px solid var(--divider-color, #e0e0e0);
      }
      .chore-chip .chip-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--primary-text-color);
      }

      .chore-chip.approved { border-left: 3px solid var(--cal-green); }
      .chore-chip.pending  { border-left: 3px solid var(--cal-amber); }
      .chore-chip.due      { border-left: 3px solid var(--cal-grey); }
      .chore-chip.rotating { opacity: 0.55; font-style: italic; }

      .dot {
        width: 6px; height: 6px; border-radius: 50%;
        flex-shrink: 0;
      }
      .dot.approved { background: var(--cal-green); }
      .dot.pending  { background: var(--cal-amber); }
      .dot.due      { background: var(--cal-grey); }

      .legend {
        display: flex;
        gap: 12px;
        flex-wrap: wrap;
        padding: 10px 4px 2px;
        font-size: 0.7rem;
        color: var(--secondary-text-color);
      }
      .legend-item { display: flex; align-items: center; gap: 4px; }

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

  getCardSize() { return 5; }
  static getConfigElement() { return document.createElement("taskmate-calendar-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Task Calendar" };
  }

  _shiftWeek(delta) { this._weekOffset = (this._weekOffset || 0) + delta; }
  _resetWeek() { this._weekOffset = 0; }

  _getWeekDays(tz) {
    const today = new Date();
    const todayDow = today.getDay(); // 0 = Sunday
    const mondayOffset = todayDow === 0 ? -6 : 1 - todayDow;
    const monday = addDays(today, mondayOffset + (this._weekOffset || 0) * 7);

    const shortNames = [
      this._t("calendar.day_mon"), this._t("calendar.day_tue"),
      this._t("calendar.day_wed"), this._t("calendar.day_thu"),
      this._t("calendar.day_fri"), this._t("calendar.day_sat"),
      this._t("calendar.day_sun"),
    ];
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = addDays(monday, i);
      days.push({
        key: ymd(d, tz),
        short: shortNames[i],
        dow: DAY_NAMES[i],
        date: d,
      });
    }
    return days;
  }

  // Port of coordinator.is_chore_available_for_child() restricted to the
  // schedule-rule parts that tell us which *days* a chore falls on.
  // We deliberately do NOT check visibility_entity (that's a live-state
  // thing that doesn't make sense for past/future days) nor
  // last_completed_at for recurring chores (the calendar shows the
  // recurrence pattern, the completion dots overlay actual history).
  _isChoreScheduledOn(chore, dayDow, dayDate, todayKey, tz) {
    if (chore.enabled === false) return false;

    const scheduleMode = chore.schedule_mode || "specific_days";
    const createdDate = chore.created_date || "";

    // One-shot: only on the created_date
    if (scheduleMode === "one_shot") {
      if (!createdDate) return false;
      return createdDate === ymd(dayDate, tz);
    }

    // If we have a created_date for a recurring/specific chore,
    // don't schedule it before that date.
    if (createdDate) {
      try {
        const created = new Date(createdDate + "T00:00:00");
        if (dayDate < new Date(created.toDateString())) return false;
      } catch (e) { /* ignore */ }
    }

    if (scheduleMode === "specific_days") {
      const dueDays = Array.isArray(chore.due_days) ? chore.due_days : [];
      if (dueDays.length === 0) return true; // no restriction
      return dueDays.includes(dayDow);
    }

    if (scheduleMode === "recurring") {
      const recurrence = chore.recurrence || "weekly";
      const recurrenceDay = (chore.recurrence_day || "").toLowerCase();
      const recurrenceStart = chore.recurrence_start || "";

      // weekly / every_2_weeks anchored to a specific weekday
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

      // Fallback: show on the same weekday as today for weekly-like
      const windowDays = WINDOW_DAYS[recurrence] || 7;
      if (windowDays === 7 || windowDays === 14) {
        return dayDow === DAY_NAMES[new Date(todayKey + "T00:00:00").getDay() === 0 ? 6 : new Date(todayKey + "T00:00:00").getDay() - 1];
      }
      return false;
    }

    return false;
  }

  _isAssignedTo(chore, childId) {
    const assignedTo = Array.isArray(chore.assigned_to) ? chore.assigned_to : [];
    if (assignedTo.length === 0) return true; // unassigned = everyone
    return assignedTo.includes(childId);
  }

  // Rotating chores (alternating/random/balanced) only show as "active"
  // for the currently rotated child on today — for other days we render
  // them dimmed/italic for every assigned child so you know it rotates.
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

    // Dedup + collect completions for the visible week
    const weekDays = this._getWeekDays(tz);
    const weekKeys = new Set(weekDays.map((d) => d.key));
    const todayKey = ymd(new Date(), tz);

    const rawCompletions = entity.attributes.recent_completions
      || entity.attributes.todays_completions
      || [];
    const seen = new Set();
    const completions = [];
    rawCompletions.forEach((c) => {
      const id = c.completion_id || `${c.chore_id}:${c.child_id}:${c.completed_at}`;
      if (seen.has(id)) return;
      seen.add(id);
      if (!c.completed_at) return;
      const key = ymd(new Date(c.completed_at), tz);
      if (!weekKeys.has(key)) return;
      completions.push({ ...c, _dayKey: key });
    });

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

    const weekLabel = `${weekDays[0].date.toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${weekDays[6].date.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`;

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || "#3498db"}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:calendar-account"></ha-icon>
            <span class="header-title">${this.config.title || this._t("calendar.default_title")}</span>
          </div>
          <div class="week-nav">
            <button @click=${() => this._shiftWeek(-1)} title=${this._t("calendar.prev_week")}>
              <ha-icon icon="mdi:chevron-left"></ha-icon>
            </button>
            <button @click=${() => this._resetWeek()} title=${this._t("calendar.this_week")}>
              ${this._t("calendar.this_week")}
            </button>
            <button @click=${() => this._shiftWeek(1)} title=${this._t("calendar.next_week")}>
              <ha-icon icon="mdi:chevron-right"></ha-icon>
            </button>
            <span class="week-label">${weekLabel}</span>
          </div>
        </div>

        <div class="card-content">
          <div class="grid">
            <div class="child-head"></div>
            ${weekDays.map((d) => html`
              <div class="day-head ${d.key === todayKey ? "today" : ""}">
                ${d.short}<br><span style="font-weight:500;opacity:0.75">${d.date.getDate()}</span>
              </div>
            `)}

            ${children.map((child) => html`
              <div class="child-cell">
                <div class="child-avatar">
                  <ha-icon icon="${child.avatar || "mdi:account-circle"}"></ha-icon>
                </div>
                <div class="child-name" title=${child.name}>${child.name}</div>
              </div>
              ${weekDays.map((day) => this._renderDayCell(child, day, chores, completions, todayKey, tz, pointsIcon))}
            `)}
          </div>

          <div class="legend">
            <span class="legend-item"><span class="dot approved"></span>${this._t("common.approved")}</span>
            <span class="legend-item"><span class="dot pending"></span>${this._t("common.pending")}</span>
            <span class="legend-item"><span class="dot due"></span>${this._t("calendar.legend_due")}</span>
          </div>
        </div>
      </ha-card>
    `;
  }

  _renderDayCell(child, day, chores, completions, todayKey, tz, pointsIcon) {
    const isToday = day.key === todayKey;
    const cellClass = `day-cell${isToday ? " today" : ""}`;

    const chips = [];
    chores.forEach((chore) => {
      if (!this._isAssignedTo(chore, child.id)) return;

      // Skip chores that are per-child disabled (one-shot already done)
      const disabledFor = Array.isArray(chore.disabled_for) ? chore.disabled_for : [];
      if (disabledFor.includes(child.id)) return;

      if (!this._isChoreScheduledOn(chore, day.dow, day.date, todayKey, tz)) return;

      const rotation = this._rotationRenderMode(chore, child.id, day.key, todayKey);
      if (rotation === "hidden") return;

      // Find completion state for this chore+child on this day
      const comp = completions.find(
        (c) => c.chore_id === chore.id
          && c.child_id === child.id
          && c._dayKey === day.key,
      );
      let state = "due";
      if (comp) state = comp.approved ? "approved" : "pending";

      const extra = rotation === "rotating" ? " rotating" : "";
      const title = `${chore.name} · ${chore.points} pts${rotation === "rotating" ? ` · ${this._t("calendar.rotating")}` : ""}`;
      chips.push(html`
        <div class="chore-chip ${state}${extra}" title=${title}>
          <span class="dot ${state}"></span>
          <span class="chip-name">${chore.name}</span>
        </div>
      `);
    });

    const emptyClass = chips.length === 0 ? " empty" : "";
    return html`
      <div class="${cellClass}${emptyClass}">
        ${chips.length > 0 ? chips : html`<span style="opacity:0.5;font-size:0.7rem;text-align:center">·</span>`}
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
  description: "Week view of chores assigned to each child",
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
