/**
 * TaskMate admin panel — sidebar entry at /taskmate-admin.
 *
 * HA-native styling:
 *   - All custom --tm-* tokens now map to HA theme variables.
 *   - Dark mode handled automatically via HA vars.
 *   - Version extracted from resource URL (?v=x.x.x), same as cards.
 */

const PANEL_VERSION = (() => {
  try { return new URL(import.meta.url).searchParams.get("v") || "?"; } catch (_) {}
  const el = document.querySelector('script[src*="/taskmate-panel.js"]');
  return el ? new URLSearchParams(el.src.split("?")[1] || "").get("v") || "?" : "?";
})();

const TABS = [
  { id: "children",  lk: "panel.tab_children" },
  { id: "activity",  lk: "panel.tab_activity" },
  { id: "chores",    lk: "panel.tab_chores" },
  { id: "rewards",   lk: "panel.tab_rewards" },
  { id: "penalties", lk: "panel.tab_penalties" },
  { id: "bonuses",   lk: "panel.tab_bonuses" },
  { id: "groups",    lk: "panel.tab_groups" },
  { id: "badges",    lk: "panel.tab_badges" },
  { id: "templates",     lk: "panel.tab_templates" },
  { id: "notifications", lk: "panel.tab_notifications" },
  { id: "audit",         lk: "panel.tab_audit" },
  { id: "settings",      lk: "panel.tab_settings", label: "⚙" },
];

const BADGE_METRICS = [
  { v: "total_points",  lk: "badge.metric_total_points" },
  { v: "total_chores",  lk: "badge.metric_total_chores" },
  { v: "total_rewards", lk: "badge.metric_total_rewards" },
  { v: "current_streak", lk: "badge.metric_current_streak" },
  { v: "best_streak",   lk: "badge.metric_best_streak" },
  { v: "perfect_weeks", lk: "badge.metric_perfect_weeks" },
  { v: "first_chore",   lk: "badge.metric_first_chore" },
  { v: "first_reward",  lk: "badge.metric_first_reward" },
];
const BADGE_BOOL_METRICS = ["first_chore", "first_reward"];
const BADGE_OPERATORS = ["≥", "=", "≤", ">", "<", "≠"];
const BADGE_OP_VALUES = { "≥": ">=", "=": "==", "≤": "<=", ">": ">", "<": "<", "≠": "!=" };
const BADGE_TIERS = [
  { v: "bronze",   lk: "badge.tier_bronze" },
  { v: "silver",   lk: "badge.tier_silver" },
  { v: "gold",     lk: "badge.tier_gold" },
  { v: "platinum", lk: "badge.tier_platinum" },
];

const SCHEDULE_MODES = [
  { v: "specific_days", lk: "panel.schedule_specific_days" },
  { v: "recurring",     lk: "panel.schedule_recurring" },
  { v: "one_shot",      lk: "panel.schedule_one_shot" },
];

const RECURRENCES = [
  { v: "every_2_days",   lk: "panel.recurrence_every_2_days" },
  { v: "weekly",         lk: "panel.recurrence_weekly" },
  { v: "every_2_weeks",  lk: "panel.recurrence_every_2_weeks" },
  { v: "monthly",        lk: "panel.recurrence_monthly" },
  { v: "every_3_months", lk: "panel.recurrence_every_3_months" },
  { v: "every_6_months", lk: "panel.recurrence_every_6_months" },
];

const FIRST_OCCURRENCE = [
  { v: "available_immediately",     lk: "panel.first_occ_available_immediately" },
  { v: "wait_for_first_occurrence", lk: "panel.first_occ_wait" },
];

const ASSIGNMENT_MODES = [
  { v: "everyone",    lk: "panel.assign_everyone" },
  { v: "alternating", lk: "panel.assign_alternating" },
  { v: "random",      lk: "panel.assign_random" },
  { v: "balanced",    lk: "panel.assign_balanced" },
  { v: "first_come",  lk: "panel.assign_first_come" },
  { v: "unassigned",  lk: "panel.assign_unassigned" },
];

const VISIBILITY_OPS = [
  { v: "none",       lk: "panel.vis_none" },
  { v: "equals",     lk: "panel.vis_equals" },
  { v: "not_equals", lk: "panel.vis_not_equals" },
  { v: "gte",        lk: "panel.vis_gte" },
  { v: "lte",        lk: "panel.vis_lte" },
  { v: "gt",         lk: "panel.vis_gt" },
  { v: "lt",         lk: "panel.vis_lt" },
];

const COMPLETION_SOUNDS = [
  "none", "coin", "levelup", "fanfare", "chime", "powerup", "undo",
  "fart1", "fart2", "fart3", "fart4", "fart5", "fart6", "fart7",
  "fart8", "fart9", "fart10", "fart_random",
];

const DAYS = [
  { v: "monday",    lk: "panel.day_mon" },
  { v: "tuesday",   lk: "panel.day_tue" },
  { v: "wednesday", lk: "panel.day_wed" },
  { v: "thursday",  lk: "panel.day_thu" },
  { v: "friday",    lk: "panel.day_fri" },
  { v: "saturday",  lk: "panel.day_sat" },
  { v: "sunday",    lk: "panel.day_sun" },
];

const STREAK_MODES = [
  { v: "reset", lk: "panel.streak_reset" },
  { v: "pause", lk: "panel.streak_pause" },
];

const TASK_GROUP_POLICIES = [
  { v: "sticky", lk: "panel.group_policy_sticky" },
  { v: "spread", lk: "panel.group_policy_spread" },
];


class TaskMatePanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._state = null;
    this._error = null;
    this._loading = false;
    this._timePeriodsDraft = null;  // local edit state for the period editor
    this._vacationDraft = null;     // local edit state for the vacation editor
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
    this._badgesSubTab = "catalogue"; // "catalogue" | "custom" | "history"
    this._rendered = false;
    this._shellReady = false;
    this._zoneCache = {};
    this._cachedStyles = null;
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
    this._showIds = localStorage.getItem("taskmate-show-ids") === "true";
    this._ensureHaComponents();
  }

  async _ensureHaComponents() {
    if (customElements.get("ha-textfield")) return;
    try { await window.loadCardHelpers?.(); } catch (_) {}
    await Promise.all([
      customElements.whenDefined("ha-textfield").catch(() => {}),
      customElements.whenDefined("ha-switch").catch(() => {}),
      customElements.whenDefined("ha-icon-picker").catch(() => {}),
    ]);
    if (this._rendered) this._render();
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
    // Render on first hass, or if HA pushed a fresh hass after a reconnect
    // that completed while the tab was already visible (no visibilitychange
    // to lean on) and our shell was stripped out in the meantime.
    if (!this._rendered || !this.querySelector(".tm-shell")) this._render();
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
    // Render if we never have, or if our content was stripped while we were
    // detached (HA cached us through a connection drop, or SPA nav away/back).
    // _render's self-heal rebuilds the shell when .tm-shell is missing.
    if (!this._rendered || !this.querySelector(".tm-shell")) this._render();
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
    // Tab woke up. HA may have stripped our DOM while the socket was down —
    // repaint cached state immediately if the shell is gone, then always
    // refetch so returning to the tab shows current data. This mirrors how
    // Lovelace repaints on reconnect and also clears any staleness from
    // changes made on another device while the tab was idle.
    if (!this.querySelector(".tm-shell")) this._render();
    this._fetchState();
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


  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this._hass, key, params) : key;
  }

  // Transaction reasons are stored in English in the DB (e.g. "Penalty: Messy room").
  // Mirror the activity-card mapping so panel views render in the user's language.
  _translateReason(reason) {
    if (!reason) return reason;
    const prefixMap = [
      ['Allocated to pool:', 'activity.reason_allocated_to_pool'],
      ['Pool refund (reward expired):', 'activity.reason_pool_refund_expired'],
      ['Pool refund (reward sold out):', 'activity.reason_pool_refund_sold_out'],
      ['Pool refund (reward cost reduced):', 'activity.reason_pool_refund_cost_reduced'],
      ['Penalty:', 'activity.reason_penalty'],
      ['Bonus:', 'activity.reason_bonus'],
    ];
    for (const [prefix, key] of prefixMap) {
      if (reason.startsWith(prefix)) {
        const name = reason.slice(prefix.length).trim();
        return this._t(key, { name });
      }
    }
    if (reason.startsWith('Perfect week bonus!')) {
      return this._t('activity.reason_perfect_week');
    }
    const weekendMatch = reason.match(/^Weekend bonus \(×(\d+)\)$/);
    if (weekendMatch) {
      return this._t('activity.reason_weekend_bonus', { multiplier: weekendMatch[1] });
    }
    const streakMatch = reason.match(/^Streak milestone bonus \((\d+) day streak!\)$/);
    if (streakMatch) {
      return this._t('activity.reason_streak_milestone', { days: streakMatch[1] });
    }
    return reason;
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
    }
    // Fetch notifications state separately — failure here must not abort
    // the main state load or its retry logic.
    try {
      this._notifState = await this._hass.callWS({ type: "taskmate/notifications/get_state" });
      this._notifyServices = await this._hass.callWS({ type: "taskmate/notifications/list_notify_services" });
    } catch (e) {
      console.warn("TaskMate notifications state fetch failed", e);
      this._notifState = null;
      this._notifyServices = [];
    }
    this._loading = false;
    this._render();
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
      if (!confirm(this._t("panel.confirm_unsaved"))) return;
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
    if (act === "toggle-ha-menu") { this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true })); return; }
    if (act === "copy-id") { navigator.clipboard.writeText(t.dataset.id).then(() => this._showToast("ok", this._t("panel.toast_copied"))); return; }

    // Children
    if (act === "add-child")    { this._openChildDialog(null); return; }
    if (act === "edit-child")   { this._openChildDialog(t.dataset.id); return; }
    if (act === "delete-child") { this._confirmDelete("child", t.dataset.id); return; }
    if (act === "save-child")   { this._doSaveChild(); return; }
    if (act === "reorder-chores-for-child") { this._openReorderDialog(t.dataset.id); return; }
    if (act === "reorder-move") { this._moveInReorder(t.dataset.dragId, Number(t.dataset.dir)); return; }
    if (act === "save-chore-order") { this._dialog && this._dialog.data && this._dialog.data.global ? this._doSaveGlobalChoreOrder() : this._doSaveChoreOrder(); return; }
    if (act === "reorder-chores-global") { this._openGlobalReorderDialog(); return; }

    // Chores
    if (act === "add-chore")    { this._openChoreDialog(null); return; }
    if (act === "edit-chore")   { this._openChoreDialog(t.dataset.id); return; }
    if (act === "clone-chore")  { this._doCloneChore(t.dataset.id); return; }
    if (act === "delete-chore") { this._confirmDelete("chore", t.dataset.id); return; }
    if (act === "parent-complete-chore") { this._doParentComplete(t.dataset.id); return; }
    if (act === "skip-chore") { this._doSkipChore(t.dataset.id); return; }
    if (act === "toggle-chore-active") { this._doToggleChoreActive(t.dataset.id); return; }
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

    // Badges
    if (act === "badges-subtab") { this._badgesSubTab = t.dataset.sub; this._render(); return; }
    if (act === "add-badge")    { this._openBadgeDialog(null); return; }
    if (act === "edit-badge")   { this._openBadgeDialog(t.dataset.id); return; }
    if (act === "delete-badge") { this._confirmDeleteBadge(t.dataset.id); return; }
    if (act === "save-badge")   { this._doSaveBadge(); return; }
    if (act === "toggle-badge-enabled") { this._doToggleBadgeEnabled(t.dataset.id, t.dataset.enabled === "true"); return; }
    if (act === "award-badge")  { this._openAwardDialog(t.dataset.id); return; }
    if (act === "do-award-badge") { this._doAwardBadge(t.dataset.id, this._dialog?.data?.child_id || ""); return; }
    if (act === "revoke-badge") { this._doRevokeBadge(t.dataset.id, t.dataset.name); return; }
    if (act === "rebuild-badges") { this._doRebuildBadges(); return; }
    if (act === "badge-add-criterion") { this._syncIconPickers(); if (this._dialog?.data?.criteria) { this._dialog.data.criteria.push({ metric: "total_points", operator: ">=", value: 1 }); this._render(); } return; }
    if (act === "badge-remove-criterion") { this._syncIconPickers(); if (this._dialog?.data?.criteria) { this._dialog.data.criteria.splice(Number(t.dataset.idx), 1); this._render(); } return; }
    if (act === "badge-toggle-assigned") { this._syncIconPickers(); this._toggleArrayField("assigned_to", t.dataset.id); return; }

    // Notifications tab
    if (act === "notif-set-master")       { this._notifSetMaster(t.dataset.typeId, t.checked); return; }
    if (act === "notif-send-test")        { this._doSendTestNotif(t.dataset.typeId); return; }
    if (act === "notif-set-route")        { this._notifSetRoute(t.dataset.typeId, t.dataset.recipientId, t.checked, t.dataset.time || null); return; }
    if (act === "notif-set-route-time")   { /* handled in _onChange */ return; }
    if (act === "notif-set-child-notify") { /* handled in _onChange */ return; }
    if (act === "notif-set-parent-notify"){ /* handled in _onChange */ return; }
    if (act === "notif-rename-parent")    { /* handled in _onChange */ return; }
    if (act === "notif-set-streak-cutoff"){ /* handled in _onChange */ return; }
    if (act === "notif-add-parent")       { this._notifAddParent(); return; }
    if (act === "notif-delete-parent")    { this._notifDeleteParent(t.dataset.parentId); return; }
    if (act === "notif-add-custom")       { this._notifAddCustom(); return; }
    if (act === "notif-delete-custom")    { this._notifDeleteCustom(t.dataset.customId); return; }
    if (act === "notif-update-custom")    { /* handled in _onChange */ return; }
    if (act === "notif-toggle-custom")    { this._notifToggleCustom(t.dataset.customId, t.checked); return; }
    if (act === "notif-toggle-day")       { this._notifToggleDay(t.dataset.customId, Number(t.dataset.day), t.checked); return; }
    if (act === "notif-toggle-recipient") { this._notifToggleRecipient(t.dataset.customId, t.dataset.recipientId); return; }

    // Settings
    if (act === "save-settings") { this._doSaveSettings(); return; }
    if (act === "config-export") { this._doExportConfig(); return; }
    if (act === "config-import") { this.querySelector("[data-role='config-import-file']")?.click(); return; }

    // Audit log
    if (act === "audit-clear") { this._doClearAudit(); return; }

    // Undo a points transaction (penalty / bonus)
    if (act === "undo-tx") { this._doUndoTransaction(t.dataset.id); return; }

    // Time-of-day period editor
    if (act === "tp-add") {
      this._syncTimePeriodInputs();
      this._timePeriodsDraft.push({ id: "", label: "", start: "", end: "", icon: "mdi:clock-outline" });
      this._render();
      return;
    }
    if (act === "tp-remove") {
      this._syncTimePeriodInputs();
      this._timePeriodsDraft.splice(Number(t.dataset.idx), 1);
      this._render();
      return;
    }
    if (act === "tp-reset") {
      this._timePeriodsDraft = this._defaultTimePeriods();
      this._render();
      return;
    }

    // Vacation / pause-mode editor
    if (act === "vac-add") {
      this._syncVacationInputs();
      this._vacationDraft.push({ id: "", name: "", start: "", end: "" });
      this._render();
      return;
    }
    if (act === "vac-remove") {
      this._syncVacationInputs();
      this._vacationDraft.splice(Number(t.dataset.idx), 1);
      this._render();
      return;
    }

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
    // Time-of-day period editor field edits
    const tpField = t.dataset?.tpField;
    const tpIdx = t.dataset?.tpIdx;
    if (tpField && tpIdx != null && this._timePeriodsDraft?.[Number(tpIdx)]) {
      this._timePeriodsDraft[Number(tpIdx)][tpField] = t.value;
      return;
    }
    // Vacation editor field edits
    const vacField = t.dataset?.vacField;
    const vacIdx = t.dataset?.vacIdx;
    if (vacField && vacIdx != null && this._vacationDraft?.[Number(vacIdx)]) {
      this._vacationDraft[Number(vacIdx)][vacField] = t.value;
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
    // Badge criterion field edits
    const bcField = t.dataset?.badgeCriterionField;
    const bcIdx = t.dataset?.badgeCriterionIdx;
    if (bcField && bcIdx != null && this._dialog?.data?.criteria?.[Number(bcIdx)]) {
      const val = (t.type === "number") ? (t.value === "" ? 1 : Number(t.value)) : t.value;
      this._dialog.data.criteria[Number(bcIdx)][bcField] = val;
      if (bcField === "metric") this._render(); // re-render to show/hide value input for bool metrics
      return;
    }
    // Dialog field
    if (this._dialog && t.dataset.field) {
      const field = t.dataset.field;
      // ha-switch / checkbox elements fire `input` on toggle in newer HA; their
      // `value` is the constant string "on", so read `.checked` instead — otherwise
      // a switch can never be set false (it always stores a truthy string). Mirrors _onChange.
      let value;
      if (t.type === "checkbox" || t.tagName === "HA-SWITCH") value = t.checked;
      else value = (t.type === "number") ? (t.value === "" ? null : Number(t.value)) : t.value;
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
    if (t.dataset.role === "config-import-file") {
      const file = t.files && t.files[0];
      t.value = "";  // allow re-selecting the same file later
      if (file) this._doImportConfig(file);
      return;
    }
    if (t.dataset.local === "show-ids") {
      this._showIds = t.checked;
      localStorage.setItem("taskmate-show-ids", this._showIds);
      this._render();
      return;
    }
    // Time-of-day period editor (time inputs fire change on blur)
    if (t.dataset?.tpField && t.dataset.tpIdx != null && this._timePeriodsDraft?.[Number(t.dataset.tpIdx)]) {
      this._timePeriodsDraft[Number(t.dataset.tpIdx)][t.dataset.tpField] = t.value;
      return;
    }
    // Vacation editor (date inputs fire change on blur)
    if (t.dataset?.vacField && t.dataset.vacIdx != null && this._vacationDraft?.[Number(t.dataset.vacIdx)]) {
      this._vacationDraft[Number(t.dataset.vacIdx)][t.dataset.vacField] = t.value;
      return;
    }
    // Notifications tab change-driven actions
    if (t.dataset.act === "notif-set-route-time") {
      this._notifSetRoute(t.dataset.typeId, t.dataset.recipientId, true, t.value || null);
      return;
    }
    if (t.dataset.act === "notif-set-child-notify") {
      this._notifSetChildNotify(t.dataset.childId, t.value);
      return;
    }
    if (t.dataset.act === "notif-set-parent-notify") {
      const p = (this._notifState && this._notifState.recipients && this._notifState.recipients.parents || []).find(x => x.id === t.dataset.parentId);
      if (p) this._notifUpsertParent({ ...p, notify_service: t.value });
      return;
    }
    if (t.dataset.act === "notif-rename-parent") {
      const p = (this._notifState && this._notifState.recipients && this._notifState.recipients.parents || []).find(x => x.id === t.dataset.parentId);
      if (p) this._notifUpsertParent({ ...p, name: t.value });
      return;
    }
    if (t.dataset.act === "notif-set-streak-cutoff") {
      this._notifSetStreakCutoff(t.value);
      return;
    }
    if (t.dataset.act === "notif-update-custom") {
      this._notifUpdateCustomField(t.dataset.customId, t.dataset.field, t.value);
      return;
    }
    // Badge criterion select changes
    const bcField2 = t.dataset?.badgeCriterionField;
    const bcIdx2 = t.dataset?.badgeCriterionIdx;
    if (bcField2 && bcIdx2 != null && this._dialog?.data?.criteria?.[Number(bcIdx2)]) {
      this._dialog.data.criteria[Number(bcIdx2)][bcField2] = t.value;
      if (bcField2 === "metric") this._render();
      return;
    }
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
    const t = e.target;
    // Period editor icon pickers live outside any dialog
    if (t.dataset?.tpField && t.dataset.tpIdx != null && this._timePeriodsDraft?.[Number(t.dataset.tpIdx)]) {
      const val = e.detail && "value" in e.detail ? e.detail.value : t.value;
      this._timePeriodsDraft[Number(t.dataset.tpIdx)][t.dataset.tpField] = val == null ? "" : val;
      return;
    }
    if (!this._dialog) return;
    if (!t.dataset || !t.dataset.field) return;
    const v = e.detail && "value" in e.detail ? e.detail.value : t.value;
    this._dialog.data[t.dataset.field] = v == null ? "" : v;
  }

  _syncIconPickers() {
    if (!this._dialog) return;
    this.querySelectorAll("ha-icon-picker[data-field]").forEach(el => {
      if (el.value != null) this._dialog.data[el.dataset.field] = el.value;
    });
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

  // Up/down buttons — the reliable cross-device path (native HTML5 drag does
  // not fire on touchscreens, so mobile users reorder via these).
  _moveInReorder(id, dir) {
    if (!this._dialog || this._dialog.kind !== "reorder") return;
    const order = [...(this._dialog.data.order || [])];
    const from = order.indexOf(id);
    if (from < 0) return;
    const to = from + dir;
    if (to < 0 || to >= order.length) return;
    order.splice(from, 1);
    order.splice(to, 0, id);
    this._dialog.data.order = order;
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
    const labels = { child: this._t("panel.entity_child"), chore: this._t("panel.entity_chore"), reward: this._t("panel.entity_reward"), penalty: this._t("panel.entity_penalty"), bonus: this._t("panel.entity_bonus"), group: this._t("panel.entity_group") };
    const collectionKey = { child: "children", chore: "chores", reward: "rewards", penalty: "penalties", bonus: "bonuses", group: "task_groups" }[kind];
    const item = (this._state[collectionKey] || []).find(x => x.id === id);
    if (!item) return;
    const extraWarn = kind === "child"
      ? `\n\n${this._t("panel.confirm_delete_child_extra")}`
      : kind === "reward"
      ? `\n\n${this._t("panel.confirm_delete_reward_extra")}`
      : kind === "chore"
      ? `\n\n${this._t("panel.confirm_delete_chore_extra")}`
      : "";
    if (!confirm(`${this._t("panel.confirm_delete_prompt", {kind: labels[kind].toLowerCase(), name: item.name})}${extraWarn}\n\n${this._t("panel.confirm_delete_suffix")}`)) return;
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
    if (!ok) { this._showToast("err", this._t("panel.toast_delete_failed", {error: err})); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_deleted"));
  }

  // ---- Parent complete --------------------------------------------------
  async _doParentComplete(choreId) {
    if (!confirm(this._t("panel.parent_complete_confirm"))) return;
    const { ok, err } = await this._callWS({ type: "taskmate/parent_complete_chore", chore_id: choreId });
    if (!ok) { this._showToast("err", this._t("panel.parent_complete_failed", {error: err})); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.parent_complete_success"));
  }

  // ---- Skip chore --------------------------------------------------------
  async _doSkipChore(choreId) {
    const s = this._state.settings || {};
    if (s.skip_confirmation_enabled !== false && !confirm(this._t("panel.skip_chore_confirm"))) return;
    const { ok, err } = await this._callService("skip_chore", { chore_id: choreId });
    if (!ok) { this._showToast("err", this._t("panel.toast_skip_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_skip_done"));
  }

  async _doToggleChoreActive(choreId) {
    const chore = (this._state.chores || []).find(c => c.id === choreId);
    if (!chore) return;
    const newEnabled = chore.enabled === false;
    const { ok, err } = await this._callWS({ type: "taskmate/update_chore", chore_id: choreId, enabled: newEnabled });
    if (!ok) { this._showToast("err", this._t("panel.toast_toggle_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", newEnabled ? this._t("panel.toast_chore_activated") : this._t("panel.toast_chore_deactivated"));
  }

  // ---- Approvals -------------------------------------------------------
  async _doApprove(kind, id) {
    const wsType = kind === "chore" ? "taskmate/approve_chore" : "taskmate/approve_reward";
    const idField = kind === "chore" ? "completion_id" : "claim_id";
    const { ok, err } = await this._callWS({ type: wsType, [idField]: id });
    if (!ok) { this._showToast("err", this._t("panel.toast_approve_failed", {error: err})); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_approved"));
  }

  async _doReject(kind, id) {
    const wsType = kind === "chore" ? "taskmate/reject_chore" : "taskmate/reject_reward";
    const idField = kind === "chore" ? "completion_id" : "claim_id";
    const { ok, err } = await this._callWS({ type: wsType, [idField]: id });
    if (!ok) { this._showToast("err", this._t("panel.toast_reject_failed", {error: err})); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_rejected"));
  }

  // ---- Children --------------------------------------------------------
  async _openChildDialog(id) {
    await this._ensureHaUsers();
    if (id) {
      const c = (this._state.children || []).find(x => x.id === id);
      if (!c) return;
      this._openDialog({ kind: "child", mode: "edit", data: {
        id: c.id, name: c.name || "", avatar: c.avatar || "mdi:account-circle",
        availability_entity: c.availability_entity || "",
        availability_inverted: !!c.availability_inverted,
        unavailability_entity: c.unavailability_entity || "",
        linked_user_id: c.linked_user_id || "",
      } });
    } else {
      this._openDialog({ kind: "child", mode: "add", data: {
        name: "", avatar: "mdi:account-circle", availability_entity: "",
        availability_inverted: false, unavailability_entity: "",
        linked_user_id: "",
      } });
    }
  }

  async _ensureHaUsers() {
    if (this._haUsers) return;
    const { ok, res } = await this._callWS({ type: "taskmate/list_ha_users" });
    this._haUsers = (ok && res && Array.isArray(res.users)) ? res.users : [];
  }

  async _doSaveChild() {
    this._syncIconPickers();
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", this._t("panel.toast_name_required")); return; }
    const wasAdd = this._dialog.mode === "add";
    const payload = wasAdd
      ? { type: "taskmate/add_child", name: d.name.trim(), avatar: d.avatar || "mdi:account-circle",
          availability_entity: d.availability_entity || "", availability_inverted: !!d.availability_inverted,
          unavailability_entity: d.unavailability_entity || "", linked_user_id: d.linked_user_id || "" }
      : { type: "taskmate/update_child", child_id: d.id, name: d.name.trim(), avatar: d.avatar || "mdi:account-circle",
          availability_entity: d.availability_entity || "", availability_inverted: !!d.availability_inverted,
          unavailability_entity: d.unavailability_entity || "", linked_user_id: d.linked_user_id || "" };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? this._t("panel.toast_child_added") : this._t("panel.toast_child_updated"));
  }

  // ---- Chore reorder ---------------------------------------------------
  _openReorderDialog(child_id) {
    const child = (this._state.children || []).find(c => c.id === child_id);
    if (!child) return;
    const childChores = (this._state.chores || []).filter(c =>
      c.assignment_mode !== "unassigned" && ((c.assigned_to || []).length === 0 || (c.assigned_to || []).includes(child_id))
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
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_order_saved"));
  }

  // ---- Global chore reorder ---------------------------------------------
  _openGlobalReorderDialog() {
    const allChores = this._state.chores || [];
    if (allChores.length < 2) return;
    const existingOrder = (this._state.chore_display_order || []).filter(id => allChores.find(c => c.id === id));
    const missing = allChores.map(c => c.id).filter(id => !existingOrder.includes(id));
    const order = [...existingOrder, ...missing];
    this._openDialog({ kind: "reorder", mode: "edit", data: { global: true, order, name: this._t("panel.tab_chores") } });
  }

  async _doSaveGlobalChoreOrder() {
    const d = this._dialog.data;
    const { ok, err } = await this._callWS({
      type: "taskmate/set_global_chore_order",
      chore_order: d.order || [],
    });
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_order_saved"));
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
    if (names.length === 0) { this._showToast("err", this._t("panel.toast_enter_chore_name")); return; }
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
    if (!ok) { this._showToast("err", this._t("panel.toast_bulk_add_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_bulk_added", {count: (res && res.count) || names.length}));
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
      if (!ok) { this._showToast("err", this._t("panel.toast_rename_failed", {error: err})); this._render(); return; }
      await this._fetchState();
      this._showToast("ok", this._t("panel.toast_renamed"));
    }
  }

  // ---- Chores ----------------------------------------------------------
  async _doCloneChore(id) {
    if (!id) return;
    const { ok, err } = await this._callWS({ type: "taskmate/clone_chore", chore_id: id });
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_chore_cloned"));
  }

  _openChoreDialog(id) {
    const blank = {
      name: "", description: "", points: 10,
      task_type: "standard",
      timed_rate_points: 10, timed_rate_minutes: 5, timed_max_daily_minutes: 0,
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
    if (!d.name || !d.name.trim()) { this._showToast("err", this._t("panel.toast_name_required")); return; }
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
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? this._t("panel.toast_chore_added") : this._t("panel.toast_chore_updated"));
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
    this._syncIconPickers();
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", this._t("panel.toast_name_required")); return; }
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
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? this._t("panel.toast_reward_added") : this._t("panel.toast_reward_updated"));
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
    this._syncIconPickers();
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", this._t("panel.toast_name_required")); return; }
    if (!d.points || d.points < 1) { this._showToast("err", this._t("panel.toast_points_required")); return; }
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
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", this._t(`panel.toast_${wasAdd ? "added" : "updated"}_${kind}`));
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
    if (!ok) { this._showToast("err", this._t("panel.toast_apply_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", this._t(kind === "penalty" ? "panel.toast_penalty_applied" : "panel.toast_bonus_applied"));
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
    if (!d.name || !d.name.trim()) { this._showToast("err", this._t("panel.toast_name_required")); return; }
    const wasAdd = this._dialog.mode === "add";
    const base = { name: d.name.trim(), policy: d.policy || "sticky", chore_ids: d.chore_ids || [] };
    const payload = wasAdd ? { type: "taskmate/add_task_group", ...base } : { type: "taskmate/update_task_group", group_id: d.id, ...base };
    const { ok, err } = await this._callWS(payload);
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", {error: err})); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? this._t("panel.toast_group_added") : this._t("panel.toast_group_updated"));
  }

  // ---- Time-of-day periods ----------------------------------------------
  _defaultTimePeriods() {
    return [
      { id: "morning",   label: "", start: "06:00", end: "12:00", icon: "mdi:weather-sunny" },
      { id: "afternoon", label: "", start: "12:00", end: "17:00", icon: "mdi:white-balance-sunny" },
      { id: "evening",   label: "", start: "17:00", end: "21:00", icon: "mdi:weather-sunset" },
      { id: "night",     label: "", start: "21:00", end: "23:59", icon: "mdi:weather-night" },
    ];
  }

  // Saved periods, falling back to the legacy flat keys / built-in defaults
  // for installs that haven't saved through the new editor yet.
  _effectiveTimePeriods() {
    const s = (this._state && this._state.settings) || {};
    if (Array.isArray(s.time_periods) && s.time_periods.length) {
      return s.time_periods.map(p => ({ ...p }));
    }
    return this._defaultTimePeriods().map(p => ({
      ...p,
      start: s[`time_${p.id}_start`] || p.start,
      end: s[`time_${p.id}_end`] || p.end,
    }));
  }

  _isBuiltinPeriod(id) {
    return ["morning", "afternoon", "evening", "night"].includes(id);
  }

  _timePeriodLabel(p) {
    if (p.label) return p.label;
    return this._isBuiltinPeriod(p.id) ? this._t(`panel.time_${p.id}`) : (p.id || "");
  }

  _timeCategoryOptions() {
    const opts = [{ v: "anytime", l: this._t("panel.time_anytime") }];
    for (const p of this._effectiveTimePeriods()) opts.push({ v: p.id, l: this._timePeriodLabel(p) });
    return opts;
  }

  _timeCategoryLabel(cat) {
    const c = cat || "anytime";
    if (c === "anytime") return this._t("panel.time_anytime");
    const p = this._effectiveTimePeriods().find(x => x.id === c);
    return p ? this._timePeriodLabel(p) : c;
  }

  _renderTimePeriodsSection() {
    if (!this._timePeriodsDraft) this._timePeriodsDraft = this._effectiveTimePeriods();
    const inUse = {};
    (this._state.chores || []).forEach(c => {
      const tc = c.time_category;
      if (tc && tc !== "anytime") inUse[tc] = (inUse[tc] || 0) + 1;
    });
    const rows = this._timePeriodsDraft.map((p, i) => {
      const used = p.id ? inUse[p.id] || 0 : 0;
      const placeholder = this._isBuiltinPeriod(p.id) ? this._t(`panel.time_${p.id}`) : this._t("panel.tp_label_placeholder");
      return `
            <div class="tm-setting-row tm-period-row">
              <ha-icon-picker data-tp-field="icon" data-tp-idx="${i}" data-current="${this._esc(p.icon || "mdi:clock-outline")}"></ha-icon-picker>
              <input type="text" class="tm-input" data-tp-field="label" data-tp-idx="${i}" value="${this._esc(p.label || "")}" placeholder="${this._esc(placeholder)}">
              <div class="tm-time-pair">
                <input type="time" class="tm-input" data-tp-field="start" data-tp-idx="${i}" value="${this._esc(p.start || "")}">
                <span>–</span>
                <input type="time" class="tm-input" data-tp-field="end" data-tp-idx="${i}" value="${this._esc(p.end || "")}">
              </div>
              ${used
                ? `<button type="button" class="tm-icon-btn tm-period-del" disabled title="${this._esc(this._t("panel.tp_in_use_title", { count: used }))}"><ha-icon icon="mdi:lock-outline"></ha-icon></button>`
                : `<button type="button" class="tm-icon-btn tm-period-del" data-act="tp-remove" data-idx="${i}" title="${this._esc(this._t("panel.tp_delete_title"))}"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>`}
              ${used ? `<div class="tm-period-inuse">${this._esc(this._t("panel.tp_in_use_hint", { count: used }))}</div>` : ""}
            </div>`;
    }).join("");
    return `
        <div class="tm-section">
          <div class="tm-section-head"><div><h3>${this._t("panel.settings_time_boundaries_title")}</h3><p class="tm-meta">${this._t("panel.settings_time_boundaries_hint")}</p></div></div>
          <div class="tm-section-body">
            ${rows}
            <div class="tm-setting-row tm-period-row tm-period-anytime">
              <ha-icon icon="mdi:clock-outline"></ha-icon>
              <div class="tm-setting-label">${this._t("panel.time_anytime")}<small>${this._t("panel.tp_anytime_hint")}</small></div>
            </div>
            <div class="tm-period-actions">
              <button type="button" class="tm-btn" data-act="tp-add"><ha-icon icon="mdi:plus"></ha-icon> ${this._t("panel.tp_add_period")}</button>
              <button type="button" class="tm-btn" data-act="tp-reset">${this._t("panel.tp_reset_defaults")}</button>
            </div>
          </div>
        </div>`;
  }

  // Pull current editor input values into the draft. Inputs also stream into
  // the draft via input/value-changed events; this is the safety net before
  // any re-render or save.
  _syncTimePeriodInputs() {
    if (!this._timePeriodsDraft) return;
    this.querySelectorAll("[data-tp-field]").forEach(el => {
      const idx = Number(el.dataset.tpIdx);
      const field = el.dataset.tpField;
      if (this._timePeriodsDraft[idx] && el.value != null) {
        this._timePeriodsDraft[idx][field] = el.value;
      }
    });
  }

  _renderVacationSection() {
    if (!this._vacationDraft) {
      const saved = (this._state?.settings?.vacation_periods) || [];
      this._vacationDraft = saved.map(p => ({ id: p.id || "", name: p.name || "", start: p.start || "", end: p.end || "" }));
    }
    const rows = this._vacationDraft.map((p, i) => `
            <div class="tm-setting-row tm-vacation-row">
              <input type="text" class="tm-input" data-vac-field="name" data-vac-idx="${i}" value="${this._esc(p.name || "")}" placeholder="${this._esc(this._t("panel.vacation_name_placeholder"))}">
              <div class="tm-time-pair">
                <input type="date" class="tm-input" data-vac-field="start" data-vac-idx="${i}" value="${this._esc(p.start || "")}">
                <span>–</span>
                <input type="date" class="tm-input" data-vac-field="end" data-vac-idx="${i}" value="${this._esc(p.end || "")}">
              </div>
              <button type="button" class="tm-icon-btn tm-period-del" data-act="vac-remove" data-idx="${i}" title="${this._esc(this._t("panel.vacation_delete_title"))}"><ha-icon icon="mdi:trash-can-outline"></ha-icon></button>
            </div>`).join("");
    return `
        <div class="tm-section">
          <div class="tm-section-head"><div><h3>${this._t("panel.settings_vacation_title")}</h3><p class="tm-meta">${this._t("panel.settings_vacation_hint")}</p></div></div>
          <div class="tm-section-body">
            ${rows || `<div class="tm-meta" style="padding: 4px 0 8px;">${this._t("panel.vacation_none")}</div>`}
            <div class="tm-period-actions">
              <button type="button" class="tm-btn" data-act="vac-add"><ha-icon icon="mdi:plus"></ha-icon> ${this._t("panel.vacation_add")}</button>
            </div>
          </div>
        </div>`;
  }

  _syncVacationInputs() {
    if (!this._vacationDraft) return;
    this.querySelectorAll("[data-vac-field]").forEach(el => {
      const idx = Number(el.dataset.vacIdx);
      const field = el.dataset.vacField;
      if (this._vacationDraft[idx] && el.value != null) this._vacationDraft[idx][field] = el.value;
    });
  }

  _validateTimePeriodsDraft() {
    const periods = [];
    for (const p of this._timePeriodsDraft) {
      const label = (p.label || "").trim();
      const id = (p.id || "").trim();
      const name = label || (this._isBuiltinPeriod(id) ? this._t(`panel.time_${id}`) : id);
      if (!label && !this._isBuiltinPeriod(id)) return { error: this._t("panel.tp_err_label_required") };
      if (!/^\d{2}:\d{2}$/.test(p.start || "") || !/^\d{2}:\d{2}$/.test(p.end || "")) {
        return { error: this._t("panel.tp_err_time_required", { name }) };
      }
      if (p.start >= p.end) return { error: this._t("panel.tp_err_order", { name }) };
      periods.push({ id, label, start: p.start, end: p.end, icon: p.icon || "" });
    }
    if (!periods.length) return { error: this._t("panel.tp_err_empty") };
    periods.sort((a, b) => (a.start < b.start ? -1 : 1));
    for (let i = 1; i < periods.length; i++) {
      if (periods[i].start < periods[i - 1].end) {
        const nameOf = (q) => q.label || (this._isBuiltinPeriod(q.id) ? this._t(`panel.time_${q.id}`) : q.id);
        return { error: this._t("panel.tp_err_overlap", { a: nameOf(periods[i]), b: nameOf(periods[i - 1]) }) };
      }
    }
    return { periods };
  }

  // ---- Backup / restore ------------------------------------------------
  async _doExportConfig() {
    const { ok, err, res } = await this._callWS({ type: "taskmate/config/export" });
    if (!ok || !res) { this._showToast("err", this._t("panel.toast_save_failed", { error: err })); return; }
    try {
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "taskmate-backup.json";
      a.click();
      URL.revokeObjectURL(url);
      this._showToast("ok", this._t("panel.backup_exported"));
    } catch (e) {
      this._showToast("err", String(e));
    }
  }

  async _doImportConfig(file) {
    let payload;
    try {
      payload = JSON.parse(await file.text());
    } catch (e) {
      this._showToast("err", this._t("panel.backup_import_bad_file"));
      return;
    }
    if (!payload || typeof payload !== "object" || !payload.data) {
      this._showToast("err", this._t("panel.backup_import_bad_file"));
      return;
    }
    if (!confirm(this._t("panel.backup_import_confirm"))) return;
    const { ok, err } = await this._callWS({ type: "taskmate/config/import", payload });
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.backup_imported"));
  }

  // ---- Settings --------------------------------------------------------
  async _doSaveSettings() {
    const root = this.querySelector(".tm-settings");
    if (!root) return;
    const fields = root.querySelectorAll("[data-setting]");
    const payload = { type: "taskmate/update_settings" };
    fields.forEach(el => {
      const name = el.dataset.setting;
      const declaredType = el.getAttribute("type") || el.type;
      let v;
      if (declaredType === "checkbox" || el.tagName === "HA-SWITCH") v = el.checked;
      else if (declaredType === "number") v = el.value === "" ? undefined : Number(el.value);
      else v = el.value;
      if (v !== undefined) payload[name] = v;
    });
    root.querySelectorAll("ha-icon-picker[data-setting]").forEach(el => {
      payload[el.dataset.setting] = el.value || "";
    });
    if (this._timePeriodsDraft) {
      this._syncTimePeriodInputs();
      const { periods, error } = this._validateTimePeriodsDraft();
      if (error) { this._showToast("err", error); return; }
      payload.time_periods = periods;
    }
    if (this._vacationDraft) {
      this._syncVacationInputs();
      const vacs = [];
      for (const p of this._vacationDraft) {
        const name = (p.name || "").trim();
        const start = p.start || "";
        const end = p.end || "";
        if (!start && !end && !name) continue;  // skip wholly-empty rows
        if (!start || !end) { this._showToast("err", this._t("panel.vacation_dates_required")); return; }
        vacs.push({ ...(p.id ? { id: p.id } : {}), name, start, end });
      }
      payload.vacation_periods = vacs;
    }
    const { ok, err, res } = await this._callWS(payload);
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", {error: err})); return; }
    this._timePeriodsDraft = null;  // rebuild from saved state on next render
    this._vacationDraft = null;
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_settings_saved", {count: (res && res.updated || []).length}));
  }

  // ---- Notifications WS helpers ----------------------------------------
  async _notifSetMaster(typeId, enabled) {
    await this._callWS({ type: "taskmate/notifications/set_master_enabled", type_id: typeId, enabled });
    await this._fetchState();
  }

  async _doSendTestNotif(typeId) {
    const { ok, err, res } = await this._callWS({ type: "taskmate/notifications/send_test", type_id: typeId });
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", { error: err })); return; }
    const count = (res && res.sent || []).length;
    this._showToast("ok", this._t("panel.notif_test_sent", { count }));
  }

  async _notifSetRoute(typeId, recipientId, enabled, time) {
    await this._callWS({ type: "taskmate/notifications/set_route", type_id: typeId, recipient_id: recipientId, enabled, time });
    await this._fetchState();
  }

  async _notifSetChildNotify(childId, notifyService) {
    await this._callWS({ type: "taskmate/notifications/set_child_notify", child_id: childId, notify_service: notifyService || null });
    await this._fetchState();
  }

  async _notifSetStreakCutoff(time) {
    await this._callWS({ type: "taskmate/notifications/set_streak_cutoff", time });
    await this._fetchState();
  }

  async _notifUpsertParent(p) {
    const payload = { type: "taskmate/notifications/upsert_parent", name: p.name, notify_service: p.notify_service, enabled: p.enabled !== false };
    if (p.id) payload.parent_id = p.id;
    await this._callWS(payload);
    await this._fetchState();
  }

  async _notifAddParent() {
    const first = (this._notifyServices || [])[0] || "";
    await this._notifUpsertParent({ name: this._t("panel.notif_default_parent_name"), notify_service: first, enabled: true });
  }

  async _notifDeleteParent(parentId) {
    await this._callWS({ type: "taskmate/notifications/delete_parent", parent_id: parentId });
    await this._fetchState();
  }

  async _notifUpsertCustom(n) {
    const payload = {
      type: "taskmate/notifications/upsert_custom",
      name: n.name, message_template: n.message_template, time: n.time,
      day_mask: n.day_mask, recipient_ids: n.recipient_ids, enabled: n.enabled,
    };
    if (n.id) payload.custom_id = n.id;
    await this._callWS(payload);
    await this._fetchState();
  }

  async _notifAddCustom() {
    await this._notifUpsertCustom({
      name: this._t("panel.notif_default_custom_name"),
      message_template: this._t("panel.notif_default_custom_message"),
      time: "20:00",
      day_mask: 0b1111111,
      recipient_ids: [],
      enabled: true,
    });
  }

  async _notifDeleteCustom(customId) {
    await this._callWS({ type: "taskmate/notifications/delete_custom", custom_id: customId });
    await this._fetchState();
  }

  async _notifToggleCustom(customId, enabled) {
    const n = (this._notifState && this._notifState.custom || []).find(x => x.id === customId);
    if (!n) return;
    await this._notifUpsertCustom({ ...n, enabled });
  }

  async _notifToggleDay(customId, dayIdx, isOn) {
    const n = (this._notifState && this._notifState.custom || []).find(x => x.id === customId);
    if (!n) return;
    const bit = 1 << dayIdx;
    const newMask = isOn ? (n.day_mask | bit) : (n.day_mask & ~bit);
    await this._notifUpsertCustom({ ...n, day_mask: newMask });
  }

  async _notifToggleRecipient(customId, recipientId) {
    const n = (this._notifState && this._notifState.custom || []).find(x => x.id === customId);
    if (!n) return;
    const has = n.recipient_ids.includes(recipientId);
    const newIds = has ? n.recipient_ids.filter(x => x !== recipientId) : [...n.recipient_ids, recipientId];
    await this._notifUpsertCustom({ ...n, recipient_ids: newIds });
  }

  async _notifUpdateCustomField(customId, field, value) {
    const n = (this._notifState && this._notifState.custom || []).find(x => x.id === customId);
    if (!n) return;
    await this._notifUpsertCustom({ ...n, [field]: value });
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
    this.querySelectorAll("ha-select[data-value], select[data-value]").forEach(el => {
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
    if (diffSec < 60)         return this._t("panel.time_ago_just_now");
    if (diffSec < 3600)       return this._t("panel.time_ago_minutes", {count: Math.floor(diffSec / 60)});
    if (diffSec < 86400)      return this._t("panel.time_ago_hours", {count: Math.floor(diffSec / 3600)});
    if (diffSec < 604800)     return this._t("panel.time_ago_days", {count: Math.floor(diffSec / 86400)});
    return then.toLocaleDateString();
  }

  // ---- rendering -------------------------------------------------------
  _render() {
    this._rendered = true;

    // Self-heal: HA's partial-panel-resolver removes the panel element from
    // the DOM while the WS connection is down (e.g. a long-backgrounded tab)
    // and re-attaches it on reconnect. If our shell was stripped out, force a
    // full rebuild — otherwise the zone-diff below short-circuits on the
    // stale _zoneCache and the content area stays blank until a hard reload.
    if (this._shellReady && !this.querySelector(".tm-shell")) {
      this._shellReady = false;
      this._zoneCache = {};
    }

    if (!this._shellReady) {
      if (!this._cachedStyles) {
        this._cachedStyles = this._styles();
      }
      const existingToast = this.querySelector(".tm-toast");
      this.innerHTML = `
        ${this._cachedStyles}
        <div class="tm-shell">
          <div data-zone="sidebar">${this._sidebar()}</div>
          <div class="tm-main">
            <div data-zone="topbar">${this._topbar()}</div>
            <div data-zone="mtabs">${this._mobileTabs()}</div>
            <div data-zone="approval">${this._approvalBanner()}</div>
            <div class="tm-body">
              <div class="tm-body-inner" data-zone="body">${this._renderBody()}</div>
            </div>
            <div data-zone="dialog">${this._dialog ? this._renderDialog() : ""}</div>
            <div data-zone="tpl">${this._renderSaveTemplateDialog()}</div>
          </div>
        </div>
      `;
      if (existingToast) this.appendChild(existingToast);
      this._shellReady = true;
      this._zoneCache = {};
      this._bindHaPickers();
      this._scrollActiveMobileTabIntoView();
      return;
    }

    const zones = {
      sidebar:  this._sidebar(),
      topbar:   this._topbar(),
      mtabs:    this._mobileTabs(),
      approval: this._approvalBanner(),
      body:     this._renderBody(),
      dialog:   this._dialog ? this._renderDialog() : "",
      tpl:      this._renderSaveTemplateDialog(),
    };

    const dialogZone = this.querySelector('[data-zone="dialog"]');
    let savedScroll = 0;
    if (dialogZone) {
      const dialogBody = dialogZone.querySelector(".tm-dialog-body");
      savedScroll = dialogBody ? dialogBody.scrollTop : 0;
    }

    const mtabsZone = this.querySelector('[data-zone="mtabs"]');
    const existingMtabs = mtabsZone ? mtabsZone.querySelector(".tm-mobile-tabs") : null;
    const savedMtabsScroll = existingMtabs ? existingMtabs.scrollLeft : 0;

    if (this._dialog) {
      const openSet = this._dialog._openAdvanced instanceof Set ? this._dialog._openAdvanced : new Set();
      this.querySelectorAll("details.tm-advanced[data-section]").forEach(el => {
        const key = el.dataset.section;
        if (!key) return;
        if (el.open) openSet.add(key); else openSet.delete(key);
      });
      this._dialog._openAdvanced = openSet;
    }

    let anyChanged = false;
    for (const [name, html] of Object.entries(zones)) {
      if (this._zoneCache[name] === html) continue;
      this._zoneCache[name] = html;
      const el = this.querySelector(`[data-zone="${name}"]`);
      if (!el) { this._shellReady = false; this._render(); return; }
      el.innerHTML = html;
      anyChanged = true;
    }

    if (anyChanged) {
      this._bindHaPickers();
    }

    if (savedScroll) {
      const newBody = dialogZone && dialogZone.querySelector(".tm-dialog-body");
      if (newBody) newBody.scrollTop = savedScroll;
    }

    if (savedMtabsScroll) {
      const newMtabs = this.querySelector(".tm-mobile-tabs");
      if (newMtabs) newMtabs.scrollLeft = savedMtabsScroll;
    }

    this._scrollActiveMobileTabIntoView();
  }

  _scrollActiveMobileTabIntoView() {
    const nav = this.querySelector(".tm-mobile-tabs");
    if (!nav) return;
    const active = nav.querySelector(".tm-mtab-active");
    if (!active) return;
    const navRect = nav.getBoundingClientRect();
    const btnRect = active.getBoundingClientRect();
    if (btnRect.left < navRect.left || btnRect.right > navRect.right) {
      const target = active.offsetLeft - (nav.clientWidth - active.offsetWidth) / 2;
      nav.scrollTo({ left: Math.max(0, target), behavior: "smooth" });
    }
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
      { head: this._t("panel.nav_today"), items: [
        { id: "activity", label: this._t("panel.tab_activity"), icon: "mdi:pulse" },
      ]},
      { head: this._t("panel.nav_manage"), items: [
        { id: "children",  label: this._t("panel.tab_children"),  icon: "mdi:account-multiple" },
        { id: "chores",    label: this._t("panel.tab_chores"),    icon: "mdi:check-circle-outline" },
        { id: "rewards",   label: this._t("panel.tab_rewards"),   icon: "mdi:gift-outline" },
        { id: "penalties", label: this._t("panel.tab_penalties"), icon: "mdi:alert-circle-outline" },
        { id: "bonuses",   label: this._t("panel.tab_bonuses"),   icon: "mdi:flash-outline" },
        { id: "groups",    label: this._t("panel.tab_groups"),    icon: "mdi:layers-outline" },
        { id: "badges",    label: this._t("panel.tab_badges"),     icon: "mdi:medal-outline" },
        { id: "templates", label: this._t("panel.tab_templates"), icon: "mdi:clipboard-list-outline" },
      ]},
      { head: this._t("panel.nav_system"), items: [
        { id: "notifications", label: this._t("panel.tab_notifications"), icon: "mdi:bell-outline" },
        { id: "settings", label: this._t("panel.tab_settings"), icon: "mdi:cog-outline" },
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
                  <button type="button" class="tm-nav-item ${active ? "tm-nav-active" : ""}" data-act="tab" data-tab="${it.id}">
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
        <button type="button" class="tm-menu-btn" data-act="toggle-ha-menu" aria-label="Menu">
          <ha-icon icon="mdi:menu"></ha-icon>
        </button>
        <div class="tm-crumbs">
          <span class="tm-crumbs-root">TaskMate</span>
          <span class="tm-crumbs-sep">/</span>
          <strong>${this._esc(crumbLabel)}</strong>
        </div>
        ${pendingCount > 0 && this._activeTab !== "activity" ? `
          <button type="button" class="tm-approval-pill" data-act="switch-to-activity" title="${this._t("panel.pending_tooltip", {count: pendingCount})}">
            <span class="tm-approval-dot"></span>
            ${this._t("panel.topbar_pending", {count: pendingCount})}
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
            <button type="button" class="tm-mtab ${active ? "tm-mtab-active" : ""}" data-act="tab" data-tab="${it.id}">
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
    if (completionsP) parts.push(`<strong>${completionsP}</strong> ${this._t("panel.topbar_chore_count", {count: completionsP})}`);
    if (rewardsP)     parts.push(`<strong>${rewardsP}</strong> ${this._t("panel.topbar_reward_count", {count: rewardsP})}`);
    return `
      <div class="tm-approval-banner">
        <ha-icon icon="mdi:bell-ring-outline"></ha-icon>
        <span>${this._t("panel.topbar_awaiting_approval", {details: parts.join(" · ")})}</span>
        <button type="button" class="tm-btn tm-btn-raised tm-btn-sm" data-act="switch-to-activity">${this._t("panel.btn_review")}</button>
      </div>
    `;
  }

  _renderBody() {
    if (this._loading && !this._state) return `<div class="tm-card tm-loading">${this._t("panel.loading")}</div>`;
    if (this._error) return `
      <div class="tm-card tm-card-error">
        <h2>${this._t("panel.error_failed_to_load")}</h2>
        <p>${this._esc(this._error)}</p>
        <button type="button" class="tm-btn tm-btn-raised" data-act="retry">${this._t("panel.btn_retry")}</button>
      </div>`;
    if (!this._state) return `<div class="tm-card">${this._t("panel.error_no_state")}</div>`;

    switch (this._activeTab) {
      case "children":  return this._renderChildrenTab();
      case "activity":  return this._renderActivityTab();
      case "chores":    return this._renderChoresTab();
      case "rewards":   return this._renderRewardsTab();
      case "penalties": return this._renderPenBonTab("penalty");
      case "bonuses":   return this._renderPenBonTab("bonus");
      case "groups":    return this._renderGroupsTab();
      case "badges":    return this._renderBadgesTab();
      case "templates":     return this._renderTemplatesTab();
      case "notifications": return this._renderNotificationsTab();
      case "audit":         return this._renderAuditTab();
      case "settings":      return this._renderSettingsTab();
      default:          return `<div class="tm-card">${this._t("panel.tab_unknown")}</div>`;
    }
  }

  _searchBox(placeholder) {
    return `
      <div class="tm-search-wrap">
        <ha-icon icon="mdi:magnify" class="tm-search-icon"></ha-icon>
        <input class="tm-search" placeholder="${this._esc(placeholder)}" data-filter="true" value="${this._esc(this._filter)}">
        ${this._filter ? `<button type="button" class="tm-search-clear" data-act="clear-filter" title="${this._t("panel.tooltip_clear")}">✕</button>` : ""}
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
    const pointsName = this._state.settings.points_name || this._t("common.points");
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${this._t("panel.child_title")} <span class="tm-toolbar-count">${all.length}</span></h2>
        ${all.length > 0 ? this._searchBox(this._t("panel.search_children")) : ""}
        <button type="button" class="tm-btn tm-btn-raised" data-act="add-child">${this._t("panel.btn_add_child")}</button>
      </div>
      ${all.length === 0 ? this._emptyState("👨‍👩‍👧‍👦", this._t("panel.empty_children_title"), this._t("panel.empty_children_copy"), "add-child", this._t("panel.btn_add_child")) :
        children.length === 0 ? `<div class="tm-card tm-empty"><p>${this._t("panel.empty_no_match", {kind: this._t("panel.tab_children").toLowerCase(), filter: this._esc(this._filter)})}</p></div>` : `
        <div class="tm-grid">
          ${children.map(c => this._renderChildCard(c, pointsName)).join("")}
          <button type="button" class="tm-add-tile" data-act="add-child"><span class="tm-add-plus">＋</span>${this._t("panel.child_add_tile")}</button>
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
            <h3>${this._esc(child.name || this._t("panel.child_unnamed"))}</h3>
            ${this._idBadge(child.id)}
            <div class="tm-meta">${child.availability_entity ? `<code>${this._esc(child.availability_entity)}</code>${child.availability_inverted ? ` <em>${this._t("panel.child_inverted")}</em>` : ""}` : `${this._t("panel.child_no_availability")}`}${child.unavailability_entity ? ` · ${this._t("panel.child_busy_label")} <code>${this._esc(child.unavailability_entity)}</code>` : ""}</div>
          </div>
        </div>
        <div class="tm-stats-row">
          <div class="tm-stat tm-stat-highlight"><div class="tm-stat-value">${this._fmtNum(child.points || 0)}</div><div class="tm-stat-label">${this._esc(pointsName)}</div></div>
          <div class="tm-stat"><div class="tm-stat-value">${this._fmtNum(child.total_points_earned || 0)}</div><div class="tm-stat-label">${this._t("panel.child_stat_earned")}</div></div>
          <div class="tm-stat"><div class="tm-stat-value">${this._fmtNum(child.total_chores_completed || 0)}</div><div class="tm-stat-label">${this._t("panel.child_stat_done")}</div></div>
        </div>
        <div class="tm-card-foot">
          <button type="button" class="tm-btn tm-btn-sm" data-act="edit-child" data-id="${this._esc(child.id)}">${this._t("panel.btn_edit")}</button>
          <button type="button" class="tm-btn tm-btn-sm" data-act="reorder-chores-for-child" data-id="${this._esc(child.id)}" title="${this._t("panel.chore_order_title")}">⇅ ${this._t("panel.chore_order_title")}</button>
          <button type="button" class="tm-btn tm-btn-sm tm-btn-danger" data-act="delete-child" data-id="${this._esc(child.id)}">${this._t("panel.btn_delete")}</button>
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
      child: c.child_id === "__parent__" ? "Parent" : ((childById[c.child_id] || {}).name || "?"),
      label: `${this._t("panel.activity_completed_chore", {name: (choreById[c.chore_id] || {}).name || this._t("panel.activity_deleted_chore")})}`,
      points: c.points_awarded,
    }));
    claims.filter(c => c.approved).forEach(c => events.push({
      ts: c.approved_at || c.claimed_at, kind: "claim",
      child: (childById[c.child_id] || {}).name || "?",
      label: `${this._t("panel.activity_claimed_reward", {name: (rewardById[c.reward_id] || {}).name || this._t("panel.activity_deleted_reward")})}`,
      points: -((rewardById[c.reward_id] || {}).cost || 0),
    }));
    transactions.forEach(t => events.push({
      ts: t.created_at, kind: "manual",
      child: (childById[t.child_id] || {}).name || "?",
      label: this._translateReason(t.reason) || (t.points >= 0 ? this._t("panel.activity_manual_addition") : this._t("panel.activity_manual_deduction")),
      points: t.points,
    }));
    events.sort((a, b) => (b.ts || "").localeCompare(a.ts || ""));
    const recent = events.slice(0, 30);

    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${this._t("panel.activity_title")}</h2>
      </div>

      <!-- Pending approvals -->
      <div class="tm-card">
        <h3 class="tm-section-title">${this._t("panel.activity_pending_approvals")}
          ${(pendingCompletions.length + pendingClaims.length) > 0
            ? `<span class="tm-pill tm-pill-warn">${pendingCompletions.length + pendingClaims.length}</span>`
            : `<span class="tm-pill tm-pill-success">${this._t("panel.activity_pending_all_clear")}</span>`}
        </h3>
        ${pendingCompletions.length === 0 && pendingClaims.length === 0 ? `
          <p class="tm-meta">${this._t("panel.activity_no_items")}</p>
        ` : `
          <div class="tm-approval-list">
            ${pendingCompletions.map(c => {
              const chore = choreById[c.chore_id];
              const child = childById[c.child_id];
              let choreName = (chore && chore.name) || this._t("panel.activity_deleted_chore");
              let chorePoints = chore ? chore.points : 0;
              if (c.bonus_subtask_id && chore) {
                const sub = (chore.bonus_subtasks || []).find(b => b.id === c.bonus_subtask_id);
                if (sub) { choreName = `${chore.name} › ${sub.name}`; chorePoints = sub.points; }
              } else if (chore && chore.task_type === "timed" && (c.timed_duration_seconds || 0) > 0) {
                // Timed chores accrue points by elapsed-time rate, so the actual
                // earned points can be lower than chore.points. Mirror sensor.py.
                const rateSeconds = (chore.timed_rate_minutes || 0) * 60;
                if (rateSeconds > 0) {
                  chorePoints = Math.floor(c.timed_duration_seconds / rateSeconds) * (chore.timed_rate_points || 0);
                }
              }
              return `
                <div class="tm-approval-item">
                  <div class="tm-approval-icon"><ha-icon icon="${c.bonus_subtask_id ? 'mdi:star-plus' : 'mdi:checkbox-marked-circle-outline'}"></ha-icon></div>
                  <div class="tm-approval-body">
                    <div class="tm-approval-line">${this._t("panel.activity_completed_text", {child: this._esc((child && child.name) || "?"), chore: this._esc(choreName)})}</div>
                    <div class="tm-meta">${this._timeAgo(c.completed_at)} · ${chorePoints} ${this._t("panel.activity_points")}</div>
                  </div>
                  <div class="tm-approval-actions">
                    <button type="button" class="tm-btn tm-btn-sm" data-act="reject-chore" data-id="${this._esc(c.id)}">${this._t("panel.activity_reject")}</button>
                    <button type="button" class="tm-btn tm-btn-raised tm-btn-sm" data-act="approve-chore" data-id="${this._esc(c.id)}">${this._t("panel.activity_approve")}</button>
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
                    <div class="tm-approval-line">${this._t("panel.activity_claimed_text", {child: this._esc((child && child.name) || "?"), reward: this._esc((reward && reward.name) || this._t("panel.activity_deleted_reward"))})}</div>
                    <div class="tm-meta">${this._timeAgo(c.claimed_at)}${reward ? ` · ${reward.cost} ${this._t("panel.activity_points")}` : ""}</div>
                  </div>
                  <div class="tm-approval-actions">
                    <button type="button" class="tm-btn tm-btn-sm" data-act="reject-reward" data-id="${this._esc(c.id)}">${this._t("panel.activity_reject")}</button>
                    <button type="button" class="tm-btn tm-btn-raised tm-btn-sm" data-act="approve-reward" data-id="${this._esc(c.id)}">${this._t("panel.activity_approve")}</button>
                  </div>
                </div>
              `;
            }).join("")}
          </div>
        `}
      </div>

      <!-- Recent activity feed -->
      <div class="tm-card">
        <h3 class="tm-section-title">${this._t("panel.activity_recent")}</h3>
        ${recent.length === 0 ? `<p class="tm-meta">${this._t("panel.activity_no_recent")}</p>` : `
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
        <h3 class="tm-section-title">${this._t("panel.activity_audit_log")}
          <span class="tm-pill">${this._t(transactions.length === 1 ? "panel.activity_transaction_count" : "panel.activity_transaction_count_plural", {count: transactions.length})}</span>
        </h3>
        ${transactions.length === 0 ? `<p class="tm-meta">${this._t("panel.activity_no_points_transactions")}</p>` : `
          <div class="tm-table-wrap">
            <table class="tm-table">
              <thead><tr><th>${this._t("panel.activity_table_when")}</th><th>${this._t("panel.activity_table_child")}</th><th>${this._t("panel.activity_table_points")}</th><th>${this._t("panel.activity_table_reason")}</th><th></th></tr></thead>
              <tbody>
                ${[...transactions].reverse().map(t => {
                  const child = childById[t.child_id];
                  const undoable = typeof t.reason === "string" && (t.reason.startsWith("Penalty: ") || t.reason.startsWith("Bonus: "));
                  return `
                    <tr class="tm-row">
                      <td class="tm-meta">${this._esc(this._timeAgo(t.created_at))}</td>
                      <td>${this._esc((child && child.name) || "?")}</td>
                      <td><strong class="tm-numeric ${t.points >= 0 ? 'tm-pos' : 'tm-neg'}">${t.points >= 0 ? '+' : ''}${t.points}</strong></td>
                      <td>${this._esc(this._translateReason(t.reason) || "—")}</td>
                      <td>${undoable ? `<button type="button" class="tm-icon-btn" data-act="undo-tx" data-id="${this._esc(t.id)}" title="${this._esc(this._t("panel.activity_undo"))}"><ha-icon icon="mdi:undo-variant"></ha-icon></button>` : ""}</td>
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
  _sortChoresByDisplayOrder(chores) {
    const order = this._state.chore_display_order || [];
    if (!order.length) return chores;
    const idx = Object.fromEntries(order.map((id, i) => [id, i]));
    return [...chores].sort((a, b) => {
      const ai = idx[a.id] ?? Number.MAX_SAFE_INTEGER;
      const bi = idx[b.id] ?? Number.MAX_SAFE_INTEGER;
      return ai - bi;
    });
  }

  _renderChoresTab() {
    const raw = this._state.chores || [];
    const all = this._sortChoresByDisplayOrder(raw);
    const chores = this._filterByName(all);
    const childById = Object.fromEntries((this._state.children || []).map(c => [c.id, c]));
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${this._t("panel.chore_title")} <span class="tm-toolbar-count">${all.length}</span></h2>
        ${all.length > 0 ? this._searchBox(this._t("panel.search_chores")) : ""}
        <button type="button" class="tm-btn" data-act="reorder-chores-global">${this._t("panel.btn_reorder_chores")}</button>
        <button type="button" class="tm-btn" data-act="bulk-add-chore">${this._t("panel.btn_bulk_add")}</button>
        <button type="button" class="tm-btn" data-act="tpl-add-from">${this._t("panel.btn_from_template")}</button>
        <button type="button" class="tm-btn" data-act="tpl-save-from">${this._t("panel.btn_save_as_template")}</button>
        <button type="button" class="tm-btn tm-btn-raised" data-act="add-chore">${this._t("panel.btn_add_chore")}</button>
      </div>
      ${all.length === 0 ? this._emptyState("📋", this._t("panel.empty_chores_title"), this._t("panel.empty_chores_copy"), "add-chore", this._t("panel.btn_add_chore")) :
        chores.length === 0 ? `<div class="tm-card tm-empty"><p>${this._t("panel.empty_no_match", {kind: this._t("panel.tab_chores").toLowerCase(), filter: this._esc(this._filter)})}</p></div>` : `
        <div class="tm-table-wrap">
          <table class="tm-table">
            <thead><tr>
              <th>${this._t("panel.chore_table_name")}</th><th>${this._t("panel.chore_table_points")}</th><th>${this._t("panel.chore_table_period")}</th><th>${this._t("panel.chore_table_assigned")}</th><th>${this._t("panel.chore_table_current")}</th><th>${this._t("panel.chore_table_schedule")}</th><th>${this._t("panel.chore_table_approval")}</th><th></th>
            </tr></thead>
            <tbody>
              ${chores.map(c => this._renderChoreRow(c, childById)).join("")}
            </tbody>
          </table>
        </div>
        <p class="tm-meta tm-table-hint">${this._t("panel.chore_tip_rename")}</p>
      `}
    `;
  }

  _renderChoreRow(c, childById) {
    const renaming = this._inlineRename && this._inlineRename.kind === "chore" && this._inlineRename.id === c.id;
    const isRotation = ["alternating", "random", "balanced"].includes(c.assignment_mode);
    const curChild = c.assignment_current_child_id || "";
    const assignedNames = c.assignment_mode === "unassigned"
      ? `<span class="tm-text-muted">${this._t("panel.assign_unassigned_short")}</span>`
      : (c.assigned_to || []).length === 0
      ? `<span class="tm-text-muted">${this._t("panel.common_all_children")}</span>`
      : this._esc((c.assigned_to || []).map(id => (childById[id] && childById[id].name) || "?").join(", "));
    const currentName = isRotation && curChild && childById[curChild]
      ? `<strong>${this._esc(childById[curChild].name)}</strong>`
      : isRotation ? `<span class="tm-text-muted">—</span>` : "";
    const schedLabel = c.schedule_mode === "recurring"
      ? this._labelOf(RECURRENCES, c.recurrence) + (c.recurrence_day && c.recurrence_day !== "any_day" ? ` · ${this._labelOf(DAYS, c.recurrence_day)}` : "")
      : c.schedule_mode === "one_shot"
      ? this._t("panel.common_one_shot")
      : ((c.due_days || []).length === 0 ? this._t("panel.common_daily") : (c.due_days || []).map(d => this._labelOf(DAYS, d)).join(" · "));
    const schedClass = c.schedule_mode === "recurring" ? "tm-pill-accent" : c.schedule_mode === "one_shot" ? "tm-pill-warn" : "tm-pill-success";
    const modeBadge = c.assignment_mode && c.assignment_mode !== "everyone"
      ? `<span class="tm-pill tm-pill-${c.assignment_mode}">${this._t(`panel.assign_${c.assignment_mode}_short`)}</span>` : "";
    const nameCell = renaming
      ? `<input class="tm-inline-input" type="text" data-field="_inlineRename" value="${this._esc(this._inlineRename.value)}" autofocus>
         <button type="button" class="tm-icon-btn" data-act="rename-chore-commit" title="${this._t("panel.tooltip_save")}">✓</button>
         <button type="button" class="tm-icon-btn" data-act="rename-chore-cancel" title="${this._t("panel.tooltip_cancel")}">✕</button>`
      : `<strong data-rename="chore" data-id="${this._esc(c.id)}" title="${this._t("panel.tooltip_rename")}">${this._esc(c.name)}</strong>${c.enabled === false ? ` <span class="tm-pill">${this._t("panel.common_disabled")}</span>` : ""}${this._idBadge(c.id)}`;
    return `
      <tr class="tm-row ${c.enabled === false ? "tm-row-disabled" : ""}">
        <td>${nameCell}</td>
        <td><strong class="tm-numeric">${c.task_type === "timed" ? `${c.timed_rate_points || 0}/${c.timed_rate_minutes || 1} min` : c.points}</strong></td>
        <td><span class="tm-pill">${this._esc(this._timeCategoryLabel(c.time_category))}</span></td>
        <td>${assignedNames} ${modeBadge}</td>
        <td>${currentName}</td>
        <td><span class="tm-pill ${schedClass} tm-pill-dot">${this._esc(schedLabel)}</span></td>
        <td>${c.requires_approval ? `<span class='tm-yes'>${this._t("panel.common_yes")}</span>` : `<span class='tm-no'>${this._t("panel.common_no")}</span>`}</td>
        <td class="tm-row-actions"><div>
          ${this._state.parent_completable && this._state.parent_completable[c.id] ? `<button type="button" class="tm-icon-btn" data-act="parent-complete-chore" data-id="${this._esc(c.id)}" title="${this._t("panel.parent_complete_tooltip")}">👤✓</button>` : ""}
          ${["alternating", "random", "balanced"].includes(c.assignment_mode) ? `<button type="button" class="tm-icon-btn" data-act="skip-chore" data-id="${this._esc(c.id)}" title="${this._t("panel.btn_skip_chore")}">⏭</button>` : ""}
          <button type="button" class="tm-icon-btn" data-act="toggle-chore-active" data-id="${this._esc(c.id)}" title="${c.enabled === false ? this._t("panel.btn_activate_chore") : this._t("panel.btn_deactivate_chore")}">${c.enabled === false ? "▶" : "⏸"}</button>
          <button type="button" class="tm-icon-btn" data-act="edit-chore" data-id="${this._esc(c.id)}" title="${this._t("panel.btn_edit")}">✏</button>
          <button type="button" class="tm-icon-btn" data-act="clone-chore" data-id="${this._esc(c.id)}" title="${this._t("panel.btn_clone_chore")}">⧉</button>
          <button type="button" class="tm-icon-btn" data-act="delete-chore" data-id="${this._esc(c.id)}" title="${this._t("panel.btn_delete")}">🗑</button>
        </div></td>
      </tr>
    `;
  }

  // -- Rewards tab -------------------------------------------------------
  _renderRewardsTab() {
    const all = this._state.rewards || [];
    const rewards = this._filterByName(all);
    const pointsName = this._state.settings.points_name || this._t("common.points");
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${this._t("panel.reward_title")} <span class="tm-toolbar-count">${all.length}</span></h2>
        ${all.length > 0 ? this._searchBox(this._t("panel.search_rewards")) : ""}
        <button type="button" class="tm-btn tm-btn-raised" data-act="add-reward">${this._t("panel.btn_add_reward")}</button>
      </div>
      ${all.length === 0 ? this._emptyState("🎁", this._t("panel.empty_rewards_title"), this._t("panel.empty_rewards_copy", {points_name: pointsName.toLowerCase()}), "add-reward", this._t("panel.btn_add_reward")) :
        rewards.length === 0 ? `<div class="tm-card tm-empty"><p>${this._t("panel.empty_no_match", {kind: this._t("panel.tab_rewards").toLowerCase(), filter: this._esc(this._filter)})}</p></div>` : `
        <div class="tm-grid">
          ${rewards.map(r => this._renderRewardCard(r, pointsName)).join("")}
          <button type="button" class="tm-add-tile" data-act="add-reward"><span class="tm-add-plus">＋</span>${this._t("panel.reward_add_tile")}</button>
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
            <h3>${this._esc(r.name)} ${r.is_jackpot ? `<span class="tm-pill tm-pill-jackpot">🏆 ${this._t("panel.reward_badge_jackpot")}</span>` : ""} ${r.pool_enabled ? `<span class="tm-pill tm-pill-pool">${this._t("panel.reward_badge_pool")}</span>` : ""}</h3>
            ${this._idBadge(r.id)}
            <div class="tm-meta">${this._esc(r.description || "")}</div>
          </div>
        </div>
        <div class="tm-stats-row" style="grid-template-columns: 1fr 1fr ${r.expires_at ? "1fr" : ""};">
          <div class="tm-stat"><div class="tm-stat-value tm-numeric tm-cost">${this._fmtNum(r.cost)}</div><div class="tm-stat-label">${this._t("panel.reward_stat_cost", {points_name: pointsName})}</div></div>
          ${r.quantity != null ? `<div class="tm-stat"><div class="tm-stat-value tm-numeric">${r.quantity}</div><div class="tm-stat-label">${this._t("panel.reward_stat_remaining")}</div></div>` : `<div class="tm-stat"><div class="tm-stat-value">∞</div><div class="tm-stat-label">${this._t("panel.reward_stat_unlimited")}</div></div>`}
          ${r.expires_at ? `<div class="tm-stat"><div class="tm-stat-value" style="font-size: 14px;">${this._esc(r.expires_at)}</div><div class="tm-stat-label">${this._t("panel.reward_stat_expires")}</div></div>` : ""}
        </div>
        ${showProgress ? `
          <div class="tm-progress"><span style="width:${pct}%"></span></div>
          <div class="tm-progress-text"><span><strong>${this._fmtNum(totalPooled)}</strong> / ${this._fmtNum(r.cost)}</span><span>${pct}%</span></div>
        ` : ""}
        <div class="tm-card-foot">
          <button type="button" class="tm-btn tm-btn-sm" data-act="edit-reward" data-id="${this._esc(r.id)}">${this._t("panel.btn_edit")}</button>
          <button type="button" class="tm-btn tm-btn-sm tm-btn-danger" data-act="delete-reward" data-id="${this._esc(r.id)}">${this._t("panel.btn_delete")}</button>
        </div>
      </article>
    `;
  }

  // -- Badges tab --------------------------------------------------------
  _renderBadgesTab() {
    const allBadges = this._state.badges || [];
    const sub = this._badgesSubTab || "catalogue";
    const catalogueCount = allBadges.filter(b => b.builtin).length;
    const customCount = allBadges.filter(b => !b.builtin).length;
    const subTabs = [
      { id: "catalogue", label: this._t("panel.badge_subtab_catalogue", { count: catalogueCount }) },
      { id: "custom",    label: this._t("panel.badge_subtab_custom", { count: customCount }) },
      { id: "history",   label: this._t("panel.badge_subtab_history") },
    ];
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${this._t("panel.badge_tab_title")} <span class="tm-toolbar-count">${allBadges.length}</span></h2>
        ${sub === "custom" ? `<button type="button" class="tm-btn tm-btn-raised" data-act="add-badge">${this._t("panel.badge_add_btn")}</button>` : ""}
      </div>
      <div class="tm-badge-subtabs">
        ${subTabs.map(s => `<button type="button" class="tm-badge-subtab${sub === s.id ? " tm-badge-subtab-active" : ""}" data-act="badges-subtab" data-sub="${s.id}">${this._esc(s.label)}</button>`).join("")}
      </div>
      ${sub === "catalogue" ? this._renderBadgeCatalogueTab(allBadges) : ""}
      ${sub === "custom"    ? this._renderBadgeCustomTab(allBadges) : ""}
      ${sub === "history"   ? this._renderBadgeHistoryTab() : ""}
    `;
  }

  _tierClass(tier) {
    return `tm-badge-tier-${(tier || "bronze").toLowerCase()}`;
  }

  _criteriaLabel(criteria, combinator = "AND") {
    if (!criteria || !criteria.length) return this._t("badge.manual_award_only");
    const joinKey = combinator === "OR" ? "badge.criteria_or" : "badge.criteria_and";
    return criteria.map(c => `${this._t("badge.criteria_" + c.metric)} ${c.operator} ${c.value}`).join(` ${this._t(joinKey)} `);
  }

  _badgeName(b) {
    if (!b.builtin) return b.name;
    const key = "badge.name_" + b.id.replace("builtin.", "");
    const t = this._t(key);
    return t !== key ? t : b.name;
  }

  _badgeDesc(b) {
    if (!b.builtin) return b.description || "";
    const key = "badge.desc_" + b.id.replace("builtin.", "");
    const t = this._t(key);
    return t !== key ? t : (b.description || "");
  }

  _renderBadgeCatalogueTab(allBadges) {
    const builtins = allBadges.filter(b => b.builtin);
    if (!builtins.length) return `<div class="tm-card tm-empty"><p>${this._t("panel.badge_empty_catalogue")}</p></div>`;
    return `
      <div class="tm-table-wrap">
        <table class="tm-table">
          <thead><tr><th>${this._t("panel.badge_table_badge")}</th><th>${this._t("panel.badge_table_tier")}</th><th>${this._t("panel.badge_table_criteria")}</th><th>${this._t("panel.badge_table_bonus")}</th><th>${this._t("panel.badge_table_enabled")}</th><th></th></tr></thead>
          <tbody>
            ${builtins.map(b => `
              <tr class="tm-row tm-badge-row ${this._tierClass(b.tier)}">
                <td>
                  <div class="tm-badge-icon-sm">${this._mdi(b.icon)}</div>
                  <span style="margin-left:8px"><strong>${this._esc(this._badgeName(b))}</strong>
                  <span class="tm-pill" style="background:var(--tm-surface-2);font-size:10px;margin-left:4px">${this._t("panel.badge_builtin_pill")}</span></span>
                  ${this._badgeDesc(b) ? `<div class="tm-meta">${this._esc(this._badgeDesc(b))}</div>` : ""}
                </td>
                <td><span class="tm-badge-tier-label">${this._t("badge.tier_" + (b.tier || "bronze"))}</span></td>
                <td><code class="tm-badge-criteria">${this._esc(this._criteriaLabel(b.criteria, b.combinator))}</code></td>
                <td><strong class="${b.point_bonus ? "tm-pos" : "tm-text-muted"}">${b.point_bonus ? `+${b.point_bonus}` : "—"}</strong></td>
                <td>
                  <button type="button" class="tm-badge-toggle${b.enabled !== false ? " tm-badge-toggle-on" : ""}"
                    data-act="toggle-badge-enabled" data-id="${this._esc(b.id)}" data-enabled="${b.enabled !== false}"
                    title="${b.enabled !== false ? this._t("panel.badge_toggle_disable") : this._t("panel.badge_toggle_enable")}">
                  </button>
                </td>
                <td class="tm-row-actions"><div>
                  <button type="button" class="tm-icon-btn" data-act="edit-badge" data-id="${this._esc(b.id)}" title="${this._t("panel.badge_edit_btn")}">✏</button>
                </div></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  _renderBadgeCustomTab(allBadges) {
    const customs = allBadges.filter(b => !b.builtin);
    if (!customs.length) return `
      <div class="tm-card tm-empty" style="text-align:center;padding:32px">
        <p style="font-size:24px;margin-bottom:8px">🏅</p>
        <p style="font-weight:600;margin-bottom:4px">${this._t("panel.badge_empty_custom_title")}</p>
        <p class="tm-meta" style="margin-bottom:16px">${this._t("panel.badge_empty_custom_desc")}</p>
        <button type="button" class="tm-btn tm-btn-raised" data-act="add-badge">${this._t("panel.badge_add_btn")}</button>
      </div>`;
    return `
      <div class="tm-table-wrap">
        <table class="tm-table">
          <thead><tr><th>${this._t("panel.badge_table_badge")}</th><th>${this._t("panel.badge_table_tier")}</th><th>${this._t("panel.badge_table_criteria")}</th><th>${this._t("panel.badge_table_bonus")}</th><th>${this._t("panel.badge_table_enabled")}</th><th></th></tr></thead>
          <tbody>
            ${customs.map(b => `
              <tr class="tm-row tm-badge-row ${this._tierClass(b.tier)}">
                <td>
                  <div class="tm-badge-icon-sm">${this._mdi(b.icon || "mdi:medal")}</div>
                  <span style="margin-left:8px"><strong>${this._esc(b.name)}</strong></span>
                  ${b.description ? `<div class="tm-meta">${this._esc(b.description)}</div>` : ""}
                </td>
                <td><span class="tm-badge-tier-label">${this._t("badge.tier_" + (b.tier || "bronze"))}</span></td>
                <td><code class="tm-badge-criteria">${this._esc(this._criteriaLabel(b.criteria, b.combinator))}</code></td>
                <td><strong class="${b.point_bonus ? "tm-pos" : "tm-text-muted"}">${b.point_bonus ? `+${b.point_bonus}` : "—"}</strong></td>
                <td>
                  <button type="button" class="tm-badge-toggle${b.enabled !== false ? " tm-badge-toggle-on" : ""}"
                    data-act="toggle-badge-enabled" data-id="${this._esc(b.id)}" data-enabled="${b.enabled !== false}"
                    title="${b.enabled !== false ? this._t("panel.badge_toggle_disable") : this._t("panel.badge_toggle_enable")}">
                  </button>
                </td>
                <td class="tm-row-actions"><div>
                  <button type="button" class="tm-btn tm-btn-sm" data-act="award-badge" data-id="${this._esc(b.id)}">${this._t("panel.badge_award_btn")}</button>
                  <button type="button" class="tm-icon-btn" data-act="edit-badge" data-id="${this._esc(b.id)}" title="${this._t("panel.badge_edit_btn")}">✏</button>
                  <button type="button" class="tm-icon-btn" data-act="delete-badge" data-id="${this._esc(b.id)}" title="${this._t("panel.badge_delete_btn")}">🗑</button>
                </div></td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  _renderBadgeHistoryTab() {
    const awards = (this._state.awarded_badges || []).slice().sort((a, b) => (b.earned_at || "").localeCompare(a.earned_at || ""));
    const badgeById = Object.fromEntries((this._state.badges || []).map(b => [b.id, b]));
    const childById = Object.fromEntries((this._state.children || []).map(c => [c.id, c]));
    const rebuildBtn = `<button type="button" class="tm-btn" data-act="rebuild-badges" title="${this._t("panel.badge_rebuild_tooltip")}">${this._t("panel.badge_rebuild_btn")}</button>`;
    if (!awards.length) return `
      <div style="display:flex;justify-content:flex-end;margin-bottom:12px">${rebuildBtn}</div>
      <div class="tm-card tm-empty"><p>${this._t("panel.badge_empty_history")}</p></div>`;
    return `
      <div style="display:flex;justify-content:flex-end;margin-bottom:12px">${rebuildBtn}</div>
      <div class="tm-table-wrap">
        <table class="tm-table">
          <thead><tr><th>${this._t("panel.badge_table_badge")}</th><th>${this._t("panel.badge_table_child")}</th><th>${this._t("panel.badge_table_when")}</th><th>${this._t("panel.badge_table_source")}</th><th></th></tr></thead>
          <tbody>
            ${awards.map(a => {
              const badge = badgeById[a.badge_id] || {};
              const child = childById[a.child_id] || {};
              const tierCls = this._tierClass(badge.tier || "bronze");
              const srcLabel = a.silent ? this._t("badge.source_silent") : a.manually_awarded ? this._t("badge.source_manual") : this._t("badge.source_auto");
              const srcCls = a.silent ? "tm-badge-src-silent" : a.manually_awarded ? "tm-badge-src-manual" : "tm-badge-src-auto";
              const when = a.earned_at ? new Date(a.earned_at).toLocaleString() : "—";
              return `
                <tr class="tm-row tm-badge-row ${tierCls}">
                  <td>
                    <div class="tm-badge-icon-sm">${this._mdi(badge.icon || "mdi:medal")}</div>
                    <span style="margin-left:8px"><strong>${this._esc(this._badgeName(badge) || a.badge_id)}</strong></span>
                  </td>
                  <td><strong style="color:var(--tm-accent)">${this._esc(child.name || a.child_id)}</strong></td>
                  <td class="tm-meta">${this._esc(when)}</td>
                  <td><span class="tm-badge-src ${srcCls}">${srcLabel}</span></td>
                  <td class="tm-row-actions"><div>
                    <button type="button" class="tm-btn tm-btn-sm tm-btn-danger" data-act="revoke-badge" data-id="${this._esc(a.id)}" data-name="${this._esc(this._badgeName(badge) || "badge")}">${this._t("panel.badge_revoke_btn")}</button>
                  </div></td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  // Badge dialog open/save/delete
  _openBadgeDialog(id) {
    const blank = { name: "", description: "", icon: "mdi:medal", tier: "bronze", point_bonus: 0, notify_on_earn: true, assigned_to: [], criteria: [], builtin: false };
    if (id) {
      const b = (this._state.badges || []).find(x => x.id === id);
      if (!b) return;
      this._openDialog({ kind: "badge", mode: "edit", data: { ...blank, ...b, assigned_to: [...(b.assigned_to || [])], criteria: (b.criteria || []).map(c => ({ ...c })) } });
    } else {
      this._openDialog({ kind: "badge", mode: "add", data: { ...blank } });
    }
  }

  async _doSaveBadge() {
    this._syncIconPickers();
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) { this._showToast("err", this._t("panel.toast_badge_name_required")); return; }
    // validate criteria values
    for (const c of (d.criteria || [])) {
      if (!BADGE_BOOL_METRICS.includes(c.metric) && (!c.value || Number(c.value) < 1)) {
        this._showToast("err", this._t("panel.toast_badge_criterion_invalid")); return;
      }
    }
    const wasAdd = this._dialog.mode === "add";
    const base = {
      name: d.name.trim(),
      description: d.description || "",
      icon: d.icon || "mdi:medal",
      tier: d.tier || "bronze",
      point_bonus: Number(d.point_bonus) || 0,
      notify_on_earn: d.notify_on_earn !== false && d.notify_on_earn !== "false",
      assigned_to: d.assigned_to || [],
      criteria: (d.criteria || []).map(c => ({
        metric: c.metric,
        operator: BADGE_BOOL_METRICS.includes(c.metric) ? ">=" : (c.operator || ">="),
        value: BADGE_BOOL_METRICS.includes(c.metric) ? 1 : Number(c.value),
      })),
      combinator: d.combinator === "OR" ? "OR" : "AND",
    };
    let ok, err;
    if (wasAdd) {
      ({ ok, err } = await this._callService("add_badge", base));
    } else {
      ({ ok, err } = await this._callService("update_badge", { badge_id: d.id, ...base }));
    }
    if (!ok) { this._showToast("err", this._t("panel.toast_badge_save_failed", { error: err })); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", wasAdd ? this._t("panel.toast_badge_added") : this._t("panel.toast_badge_updated"));
  }

  async _confirmDeleteBadge(id) {
    const b = (this._state.badges || []).find(x => x.id === id);
    if (!b) return;
    if (!confirm(this._t("panel.badge_confirm_delete", { name: b.name }))) return;
    const { ok, err } = await this._callService("remove_badge", { badge_id: id });
    if (!ok) { this._showToast("err", this._t("panel.toast_badge_delete_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_badge_deleted"));
  }

  async _doToggleBadgeEnabled(id, currentlyEnabled) {
    const { ok, err } = await this._callService("update_badge", { badge_id: id, enabled: !currentlyEnabled });
    if (!ok) { this._showToast("err", this._t("panel.toast_badge_update_failed", { error: err })); return; }
    await this._fetchState();
  }

  _openAwardDialog(badgeId) {
    const b = (this._state.badges || []).find(x => x.id === badgeId);
    if (!b) return;
    this._openDialog({ kind: "award-badge", mode: "award", data: { badge_id: badgeId, badge_name: b.name, child_id: "" } });
  }

  async _doAwardBadge(badgeId, childId) {
    if (!childId) { this._showToast("err", this._t("panel.toast_badge_select_child")); return; }
    const { ok, err } = await this._callService("award_badge_manually", { badge_id: badgeId, child_id: childId });
    if (!ok) { this._showToast("err", this._t("panel.toast_badge_award_failed", { error: err })); return; }
    this._closeDialog(true);
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_badge_awarded"));
  }

  async _doRevokeBadge(awardedBadgeId, badgeName) {
    if (!confirm(this._t("panel.badge_confirm_revoke", { name: badgeName }))) return;
    const { ok, err } = await this._callService("revoke_badge", { awarded_badge_id: awardedBadgeId });
    if (!ok) { this._showToast("err", this._t("panel.toast_badge_revoke_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_badge_revoked"));
  }

  async _doRebuildBadges() {
    if (!confirm(this._t("panel.badge_confirm_rebuild"))) return;
    const { ok, err } = await this._callService("rebuild_badges", {});
    if (!ok) { this._showToast("err", this._t("panel.toast_badge_rebuild_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.toast_badge_rebuilt"));
  }

  async _callService(service, data = {}) {
    try {
      await this._hass.callService("taskmate", service, data);
      return { ok: true };
    } catch (err) {
      return { ok: false, err: (err && err.message) || String(err) };
    }
  }

  // Badge dialog renders
  _renderBadgeDialog() {
    const d = this._dialog.data;
    const isBuiltin = !!d.builtin;
    const children = this._state.children || [];
    const title = this._dialog.mode === "add" ? this._t("panel.badge_dialog_add_title") : this._t("panel.badge_dialog_edit_title", { name: d.name });
    const criteria = d.criteria || [];
    return this._dialogShell(title,
      [
        isBuiltin ? `<div class="tm-field"><span class="tm-pill" style="background:var(--tm-surface-2)">${this._t("panel.badge_builtin_hint")}</span></div>` : "",
        !isBuiltin ? this._field(this._t("panel.badge_name_label"), "name", d.name, "text") : "",
        !isBuiltin ? this._field(this._t("panel.badge_description_label"), "description", d.description, "text") : "",
        `<div class="tm-field-row">
          ${!isBuiltin ? this._iconPickerField(this._t("panel.badge_icon_label"), "icon", d.icon) : ""}
          ${this._select(this._t("panel.badge_tier_label"), "tier", d.tier || "bronze", BADGE_TIERS)}
        </div>`,
        `<div class="tm-field-row">
          ${this._field(this._t("panel.badge_bonus_label"), "point_bonus", d.point_bonus || 0, "number")}
          ${this._select(this._t("panel.badge_notify_label"), "notify_on_earn", d.notify_on_earn !== false ? "true" : "false", [{ v: "true", l: this._t("panel.badge_notify_yes") }, { v: "false", l: this._t("panel.badge_notify_no") }])}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.badge_assigned_label")}</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="badge-toggle-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">${this._t("panel.badge_assigned_hint")}</span>
          </div>
        ` : "",
        !isBuiltin ? `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.badge_criteria_label")}</span>
            <div class="tm-badge-criteria-block">
              ${criteria.length === 0 ? `<p class="tm-field-hint" style="margin:0 0 8px">${this._t("panel.badge_no_criteria_hint")}</p>` : ""}
              ${criteria.map((c, idx) => {
                const isBool = BADGE_BOOL_METRICS.includes(c.metric);
                return `
                  <div class="tm-badge-criterion-row">
                    <select class="tm-select" data-badge-criterion-field="metric" data-badge-criterion-idx="${idx}">
                      ${BADGE_METRICS.map(m => `<option value="${m.v}"${c.metric === m.v ? " selected" : ""}>${this._t(m.lk)}</option>`).join("")}
                    </select>
                    ${isBool ? `<span class="tm-badge-op">=</span>` : `
                    <select class="tm-select tm-badge-op-select" data-badge-criterion-field="operator" data-badge-criterion-idx="${idx}">
                      ${BADGE_OPERATORS.map(sym => { const v = BADGE_OP_VALUES[sym]; return `<option value="${v}"${(c.operator || ">=") === v ? " selected" : ""}>${sym}</option>`; }).join("")}
                    </select>`}
                    ${isBool ? `<span class="tm-field-hint" style="flex:1">true</span>` : `<input class="tm-input" type="number" min="0" value="${c.value || 1}" data-badge-criterion-field="value" data-badge-criterion-idx="${idx}">`}
                    <button type="button" class="tm-icon-btn" data-act="badge-remove-criterion" data-idx="${idx}" title="${this._t("panel.badge_remove_criterion_btn")}">✕</button>
                  </div>
                `;
              }).join("")}
              <button type="button" class="tm-btn" data-act="badge-add-criterion" style="margin-top:6px;width:100%;border-style:dashed">${this._t("panel.badge_add_criterion_btn")}</button>
              ${criteria.length >= 2 ? `
                <div class="tm-badge-combinator">
                  <span class="tm-field-hint">${this._t("panel.badge_combinator_label")}</span>
                  <select class="tm-select" data-field="combinator">
                    <option value="AND"${(d.combinator || "AND") !== "OR" ? " selected" : ""}>${this._t("panel.badge_combinator_all")}</option>
                    <option value="OR"${d.combinator === "OR" ? " selected" : ""}>${this._t("panel.badge_combinator_any")}</option>
                  </select>
                </div>
              ` : ""}
            </div>
          </div>
        ` : "",
      ].join(""),
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.badge_cancel_btn")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="save-badge">${this._t("panel.badge_save_btn")}</button>`
    );
  }

  _renderAwardDialog() {
    const d = this._dialog.data;
    const children = this._state.children || [];
    return this._dialogShell(this._t("panel.badge_dialog_award_title", { name: d.badge_name }),
      `<div class="tm-field">
        <span class="tm-field-label">${this._t("panel.badge_award_to_label")}</span>
        <select class="tm-select" data-field="child_id">
          <option value="">${this._t("panel.badge_award_select_child")}</option>
          ${children.map(c => `<option value="${this._esc(c.id)}">${this._esc(c.name)}</option>`).join("")}
        </select>
      </div>`,
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.badge_cancel_btn")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="do-award-badge" data-id="${this._esc(d.badge_id)}">${this._t("panel.badge_award_btn")}</button>`
    );
  }

  // -- Penalties / Bonuses tab -------------------------------------------
  _renderPenBonTab(kind) {
    const allItems = (kind === "penalty" ? this._state.penalties : this._state.bonuses) || [];
    const items = this._filterByName(allItems);
    const childById = Object.fromEntries((this._state.children || []).map(c => [c.id, c]));
    const labels = kind === "penalty" ? { plural: this._t("panel.penalty_title"), add: this._t("panel.btn_add_penalty"), icon: "⚠️" } : { plural: this._t("panel.bonus_title"), add: this._t("panel.btn_add_bonus"), icon: "⭐" };
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${labels.plural} <span class="tm-toolbar-count">${allItems.length}</span></h2>
        ${allItems.length > 0 ? this._searchBox(kind === "penalty" ? this._t("panel.search_penalties") : this._t("panel.search_bonuses")) : ""}
        <button type="button" class="tm-btn tm-btn-raised" data-act="add-${kind}">${labels.add}</button>
      </div>
      ${allItems.length === 0 ? this._emptyState(labels.icon, kind === "penalty" ? this._t("panel.penalty_empty_title") : this._t("panel.bonus_empty_title"), kind === "penalty" ? this._t("panel.penalty_empty_description") : this._t("panel.bonus_empty_description"), `add-${kind}`, labels.add) :
        items.length === 0 ? `<div class="tm-card tm-empty"><p>${this._t("panel.empty_no_match", {kind: labels.plural.toLowerCase(), filter: this._esc(this._filter)})}</p></div>` : `
        <div class="tm-table-wrap">
          <table class="tm-table">
            <thead><tr><th>${this._t("panel.penbon_table_name")}</th><th>${this._t("panel.penbon_table_points")}</th><th>${this._t("panel.penbon_table_assigned")}</th><th></th></tr></thead>
            <tbody>
              ${items.map(item => {
                const assignedNames = (item.assigned_to || []).length === 0
                  ? `<span class="tm-text-muted">${this._t("panel.common_all_children")}</span>`
                  : this._esc((item.assigned_to || []).map(id => (childById[id] && childById[id].name) || "?").join(", "));
                return `
                  <tr class="tm-row">
                    <td><span class="tm-row-icon">${this._mdi(item.icon)}</span><strong>${this._esc(item.name)}</strong>${this._idBadge(item.id)}${item.description ? `<div class="tm-meta">${this._esc(item.description)}</div>` : ""}</td>
                    <td><strong class="tm-numeric ${kind === "penalty" ? "tm-neg" : "tm-pos"}">${kind === "penalty" ? "−" : "+"}${item.points}</strong></td>
                    <td>${assignedNames}</td>
                    <td class="tm-row-actions"><div>
                      <button type="button" class="tm-btn tm-btn-sm" data-act="apply-${kind}" data-id="${this._esc(item.id)}">${this._t("panel.btn_apply")}</button>
                      <button type="button" class="tm-icon-btn" data-act="edit-${kind}" data-id="${this._esc(item.id)}" title="${this._t("panel.btn_edit")}">✏</button>
                      <button type="button" class="tm-icon-btn" data-act="delete-${kind}" data-id="${this._esc(item.id)}" title="${this._t("panel.btn_delete")}">🗑</button>
                    </div></td>
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
        <h2 class="tm-toolbar-title">${this._t("panel.group_title")} <span class="tm-toolbar-count">${all.length}</span></h2>
        ${all.length > 0 ? this._searchBox(this._t("panel.search_groups")) : ""}
        <button type="button" class="tm-btn tm-btn-raised" data-act="add-group">${this._t("panel.btn_add_group")}</button>
      </div>
      ${all.length === 0 ? this._emptyState("🔗", this._t("panel.empty_groups_title"), this._t("panel.empty_groups_copy"), "add-group", this._t("panel.btn_add_group")) :
        groups.length === 0 ? `<div class="tm-card tm-empty"><p>${this._t("panel.empty_no_match", {kind: this._t("panel.tab_groups").toLowerCase(), filter: this._esc(this._filter)})}</p></div>` : `
        <div class="tm-grid">
          ${groups.map(g => `
            <article class="tm-card">
              <div class="tm-child-head">
                <div class="tm-avatar"><ha-icon icon="${g.policy === 'sticky' ? 'mdi:link-variant' : 'mdi:arrow-split-horizontal'}"></ha-icon></div>
                <div class="tm-child-name">
                  <h3>${this._esc(g.name)}</h3>
                  ${this._idBadge(g.id)}
                  <div class="tm-meta"><span class="tm-pill tm-pill-${g.policy}">${this._t(`panel.group_policy_${g.policy}_short`)}</span> · ${this._t("panel.group_chore_count", {count: (g.chore_ids || []).length})}</div>
                </div>
              </div>
              <ul class="tm-group-list">
                ${(g.chore_ids || []).map(id => `<li>${this._esc((choreById[id] && choreById[id].name) || this._t("panel.group_missing_chore", {id}))}</li>`).join("")}
              </ul>
              <div class="tm-card-foot">
                <button type="button" class="tm-btn tm-btn-sm" data-act="edit-group" data-id="${this._esc(g.id)}">${this._t("panel.btn_edit")}</button>
                <button type="button" class="tm-btn tm-btn-sm tm-btn-danger" data-act="delete-group" data-id="${this._esc(g.id)}">${this._t("panel.btn_delete")}</button>
              </div>
            </article>
          `).join("")}
          <button type="button" class="tm-add-tile" data-act="add-group"><span class="tm-add-plus">＋</span>${this._t("panel.group_add_tile")}</button>
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
        <h2 class="tm-toolbar-title">${this._t("panel.template_title")} <span class="tm-toolbar-count">${templates.length}</span></h2>
        <span style="flex:1"></span>
        <button type="button" class="tm-btn tm-btn-raised" data-act="tpl-create">${this._t("panel.btn_create_template_toolbar")}</button>
      </div>
      ${custom.length > 0 ? `
        <div class="tm-section-divider">${this._t("panel.template_custom_templates")}</div>
        ${custom.map(t => this._renderManageTemplateCard(t, false)).join("")}
      ` : ""}
      <div class="tm-section-divider">${custom.length > 0 ? this._t("panel.template_builtin_templates") : this._t("panel.template_builtin_packs")}</div>
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
          <div class="tm-meta">${this._t("panel.template_pts_total", {count, points: pts})}</div>
        </div>
        <div class="tm-row-actions">
          ${locked ? "" : `<button type="button" class="tm-btn tm-btn-sm" data-act="tpl-edit" data-id="${this._esc(tpl.id)}">${this._t("panel.btn_edit")}</button>`}
          ${locked ? "" : `<button type="button" class="tm-btn tm-btn-sm tm-btn-danger" data-act="tpl-delete" data-id="${this._esc(tpl.id)}">${this._t("panel.btn_delete")}</button>`}
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
        <h2 class="tm-toolbar-title">${this._t("panel.template_picker_title")}</h2>
        <span style="flex:1"></span>
        <button type="button" class="tm-btn" data-act="tpl-back">${this._t("panel.btn_cancel")}</button>
      </div>
      <div class="tm-section-divider">${this._t("panel.template_builtin_packs")}</div>
      <div class="tm-grid">
        ${builtin.map(t => this._renderTemplatePickerCard(t)).join("")}
      </div>
      ${custom.length > 0 ? `
        <div class="tm-section-divider">${this._t("panel.template_custom_packs")}</div>
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
            <div class="tm-meta">${this._t("panel.template_pts_total", {count, points: pts})}</div>
          </div>
          <span class="tm-pill ${tpl.builtin ? "tm-pill-accent" : "tm-pill-success"}">${tpl.builtin ? this._t("panel.template_builtin") : this._t("panel.template_custom")}</span>
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
        <span class="tm-pill ${tpl.builtin ? "tm-pill-accent" : "tm-pill-success"}" style="margin-left:8px">${tpl.builtin ? this._t("panel.template_builtin") : this._t("panel.template_custom")}</span>
        <span style="flex:1"></span>
        <button type="button" class="tm-btn" data-act="tpl-back">${this._t("panel.btn_back")}</button>
      </div>
      <p class="tm-meta" style="margin-bottom:16px">${this._t("panel.template_preview_hint")}</p>
      ${chores.map((c, i) => this._renderTemplateChoreCard(c, i)).join("")}
      ${chores.length > 0 ? `
        <div class="tm-tpl-confirm-bar">
          <div>${this._t("panel.template_confirm_bar", {count: chores.length, points: totalPts})}</div>
          <button type="button" class="tm-btn tm-btn-raised" data-act="tpl-apply">${this._t("panel.template_create_btn", {count: chores.length})}</button>
        </div>
      ` : `<div class="tm-card tm-empty"><p>${this._t("panel.empty_template_all_removed")}</p></div>`}
    `;
  }

  _renderTemplateChoreCard(chore, idx) {
    const expanded = chore._expanded;
    const schedLabel = (chore.due_days || []).length === 0 ? this._t("panel.common_daily") : (chore.due_days || []).map(d => this._labelOf(DAYS, d)).join(", ");
    return `
      <div class="tm-tpl-preview-card">
        <div class="tm-tpl-preview-header" data-act="tpl-toggle-expand" data-idx="${idx}">
          <span class="tm-tpl-expand ${expanded ? "open" : ""}">▶</span>
          <span class="tm-tpl-preview-name">${this._esc(chore.name)}</span>
          <span class="tm-tpl-preview-summary">
            <span>${this._t("panel.pts_display", {count: chore.points || 0})}</span>
            <span>${schedLabel}</span>
            <span>${this._esc(this._timeCategoryLabel(chore.time_category))}</span>
          </span>
          <button type="button" class="tm-tpl-remove" data-act="tpl-remove-chore" data-idx="${idx}" title="${this._t("panel.tooltip_remove_batch")}">✕</button>
        </div>
        ${expanded ? `
          <div class="tm-tpl-preview-body">
            <div class="tm-field-row">
              <div class="tm-field"><span class="tm-field-label">${this._t("panel.common_name")}</span><input class="tm-input" type="text" data-tpl-field="name" data-tpl-idx="${idx}" value="${this._esc(chore.name)}"></div>
              <div class="tm-field"><span class="tm-field-label">${this._t("panel.common_points")}</span><input class="tm-input" type="number" data-tpl-field="points" data-tpl-idx="${idx}" value="${chore.points || 0}" min="0"></div>
            </div>
            <div class="tm-field-row">
              <div class="tm-field"><span class="tm-field-label">${this._t("panel.chore_time_category_label")}</span>
                <select class="tm-select" data-tpl-field="time_category" data-tpl-idx="${idx}">
                  ${this._timeCategoryOptions().map(t => `<option value="${this._esc(t.v)}" ${chore.time_category === t.v ? "selected" : ""}>${this._esc(t.l)}</option>`).join("")}
                </select>
              </div>
              <div class="tm-field"><span class="tm-field-label">${this._t("panel.template_assignment_mode_label")}</span>
                <select class="tm-select" data-tpl-field="assignment_mode" data-tpl-idx="${idx}">
                  ${ASSIGNMENT_MODES.map(m => `<option value="${m.v}" ${chore.assignment_mode === m.v ? "selected" : ""}>${this._t(m.lk).split(" — ")[0]}</option>`).join("")}
                </select>
              </div>
            </div>
            <div class="tm-field" style="margin-bottom:12px"><span class="tm-field-label">${this._t("panel.template_schedule_days_label")}</span>
              <div class="tm-day-pills">
                ${DAYS.map(d => `<span class="tm-day-pill ${(chore.due_days || []).includes(d.v) ? "active" : ""}" data-act="tpl-toggle-day" data-idx="${idx}" data-day="${d.v}">${this._t(d.lk)}</span>`).join("")}
              </div>
            </div>
            <div class="tm-field-row">
              <div class="tm-field"><span class="tm-field-label">${this._t("panel.template_requires_approval_label")}</span>
                <select class="tm-select" data-tpl-field="requires_approval" data-tpl-idx="${idx}">
                  <option value="false" ${!chore.requires_approval ? "selected" : ""}>${this._t("panel.template_requires_approval_no")}</option>
                  <option value="true" ${chore.requires_approval ? "selected" : ""}>${this._t("panel.template_requires_approval_yes")}</option>
                </select>
              </div>
              <div class="tm-field"><span class="tm-field-label">${this._t("panel.template_daily_limit_label")}</span>
                <input class="tm-input" type="number" data-tpl-field="daily_limit" data-tpl-idx="${idx}" value="${chore.daily_limit || 1}" min="1">
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
            <h2>${this._t("panel.template_save_title")}</h2>
            <button type="button" class="tm-icon-btn" data-act="tpl-save-cancel">✕</button>
          </div>
          <div class="tm-dialog-body">
            <div class="tm-field" style="margin-bottom:14px"><span class="tm-field-label">${this._t("panel.template_save_name_label")}</span><input class="tm-input" type="text" data-field="tpl_save_name" placeholder="${this._t("panel.template_save_name_placeholder")}"></div>
            <div class="tm-field" style="margin-bottom:14px"><span class="tm-field-label">${this._t("panel.template_save_icon_label")}</span><input class="tm-input" type="text" data-field="tpl_save_icon" placeholder="mdi:clipboard-list" value="mdi:clipboard-list"></div>
            <label class="tm-field-label" style="display:block;margin-bottom:8px">${this._t("panel.template_save_select_chores")}</label>
            <div class="tm-tpl-checklist">
              ${chores.map(c => `
                <label class="tm-tpl-check-row">
                  <input type="checkbox" data-tpl-chore-check="${this._esc(c.id)}">
                  <span>${this._esc(c.name)}</span>
                  <span class="tm-text-muted" style="margin-left:auto">${this._t("panel.pts_display", {count: c.points})}</span>
                </label>
              `).join("")}
            </div>
          </div>
          <div class="tm-dialog-foot">
            <button type="button" class="tm-btn" data-act="tpl-save-cancel">${this._t("panel.btn_cancel")}</button>
            <button type="button" class="tm-btn tm-btn-raised" data-act="tpl-save-confirm">${this._t("panel.btn_save_template")}</button>
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
      this._showToast("success", this._t("panel.toast_created_chores", {count: chores.length}));
      this._templateView = null;
      this._templateSelected = null;
      this._templateChores = [];
      await this._fetchState();
      this._activeTab = "chores";
      this._render();
    } else {
      this._showToast("error", err || this._t("panel.toast_template_failed_apply"));
    }
  }

  async _doSaveFromChores() {
    const name = this.querySelector('[data-field="tpl_save_name"]')?.value?.trim();
    const icon = this.querySelector('[data-field="tpl_save_icon"]')?.value?.trim() || "mdi:clipboard-list";
    const checkboxes = this.querySelectorAll('[data-tpl-chore-check]:checked');
    const chore_ids = Array.from(checkboxes).map(cb => cb.dataset.tplChoreCheck);
    if (!name || chore_ids.length === 0) {
      this._showToast("error", this._t("panel.toast_name_enter_select"));
      return;
    }
    const { ok, err } = await this._callWS({ type: "taskmate/templates/save_from_chores", chore_ids, name, icon });
    if (ok) {
      this._showToast("success", this._t("panel.toast_template_saved", {name}));
      this._saveTemplateDialog = false;
      await this._fetchState();
      this._render();
    } else {
      this._showToast("error", err || this._t("panel.toast_template_failed_save"));
    }
  }

  async _confirmDeleteTemplate(templateId) {
    const templates = this._state.templates || [];
    const tpl = templates.find(t => t.id === templateId);
    if (!tpl) return;
    if (!confirm(this._t("panel.confirm_delete_template", {name: tpl.name}))) return;
    const { ok, err } = await this._callWS({ type: "taskmate/templates/delete", template_id: templateId });
    if (ok) {
      this._showToast("success", this._t("panel.toast_template_deleted"));
      await this._fetchState();
    } else {
      this._showToast("error", err || this._t("panel.toast_template_failed_delete"));
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
    if (!d || !d.name?.trim() || !d.chores?.length) { this._showToast("error", this._t("panel.toast_name_and_chore_required")); return; }
    const { ok, err } = await this._callWS({ type: "taskmate/templates/create", name: d.name.trim(), icon: d.icon || "mdi:clipboard-list", chores: d.chores });
    if (ok) { this._showToast("success", this._t("panel.toast_template_created", {name: d.name})); this._closeDialog(true); await this._fetchState(); }
    else { this._showToast("error", err || this._t("panel.toast_template_failed_create")); }
  }

  async _doSaveEditedTemplate() {
    const d = this._dialog?.data;
    if (!d || !d.template_id || !d.name?.trim()) { this._showToast("error", this._t("panel.toast_name_required_template")); return; }
    const { ok, err } = await this._callWS({ type: "taskmate/templates/update", template_id: d.template_id, name: d.name.trim(), icon: d.icon || "mdi:clipboard-list", chores: d.chores || [] });
    if (ok) { this._showToast("success", this._t("panel.toast_template_updated")); this._closeDialog(true); await this._fetchState(); }
    else { this._showToast("error", err || this._t("panel.toast_template_failed_update")); }
  }

  async _doUndoTransaction(id) {
    if (!id) return;
    if (!confirm(this._t("panel.activity_undo_confirm"))) return;
    const { ok, err } = await this._callWS({ type: "taskmate/undo_transaction", transaction_id: id });
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.activity_undone"));
  }

  // -- Audit tab ---------------------------------------------------------
  async _doClearAudit() {
    if (!confirm(this._t("panel.audit_clear_confirm"))) return;
    const { ok, err } = await this._callWS({ type: "taskmate/audit/clear" });
    if (!ok) { this._showToast("err", this._t("panel.toast_save_failed", { error: err })); return; }
    await this._fetchState();
    this._showToast("ok", this._t("panel.audit_cleared"));
  }

  _renderAuditTab() {
    const entries = this._state.audit_log || [];
    const rows = entries.map(a => {
      let when = a.ts || "";
      try { if (a.ts) when = new Date(a.ts).toLocaleString(); } catch (e) {}
      return `
            <div class="tm-audit-row">
              <div class="tm-audit-when">${this._esc(when)}</div>
              <div class="tm-audit-user">${this._esc(a.user_name || a.user_id || "—")}</div>
              <div class="tm-audit-action">${this._esc(a.action || "")}</div>
              <div class="tm-audit-target">${this._esc(a.target || "")}</div>
            </div>`;
    }).join("");
    return `
        <div class="tm-section">
          <div class="tm-section-head">
            <div><h3>${this._t("panel.tab_audit")}</h3><p class="tm-meta">${this._t("panel.audit_hint")}</p></div>
            ${entries.length ? `<button type="button" class="tm-btn" data-act="audit-clear"><ha-icon icon="mdi:trash-can-outline"></ha-icon> ${this._t("panel.audit_clear")}</button>` : ""}
          </div>
          <div class="tm-section-body">
            ${entries.length ? `
              <div class="tm-audit-row tm-audit-head">
                <div>${this._t("panel.audit_when")}</div><div>${this._t("panel.audit_user")}</div>
                <div>${this._t("panel.audit_action")}</div><div>${this._t("panel.audit_target")}</div>
              </div>
              ${rows}
            ` : `<div class="tm-meta" style="padding: 8px 0;">${this._t("panel.audit_empty")}</div>`}
          </div>
        </div>`;
  }

  // -- Settings tab ------------------------------------------------------
  _renderSettingsTab() {
    const s = this._state.settings || {};
    const notifyServices = Object.keys((this._hass && this._hass.services && this._hass.services.notify) || {});
    const notifyOptions = [
      { v: "", l: this._t("panel.settings_notify_none") },
      ...notifyServices.map(k => ({ v: `notify.${k}`, l: `notify.${k}` })),
    ];
    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${this._t("panel.settings_title")}</h2>
      </div>
      <div class="tm-settings">
        <div class="tm-section">
          <div class="tm-section-head">
            <div>
              <h3>${this._t("panel.settings_currency_title")}</h3>
              <p class="tm-meta">${this._t("panel.settings_currency_hint")}</p>
            </div>
          </div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_points_name_label")}<small>${this._t("panel.settings_points_name_hint")}</small></div>
              <input type="text" class="tm-input" data-setting="points_name" value="${this._esc(s.points_name || this._t("panel.settings_points_default"))}" placeholder="${this._esc(this._t("panel.settings_points_default"))}">
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_points_icon_label")}<small>${this._t("panel.settings_points_icon_hint")}</small></div>
              <ha-icon-picker data-setting="points_icon" data-current="${this._esc(s.points_icon || 'mdi:star')}"></ha-icon-picker>
            </div>
          </div>
        </div>

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>${this._t("panel.settings_history_title")}</h3></div></div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_retention_label")}<small>${this._t("panel.settings_retention_hint")}</small></div>
              <input type="number" class="tm-input" min="30" max="365" data-setting="history_days" value="${s.history_days || 90}">
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_streak_reset_label")}<small>${this._t("panel.settings_streak_reset_hint")}</small></div>
              <select class="tm-select" data-setting="streak_reset_mode">
                ${STREAK_MODES.map(m => `<option value="${m.v}" ${m.v === (s.streak_reset_mode || "reset") ? "selected" : ""}>${this._esc(this._t(m.lk))}</option>`).join("")}
              </select>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_weekend_multiplier_label")}<small>${this._t("panel.settings_weekend_multiplier_hint")}</small></div>
              <input type="number" class="tm-input" step="0.1" min="1" max="5" data-setting="weekend_multiplier" value="${s.weekend_multiplier || 1.0}">
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_calendar_projection_label")}<small>${this._t("panel.settings_calendar_projection_hint")}</small></div>
              <input type="number" class="tm-input" min="1" max="90" data-setting="calendar_projection_days" value="${s.calendar_projection_days || 14}">
            </div>
          </div>
        </div>

        ${this._renderTimePeriodsSection()}

        ${this._renderVacationSection()}

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>${this._t("panel.settings_bonuses_title")}</h3></div></div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_streak_milestones_label")}<small>${this._t("panel.settings_streak_milestones_hint")}</small></div>
              <ha-switch data-setting="streak_milestones_enabled" ${s.streak_milestones_enabled ? "checked" : ""}></ha-switch>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_perfect_week_label")}<small>${this._t("panel.settings_perfect_week_hint")}</small></div>
              <ha-switch data-setting="perfect_week_enabled" ${s.perfect_week_enabled ? "checked" : ""}></ha-switch>
            </div>
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_perfect_week_bonus_label")}<small>${this._t("panel.settings_perfect_week_bonus_hint")}</small></div>
              <input type="number" class="tm-input" min="0" data-setting="perfect_week_bonus" value="${s.perfect_week_bonus || 50}">
            </div>
          </div>
        </div>

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>${this._t("panel.settings_chore_rotation_title")}</h3></div></div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_skip_confirm_label")}<small>${this._t("panel.settings_skip_confirm_hint")}</small></div>
              <ha-switch data-setting="skip_confirmation_enabled" ${s.skip_confirmation_enabled !== false ? "checked" : ""}></ha-switch>
            </div>
          </div>
        </div>

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>${this._t("panel.settings_notifications_title")}</h3></div></div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_notify_label")}<small>${this._t("panel.settings_notify_hint")}</small></div>
              <select class="tm-select" data-setting="notify_service">
                ${notifyOptions.map(o => `<option value="${this._esc(o.v)}" ${o.v === (s.notify_service || "") ? "selected" : ""}>${this._esc(o.l)}</option>`).join("")}
              </select>
            </div>
          </div>
        </div>

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>${this._t("panel.settings_show_ids_label")}</h3><p class="tm-meta">${this._t("panel.settings_show_ids_hint")}</p></div></div>
          <div class="tm-section-body">
            <div class="tm-setting-row">
              <div class="tm-setting-label">${this._t("panel.settings_show_ids_label")}</div>
              <ha-switch ${this._showIds ? "checked" : ""} data-local="show-ids"></ha-switch>
            </div>
          </div>
        </div>

        <div class="tm-section">
          <div class="tm-section-head"><div><h3>${this._t("panel.backup_title")}</h3><p class="tm-meta">${this._t("panel.backup_hint")}</p></div></div>
          <div class="tm-section-body">
            <div class="tm-period-actions">
              <button type="button" class="tm-btn" data-act="config-export"><ha-icon icon="mdi:download"></ha-icon> ${this._t("panel.backup_export")}</button>
              <button type="button" class="tm-btn" data-act="config-import"><ha-icon icon="mdi:upload"></ha-icon> ${this._t("panel.backup_import")}</button>
              <input type="file" accept="application/json,.json" data-role="config-import-file" style="display:none">
            </div>
          </div>
        </div>

        <div class="tm-settings-foot">
          <button type="button" class="tm-btn tm-btn-raised" data-act="save-settings">${this._t("panel.btn_save_settings")}</button>
        </div>
      </div>
    `;
  }

  // -- Notifications tab -------------------------------------------------
  _renderNotificationsTab() {
    if (!this._notifState) {
      return `<div class="tm-card tm-empty"><p>${this._t("panel.notif_loading")}</p></div>`;
    }
    const ns = this._notifState;
    const services = this._notifyServices || [];

    // Build full recipient list (children + parents) used by matrix columns + chip picker
    const recipients = [
      ...ns.recipients.children.map(c => ({ id: c.id, name: c.name, kind: "child", notify_service: c.notify_service })),
      ...ns.recipients.parents.map(p => ({ id: p.id, name: p.name, kind: "parent", notify_service: p.notify_service, enabled: p.enabled })),
    ];

    return `
      <div class="tm-toolbar">
        <h2 class="tm-toolbar-title">${this._t("panel.notif_tab_title")}</h2>
      </div>

      ${this._renderNotifRecipientsSection(ns, services)}
      ${this._renderNotifMatrixSection(ns, recipients)}
      ${this._renderNotifCustomSection(ns, recipients)}

      <div class="tm-notif-info-box">
        <strong>${this._t("panel.notif_power_user_note_title")}</strong>
        ${this._t("panel.notif_power_user_note_body")}
      </div>
    `;
  }

  _renderNotifRecipientsSection(ns, services) {
    const optTags = (selected) => {
      const opts = [`<option value=""${!selected ? " selected" : ""}>${this._t("panel.notif_none")}</option>`];
      for (const s of services) opts.push(`<option value="${this._esc(s)}"${s === selected ? " selected" : ""}>${this._esc(s)}</option>`);
      return opts.join("");
    };
    return `
      <div class="tm-card" style="margin-bottom:16px">
        <h3>${this._t("panel.notif_section_recipients")}</h3>
        <p class="tm-meta">${this._t("panel.notif_section_recipients_desc")}</p>
        <div class="tm-grid-2">
          <div>
            <h4>${this._t("panel.notif_recipients_children")}</h4>
            ${ns.recipients.children.map(c => `
              <div class="tm-row" style="display:flex;gap:10px;align-items:center;padding:8px 0;border-top:1px solid var(--tm-border,#3a3a3a)">
                <div style="flex:1"><strong>${this._esc(c.name)}</strong></div>
                <select class="tm-notif-select" data-act="notif-set-child-notify" data-child-id="${this._esc(c.id.replace(/^child:/, ""))}">
                  ${optTags(c.notify_service)}
                </select>
              </div>
            `).join("")}
          </div>
          <div>
            <h4>${this._t("panel.notif_recipients_parents")}</h4>
            ${ns.recipients.parents.map(p => `
              <div class="tm-row" style="display:flex;gap:10px;align-items:center;padding:8px 0;border-top:1px solid var(--tm-border,#3a3a3a)">
                <input type="text" value="${this._esc(p.name)}" data-act="notif-rename-parent" data-parent-id="${this._esc(p.id)}" style="flex:1;background:transparent;border:none;color:inherit;font-size:14px;font-weight:500">
                <select class="tm-notif-select" data-act="notif-set-parent-notify" data-parent-id="${this._esc(p.id)}">
                  ${optTags(p.notify_service)}
                </select>
                <button type="button" class="tm-icon-btn" data-act="notif-delete-parent" data-parent-id="${this._esc(p.id)}" title="${this._t("panel.notif_remove_parent")}">×</button>
              </div>
            `).join("")}
            <button type="button" class="tm-btn" data-act="notif-add-parent" style="margin-top:10px;width:100%">+ ${this._t("panel.notif_add_parent")}</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderNotifMatrixSection(ns, recipients) {
    return `
      <div class="tm-card" style="margin-bottom:16px">
        <h3>${this._t("panel.notif_section_matrix")}</h3>
        <p class="tm-meta">${this._t("panel.notif_section_matrix_desc")}</p>
        <div class="tm-table-wrap">
          <table class="tm-table">
            <thead>
              <tr>
                <th style="min-width:280px">${this._t("panel.notif_matrix_col_notification")}</th>
                ${recipients.map(r => `<th style="text-align:center;min-width:80px">${this._esc(r.name)}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${ns.types.map(t => this._renderNotifMatrixRow(t, ns.config[t.id] || { master_enabled: false, routes: {} }, recipients, ns.settings)).join("")}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  _renderNotifMatrixRow(t, c, recipients, settings) {
    const active = !!c.master_enabled;
    return `
      <tr class="${active ? "" : "tm-row-disabled"}">
        <td>
          <div style="display:flex;gap:10px;align-items:flex-start">
            <input type="checkbox" class="tm-notif-switch" data-act="notif-set-master" data-type-id="${this._esc(t.id)}" ${active ? "checked" : ""}>
            <div>
              <strong>${this._t("notification." + t.id + ".name")}</strong>
              <div class="tm-meta">${this._t("notification." + t.id + ".description")}</div>
              ${t.id === "streak_at_risk" ? `
                <div class="tm-meta" style="margin-top:6px;display:flex;align-items:center;gap:8px">
                  ${this._t("panel.notif_streak_cutoff_label")}
                  <input type="time" class="tm-notif-time-input" value="${this._esc(settings.streak_at_risk_cutoff_time || "20:00")}" data-act="notif-set-streak-cutoff" style="display:inline;margin:0;width:90px">
                </div>
              ` : ""}
              <div style="margin-top:6px">
                <button type="button" class="tm-btn" data-act="notif-send-test" data-type-id="${this._esc(t.id)}" style="padding:2px 10px;font-size:12px">
                  <ha-icon icon="mdi:send" style="--mdc-icon-size:14px"></ha-icon> ${this._t("panel.notif_send_test")}
                </button>
              </div>
            </div>
          </div>
        </td>
        ${recipients.map(r => this._renderNotifMatrixCell(t, c, r)).join("")}
      </tr>
    `;
  }

  _renderNotifMatrixCell(t, c, r) {
    const valid =
      t.audience === "both" ||
      (t.audience === "child" && r.kind === "child") ||
      (t.audience === "parent" && r.kind === "parent");
    if (!valid) return `<td class="tm-notif-matrix-cell" style="color:var(--tm-text-muted,#666)">—</td>`;
    const route = c.routes[r.id] || { enabled: false, time: null };
    return `
      <td class="tm-notif-matrix-cell">
        <input type="checkbox" class="tm-notif-switch" data-act="notif-set-route" data-type-id="${this._esc(t.id)}" data-recipient-id="${this._esc(r.id)}" data-time="${this._esc(route.time || "")}" ${route.enabled ? "checked" : ""} ${c.master_enabled ? "" : "disabled"}>
        ${t.per_recipient_time ? `
          <input type="time" class="tm-notif-time-input" data-act="notif-set-route-time" data-type-id="${this._esc(t.id)}" data-recipient-id="${this._esc(r.id)}" value="${this._esc(route.time || "20:00")}" ${(c.master_enabled && route.enabled) ? "" : "disabled"}>
        ` : ""}
      </td>
    `;
  }

  _renderNotifCustomSection(ns, recipients) {
    return `
      <div class="tm-card" style="margin-bottom:16px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <h3>${this._t("panel.notif_section_custom")}</h3>
          <button type="button" class="tm-btn tm-btn-raised" data-act="notif-add-custom">+ ${this._t("panel.notif_add_custom")}</button>
        </div>
        <p class="tm-meta">${this._t("panel.notif_section_custom_desc")}</p>
        ${(ns.custom || []).length === 0 ? `<div class="tm-empty"><p>${this._t("panel.notif_custom_empty")}</p></div>` : ""}
        ${(ns.custom || []).map(n => this._renderNotifCustomCard(n, recipients)).join("")}
      </div>
    `;
  }

  _renderNotifCustomCard(n, recipients) {
    const days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    return `
      <div class="tm-notif-custom-card">
        <div class="tm-notif-custom-row">
          <input type="text" class="tm-input" value="${this._esc(n.name)}" data-act="notif-update-custom" data-custom-id="${this._esc(n.id)}" data-field="name" placeholder="${this._t("panel.notif_custom_name_placeholder")}">
          <input type="time" class="tm-input" value="${this._esc(n.time)}" data-act="notif-update-custom" data-custom-id="${this._esc(n.id)}" data-field="time">
          <input type="checkbox" class="tm-notif-switch" data-act="notif-toggle-custom" data-custom-id="${this._esc(n.id)}" ${n.enabled ? "checked" : ""}>
          <button type="button" class="tm-notif-delete" data-act="notif-delete-custom" data-custom-id="${this._esc(n.id)}" aria-label="${this._t("panel.btn_delete")}">×</button>
        </div>
        <input type="text" class="tm-input tm-notif-custom-msg" value="${this._esc(n.message_template)}" data-act="notif-update-custom" data-custom-id="${this._esc(n.id)}" data-field="message_template" placeholder="${this._t("panel.notif_custom_message_placeholder")}">
        <div class="tm-notif-toggle-group">
          ${days.map((d, i) => {
            const on = !!(n.day_mask & (1 << i));
            return `
              <label class="tm-notif-toggle tm-notif-toggle-day ${on ? "tm-notif-toggle-on" : ""}">
                <input type="checkbox" data-act="notif-toggle-day" data-custom-id="${this._esc(n.id)}" data-day="${i}" ${on ? "checked" : ""}>
                <span>${this._t("panel.notif_day_" + d.toLowerCase())}</span>
              </label>
            `;
          }).join("")}
        </div>
        <div class="tm-notif-toggle-group">
          ${recipients.map(r => {
            const on = n.recipient_ids.includes(r.id);
            const name = (r.name && r.name.trim()) || this._t("panel.notif_unnamed_recipient");
            return `
              <button type="button" class="tm-notif-toggle tm-notif-toggle-pill ${on ? "tm-notif-toggle-on" : ""}"
                      data-act="notif-toggle-recipient" data-custom-id="${this._esc(n.id)}" data-recipient-id="${this._esc(r.id)}"
                      aria-pressed="${on ? "true" : "false"}">
                ${this._esc(name)}
              </button>
            `;
          }).join("")}
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
    if (this._dialog.kind === "badge")       return this._renderBadgeDialog();
    if (this._dialog.kind === "award-badge") return this._renderAwardDialog();
    return "";
  }

  _renderCreateEditTemplateDialog() {
    const d = this._dialog.data;
    const isEdit = this._dialog.kind === "edit-template";
    return `
      <div class="tm-scrim" data-act="scrim">
        <div class="tm-dialog" style="max-width:680px">
          <div class="tm-dialog-head">
            <h2>${isEdit ? this._t("panel.template_edit_title") : this._t("panel.template_create_title")}</h2>
            <button type="button" class="tm-icon-btn" data-act="close-dialog">✕</button>
          </div>
          <div class="tm-dialog-body">
            <div class="tm-field-row" style="margin-bottom:16px">
              <div class="tm-field"><span class="tm-field-label">${this._t("panel.template_name_label")}</span><input class="tm-input" type="text" data-field="name" value="${this._esc(d.name)}"></div>
              <div class="tm-field"><span class="tm-field-label">${this._t("panel.template_icon_label")}</span><input class="tm-input" type="text" data-field="icon" value="${this._esc(d.icon)}"></div>
            </div>
            <label class="tm-field-label" style="display:block;margin-bottom:8px">${this._t("panel.template_chores_in_template")}</label>
            ${(d.chores || []).map((c, i) => `
              <div class="tm-tpl-preview-card" style="margin-bottom:8px">
                <div style="display:flex;align-items:center;gap:10px;padding:10px 14px">
                  <span style="font-weight:600;flex:1">${this._esc(c.name || this._t("panel.template_unnamed"))}</span>
                  <span class="tm-meta">${this._t("panel.pts_display", {count: c.points || 0})}</span>
                  <button type="button" class="tm-tpl-remove" data-act="tpl-dialog-remove-chore" data-idx="${i}">✕</button>
                </div>
                <div style="padding:0 14px 12px;border-top:1px solid var(--tm-border-soft)">
                  <div class="tm-field-row" style="margin-top:10px">
                    <div class="tm-field"><span class="tm-field-label">${this._t("panel.common_name")}</span><input class="tm-input" type="text" data-tpl-dialog-field="name" data-tpl-dialog-idx="${i}" value="${this._esc(c.name)}"></div>
                    <div class="tm-field"><span class="tm-field-label">${this._t("panel.common_points")}</span><input class="tm-input" type="number" data-tpl-dialog-field="points" data-tpl-dialog-idx="${i}" value="${c.points || 0}" min="0"></div>
                  </div>
                  <div class="tm-field-row">
                    <div class="tm-field"><span class="tm-field-label">${this._t("panel.chore_time_category_label")}</span>
                      <select class="tm-select" data-tpl-dialog-field="time_category" data-tpl-dialog-idx="${i}">
                        ${this._timeCategoryOptions().map(t => `<option value="${this._esc(t.v)}" ${c.time_category === t.v ? "selected" : ""}>${this._esc(t.l)}</option>`).join("")}
                      </select>
                    </div>
                    <div class="tm-field"><span class="tm-field-label">${this._t("panel.template_schedule_label")}</span>
                      <select class="tm-select" data-tpl-dialog-field="schedule_mode" data-tpl-dialog-idx="${i}">
                        ${SCHEDULE_MODES.map(s => `<option value="${s.v}" ${c.schedule_mode === s.v ? "selected" : ""}>${this._t(s.lk)}</option>`).join("")}
                      </select>
                    </div>
                  </div>
                </div>
              </div>
            `).join("")}
            <button type="button" class="tm-btn" data-act="tpl-dialog-add-chore" style="margin-top:8px">${this._t("panel.btn_add_chore_template")}</button>
          </div>
          <div class="tm-dialog-foot">
            <button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_cancel")}</button>
            <button type="button" class="tm-btn tm-btn-raised" data-act="${isEdit ? "tpl-save-edited" : "tpl-save-created"}">${isEdit ? this._t("panel.btn_save_changes") : this._t("panel.btn_create_template")}</button>
          </div>
        </div>
      </div>
    `;
  }

  _renderChildDialog() {
    const d = this._dialog.data;
    const hasAvail = !!(d.availability_entity && d.availability_entity.trim());
    return this._dialogShell(this._dialog.mode === "add" ? this._t("panel.dialog_add_child") : this._t("panel.dialog_edit_child"),
      [
        this._field(this._t("panel.child_name_label"), "name", d.name, "text", this._t("panel.child_name_placeholder")),
        this._iconPickerField(this._t("panel.child_avatar_label"), "avatar", d.avatar),
        this._entityPickerField(this._t("panel.child_availability_label"), "availability_entity", d.availability_entity, ["binary_sensor", "sensor", "input_boolean", "person"],
          this._t("panel.child_availability_hint")),
        hasAvail ? this._switch(this._t("panel.child_invert_label"), "availability_inverted", d.availability_inverted,
          this._t("panel.child_invert_hint")) : "",
        this._entityPickerField(this._t("panel.child_unavailability_label"), "unavailability_entity", d.unavailability_entity, ["binary_sensor", "sensor", "input_boolean", "person", "calendar"],
          this._t("panel.child_unavailability_hint")),
        this._select(
          this._t("panel.child_link_user_label"), "linked_user_id", d.linked_user_id || "",
          [{ v: "", l: this._t("panel.child_link_user_none") }].concat(
            (this._haUsers || []).map(u => ({ v: u.id, l: u.is_admin ? `${u.name} (admin)` : u.name }))
          ),
          this._t("panel.child_link_user_hint")),
      ].join(""),
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_cancel")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="save-child">${this._t("panel.btn_save")}</button>`
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
    const isUnassigned     = d.assignment_mode === "unassigned";
    const calendarEntities = Object.keys((this._hass && this._hass.states) || {})
      .filter(id => id.startsWith("calendar."))
      .sort();

    const isTimedTask = d.task_type === "timed";

    return this._dialogShell(this._dialog.mode === "add" ? this._t("panel.dialog_add_chore") : this._t("panel.dialog_edit_chore"),
      [
        this._field(this._t("panel.chore_name_label"), "name", d.name, "text"),
        this._field(this._t("panel.chore_description_label"), "description", d.description, "text"),
        this._select(this._t("panel.chore_task_type_label"), "task_type", d.task_type || "standard", [
          { v: "standard", l: this._t("panel.chore_task_type_standard") },
          { v: "timed", l: this._t("panel.chore_task_type_timed") },
        ], "", true),
        isTimedTask ? `<div class="tm-field-row">
          ${this._field(this._t("panel.chore_points_per_window_label"), "timed_rate_points", d.timed_rate_points || 10, "number")}
          ${this._field(this._t("panel.chore_window_minutes_label"), "timed_rate_minutes", d.timed_rate_minutes || 5, "number")}
        </div>
        <div class="tm-field-row">
          ${this._field(this._t("panel.chore_daily_cap_label"), "timed_max_daily_minutes", d.timed_max_daily_minutes || 0, "number")}
          ${this._field(this._t("panel.chore_daily_limit_label"), "daily_limit", d.daily_limit, "number")}
        </div>` : `<div class="tm-field-row">
          ${this._field(this._t("panel.chore_points_label"), "points", d.points, "number")}
          ${d.assignment_mode === "first_come" ? "" : this._field(this._t("panel.chore_daily_limit_label"), "daily_limit", d.daily_limit, "number")}
        </div>`,
        this._select(this._t("panel.chore_assignment_mode_label"), "assignment_mode", d.assignment_mode, ASSIGNMENT_MODES,
          this._t("panel.chore_assignment_mode_hint"), true),
        !isUnassigned ? (children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.chore_assign_label")}</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">${this._t("panel.chore_assign_hint")}</span>
          </div>
        ` : `<div class="tm-field"><span class="tm-field-hint">${this._t("panel.chore_assign_no_children")}</span></div>`) : "",
        showRotation && children.length > 0 ? this._select(
          this._t("panel.chore_rotation_label"), "manual_start_child_id", d.manual_start_child_id,
          [{ v: "", l: this._t("panel.chore_rotation_no_override") }, ...children.map(c => ({ v: c.id, l: c.name }))],
          this._t("panel.chore_rotation_hint")
        ) : "",
        this._select(this._t("panel.chore_time_category_label"), "time_category", d.time_category, this._timeCategoryOptions()),
        this._field(this._t("panel.chore_claim_allowance_label"), "claim_allowance_minutes", d.claim_allowance_minutes, "number",
          this._t("panel.chore_claim_allowance_hint")),
        this._select(this._t("panel.chore_schedule_mode_label"), "schedule_mode", d.schedule_mode, SCHEDULE_MODES, "", true),
        showSpecificDays ? `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.chore_days_label")}</span>
            <div class="tm-day-row">
              ${DAYS.map(day => `
                <button type="button" class="tm-day-btn ${(d.due_days || []).includes(day.v) ? "tm-day-on" : ""}" data-act="toggle-day" data-day="${day.v}">${this._t(day.lk)}</button>
              `).join("")}
            </div>
          </div>
        ` : "",
        showRecurring ? `
          <div class="tm-field-row">
            ${this._select(this._t("panel.chore_recurrence_label"), "recurrence", d.recurrence, RECURRENCES)}
            ${this._field(this._t("panel.chore_recurrence_day_label"), "recurrence_day", d.recurrence_day, "text", this._t("panel.chore_recurrence_day_hint"))}
          </div>
          <div class="tm-field-row">
            ${this._dateField(this._t("panel.chore_recurrence_start_label"), "recurrence_start", d.recurrence_start, this._t("panel.chore_recurrence_start_hint"))}
            ${this._select(this._t("panel.chore_first_occurrence_label"), "first_occurrence_mode", d.first_occurrence_mode, FIRST_OCCURRENCE)}
          </div>
        ` : "",
        this._select(this._t("panel.chore_completion_sound_label"), "completion_sound", d.completion_sound, COMPLETION_SOUNDS.map(s => ({ v: s, l: s }))),
        this._switch(this._t("panel.chore_approval_label"), "requires_approval", d.requires_approval),
        this._switch(this._t("panel.chore_require_availability"), "require_availability", d.require_availability,
          this._t("panel.chore_require_availability_hint")),
        memberInGroup ? `
          <div class="tm-field">
            <span class="tm-field-hint">${this._t("panel.chore_group_hint", {name: this._esc(memberInGroup.name), policy: memberInGroup.policy})}</span>
          </div>
        ` : "",
        `<details class="tm-advanced" data-section="bonus_subtasks"${this._dialog._openAdvanced?.has("bonus_subtasks") ? " open" : ""}>
          <summary>${this._t("panel.chore_advanced_bonus_subtasks")}</summary>
          <div>
            <span class="tm-field-hint" style="margin-bottom:8px;display:block">${this._t("panel.chore_advanced_bonus_subtasks_hint")}</span>
            ${(d.bonus_subtasks || []).map((b, idx) => `
              <div class="tm-field-row" style="align-items:flex-end;gap:6px;margin-bottom:6px">
                <div class="tm-field" style="flex:2;margin:0"><input class="tm-input" placeholder="${this._t("panel.chore_subtask_name_placeholder")}" value="${this._esc(b.name)}" data-field="bonus_subtasks[${idx}].name"></div>
                <div class="tm-field" style="flex:0 0 70px;margin:0"><input class="tm-input" type="number" min="0" placeholder="${this._t("panel.chore_subtask_points_placeholder")}" value="${b.points}" data-field="bonus_subtasks[${idx}].points"></div>
                <button type="button" class="tm-btn tm-btn-icon" data-act="remove-bonus-subtask" data-idx="${idx}" title="${this._t("panel.tooltip_remove")}" style="padding:6px 10px">✕</button>
              </div>
            `).join("")}
            <button type="button" class="tm-btn" data-act="add-bonus-subtask" style="margin-top:4px">${this._t("panel.btn_add_bonus_subtask")}</button>
          </div>
        </details>`,
        `<details class="tm-advanced" data-section="visibility"${this._dialog._openAdvanced?.has("visibility") ? " open" : ""}>
          <summary>${this._t("panel.chore_advanced_visibility")}</summary>
          <div>
            ${this._entityPickerField(this._t("panel.chore_vis_entity_label"), "visibility_entity", d.visibility_entity, ["binary_sensor", "sensor", "switch", "input_boolean", "input_select"],
              this._t("panel.chore_vis_entity_hint"))}
            <div class="tm-field-row">
              ${this._select(this._t("panel.chore_vis_operator_label"), "visibility_operator", d.visibility_operator, VISIBILITY_OPS)}
              ${this._field(this._t("panel.chore_vis_value_label"), "visibility_state", d.visibility_state, "text", this._t("panel.chore_vis_value_hint"))}
            </div>
            <div class="tm-field">
              <span class="tm-field-label">${this._t("panel.chore_calendar_label")}</span>
              ${calendarEntities.length === 0 ? `<span class="tm-field-hint">${this._t("panel.chore_calendar_no_entities")}</span>` : `
                <div class="tm-chip-row">
                  ${calendarEntities.map(cid => `
                    <button type="button" class="tm-chip-btn ${(d.publish_calendar_entities || []).includes(cid) ? "tm-chip-on" : ""}" data-act="toggle-calendar" data-id="${this._esc(cid)}">
                      ${this._esc(cid)}
                    </button>
                  `).join("")}
                </div>
                <span class="tm-field-hint">${this._t("panel.chore_calendar_hint")}</span>
              `}
            </div>
            ${this._switch(this._t("panel.chore_enabled_label"), "enabled", d.enabled !== false)}
          </div>
        </details>`,
      ].join(""),
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_cancel")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="save-chore">${this._t("panel.btn_save")}</button>`
    );
  }

  _renderRewardDialog() {
    const d = this._dialog.data;
    const children = this._state.children || [];
    const pointsName = this._state.settings.points_name || this._t("common.points");
    return this._dialogShell(this._dialog.mode === "add" ? this._t("panel.dialog_add_reward") : this._t("panel.dialog_edit_reward"),
      [
        this._field(this._t("panel.chore_name_label"), "name", d.name, "text"),
        this._field(this._t("panel.chore_description_label"), "description", d.description, "text"),
        `<div class="tm-field-row">
          ${this._field(this._t("panel.reward_cost_label", {points_name: pointsName}), "cost", d.cost, "number")}
          ${this._iconPickerField(this._t("panel.reward_icon_label"), "icon", d.icon)}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.reward_assigned_label")}</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-reward-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">${this._t("panel.reward_assigned_hint")}</span>
          </div>
        ` : "",
        this._switch(this._t("panel.reward_pool_label"), "pool_enabled", d.pool_enabled,
          this._t("panel.reward_pool_hint")),
        this._switch(this._t("panel.reward_is_jackpot_label"), "is_jackpot", d.is_jackpot,
          this._t("panel.reward_is_jackpot_hint")),
        `<div class="tm-field-row">
          ${this._field(this._t("panel.reward_quantity_label"), "quantity_str", d.quantity_str, "text", this._t("panel.reward_quantity_hint"))}
          ${this._dateField(this._t("panel.reward_expires_label"), "expires_at", d.expires_at, this._t("panel.reward_expires_hint"))}
        </div>`,
      ].join(""),
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_cancel")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="save-reward">${this._t("panel.btn_save")}</button>`
    );
  }

  _renderPenBonDialog(kind) {
    const d = this._dialog.data;
    const children = this._state.children || [];
    const isPenalty = kind === "penalty";
    return this._dialogShell(this._dialog.mode === "add" ? (isPenalty ? this._t("panel.dialog_add_penalty") : this._t("panel.dialog_add_bonus")) : (isPenalty ? this._t("panel.dialog_edit_penalty") : this._t("panel.dialog_edit_bonus")),
      [
        this._field(this._t("panel.chore_name_label"), "name", d.name, "text"),
        this._field(this._t("panel.chore_description_label"), "description", d.description, "text"),
        `<div class="tm-field-row">
          ${this._field(this._t(isPenalty ? "panel.penbon_points_deduct" : "panel.penbon_points_award"), "points", d.points, "number")}
          ${this._iconPickerField(this._t("panel.reward_icon_label"), "icon", d.icon)}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.penbon_applies_to")}</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-penbon-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">${this._t("panel.penbon_applies_to_hint")}</span>
          </div>
        ` : "",
      ].join(""),
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_cancel")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="save-${kind}">${this._t("panel.btn_save")}</button>`
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
    return this._dialogShell(isPenalty ? this._t("panel.dialog_apply_penalty", {name: item.name}) : this._t("panel.dialog_apply_bonus", {name: item.name}),
      `<p>${isPenalty ? this._t("panel.penalty_apply_text", {points: item.points}) : this._t("panel.bonus_apply_text", {points: item.points})}</p>
       ${eligible.length === 0 ? `<p class="tm-meta">${this._t("panel.penbon_no_eligible", {kind})}</p>` : `
        <div class="tm-chip-row" style="margin-top: 12px;">
          ${eligible.map(c => `
            <button type="button" class="tm-btn" data-act="do-apply-${kind}" data-id="${this._esc(item.id)}" data-child="${this._esc(c.id)}">
              ${this._esc(c.name)}
            </button>
          `).join("")}
        </div>
       `}`,
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_close")}</button>`
    );
  }

  _renderGroupDialog() {
    const d = this._dialog.data;
    const chores = (this._state.chores || []).filter(c => c.assignment_mode && !["everyone", "first_come"].includes(c.assignment_mode));
    return this._dialogShell(this._dialog.mode === "add" ? this._t("panel.dialog_add_group") : this._t("panel.dialog_edit_group"),
      [
        this._field(this._t("panel.common_name"), "name", d.name, "text"),
        this._select(this._t("panel.group_policy_label"), "policy", d.policy, TASK_GROUP_POLICIES,
          this._t("panel.group_policy_hint")),
        chores.length === 0 ? `
          <div class="tm-field">
            <span class="tm-field-hint">${this._t("panel.group_no_rotation_chores")}</span>
          </div>
        ` : `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.group_chores_label")}</span>
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
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_cancel")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="save-group">${this._t("panel.btn_save")}</button>`
    );
  }

  _renderBulkChoreDialog() {
    const d = this._dialog.data;
    const children = this._state.children || [];
    return this._dialogShell(this._t("panel.bulk_title"),
      [
        `<div class="tm-field">
          <span class="tm-field-label">${this._t("panel.bulk_chore_names_label")}</span>
          <textarea class="tm-textarea" data-field="chore_names" rows="6" placeholder="${this._t("panel.bulk_chore_names_placeholder")}">${this._esc(d.chore_names || "")}</textarea>
          <span class="tm-field-hint">${this._t("panel.bulk_chore_names_hint")}</span>
        </div>`,
        `<div class="tm-field-row">
          ${this._field(this._t("panel.bulk_points_label"), "points", d.points, "number")}
          ${this._field(this._t("panel.chore_daily_limit_label"), "daily_limit", d.daily_limit, "number")}
        </div>`,
        children.length > 0 ? `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.bulk_assigned_to")}</span>
            <div class="tm-chip-row">
              ${children.map(c => `
                <button type="button" class="tm-chip-btn ${(d.assigned_to || []).includes(c.id) ? "tm-chip-on" : ""}" data-act="toggle-assigned" data-id="${this._esc(c.id)}">
                  ${this._esc(c.name)}
                </button>
              `).join("")}
            </div>
            <span class="tm-field-hint">${this._t("panel.bulk_leave_empty_hint")}</span>
          </div>
        ` : "",
        this._select(this._t("panel.chore_time_category_label"), "time_category", d.time_category, this._timeCategoryOptions()),
        this._select(this._t("panel.chore_schedule_mode_label"), "schedule_mode", d.schedule_mode, SCHEDULE_MODES, "", true),
        d.schedule_mode === "specific_days" ? `
          <div class="tm-field">
            <span class="tm-field-label">${this._t("panel.bulk_days_label")}</span>
            <div class="tm-day-row">
              ${DAYS.map(day => `
                <button type="button" class="tm-day-btn ${(d.due_days || []).includes(day.v) ? "tm-day-on" : ""}" data-act="toggle-bulk-day" data-day="${day.v}">${this._t(day.lk)}</button>
              `).join("")}
            </div>
          </div>
        ` : "",
        this._select(this._t("panel.chore_completion_sound_label"), "completion_sound", d.completion_sound, COMPLETION_SOUNDS.map(s => ({ v: s, l: s }))),
        this._switch(this._t("panel.chore_approval_label"), "requires_approval", d.requires_approval),
      ].join(""),
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_cancel")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="save-bulk-chores">${this._t("panel.btn_create_chores")}</button>`
    );
  }

  _renderReorderDialog() {
    const d = this._dialog.data;
    const choreById = Object.fromEntries((this._state.chores || []).map(c => [c.id, c]));
    const title = d.global ? this._t("panel.reorder_global_title") : this._t("panel.reorder_title", {name: d.name});
    const hint = d.global ? this._t("panel.reorder_global_hint") : this._t("panel.reorder_hint");
    return this._dialogShell(title,
      `<p class="tm-meta">${hint}</p>
       <div class="tm-reorder-list">
         ${(d.order || []).map((id, idx, arr) => {
           const c = choreById[id];
           if (!c) return "";
           return `
             <div class="tm-reorder-item" draggable="true" data-drag-id="${this._esc(id)}">
               <div class="tm-reorder-handle">⠿</div>
               <div class="tm-reorder-name">${this._esc(c.name)}</div>
               <div class="tm-reorder-points tm-numeric">${c.points}</div>
               <div class="tm-reorder-moves">
                 <button type="button" class="tm-reorder-move" data-act="reorder-move" data-dir="-1" data-drag-id="${this._esc(id)}" ${idx === 0 ? "disabled" : ""} title="${this._t("reorder.move_up")}" aria-label="${this._t("reorder.move_up")}">▲</button>
                 <button type="button" class="tm-reorder-move" data-act="reorder-move" data-dir="1" data-drag-id="${this._esc(id)}" ${idx === arr.length - 1 ? "disabled" : ""} title="${this._t("reorder.move_down")}" aria-label="${this._t("reorder.move_down")}">▼</button>
               </div>
             </div>
           `;
         }).join("")}
       </div>`,
      `<button type="button" class="tm-btn" data-act="close-dialog">${this._t("panel.btn_cancel")}</button>
       <button type="button" class="tm-btn tm-btn-raised" data-act="save-chore-order">${this._t("panel.btn_save_order")}</button>`
    );
  }

  // ---- form helpers ----------------------------------------------------
  _dialogShell(title, body, footer) {
    return `
      <div class="tm-scrim" data-act="scrim">
        <div class="tm-dialog">
          <header class="tm-dialog-head">
            <h2>${this._esc(title)}</h2>
            <button type="button" class="tm-icon-btn" data-act="close-dialog" title="${this._t("panel.tooltip_close")}">&times;</button>
          </header>
          <div class="tm-dialog-body">${body}</div>
          <footer class="tm-dialog-foot">${footer}</footer>
        </div>
      </div>`;
  }

  _field(label, name, value, type = "text", hint = "") {
    return `
      <div class="tm-field">
        <span class="tm-field-label">${this._esc(label)}</span>
        <input
          class="tm-input"
          data-field="${name}"
          value="${this._esc(value == null ? "" : value)}"
          ${type === "number" ? 'type="number"' : 'type="text"'}
        >
        ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
      </div>`;
  }

  _dateField(label, name, value, hint = "") {
    return `
      <div class="tm-field">
        <span class="tm-field-label">${this._esc(label)}</span>
        <input
          class="tm-input"
          data-field="${name}"
          value="${this._esc(value || "")}"
          type="date"
        >
        ${hint ? `<span class="tm-field-hint">${hint}</span>` : ""}
      </div>`;
  }

  _select(label, name, value, options, hint = "", rerender = false) {
    return `
      <div class="tm-field">
        <span class="tm-field-label">${this._esc(label)}</span>
        <select
          class="tm-select"
          data-field="${name}"
          ${rerender ? 'data-rerender="true"' : ""}
        >
          ${options.map(o => `<option value="${this._esc(o.v)}" ${String(o.v) === String(value) ? "selected" : ""}>${this._esc(o.lk ? this._t(o.lk) : o.l)}</option>`).join("")}
        </select>
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
                <button type="button" class="tm-entity-clear" data-act="clear-field" data-field="${name}" title="${this._t("panel.tooltip_clear")}">✕</button>
              </div>`
            : `<div class="tm-ep-search-wrap">
                <ha-icon icon="mdi:magnify" class="tm-ep-search-icon"></ha-icon>
                <input type="text" class="tm-ep-input" placeholder="${this._t("panel.entity_search_placeholder")}" value="" autocomplete="off">
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
        <button type="button" class="tm-btn tm-btn-raised" data-act="${action}">${this._esc(label)}</button>
      </div>
    `;
  }

  _idBadge(id) {
    if (!this._showIds || !id) return "";
    return `<span class="tm-id-badge"><code>${this._esc(id)}</code><button type="button" class="tm-id-copy" data-act="copy-id" data-id="${this._esc(id)}" title="${this._t("panel.toast_copied")}"><ha-icon icon="mdi:content-copy"></ha-icon></button></span>`;
  }

  _labelOf(arr, val) {
    const item = arr.find(x => x.v === val);
    if (!item) return val || "";
    return item.lk ? this._t(item.lk) : (item.l || val || "");
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
        --tm-accent-hover:  color-mix(in srgb, var(--primary-color, #03a9f4), #000 14%);
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
      .tm-shell > [data-zone], .tm-main > [data-zone] { display: contents; }

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
      .tm-menu-btn {
        display: none;
        background: transparent;
        border: 0;
        color: var(--tm-text);
        padding: 6px;
        margin-left: -6px;
        border-radius: 8px;
        cursor: pointer;
        align-items: center; justify-content: center;
      }
      .tm-menu-btn:hover { background: var(--tm-surface-2); }
      .tm-menu-btn ha-icon { --mdc-icon-size: 22px; }
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
        box-sizing: border-box;
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
        background: var(--tm-accent-hover);
        border-color: var(--tm-accent-hover);
        color: var(--text-primary-color, #fff);
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
      .tm-row-actions { text-align: right; white-space: nowrap; }
      .tm-row-actions > div { display: inline-flex; gap: 4px; align-items: center; }
      .tm-numeric { font-feature-settings: "tnum"; }
      .tm-yes { color: var(--tm-positive); font-weight: 500; }
      .tm-no  { color: var(--tm-text-faint); }
      .tm-neg { color: var(--tm-danger); }
      .tm-pos { color: var(--tm-positive); }
      .tm-current-assignee { color: var(--tm-accent); font-weight: 600; }
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
      .tm-pill-first_come { background: var(--tm-gold-soft); color: var(--tm-gold); border-color: color-mix(in srgb, var(--tm-gold), transparent 75%); }
      .tm-pill-unassigned { background: var(--tm-muted-bg, #f0f0f0); color: var(--tm-text-muted); border-color: var(--tm-border); }
      .tm-pill-dot::before {
        content: ""; width: 5px; height: 5px; border-radius: 50%;
        background: currentColor;
      }

      /* ID badge (Show IDs toggle) */
      .tm-id-badge {
        display: inline-flex; align-items: center; gap: 4px;
        margin-top: 2px;
      }
      .tm-id-badge code {
        font-family: ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace;
        font-size: 10.5px; color: var(--tm-text-faint);
        background: var(--tm-surface-2); padding: 1px 6px;
        border-radius: 4px; user-select: all;
      }
      .tm-id-copy {
        background: none; border: none; cursor: pointer;
        padding: 2px; border-radius: 4px;
        color: var(--tm-text-faint); display: inline-flex; align-items: center;
        transition: color 0.15s;
      }
      .tm-id-copy:hover { color: var(--tm-accent); }
      .tm-id-copy ha-icon { --mdc-icon-size: 14px; }

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
      .tm-difficulty-mults { display: flex; gap: 12px; flex-wrap: wrap; }
      .tm-difficulty-mults label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--tm-text-faint); }
      .tm-difficulty-mults .tm-input { width: 90px; }
      .tm-setting-row ha-textfield,
      .tm-setting-row ha-select,
      .tm-setting-row input.tm-input,
      .tm-setting-row select.tm-select {
        max-width: 360px;
      }
      .tm-time-pair {
        display: flex; align-items: center; gap: 8px;
      }
      .tm-time-pair .tm-input { max-width: 130px; }
      .tm-time-pair span { color: var(--tm-text-faint); }
      .tm-period-row {
        grid-template-columns: 56px minmax(140px, 1fr) auto 36px;
        gap: 12px;
      }
      .tm-period-row ha-icon-picker { max-width: 56px; }
      .tm-period-row > .tm-input { max-width: none; }
      .tm-vacation-row {
        grid-template-columns: minmax(140px, 1fr) auto 36px;
        gap: 12px;
      }
      .tm-vacation-row > .tm-input { max-width: none; }
      .tm-audit-row {
        display: grid;
        grid-template-columns: 180px 130px 180px 1fr;
        gap: 12px;
        padding: 8px 20px;
        border-top: 1px solid var(--tm-border-soft);
        font-size: 13px;
      }
      .tm-audit-row:first-child { border-top: 0; }
      .tm-audit-head { font-weight: 600; color: var(--tm-text-faint); }
      .tm-audit-when, .tm-audit-user { color: var(--tm-text-faint); }
      .tm-audit-action { font-family: var(--code-font-family, monospace); }
      @media (max-width: 700px) {
        .tm-audit-row { grid-template-columns: 1fr 1fr; }
        .tm-audit-head { display: none; }
      }
      .tm-period-del {
        color: var(--tm-text-faint);
      }
      .tm-period-del:not([disabled]):hover { color: var(--error-color, #d9434f); }
      .tm-period-del[disabled] { opacity: .5; cursor: not-allowed; }
      .tm-period-inuse {
        grid-column: 1 / -1;
        font-size: 12px; color: var(--tm-text-faint);
        margin-top: -6px;
      }
      .tm-period-anytime {
        grid-template-columns: 56px 1fr;
        color: var(--tm-text-faint);
      }
      .tm-period-anytime ha-icon { margin: 0 auto; }
      .tm-period-actions {
        display: flex; gap: 10px;
        padding: 14px 20px;
        border-top: 1px solid var(--tm-border-soft);
      }
      @media (max-width: 700px) {
        .tm-period-row { grid-template-columns: 48px 1fr 36px; }
        .tm-period-row .tm-time-pair { grid-column: 1 / -1; }
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
      .tm-input, .tm-select {
        width: 100%; box-sizing: border-box;
        background: var(--tm-surface-0);
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
        padding: 10px 12px;
        color: var(--tm-text);
        font-size: 13px; font-family: inherit;
        box-shadow: var(--tm-shadow-xs);
        transition: all 0.1s var(--tm-easing);
      }
      .tm-input:hover, .tm-select:hover { border-color: var(--tm-border-strong); }
      .tm-input:focus, .tm-select:focus { outline: 0; border-color: var(--tm-accent); box-shadow: var(--tm-shadow-focus); }
      .tm-input::placeholder { color: var(--tm-text-vfaint); }
      .tm-select {
        cursor: pointer;
        appearance: none; -webkit-appearance: none;
        padding-right: 32px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24'%3E%3Cpath fill='%23888' d='M7 10l5 5 5-5z'/%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: right 10px center;
      }
      .tm-select option { background: var(--tm-surface-0); color: var(--tm-text); }
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
      .tm-reorder-moves { display: flex; flex-direction: column; gap: 2px; }
      .tm-reorder-move {
        display: flex; align-items: center; justify-content: center;
        width: 28px; height: 20px; padding: 0;
        border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm);
        background: var(--tm-surface-1);
        color: var(--tm-text);
        font-size: 10px; line-height: 1;
        cursor: pointer;
        transition: all 0.12s var(--tm-easing);
      }
      .tm-reorder-move:hover:not(:disabled) { border-color: var(--tm-accent); color: var(--tm-accent); }
      .tm-reorder-move:disabled { opacity: 0.3; cursor: default; }

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

      /* ===== Badges ===== */
      .tm-badge-subtabs {
        display: flex; gap: 2px; border-bottom: 1px solid var(--tm-border);
        margin-bottom: 16px;
      }
      .tm-badge-subtab {
        padding: 9px 14px; font-size: 13px; font-weight: 500;
        color: var(--tm-text-muted); background: transparent; border: 0;
        border-bottom: 2px solid transparent; margin-bottom: -1px;
        cursor: pointer; font-family: inherit; transition: color 0.1s;
      }
      .tm-badge-subtab:hover { color: var(--tm-text); }
      .tm-badge-subtab-active { color: var(--tm-accent); border-bottom-color: var(--tm-accent); }

      .tm-badge-row td { vertical-align: middle; }

      /* tier colour token */
      .tm-badge-tier-bronze   { --badge-t: #cd7f32; }
      .tm-badge-tier-silver   { --badge-t: #c0c0c0; }
      .tm-badge-tier-gold     { --badge-t: #f1c40f; }
      .tm-badge-tier-platinum { --badge-t: #67e8f9; }

      .tm-badge-icon-sm {
        width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
        background: var(--badge-t, #cd7f32);
        display: inline-flex; align-items: center; justify-content: center;
        color: #1a1a1a; --mdc-icon-size: 18px; vertical-align: middle;
      }
      .tm-badge-tier-label {
        font-size: 10.5px; font-weight: 700; text-transform: uppercase;
        letter-spacing: 1px; color: var(--badge-t, #cd7f32);
      }
      .tm-badge-criteria {
        font-family: ui-monospace, monospace; font-size: 11.5px;
        color: var(--tm-text-muted); white-space: nowrap;
      }
      .tm-badge-toggle {
        width: 36px; height: 20px; border-radius: 999px;
        background: var(--tm-border-strong); border: 0; cursor: pointer;
        position: relative; transition: background 0.15s; flex-shrink: 0;
      }
      .tm-badge-toggle::after {
        content: ""; position: absolute; top: 2px; left: 2px;
        width: 16px; height: 16px; border-radius: 50%;
        background: #fff; transition: transform 0.15s;
      }
      .tm-badge-toggle-on { background: var(--tm-accent); }
      .tm-badge-toggle-on::after { transform: translateX(16px); }

      .tm-badge-src {
        font-size: 10px; font-weight: 700; padding: 2px 8px;
        border-radius: 999px; background: var(--tm-surface-2); color: var(--tm-text-muted);
      }
      .tm-badge-src-manual { background: #3a2a1a; color: #f1c40f; }
      .tm-badge-src-silent  { background: var(--tm-surface-2); color: var(--tm-text-faint); }
      .tm-badge-src-auto    { background: var(--tm-accent-soft); color: var(--tm-accent-text); }

      .tm-badge-criteria-block {
        background: var(--tm-surface-0); border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm); padding: 12px; margin-top: 6px;
      }
      .tm-badge-criterion-row {
        display: grid; grid-template-columns: 1.4fr 30px 0.8fr 28px;
        gap: 6px; align-items: center; margin-bottom: 8px;
      }
      .tm-badge-op { font-size: 16px; text-align: center; color: var(--tm-text-muted); }

      /* ===== Notifications: custom card buttons ===== */
      .tm-notif-custom-card {
        margin-top: 10px;
        padding: 14px;
        background: var(--tm-surface-1);
        border: 1px solid var(--tm-border);
        border-radius: 10px;
      }
      .tm-notif-custom-row {
        display: grid;
        grid-template-columns: 1fr 110px 42px 32px;
        gap: 10px;
        align-items: center;
        margin-bottom: 10px;
      }
      .tm-notif-custom-msg { width: 100%; margin-bottom: 12px; }
      .tm-notif-toggle-group {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        margin-bottom: 8px;
      }
      .tm-notif-toggle-group:last-child { margin-bottom: 0; }
      .tm-notif-toggle {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        padding: 7px 14px;
        font-size: 12.5px;
        font-weight: 500;
        font-family: inherit;
        line-height: 1.2;
        background: var(--tm-surface-0);
        color: var(--tm-text);
        border: 1px solid var(--tm-border);
        transition: background 0.12s var(--tm-easing), color 0.12s var(--tm-easing), border-color 0.12s var(--tm-easing);
        user-select: none;
      }
      .tm-notif-toggle:hover {
        background: var(--tm-accent-soft);
        border-color: var(--tm-accent);
        color: var(--tm-accent-text);
      }
      .tm-notif-toggle input[type="checkbox"] { display: none; }
      .tm-notif-toggle-day { border-radius: var(--tm-radius-sm); min-width: 46px; }
      .tm-notif-toggle-pill { border-radius: 999px; }
      .tm-notif-toggle-on {
        background: var(--tm-accent);
        color: var(--text-primary-color, #fff);
        border-color: var(--tm-accent);
      }
      .tm-notif-toggle-on:hover {
        background: var(--tm-accent-hover);
        color: var(--text-primary-color, #fff);
        border-color: var(--tm-accent-hover);
      }

      /* Notification toggle switches (CSS-only on native checkbox) */
      .tm-notif-switch {
        -webkit-appearance: none;
        appearance: none;
        width: 38px; height: 22px;
        background: var(--tm-border-strong);
        border: none; border-radius: 999px;
        cursor: pointer; position: relative;
        transition: background 0.15s;
        flex-shrink: 0; vertical-align: middle;
        margin: 0;
      }
      .tm-notif-switch::after {
        content: ""; position: absolute;
        top: 3px; left: 3px;
        width: 16px; height: 16px; border-radius: 50%;
        background: #fff; transition: transform 0.15s;
      }
      .tm-notif-switch:checked { background: var(--tm-accent); }
      .tm-notif-switch:checked::after { transform: translateX(16px); }
      .tm-notif-switch:disabled { opacity: 0.35; cursor: not-allowed; }

      /* Notification matrix cells */
      .tm-notif-matrix-cell { text-align: center; vertical-align: middle; }
      .tm-notif-time-input {
        display: block; margin: 6px auto 0; width: 86px;
        font-size: 12px; padding: 5px 6px; text-align: center;
        background: var(--tm-surface-0); border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm); color: var(--tm-text);
        font-family: inherit; transition: border-color 0.1s;
      }
      .tm-notif-time-input:focus {
        outline: 0; border-color: var(--tm-accent);
        box-shadow: var(--tm-shadow-focus);
      }
      .tm-notif-time-input:disabled { opacity: 0.35; }

      /* Notification recipient selects */
      .tm-notif-select {
        background: var(--tm-surface-0); border: 1px solid var(--tm-border);
        border-radius: var(--tm-radius-sm); padding: 7px 10px;
        color: var(--tm-text); font-size: 12.5px; font-family: inherit;
        cursor: pointer; max-width: 240px; transition: border-color 0.1s;
      }
      .tm-notif-select:hover { border-color: var(--tm-border-strong); }
      .tm-notif-select:focus { outline: 0; border-color: var(--tm-accent); box-shadow: var(--tm-shadow-focus); }

      /* Notification delete button */
      .tm-notif-delete {
        width: 30px; height: 30px;
        border: 1px solid transparent; background: transparent;
        border-radius: var(--tm-radius-sm);
        display: grid; place-items: center;
        color: var(--tm-text-faint); cursor: pointer;
        font-size: 16px; font-family: inherit;
        transition: all 0.1s;
      }
      .tm-notif-delete:hover {
        background: var(--tm-danger-soft); color: var(--tm-danger);
        border-color: var(--tm-danger-soft);
      }

      /* Power user info box */
      .tm-notif-info-box {
        margin-top: 16px; padding: 14px 16px;
        background: var(--tm-surface-1); border: 1px solid var(--tm-border);
        border-left: 3px solid var(--tm-accent, #4fc3f7);
        border-radius: var(--tm-radius-sm);
        font-size: 12.5px; color: var(--tm-text-muted); line-height: 1.55;
      }
      .tm-notif-info-box strong {
        color: var(--tm-text); display: block;
        margin-bottom: 4px; font-size: 13px;
      }

      /* ===== Mobile / narrow ===== */
      @media (max-width: 900px) {
        .tm-shell { grid-template-columns: 1fr; }
        .tm-sidebar { display: none; }
        .tm-menu-btn { display: inline-flex; }
        .tm-topbar { padding: 0 12px; }
        .tm-mobile-tabs {
          display: flex;
          overflow-x: auto;
          overflow-y: hidden;
          overscroll-behavior: contain;
          touch-action: pan-x;
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
