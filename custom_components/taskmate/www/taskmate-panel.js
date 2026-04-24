/**
 * TaskMate admin panel — sidebar entry at /taskmate-admin.
 *
 * All seven tabs (Children, Chores, Rewards, Penalties, Bonuses, Groups,
 * Settings) are wired to WebSocket commands. The classic options-flow menu
 * remains in place but is now redundant for everyday admin work.
 *
 * Vanilla HTMLElement — no LitElement dependency. The panel hits a single
 * read command (taskmate/get_state) on mount and after every mutation;
 * mutations call dedicated WS commands which in turn call coordinator
 * methods so existing business logic (refunds, cleanup, recompute) runs.
 */

const PANEL_VERSION = "3.5.0-alpha.5";

const TABS = [
  { id: "children",  label: "Children" },
  { id: "chores",    label: "Chores" },
  { id: "rewards",   label: "Rewards" },
  { id: "penalties", label: "Penalties" },
  { id: "bonuses",   label: "Bonuses" },
  { id: "groups",    label: "Groups" },
  { id: "settings",  label: "⚙",  title: "Settings" },
];

const TIME_CATEGORIES = [
  { v: "anytime",   l: "Anytime" },
  { v: "morning",   l: "Morning" },
  { v: "afternoon", l: "Afternoon" },
  { v: "evening",   l: "Evening" },
  { v: "night",     l: "Night" },
];

const SCHEDULE_MODES = [
  { v: "specific_days", l: "Specific days of the week" },
  { v: "recurring",     l: "Recurring (every N days/weeks/months)" },
  { v: "one_shot",      l: "One-time task" },
];

const RECURRENCES = [
  { v: "every_2_days",   l: "Every 2 days" },
  { v: "weekly",         l: "Weekly" },
  { v: "every_2_weeks",  l: "Every 2 weeks" },
  { v: "monthly",        l: "Monthly" },
  { v: "every_3_months", l: "Every 3 months" },
  { v: "every_6_months", l: "Every 6 months" },
];

const FIRST_OCCURRENCE = [
  { v: "available_immediately",     l: "Available immediately" },
  { v: "wait_for_first_occurrence", l: "Wait for first scheduled occurrence" },
];

const ASSIGNMENT_MODES = [
  { v: "everyone",    l: "Everyone — every assigned child sees the chore" },
  { v: "alternating", l: "Alternating — rotate through children, one per day" },
  { v: "random",      l: "Random — pick one assigned child each day" },
  { v: "balanced",    l: "Balanced — split today's chores evenly across children" },
];

const VISIBILITY_OPS = [
  { v: "equals",     l: "Equals" },
  { v: "not_equals", l: "Not equal" },
  { v: "gte",        l: "Greater than or equal (≥)" },
  { v: "lte",        l: "Less than or equal (≤)" },
  { v: "gt",         l: "Greater than (>)" },
  { v: "lt",         l: "Less than (<)" },
];

const COMPLETION_SOUNDS = [
  "none", "coin", "levelup", "fanfare", "chime", "powerup", "undo",
  "fart1", "fart2", "fart3", "fart4", "fart5", "fart6", "fart7",
  "fart8", "fart9", "fart10", "fart_random",
];

const DAYS = [
  { v: "monday",    l: "Mon" },
  { v: "tuesday",   l: "Tue" },
  { v: "wednesday", l: "Wed" },
  { v: "thursday",  l: "Thu" },
  { v: "friday",    l: "Fri" },
  { v: "saturday",  l: "Sat" },
  { v: "sunday",    l: "Sun" },
];

const STREAK_MODES = [
  { v: "reset", l: "Reset — streak goes to 0 on missed day" },
  { v: "pause", l: "Pause — streak preserved until next completion" },
];

const TASK_GROUP_POLICIES = [
  { v: "sticky", l: "Sticky — same child for all chores in the group today" },
  { v: "spread", l: "Spread — different children across the group today" },
];


class TaskMatePanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._state = null;
    this._error = null;
    this._loading = false;
    this._activeTab = "children";
    this._dialog = null;        // { kind, mode: "add"|"edit", data }
    this._rendered = false;
    this._onClick = this._onClick.bind(this);
    this._onInput = this._onInput.bind(this);
    this._onChange = this._onChange.bind(this);
    this._onKeyDown = this._onKeyDown.bind(this);
  }

  // ---- HA injects these ------------------------------------------------
  set hass(value) {
    const first = this._hass === null;
    this._hass = value;
    if (first) this._fetchState();
    if (!this._rendered) this._render();
  }
  get hass() { return this._hass; }
  set narrow(_v) {}
  set route(_v) {}
  set panel(_v) {}

  connectedCallback() {
    this.addEventListener("click", this._onClick);
    this.addEventListener("input", this._onInput);
    this.addEventListener("change", this._onChange);
    this.addEventListener("keydown", this._onKeyDown);
    if (!this._rendered) this._render();
  }
  disconnectedCallback() {
    this.removeEventListener("click", this._onClick);
    this.removeEventListener("input", this._onInput);
    this.removeEventListener("change", this._onChange);
    this.removeEventListener("keydown", this._onKeyDown);
  }

  // ---- state -----------------------------------------------------------
  async _fetchState() {
    if (!this._hass) return;
    this._loading = true;
    this._render();
    try {
      this._state = await this._hass.callWS({ type: "taskmate/get_state" });
      this._error = null;
    } catch (err) {
      this._error = (err && err.message) || String(err);
      this._state = null;
    } finally {
      this._loading = false;
      this._render();
    }
  }

  async _callWS(payload) {
    try {
      const res = await this._hass.callWS(payload);
      return { ok: true, res };
    } catch (err) {
      return { ok: false, err: (err && err.message) || String(err) };
    }
  }

  _showToast(kind, text) {
    const existing = this.querySelector(".tm-toast");
    if (existing) existing.remove();
    const node = document.createElement("div");
    node.className = `tm-toast tm-toast-${kind}`;
    node.textContent = text;
    this.appendChild(node);
    setTimeout(() => { if (node.isConnected) node.remove(); }, 3500);
  }

  // ---- event delegation ------------------------------------------------
  _onClick(e) {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const act = t.dataset.act;

    if (act === "tab")           { this._activeTab = t.dataset.tab; this._render(); return; }
    if (act === "close-dialog")  { this._dialog = null; this._render(); return; }
    if (act === "scrim") {
      if (e.target === this.querySelector(".tm-scrim")) { this._dialog = null; this._render(); }
      return;
    }
    if (act === "retry")         { this._fetchState(); return; }

    // -- Children --
    if (act === "add-child")     { this._openChildDialog(null); return; }
    if (act === "edit-child")    { this._openChildDialog(t.dataset.id); return; }
    if (act === "delete-child")  { this._confirmDelete("child", t.dataset.id); return; }
    if (act === "save-child")    { this._doSaveChild(); return; }

    // -- Chores --
    if (act === "add-chore")     { this._openChoreDialog(null); return; }
    if (act === "edit-chore")    { this._openChoreDialog(t.dataset.id); return; }
    if (act === "delete-chore")  { this._confirmDelete("chore", t.dataset.id); return; }
    if (act === "save-chore")    { this._doSaveChore(); return; }
    if (act === "toggle-day")    { this._toggleArrayField("due_days", t.dataset.day); return; }
    if (act === "toggle-assigned") { this._toggleArrayField("assigned_to", t.dataset.id); return; }
    if (act === "toggle-advanced") { const adv = this.querySelector(".tm-advanced"); if (adv) adv.toggleAttribute("open"); return; }

    // -- Rewards --
    if (act === "add-reward")    { this._openRewardDialog(null); return; }
    if (act === "edit-reward")   { this._openRewardDialog(t.dataset.id); return; }
    if (act === "delete-reward") { this._confirmDelete("reward", t.dataset.id); return; }
    if (act === "save-reward")   { this._doSaveReward(); return; }
    if (act === "toggle-reward-assigned") { this._toggleArrayField("assigned_to", t.dataset.id); return; }

    // -- Penalties --
    if (act === "add-penalty")    { this._openPenBonDialog("penalty", null); return; }
    if (act === "edit-penalty")   { this._openPenBonDialog("penalty", t.dataset.id); return; }
    if (act === "delete-penalty") { this._confirmDelete("penalty", t.dataset.id); return; }
    if (act === "save-penalty")   { this._doSavePenBon("penalty"); return; }
    if (act === "apply-penalty")  { this._openApplyDialog("penalty", t.dataset.id); return; }
    if (act === "do-apply-penalty") { this._doApplyPenBon("penalty", t.dataset.id, t.dataset.child); return; }

    // -- Bonuses --
    if (act === "add-bonus")    { this._openPenBonDialog("bonus", null); return; }
    if (act === "edit-bonus")   { this._openPenBonDialog("bonus", t.dataset.id); return; }
    if (act === "delete-bonus") { this._confirmDelete("bonus", t.dataset.id); return; }
    if (act === "save-bonus")   { this._doSavePenBon("bonus"); return; }
    if (act === "apply-bonus")  { this._openApplyDialog("bonus", t.dataset.id); return; }
    if (act === "do-apply-bonus") { this._doApplyPenBon("bonus", t.dataset.id, t.dataset.child); return; }

    if (act === "toggle-penbon-assigned") { this._toggleArrayField("assigned_to", t.dataset.id); return; }

    // -- Task groups --
    if (act === "add-group")    { this._openGroupDialog(null); return; }
    if (act === "edit-group")   { this._openGroupDialog(t.dataset.id); return; }
    if (act === "delete-group") { this._confirmDelete("group", t.dataset.id); return; }
    if (act === "save-group")   { this._doSaveGroup(); return; }
    if (act === "toggle-group-chore") { this._toggleArrayField("chore_ids", t.dataset.id); return; }

    // -- Settings --
    if (act === "save-settings") { this._doSaveSettings(); return; }
  }

  _onInput(e) {
    if (!this._dialog) return;
    const t = e.target;
    if (!t.dataset || !t.dataset.field) return;
    const value = (t.type === "number") ? (t.value === "" ? null : Number(t.value)) : t.value;
    this._dialog.data[t.dataset.field] = value;
  }

  _onChange(e) {
    if (!this._dialog) return;
    const t = e.target;
    if (!t.dataset || !t.dataset.field) return;
    let value;
    if (t.type === "checkbox") value = t.checked;
    else if (t.type === "number") value = (t.value === "" ? null : Number(t.value));
    else value = t.value;
    this._dialog.data[t.dataset.field] = value;
  }

  _onKeyDown(e) {
    if (e.key === "Escape" && this._dialog) { this._dialog = null; this._render(); }
  }

  _toggleArrayField(field, value) {
    if (!this._dialog || !this._dialog.data) return;
    const arr = Array.isArray(this._dialog.data[field]) ? [...this._dialog.data[field]] : [];
    const i = arr.indexOf(value);
    if (i >= 0) arr.splice(i, 1); else arr.push(value);
    this._dialog.data[field] = arr;
    this._render();
  }

  _confirmDelete(kind, id) {
    const labels = { child: "Child", chore: "Chore", reward: "Reward", penalty: "Penalty", bonus: "Bonus", group: "Group" };
    const collectionKey = { child: "children", chore: "chores", reward: "rewards", penalty: "penalties", bonus: "bonuses", group: "task_groups" }[kind];
    const item = (this._state[collectionKey] || []).find(x => x.id === id);
    if (!item) return;
    const extraWarn = kind === "child"
      ? "\n\nThis also removes all of their completion history, reward claims, points transactions, and pool allocations. Chores assigned to them will be updated."
      : kind === "reward"
      ? "\n\nAny points children have pooled for this reward will be refunded to their balance."
      : kind === "chore"
      ? "\n\nThis also removes the chore from any task groups it belonged to."
      : "";
    if (!confirm(`Delete ${labels[kind].toLowerCase()} "${item.name}"?${extraWarn}\n\nThis cannot be undone.`)) return;
    this._doRemove(kind, id);
  }

  async _doRemove(kind, id) {
    const wsType = {
      child:   "taskmate/remove_child",
      chore:   "taskmate/remove_chore",
      reward:  "taskmate/remove_reward",
      penalty: "taskmate/remove_penalty",
      bonus:   "taskmate/remove_bonus",
      group:   "taskmate/remove_task_group",
    }[kind];
    const idField = {
      child: "child_id", chore: "chore_id", reward: "reward_id",
      penalty: "penalty_id", bonus: "bonus_id", group: "group_id",
    }[kind];
    const { ok, err } = await this._callWS({ type: wsType, [idField]: id });
    if (!ok) { this._showToast("err", `Delete failed: ${err}`); return; }
    await this._fetchState();
    this._showToast("ok", "Deleted");
  }

  // ---- Children: dialog open / save ------------------------------------
  _openChildDialog(id) {
    if (id) {
      const c = (this._state.children || []).find(x => x.id === id);
      if (!c) return;
      this._dialog = { kind: "child", mode: "edit", data: {
        id: c.id, name: c.name || "", avatar: c.avatar || "mdi:account-circle",
        availability_entity: c.availability_entity || "",
      } };
    } else {
      this._dialog = { kind: "child", mode: "add", data: {
        name: "", avatar: "mdi:account-circle", availability_entity: "",
      } };
    }
    this._render();
  }

  async _doSaveChild() {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", "Name is required"); return; }
    const wasAdd = this._dialog.mode === "add";
    const payload = wasAdd
      ? { type: "taskmate/add_child", name: d.name.trim(), avatar: d.avatar || "mdi:account-circle", availability_entity: d.availability_entity || "" }
      : { type: "taskmate/update_child", child_id: d.id, name: d.name.trim(), avatar: d.avatar || "mdi:account-circle", availability_entity: d.availability_entity || "" };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._dialog = null;
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Child added" : "Child updated");
  }

  // ---- Chores: dialog open / save --------------------------------------
  _openChoreDialog(id) {
    const blank = {
      name: "", description: "", points: 10,
      assigned_to: [], requires_approval: true,
      time_category: "anytime", completion_sound: "coin", daily_limit: 1,
      schedule_mode: "specific_days",
      due_days: [], recurrence: "weekly", recurrence_day: "", recurrence_start: "",
      first_occurrence_mode: "available_immediately",
      assignment_mode: "everyone", assignment_rotation_anchor: "",
      require_availability: false,
      visibility_entity: "", visibility_state: "on", visibility_operator: "equals",
      enabled: true,
      publish_calendar_entities_csv: "",
    };
    if (id) {
      const c = (this._state.chores || []).find(x => x.id === id);
      if (!c) return;
      this._dialog = { kind: "chore", mode: "edit", data: {
        ...blank,
        ...c,
        assigned_to: [...(c.assigned_to || [])],
        due_days: [...(c.due_days || [])],
        publish_calendar_entities_csv: (c.publish_calendar_entities || []).join(", "),
      } };
    } else {
      this._dialog = { kind: "chore", mode: "add", data: blank };
    }
    this._render();
  }

  async _doSaveChore() {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", "Name is required"); return; }
    const wasAdd = this._dialog.mode === "add";
    const calCsv = (d.publish_calendar_entities_csv || "").split(",").map(s => s.trim()).filter(Boolean);
    const base = {
      name: d.name.trim(),
      description: d.description || "",
      points: Number(d.points) || 0,
      assigned_to: d.assigned_to || [],
      requires_approval: !!d.requires_approval,
      time_category: d.time_category || "anytime",
      completion_sound: d.completion_sound || "coin",
      daily_limit: Number(d.daily_limit) || 1,
      schedule_mode: d.schedule_mode || "specific_days",
      due_days: d.due_days || [],
      recurrence: d.recurrence || "weekly",
      recurrence_day: d.recurrence_day || "",
      recurrence_start: d.recurrence_start || "",
      first_occurrence_mode: d.first_occurrence_mode || "available_immediately",
      assignment_mode: d.assignment_mode || "everyone",
      assignment_rotation_anchor: d.assignment_rotation_anchor || "",
      require_availability: !!d.require_availability,
      visibility_entity: d.visibility_entity || "",
      visibility_state: d.visibility_state || "on",
      visibility_operator: d.visibility_operator || "equals",
      enabled: d.enabled !== false,
      publish_calendar_entities: calCsv,
    };
    const payload = wasAdd
      ? { type: "taskmate/add_chore", ...base }
      : { type: "taskmate/update_chore", chore_id: d.id, ...base };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._dialog = null;
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Chore added" : "Chore updated");
  }

  // ---- Rewards ---------------------------------------------------------
  _openRewardDialog(id) {
    const blank = { name: "", description: "", cost: 50, icon: "mdi:gift",
      assigned_to: [], is_jackpot: false, pool_enabled: false,
      quantity_str: "", expires_at: "" };
    if (id) {
      const r = (this._state.rewards || []).find(x => x.id === id);
      if (!r) return;
      this._dialog = { kind: "reward", mode: "edit", data: {
        ...blank, ...r,
        assigned_to: [...(r.assigned_to || [])],
        quantity_str: r.quantity == null ? "" : String(r.quantity),
        expires_at: r.expires_at || "",
      } };
    } else {
      this._dialog = { kind: "reward", mode: "add", data: blank };
    }
    this._render();
  }

  async _doSaveReward() {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", "Name is required"); return; }
    const wasAdd = this._dialog.mode === "add";
    const qty = (d.quantity_str === "" || d.quantity_str == null) ? null : Math.max(0, Number(d.quantity_str));
    const base = {
      name: d.name.trim(),
      cost: Number(d.cost) || 0,
      description: d.description || "",
      icon: d.icon || "mdi:gift",
      assigned_to: d.assigned_to || [],
      is_jackpot: !!d.is_jackpot,
      pool_enabled: !!d.pool_enabled,
      quantity: qty,
      expires_at: (d.expires_at || "").trim() || null,
    };
    const payload = wasAdd ? { type: "taskmate/add_reward", ...base } : { type: "taskmate/update_reward", reward_id: d.id, ...base };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._dialog = null;
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Reward added" : "Reward updated");
  }

  // ---- Penalties / Bonuses (shared shape) ------------------------------
  _openPenBonDialog(kind, id) {
    const blank = { name: "", description: "", points: 10,
      icon: kind === "penalty" ? "mdi:alert-circle-outline" : "mdi:star-circle-outline",
      assigned_to: [] };
    if (id) {
      const item = ((kind === "penalty" ? this._state.penalties : this._state.bonuses) || []).find(x => x.id === id);
      if (!item) return;
      this._dialog = { kind, mode: "edit", data: { ...blank, ...item, assigned_to: [...(item.assigned_to || [])] } };
    } else {
      this._dialog = { kind, mode: "add", data: blank };
    }
    this._render();
  }

  async _doSavePenBon(kind) {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", "Name is required"); return; }
    if (!d.points || d.points < 1) { this._showToast("err", "Points must be 1 or higher"); return; }
    const wasAdd = this._dialog.mode === "add";
    const wsBase = kind === "penalty" ? "penalty" : "bonus";
    const idField = `${wsBase}_id`;
    const wsType = wasAdd ? `taskmate/add_${wsBase}` : `taskmate/update_${wsBase}`;
    const base = {
      name: d.name.trim(),
      points: Number(d.points),
      description: d.description || "",
      icon: d.icon || (kind === "penalty" ? "mdi:alert-circle-outline" : "mdi:star-circle-outline"),
      assigned_to: d.assigned_to || [],
    };
    const payload = wasAdd ? { type: wsType, ...base } : { type: wsType, [idField]: d.id, ...base };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._dialog = null;
    await this._fetchState();
    this._showToast("ok", `${wasAdd ? "Added" : "Updated"} ${kind}`);
  }

  _openApplyDialog(kind, id) {
    const item = ((kind === "penalty" ? this._state.penalties : this._state.bonuses) || []).find(x => x.id === id);
    if (!item) return;
    this._dialog = { kind: `apply-${kind}`, mode: "apply", data: { id, item } };
    this._render();
  }

  async _doApplyPenBon(kind, id, child_id) {
    const wsType = kind === "penalty" ? "taskmate/apply_penalty" : "taskmate/apply_bonus";
    const idField = `${kind}_id`;
    const { ok, err } = await this._callWS({ type: wsType, [idField]: id, child_id });
    if (!ok) { this._showToast("err", `Apply failed: ${err}`); return; }
    this._dialog = null;
    await this._fetchState();
    this._showToast("ok", kind === "penalty" ? "Penalty applied" : "Bonus applied");
  }

  // ---- Task groups -----------------------------------------------------
  _openGroupDialog(id) {
    const blank = { name: "", policy: "sticky", chore_ids: [] };
    if (id) {
      const g = (this._state.task_groups || []).find(x => x.id === id);
      if (!g) return;
      this._dialog = { kind: "group", mode: "edit", data: { ...blank, ...g, chore_ids: [...(g.chore_ids || [])] } };
    } else {
      this._dialog = { kind: "group", mode: "add", data: blank };
    }
    this._render();
  }

  async _doSaveGroup() {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", "Name is required"); return; }
    const wasAdd = this._dialog.mode === "add";
    const base = { name: d.name.trim(), policy: d.policy || "sticky", chore_ids: d.chore_ids || [] };
    const payload = wasAdd ? { type: "taskmate/add_task_group", ...base } : { type: "taskmate/update_task_group", group_id: d.id, ...base };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._dialog = null;
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Group added" : "Group updated");
  }

  // ---- Settings --------------------------------------------------------
  async _doSaveSettings() {
    // Settings tab uses inline inputs; gather values directly from DOM.
    const root = this.querySelector(".tm-settings");
    if (!root) return;
    const fields = root.querySelectorAll("[data-setting]");
    const payload = { type: "taskmate/update_settings" };
    fields.forEach(el => {
      const name = el.dataset.setting;
      let v;
      if (el.type === "checkbox") v = el.checked;
      else if (el.type === "number") v = el.value === "" ? undefined : Number(el.value);
      else v = el.value;
      if (v !== undefined) payload[name] = v;
    });
    const { ok, err, res } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    await this._fetchState();
    this._showToast("ok", `Saved (${(res && res.updated || []).length} field${(res && res.updated || []).length === 1 ? "" : "s"})`);
  }

  // ---- rendering -------------------------------------------------------
  _render() {
    this._rendered = true;
    const existingToast = this.querySelector(".tm-toast");
    this.innerHTML = `
      ${this._styles()}
      <div class="tm-shell">
        ${this._appbar()}
        ${this._tabstrip()}
        <div class="tm-body">
          ${this._renderBody()}
        </div>
        ${this._dialog ? this._renderDialog() : ""}
      </div>
    `;
    if (existingToast) this.appendChild(existingToast);
  }

  _appbar() {
    return `
      <div class="tm-appbar">
        <h1>TaskMate</h1>
        <span class="tm-chip">v${PANEL_VERSION}</span>
      </div>
    `;
  }

  _tabstrip() {
    return `
      <nav class="tm-tabs">
        ${TABS.map(t => `
          <button class="tm-tab ${t.id === this._activeTab ? "tm-tab-active" : ""}" data-act="tab" data-tab="${t.id}" ${t.title ? `title="${t.title}"` : ""}>
            ${this._esc(t.label)}
          </button>
        `).join("")}
      </nav>
    `;
  }

  _renderBody() {
    if (this._loading && !this._state) return `<div class="tm-card">Loading…</div>`;
    if (this._error) return `
      <div class="tm-card tm-card-error">
        <h2>Failed to load state</h2>
        <p>${this._esc(this._error)}</p>
        <button class="tm-btn" data-act="retry">Retry</button>
      </div>`;
    if (!this._state) return `<div class="tm-card">No state yet.</div>`;

    switch (this._activeTab) {
      case "children":  return this._renderChildrenTab();
      case "chores":    return this._renderChoresTab();
      case "rewards":   return this._renderRewardsTab();
      case "penalties": return this._renderPenBonTab("penalty");
      case "bonuses":   return this._renderPenBonTab("bonus");
      case "groups":    return this._renderGroupsTab();
      case "settings":  return this._renderSettingsTab();
      default:          return `<div class="tm-card">Unknown tab</div>`;
    }
  }

  // -- Children tab ------------------------------------------------------
  _renderChildrenTab() {
    const children = this._state.children || [];
    const pointsName = this._state.settings.points_name || "points";
    return `
      <div class="tm-toolbar">
        <div class="tm-title-sub">Manage the children in your family. Points balance and history stay intact when you edit.</div>
        <button class="tm-btn" data-act="add-child">+ Add child</button>
      </div>
      ${children.length === 0 ? `
        <div class="tm-card tm-empty">
          <h2>No children yet</h2>
          <p>Add your first child to get started.</p>
          <button class="tm-btn" data-act="add-child">+ Add child</button>
        </div>
      ` : `
        <div class="tm-grid">
          ${children.map(c => this._renderChildCard(c, pointsName)).join("")}
          <button class="tm-add-tile" data-act="add-child"><span class="tm-add-plus">+</span>Add child</button>
        </div>
      `}
    `;
  }

  _renderChildCard(child, pointsName) {
    return `
      <article class="tm-card tm-child-card">
        <header class="tm-child-head">
          <div class="tm-avatar">${this._mdi(child.avatar)}</div>
          <div class="tm-child-name">
            <h3>${this._esc(child.name || "(unnamed)")}</h3>
            <div class="tm-sub">${child.availability_entity ? `Availability: <code>${this._esc(child.availability_entity)}</code>` : `<em>No availability sensor</em>`}</div>
          </div>
        </header>
        <div class="tm-stats">
          <div class="tm-stat"><strong>${this._fmtNum(child.points || 0)}</strong><span>${this._esc(pointsName)}</span></div>
          <div class="tm-stat"><strong>${this._fmtNum(child.total_points_earned || 0)}</strong><span>earned</span></div>
          <div class="tm-stat"><strong>${this._fmtNum(child.total_chores_completed || 0)}</strong><span>chores done</span></div>
        </div>
        <footer class="tm-card-foot">
          <button class="tm-btn tm-btn-ghost" data-act="edit-child" data-id="${this._esc(child.id)}">Edit</button>
          <button class="tm-btn tm-btn-danger" data-act="delete-child" data-id="${this._esc(child.id)}">Delete</button>
        </footer>
      </article>
    `;
  }

  // -- Chores tab --------------------------------------------------------
  _renderChoresTab() {
    const chores = this._state.chores || [];
    const childById = Object.fromEntries((this._state.children || []).map(c => [c.id, c]));
    return `
      <div class="tm-toolbar">
        <div class="tm-title-sub">${chores.length} chore${chores.length === 1 ? "" : "s"} configured.</div>
        <button class="tm-btn" data-act="add-chore">+ Add chore</button>
      </div>
      ${chores.length === 0 ? `
        <div class="tm-card tm-empty">
          <h2>No chores yet</h2>
          <p>Add a chore — it'll appear on the assigned children's cards.</p>
          <button class="tm-btn" data-act="add-chore">+ Add chore</button>
        </div>
      ` : `
        <div class="tm-table-wrap">
          <table class="tm-table">
            <thead><tr>
              <th>Name</th><th>Points</th><th>Assigned</th><th>Schedule</th><th>Approval</th><th></th>
            </tr></thead>
            <tbody>
              ${chores.map(c => this._renderChoreRow(c, childById)).join("")}
            </tbody>
          </table>
        </div>
      `}
    `;
  }

  _renderChoreRow(c, childById) {
    const assignedNames = (c.assigned_to || []).map(id => (childById[id] && childById[id].name) || "?").join(", ") || "(unassigned)";
    const schedLabel = c.schedule_mode === "recurring"
      ? this._labelOf(RECURRENCES, c.recurrence) + (c.recurrence_day && c.recurrence_day !== "any_day" ? ` · ${c.recurrence_day}` : "")
      : c.schedule_mode === "one_shot"
      ? "One-shot"
      : ((c.due_days || []).length === 0 ? "Daily" : (c.due_days || []).map(d => d.slice(0, 3)).join("/"));
    const modeBadge = c.assignment_mode && c.assignment_mode !== "everyone"
      ? `<span class="tm-pill tm-pill-${c.assignment_mode}">${c.assignment_mode}</span>` : "";
    return `
      <tr class="tm-row ${c.enabled === false ? "tm-row-disabled" : ""}">
        <td><strong>${this._esc(c.name)}</strong>${c.enabled === false ? ` <span class="tm-pill">disabled</span>` : ""}</td>
        <td><strong>${c.points}</strong></td>
        <td>${this._esc(assignedNames)} ${modeBadge}</td>
        <td>${this._esc(schedLabel)}</td>
        <td>${c.requires_approval ? "<span class='tm-yes'>Yes</span>" : "<span class='tm-no'>No</span>"}</td>
        <td class="tm-row-actions">
          <button class="tm-icon-btn" data-act="edit-chore" data-id="${this._esc(c.id)}" title="Edit">✏</button>
          <button class="tm-icon-btn" data-act="delete-chore" data-id="${this._esc(c.id)}" title="Delete">🗑</button>
        </td>
      </tr>
    `;
  }

  // -- Rewards tab -------------------------------------------------------
  _renderRewardsTab() {
    const rewards = this._state.rewards || [];
    const pointsName = this._state.settings.points_name || "points";
    return `
      <div class="tm-toolbar">
        <div class="tm-title-sub">${rewards.length} reward${rewards.length === 1 ? "" : "s"} configured.</div>
        <button class="tm-btn" data-act="add-reward">+ Add reward</button>
      </div>
      ${rewards.length === 0 ? `
        <div class="tm-card tm-empty">
          <h2>No rewards yet</h2>
          <p>Add a reward children can spend their ${this._esc(pointsName.toLowerCase())} on.</p>
          <button class="tm-btn" data-act="add-reward">+ Add reward</button>
        </div>
      ` : `
        <div class="tm-grid">
          ${rewards.map(r => this._renderRewardCard(r, pointsName)).join("")}
          <button class="tm-add-tile" data-act="add-reward"><span class="tm-add-plus">+</span>Add reward</button>
        </div>
      `}
    `;
  }

  _renderRewardCard(r, pointsName) {
    const totalPooled = (this._state.pool_allocations || []).filter(a => a.reward_id === r.id).reduce((s, a) => s + (a.allocated_points || 0), 0);
    const progressBar = r.pool_enabled && r.cost > 0
      ? `<div class="tm-progress"><span style="width:${Math.min(100, Math.round(totalPooled / r.cost * 100))}%"></span></div>
         <div class="tm-sub">${this._fmtNum(totalPooled)} / ${this._fmtNum(r.cost)} ${this._esc(pointsName)}</div>`
      : "";
    return `
      <article class="tm-card tm-reward-card">
        <header class="tm-child-head">
          <div class="tm-avatar tm-reward-avatar">${this._mdi(r.icon || "mdi:gift")}</div>
          <div class="tm-child-name">
            <h3>${this._esc(r.name)} ${r.is_jackpot ? `<span class="tm-pill tm-pill-jackpot">🏆 Jackpot</span>` : ""} ${r.pool_enabled ? `<span class="tm-pill tm-pill-pool">Pool</span>` : ""}</h3>
            <div class="tm-sub">${this._esc(r.description || "")}</div>
          </div>
        </header>
        <div class="tm-stats">
          <div class="tm-stat"><strong>${this._fmtNum(r.cost)}</strong><span>${this._esc(pointsName)} cost</span></div>
          ${r.quantity != null ? `<div class="tm-stat"><strong>${r.quantity}</strong><span>remaining</span></div>` : ""}
          ${r.expires_at ? `<div class="tm-stat"><strong>${this._esc(r.expires_at)}</strong><span>expires</span></div>` : ""}
        </div>
        ${progressBar}
        <footer class="tm-card-foot">
          <button class="tm-btn tm-btn-ghost" data-act="edit-reward" data-id="${this._esc(r.id)}">Edit</button>
          <button class="tm-btn tm-btn-danger" data-act="delete-reward" data-id="${this._esc(r.id)}">Delete</button>
        </footer>
      </article>
    `;
  }

  // -- Penalties / Bonuses tab -------------------------------------------
  _renderPenBonTab(kind) {
    const items = (kind === "penalty" ? this._state.penalties : this._state.bonuses) || [];
    const childById = Object.fromEntries((this._state.children || []).map(c => [c.id, c]));
    const labels = kind === "penalty" ? { plural: "Penalties", add: "+ Add penalty" } : { plural: "Bonuses", add: "+ Add bonus" };
    return `
      <div class="tm-toolbar">
        <div class="tm-title-sub">${items.length} ${labels.plural.toLowerCase()} configured.</div>
        <button class="tm-btn" data-act="add-${kind}">${labels.add}</button>
      </div>
      ${items.length === 0 ? `
        <div class="tm-card tm-empty">
          <h2>No ${labels.plural.toLowerCase()} yet</h2>
          <p>${kind === "penalty" ? "Add a penalty to deduct points from a child for misbehaviour." : "Add a bonus to award points for going above and beyond."}</p>
          <button class="tm-btn" data-act="add-${kind}">${labels.add}</button>
        </div>
      ` : `
        <div class="tm-table-wrap">
          <table class="tm-table">
            <thead><tr><th>Name</th><th>Points</th><th>Assigned</th><th></th></tr></thead>
            <tbody>
              ${items.map(item => {
                const assignedNames = (item.assigned_to || []).length === 0
                  ? "Both / All"
                  : (item.assigned_to || []).map(id => (childById[id] && childById[id].name) || "?").join(", ");
                return `
                  <tr class="tm-row">
                    <td><span class="tm-row-icon">${this._mdi(item.icon)}</span><strong>${this._esc(item.name)}</strong>${item.description ? `<div class="tm-sub">${this._esc(item.description)}</div>` : ""}</td>
                    <td><strong class="${kind === "penalty" ? "tm-neg" : "tm-pos"}">${kind === "penalty" ? "−" : "+"}${item.points}</strong></td>
                    <td>${this._esc(assignedNames)}</td>
                    <td class="tm-row-actions">
                      <button class="tm-btn tm-btn-ghost" data-act="apply-${kind}" data-id="${this._esc(item.id)}">Apply…</button>
                      <button class="tm-icon-btn" data-act="edit-${kind}" data-id="${this._esc(item.id)}" title="Edit">✏</button>
                      <button class="tm-icon-btn" data-act="delete-${kind}" data-id="${this._esc(item.id)}" title="Delete">🗑</button>
                    </td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>
      `}
    `;
  }

  // -- Groups tab --------------------------------------------------------
  _renderGroupsTab() {
    const groups = this._state.task_groups || [];
    const choreById = Object.fromEntries((this._state.chores || []).map(c => [c.id, c]));
    return `
      <div class="tm-toolbar">
        <div class="tm-title-sub">Groups coordinate chore assignment across multiple chores. Sticky = same child for all; Spread = different children.</div>
        <button class="tm-btn" data-act="add-group">+ Add group</button>
      </div>
      ${groups.length === 0 ? `
        <div class="tm-card tm-empty">
          <h2>No task groups yet</h2>
          <p>Create a group to make chores rotate together (e.g. all the kitchen chores stay with one child each day).</p>
          <button class="tm-btn" data-act="add-group">+ Add group</button>
        </div>
      ` : `
        <div class="tm-grid">
          ${groups.map(g => `
            <article class="tm-card">
              <h3 style="margin: 0 0 6px;">${this._esc(g.name)} <span class="tm-pill tm-pill-${g.policy}">${g.policy}</span></h3>
              <div class="tm-sub" style="margin-bottom: 12px;">${(g.chore_ids || []).length} member chore${(g.chore_ids || []).length === 1 ? "" : "s"}</div>
              <ul class="tm-group-list">
                ${(g.chore_ids || []).map(id => `<li>${this._esc((choreById[id] && choreById[id].name) || `(missing chore ${id})`)}</li>`).join("")}
              </ul>
              <footer class="tm-card-foot" style="margin-top: 12px;">
                <button class="tm-btn tm-btn-ghost" data-act="edit-group" data-id="${this._esc(g.id)}">Edit</button>
                <button class="tm-btn tm-btn-danger" data-act="delete-group" data-id="${this._esc(g.id)}">Delete</button>
              </footer>
            </article>
          `).join("")}
          <button class="tm-add-tile" data-act="add-group"><span class="tm-add-plus">+</span>Add group</button>
        </div>
      `}
    `;
  }

  // -- Settings tab ------------------------------------------------------
  _renderSettingsTab() {
    const s = this._state.settings || {};
    return `
      <div class="tm-card tm-settings">
        <h2>Currency</h2>
        <div class="tm-field-row">
          <label class="tm-field-inline"><span>Points name</span>
            <input type="text" data-setting="points_name" value="${this._esc(s.points_name || "Stars")}" placeholder="Stars">
          </label>
          <label class="tm-field-inline"><span>Points icon</span>
            <input type="text" data-setting="points_icon" value="${this._esc(s.points_icon || "mdi:star")}" placeholder="mdi:star">
          </label>
        </div>

        <h2>History &amp; streaks</h2>
        <div class="tm-field-row">
          <label class="tm-field-inline"><span>History days to retain (30–365)</span>
            <input type="number" min="30" max="365" data-setting="history_days" value="${s.history_days || 90}">
          </label>
          <label class="tm-field-inline"><span>Streak reset mode</span>
            <select data-setting="streak_reset_mode">
              ${STREAK_MODES.map(m => `<option value="${m.v}" ${m.v === (s.streak_reset_mode || "reset") ? "selected" : ""}>${this._esc(m.l)}</option>`).join("")}
            </select>
          </label>
        </div>
        <div class="tm-field-row">
          <label class="tm-field-inline"><span>Weekend points multiplier (1.0 = off)</span>
            <input type="number" step="0.1" min="1" max="5" data-setting="weekend_multiplier" value="${s.weekend_multiplier || 1.0}">
          </label>
          <label class="tm-field-inline"><span>Calendar planning horizon (days)</span>
            <input type="number" min="1" max="90" data-setting="calendar_projection_days" value="${s.calendar_projection_days || 14}">
          </label>
        </div>

        <h2>Bonuses</h2>
        <div class="tm-check-row">
          <label class="tm-switch"><input type="checkbox" data-setting="streak_milestones_enabled" ${s.streak_milestones_enabled ? "checked" : ""}><span class="tm-slider"></span></label>
          Award bonus points at streak milestones (3, 7, 14, 30, 60, 100 days)
        </div>
        <div class="tm-check-row">
          <label class="tm-switch"><input type="checkbox" data-setting="perfect_week_enabled" ${s.perfect_week_enabled ? "checked" : ""}><span class="tm-slider"></span></label>
          Award bonus for completing chores every day of a week
        </div>
        <div class="tm-field-row">
          <label class="tm-field-inline"><span>Perfect week bonus points</span>
            <input type="number" min="0" data-setting="perfect_week_bonus" value="${s.perfect_week_bonus || 50}">
          </label>
        </div>

        <h2>Notifications</h2>
        <div class="tm-field-row">
          <label class="tm-field-inline"><span>Notify service for approval pings</span>
            <input type="text" data-setting="notify_service" value="${this._esc(s.notify_service || "")}" placeholder="notify.mobile_app_your_phone">
          </label>
        </div>
        <div class="tm-sub" style="margin-bottom: 16px;">Leave blank to use HA's persistent notifications only.</div>

        <footer class="tm-card-foot" style="border-top: 1px solid var(--divider-color); padding-top: 16px; justify-content: flex-end;">
          <button class="tm-btn" data-act="save-settings">Save settings</button>
        </footer>
      </div>
    `;
  }

  // -- Dialogs -----------------------------------------------------------
  _renderDialog() {
    if (this._dialog.kind === "child")        return this._renderChildDialog();
    if (this._dialog.kind === "chore")        return this._renderChoreDialog();
    if (this._dialog.kind === "reward")       return this._renderRewardDialog();
    if (this._dialog.kind === "penalty")      return this._renderPenBonDialog("penalty");
    if (this._dialog.kind === "bonus")        return this._renderPenBonDialog("bonus");
    if (this._dialog.kind === "group")        return this._renderGroupDialog();
    if (this._dialog.kind === "apply-penalty") return this._renderApplyDialog("penalty");
    if (this._dialog.kind === "apply-bonus")   return this._renderApplyDialog("bonus");
    return "";
  }

  _renderChildDialog() {
    const d = this._dialog.data;
    return this._dialogShell(this._dialog.mode === "add" ? "Add child" : "Edit child",
      [
        this._field("Name", "name", d.name, "text", "e.g. Malia"),
        this._field("Avatar (MDI icon)", "avatar", d.avatar, "text", "Examples: mdi:face-woman, mdi:face-man, mdi:dog"),
        this._field("Availability sensor (optional)", "availability_entity", d.availability_entity, "text",
          "HA entity that says whether the child is available. States <code>on</code>, <code>home</code>, <code>available</code>, <code>present</code>, <code>true</code> mean available. Leave blank to treat as always available."),
      ].join(""),
      `<button class="tm-btn tm-btn-ghost" data-act="close-dialog">Cancel</button>
       <button class="tm-btn" data-act="save-child">Save</button>`
    );
  }

  _renderChoreDialog() {
    const d = this._dialog.data;
    const children = this._state.children || [];
    const groups = this._state.task_groups || [];
    const memberInGroup = (d.id && groups.find(g => (g.chore_ids || []).includes(d.id))) || null;
    const showSpecificDays = d.schedule_mode === "specific_days";
    const showRecurring    = d.schedule_mode === "recurring";

    return this._dialogShell(this._dialog.mode === "add" ? "Add chore" : "Edit chore",
      [
        this._field("Name", "name", d.name, "text"),
        this._field("Description (optional)", "description", d.description, "text"),

        `<div class="tm-field-row">
          ${this._field("Points", "points", d.points, "number")}
          ${this._field("Daily limit", "daily_limit", d.daily_limit, "number")}
        </div>`,

        // Assigned to (multi-checkbox)
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">Assigned to</span>
            <div class="tm-multi">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">Leave empty to assign to all children.</span>
          </div>
        ` : `<div class="tm-field"><span class="tm-field-hint">Add some children first to assign chores to them.</span></div>`,

        this._select("Assignment mode", "assignment_mode", d.assignment_mode, ASSIGNMENT_MODES,
          "Everyone = all assigned children see it. Alternating = rotate one per day. Random = pick one daily. Balanced = split evenly across the day."),

        this._select("Time category", "time_category", d.time_category, TIME_CATEGORIES),

        // Schedule mode
        this._select("Schedule mode", "schedule_mode", d.schedule_mode, SCHEDULE_MODES),

        showSpecificDays ? `
          <div class="tm-field">
            <span class="tm-field-label">Days of week (leave empty = every day)</span>
            <div class="tm-day-row">
              ${DAYS.map(day => `
                <button type="button" class="tm-day-btn ${(d.due_days || []).includes(day.v) ? "tm-day-on" : ""}" data-act="toggle-day" data-day="${day.v}">${day.l}</button>
              `).join("")}
            </div>
          </div>
        ` : "",

        showRecurring ? `
          <div class="tm-field-row">
            ${this._select("Recurrence", "recurrence", d.recurrence, RECURRENCES)}
            ${this._field("Day of week (weekly only)", "recurrence_day", d.recurrence_day, "text", "e.g. monday — leave blank for any day")}
          </div>
          <div class="tm-field-row">
            ${this._field("Start date (every-2-days only)", "recurrence_start", d.recurrence_start, "text", "YYYY-MM-DD; blank = today")}
            ${this._select("First occurrence", "first_occurrence_mode", d.first_occurrence_mode, FIRST_OCCURRENCE)}
          </div>
        ` : "",

        this._select("Completion sound", "completion_sound", d.completion_sound, COMPLETION_SOUNDS.map(s => ({ v: s, l: s }))),

        // Switches
        this._switch("Requires parent approval", "requires_approval", d.requires_approval),
        this._switch("Skip unavailable children", "require_availability", d.require_availability,
          "Uses each child's availability sensor (set on their profile)."),

        memberInGroup ? `
          <div class="tm-field">
            <span class="tm-field-hint">Member of task group: <strong>${this._esc(memberInGroup.name)}</strong> (${memberInGroup.policy}). Manage membership on the Groups tab.</span>
          </div>
        ` : "",

        // Advanced section
        `<details class="tm-advanced">
          <summary>Advanced</summary>
          <div style="padding-top: 12px;">
            ${this._field("Visibility entity (optional)", "visibility_entity", d.visibility_entity, "text", "Entity ID; chore only shows when its state matches the rule below.")}
            <div class="tm-field-row">
              ${this._select("Visibility operator", "visibility_operator", d.visibility_operator, VISIBILITY_OPS)}
              ${this._field("Visibility value", "visibility_state", d.visibility_state, "text", 'e.g. "on", "home", "30"')}
            </div>
            ${this._field("Calendar entities to publish to (comma-separated)", "publish_calendar_entities_csv", d.publish_calendar_entities_csv, "text", "e.g. calendar.family, calendar.kids — blank = no calendar publishing")}
            ${this._switch("Enabled", "enabled", d.enabled !== false)}
          </div>
        </details>`,
      ].join(""),
      `<button class="tm-btn tm-btn-ghost" data-act="close-dialog">Cancel</button>
       <button class="tm-btn" data-act="save-chore">Save</button>`
    );
  }

  _renderRewardDialog() {
    const d = this._dialog.data;
    const children = this._state.children || [];
    const pointsName = this._state.settings.points_name || "points";
    return this._dialogShell(this._dialog.mode === "add" ? "Add reward" : "Edit reward",
      [
        this._field("Name", "name", d.name, "text"),
        this._field("Description (optional)", "description", d.description, "text"),
        `<div class="tm-field-row">
          ${this._field(`Cost (${pointsName})`, "cost", d.cost, "number")}
          ${this._field("Icon (MDI)", "icon", d.icon, "text")}
        </div>`,

        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">Assigned to</span>
            <div class="tm-multi">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-reward-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">Leave empty to make available to all children.</span>
          </div>
        ` : "",

        this._switch("Pool reward (savings jar)", "pool_enabled", d.pool_enabled,
          "Children deposit points into this reward's dedicated pool rather than spending from their balance. Good for long-term savings goals."),
        this._switch("Jackpot — pool from all assigned children", "is_jackpot", d.is_jackpot,
          "Combine all children's contributions toward one shared reward."),

        `<div class="tm-field-row">
          ${this._field("Limited quantity (blank = unlimited)", "quantity_str", d.quantity_str, "text", "Each approved claim reduces by 1.")}
          ${this._field("Expires (YYYY-MM-DD, blank = never)", "expires_at", d.expires_at, "text", "Pooled points are refunded at midnight.")}
        </div>`,
      ].join(""),
      `<button class="tm-btn tm-btn-ghost" data-act="close-dialog">Cancel</button>
       <button class="tm-btn" data-act="save-reward">Save</button>`
    );
  }

  _renderPenBonDialog(kind) {
    const d = this._dialog.data;
    const children = this._state.children || [];
    const isPenalty = kind === "penalty";
    return this._dialogShell(`${this._dialog.mode === "add" ? "Add" : "Edit"} ${kind}`,
      [
        this._field("Name", "name", d.name, "text"),
        this._field("Description (optional)", "description", d.description, "text"),
        `<div class="tm-field-row">
          ${this._field(`Points to ${isPenalty ? "deduct" : "award"}`, "points", d.points, "number")}
          ${this._field("Icon (MDI)", "icon", d.icon, "text")}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">Applies to</span>
            <div class="tm-multi">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-penbon-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">Leave empty to apply to all children.</span>
          </div>
        ` : "",
      ].join(""),
      `<button class="tm-btn tm-btn-ghost" data-act="close-dialog">Cancel</button>
       <button class="tm-btn" data-act="save-${kind}">Save</button>`
    );
  }

  _renderApplyDialog(kind) {
    const d = this._dialog.data;
    const item = d.item;
    const children = this._state.children || [];
    const isPenalty = kind === "penalty";
    const eligible = (item.assigned_to || []).length === 0
      ? children
      : children.filter(c => (item.assigned_to || []).includes(c.id));
    return this._dialogShell(`Apply ${kind}: ${item.name}`,
      `<p>Choose which child to ${isPenalty ? "apply this penalty to (will deduct" : "award this bonus to (will add"} <strong>${item.points}</strong> points).</p>
       ${eligible.length === 0 ? `<p class="tm-sub">No eligible children. Edit the ${kind} to set who it applies to.</p>` : `
        <div class="tm-multi" style="margin-top: 12px;">
          ${eligible.map(c => `
            <button type="button" class="tm-btn tm-btn-ghost" data-act="do-apply-${kind}" data-id="${this._esc(item.id)}" data-child="${this._esc(c.id)}">
              ${this._esc(c.name)}
            </button>
          `).join("")}
        </div>
       `}`,
      `<button class="tm-btn tm-btn-ghost" data-act="close-dialog">Close</button>`
    );
  }

  _renderGroupDialog() {
    const d = this._dialog.data;
    const chores = (this._state.chores || []).filter(c => c.assignment_mode && c.assignment_mode !== "everyone");
    return this._dialogShell(this._dialog.mode === "add" ? "Add task group" : "Edit task group",
      [
        this._field("Name", "name", d.name, "text"),
        this._select("Policy", "policy", d.policy, TASK_GROUP_POLICIES,
          "Sticky = same child for all chores in the group today. Spread = different children today."),
        chores.length === 0 ? `
          <div class="tm-field">
            <span class="tm-field-hint">Only rotation-mode chores (alternating / random / balanced) can join a group. Edit a chore's assignment mode first.</span>
          </div>
        ` : `
          <div class="tm-field">
            <span class="tm-field-label">Member chores (order matters for sticky — first is the leader)</span>
            <div class="tm-multi">
              ${chores.map(c => `
                <button type="button" class="tm-chip-btn ${(d.chore_ids || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-group-chore" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
          </div>
        `,
      ].join(""),
      `<button class="tm-btn tm-btn-ghost" data-act="close-dialog">Cancel</button>
       <button class="tm-btn" data-act="save-group">Save</button>`
    );
  }

  // ---- form-element helpers --------------------------------------------
  _dialogShell(title, body, footer) {
    return `
      <div class="tm-scrim" data-act="scrim">
        <div class="tm-dialog">
          <header class="tm-dialog-head">
            <h2>${this._esc(title)}</h2>
            <button class="tm-icon-btn" data-act="close-dialog" title="Close">&times;</button>
          </header>
          <div class="tm-dialog-body">${body}</div>
          <footer class="tm-dialog-foot">${footer}</footer>
        </div>
      </div>`;
  }

  _field(label, name, value, type = "text", hint = "") {
    return `
      <label class="tm-field">
        <span class="tm-field-label">${this._esc(label)}</span>
        <input type="${type}" data-field="${name}" value="${this._esc(value == null ? "" : value)}">
        ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
      </label>`;
  }

  _select(label, name, value, options, hint = "") {
    return `
      <label class="tm-field">
        <span class="tm-field-label">${this._esc(label)}</span>
        <select data-field="${name}">
          ${options.map(o => `<option value="${this._esc(o.v)}" ${o.v === value ? "selected" : ""}>${this._esc(o.l)}</option>`).join("")}
        </select>
        ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
      </label>`;
  }

  _switch(label, name, checked, hint = "") {
    return `
      <div class="tm-check-row">
        <label class="tm-switch">
          <input type="checkbox" data-field="${name}" ${checked ? "checked" : ""}>
          <span class="tm-slider"></span>
        </label>
        <div>
          <div>${this._esc(label)}</div>
          ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
        </div>
      </div>`;
  }

  _labelOf(options, value) {
    const o = options.find(x => x.v === value);
    return o ? o.l : value;
  }

  _esc(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  _fmtNum(n) {
    if (n == null) return "0";
    return new Intl.NumberFormat().format(n);
  }

  _mdi(name) {
    return `<ha-icon icon="${this._esc(name || "mdi:account-circle")}"></ha-icon>`;
  }

  // ---- styles ----------------------------------------------------------
  _styles() {
    return `<style>
      :host, taskmate-panel { display: block; height: 100%; background: var(--primary-background-color, #111418); color: var(--primary-text-color, #e1e3e6); }
      .tm-shell { display: flex; flex-direction: column; height: 100%; font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif); position: relative; }

      .tm-appbar { height: 56px; background: var(--app-header-background-color, #1a1d22); color: var(--app-header-text-color, #fff); display: flex; align-items: center; gap: 12px; padding: 0 16px; flex-shrink: 0; border-bottom: 1px solid var(--divider-color, #2a2e36); }
      .tm-appbar h1 { margin: 0; font-size: 20px; font-weight: 400; flex: 1; }
      .tm-chip { background: rgba(255,255,255,0.1); padding: 4px 10px; border-radius: 999px; font-size: 12px; }

      .tm-tabs { display: flex; background: var(--app-header-background-color, #1a1d22); border-bottom: 1px solid var(--divider-color, #2a2e36); padding: 0 8px; overflow-x: auto; flex-shrink: 0; scrollbar-width: none; }
      .tm-tabs::-webkit-scrollbar { display: none; }
      .tm-tab { border: 0; background: transparent; color: var(--secondary-text-color, #9aa0a6); padding: 14px 18px; cursor: pointer; font-size: 14px; font-weight: 500; border-bottom: 2px solid transparent; margin-bottom: -1px; white-space: nowrap; font-family: inherit; }
      .tm-tab:hover { color: var(--primary-text-color, #e1e3e6); }
      .tm-tab-active { color: var(--primary-color, #03a9f4); border-bottom-color: var(--primary-color, #03a9f4); }

      .tm-body { flex: 1; overflow: auto; padding: 20px 24px 48px; }
      .tm-toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
      .tm-title-sub { flex: 1; color: var(--secondary-text-color, #9aa0a6); font-size: 13px; }

      .tm-card { background: var(--card-background-color, #1c1f24); border: 1px solid var(--divider-color, #2a2e36); border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; }
      .tm-card h2 { margin: 16px 0 12px; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--primary-text-color); }
      .tm-card h2:first-child { margin-top: 0; }
      .tm-card p { margin: 8px 0; color: var(--secondary-text-color, #9aa0a6); }
      .tm-card code { background: var(--code-editor-background-color, #0e1115); padding: 2px 6px; border-radius: 4px; font-size: 12px; }
      .tm-card-error { border-left: 3px solid var(--error-color, #ef5350); color: var(--error-color, #ef5350); }
      .tm-empty { text-align: center; padding: 40px 24px; }

      .tm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
      .tm-child-card { margin-bottom: 0; display: flex; flex-direction: column; }
      .tm-child-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
      .tm-avatar { width: 48px; height: 48px; border-radius: 50%; background: var(--secondary-background-color, #242830); display: grid; place-items: center; flex-shrink: 0; color: var(--primary-color, #03a9f4); }
      .tm-avatar ha-icon { --mdc-icon-size: 28px; }
      .tm-reward-avatar { color: var(--accent-color, #ffca28); }
      .tm-child-name { min-width: 0; flex: 1; }
      .tm-child-name h3 { margin: 0; font-size: 17px; font-weight: 600; }
      .tm-sub { color: var(--secondary-text-color, #9aa0a6); font-size: 12px; margin-top: 2px; word-break: break-all; }
      .tm-sub code { background: var(--code-editor-background-color, #0e1115); padding: 1px 6px; border-radius: 4px; font-size: 11px; }

      .tm-stats { display: flex; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
      .tm-stat { background: var(--secondary-background-color, #242830); padding: 8px 12px; border-radius: 8px; flex: 1; min-width: 80px; }
      .tm-stat strong { display: block; font-size: 20px; font-weight: 600; color: var(--primary-color, #03a9f4); }
      .tm-stat span { font-size: 11px; color: var(--secondary-text-color, #9aa0a6); text-transform: uppercase; letter-spacing: 0.5px; }

      .tm-card-foot { display: flex; gap: 8px; margin-top: auto; padding-top: 12px; border-top: 1px solid var(--divider-color, #2a2e36); }

      .tm-add-tile { display: grid; place-items: center; gap: 6px; background: transparent; border: 2px dashed var(--divider-color, #2a2e36); border-radius: 12px; color: var(--secondary-text-color, #9aa0a6); cursor: pointer; min-height: 180px; font-size: 14px; font-family: inherit; transition: border-color .15s, color .15s, background .15s; }
      .tm-add-tile:hover { border-color: var(--primary-color, #03a9f4); color: var(--primary-color, #03a9f4); background: rgba(3,169,244,0.06); }
      .tm-add-plus { font-size: 32px; line-height: 1; }

      .tm-btn { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #001a26); border: 0; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500; font-family: inherit; }
      .tm-btn:hover { filter: brightness(1.1); }
      .tm-btn-ghost { background: transparent; color: var(--primary-text-color, #e1e3e6); border: 1px solid var(--divider-color, #2a2e36); }
      .tm-btn-ghost:hover { background: var(--secondary-background-color, #242830); filter: none; }
      .tm-btn-danger { background: transparent; color: var(--error-color, #ef5350); border: 1px solid rgba(239,83,80,0.4); }
      .tm-btn-danger:hover { background: rgba(239,83,80,0.1); filter: none; }
      .tm-icon-btn { width: 36px; height: 36px; border: 0; background: transparent; border-radius: 50%; cursor: pointer; display: grid; place-items: center; color: var(--secondary-text-color, #9aa0a6); font-size: 18px; line-height: 1; font-family: inherit; }
      .tm-icon-btn:hover { background: var(--secondary-background-color, #242830); color: var(--primary-text-color, #e1e3e6); }

      /* Pills */
      .tm-pill { display: inline-block; background: var(--secondary-background-color, #242830); color: var(--secondary-text-color, #9aa0a6); padding: 1px 8px; border-radius: 999px; font-size: 11px; margin-left: 4px; vertical-align: middle; }
      .tm-pill-alternating, .tm-pill-random, .tm-pill-balanced { background: rgba(3,169,244,0.15); color: var(--primary-color, #03a9f4); }
      .tm-pill-jackpot { background: rgba(255,202,40,0.15); color: var(--accent-color, #ffca28); }
      .tm-pill-pool { background: rgba(255,167,38,0.15); color: #ffa726; }
      .tm-pill-sticky { background: rgba(149,117,205,0.18); color: #b39ddb; }
      .tm-pill-spread { background: rgba(102,187,106,0.15); color: var(--success-color, #66bb6a); }

      /* Tables */
      .tm-table-wrap { background: var(--card-background-color, #1c1f24); border: 1px solid var(--divider-color, #2a2e36); border-radius: 12px; overflow: hidden; }
      .tm-table { width: 100%; border-collapse: collapse; font-size: 13px; }
      .tm-table th, .tm-table td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--divider-color, #2a2e36); }
      .tm-table th { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--secondary-text-color, #9aa0a6); font-weight: 500; background: var(--app-header-background-color, #1a1d22); }
      .tm-table tr:last-child td { border-bottom: 0; }
      .tm-row:hover { background: var(--secondary-background-color, #242830); }
      .tm-row-disabled { opacity: 0.5; }
      .tm-row-icon { display: inline-flex; vertical-align: middle; margin-right: 8px; --mdc-icon-size: 18px; color: var(--secondary-text-color); }
      .tm-row-actions { text-align: right; white-space: nowrap; display: flex; gap: 4px; justify-content: flex-end; align-items: center; }
      .tm-yes { color: var(--success-color, #66bb6a); }
      .tm-no  { color: var(--secondary-text-color, #6a7079); }
      .tm-neg { color: var(--error-color, #ef5350); }
      .tm-pos { color: var(--success-color, #66bb6a); }

      .tm-progress { height: 8px; background: var(--secondary-background-color, #242830); border-radius: 999px; overflow: hidden; margin: 8px 0 4px; }
      .tm-progress > span { display: block; height: 100%; background: linear-gradient(90deg, var(--primary-color, #03a9f4), #4fc3f7); }

      .tm-group-list { margin: 0; padding-left: 20px; color: var(--secondary-text-color, #9aa0a6); font-size: 13px; }

      /* Settings */
      .tm-settings .tm-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 8px; }
      .tm-field-inline { display: block; margin-bottom: 12px; }
      .tm-field-inline span { display: block; color: var(--secondary-text-color, #9aa0a6); font-size: 12px; margin-bottom: 4px; }
      .tm-field-inline input, .tm-field-inline select { width: 100%; background: var(--secondary-background-color, #242830); border: 1px solid var(--divider-color, #2a2e36); border-radius: 8px; padding: 8px 12px; color: var(--primary-text-color); font-size: 14px; box-sizing: border-box; font-family: inherit; }

      /* Dialog */
      .tm-scrim { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: flex-start; justify-content: center; padding: 60px 20px; z-index: 100; overflow-y: auto; }
      .tm-dialog { background: var(--card-background-color, #1c1f24); border: 1px solid var(--divider-color, #2a2e36); border-radius: 12px; width: 100%; max-width: 560px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); display: flex; flex-direction: column; max-height: calc(100vh - 120px); }
      .tm-dialog-head { padding: 16px 20px; border-bottom: 1px solid var(--divider-color, #2a2e36); display: flex; align-items: center; }
      .tm-dialog-head h2 { margin: 0; font-size: 18px; font-weight: 500; flex: 1; }
      .tm-dialog-body { padding: 16px 20px; overflow-y: auto; }
      .tm-dialog-body .tm-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
      .tm-dialog-foot { padding: 14px 20px; border-top: 1px solid var(--divider-color, #2a2e36); display: flex; justify-content: flex-end; gap: 10px; }

      .tm-field { display: block; margin-bottom: 16px; }
      .tm-field-label { display: block; color: var(--secondary-text-color, #9aa0a6); font-size: 12px; margin-bottom: 6px; font-weight: 500; }
      .tm-field input, .tm-field select { width: 100%; background: var(--secondary-background-color, #242830); border: 1px solid var(--divider-color, #2a2e36); border-radius: 8px; padding: 9px 12px; color: var(--primary-text-color, #e1e3e6); font-size: 14px; box-sizing: border-box; font-family: inherit; }
      .tm-field input:focus, .tm-field select:focus { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: -1px; border-color: transparent; }
      .tm-field-hint { display: block; color: var(--secondary-text-color, #6a7079); font-size: 12px; margin-top: 6px; line-height: 1.4; }
      .tm-field-hint code { background: var(--code-editor-background-color, #0e1115); padding: 1px 5px; border-radius: 3px; font-size: 11px; }

      .tm-multi { display: flex; gap: 6px; flex-wrap: wrap; }
      .tm-chip-btn { background: var(--secondary-background-color, #242830); color: var(--secondary-text-color, #9aa0a6); border: 1px solid var(--divider-color, #2a2e36); padding: 6px 12px; border-radius: 999px; cursor: pointer; font-size: 13px; font-family: inherit; }
      .tm-chip-btn:hover { color: var(--primary-text-color, #e1e3e6); }
      .tm-chip-on { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #001a26); border-color: var(--primary-color, #03a9f4); }

      .tm-day-row { display: flex; gap: 6px; flex-wrap: wrap; }
      .tm-day-btn { width: 44px; height: 36px; background: var(--secondary-background-color, #242830); color: var(--secondary-text-color, #9aa0a6); border: 1px solid var(--divider-color, #2a2e36); border-radius: 6px; cursor: pointer; font-size: 12px; font-family: inherit; }
      .tm-day-on { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #001a26); border-color: var(--primary-color, #03a9f4); }

      .tm-check-row { display: flex; align-items: flex-start; gap: 12px; padding: 8px 0; color: var(--primary-text-color, #e1e3e6); font-size: 14px; }
      .tm-check-row > div { flex: 1; }
      .tm-switch { position: relative; display: inline-block; width: 38px; height: 22px; flex-shrink: 0; }
      .tm-switch input { opacity: 0; width: 0; height: 0; }
      .tm-slider { position: absolute; inset: 0; background: var(--secondary-background-color, #242830); border: 1px solid var(--divider-color, #2a2e36); border-radius: 999px; transition: background .15s; cursor: pointer; }
      .tm-slider::before { content: ''; position: absolute; height: 16px; width: 16px; left: 2px; top: 2px; background: white; border-radius: 50%; transition: transform .15s; }
      .tm-switch input:checked + .tm-slider { background: var(--primary-color, #03a9f4); border-color: var(--primary-color, #03a9f4); }
      .tm-switch input:checked + .tm-slider::before { transform: translateX(16px); }

      .tm-advanced { border: 1px dashed var(--divider-color, #2a2e36); border-radius: 8px; padding: 10px 14px; margin-top: 8px; }
      .tm-advanced summary { cursor: pointer; color: var(--secondary-text-color, #9aa0a6); font-size: 13px; user-select: none; }

      /* Toast */
      .tm-toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); padding: 10px 18px; border-radius: 8px; font-size: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.4); z-index: 200; }
      .tm-toast-ok { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #001a26); }
      .tm-toast-err { background: var(--error-color, #ef5350); color: white; }

      @media (max-width: 700px) {
        .tm-body { padding: 16px; }
        .tm-toolbar { flex-direction: column; align-items: stretch; }
        .tm-dialog { max-width: none; }
        .tm-scrim { padding: 0; }
        .tm-dialog { border-radius: 0; max-height: 100vh; height: 100vh; }
        .tm-dialog-body .tm-field-row, .tm-settings .tm-field-row { grid-template-columns: 1fr; }
      }
    </style>`;
  }
}

customElements.define("taskmate-panel", TaskMatePanel);
