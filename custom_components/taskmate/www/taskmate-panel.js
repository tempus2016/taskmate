/**
 * TaskMate admin panel — sidebar entry at /taskmate-admin.
 *
 * v3.5.0-beta.5 — HA-native styling:
 *   - All custom --tm-* tokens now map to HA theme variables
 *     (--primary-color, --card-background-color, etc.).
 *   - Dark mode handled automatically via HA vars (no .dark override).
 *   - Shadows, radii, fonts follow HA defaults.
 *   - Entity picker dropdown uses theme-aware colors.
 */

const PANEL_VERSION = "3.5.0-beta.5";

const TABS = [
  { id: "children",  label: "Children" },
  { id: "activity",  label: "Activity" },
  { id: "chores",    label: "Chores" },
  { id: "rewards",   label: "Rewards" },
  { id: "penalties", label: "Penalties" },
  { id: "bonuses",   label: "Bonuses" },
  { id: "groups",    label: "Groups" },
  { id: "templates", label: "Templates" },
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
  { v: "none",       l: "No filter — always show chore" },
  { v: "equals",     l: "Equals — state matches exactly" },
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
    this._dialog = null;
    this._dialogInitialHash = null;  // for confirm-on-leave
    this._filter = "";               // per-tab search/filter
    this._inlineRename = null;       // { kind: "chore", id, value }
    this._reorderDrag = null;        // tracks drag state during reorder
    this._templateView = null;       // null | "picker" | "preview"
    this._templateSelected = null;   // selected template object
    this._templateChores = [];       // editable chores for preview step
    this._saveTemplateDialog = false; // "save as template" dialog state
    this._rendered = false;
    this._onFocusIn = this._onFocusIn.bind(this);
    this._onClick = this._onClick.bind(this);
    this._onDblClick = this._onDblClick.bind(this);
    this._onInput = this._onInput.bind(this);
    this._onChange = this._onChange.bind(this);
    this._onValueChanged = this._onValueChanged.bind(this);
    this._onKeyDown = this._onKeyDown.bind(this);
    this._onDragStart = this._onDragStart.bind(this);
    this._onDragOver = this._onDragOver.bind(this);
    this._onDrop = this._onDrop.bind(this);
    this._onVisibilityChange = this._onVisibilityChange.bind(this);
    this._lastConnected = null;
  }

  set hass(value) {
    const first = this._hass === null;
    const prevConnected = this._lastConnected;
    this._hass = value;

    const isDark = this._isHaDark();
    this.classList.toggle("dark", isDark);
    this.classList.toggle("light", !isDark);
    const connNow = !!(value && value.connection && value.connection.connected !== false);
    this._lastConnected = connNow;

    if (first) {
      this._fetchState();
    } else if (connNow && prevConnected === false) {
      // WS reconnected after a drop — refetch so the panel reflects current state.
      this._fetchState();
    } else if (connNow && this._error) {
      // Recover from a previous fetch failure (e.g. WS was mid-handshake earlier).
      this._error = null;
      this._fetchState();
    }
    if (!this._rendered) this._render();
    this._bindHaPickers(false);
  }
  get hass() { return this._hass; }
  set narrow(_v) {}
  set route(_v) {}
  set panel(_v) {}

  connectedCallback() {
    this.addEventListener("focusin", this._onFocusIn);
    this.addEventListener("click", this._onClick);
    this.addEventListener("dblclick", this._onDblClick);
    this.addEventListener("input", this._onInput);
    this.addEventListener("change", this._onChange);
    this.addEventListener("value-changed", this._onValueChanged);
    this.addEventListener("keydown", this._onKeyDown);
    this.addEventListener("dragstart", this._onDragStart);
    this.addEventListener("dragover", this._onDragOver);
    this.addEventListener("drop", this._onDrop);
    document.addEventListener("visibilitychange", this._onVisibilityChange);
    if (!this.classList.contains("dark") && !this.classList.contains("light")) {
      const isDark = this._isHaDark();
      this.classList.toggle("dark", isDark);
      this.classList.toggle("light", !isDark);
    }
    if (!this._rendered) this._render();
  }
  disconnectedCallback() {
    this.removeEventListener("focusin", this._onFocusIn);
    this.removeEventListener("click", this._onClick);
    this.removeEventListener("dblclick", this._onDblClick);
    this.removeEventListener("input", this._onInput);
    this.removeEventListener("change", this._onChange);
    this.removeEventListener("value-changed", this._onValueChanged);
    this.removeEventListener("keydown", this._onKeyDown);
    this.removeEventListener("dragstart", this._onDragStart);
    this.removeEventListener("dragover", this._onDragOver);
    this.removeEventListener("drop", this._onDrop);
    document.removeEventListener("visibilitychange", this._onVisibilityChange);
  }

  _onVisibilityChange() {
    if (document.visibilityState !== "visible") return;
    if (!this._hass) return;
    // Tab woke up — if we're showing an error or have no state, refetch.
    if (this._error || !this._state) this._fetchState();
  }

  _isHaDark() {
    const el = this.isConnected ? this : document.documentElement;
    const bg = getComputedStyle(el)
      .getPropertyValue("--primary-background-color").trim();
    if (!bg) return false;
    let r, g, b;
    if (bg.startsWith("#")) {
      const h = bg.slice(1);
      r = parseInt(h.substr(0, 2), 16);
      g = parseInt(h.substr(2, 2), 16);
      b = parseInt(h.substr(4, 2), 16);
    } else {
      const m = bg.match(/\d+/g);
      if (m) { r = +m[0]; g = +m[1]; b = +m[2]; }
    }
    if (r === undefined) return false;
    return (r * 299 + g * 587 + b * 114) / 1000 < 128;
  }

  // ---- state -----------------------------------------------------------
  async _fetchState(_attempt = 0) {
    if (!this._hass) return;
    this._loading = true;
    this._render();
    try {
      this._state = await this._hass.callWS({ type: "taskmate/get_state" });
      this._error = null;
    } catch (err) {
      // Retry once after a short delay — covers the race where the WS is
      // still mid-reconnect when we make the call.
      if (_attempt < 1) {
        this._loading = false;
        await new Promise(r => setTimeout(r, 800));
        return this._fetchState(_attempt + 1);
      }
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

  _hashDialog() {
    return this._dialog ? JSON.stringify(this._dialog.data) : "";
  }

  _closeDialog(force = false) {
    if (!force && this._dialog && this._dialogInitialHash != null && this._hashDialog() !== this._dialogInitialHash) {
      if (!confirm("You have unsaved changes — discard them?")) return;
    }
    this._dialog = null;
    this._dialogInitialHash = null;
    this._render();
  }

  _openDialog(d) {
    this._dialog = d;
    this._dialogInitialHash = this._hashDialog();
    this._render();
  }

  // ---- event delegation ------------------------------------------------
  _onClick(e) {
    if (!e.target.closest(".tm-ep")) this._closeEntityDropdown();
    const epSelected = e.target.closest(".tm-ep-selected");
    if (epSelected && !e.target.closest(".tm-entity-clear")) {
      const picker = epSelected.closest(".tm-ep");
      const field = picker?.dataset?.epField;
      if (field && this._dialog?.data) {
        this._dialog.data[field] = "";
        this._render();
        requestAnimationFrame(() => {
          const input = this.querySelector(`.tm-ep[data-ep-field="${field}"] .tm-ep-input`);
          if (input) { input.focus(); }
        });
      }
      return;
    }
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const act = t.dataset.act;

    if (act === "tab")          { this._activeTab = t.dataset.tab; this._filter = ""; this._render(); return; }
    if (act === "close-dialog") { this._closeDialog(); return; }
    if (act === "clear-field") { if (this._dialog?.data) { this._dialog.data[t.dataset.field] = ""; this._render(); } return; }
    if (act === "pick-entity") { if (this._dialog?.data) { this._dialog.data[t.dataset.field] = t.dataset.value; this._closeEntityDropdown(); this._render(); } return; }
    if (act === "scrim") {
      if (e.target === this.querySelector(".tm-scrim")) this._closeDialog();
      return;
    }
    if (act === "retry")        { this._fetchState(); return; }
    if (act === "switch-to-activity") { this._activeTab = "activity"; this._render(); return; }

    // Children
    if (act === "add-child")    { this._openChildDialog(null); return; }
    if (act === "edit-child")   { this._openChildDialog(t.dataset.id); return; }
    if (act === "delete-child") { this._confirmDelete("child", t.dataset.id); return; }
    if (act === "save-child")   { this._doSaveChild(); return; }
    if (act === "reorder-chores-for-child") { this._openReorderDialog(t.dataset.id); return; }
    if (act === "save-chore-order") { this._doSaveChoreOrder(); return; }

    // Chores
    if (act === "add-chore")    { this._openChoreDialog(null); return; }
    if (act === "edit-chore")   { this._openChoreDialog(t.dataset.id); return; }
    if (act === "delete-chore") { this._confirmDelete("chore", t.dataset.id); return; }
    if (act === "save-chore")   { this._doSaveChore(); return; }
    if (act === "bulk-add-chore") { this._openBulkAddDialog(); return; }
    if (act === "save-bulk-chores") { this._doSaveBulkChores(); return; }
    if (act === "rename-chore-start") { this._startInlineRename("chore", t.dataset.id); return; }
    if (act === "rename-chore-commit") { this._commitInlineRename(); return; }
    if (act === "rename-chore-cancel") { this._inlineRename = null; this._render(); return; }
    if (act === "toggle-day")        { this._toggleArrayField("due_days", t.dataset.day); return; }
    if (act === "toggle-bulk-day")   { this._toggleArrayField("due_days", t.dataset.day); return; }
    if (act === "toggle-assigned")   { this._toggleArrayField("assigned_to", t.dataset.id); return; }
    if (act === "toggle-calendar")   { this._toggleArrayField("publish_calendar_entities", t.dataset.id); return; }
    if (act === "add-bonus-subtask") { this._addBonusSubtask(); return; }
    if (act === "remove-bonus-subtask") { this._removeBonusSubtask(Number(t.dataset.idx)); return; }

    // Rewards
    if (act === "add-reward")    { this._openRewardDialog(null); return; }
    if (act === "edit-reward")   { this._openRewardDialog(t.dataset.id); return; }
    if (act === "delete-reward") { this._confirmDelete("reward", t.dataset.id); return; }
    if (act === "save-reward")   { this._doSaveReward(); return; }
    if (act === "toggle-reward-assigned") { this._toggleArrayField("assigned_to", t.dataset.id); return; }

    // Penalties
    if (act === "add-penalty")    { this._openPenBonDialog("penalty", null); return; }
    if (act === "edit-penalty")   { this._openPenBonDialog("penalty", t.dataset.id); return; }
    if (act === "delete-penalty") { this._confirmDelete("penalty", t.dataset.id); return; }
    if (act === "save-penalty")   { this._doSavePenBon("penalty"); return; }
    if (act === "apply-penalty")  { this._openApplyDialog("penalty", t.dataset.id); return; }
    if (act === "do-apply-penalty") { this._doApplyPenBon("penalty", t.dataset.id, t.dataset.child); return; }

    // Bonuses
    if (act === "add-bonus")    { this._openPenBonDialog("bonus", null); return; }
    if (act === "edit-bonus")   { this._openPenBonDialog("bonus", t.dataset.id); return; }
    if (act === "delete-bonus") { this._confirmDelete("bonus", t.dataset.id); return; }
    if (act === "save-bonus")   { this._doSavePenBon("bonus"); return; }
    if (act === "apply-bonus")  { this._openApplyDialog("bonus", t.dataset.id); return; }
    if (act === "do-apply-bonus") { this._doApplyPenBon("bonus", t.dataset.id, t.dataset.child); return; }

    if (act === "toggle-penbon-assigned") { this._toggleArrayField("assigned_to", t.dataset.id); return; }

    // Templates
    if (act === "tpl-add-from")     { this._activeTab = "templates"; this._templateView = "picker"; this._render(); return; }
    if (act === "tpl-select")       { this._selectTemplate(t.dataset.id); return; }
    if (act === "tpl-back")         { this._templateView = null; this._templateSelected = null; this._templateChores = []; this._render(); return; }
    if (act === "tpl-remove-chore") { this._templateChores.splice(Number(t.dataset.idx), 1); this._render(); return; }
    if (act === "tpl-toggle-expand"){ const idx = Number(t.dataset.idx); if (this._templateChores[idx]) { this._templateChores[idx]._expanded = !this._templateChores[idx]._expanded; this._render(); } return; }
    if (act === "tpl-apply")        { this._doApplyTemplate(); return; }
    if (act === "tpl-save-from")    { this._saveTemplateDialog = true; this._render(); return; }
    if (act === "tpl-save-confirm") { this._doSaveFromChores(); return; }
    if (act === "tpl-save-cancel")  { this._saveTemplateDialog = false; this._render(); return; }
    if (act === "tpl-create")       { this._openCreateTemplateDialog(); return; }
    if (act === "tpl-edit")         { this._openEditTemplateDialog(t.dataset.id); return; }
    if (act === "tpl-delete")       { this._confirmDeleteTemplate(t.dataset.id); return; }
    if (act === "tpl-save-created") { this._doSaveCreatedTemplate(); return; }
    if (act === "tpl-save-edited")  { this._doSaveEditedTemplate(); return; }
    if (act === "tpl-toggle-day")   { const idx = Number(t.dataset.idx); const day = t.dataset.day; if (this._templateChores[idx]) { const days = this._templateChores[idx].due_days || []; const pos = days.indexOf(day); if (pos >= 0) days.splice(pos, 1); else days.push(day); this._templateChores[idx].due_days = days; this._render(); } return; }
    if (act === "tpl-dialog-add-chore") { if (this._dialog?.data?.chores) { this._dialog.data.chores.push({ name: "", points: 5, time_category: "anytime", schedule_mode: "specific_days", due_days: [], requires_approval: false, assignment_mode: "everyone", daily_limit: 1, completion_sound: "coin" }); this._render(); } return; }
    if (act === "tpl-dialog-remove-chore") { if (this._dialog?.data?.chores) { this._dialog.data.chores.splice(Number(t.dataset.idx), 1); this._render(); } return; }

    // Groups
    if (act === "add-group")    { this._openGroupDialog(null); return; }
    if (act === "edit-group")   { this._openGroupDialog(t.dataset.id); return; }
    if (act === "delete-group") { this._confirmDelete("group", t.dataset.id); return; }
    if (act === "save-group")   { this._doSaveGroup(); return; }
    if (act === "toggle-group-chore") { this._toggleArrayField("chore_ids", t.dataset.id); return; }

    // Settings
    if (act === "save-settings") { this._doSaveSettings(); return; }

    // Activity / approvals
    if (act === "approve-chore")  { this._doApprove("chore", t.dataset.id); return; }
    if (act === "reject-chore")   { this._doReject("chore", t.dataset.id); return; }
    if (act === "approve-reward") { this._doApprove("reward", t.dataset.id); return; }
    if (act === "reject-reward")  { this._doReject("reward", t.dataset.id); return; }

    // Filter clear
    if (act === "clear-filter") { this._filter = ""; this._render(); return; }
  }

  _onDblClick(e) {
    const t = e.target.closest("[data-rename]");
    if (!t) return;
    this._startInlineRename(t.dataset.rename, t.dataset.id);
  }

  _onFocusIn(e) {
    if (e.target.classList?.contains("tm-ep-input")) {
      e.target.value = "";
      this._openEntityDropdown(e.target);
    }
  }

  _onInput(e) {
    const t = e.target;
    if (!t.dataset) return;
    if (t.classList?.contains("tm-ep-input")) {
      this._openEntityDropdown(t);
      return;
    }
    // Filter input
    if (t.dataset.filter === "true") {
      this._filter = t.value || "";
      // Re-render only the visible tab body — but full re-render is fine for now.
      this._render();
      // Restore focus to the filter input
      const f = this.querySelector("[data-filter='true']");
      if (f) { f.focus(); f.setSelectionRange(this._filter.length, this._filter.length); }
      return;
    }
    // Inline rename input
    if (t.dataset.field === "_inlineRename") {
      this._inlineRename.value = t.value;
      return;
    }
    // Template preview chore field edits
    const tplField = t.dataset?.tplField;
    const tplIdx = t.dataset?.tplIdx;
    if (tplField && tplIdx != null && this._templateChores[Number(tplIdx)]) {
      let value = t.value;
      if (tplField === "points" || tplField === "daily_limit") value = Math.max(0, parseInt(value) || 0);
      if (tplField === "requires_approval") value = value === "true";
      this._templateChores[Number(tplIdx)][tplField] = value;
      return;
    }
    // Template dialog chore field edits
    const dField = t.dataset?.tplDialogField;
    const dIdx = t.dataset?.tplDialogIdx;
    if (dField && dIdx != null && this._dialog?.data?.chores?.[Number(dIdx)]) {
      let value = t.value;
      if (dField === "points") value = Math.max(0, parseInt(value) || 0);
      this._dialog.data.chores[Number(dIdx)][dField] = value;
      return;
    }
    // Dialog field
    if (this._dialog && t.dataset.field) {
      const field = t.dataset.field;
      const value = (t.type === "number") ? (t.value === "" ? null : Number(t.value)) : t.value;
      const arrMatch = field.match(/^(\w+)\[(\d+)\]\.(\w+)$/);
      if (arrMatch) {
        const [, arr, idx, prop] = arrMatch;
        if (this._dialog.data[arr] && this._dialog.data[arr][Number(idx)] !== undefined) {
          this._dialog.data[arr][Number(idx)][prop] = value;
        }
      } else {
        this._dialog.data[field] = value;
      }
      return;
    }
  }

  _onChange(e) {
    const t = e.target;
    if (!t.dataset) return;
    // Template preview chore field changes (selects)
    const tplField = t.dataset?.tplField;
    const tplIdx = t.dataset?.tplIdx;
    if (tplField && tplIdx != null && this._templateChores[Number(tplIdx)]) {
      let value = t.value;
      if (tplField === "requires_approval") value = value === "true";
      this._templateChores[Number(tplIdx)][tplField] = value;
      return;
    }
    // Template dialog chore field changes (selects)
    const dField = t.dataset?.tplDialogField;
    const dIdx = t.dataset?.tplDialogIdx;
    if (dField && dIdx != null && this._dialog?.data?.chores?.[Number(dIdx)]) {
      this._dialog.data.chores[Number(dIdx)][dField] = t.value;
      return;
    }
    if (!this._dialog) return;
    if (!t.dataset.field) return;
    let value;
    if (t.type === "checkbox" || t.tagName === "HA-SWITCH") value = t.checked;
    else if (t.type === "number") value = (t.value === "" ? null : Number(t.value));
    else value = t.value;
    this._dialog.data[t.dataset.field] = value;
    if (t.dataset.rerender === "true") this._render();
  }

  _onValueChanged(e) {
    if (!this._dialog) return;
    const t = e.target;
    if (!t.dataset || !t.dataset.field) return;
    const v = e.detail && "value" in e.detail ? e.detail.value : t.value;
    this._dialog.data[t.dataset.field] = v == null ? "" : v;
  }

  _onKeyDown(e) {
    if (e.key === "Escape") {
      if (this._inlineRename) { this._inlineRename = null; this._render(); return; }
      if (this._dialog) { this._closeDialog(); return; }
    }
    if (e.key === "Enter" && this._inlineRename) {
      e.preventDefault();
      this._commitInlineRename();
    }
  }

  // ---- Drag and drop (reorder dialog) ----------------------------------
  _onDragStart(e) {
    const t = e.target.closest("[data-drag-id]");
    if (!t) return;
    this._reorderDrag = { id: t.dataset.dragId };
    t.classList.add("tm-dragging");
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", t.dataset.dragId);
  }

  _onDragOver(e) {
    const t = e.target.closest("[data-drag-id]");
    if (!t || !this._reorderDrag) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }

  _onDrop(e) {
    const t = e.target.closest("[data-drag-id]");
    if (!t || !this._reorderDrag || !this._dialog || this._dialog.kind !== "reorder") return;
    e.preventDefault();
    const fromId = this._reorderDrag.id;
    const toId   = t.dataset.dragId;
    if (fromId === toId) { this._reorderDrag = null; this._render(); return; }
    const order = [...(this._dialog.data.order || [])];
    const fromIdx = order.indexOf(fromId);
    const toIdx   = order.indexOf(toId);
    if (fromIdx < 0 || toIdx < 0) return;
    order.splice(fromIdx, 1);
    order.splice(toIdx, 0, fromId);
    this._dialog.data.order = order;
    this._reorderDrag = null;
    this._render();
  }

  _toggleArrayField(field, value) {
    if (!this._dialog || !this._dialog.data) return;
    const arr = Array.isArray(this._dialog.data[field]) ? [...this._dialog.data[field]] : [];
    const i = arr.indexOf(value);
    if (i >= 0) arr.splice(i, 1); else arr.push(value);
    this._dialog.data[field] = arr;
    const body = this.querySelector(".tm-dialog-body");
    const scrollY = body ? body.scrollTop : 0;
    this._render();
    const b = this.querySelector(".tm-dialog-body");
    if (b) b.scrollTop = scrollY;
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

  // ---- Approvals -------------------------------------------------------
  async _doApprove(kind, id) {
    const wsType = kind === "chore" ? "taskmate/approve_chore" : "taskmate/approve_reward";
    const idField = kind === "chore" ? "completion_id" : "claim_id";
    const { ok, err } = await this._callWS({ type: wsType, [idField]: id });
    if (!ok) { this._showToast("err", `Approve failed: ${err}`); return; }
    await this._fetchState();
    this._showToast("ok", "Approved");
  }

  async _doReject(kind, id) {
    const wsType = kind === "chore" ? "taskmate/reject_chore" : "taskmate/reject_reward";
    const idField = kind === "chore" ? "completion_id" : "claim_id";
    const { ok, err } = await this._callWS({ type: wsType, [idField]: id });
    if (!ok) { this._showToast("err", `Reject failed: ${err}`); return; }
    await this._fetchState();
    this._showToast("ok", "Rejected");
  }

  // ---- Children --------------------------------------------------------
  _openChildDialog(id) {
    if (id) {
      const c = (this._state.children || []).find(x => x.id === id);
      if (!c) return;
      this._openDialog({ kind: "child", mode: "edit", data: {
        id: c.id, name: c.name || "", avatar: c.avatar || "mdi:account-circle",
        availability_entity: c.availability_entity || "",
        availability_inverted: !!c.availability_inverted,
        unavailability_entity: c.unavailability_entity || "",
      } });
    } else {
      this._openDialog({ kind: "child", mode: "add", data: {
        name: "", avatar: "mdi:account-circle", availability_entity: "",
        availability_inverted: false, unavailability_entity: "",
      } });
    }
  }

  async _doSaveChild() {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", "Name is required"); return; }
    const wasAdd = this._dialog.mode === "add";
    const payload = wasAdd
      ? { type: "taskmate/add_child", name: d.name.trim(), avatar: d.avatar || "mdi:account-circle",
          availability_entity: d.availability_entity || "", availability_inverted: !!d.availability_inverted,
          unavailability_entity: d.unavailability_entity || "" }
      : { type: "taskmate/update_child", child_id: d.id, name: d.name.trim(), avatar: d.avatar || "mdi:account-circle",
          availability_entity: d.availability_entity || "", availability_inverted: !!d.availability_inverted,
          unavailability_entity: d.unavailability_entity || "" };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Child added" : "Child updated");
  }

  // ---- Chore reorder ---------------------------------------------------
  _openReorderDialog(child_id) {
    const child = (this._state.children || []).find(c => c.id === child_id);
    if (!child) return;
    const childChores = (this._state.chores || []).filter(c =>
      (c.assigned_to || []).length === 0 || (c.assigned_to || []).includes(child_id)
    );
    // Use the child's stored chore_order if present, else fall back to the chore list order.
    const existingOrder = (child.chore_order || []).filter(id => childChores.find(c => c.id === id));
    const missing = childChores.map(c => c.id).filter(id => !existingOrder.includes(id));
    const order = [...existingOrder, ...missing];
    this._openDialog({ kind: "reorder", mode: "edit", data: { child_id, order, name: child.name } });
  }

  async _doSaveChoreOrder() {
    const d = this._dialog.data;
    const { ok, err } = await this._callWS({
      type: "taskmate/set_chore_order",
      child_id: d.child_id,
      chore_order: d.order || [],
    });
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", "Order saved");
  }

  // ---- Bulk add chores -------------------------------------------------
  _openBulkAddDialog() {
    this._openDialog({ kind: "bulk-chore", mode: "add", data: {
      chore_names: "",
      points: 10,
      assigned_to: [],
      requires_approval: true,
      time_category: "anytime",
      schedule_mode: "specific_days",
      due_days: [],
      daily_limit: 1,
      completion_sound: "coin",
    } });
  }

  async _doSaveBulkChores() {
    const d = this._dialog.data;
    const names = (d.chore_names || "").split(/[\n,]/).map(s => s.trim()).filter(Boolean);
    if (names.length === 0) { this._showToast("err", "Enter at least one chore name"); return; }
    const { ok, err, res } = await this._callWS({
      type: "taskmate/add_chores_bulk",
      chore_names: names,
      points: Number(d.points) || 10,
      assigned_to: d.assigned_to || [],
      requires_approval: !!d.requires_approval,
      time_category: d.time_category || "anytime",
      schedule_mode: d.schedule_mode || "specific_days",
      due_days: d.due_days || [],
      daily_limit: Number(d.daily_limit) || 1,
      completion_sound: d.completion_sound || "coin",
    });
    if (!ok) { this._showToast("err", `Bulk add failed: ${err}`); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", `Added ${(res && res.count) || names.length} chore${((res && res.count) || names.length) === 1 ? "" : "s"}`);
  }

  // ---- Inline rename ---------------------------------------------------
  _startInlineRename(kind, id) {
    if (kind !== "chore") return;
    const c = (this._state.chores || []).find(x => x.id === id);
    if (!c) return;
    this._inlineRename = { kind: "chore", id, value: c.name };
    this._render();
    const inp = this.querySelector("[data-field='_inlineRename']");
    if (inp) { inp.focus(); inp.select(); }
  }

  async _commitInlineRename() {
    if (!this._inlineRename) return;
    const { kind, id, value } = this._inlineRename;
    const newName = (value || "").trim();
    if (!newName) { this._inlineRename = null; this._render(); return; }
    if (kind === "chore") {
      const c = (this._state.chores || []).find(x => x.id === id);
      if (c && c.name === newName) { this._inlineRename = null; this._render(); return; }
      const { ok, err } = await this._callWS({ type: "taskmate/update_chore", chore_id: id, name: newName });
      this._inlineRename = null;
      if (!ok) { this._showToast("err", `Rename failed: ${err}`); this._render(); return; }
      await this._fetchState();
      this._showToast("ok", "Renamed");
    }
  }

  // ---- Chores ----------------------------------------------------------
  _openChoreDialog(id) {
    const blank = {
      name: "", description: "", points: 10,
      assigned_to: [], requires_approval: true,
      time_category: "anytime", completion_sound: "coin", daily_limit: 1,
      claim_allowance_minutes: 0,
      schedule_mode: "specific_days",
      due_days: [], recurrence: "weekly", recurrence_day: "", recurrence_start: "",
      first_occurrence_mode: "available_immediately",
      assignment_mode: "everyone", assignment_rotation_anchor: "",
      manual_start_child_id: "",
      require_availability: false,
      visibility_entity: "", visibility_state: "on", visibility_operator: "none",
      enabled: true,
      publish_calendar_entities: [],
      bonus_subtasks: [],
    };
    if (id) {
      const c = (this._state.chores || []).find(x => x.id === id);
      if (!c) return;
      this._openDialog({ kind: "chore", mode: "edit", data: {
        ...blank, ...c,
        assigned_to: [...(c.assigned_to || [])],
        due_days: [...(c.due_days || [])],
        publish_calendar_entities: [...(c.publish_calendar_entities || [])],
        bonus_subtasks: (c.bonus_subtasks || []).map(b => ({...b})),
        visibility_operator: c.visibility_operator || "none",
        manual_start_child_id: "",
      } });
    } else {
      this._openDialog({ kind: "chore", mode: "add", data: blank });
    }
  }

  async _doSaveChore() {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", "Name is required"); return; }
    const wasAdd = this._dialog.mode === "add";
    const base = {
      name: d.name.trim(),
      description: d.description || "",
      points: Number(d.points) || 0,
      assigned_to: d.assigned_to || [],
      requires_approval: !!d.requires_approval,
      time_category: d.time_category || "anytime",
      claim_allowance_minutes: Math.max(0, Number(d.claim_allowance_minutes) || 0),
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
      visibility_operator: d.visibility_operator || "none",
      enabled: d.enabled !== false,
      publish_calendar_entities: d.publish_calendar_entities || [],
      bonus_subtasks: (d.bonus_subtasks || []).filter(b => b.name && b.name.trim()).map(b => ({
        name: b.name.trim(), points: Number(b.points) || 5,
        description: b.description || "", ...(b.id ? {id: b.id} : {}),
      })),
      task_type: d.task_type || "standard",
      timed_rate_points: Number(d.timed_rate_points) || 10,
      timed_rate_minutes: Math.max(1, Number(d.timed_rate_minutes) || 5),
      timed_max_daily_minutes: Math.max(0, Number(d.timed_max_daily_minutes) || 0),
      manual_start_child_id: d.manual_start_child_id || null,
    };
    const payload = wasAdd
      ? { type: "taskmate/add_chore", ...base }
      : { type: "taskmate/update_chore", chore_id: d.id, ...base };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Chore added" : "Chore updated");
  }

  _addBonusSubtask() {
    if (!this._dialog) return;
    const d = this._dialog.data;
    d.bonus_subtasks = d.bonus_subtasks || [];
    d.bonus_subtasks.push({ name: "", points: 5, description: "" });
    this._render();
  }

  _removeBonusSubtask(idx) {
    if (!this._dialog) return;
    const d = this._dialog.data;
    if (d.bonus_subtasks && d.bonus_subtasks[idx] !== undefined) {
      d.bonus_subtasks.splice(idx, 1);
      this._render();
    }
  }

  // ---- Rewards ---------------------------------------------------------
  _openRewardDialog(id) {
    const blank = { name: "", description: "", cost: 50, icon: "mdi:gift",
      assigned_to: [], is_jackpot: false, pool_enabled: false,
      quantity_str: "", expires_at: "" };
    if (id) {
      const r = (this._state.rewards || []).find(x => x.id === id);
      if (!r) return;
      this._openDialog({ kind: "reward", mode: "edit", data: {
        ...blank, ...r,
        assigned_to: [...(r.assigned_to || [])],
        quantity_str: r.quantity == null ? "" : String(r.quantity),
        expires_at: r.expires_at || "",
      } });
    } else {
      this._openDialog({ kind: "reward", mode: "add", data: blank });
    }
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
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Reward added" : "Reward updated");
  }

  // ---- Penalties / Bonuses ---------------------------------------------
  _openPenBonDialog(kind, id) {
    const blank = { name: "", description: "", points: 10,
      icon: kind === "penalty" ? "mdi:alert-circle-outline" : "mdi:star-circle-outline",
      assigned_to: [] };
    if (id) {
      const item = ((kind === "penalty" ? this._state.penalties : this._state.bonuses) || []).find(x => x.id === id);
      if (!item) return;
      this._openDialog({ kind, mode: "edit", data: { ...blank, ...item, assigned_to: [...(item.assigned_to || [])] } });
    } else {
      this._openDialog({ kind, mode: "add", data: blank });
    }
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
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", `${wasAdd ? "Added" : "Updated"} ${kind}`);
  }

  _openApplyDialog(kind, id) {
    const item = ((kind === "penalty" ? this._state.penalties : this._state.bonuses) || []).find(x => x.id === id);
    if (!item) return;
    this._openDialog({ kind: `apply-${kind}`, mode: "apply", data: { id, item } });
  }

  async _doApplyPenBon(kind, id, child_id) {
    const wsType = kind === "penalty" ? "taskmate/apply_penalty" : "taskmate/apply_bonus";
    const idField = `${kind}_id`;
    const { ok, err } = await this._callWS({ type: wsType, [idField]: id, child_id });
    if (!ok) { this._showToast("err", `Apply failed: ${err}`); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", kind === "penalty" ? "Penalty applied" : "Bonus applied");
  }

  // ---- Task groups -----------------------------------------------------
  _openGroupDialog(id) {
    const blank = { name: "", policy: "sticky", chore_ids: [] };
    if (id) {
      const g = (this._state.task_groups || []).find(x => x.id === id);
      if (!g) return;
      this._openDialog({ kind: "group", mode: "edit", data: { ...blank, ...g, chore_ids: [...(g.chore_ids || [])] } });
    } else {
      this._openDialog({ kind: "group", mode: "add", data: blank });
    }
  }

  async _doSaveGroup() {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", "Name is required"); return; }
    const wasAdd = this._dialog.mode === "add";
    const base = { name: d.name.trim(), policy: d.policy || "sticky", chore_ids: d.chore_ids || [] };
    const payload = wasAdd ? { type: "taskmate/add_task_group", ...base } : { type: "taskmate/update_task_group", group_id: d.id, ...base };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Group added" : "Group updated");
  }

  // ---- Settings --------------------------------------------------------
  async _doSaveSettings() {
    const root = this.querySelector(".tm-settings");
    if (!root) return;
    const fields = root.querySelectorAll("[data-setting]");
    const payload = { type: "taskmate/update_settings" };
    fields.forEach(el => {
      const name = el.dataset.setting;
      let v;
      if (el.type === "checkbox" || el.tagName === "HA-SWITCH") v = el.checked;
      else if (el.type === "number") v = el.value === "" ? undefined : Number(el.value);
      else v = el.value;
      if (v !== undefined) payload[name] = v;
    });
    root.querySelectorAll("ha-icon-picker[data-setting]").forEach(el => {
      payload[el.dataset.setting] = el.value || "";
    });
    const { ok, err, res } = await this._callWS(payload);
    if (!ok) { this._showToast("err", `Save failed: ${err}`); return; }
    await this._fetchState();
    this._showToast("ok", `Saved (${(res && res.updated || []).length} field${(res && res.updated || []).length === 1 ? "" : "s"})`);
  }

  // ---- HA picker binding -----------------------------------------------
  _bindHaPickers(syncValues = true) {
    if (!this._hass) return;
    this.querySelectorAll("ha-icon-picker").forEach(el => {
      el.hass = this._hass;
      if (syncValues) {
        const v = el.getAttribute("data-current") || "";
        if (el.value !== v) el.value = v;
      }
    });
    if (!syncValues) return;
    this.querySelectorAll("ha-textfield[data-value]").forEach(el => {
      const v = el.getAttribute("data-value") || "";
      if (el.value !== v) el.value = v;
    });
    this.querySelectorAll("ha-select[data-value]").forEach(el => {
      const v = el.getAttribute("data-value") || "";
      if (el.value !== v) el.value = v;
    });
  }

  // ---- Time helpers ----------------------------------------------------
  _timeAgo(iso) {
    if (!iso) return "—";
    const then = new Date(iso);
    if (isNaN(then)) return iso;
    const diffSec = Math.floor((Date.now() - then.getTime()) / 1000);
    if (diffSec < 60)         return "just now";
    if (diffSec < 3600)       return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400)      return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800)     return `${Math.floor(diffSec / 86400)}d ago`;
    return then.toLocaleDateString();
  }

  // ---- rendering -------------------------------------------------------
  _render() {
    this._rendered = true;
    const existingToast = this.querySelector(".tm-toast");
    this.innerHTML = `
      ${this._styles()}
      <div class="tm-shell">
        ${this._sidebar()}
        <div class="tm-main">
          ${this._topbar()}
          ${this._mobileTabs()}
          ${this._approvalBanner()}
          <div class="tm-body">
            <div class="tm-body-inner">
              ${this._renderBody()}
            </div>
          </div>
        </div>
        ${this._dialog ? this._renderDialog() : ""}
        ${this._renderSaveTemplateDialog()}
      </div>
    `;
    if (existingToast) this.appendChild(existingToast);
    this._bindHaPickers();
  }

  _sidebarGroups() {
    const counts = this._state ? {
      children:  (this._state.children || []).length,
      activity:  (this._state.pending_completions || []).length + (this._state.pending_reward_claims || []).length,
      chores:    (this._state.chores || []).length,
      rewards:   (this._state.rewards || []).length,
      penalties: (this._state.penalties || []).length,
      bonuses:   (this._state.bonuses || []).length,
      groups:    (this._state.task_groups || []).length,
      templates: (this._state.templates || []).length,
    } : {};
    return [
      { head: "Today", items: [
        { id: "activity", label: "Activity", icon: "mdi:pulse" },
      ]},
      { head: "Manage", items: [
        { id: "children",  label: "Children",  icon: "mdi:account-multiple" },
        { id: "chores",    label: "Chores",    icon: "mdi:check-circle-outline" },
        { id: "rewards",   label: "Rewards",   icon: "mdi:gift-outline" },
        { id: "penalties", label: "Penalties", icon: "mdi:alert-circle-outline" },
        { id: "bonuses",   label: "Bonuses",   icon: "mdi:flash-outline" },
        { id: "groups",    label: "Groups",    icon: "mdi:layers-outline" },
        { id: "templates", label: "Templates", icon: "mdi:clipboard-list-outline" },
      ]},
      { head: "System", items: [
        { id: "settings", label: "Settings", icon: "mdi:cog-outline" },
      ]},
    ].map(g => ({
      ...g,
      items: g.items.map(it => ({ ...it, count: counts[it.id] }))
    }));
  }

  _sidebar() {
    const groups = this._sidebarGroups();
    return `
      <aside class="tm-sidebar">
        <div class="tm-brand">
          <div class="tm-brand-mark"><ha-icon icon="mdi:checkbox-marked-circle-plus-outline"></ha-icon></div>
          <div class="tm-brand-text">
            TaskMate
            <small>v${PANEL_VERSION}</small>
          </div>
        </div>
        <nav class="tm-nav">
          ${groups.map(g => `
            <div class="tm-nav-group">
              <div class="tm-nav-head">${this._esc(g.head)}</div>
              ${g.items.map(it => {
                const active = it.id === this._activeTab;
                const urgent = it.id === "activity" && it.count > 0;
                const showCount = it.count != null && it.count > 0;
                return `
                  <button class="tm-nav-item ${active ? "tm-nav-active" : ""}" data-act="tab" data-tab="${it.id}">
                    <span class="tm-nav-icon"><ha-icon icon="${it.icon}"></ha-icon></span>
                    <span class="tm-nav-label">${this._esc(it.label)}</span>
                    ${showCount ? `<span class="tm-nav-badge ${urgent ? "tm-nav-badge-urgent" : ""}">${it.count}</span>` : ""}
                  </button>
                `;
              }).join("")}
            </div>
          `).join("")}
        </nav>
      </aside>
    `;
  }

  _topbar() {
    const crumb = this._sidebarGroups()
      .flatMap(g => g.items)
      .find(i => i.id === this._activeTab);
    const crumbLabel = crumb ? crumb.label : "";
    const pendingCount = this._state
      ? (this._state.pending_completions || []).length + (this._state.pending_reward_claims || []).length
      : 0;
    return `
      <div class="tm-topbar">
        <div class="tm-crumbs">
          <span class="tm-crumbs-root">TaskMate</span>
          <span class="tm-crumbs-sep">/</span>
          <strong>${this._esc(crumbLabel)}</strong>
        </div>
        ${pendingCount > 0 && this._activeTab !== "activity" ? `
          <button class="tm-approval-pill" data-act="switch-to-activity" title="${pendingCount} pending — click to review">
            <span class="tm-approval-dot"></span>
            ${pendingCount} pending
          </button>
        ` : ""}
      </div>
    `;
  }

  _mobileTabs() {
    const groups = this._sidebarGroups();
    return `
      <nav class="tm-mobile-tabs">
        ${groups.flatMap(g => g.items).map(it => {
          const active = it.id === this._activeTab;
          const urgent = it.id === "activity" && it.count > 0;
          const showCount = it.count != null && it.count > 0;
          return `
            <button class="tm-mtab ${active ? "tm-mtab-active" : ""}" data-act="tab" data-tab="${it.id}">
              ${this._esc(it.label)}${showCount ? `<span class="tm-mtab-pill ${urgent ? "tm-mtab-pill-urgent" : ""}">${it.count}</span>` : ""}
            </button>
          `;
        }).join("")}
      </nav>
    `;
  }

  _approvalBanner() {
    if (!this._state) return "";
    if (this._activeTab === "activity") return "";
    const completionsP = (this._state.pending_completions || []).length;
    const rewardsP     = (this._state.pending_reward_claims || []).length;
    const total = completionsP + rewardsP;
    if (total === 0) return "";
    const parts = [];
    if (completionsP) parts.push(`<strong>${completionsP}</strong> chore${completionsP === 1 ? "" : "s"}`);
    if (rewardsP)     parts.push(`<strong>${rewardsP}</strong> reward claim${rewardsP === 1 ? "" : "s"}`);
    return `
      <div class="tm-approval-banner">
        <ha-icon icon="mdi:bell-ring-outline"></ha-icon>
        <span>Awaiting your approval — ${parts.join(" · ")}</span>
        <button class="tm-btn tm-btn-raised tm-btn-sm" data-act="switch-to-activity">Review</button>
      </div>
    `;
  }

  _renderBody() {
    if (this._loading && !this._state) return `<div class="tm-card tm-loading">Loading…</div>`;
    if (this._error) return `
      <div class="tm-card tm-card-error">
        <h2>Failed to load state</h2>
        <p>${this._esc(this._error)}</p>
        <button class="tm-btn tm-btn-raised" data-act="retry">Retry</button>
      </div>`;
    if (!this._state) return `<div class="tm-card">No state yet.</div>`;

    switch (this._activeTab) {
      case "children":  return this._renderChildrenTab();
      case "activity":  return this._renderActivityTab();
      case "chores":    return this._renderChoresTab();
      case "rewards":   return this._renderRewardsTab();
      case "penalties": return this._renderPenBonTab("penalty");
      case "bonuses":   return this._renderPenBonTab("bonus");
      case "groups":    return this._renderGroupsTab();
      case "templates": return this._renderTemplatesTab();
      case "settings":  return this._renderSettingsTab();
      default:          return `<div class="tm-card">Unknown tab</div>`;
    }
  }

  _searchBox(placeholder) {
    return `
      <div class="tm-search-wrap">
        <ha-icon icon="mdi:magnify" class="tm-search-icon"></ha-icon>
        <input class="tm-search" placeholder="${this._esc(placeholder)}" data-filter="true" value="${this._esc(this._filter)}">
        ${this._filter ? `<button class="tm-search-clear" data-act="clear-filter" title="Clear">✕</button>` : ""}
      </div>
    `;
  }

  _filterByName(items) {
    if (!this._filter) return items;
    const q = this._filter.toLowerCase();
    return items.filter(it => (it.name || "").toLowerCase().includes(q));
  }

  // -- Children tab ------------------------------------------------------
  _renderChildrenTab() {
    const all = this._state.children || [];
    const children = this._filterByName(all);
    const pointsName = this._state.settings.points_name || "points";
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">Children <span class="tm-toolbar-count">${all.length}</span></h2>
        ${all.length > 0 ? this._searchBox("Search children…") : ""}
        <button class="tm-btn tm-btn-raised" data-act="add-child">＋ Add child</button>
      </div>
      ${all.length === 0 ? this._emptyState("👨‍👩‍👧‍👦", "No children yet", "Add your first child to get started.", "add-child", "+ Add child") :
        children.length === 0 ? `<div class="tm-card tm-empty"><p>No children match "<strong>${this._esc(this._filter)}</strong>".</p></div>` : `
        <div class="tm-grid">
          ${children.map(c => this._renderChildCard(c, pointsName)).join("")}
          <button class="tm-add-tile" data-act="add-child"><span class="tm-add-plus">＋</span>Add child</button>
        </div>
      `}
    `;
  }

  _renderChildCard(child, pointsName) {
    return `
      <article class="tm-card tm-child-card">
        <div class="tm-child-head">
          <div class="tm-avatar">${this._mdi(child.avatar)}</div>
          <div class="tm-child-name">
            <h3>${this._esc(child.name || "(unnamed)")}</h3>
            <div class="tm-meta">${child.availability_entity ? `<code>${this._esc(child.availability_entity)}</code>${child.availability_inverted ? ` <em>(inverted)</em>` : ""}` : `No availability sensor`}${child.unavailability_entity ? ` · Busy: <code>${this._esc(child.unavailability_entity)}</code>` : ""}</div>
          </div>
        </div>
        <div class="tm-stats-row">
          <div class="tm-stat tm-stat-highlight"><div class="tm-stat-value">${this._fmtNum(child.points || 0)}</div><div class="tm-stat-label">${this._esc(pointsName)}</div></div>
          <div class="tm-stat"><div class="tm-stat-value">${this._fmtNum(child.total_points_earned || 0)}</div><div class="tm-stat-label">Earned</div></div>
          <div class="tm-stat"><div class="tm-stat-value">${this._fmtNum(child.total_chores_completed || 0)}</div><div class="tm-stat-label">Done</div></div>
        </div>
        <div class="tm-card-foot">
          <button class="tm-btn tm-btn-sm" data-act="edit-child" data-id="${this._esc(child.id)}">Edit</button>
          <button class="tm-btn tm-btn-sm" data-act="reorder-chores-for-child" data-id="${this._esc(child.id)}" title="Reorder this child's chores">⇅ Chore Order</button>
          <button class="tm-btn tm-btn-sm tm-btn-danger" data-act="delete-child" data-id="${this._esc(child.id)}">Delete</button>
        </div>
      </article>
    `;
  }

  // -- Activity tab ------------------------------------------------------
  _renderActivityTab() {
    const pendingCompletions = this._state.pending_completions || [];
    const pendingClaims      = this._state.pending_reward_claims || [];
    const transactions       = this._state.points_transactions || [];
    const completions        = this._state.completions || [];
    const claims             = this._state.reward_claims || [];

    const childById = Object.fromEntries((this._state.children || []).map(c => [c.id, c]));
    const choreById = Object.fromEntries((this._state.chores || []).map(c => [c.id, c]));
    const rewardById = Object.fromEntries((this._state.rewards || []).map(r => [r.id, r]));

    // Recent activity feed: merge approved completions + claims + transactions
    const events = [];
    completions.filter(c => c.approved).forEach(c => events.push({
      ts: c.approved_at || c.completed_at, kind: "completion",
      child: (childById[c.child_id] || {}).name || "?",
      label: `Completed: ${(choreById[c.chore_id] || {}).name || "(deleted chore)"}`,
      points: c.points_awarded,
    }));
    claims.filter(c => c.approved).forEach(c => events.push({
      ts: c.approved_at || c.claimed_at, kind: "claim",
      child: (childById[c.child_id] || {}).name || "?",
      label: `Claimed: ${(rewardById[c.reward_id] || {}).name || "(deleted reward)"}`,
      points: -((rewardById[c.reward_id] || {}).cost || 0),
    }));
    transactions.forEach(t => events.push({
      ts: t.created_at, kind: "manual",
      child: (childById[t.child_id] || {}).name || "?",
      label: t.reason || (t.points >= 0 ? "Manual addition" : "Manual deduction"),
      points: t.points,
    }));
    events.sort((a, b) => (b.ts || "").localeCompare(a.ts || ""));
    const recent = events.slice(0, 30);

    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">Activity</h2>
      </div>

      <!-- Pending approvals -->
      <div class="tm-card">
        <h3 class="tm-section-title">Pending approvals
          ${(pendingCompletions.length + pendingClaims.length) > 0
            ? `<span class="tm-pill tm-pill-warn">${pendingCompletions.length + pendingClaims.length}</span>`
            : `<span class="tm-pill tm-pill-success">All clear</span>`}
        </h3>
        ${pendingCompletions.length === 0 && pendingClaims.length === 0 ? `
          <p class="tm-meta">No items waiting for review.</p>
        ` : `
          <div class="tm-approval-list">
            ${pendingCompletions.map(c => {
              const chore = choreById[c.chore_id];
              const child = childById[c.child_id];
              let choreName = (chore && chore.name) || "(deleted chore)";
              let chorePoints = chore ? chore.points : 0;
              if (c.bonus_subtask_id && chore) {
                const sub = (chore.bonus_subtasks || []).find(b => b.id === c.bonus_subtask_id);
                if (sub) { choreName = `${chore.name} › ${sub.name}`; chorePoints = sub.points; }
              }
              return `
                <div class="tm-approval-item">
                  <div class="tm-approval-icon"><ha-icon icon="${c.bonus_subtask_id ? 'mdi:star-plus' : 'mdi:checkbox-marked-circle-outline'}"></ha-icon></div>
                  <div class="tm-approval-body">
                    <div class="tm-approval-line"><strong>${this._esc((child && child.name) || "?")}</strong> completed <strong>${this._esc(choreName)}</strong></div>
                    <div class="tm-meta">${this._timeAgo(c.completed_at)} · ${chorePoints} points</div>
                  </div>
                  <div class="tm-approval-actions">
                    <button class="tm-btn tm-btn-sm" data-act="reject-chore" data-id="${this._esc(c.id)}">Reject</button>
                    <button class="tm-btn tm-btn-raised tm-btn-sm" data-act="approve-chore" data-id="${this._esc(c.id)}">Approve</button>
                  </div>
                </div>
              `;
            }).join("")}
            ${pendingClaims.map(c => {
              const reward = rewardById[c.reward_id];
              const child = childById[c.child_id];
              return `
                <div class="tm-approval-item">
                  <div class="tm-approval-icon"><ha-icon icon="mdi:gift-outline"></ha-icon></div>
                  <div class="tm-approval-body">
                    <div class="tm-approval-line"><strong>${this._esc((child && child.name) || "?")}</strong> claimed reward <strong>${this._esc((reward && reward.name) || "(deleted reward)")}</strong></div>
                    <div class="tm-meta">${this._timeAgo(c.claimed_at)}${reward ? ` · ${reward.cost} points` : ""}</div>
                  </div>
                  <div class="tm-approval-actions">
                    <button class="tm-btn tm-btn-sm" data-act="reject-reward" data-id="${this._esc(c.id)}">Reject</button>
                    <button class="tm-btn tm-btn-raised tm-btn-sm" data-act="approve-reward" data-id="${this._esc(c.id)}">Approve</button>
                  </div>
                </div>
              `;
            }).join("")}
          </div>
        `}
      </div>

      <!-- Recent activity feed -->
      <div class="tm-card">
        <h3 class="tm-section-title">Recent activity</h3>
        ${recent.length === 0 ? `<p class="tm-meta">Nothing here yet — activity will appear as chores are completed and rewards claimed.</p>` : `
          <div class="tm-timeline">
            ${recent.map(ev => `
              <div class="tm-timeline-row">
                <div class="tm-timeline-time">${this._esc(this._timeAgo(ev.ts))}</div>
                <div class="tm-timeline-icon tm-timeline-${ev.kind}"><ha-icon icon="${ev.kind === 'completion' ? 'mdi:check-circle' : ev.kind === 'claim' ? 'mdi:gift' : ev.points >= 0 ? 'mdi:plus-circle' : 'mdi:minus-circle'}"></ha-icon></div>
                <div class="tm-timeline-body">
                  <div><strong>${this._esc(ev.child)}</strong> · ${this._esc(ev.label)}</div>
                </div>
                <div class="tm-timeline-points ${ev.points >= 0 ? 'tm-pos' : 'tm-neg'} tm-numeric">${ev.points >= 0 ? '+' : ''}${ev.points || 0}</div>
              </div>
            `).join("")}
          </div>
        `}
      </div>

      <!-- Audit log -->
      <div class="tm-card">
        <h3 class="tm-section-title">Audit log
          <span class="tm-pill">${transactions.length} transaction${transactions.length === 1 ? "" : "s"}</span>
        </h3>
        ${transactions.length === 0 ? `<p class="tm-meta">No points transactions yet.</p>` : `
          <div class="tm-table-wrap">
            <table class="tm-table">
              <thead><tr><th>When</th><th>Child</th><th>Points</th><th>Reason</th></tr></thead>
              <tbody>
                ${[...transactions].reverse().map(t => {
                  const child = childById[t.child_id];
                  return `
                    <tr class="tm-row">
                      <td class="tm-meta">${this._esc(this._timeAgo(t.created_at))}</td>
                      <td>${this._esc((child && child.name) || "?")}</td>
                      <td><strong class="tm-numeric ${t.points >= 0 ? 'tm-pos' : 'tm-neg'}">${t.points >= 0 ? '+' : ''}${t.points}</strong></td>
                      <td>${this._esc(t.reason || "—")}</td>
                    </tr>
                  `;
                }).join("")}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  }

  // -- Chores tab --------------------------------------------------------
  _renderChoresTab() {
    const all = this._state.chores || [];
    const chores = this._filterByName(all);
    const childById = Object.fromEntries((this._state.children || []).map(c => [c.id, c]));
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">Chores <span class="tm-toolbar-count">${all.length}</span></h2>
        ${all.length > 0 ? this._searchBox("Filter chores…") : ""}
        <button class="tm-btn" data-act="bulk-add-chore">＋＋ Bulk add</button>
        <button class="tm-btn" data-act="tpl-add-from">📋 From template</button>
        <button class="tm-btn" data-act="tpl-save-from">💾 Save as template</button>
        <button class="tm-btn tm-btn-raised" data-act="add-chore">＋ Add chore</button>
      </div>
      ${all.length === 0 ? this._emptyState("📋", "No chores yet", "Add a chore — it'll show on the assigned children's cards.", "add-chore", "+ Add chore") :
        chores.length === 0 ? `<div class="tm-card tm-empty"><p>No chores match "<strong>${this._esc(this._filter)}</strong>".</p></div>` : `
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
        <p class="tm-meta tm-table-hint">Tip: double-click a chore name to rename it inline.</p>
      `}
    `;
  }

  _renderChoreRow(c, childById) {
    const renaming = this._inlineRename && this._inlineRename.kind === "chore" && this._inlineRename.id === c.id;
    const assignedNames = (c.assigned_to || []).length === 0
      ? `<span class="tm-text-muted">All children</span>`
      : this._esc((c.assigned_to || []).map(id => (childById[id] && childById[id].name) || "?").join(", "));
    const schedLabel = c.schedule_mode === "recurring"
      ? this._labelOf(RECURRENCES, c.recurrence) + (c.recurrence_day && c.recurrence_day !== "any_day" ? ` · ${c.recurrence_day}` : "")
      : c.schedule_mode === "one_shot"
      ? "One-shot"
      : ((c.due_days || []).length === 0 ? "Daily" : (c.due_days || []).map(d => d.slice(0, 3)).join(" · "));
    const schedClass = c.schedule_mode === "recurring" ? "tm-pill-accent" : c.schedule_mode === "one_shot" ? "tm-pill-warn" : "tm-pill-success";
    const modeBadge = c.assignment_mode && c.assignment_mode !== "everyone"
      ? `<span class="tm-pill tm-pill-${c.assignment_mode}">${c.assignment_mode}</span>` : "";
    const nameCell = renaming
      ? `<input class="tm-inline-input" type="text" data-field="_inlineRename" value="${this._esc(this._inlineRename.value)}" autofocus>
         <button class="tm-icon-btn" data-act="rename-chore-commit" title="Save">✓</button>
         <button class="tm-icon-btn" data-act="rename-chore-cancel" title="Cancel">✕</button>`
      : `<strong data-rename="chore" data-id="${this._esc(c.id)}" title="Double-click to rename">${this._esc(c.name)}</strong>${c.enabled === false ? ` <span class="tm-pill">disabled</span>` : ""}`;
    return `
      <tr class="tm-row ${c.enabled === false ? "tm-row-disabled" : ""}">
        <td>${nameCell}</td>
        <td><strong class="tm-numeric">${c.points}</strong></td>
        <td>${assignedNames} ${modeBadge}</td>
        <td><span class="tm-pill ${schedClass} tm-pill-dot">${this._esc(schedLabel)}</span></td>
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
    const all = this._state.rewards || [];
    const rewards = this._filterByName(all);
    const pointsName = this._state.settings.points_name || "points";
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">Rewards <span class="tm-toolbar-count">${all.length}</span></h2>
        ${all.length > 0 ? this._searchBox("Search rewards…") : ""}
        <button class="tm-btn tm-btn-raised" data-act="add-reward">＋ Add reward</button>
      </div>
      ${all.length === 0 ? this._emptyState("🎁", "No rewards yet", `Add a reward children can spend their ${this._esc(pointsName.toLowerCase())} on.`, "add-reward", "+ Add reward") :
        rewards.length === 0 ? `<div class="tm-card tm-empty"><p>No rewards match "<strong>${this._esc(this._filter)}</strong>".</p></div>` : `
        <div class="tm-grid">
          ${rewards.map(r => this._renderRewardCard(r, pointsName)).join("")}
          <button class="tm-add-tile" data-act="add-reward"><span class="tm-add-plus">＋</span>Add reward</button>
        </div>
      `}
    `;
  }

  _renderRewardCard(r, pointsName) {
    const totalPooled = (this._state.pool_allocations || []).filter(a => a.reward_id === r.id).reduce((s, a) => s + (a.allocated_points || 0), 0);
    const showProgress = r.pool_enabled && r.cost > 0;
    const pct = showProgress ? Math.min(100, Math.round(totalPooled / r.cost * 100)) : 0;
    return `
      <article class="tm-card tm-reward-card">
        <div class="tm-child-head">
          <div class="tm-avatar tm-avatar-reward">${this._mdi(r.icon || "mdi:gift")}</div>
          <div class="tm-child-name">
            <h3>${this._esc(r.name)} ${r.is_jackpot ? `<span class="tm-pill tm-pill-jackpot">🏆 Jackpot</span>` : ""} ${r.pool_enabled ? `<span class="tm-pill tm-pill-pool">Pool</span>` : ""}</h3>
            <div class="tm-meta">${this._esc(r.description || "")}</div>
          </div>
        </div>
        <div class="tm-stats-row" style="grid-template-columns: 1fr 1fr ${r.expires_at ? "1fr" : ""};">
          <div class="tm-stat"><div class="tm-stat-value tm-numeric tm-cost">${this._fmtNum(r.cost)}</div><div class="tm-stat-label">${this._esc(pointsName)} cost</div></div>
          ${r.quantity != null ? `<div class="tm-stat"><div class="tm-stat-value tm-numeric">${r.quantity}</div><div class="tm-stat-label">Remaining</div></div>` : `<div class="tm-stat"><div class="tm-stat-value">∞</div><div class="tm-stat-label">Unlimited</div></div>`}
          ${r.expires_at ? `<div class="tm-stat"><div class="tm-stat-value" style="font-size: 14px;">${this._esc(r.expires_at)}</div><div class="tm-stat-label">Expires</div></div>` : ""}
        </div>
        ${showProgress ? `
          <div class="tm-progress"><span style="width:${pct}%"></span></div>
          <div class="tm-progress-text"><span><strong>${this._fmtNum(totalPooled)}</strong> / ${this._fmtNum(r.cost)}</span><span>${pct}%</span></div>
        ` : ""}
        <div class="tm-card-foot">
          <button class="tm-btn tm-btn-sm" data-act="edit-reward" data-id="${this._esc(r.id)}">Edit</button>
          <button class="tm-btn tm-btn-sm tm-btn-danger" data-act="delete-reward" data-id="${this._esc(r.id)}">Delete</button>
        </div>
      </article>
    `;
  }

  // -- Penalties / Bonuses tab -------------------------------------------
  _renderPenBonTab(kind) {
    const allItems = (kind === "penalty" ? this._state.penalties : this._state.bonuses) || [];
    const items = this._filterByName(allItems);
    const childById = Object.fromEntries((this._state.children || []).map(c => [c.id, c]));
    const labels = kind === "penalty" ? { plural: "Penalties", add: "+ Add penalty", icon: "⚠️" } : { plural: "Bonuses", add: "+ Add bonus", icon: "⭐" };
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${labels.plural} <span class="tm-toolbar-count">${allItems.length}</span></h2>
        ${allItems.length > 0 ? this._searchBox(`Search ${labels.plural.toLowerCase()}…`) : ""}
        <button class="tm-btn tm-btn-raised" data-act="add-${kind}">＋ Add ${kind}</button>
      </div>
      ${allItems.length === 0 ? this._emptyState(labels.icon, `No ${labels.plural.toLowerCase()} yet`, kind === "penalty" ? "Add a penalty to deduct points for misbehaviour." : "Add a bonus to award points for going above and beyond.", `add-${kind}`, labels.add) :
        items.length === 0 ? `<div class="tm-card tm-empty"><p>No ${labels.plural.toLowerCase()} match "<strong>${this._esc(this._filter)}</strong>".</p></div>` : `
        <div class="tm-table-wrap">
          <table class="tm-table">
            <thead><tr><th>Name</th><th>Points</th><th>Assigned</th><th></th></tr></thead>
            <tbody>
              ${items.map(item => {
                const assignedNames = (item.assigned_to || []).length === 0
                  ? `<span class="tm-text-muted">All children</span>`
                  : this._esc((item.assigned_to || []).map(id => (childById[id] && childById[id].name) || "?").join(", "));
                return `
                  <tr class="tm-row">
                    <td><span class="tm-row-icon">${this._mdi(item.icon)}</span><strong>${this._esc(item.name)}</strong>${item.description ? `<div class="tm-meta">${this._esc(item.description)}</div>` : ""}</td>
                    <td><strong class="tm-numeric ${kind === "penalty" ? "tm-neg" : "tm-pos"}">${kind === "penalty" ? "−" : "+"}${item.points}</strong></td>
                    <td>${assignedNames}</td>
                    <td class="tm-row-actions">
                      <button class="tm-btn tm-btn-sm" data-act="apply-${kind}" data-id="${this._esc(item.id)}">Apply…</button>
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
    const all = this._state.task_groups || [];
    const groups = this._filterByName(all);
    const choreById = Object.fromEntries((this._state.chores || []).map(c => [c.id, c]));
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">Task groups <span class="tm-toolbar-count">${all.length}</span></h2>
        ${all.length > 0 ? this._searchBox("Search groups…") : ""}
        <button class="tm-btn tm-btn-raised" data-act="add-group">＋ Add group</button>
      </div>
      ${all.length === 0 ? this._emptyState("🔗", "No task groups yet", "Create a group to make chores rotate together (e.g. all kitchen chores stay with one child each day).", "add-group", "+ Add group") :
        groups.length === 0 ? `<div class="tm-card tm-empty"><p>No groups match "<strong>${this._esc(this._filter)}</strong>".</p></div>` : `
        <div class="tm-grid">
          ${groups.map(g => `
            <article class="tm-card">
              <div class="tm-child-head">
                <div class="tm-avatar"><ha-icon icon="${g.policy === 'sticky' ? 'mdi:link-variant' : 'mdi:arrow-split-horizontal'}"></ha-icon></div>
                <div class="tm-child-name">
                  <h3>${this._esc(g.name)}</h3>
                  <div class="tm-meta"><span class="tm-pill tm-pill-${g.policy}">${g.policy}</span> · ${(g.chore_ids || []).length} chore${(g.chore_ids || []).length === 1 ? "" : "s"}</div>
                </div>
              </div>
              <ul class="tm-group-list">
                ${(g.chore_ids || []).map(id => `<li>${this._esc((choreById[id] && choreById[id].name) || `(missing chore ${id})`)}</li>`).join("")}
              </ul>
              <div class="tm-card-foot">
                <button class="tm-btn tm-btn-sm" data-act="edit-group" data-id="${this._esc(g.id)}">Edit</button>
                <button class="tm-btn tm-btn-sm tm-btn-danger" data-act="delete-group" data-id="${this._esc(g.id)}">Delete</button>
              </div>
            </article>
          `).join("")}
          <button class="tm-add-tile" data-act="add-group"><span class="tm-add-plus">＋</span>Add group</button>
        </div>
      `}
    `;
  }

  // -- Templates tab ---------------------------------------------------------
  _renderTemplatesTab() {
    if (this._templateView === "picker") return this._renderTemplatePicker();
    if (this._templateView === "preview") return this._renderTemplatePreview();
    return this._renderTemplateManagement();
  }

  _renderTemplateManagement() {
    const templates = this._state.templates || [];
    const custom = templates.filter(t => !t.builtin);
    const builtin = templates.filter(t => t.builtin);
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">Templates <span class="tm-toolbar-count">${templates.length}</span></h2>
        <span style="flex:1"></span>
        <button class="tm-btn tm-btn-raised" data-act="tpl-create">＋ Create template</button>
      </div>
      ${custom.length > 0 ? `
        <div class="tm-section-divider">Custom templates</div>
        ${custom.map(t => this._renderManageTemplateCard(t, false)).join("")}
      ` : ""}
      <div class="tm-section-divider">${custom.length > 0 ? "Built-in templates" : "Built-in template packs"}</div>
      ${builtin.map(t => this._renderManageTemplateCard(t, true)).join("")}
    `;
  }

  _renderManageTemplateCard(tpl, locked) {
    const count = (tpl.chores || []).length;
    const pts = (tpl.chores || []).reduce((s, c) => s + (c.points || 0), 0);
    return `
      <div class="tm-manage-tpl ${locked ? "tm-manage-tpl-locked" : ""}">
        <div class="tm-tpl-icon"><ha-icon icon="${this._esc(tpl.icon || "mdi:clipboard-list")}"></ha-icon></div>
        <div class="tm-manage-tpl-info">
          <div class="tm-manage-tpl-name">${this._esc(tpl.name)}${locked ? ' <span class="tm-text-vfaint" style="font-size:12px">🔒</span>' : ""}</div>
          <div class="tm-meta">${count} chore${count !== 1 ? "s" : ""} · ${pts} pts total</div>
        </div>
        <div class="tm-row-actions">
          ${locked ? "" : `<button class="tm-btn tm-btn-sm" data-act="tpl-edit" data-id="${this._esc(tpl.id)}">Edit</button>`}
          ${locked ? "" : `<button class="tm-btn tm-btn-sm tm-btn-danger" data-act="tpl-delete" data-id="${this._esc(tpl.id)}">Delete</button>`}
        </div>
      </div>
    `;
  }

  _renderTemplatePicker() {
    const templates = this._state.templates || [];
    const builtin = templates.filter(t => t.builtin);
    const custom = templates.filter(t => !t.builtin);
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">Add from Template</h2>
        <span style="flex:1"></span>
        <button class="tm-btn" data-act="tpl-back">Cancel</button>
      </div>
      <div class="tm-section-divider">Built-in packs</div>
      <div class="tm-grid">
        ${builtin.map(t => this._renderTemplatePickerCard(t)).join("")}
      </div>
      ${custom.length > 0 ? `
        <div class="tm-section-divider">Custom packs</div>
        <div class="tm-grid">
          ${custom.map(t => this._renderTemplatePickerCard(t)).join("")}
        </div>
      ` : ""}
    `;
  }

  _renderTemplatePickerCard(tpl) {
    const count = (tpl.chores || []).length;
    const pts = (tpl.chores || []).reduce((s, c) => s + (c.points || 0), 0);
    return `
      <div class="tm-card tm-tpl-picker-card" data-act="tpl-select" data-id="${this._esc(tpl.id)}" style="margin-bottom:0">
        <div class="tm-tpl-picker-head">
          <div class="tm-tpl-icon"><ha-icon icon="${this._esc(tpl.icon || "mdi:clipboard-list")}"></ha-icon></div>
          <div style="flex:1">
            <div class="tm-tpl-picker-name">${this._esc(tpl.name)}</div>
            <div class="tm-meta">${count} chore${count !== 1 ? "s" : ""} · ${pts} pts total</div>
          </div>
          <span class="tm-pill ${tpl.builtin ? "tm-pill-accent" : "tm-pill-success"}">${tpl.builtin ? "Built-in" : "Custom"}</span>
        </div>
        <div class="tm-tpl-chore-pills">
          ${(tpl.chores || []).map(c => `<span class="tm-tpl-chore-pill">${this._esc(c.name)}</span>`).join("")}
        </div>
      </div>
    `;
  }

  _renderTemplatePreview() {
    const tpl = this._templateSelected;
    if (!tpl) return "";
    const chores = this._templateChores;
    const totalPts = chores.reduce((s, c) => s + (c.points || 0), 0);
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${this._esc(tpl.name)}</h2>
        <span class="tm-pill ${tpl.builtin ? "tm-pill-accent" : "tm-pill-success"}" style="margin-left:8px">${tpl.builtin ? "Built-in" : "Custom"}</span>
        <span style="flex:1"></span>
        <button class="tm-btn" data-act="tpl-back">← Back</button>
      </div>
      <p class="tm-meta" style="margin-bottom:16px">Review and customise each chore before creating. Expand to edit all fields, or remove with ✕.</p>
      ${chores.map((c, i) => this._renderTemplateChoreCard(c, i)).join("")}
      ${chores.length > 0 ? `
        <div class="tm-tpl-confirm-bar">
          <div><strong>${chores.length} chore${chores.length !== 1 ? "s" : ""}</strong> will be created · ${totalPts} pts total</div>
          <button class="tm-btn tm-btn-raised" data-act="tpl-apply">Create ${chores.length} chore${chores.length !== 1 ? "s" : ""}</button>
        </div>
      ` : `<div class="tm-card tm-empty"><p>All chores removed — go back and pick a different template.</p></div>`}
    `;
  }

  _renderTemplateChoreCard(chore, idx) {
    const expanded = chore._expanded;
    const schedLabel = (chore.due_days || []).length === 0 ? "Daily" : (chore.due_days || []).map(d => d.slice(0, 3)).join(", ");
    return `
      <div class="tm-tpl-preview-card">
        <div class="tm-tpl-preview-header" data-act="tpl-toggle-expand" data-idx="${idx}">
          <span class="tm-tpl-expand ${expanded ? "open" : ""}">▶</span>
          <span class="tm-tpl-preview-name">${this._esc(chore.name)}</span>
          <span class="tm-tpl-preview-summary">
            <span>${chore.points || 0} pt${(chore.points || 0) !== 1 ? "s" : ""}</span>
            <span>${schedLabel}</span>
            <span>${this._esc(chore.time_category || "anytime")}</span>
          </span>
          <button class="tm-tpl-remove" data-act="tpl-remove-chore" data-idx="${idx}" title="Remove from batch">✕</button>
        </div>
        ${expanded ? `
          <div class="tm-tpl-preview-body">
            <div class="tm-field-row">
              <div class="tm-field"><label>Name</label><input type="text" data-tpl-field="name" data-tpl-idx="${idx}" value="${this._esc(chore.name)}"></div>
              <div class="tm-field"><label>Points</label><input type="number" data-tpl-field="points" data-tpl-idx="${idx}" value="${chore.points || 0}" min="0"></div>
            </div>
            <div class="tm-field-row">
              <div class="tm-field"><label>Time category</label>
                <select data-tpl-field="time_category" data-tpl-idx="${idx}">
                  ${TIME_CATEGORIES.map(t => `<option value="${t.v}" ${chore.time_category === t.v ? "selected" : ""}>${t.l}</option>`).join("")}
                </select>
              </div>
              <div class="tm-field"><label>Assignment mode</label>
                <select data-tpl-field="assignment_mode" data-tpl-idx="${idx}">
                  ${ASSIGNMENT_MODES.map(m => `<option value="${m.v}" ${chore.assignment_mode === m.v ? "selected" : ""}>${m.l.split(" — ")[0]}</option>`).join("")}
                </select>
              </div>
            </div>
            <div class="tm-field" style="margin-bottom:12px"><label>Schedule (days)</label>
              <div class="tm-day-pills">
                ${DAYS.map(d => `<span class="tm-day-pill ${(chore.due_days || []).includes(d.v) ? "active" : ""}" data-act="tpl-toggle-day" data-idx="${idx}" data-day="${d.v}">${d.l}</span>`).join("")}
              </div>
            </div>
            <div class="tm-field-row">
              <div class="tm-field"><label>Requires approval</label>
                <select data-tpl-field="requires_approval" data-tpl-idx="${idx}">
                  <option value="false" ${!chore.requires_approval ? "selected" : ""}>No</option>
                  <option value="true" ${chore.requires_approval ? "selected" : ""}>Yes</option>
                </select>
              </div>
              <div class="tm-field"><label>Daily limit</label>
                <input type="number" data-tpl-field="daily_limit" data-tpl-idx="${idx}" value="${chore.daily_limit || 1}" min="1">
              </div>
            </div>
          </div>
        ` : ""}
      </div>
    `;
  }

  _renderSaveTemplateDialog() {
    if (!this._saveTemplateDialog) return "";
    const chores = this._state.chores || [];
    return `
      <div class="tm-scrim" data-act="scrim">
        <div class="tm-dialog">
          <div class="tm-dialog-head">
            <h2>Save as Template</h2>
            <button class="tm-icon-btn" data-act="tpl-save-cancel">✕</button>
          </div>
          <div class="tm-dialog-body">
            <div class="tm-field" style="margin-bottom:14px"><label>Template name</label><input type="text" data-field="tpl_save_name" placeholder="e.g. My morning pack"></div>
            <div class="tm-field" style="margin-bottom:14px"><label>Icon (MDI)</label><input type="text" data-field="tpl_save_icon" placeholder="mdi:clipboard-list" value="mdi:clipboard-list"></div>
            <label class="tm-field-label" style="display:block;margin-bottom:8px">Select chores to include</label>
            <div class="tm-tpl-checklist">
              ${chores.map(c => `
                <label class="tm-tpl-check-row">
                  <input type="checkbox" data-tpl-chore-check="${this._esc(c.id)}">
                  <span>${this._esc(c.name)}</span>
                  <span class="tm-text-muted" style="margin-left:auto">${c.points} pts</span>
                </label>
              `).join("")}
            </div>
          </div>
          <div class="tm-dialog-foot">
            <button class="tm-btn" data-act="tpl-save-cancel">Cancel</button>
            <button class="tm-btn tm-btn-raised" data-act="tpl-save-confirm">Save template</button>
          </div>
        </div>
      </div>
    `;
  }

  _selectTemplate(templateId) {
    const templates = this._state.templates || [];
    const tpl = templates.find(t => t.id === templateId);
    if (!tpl) return;
    this._templateSelected = tpl;
    this._templateChores = (tpl.chores || []).map(c => ({ ...c, _expanded: false }));
    this._templateView = "preview";
    this._render();
  }

  async _doApplyTemplate() {
    const chores = this._templateChores.map(c => {
      const { _expanded, ...rest } = c;
      return rest;
    });
    if (chores.length === 0) return;
    const { ok, err } = await this._callWS({ type: "taskmate/templates/apply", chores });
    if (ok) {
      this._showToast("success", `Created ${chores.length} chore${chores.length !== 1 ? "s" : ""}`);
      this._templateView = null;
      this._templateSelected = null;
      this._templateChores = [];
      await this._fetchState();
      this._activeTab = "chores";
      this._render();
    } else {
      this._showToast("error", err || "Failed to apply template");
    }
  }

  async _doSaveFromChores() {
    const name = this.querySelector('[data-field="tpl_save_name"]')?.value?.trim();
    const icon = this.querySelector('[data-field="tpl_save_icon"]')?.value?.trim() || "mdi:clipboard-list";
    const checkboxes = this.querySelectorAll('[data-tpl-chore-check]:checked');
    const chore_ids = Array.from(checkboxes).map(cb => cb.dataset.tplChoreCheck);
    if (!name || chore_ids.length === 0) {
      this._showToast("error", "Enter a name and select at least one chore");
      return;
    }
    const { ok, err } = await this._callWS({ type: "taskmate/templates/save_from_chores", chore_ids, name, icon });
    if (ok) {
      this._showToast("success", `Template "${name}" saved`);
      this._saveTemplateDialog = false;
      await this._fetchState();
      this._render();
    } else {
      this._showToast("error", err || "Failed to save template");
    }
  }

  async _confirmDeleteTemplate(templateId) {
    const templates = this._state.templates || [];
    const tpl = templates.find(t => t.id === templateId);
    if (!tpl) return;
    if (!confirm(`Delete template "${tpl.name}"? This cannot be undone.`)) return;
    const { ok, err } = await this._callWS({ type: "taskmate/templates/delete", template_id: templateId });
    if (ok) {
      this._showToast("success", "Template deleted");
      await this._fetchState();
    } else {
      this._showToast("error", err || "Failed to delete");
    }
  }

  _openCreateTemplateDialog() {
    this._openDialog({
      kind: "create-template",
      data: { name: "", icon: "mdi:clipboard-list", chores: [{ name: "", points: 5, time_category: "anytime", schedule_mode: "specific_days", due_days: [], requires_approval: false, assignment_mode: "everyone", daily_limit: 1, completion_sound: "coin" }] },
    });
  }

  _openEditTemplateDialog(templateId) {
    const templates = this._state.templates || [];
    const tpl = templates.find(t => t.id === templateId);
    if (!tpl) return;
    this._openDialog({
      kind: "edit-template",
      data: { template_id: templateId, name: tpl.name, icon: tpl.icon || "mdi:clipboard-list", chores: (tpl.chores || []).map(c => ({ ...c })) },
    });
  }

  async _doSaveCreatedTemplate() {
    const d = this._dialog?.data;
    if (!d || !d.name?.trim() || !d.chores?.length) { this._showToast("error", "Name and at least one chore required"); return; }
    const { ok, err } = await this._callWS({ type: "taskmate/templates/create", name: d.name.trim(), icon: d.icon || "mdi:clipboard-list", chores: d.chores });
    if (ok) { this._showToast("success", `Template "${d.name}" created`); this._closeDialog(true); await this._fetchState(); }
    else { this._showToast("error", err || "Failed to create template"); }
  }

  async _doSaveEditedTemplate() {
    const d = this._dialog?.data;
    if (!d || !d.template_id || !d.name?.trim()) { this._showToast("error", "Name required"); return; }
    const { ok, err } = await this._callWS({ type: "taskmate/templates/update", template_id: d.template_id, name: d.name.trim(), icon: d.icon || "mdi:clipboard-list", chores: d.chores || [] });
    if (ok) { this._showToast("success", "Template updated"); this._closeDialog(true); await this._fetchState(); }
    else { this._showToast("error", err || "Failed to update"); }
  }

  // -- Settings tab ------------------------------------------------------
  _renderSettingsTab() {
    const s = this._state.settings || {};
    const notifyServices = Object.keys((this._hass && this._hass.services && this._hass.services.notify) || {});
    const notifyOptions = [
      { v: "", l: "(none — use HA persistent notifications)" },
      ...notifyServices.map(k => ({ v: `notify.${k}`, l: `notify.${k}` })),
    ];
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">Settings</h2>
      </div>
      <div class="tm-settings">
        <div class="tm-section">
          <div class="tm-section-head">
            <div>
              <h3>Currency</h3>
              <p class="tm-meta">How points are named and shown across the app.</p>
            </div>
          </div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">Points name<small>What you call them, e.g. Stars or Coins</small></div>
              <ha-textfield data-setting="points_name" data-value="${this._esc(s.points_name || "Stars")}" placeholder="Stars"></ha-textfield>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">Points icon<small>Pick any MDI icon</small></div>
              <ha-icon-picker data-setting="points_icon" data-current="${this._esc(s.points_icon || 'mdi:star')}"></ha-icon-picker>
            </div>
          </div>
        </div>

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>History &amp; streaks</h3></div></div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">Retention<small>How many days of completion history to keep</small></div>
              <ha-textfield type="number" min="30" max="365" data-setting="history_days" data-value="${s.history_days || 90}"></ha-textfield>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">Streak reset<small>What happens when a day is missed</small></div>
              <ha-select data-setting="streak_reset_mode" data-value="${this._esc(s.streak_reset_mode || "reset")}" fixedMenuPosition naturalMenuWidth>
                ${STREAK_MODES.map(m => `<mwc-list-item value="${m.v}" ${m.v === (s.streak_reset_mode || "reset") ? "selected activated" : ""}>${this._esc(m.l)}</mwc-list-item>`).join("")}
              </ha-select>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">Weekend multiplier<small>Bonus on Sat/Sun (1.0 = off)</small></div>
              <ha-textfield type="number" step="0.1" min="1" max="5" data-setting="weekend_multiplier" data-value="${s.weekend_multiplier || 1.0}"></ha-textfield>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">Calendar projection<small>Days ahead each chore publishes to calendars</small></div>
              <ha-textfield type="number" min="1" max="90" data-setting="calendar_projection_days" data-value="${s.calendar_projection_days || 14}"></ha-textfield>
            </div>
          </div>
        </div>

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>Bonuses</h3></div></div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">Streak milestones<small>Bonus at 3, 7, 14, 30, 60, 100 days</small></div>
              <ha-switch data-setting="streak_milestones_enabled" ${s.streak_milestones_enabled ? "checked" : ""}></ha-switch>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">Perfect-week bonus<small>Bonus for completing every day of a week</small></div>
              <ha-switch data-setting="perfect_week_enabled" ${s.perfect_week_enabled ? "checked" : ""}></ha-switch>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">Perfect-week bonus points<small>How many points to award</small></div>
              <ha-textfield type="number" min="0" data-setting="perfect_week_bonus" data-value="${s.perfect_week_bonus || 50}"></ha-textfield>
            </div>
          </div>
        </div>

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>Notifications</h3></div></div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">Notify service<small>Used for parent approval pings</small></div>
              <ha-select data-setting="notify_service" data-value="${this._esc(s.notify_service || "")}" fixedMenuPosition naturalMenuWidth>
                ${notifyOptions.map(o => `<mwc-list-item value="${this._esc(o.v)}" ${o.v === (s.notify_service || "") ? "selected activated" : ""}>${this._esc(o.l)}</mwc-list-item>`).join("")}
              </ha-select>
            </div>
          </div>
        </div>

        <div class="tm-settings-foot">
          <button class="tm-btn tm-btn-raised" data-act="save-settings">Save settings</button>
        </div>
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
    if (this._dialog.kind === "bulk-chore")    return this._renderBulkChoreDialog();
    if (this._dialog.kind === "reorder")       return this._renderReorderDialog();
    if (this._dialog.kind === "create-template" || this._dialog.kind === "edit-template") return this._renderCreateEditTemplateDialog();
    return "";
  }

  _renderCreateEditTemplateDialog() {
    const d = this._dialog.data;
    const isEdit = this._dialog.kind === "edit-template";
    return `
      <div class="tm-scrim" data-act="scrim">
        <div class="tm-dialog" style="max-width:680px">
          <div class="tm-dialog-head">
            <h2>${isEdit ? "Edit" : "Create"} Template</h2>
            <button class="tm-icon-btn" data-act="close-dialog">✕</button>
          </div>
          <div class="tm-dialog-body">
            <div class="tm-field-row" style="margin-bottom:16px">
              <div class="tm-field"><label>Name</label><input type="text" data-field="name" value="${this._esc(d.name)}"></div>
              <div class="tm-field"><label>Icon (MDI)</label><input type="text" data-field="icon" value="${this._esc(d.icon)}"></div>
            </div>
            <label class="tm-field-label" style="display:block;margin-bottom:8px">Chores in this template</label>
            ${(d.chores || []).map((c, i) => `
              <div class="tm-tpl-preview-card" style="margin-bottom:8px">
                <div style="display:flex;align-items:center;gap:10px;padding:10px 14px">
                  <span style="font-weight:600;flex:1">${this._esc(c.name || "(unnamed)")}</span>
                  <span class="tm-meta">${c.points || 0} pts</span>
                  <button class="tm-tpl-remove" data-act="tpl-dialog-remove-chore" data-idx="${i}">✕</button>
                </div>
                <div style="padding:0 14px 12px;border-top:1px solid var(--tm-border-soft)">
                  <div class="tm-field-row" style="margin-top:10px">
                    <div class="tm-field"><label>Name</label><input type="text" data-tpl-dialog-field="name" data-tpl-dialog-idx="${i}" value="${this._esc(c.name)}"></div>
                    <div class="tm-field"><label>Points</label><input type="number" data-tpl-dialog-field="points" data-tpl-dialog-idx="${i}" value="${c.points || 0}" min="0"></div>
                  </div>
                  <div class="tm-field-row">
                    <div class="tm-field"><label>Time category</label>
                      <select data-tpl-dialog-field="time_category" data-tpl-dialog-idx="${i}">
                        ${TIME_CATEGORIES.map(t => `<option value="${t.v}" ${c.time_category === t.v ? "selected" : ""}>${t.l}</option>`).join("")}
                      </select>
                    </div>
                    <div class="tm-field"><label>Schedule</label>
                      <select data-tpl-dialog-field="schedule_mode" data-tpl-dialog-idx="${i}">
                        ${SCHEDULE_MODES.map(s => `<option value="${s.v}" ${c.schedule_mode === s.v ? "selected" : ""}>${s.l}</option>`).join("")}
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            `).join("")}
            <button class="tm-btn" data-act="tpl-dialog-add-chore" style="margin-top:8px">+ Add chore</button>
          </div>
          <div class="tm-dialog-foot">
            <button class="tm-btn" data-act="close-dialog">Cancel</button>
            <button class="tm-btn tm-btn-raised" data-act="${isEdit ? "tpl-save-edited" : "tpl-save-created"}">${isEdit ? "Save Changes" : "Create Template"}</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderChildDialog() {
    const d = this._dialog.data;
    const hasAvail = !!(d.availability_entity && d.availability_entity.trim());
    return this._dialogShell(this._dialog.mode === "add" ? "Add child" : "Edit child",
      [
        this._field("Name", "name", d.name, "text", "e.g. Malia"),
        this._iconPickerField("Avatar", "avatar", d.avatar),
        this._entityPickerField("Availability sensor (optional)", "availability_entity", d.availability_entity, ["binary_sensor", "sensor", "input_boolean", "person"],
          "States <code>on</code>, <code>home</code>, <code>available</code>, <code>present</code>, <code>true</code> mean available. Leave blank to treat as always available."),
        hasAvail ? this._switch("Invert logic (ON = unavailable)", "availability_inverted", d.availability_inverted,
          "Turn on for calendar or schedule sensors where an active state means the child is busy.") : "",
        this._entityPickerField("Unavailability sensor (optional)", "unavailability_entity", d.unavailability_entity, ["binary_sensor", "sensor", "input_boolean", "person", "calendar"],
          "A second sensor where <code>on</code>/<code>active</code> means the child is busy. Useful for school calendars. The child is available only when the availability sensor says available AND this sensor does not say busy."),
      ].join(""),
      `<button class="tm-btn" data-act="close-dialog">Cancel</button>
       <button class="tm-btn tm-btn-raised" data-act="save-child">Save</button>`
    );
  }

  _renderChoreDialog() {
    const d = this._dialog.data;
    const children = this._state.children || [];
    const groups = this._state.task_groups || [];
    const memberInGroup = (d.id && groups.find(g => (g.chore_ids || []).includes(d.id))) || null;
    const showSpecificDays = d.schedule_mode === "specific_days";
    const showRecurring    = d.schedule_mode === "recurring";
    const showRotation     = ["alternating", "random", "balanced"].includes(d.assignment_mode);
    const calendarEntities = Object.keys((this._hass && this._hass.states) || {})
      .filter(id => id.startsWith("calendar."))
      .sort();

    const isTimedTask = d.task_type === "timed";

    return this._dialogShell(this._dialog.mode === "add" ? "Add chore" : "Edit chore",
      [
        this._field("Name", "name", d.name, "text"),
        this._field("Description (optional)", "description", d.description, "text"),
        this._select("Task type", "task_type", d.task_type || "standard", [
          { v: "standard", l: "Standard — fixed points on completion" },
          { v: "timed", l: "Timed — points per minute" },
        ]),
        isTimedTask ? `<div class="tm-field-row">
          ${this._field("Points per window", "timed_rate_points", d.timed_rate_points || 10, "number")}
          ${this._field("Window (minutes)", "timed_rate_minutes", d.timed_rate_minutes || 5, "number")}
        </div>
        <div class="tm-field-row">
          ${this._field("Daily cap (minutes, 0 = unlimited)", "timed_max_daily_minutes", d.timed_max_daily_minutes || 0, "number")}
          ${this._field("Daily limit", "daily_limit", d.daily_limit, "number")}
        </div>` : `<div class="tm-field-row">
          ${this._field("Points", "points", d.points, "number")}
          ${this._field("Daily limit", "daily_limit", d.daily_limit, "number")}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">Assigned to</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">Leave empty to assign to <strong>all children</strong>.</span>
          </div>
        ` : `<div class="tm-field"><span class="tm-field-hint">Add some children first to assign chores to them.</span></div>`,
        this._select("Assignment mode", "assignment_mode", d.assignment_mode, ASSIGNMENT_MODES,
          "Everyone = all assigned children see it. Alternating = rotate one per day. Random = pick one daily. Balanced = split evenly across the day.", true),
        showRotation && children.length > 0 ? this._select(
          "Start rotation with (optional)", "manual_start_child_id", d.manual_start_child_id,
          [{ v: "", l: "(no override)" }, ...children.map(c => ({ v: c.id, l: c.name }))],
          "Alternating mode: permanently reorders the pool. Random/Balanced: only overrides today; tomorrow resumes normally."
        ) : "",
        this._select("Time category", "time_category", d.time_category, TIME_CATEGORIES),
        this._field("Claim allowance (minutes)", "claim_allowance_minutes", d.claim_allowance_minutes, "number",
          "Extra minutes after the time-of-day window ends during which the chore stays claimable. 0 = no grace. Night chores still cap at midnight."),
        this._select("Schedule mode", "schedule_mode", d.schedule_mode, SCHEDULE_MODES, "", true),
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
            ${this._dateField("Start date (every-2-days only)", "recurrence_start", d.recurrence_start, "Anchor date — blank = today")}
            ${this._select("First occurrence", "first_occurrence_mode", d.first_occurrence_mode, FIRST_OCCURRENCE)}
          </div>
        ` : "",
        this._select("Completion sound", "completion_sound", d.completion_sound, COMPLETION_SOUNDS.map(s => ({ v: s, l: s }))),
        this._switch("Requires parent approval", "requires_approval", d.requires_approval),
        this._switch("Skip unavailable children", "require_availability", d.require_availability,
          "Uses each child's availability sensor (set on their profile)."),
        memberInGroup ? `
          <div class="tm-field">
            <span class="tm-field-hint">Member of task group: <strong>${this._esc(memberInGroup.name)}</strong> (${memberInGroup.policy}). Manage membership on the Groups tab.</span>
          </div>
        ` : "",
        `<details class="tm-advanced">
          <summary>Bonus sub-tasks (optional)</summary>
          <div>
            <span class="tm-field-hint" style="margin-bottom:8px;display:block">Optional extra-credit tasks that unlock after the main chore is completed.</span>
            ${(d.bonus_subtasks || []).map((b, idx) => `
              <div class="tm-field-row" style="align-items:flex-end;gap:6px;margin-bottom:6px">
                <div class="tm-field" style="flex:2;margin:0"><input class="tm-input" placeholder="Sub-task name" value="${this._esc(b.name)}" data-field="bonus_subtasks[${idx}].name"></div>
                <div class="tm-field" style="flex:0 0 70px;margin:0"><input class="tm-input" type="number" min="0" placeholder="Pts" value="${b.points}" data-field="bonus_subtasks[${idx}].points"></div>
                <button type="button" class="tm-btn tm-btn-icon" data-act="remove-bonus-subtask" data-idx="${idx}" title="Remove" style="padding:6px 10px">✕</button>
              </div>
            `).join("")}
            <button type="button" class="tm-btn" data-act="add-bonus-subtask" style="margin-top:4px">+ Add bonus sub-task</button>
          </div>
        </details>`,
        `<details class="tm-advanced">
          <summary>Advanced — visibility &amp; calendar publishing</summary>
          <div>
            ${this._entityPickerField("Visibility entity (optional)", "visibility_entity", d.visibility_entity, ["binary_sensor", "sensor", "switch", "input_boolean", "input_select"],
              "Chore only shows when its state matches the rule below. Leave blank for always-show.")}
            <div class="tm-field-row">
              ${this._select("Visibility operator", "visibility_operator", d.visibility_operator, VISIBILITY_OPS)}
              ${this._field("Visibility value", "visibility_state", d.visibility_state, "text", 'e.g. "on", "home", "30"')}
            </div>
            <div class="tm-field">
              <span class="tm-field-label">Publish to calendars (optional)</span>
              ${calendarEntities.length === 0 ? `<span class="tm-field-hint">No calendar entities found in Home Assistant. Set one up first.</span>` : `
                <div class="tm-chip-row">
                  ${calendarEntities.map(cid => `
                    <button type="button" class="tm-chip-btn ${(d.publish_calendar_entities || []).includes(cid) ? "tm-chip-on" : ""}" data-act="toggle-calendar" data-id="${this._esc(cid)}">
                      ${this._esc(cid)}
                    </button>
                  `).join("")}
                </div>
                <span class="tm-field-hint">Today's assignment will be added as a calendar event on each selected calendar.</span>
              `}
            </div>
            ${this._switch("Enabled", "enabled", d.enabled !== false)}
          </div>
        </details>`,
      ].join(""),
      `<button class="tm-btn" data-act="close-dialog">Cancel</button>
       <button class="tm-btn tm-btn-raised" data-act="save-chore">Save</button>`
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
          ${this._iconPickerField("Icon", "icon", d.icon)}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">Assigned to</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-reward-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">Leave empty to make available to <strong>all children</strong>.</span>
          </div>
        ` : "",
        this._switch("Pool reward (savings jar)", "pool_enabled", d.pool_enabled,
          "Children deposit points into this reward's dedicated pool rather than spending from their balance."),
        this._switch("Jackpot — pool from all assigned children", "is_jackpot", d.is_jackpot,
          "Combine all children's contributions toward one shared reward."),
        `<div class="tm-field-row">
          ${this._field("Limited quantity (blank = unlimited)", "quantity_str", d.quantity_str, "text", "Each approved claim reduces by 1.")}
          ${this._dateField("Expires (blank = never)", "expires_at", d.expires_at, "Pooled points are refunded at midnight.")}
        </div>`,
      ].join(""),
      `<button class="tm-btn" data-act="close-dialog">Cancel</button>
       <button class="tm-btn tm-btn-raised" data-act="save-reward">Save</button>`
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
          ${this._iconPickerField("Icon", "icon", d.icon)}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">Applies to</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-penbon-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">Leave empty to apply to <strong>all children</strong>.</span>
          </div>
        ` : "",
      ].join(""),
      `<button class="tm-btn" data-act="close-dialog">Cancel</button>
       <button class="tm-btn tm-btn-raised" data-act="save-${kind}">Save</button>`
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
       ${eligible.length === 0 ? `<p class="tm-meta">No eligible children. Edit the ${kind} to set who it applies to.</p>` : `
        <div class="tm-chip-row" style="margin-top: 12px;">
          ${eligible.map(c => `
            <button class="tm-btn" data-act="do-apply-${kind}" data-id="${this._esc(item.id)}" data-child="${this._esc(c.id)}">
              ${this._esc(c.name)}
            </button>
          `).join("")}
        </div>
       `}`,
      `<button class="tm-btn" data-act="close-dialog">Close</button>`
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
            <div class="tm-chip-row">
              ${chores.map(c => `
                <button type="button" class="tm-chip-btn ${(d.chore_ids || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-group-chore" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
          </div>
        `,
      ].join(""),
      `<button class="tm-btn" data-act="close-dialog">Cancel</button>
       <button class="tm-btn tm-btn-raised" data-act="save-group">Save</button>`
    );
  }

  _renderBulkChoreDialog() {
    const d = this._dialog.data;
    const children = this._state.children || [];
    return this._dialogShell("Bulk add chores",
      [
        `<div class="tm-field">
          <span class="tm-field-label">Chore names (one per line, or comma-separated)</span>
          <textarea class="tm-textarea" data-field="chore_names" rows="6" placeholder="Make bed&#10;Empty dishwasher&#10;Feed dog">${this._esc(d.chore_names || "")}</textarea>
          <span class="tm-field-hint">All chores will share the settings below.</span>
        </div>`,
        `<div class="tm-field-row">
          ${this._field("Points (each)", "points", d.points, "number")}
          ${this._field("Daily limit", "daily_limit", d.daily_limit, "number")}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">Assigned to</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">Leave empty to assign to all children.</span>
          </div>
        ` : "",
        this._select("Time category", "time_category", d.time_category, TIME_CATEGORIES),
        this._select("Schedule mode", "schedule_mode", d.schedule_mode, SCHEDULE_MODES, "", true),
        d.schedule_mode === "specific_days" ? `
          <div class="tm-field">
            <span class="tm-field-label">Days of week (empty = every day)</span>
            <div class="tm-day-row">
              ${DAYS.map(day => `
                <button type="button" class="tm-day-btn ${(d.due_days || []).includes(day.v) ? "tm-day-on" : ""}" data-act="toggle-bulk-day" data-day="${day.v}">${day.l}</button>
              `).join("")}
            </div>
          </div>
        ` : "",
        this._select("Completion sound", "completion_sound", d.completion_sound, COMPLETION_SOUNDS.map(s => ({ v: s, l: s }))),
        this._switch("Requires parent approval", "requires_approval", d.requires_approval),
      ].join(""),
      `<button class="tm-btn" data-act="close-dialog">Cancel</button>
       <button class="tm-btn tm-btn-raised" data-act="save-bulk-chores">Create chores</button>`
    );
  }

  _renderReorderDialog() {
    const d = this._dialog.data;
    const choreById = Object.fromEntries((this._state.chores || []).map(c => [c.id, c]));
    return this._dialogShell(`Reorder chores · ${d.name}`,
      `<p class="tm-meta">Drag rows to reorder how chores appear on this child's card. Save to apply.</p>
       <div class="tm-reorder-list">
         ${(d.order || []).map(id => {
           const c = choreById[id];
           if (!c) return "";
           return `
             <div class="tm-reorder-item" draggable="true" data-drag-id="${this._esc(id)}">
               <div class="tm-reorder-handle">⠿</div>
               <div class="tm-reorder-name">${this._esc(c.name)}</div>
               <div class="tm-reorder-points tm-numeric">${c.points}</div>
             </div>
           `;
         }).join("")}
       </div>`,
      `<button class="tm-btn" data-act="close-dialog">Cancel</button>
       <button class="tm-btn tm-btn-raised" data-act="save-chore-order">Save order</button>`
    );
  }

  // ---- form helpers ----------------------------------------------------
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
      <div class="tm-field">
        <ha-textfield
          label="${this._esc(label)}"
          data-field="${name}"
          data-value="${this._esc(value == null ? "" : value)}"
          ${type === "number" ? 'type="number"' : ''}
        ></ha-textfield>
        ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
      </div>`;
  }

  _dateField(label, name, value, hint = "") {
    return `
      <div class="tm-field">
        <ha-textfield
          label="${this._esc(label)}"
          data-field="${name}"
          data-value="${this._esc(value || "")}"
          type="date"
        ></ha-textfield>
        ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
      </div>`;
  }

  _select(label, name, value, options, hint = "", rerender = false) {
    return `
      <div class="tm-field">
        <ha-select
          label="${this._esc(label)}"
          data-field="${name}"
          data-value="${this._esc(value || "")}"
          ${rerender ? 'data-rerender="true"' : ""}
          fixedMenuPosition
          naturalMenuWidth
        >
          ${options.map(o => `<mwc-list-item value="${this._esc(o.v)}" ${String(o.v) === String(value) ? "selected activated" : ""}>${this._esc(o.l)}</mwc-list-item>`).join("")}
        </ha-select>
        ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
      </div>`;
  }

  _switch(label, name, checked, hint = "") {
    return `
      <div class="tm-check-row">
        <ha-switch data-field="${name}" ${checked ? "checked" : ""}></ha-switch>
        <div>
          <div class="tm-check-title">${this._esc(label)}</div>
          ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
        </div>
      </div>`;
  }

  _iconPickerField(label, name, value) {
    return `
      <div class="tm-field">
        <span class="tm-field-label">${this._esc(label)}</span>
        <ha-icon-picker data-field="${name}" data-current="${this._esc(value || "")}"></ha-icon-picker>
      </div>`;
  }

  _entityDomainIcon(entityId) {
    const domain = (entityId || "").split(".")[0];
    const map = {
      binary_sensor: "mdi:checkbox-marked-circle-outline",
      sensor: "mdi:eye",
      input_boolean: "mdi:toggle-switch",
      person: "mdi:account",
      calendar: "mdi:calendar",
      switch: "mdi:light-switch",
      input_select: "mdi:form-dropdown",
    };
    return map[domain] || "mdi:puzzle";
  }

  _entityPickerField(label, name, value, domains, hint = "") {
    const friendly = value && this._hass?.states?.[value]?.attributes?.friendly_name || "";
    const icon = value ? (this._hass?.states?.[value]?.attributes?.icon || this._entityDomainIcon(value)) : "";
    return `
      <div class="tm-field">
        <span class="tm-field-label">${this._esc(label)}</span>
        <div class="tm-ep" data-ep-field="${name}" data-ep-domains="${(domains || []).join(",")}">
          ${value
            ? `<div class="tm-ep-selected">
                <ha-icon icon="${this._esc(icon)}" class="tm-ep-selected-icon"></ha-icon>
                <span class="tm-ep-selected-text">${this._esc(friendly || value)}</span>
                <button type="button" class="tm-entity-clear" data-act="clear-field" data-field="${name}" title="Clear">✕</button>
              </div>`
            : `<div class="tm-ep-search-wrap">
                <ha-icon icon="mdi:magnify" class="tm-ep-search-icon"></ha-icon>
                <input type="text" class="tm-ep-input" placeholder="Search | Add custom item" value="" autocomplete="off">
              </div>`
          }
        </div>
        ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
      </div>`;
  }

  _openEntityDropdown(input) {
    this._closeEntityDropdown();
    const picker = input.closest(".tm-ep");
    if (!picker || !this._hass?.states) return;
    const field = picker.dataset.epField;
    const domains = (picker.dataset.epDomains || "").split(",").filter(Boolean);
    const query = input.value.toLowerCase();
    const entities = Object.entries(this._hass.states)
      .filter(([id, st]) => {
        if (domains.length && !domains.some(d => id.startsWith(d + "."))) return false;
        if (!query) return true;
        const fn = st.attributes?.friendly_name || "";
        return id.toLowerCase().includes(query) || fn.toLowerCase().includes(query);
      })
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(0, 50);
    if (!entities.length) return;
    const dd = document.createElement("div");
    dd.className = "tm-ep-dropdown";
    entities.forEach(([id, st]) => {
      const fn = st.attributes?.friendly_name || "";
      const stateIcon = st.attributes?.icon || this._entityDomainIcon(id);
      const opt = document.createElement("div");
      opt.className = "tm-ep-option";
      opt.dataset.act = "pick-entity";
      opt.dataset.field = field;
      opt.dataset.value = id;
      const iconEl = document.createElement("ha-icon");
      iconEl.setAttribute("icon", stateIcon);
      iconEl.className = "tm-ep-option-icon";
      opt.appendChild(iconEl);
      const textWrap = document.createElement("div");
      textWrap.className = "tm-ep-option-text";
      const idDiv = document.createElement("div");
      idDiv.className = "tm-ep-id";
      idDiv.textContent = fn || id;
      textWrap.appendChild(idDiv);
      if (fn) {
        const nameDiv = document.createElement("div");
        nameDiv.className = "tm-ep-name";
        nameDiv.textContent = id;
        textWrap.appendChild(nameDiv);
      }
      opt.appendChild(textWrap);
      dd.appendChild(opt);
    });
    picker.appendChild(dd);
  }

  _closeEntityDropdown() {
    const dd = this.querySelector(".tm-ep-dropdown");
    if (dd) dd.remove();
  }

  _emptyState(icon, title, copy, action, label) {
    return `
      <div class="tm-empty">
        <div class="tm-empty-icon">${icon}</div>
        <h3>${this._esc(title)}</h3>
        <p>${this._esc(copy)}</p>
        <button class="tm-btn tm-btn-raised" data-act="${action}">${this._esc(label)}</button>
      </div>
    `;
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

  _styles() {
    return `<style>
      taskmate-panel {
        display: block; height: 100%;

        --tm-bg:            var(--primary-background-color, #fafafa);
        --tm-surface-0:     var(--card-background-color, #fff);
        --tm-surface-1:     var(--card-background-color, #fff);
        --tm-surface-2:     var(--secondary-background-color, #f5f5f5);
        --tm-surface-3:     var(--secondary-background-color, #e8e8e8);
        --tm-surface-hover: var(--secondary-background-color, #f5f5f5);

        --tm-border:        var(--divider-color, #e0e0e0);
        --tm-border-strong: var(--divider-color, #d4d4d4);
        --tm-border-soft:   var(--divider-color, #e8e8e8);

        --tm-text:          var(--primary-text-color, #212121);
        --tm-text-muted:    var(--secondary-text-color, #727272);
        --tm-text-faint:    var(--secondary-text-color, #727272);
        --tm-text-vfaint:   var(--disabled-text-color, #bdbdbd);

        --tm-accent:        var(--primary-color, #03a9f4);
        --tm-accent-hover:  var(--primary-color, #03a9f4);
        --tm-accent-press:  var(--primary-color, #03a9f4);
        --tm-accent-soft:   color-mix(in srgb, var(--primary-color, #03a9f4), transparent 90%);
        --tm-accent-border: color-mix(in srgb, var(--primary-color, #03a9f4), transparent 70%);
        --tm-accent-text:   var(--primary-color, #03a9f4);
        --tm-accent-glow:   color-mix(in srgb, var(--primary-color, #03a9f4), transparent 85%);

        --tm-positive:      var(--success-color, #4caf50);
        --tm-positive-soft: color-mix(in srgb, var(--success-color, #4caf50), transparent 90%);
        --tm-positive-border:color-mix(in srgb, var(--success-color, #4caf50), transparent 70%);
        --tm-warning:       var(--warning-color, #ff9800);
        --tm-warning-soft:  color-mix(in srgb, var(--warning-color, #ff9800), transparent 90%);
        --tm-warning-border:color-mix(in srgb, var(--warning-color, #ff9800), transparent 70%);
        --tm-danger:        var(--error-color, #db4437);
        --tm-danger-soft:   color-mix(in srgb, var(--error-color, #db4437), transparent 90%);
        --tm-danger-border: color-mix(in srgb, var(--error-color, #db4437), transparent 70%);

        --tm-gold:          var(--warning-color, #ff9800);
        --tm-gold-soft:     color-mix(in srgb, var(--warning-color, #ff9800), transparent 90%);
        --tm-pool:          var(--accent-color, #ff9800);
        --tm-pool-soft:     color-mix(in srgb, var(--accent-color, #ff9800), transparent 90%);
        --tm-sticky:        var(--info-color, #039be5);
        --tm-sticky-soft:   color-mix(in srgb, var(--info-color, #039be5), transparent 90%);

        --tm-radius-sm:     8px;
        --tm-radius:        var(--ha-card-border-radius, 12px);
        --tm-radius-lg:     var(--ha-card-border-radius, 12px);

        --tm-shadow-xs:     none;
        --tm-shadow-sm:     none;
        --tm-shadow:        var(--ha-card-box-shadow, none);
        --tm-shadow-lg:     var(--ha-card-box-shadow, 0 2px 6px rgba(0,0,0,0.15));
        --tm-shadow-focus:  0 0 0 2px var(--tm-accent-glow);
        --tm-easing:        ease;

        --tm-sidebar-w:     240px;

        background: var(--tm-bg);
        color: var(--tm-text);
        font-family: var(--paper-font-body1_-_font-family, Roboto, "Noto Sans", sans-serif);
        font-size: 14px;
        line-height: 1.5;
        -webkit-font-smoothing: antialiased;
      }

      /* ===== Shell ===== */
      .tm-shell {
        display: grid;
        grid-template-columns: var(--tm-sidebar-w) 1fr;
        height: 100%;
        position: relative;
        overflow: hidden;
      }
      .tm-main { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }

      /* ===== Sidebar ===== */
      .tm-sidebar {
        background: var(--tm-surface-0);
        border-right: 1px solid var(--tm-border);
        display: flex; flex-direction: column;
        overflow: hidden;
      }
      .tm-brand {
        display: flex; align-items: center; gap: 10px;
        padding: 14px 16px;
        border-bottom: 1px solid var(--tm-border-soft);
      }
      .tm-brand-mark {
        width: 28px; height: 28px;
        border-radius: 7px;
        background: var(--tm-accent);
        color: var(--text-primary-color, #fff);
        display: grid; place-items: center;
        flex-shrink: 0;
      }
      .tm-brand-mark ha-icon { --mdc-icon-size: 16px; }
      .tm-brand-text {
        flex: 1; min-width: 0;
        font-weight: 600; font-size: 14px;
        letter-spacing: -0.01em;
        line-height: 1.15;
      }
      .tm-brand-text small {
        display: block;
        font-weight: 400;
        color: var(--tm-text-faint);
        font-size: 11px;
        font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
        margin-top: 1px;
      }
      .tm-nav {
        padding: 10px 8px;
        flex: 1;
        overflow-y: auto;
      }
      .tm-nav-group { margin-bottom: 16px; }
      .tm-nav-group:last-child { margin-bottom: 0; }
      .tm-nav-head {
        font-size: 10.5px;
        font-weight: 600;
        color: var(--tm-text-faint);
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 4px 10px 6px;
      }
      .tm-nav-item {
        display: flex; align-items: center; gap: 10px;
        padding: 7px 10px;
        border-radius: var(--tm-radius-sm);
        color: var(--tm-text-muted);
        cursor: pointer;
        font-size: 13px;
        font-weight: 500;
        font-family: inherit;
        background: transparent; border: 0;
        width: 100%; text-align: left;
        position: relative;
        transition: all 0.1s var(--tm-easing);
      }
      .tm-nav-item:hover { background: var(--tm-surface-2); color: var(--tm-text); }
      .tm-nav-active {
        background: var(--tm-surface-2);
        color: var(--tm-text);
        font-weight: 600;
      }
      .tm-nav-active::before {
        content: ""; position: absolute;
        left: -8px; top: 6px; bottom: 6px; width: 2px;
        background: var(--tm-accent);
        border-radius: 0 2px 2px 0;
      }
      .tm-nav-icon {
        width: 16px; height: 16px;
        display: grid; place-items: center;
        color: var(--tm-text-faint);
        flex-shrink: 0;
      }
      .tm-nav-icon ha-icon { --mdc-icon-size: 16px; }
      .tm-nav-active .tm-nav-icon { color: var(--tm-accent); }
      .tm-nav-label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
      .tm-nav-badge {
        font-size: 11px;
        color: var(--tm-text-faint);
        background: var(--tm-surface-3);
        padding: 1px 7px;
        border-radius: 999px;
        font-variant-numeric: tabular-nums;
        line-height: 1.4;
      }
      .tm-nav-active .tm-nav-badge {
        background: var(--tm-accent-soft);
        color: var(--tm-accent-text);
      }
      .tm-nav-badge-urgent {
        background: var(--tm-warning-soft) !important;
        color: var(--tm-warning) !important;
      }

      /* ===== Topbar ===== */
      .tm-topbar {
        height: 52px;
        display: flex; align-items: center; gap: 12px;
        padding: 0 24px;
        border-bottom: 1px solid var(--tm-border);
        background: var(--tm-surface-0);
        flex-shrink: 0;
      }
      .tm-crumbs {
        display: flex; align-items: center; gap: 8px;
        font-size: 13px;
        color: var(--tm-text-faint);
        flex: 1;
      }
      .tm-crumbs strong {
        color: var(--tm-text);
        font-weight: 600;
        letter-spacing: -0.005em;
      }
      .tm-crumbs-sep { color: var(--tm-text-vfaint); }
      .tm-approval-pill {
        background: var(--tm-warning-soft);
        color: var(--tm-warning);
        border: 1px solid var(--tm-warning-border);
        padding: 4px 12px 4px 10px;
        border-radius: 999px;
        font-size: 12px; font-weight: 500;
        cursor: pointer;
        font-family: inherit;
        display: inline-flex; align-items: center; gap: 6px;
        transition: all 0.1s var(--tm-easing);
      }
      .tm-approval-pill:hover { filter: brightness(0.97); }
      .tm-approval-dot {
        width: 6px; height: 6px; border-radius: 50%;
        background: var(--tm-warning);
        animation: tm-pulse 2s ease-in-out infinite;
      }
      @keyframes tm-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.45; } }

      /* ===== Mobile tabs (hidden by default, shown on narrow) ===== */
      .tm-mobile-tabs { display: none; }

      /* Approval banner */
      .tm-approval-banner {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 24px;
        background: var(--tm-warning-soft);
        border-bottom: 1px solid var(--tm-warning-border);
        color: var(--tm-warning);
        font-size: 13px;
      }
      .tm-approval-banner ha-icon { --mdc-icon-size: 18px; color: var(--tm-warning); }
      .tm-approval-banner span { flex: 1; }
      .tm-approval-banner strong { color: var(--tm-text); font-weight: 600; }

      /* Body */
      .tm-body { flex: 1; overflow-y: auto; padding: 24px 32px 56px; background: var(--tm-bg); }
      .tm-body-inner { max-width: 1180px; margin: 0 auto; }

      /* Toolbar */
      .tm-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
      .tm-toolbar-title {
        margin: 0; font-size: 20px; font-weight: 600;
        letter-spacing: -0.018em;
      }
      .tm-toolbar-count {
        color: var(--tm-text-faint); font-weight: 400;
        margin-left: 6px;
        font-variant-numeric: tabular-nums;
        font-size: 16px;
      }

      /* Search input */
      .tm-search-wrap {
        position: relative;
        flex: 1; min-width: 240px; max-width: 400px;
      }
      .tm-search-icon {
        position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
        --mdc-icon-size: 14px; color: var(--tm-text-faint);
        pointer-events: none;
      }
      .tm-search {
        width: 100%;
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
        padding: 6px 10px 6px 32px;
        color: var(--tm-text);
        font-size: 13px;
        font-family: inherit;
        box-shadow: var(--tm-shadow-xs);
        transition: all 0.1s var(--tm-easing);
      }
      .tm-search:hover { border-color: var(--tm-border-strong); }
      .tm-search:focus {
        outline: 0;
        border-color: var(--tm-accent);
        box-shadow: var(--tm-shadow-focus);
      }
      .tm-search::placeholder { color: var(--tm-text-vfaint); }
      .tm-search-clear {
        position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
        background: var(--tm-surface-2);
        color: var(--tm-text-muted);
        border: 0;
        width: 20px; height: 20px;
        border-radius: 50%; cursor: pointer; font-size: 11px;
        display: grid; place-items: center;
      }
      .tm-search-clear:hover { background: var(--tm-surface-3); color: var(--tm-text); }

      /* Buttons */
      .tm-btn {
        display: inline-flex; align-items: center; justify-content: center;
        gap: 6px; padding: 8px 16px;
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
        background: var(--tm-surface-0);
        color: var(--tm-accent);
        font-size: 13px; font-weight: 500;
        font-family: inherit;
        cursor: pointer;
        transition: all 0.12s var(--tm-easing);
        white-space: nowrap;
        text-decoration: none;
        line-height: 1.3;
      }
      .tm-btn:hover {
        background: var(--tm-accent-soft);
        border-color: var(--tm-accent);
      }
      .tm-btn-raised {
        background: var(--tm-accent);
        color: var(--text-primary-color, #fff);
        border-color: var(--tm-accent);
        box-shadow: var(--tm-shadow-xs);
      }
      .tm-btn-raised:hover {
        filter: brightness(1.1);
        box-shadow: var(--tm-shadow-sm);
      }
      .tm-btn-sm {
        padding: 5px 12px; font-size: 12.5px;
      }
      .tm-btn-danger {
        color: var(--tm-danger);
        border-color: var(--tm-danger-soft);
      }
      .tm-btn-danger:hover {
        background: var(--tm-danger-soft);
        border-color: var(--tm-danger);
      }
      .tm-icon-btn {
        width: 28px; height: 28px;
        border: 0; background: transparent;
        border-radius: var(--tm-radius-sm);
        display: grid; place-items: center;
        color: var(--tm-text-faint);
        cursor: pointer;
        font-family: inherit;
        transition: all 0.1s var(--tm-easing);
      }
      .tm-icon-btn ha-icon { --mdc-icon-size: 16px; }
      .tm-icon-btn:hover { background: var(--tm-surface-2); color: var(--tm-text); }

      /* Cards */
      .tm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(320px, 100%), 1fr)); gap: 14px; }
      .tm-card {
        position: relative; overflow: hidden;
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-lg);
        padding: 18px;
        box-shadow: var(--tm-shadow-xs);
        transition: all 0.15s var(--tm-easing);
        margin-bottom: 14px;
      }
      .tm-card:last-child { margin-bottom: 0; }
      .tm-card:hover { border-color: var(--tm-border-strong); box-shadow: var(--tm-shadow-sm); }
      .tm-card-error { border-left: 3px solid var(--tm-danger); color: var(--tm-danger); }
      .tm-loading { color: var(--tm-text-muted); }

      .tm-section-title {
        margin: 0 0 12px;
        font-size: 14px; font-weight: 600;
        letter-spacing: -0.005em;
        display: flex; align-items: center; gap: 8px;
      }

      /* Child / reward / group cards share head/avatar */
      .tm-child-card { display: flex; flex-direction: column; gap: 14px; margin-bottom: 0; }
      .tm-child-head { display: flex; align-items: center; gap: 12px; }
      .tm-avatar {
        width: 44px; height: 44px;
        border-radius: 10px;
        background: var(--tm-accent-soft);
        border: 1px solid var(--tm-border);
        display: grid; place-items: center;
        flex-shrink: 0;
        color: var(--tm-accent);
      }
      .tm-avatar ha-icon { --mdc-icon-size: 24px; }
      .tm-avatar-reward  { color: var(--tm-gold); }
      .tm-child-name { min-width: 0; flex: 1; }
      .tm-child-name h3 { margin: 0; font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }
      .tm-meta { color: var(--tm-text-faint); font-size: 12px; margin-top: 2px; word-break: break-word; }
      .tm-meta code { font-family: ui-monospace, "SF Mono", Menlo, monospace; background: var(--tm-surface-2); padding: 1px 6px; border-radius: 4px; font-size: 11px; color: var(--tm-text-muted); }
      .tm-text-muted { color: var(--tm-text-muted); }

      .tm-stats-row {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 1px;
        background: var(--tm-border-soft);
        border: 1px solid var(--tm-border-soft);
        border-radius: var(--tm-radius);
        overflow: hidden;
      }
      .tm-stat {
        background: var(--tm-surface-1);
        padding: 10px 12px;
      }
      .tm-stat-value {
        font-size: 17px; font-weight: 600;
        letter-spacing: -0.01em;
        font-variant-numeric: tabular-nums;
        color: var(--tm-text);
        line-height: 1.15;
      }
      .tm-stat-label {
        font-size: 11px;
        color: var(--tm-text-faint);
        margin-top: 2px; font-weight: 400;
        letter-spacing: 0.01em;
      }
      .tm-stat-highlight .tm-stat-value { color: var(--tm-gold); }

      .tm-card-foot {
        display: flex; gap: 6px;
        margin-top: auto;
        padding-top: 12px;
        border-top: 1px solid var(--tm-border-soft);
        flex-wrap: wrap;
        align-items: center;
      }

      .tm-add-tile {
        background: transparent;
        border: 1.5px dashed var(--tm-border-strong);
        border-radius: var(--tm-radius-lg);
        padding: 36px 18px;
        color: var(--tm-text-faint);
        text-align: center;
        font-size: 13px; font-weight: 500;
        cursor: pointer;
        font-family: inherit;
        display: grid; place-items: center; gap: 8px;
        transition: all 0.12s var(--tm-easing);
        min-height: 200px;
      }
      .tm-add-tile:hover {
        border-color: var(--tm-accent);
        color: var(--tm-accent-text);
        background: var(--tm-accent-soft);
      }
      .tm-add-plus {
        width: 32px; height: 32px;
        border-radius: 50%;
        background: var(--tm-surface-2);
        display: grid; place-items: center;
        font-size: 18px;
        transition: all 0.15s var(--tm-easing);
      }
      .tm-add-tile:hover .tm-add-plus { background: var(--tm-accent); color: var(--text-primary-color, #fff); }

      /* Tables */
      .tm-table-wrap {
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-lg);
        overflow: hidden;
        box-shadow: var(--tm-shadow-xs);
      }
      .tm-table { width: 100%; border-collapse: collapse; font-size: 13px; }
      .tm-table th, .tm-table td {
        text-align: left;
        padding: 11px 16px;
        border-bottom: 1px solid var(--tm-border-soft);
        vertical-align: middle;
      }
      .tm-table th {
        color: var(--tm-text-faint);
        font-weight: 500; font-size: 11.5px;
        text-transform: uppercase; letter-spacing: 0.02em;
        background: var(--tm-surface-2);
        border-bottom: 1px solid var(--tm-border);
      }
      .tm-table tr:last-child td { border-bottom: 0; }
      .tm-row { transition: background 0.1s var(--tm-easing); }
      .tm-row:hover { background: var(--tm-surface-hover); }
      .tm-row-disabled { opacity: 0.5; }
      .tm-row-icon { display: inline-flex; vertical-align: middle; margin-right: 10px; opacity: 0.7; --mdc-icon-size: 18px; color: var(--tm-text-muted); }
      .tm-row-actions { text-align: right; white-space: nowrap; display: flex; gap: 4px; justify-content: flex-end; align-items: center; }
      .tm-numeric { font-feature-settings: "tnum"; }
      .tm-yes { color: var(--tm-positive); font-weight: 500; }
      .tm-no  { color: var(--tm-text-faint); }
      .tm-neg { color: var(--tm-danger); }
      .tm-pos { color: var(--tm-positive); }
      .tm-cost { color: var(--tm-gold); }
      .tm-table-hint { margin-top: 8px; font-size: 11px; }

      .tm-inline-input {
        background: var(--tm-surface-1);
        border: 1px solid var(--tm-accent);
        border-radius: 6px;
        padding: 4px 8px;
        color: var(--tm-text);
        font-size: 13px; font-weight: 500;
        font-family: inherit;
        max-width: 240px;
        outline: 0;
        box-shadow: 0 0 0 3px var(--tm-accent-soft);
      }

      /* Pills */
      .tm-pill {
        display: inline-flex; align-items: center; gap: 5px;
        padding: 2px 8px; border-radius: 999px;
        font-size: 11.5px; font-weight: 500;
        line-height: 1.5;
        background: var(--tm-surface-2); color: var(--tm-text-muted);
        border: 1px solid var(--tm-border);
        margin-left: 4px; vertical-align: middle;
      }
      .tm-pill-accent  { background: var(--tm-accent-soft);   color: var(--tm-accent-text); border-color: var(--tm-accent-border); }
      .tm-pill-success { background: var(--tm-positive-soft); color: var(--tm-positive);    border-color: var(--tm-positive-border); }
      .tm-pill-warn    { background: var(--tm-warning-soft);  color: var(--tm-warning);     border-color: var(--tm-warning-border); }
      .tm-pill-danger  { background: var(--tm-danger-soft);   color: var(--tm-danger);      border-color: var(--tm-danger-border); }
      .tm-pill-pool    { background: var(--tm-pool-soft);     color: var(--tm-pool);        border-color: color-mix(in srgb, var(--tm-pool), transparent 75%); }
      .tm-pill-sticky  { background: var(--tm-sticky-soft);   color: var(--tm-sticky);      border-color: color-mix(in srgb, var(--tm-sticky), transparent 75%); }
      .tm-pill-spread  { background: var(--tm-positive-soft); color: var(--tm-positive);    border-color: var(--tm-positive-border); }
      .tm-pill-jackpot { background: var(--tm-gold-soft);     color: var(--tm-gold);        border-color: color-mix(in srgb, var(--tm-gold), transparent 75%); }
      .tm-pill-alternating, .tm-pill-random, .tm-pill-balanced { background: var(--tm-accent-soft); color: var(--tm-accent-text); border-color: var(--tm-accent-border); }
      .tm-pill-dot::before {
        content: ""; width: 5px; height: 5px; border-radius: 50%;
        background: currentColor;
      }

      /* Reward extras */
      .tm-reward-card { display: flex; flex-direction: column; gap: 12px; margin-bottom: 0; }
      .tm-progress {
        height: 8px;
        background: var(--tm-surface-2);
        border-radius: 999px;
        overflow: hidden;
        margin-top: 4px;
        border: 1px solid var(--tm-border-soft);
      }
      .tm-progress > span {
        display: block; height: 100%;
        background: var(--tm-accent);
        border-radius: 999px;
      }
      .tm-progress-text {
        font-size: 12px; color: var(--tm-text-faint);
        display: flex; justify-content: space-between;
        font-variant-numeric: tabular-nums;
        margin-top: 6px;
      }
      .tm-progress-text strong { color: var(--tm-text); font-weight: 600; }

      /* Empty state */
      .tm-empty {
        text-align: center;
        padding: 56px 24px;
        background: var(--tm-surface-0);
        border: 1px dashed var(--tm-border-strong);
        border-radius: var(--tm-radius-lg);
      }
      .tm-empty-icon {
        width: 48px; height: 48px;
        border-radius: 12px;
        background: var(--tm-surface-2);
        display: inline-grid; place-items: center;
        font-size: 22px;
        margin-bottom: 12px;
        border: 1px solid var(--tm-border);
      }
      .tm-empty h3 { margin: 0 0 4px; font-size: 14px; font-weight: 600; letter-spacing: -0.005em; color: var(--tm-text); }
      .tm-empty p  { margin: 0 0 16px; color: var(--tm-text-muted); font-size: 13px; max-width: 360px; margin-left: auto; margin-right: auto; }

      /* Group list */
      .tm-group-list { margin: 8px 0 0; padding-left: 20px; color: var(--tm-text-muted); font-size: 13px; }
      .tm-group-list li { margin-bottom: 2px; }

      /* Activity tab */
      .tm-approval-list { display: flex; flex-direction: column; gap: 8px; }
      .tm-approval-item {
        display: flex; align-items: center; gap: 14px;
        padding: 12px;
        background: var(--tm-surface-2);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
      }
      .tm-approval-icon {
        width: 36px; height: 36px;
        border-radius: 50%;
        background: var(--tm-warning-soft);
        color: var(--tm-warning);
        display: grid; place-items: center;
        flex-shrink: 0;
      }
      .tm-approval-icon ha-icon { --mdc-icon-size: 20px; }
      .tm-approval-body { flex: 1; min-width: 0; }
      .tm-approval-line { font-size: 13px; }
      .tm-approval-actions { display: flex; gap: 6px; flex-shrink: 0; }

      .tm-timeline { display: flex; flex-direction: column; }
      .tm-timeline-row {
        display: grid; grid-template-columns: 80px 32px 1fr auto;
        gap: 12px; align-items: center;
        padding: 10px 0;
        border-top: 1px solid var(--tm-border-soft);
        font-size: 13px;
      }
      .tm-timeline-row:first-child { border-top: 0; }
      .tm-timeline-time { color: var(--tm-text-faint); font-size: 12px; font-feature-settings: "tnum"; }
      .tm-timeline-icon {
        width: 28px; height: 28px;
        border-radius: 8px;
        display: grid; place-items: center;
        background: var(--tm-surface-2);
      }
      .tm-timeline-icon ha-icon { --mdc-icon-size: 16px; }
      .tm-timeline-completion ha-icon { color: var(--tm-positive); }
      .tm-timeline-claim ha-icon      { color: var(--tm-gold); }
      .tm-timeline-manual ha-icon     { color: var(--tm-accent); }
      .tm-timeline-points { font-weight: 600; }

      /* Settings */
      .tm-settings { display: flex; flex-direction: column; gap: 16px; }
      .tm-section {
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-lg);
        overflow: hidden;
        box-shadow: var(--tm-shadow-xs);
      }
      .tm-section-head {
        padding: 16px 20px 12px;
      }
      .tm-section-head h3 { margin: 0 0 3px; font-size: 14px; font-weight: 600; letter-spacing: -0.005em; }
      .tm-section-head p  { margin: 0; color: var(--tm-text-faint); font-size: 12.5px; }
      .tm-section-body { padding: 0; }
      .tm-setting-row {
        display: grid; grid-template-columns: 280px 1fr;
        gap: 20px; align-items: center;
        padding: 14px 20px;
        border-top: 1px solid var(--tm-border-soft);
      }
      .tm-setting-row:first-child { border-top: 0; }
      .tm-setting-label { color: var(--tm-text); font-size: 13px; font-weight: 500; }
      .tm-setting-label small { display: block; color: var(--tm-text-faint); font-weight: 400; font-size: 12px; margin-top: 2px; }
      .tm-setting-row ha-textfield,
      .tm-setting-row ha-select {
        max-width: 360px;
      }
      .tm-settings-foot {
        display: flex; justify-content: flex-end;
        padding-top: 8px;
      }

      /* Switch (HA native ha-switch) */
      ha-switch {
        --mdc-theme-secondary: var(--primary-color);
      }

      /* Dialog */
      .tm-scrim {
        position: fixed; inset: 0;
        background: rgba(0,0,0,0.5);
        display: flex; align-items: flex-start; justify-content: center;
        padding: 60px 20px; z-index: 100;
        overflow-y: auto;
        animation: tm-scrim-in 0.18s var(--tm-easing);
      }
      @keyframes tm-scrim-in { from { opacity: 0; } to { opacity: 1; } }
      .tm-dialog {
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-lg);
        width: 100%; max-width: 560px;
        box-shadow: var(--tm-shadow-lg);
        display: flex; flex-direction: column;
        max-height: calc(100vh - 120px);
        overflow: hidden;
        animation: tm-dialog-in 0.2s var(--tm-easing);
      }
      @keyframes tm-dialog-in { from { opacity: 0; transform: translateY(8px) scale(0.985); } to { opacity: 1; transform: none; } }

      .tm-dialog-head {
        padding: 18px 22px;
        border-bottom: 1px solid var(--tm-border-soft);
        display: flex; align-items: center;
      }
      .tm-dialog-head h2 {
        margin: 0; font-size: 16px; font-weight: 600;
        letter-spacing: -0.01em;
        flex: 1;
      }
      .tm-dialog-body { padding: 16px 20px; overflow-y: auto; }
      .tm-dialog-foot {
        padding: 12px 20px;
        border-top: 1px solid var(--tm-border-soft);
        background: var(--tm-surface-2);
        display: flex; justify-content: flex-end; gap: 8px;
      }

      .tm-field { display: block; margin-bottom: 14px; }
      .tm-field-label {
        display: block; color: var(--tm-text);
        font-size: 12.5px; margin-bottom: 5px;
        font-weight: 500;
      }
      .tm-field ha-textfield, .tm-field ha-select {
        display: block; width: 100%;
      }
      .tm-textarea {
        width: 100%;
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
        padding: 7px 10px;
        color: var(--tm-text);
        font-size: 13px;
        font-family: inherit;
        box-sizing: border-box;
        box-shadow: var(--tm-shadow-xs);
        transition: all 0.1s var(--tm-easing);
      }
      .tm-textarea:focus {
        outline: 0;
        border-color: var(--tm-accent);
        box-shadow: var(--tm-shadow-focus);
      }
      .tm-ep { position: relative; }
      .tm-ep-search-wrap {
        display: flex; align-items: center;
        background: var(--tm-surface-0); border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm); padding: 0 10px;
        box-shadow: var(--tm-shadow-xs); transition: all 0.1s var(--tm-easing);
      }
      .tm-ep-search-wrap:focus-within {
        border-color: var(--tm-accent);
        box-shadow: var(--tm-shadow-focus);
      }
      .tm-ep-search-icon {
        --mdc-icon-size: 18px;
        color: var(--tm-text-faint); flex-shrink: 0; margin-right: 6px;
      }
      .tm-ep-input {
        flex: 1; border: 0; background: transparent; outline: 0;
        color: var(--tm-text); font-size: 13px; font-family: inherit;
        padding: 8px 0; width: 100%;
      }
      .tm-ep-input::placeholder { color: var(--tm-text-faint); }
      .tm-ep-selected {
        display: flex; align-items: center; gap: 8px;
        background: var(--tm-surface-0); border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm); padding: 6px 10px;
        cursor: pointer; transition: all 0.1s var(--tm-easing);
        box-shadow: var(--tm-shadow-xs);
      }
      .tm-ep-selected:hover { border-color: var(--tm-accent); }
      .tm-ep-selected-icon { --mdc-icon-size: 20px; color: var(--tm-text-muted); flex-shrink: 0; }
      .tm-ep-selected-text {
        flex: 1; font-size: 13px; color: var(--tm-text);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .tm-entity-clear {
        width: 20px; height: 20px;
        border: 0; background: var(--tm-surface-2);
        border-radius: 50%; cursor: pointer;
        font-size: 11px; color: var(--tm-text-faint);
        display: grid; place-items: center;
        font-family: inherit; flex-shrink: 0;
      }
      .tm-entity-clear:hover { background: var(--tm-danger-soft); color: var(--tm-danger); }
      .tm-ep-dropdown {
        position: absolute; top: 100%; left: 0; right: 0;
        max-height: 260px; overflow-y: auto;
        background: var(--tm-surface-0); border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius); z-index: 200;
        margin-top: 4px; padding: 4px 0;
        box-shadow: var(--tm-shadow-lg);
      }
      .tm-ep-option {
        display: flex; align-items: center; gap: 10px;
        padding: 8px 12px; cursor: pointer;
        transition: background 0.08s;
      }
      .tm-ep-option:hover { background: var(--tm-surface-hover); }
      .tm-ep-option-icon { --mdc-icon-size: 20px; color: var(--tm-text-muted); flex-shrink: 0; }
      .tm-ep-option-text { flex: 1; min-width: 0; }
      .tm-ep-id { font-size: 13px; color: var(--tm-text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .tm-ep-name { font-size: 11px; color: var(--tm-text-muted); margin-top: 1px; font-family: ui-monospace, monospace; }
      .tm-field-hint {
        display: block; color: var(--tm-text-faint);
        font-size: 11.5px; margin-top: 4px; line-height: 1.5;
      }
      .tm-field-hint code {
        font-family: ui-monospace, "SF Mono", Menlo, monospace;
        background: var(--tm-surface-2); padding: 1px 5px;
        border-radius: 3px; font-size: 11px;
      }
      .tm-field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
      .tm-textarea { resize: vertical; min-height: 100px; line-height: 1.5; }

      .tm-field ha-icon-picker,
      .tm-section-body ha-icon-picker {
        display: block; width: 100%;
      }

      /* Chip multi-select */
      .tm-chip-row { display: flex; gap: 6px; flex-wrap: wrap; }
      .tm-chip-btn {
        background: var(--tm-surface-0);
        color: var(--tm-text-muted);
        border: 1px solid var(--tm-border);
        padding: 4px 10px; border-radius: 999px;
        font-size: 12.5px; font-weight: 500;
        font-family: inherit;
        cursor: pointer;
        transition: all 0.1s var(--tm-easing);
      }
      .tm-chip-btn:hover { color: var(--tm-text); border-color: var(--tm-border-strong); }
      .tm-chip-on {
        background: var(--tm-accent-soft);
        color: var(--tm-accent-text);
        border-color: var(--tm-accent-border);
      }

      .tm-day-row { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; }
      .tm-day-btn {
        background: var(--tm-surface-0);
        color: var(--tm-text-muted);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
        padding: 8px 0;
        font-size: 11.5px; font-weight: 600;
        font-family: inherit; cursor: pointer;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        transition: all 0.1s var(--tm-easing);
      }
      .tm-day-btn:hover { color: var(--tm-text); border-color: var(--tm-border-strong); }
      .tm-day-on {
        background: var(--tm-accent); color: var(--text-primary-color, #fff);
        border-color: var(--tm-accent);
      }

      .tm-check-row {
        display: flex; align-items: flex-start; gap: 14px;
        padding: 12px 0;
        border-top: 1px solid var(--tm-border-soft);
      }
      .tm-check-row:first-child { border-top: 0; padding-top: 0; }
      .tm-check-row > div { flex: 1; }
      .tm-check-title { font-size: 13px; color: var(--tm-text); font-weight: 500; }

      details.tm-advanced {
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
        margin-top: 16px;
        overflow: hidden;
      }
      details.tm-advanced summary {
        cursor: pointer; padding: 12px 14px;
        color: var(--tm-text-muted); font-size: 12px; font-weight: 500;
        user-select: none; list-style: none;
        display: flex; align-items: center; gap: 8px;
      }
      details.tm-advanced summary::-webkit-details-marker { display: none; }
      details.tm-advanced summary::before {
        content: "▸";
        transition: transform 0.15s var(--tm-easing);
        color: var(--tm-text-faint);
        font-size: 10px;
      }
      details.tm-advanced[open] summary::before { transform: rotate(90deg); }
      details.tm-advanced > div {
        padding: 14px;
        border-top: 1px solid var(--tm-border-soft);
      }

      /* Reorder dialog */
      .tm-reorder-list { display: flex; flex-direction: column; gap: 4px; margin-top: 12px; }
      .tm-reorder-item {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 12px;
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
        cursor: grab;
        transition: all 0.12s var(--tm-easing);
      }
      .tm-reorder-item:hover { border-color: var(--tm-accent); background: var(--tm-surface-2); }
      .tm-reorder-item.tm-dragging { opacity: 0.4; }
      .tm-reorder-handle { color: var(--tm-text-faint); cursor: grab; font-size: 18px; user-select: none; }
      .tm-reorder-name { flex: 1; font-size: 13px; font-weight: 500; }
      .tm-reorder-points { color: var(--tm-accent); font-weight: 600; font-size: 13px; }

      /* Toast */
      .tm-toast {
        position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
        padding: 10px 16px; border-radius: var(--tm-radius);
        font-size: 13px; font-weight: 500;
        box-shadow: var(--tm-shadow);
        z-index: 200;
        animation: tm-toast-in 0.2s var(--tm-easing);
      }
      @keyframes tm-toast-in { from { opacity: 0; transform: translate(-50%, 8px); } to { opacity: 1; transform: translateX(-50%); } }
      .tm-toast-ok  { background: var(--tm-positive); color: var(--text-primary-color, #fff); }
      .tm-toast-err { background: var(--tm-danger); color: var(--text-primary-color, #fff); }

      /* Templates */
      .tm-section-divider {
        display: flex; align-items: center; gap: 12px;
        margin: 20px 0 14px; font-size: 11.5px; font-weight: 600;
        color: var(--tm-text-faint); text-transform: uppercase; letter-spacing: 0.04em;
      }
      .tm-section-divider::after { content: ''; flex: 1; height: 1px; background: var(--tm-border); }
      .tm-tpl-icon {
        width: 40px; height: 40px; border-radius: 10px;
        background: var(--tm-accent-soft); border: 1px solid var(--tm-border);
        display: grid; place-items: center; flex-shrink: 0;
        color: var(--tm-accent); --mdc-icon-size: 20px;
      }
      .tm-tpl-picker-card { cursor: pointer; display: flex; flex-direction: column; gap: 10px; }
      .tm-tpl-picker-card:hover { border-color: var(--tm-accent); background: var(--tm-accent-soft); }
      .tm-tpl-picker-head { display: flex; align-items: center; gap: 12px; }
      .tm-tpl-picker-name { font-size: 15px; font-weight: 600; }
      .tm-tpl-chore-pills { display: flex; flex-wrap: wrap; gap: 5px; }
      .tm-tpl-chore-pill {
        font-size: 11px; padding: 2px 8px;
        background: var(--tm-surface-2); border-radius: 999px;
        color: var(--tm-text-muted); border: 1px solid var(--tm-border-soft);
      }
      .tm-manage-tpl {
        display: flex; align-items: center; gap: 14px;
        padding: 14px 18px; background: var(--tm-surface-0);
        border: 1px solid var(--tm-border); border-radius: var(--tm-radius-lg);
        margin-bottom: 10px; transition: all 0.15s;
      }
      .tm-manage-tpl:hover { border-color: var(--tm-border-strong); box-shadow: var(--tm-shadow-sm); }
      .tm-manage-tpl-locked { opacity: 0.65; }
      .tm-manage-tpl-locked:hover { border-color: var(--tm-border); box-shadow: none; }
      .tm-manage-tpl-info { flex: 1; }
      .tm-manage-tpl-name { font-size: 14px; font-weight: 600; }
      .tm-tpl-preview-card {
        background: var(--tm-surface-0); border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-lg); overflow: hidden; margin-bottom: 10px;
      }
      .tm-tpl-preview-card:hover { border-color: var(--tm-border-strong); }
      .tm-tpl-preview-header {
        display: flex; align-items: center; gap: 12px;
        padding: 12px 16px; cursor: pointer;
      }
      .tm-tpl-preview-header:hover { background: var(--tm-surface-hover); }
      .tm-tpl-expand { font-size: 11px; color: var(--tm-text-faint); transition: transform 0.2s; }
      .tm-tpl-expand.open { transform: rotate(90deg); }
      .tm-tpl-preview-name { font-size: 14px; font-weight: 600; flex: 1; }
      .tm-tpl-preview-summary { font-size: 12px; color: var(--tm-text-muted); display: flex; gap: 12px; }
      .tm-tpl-remove {
        width: 26px; height: 26px; border: none; background: transparent;
        border-radius: var(--tm-radius-sm); color: var(--tm-text-faint);
        cursor: pointer; display: grid; place-items: center; font-size: 14px;
      }
      .tm-tpl-remove:hover { background: var(--tm-danger-soft); color: var(--tm-danger); }
      .tm-tpl-preview-body { padding: 14px 16px; border-top: 1px solid var(--tm-border-soft); }
      .tm-tpl-confirm-bar {
        display: flex; align-items: center; justify-content: space-between; gap: 12px;
        padding: 16px 18px; margin-top: 16px;
        background: var(--tm-surface-0); border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-lg);
      }
      .tm-tpl-confirm-bar div { font-size: 13px; color: var(--tm-text-muted); }
      .tm-tpl-confirm-bar strong { color: var(--tm-text); }
      .tm-tpl-checklist { max-height: 320px; overflow-y: auto; }
      .tm-tpl-check-row {
        display: flex; align-items: center; gap: 10px;
        padding: 8px 0; border-bottom: 1px solid var(--tm-border-soft);
        font-size: 13px; cursor: pointer;
      }
      .tm-tpl-check-row:last-child { border-bottom: none; }
      .tm-tpl-check-row input[type="checkbox"] { width: 16px; height: 16px; accent-color: var(--tm-accent); }
      .tm-day-pills { display: flex; gap: 6px; flex-wrap: wrap; }
      .tm-day-pill {
        padding: 5px 12px; border: 1px solid var(--tm-border); border-radius: 999px;
        font-size: 12px; font-weight: 500; cursor: pointer;
        background: var(--tm-surface-0); color: var(--tm-text-muted); transition: all 0.1s;
        user-select: none;
      }
      .tm-day-pill.active { background: var(--tm-accent); color: var(--text-primary-color, #fff); border-color: var(--tm-accent); }

      /* ===== Mobile / narrow ===== */
      @media (max-width: 900px) {
        .tm-shell { grid-template-columns: 1fr; }
        .tm-sidebar { display: none; }
        .tm-mobile-tabs {
          display: flex;
          overflow-x: auto;
          scrollbar-width: none;
          padding: 0 12px;
          background: var(--tm-surface-0);
          border-bottom: 1px solid var(--tm-border);
          flex-shrink: 0;
        }
        .tm-mobile-tabs::-webkit-scrollbar { display: none; }
        .tm-mtab {
          position: relative;
          background: transparent;
          border: 0;
          color: var(--tm-text-faint);
          padding: 12px 14px;
          cursor: pointer;
          font-size: 13px;
          font-weight: 500;
          font-family: inherit;
          white-space: nowrap;
          display: flex; align-items: center; gap: 6px;
          transition: color 0.1s var(--tm-easing);
        }
        .tm-mtab:hover { color: var(--tm-text); }
        .tm-mtab-active { color: var(--tm-text); }
        .tm-mtab-active::after {
          content: ""; position: absolute;
          left: 14px; right: 14px; bottom: -1px;
          height: 2px; background: var(--tm-accent);
          border-radius: 2px 2px 0 0;
        }
        .tm-mtab-pill {
          background: var(--tm-surface-2);
          color: var(--tm-text-muted);
          font-size: 10.5px; font-weight: 600;
          padding: 1px 6px; border-radius: 999px;
        }
        .tm-mtab-active .tm-mtab-pill {
          background: var(--tm-accent-soft);
          color: var(--tm-accent-text);
        }
        .tm-mtab-pill-urgent {
          background: var(--tm-warning-soft) !important;
          color: var(--tm-warning) !important;
        }
        .tm-body { padding: 16px; }
        .tm-toolbar { flex-direction: column; align-items: stretch; }
        .tm-search-wrap { max-width: none; }
        .tm-dialog { max-width: none; border-radius: 0; max-height: 100vh; height: 100vh; }
        .tm-scrim { padding: 0; }
        .tm-dialog-body .tm-field-row { grid-template-columns: 1fr; }
        .tm-setting-row { grid-template-columns: 1fr; gap: 6px; padding: 12px 16px; }
        .tm-section-head, .tm-setting-row { padding-left: 16px; padding-right: 16px; }
        .tm-timeline-row { grid-template-columns: 1fr auto; }
        .tm-timeline-time, .tm-timeline-icon { display: none; }
      }
    </style>`;
  }
}

customElements.define("taskmate-panel", TaskMatePanel);
