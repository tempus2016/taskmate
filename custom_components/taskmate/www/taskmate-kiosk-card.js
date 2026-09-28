/**
 * TaskMate Kiosk Card (#930)
 *
 * A full-screen view for a shared wall tablet. The family sees a picker of
 * faces; a child taps theirs, types their 4-digit PIN if they have one, and
 * gets only their own chores for today with big Done buttons, their points,
 * streak and progress towards the next reward. After a spell without a tap
 * (and straight after an "all done" celebration) it goes back to the picker.
 *
 * What it deliberately does NOT have: any parent action. No approve/reject,
 * no complete-on-behalf, no points adjustments, no reward claiming, no
 * settings — there is no option to turn them on.
 *
 * PINs are set by a parent in the admin panel and checked on the server
 * (taskmate/kiosk/verify_pin, rate-limited); the card never sees a PIN or its
 * hash, and only remembers which child is unlocked until it returns to the
 * picker. Completions go through the normal complete path, so the backend's
 * linked-child rule still decides who may act for whom: taskmate/kiosk/status
 * reports it per child and the card explains a refusal instead of offering
 * buttons that would fail.
 *
 * The card has ONE layout, so it consumes the design tokens directly: every
 * --tmd-* is written with the classic value as its fallback.
 *
 * Version: 1.0.0
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

const DEFAULT_HEADER = "#9b59b6";
const DEFAULT_TIMEOUT = 60;
const MIN_TIMEOUT = 15;
const MAX_TIMEOUT = 600;
// The "Still there?" countdown covers the last WARN_SECONDS of the timeout.
const WARN_SECONDS = 10;
// How long the all-done celebration stays up before the picker comes back.
const CELEBRATE_MS = 4000;
const PIN_LENGTH = 4;
// The same six-colour ring the child card uses for per-child tones.
const CHILD_FALLBACK = ["#ff7043", "#42a5f5", "#66bb6a", "#ab47bc", "#ffa726", "#26c6da"];

const clampTimeout = (v) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return DEFAULT_TIMEOUT;
  return Math.min(MAX_TIMEOUT, Math.max(MIN_TIMEOUT, Math.round(n)));
};

class TaskMateKioskCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _screen: { type: String },
      _kid: { type: String },
      _pin: { type: String },
      _pinError: { type: String },
      _status: { type: Object },
      _statusError: { type: String },
      _idle: { type: Number },
      _busy: { type: String },
      _celebrating: { type: Boolean },
      _fullscreen: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._screen = "picker";
    this._kid = null;
    this._pin = "";
    this._pinError = "";
    this._shake = false;
    this._lockedUntil = 0;
    this._status = null;
    this._statusError = "";
    this._idle = 0;
    this._busy = "";
    this._celebrating = false;
    this._armCelebrate = false;
    this._fullscreen = false;
    this._now = new Date();
    // Any touch or key press counts as activity and restarts the idle timer.
    this._onActivity = () => { this._idle = 0; };
    this._onFullscreen = () => {
      this._fullscreen = typeof document !== "undefined" && document.fullscreenElement === this;
    };
    this.addEventListener?.("pointerdown", this._onActivity);
    this.addEventListener?.("keydown", this._onActivity);
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    if (config.children !== undefined && !Array.isArray(config.children)) {
      throw new Error("children must be a list of { child_id, require_pin }");
    }
    this.config = { entity: "sensor.taskmate_overview", ...config };
  }

  getCardSize() { return 12; }

  static getConfigElement() {
    return document.createElement("taskmate-kiosk-card-editor");
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  connectedCallback() {
    super.connectedCallback?.();
    clearInterval(this._ticker);
    this._ticker = setInterval(() => this._tick(), 1000);
    if (typeof document !== "undefined") document.addEventListener?.("fullscreenchange", this._onFullscreen);
    this._scheduleStatus(0);
  }

  disconnectedCallback() {
    super.disconnectedCallback?.();
    clearInterval(this._ticker);
    this._ticker = null;
    clearTimeout(this._statusTimer);
    clearTimeout(this._celebrateTimer);
    clearTimeout(this._undoExpiryTimer);
    if (typeof document !== "undefined") document.removeEventListener?.("fullscreenchange", this._onFullscreen);
    // Leaving the dashboard locks the kiosk again.
    this._resetToPicker();
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass") && changedProps.size === 1) {
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
    }
    return true;
  }

  updated(changedProps) {
    super.updated?.(changedProps);
    // Only TaskMate-relevant hass changes get this far (shouldUpdate), so each
    // one may have changed who has what left to do: ask the server again.
    if (changedProps.has("hass")) this._scheduleStatus(300);
    if (this._screen !== "picker" && !(this._kid && this._entry(this._kid))) {
      this._toPicker();
      return;
    }
    this._scheduleUndoExpiry();
    this._maybeCelebrate();
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _attrs() {
    return (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
  }

  _timeout() { return clampTimeout(this.config.timeout ?? DEFAULT_TIMEOUT); }

  /**
   * Stamp the design on the host and settle the banner colour. Set inline on
   * the host: a shadow <style> loses to the :host default in static styles.
   */
  _applyDesign() {
    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    const configured = this.config.header_color;
    if (typeof configured === "string" && /^#[0-9a-fA-F]{3,8}$/.test(configured)) {
      this.style.setProperty("--km-header", _safeColor(configured, DEFAULT_HEADER));
    } else {
      this.style.removeProperty("--km-header");
    }
    return design;
  }

  /** The children on the picker, in the configured order. */
  _children() {
    const all = (this._attrs().children || []);
    const tone = (c) => {
      const i = Math.max(0, all.findIndex(k => String(k.id) === String(c.id)));
      return `var(--tmd-c${(i % 6) + 1}, ${CHILD_FALLBACK[i % 6]})`;
    };
    const configured = Array.isArray(this.config.children) ? this.config.children : null;
    if (!configured) {
      return all.filter(c => !c.is_guest).map(c => ({ child: c, requirePin: true, tone: tone(c) }));
    }
    const out = [];
    for (const entry of configured) {
      const id = String(entry && (entry.child_id ?? entry));
      const child = all.find(c => String(c.id) === id);
      if (child && !out.some(o => o.child.id === child.id)) {
        out.push({ child, requirePin: entry?.require_pin !== false, tone: tone(child) });
      }
    }
    return out;
  }

  _entry(id) { return this._children().find(e => String(e.child.id) === String(id)) || null; }

  _statusFor(id) { return this._status ? this._status[String(id)] || null : null; }

  _canAct(id) {
    const s = this._statusFor(id);
    return s ? s.can_act !== false : true;
  }

  _needsPin(entry) {
    const s = this._statusFor(entry.child.id);
    return entry.requirePin && !!(s && s.has_pin);
  }

  // ── Server status ────────────────────────────────────────────────────────

  _scheduleStatus(delay) {
    clearTimeout(this._statusTimer);
    this._statusTimer = setTimeout(() => this._refreshStatus(), delay);
  }

  async _refreshStatus() {
    if (!this.hass?.callWS) return;
    if (this._statusInflight) { this._statusAgain = true; return; }
    this._statusInflight = true;
    try {
      const res = await this.hass.callWS({ type: "taskmate/kiosk/status" });
      const map = {};
      for (const c of (res && res.children) || []) {
        map[String(c.id)] = { has_pin: !!c.has_pin, can_act: c.can_act !== false, due: new Set((c.due || []).map(String)) };
      }
      this._status = map;
      this._statusError = "";
    } catch (err) {
      this._statusError = String(err?.message || err);
    } finally {
      this._statusInflight = false;
      if (this._statusAgain) {
        this._statusAgain = false;
        this._scheduleStatus(0);
      } else {
        // A slow safety net: day rollovers and schedule changes that no
        // state push announces.
        this._scheduleStatus(60000);
      }
      this.requestUpdate();
    }
  }

  // ── Today's chores for one child ─────────────────────────────────────────

  /**
   * Rows for the child view. The server's `due` list (the same definition
   * the todo platform uses) says what is still to do; today's completions
   * say what is done or waiting. Before the first status reply, the
   * availability matrix stands in so the view isn't blank.
   *
   * Photo, timed and open-ended chores can't be finished here, so they carry
   * `phone: true`: they're listed in their own group and left out of the
   * done/total count, or a child with one due could never reach all done.
   */
  _rows(child) {
    const attrs = this._attrs();
    const id = String(child.id);
    const status = this._statusFor(id);
    const availability = attrs.chore_availability || {};
    const isDue = (chore) => {
      if (status) return status.due.has(String(chore.id));
      const assigned = Array.isArray(chore.assigned_to) ? chore.assigned_to.map(String) : [];
      return availability[chore.id]?.[id] === true && (!assigned.length || assigned.includes(id));
    };
    const latest = new Map();
    for (const c of attrs.todays_completions || []) {
      if (String(c.child_id) !== id || c.bonus_subtask_id) continue;
      const prev = latest.get(String(c.chore_id));
      if (!prev || new Date(c.completed_at || 0) > new Date(prev.completed_at || 0)) latest.set(String(c.chore_id), c);
    }
    const order = (child.chore_order || []).map(String);
    const chores = (attrs.chores || []).slice().sort((a, b) => {
      const ai = order.indexOf(String(a.id));
      const bi = order.indexOf(String(b.id));
      if (ai !== -1 && bi !== -1) return ai - bi;
      if (ai !== -1) return -1;
      if (bi !== -1) return 1;
      return 0;
    });
    const rows = [];
    for (const chore of chores) {
      const due = isDue(chore);
      const comp = latest.get(String(chore.id));
      const team = chore.team;
      const joined = team && Array.isArray(team.joined) ? team.joined.map(String) : [];
      if (!due && !comp) continue;
      const phone = !!(chore.require_photo || chore.open_ended || chore.task_type === "timed");
      let state;
      if (due && team && joined.includes(id)) state = "team";
      else if (due) state = phone ? "elsewhere" : "todo";
      else state = comp.approved ? "done" : "wait";
      rows.push({ chore, state, phone, completion: comp || null, team: team ? { size: Number(team.size) || 0, joined: joined.length } : null });
    }
    return rows;
  }

  /**
   * Counts only what can be ticked off on this tablet. A chore waiting for a
   * grown-up counts as done — the child has done their part, as on the child
   * card.
   */
  _progress(child) {
    const all = this._rows(child);
    const rows = all.filter(r => !r.phone);
    const phoneRows = all.filter(r => r.phone);
    const done = rows.filter(r => r.state === "done" || r.state === "wait").length;
    return { done, total: rows.length, rows, phoneRows };
  }

  _pointsFor(chore) { return chore.effective_points ?? chore.points ?? 0; }

  /** The cheapest reward this child can't afford yet — what they're saving for. */
  _nextReward(child) {
    const balance = Number(child.points) || 0;
    const id = String(child.id);
    let best = null;
    for (const r of this._attrs().rewards || []) {
      if (r.is_jackpot || r.pool_enabled || r.streak_freeze || r.is_available === false) continue;
      const assigned = Array.isArray(r.assigned_to) ? r.assigned_to.map(String) : [];
      if (assigned.length && !assigned.includes(id)) continue;
      const cost = Number(r.calculated_costs?.[id] ?? r.cost) || 0;
      if (cost <= balance) continue;
      if (!best || cost < best.cost) best = { reward: r, cost };
    }
    return best;
  }

  // ── Child undo (#918) ────────────────────────────────────────────────────
  // Exactly the child card's rule: the server marks a completion the child
  // may still take back (child_undo_pending / child_undo_until).

  _undoable(completion, now = Date.now()) {
    if (!completion || !(completion.completion_id || completion.id)) return null;
    if (completion.child_undo_pending === true) return completion;
    const until = Date.parse(completion.child_undo_until || "");
    return Number.isFinite(until) && until > now ? completion : null;
  }

  _scheduleUndoExpiry() {
    clearTimeout(this._undoExpiryTimer);
    this._undoExpiryTimer = null;
    if (this._screen !== "child" || !this._kid) return;
    const now = Date.now();
    const deadlines = (this._attrs().todays_completions || [])
      .filter(c => String(c.child_id) === String(this._kid))
      .map(c => Date.parse(c.child_undo_until || ""))
      .filter(t => Number.isFinite(t) && t > now);
    if (!deadlines.length) return;
    this._undoExpiryTimer = setTimeout(() => {
      this._undoExpiryTimer = null;
      this.requestUpdate();
    }, Math.min(Math.min(...deadlines) - now + 50, 2 ** 31 - 1));
  }

  // ── Actions ──────────────────────────────────────────────────────────────

  _notify(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message }, bubbles: true, composed: true,
    }));
  }

  _openKid(entry) {
    // Until the server has said who has a PIN, a tap can't know whether to
    // ask for one — so faces stay inert rather than risk skipping the pad.
    if (!this._status) return;
    this._idle = 0;
    this._pin = "";
    this._pinError = "";
    this._kid = String(entry.child.id);
    this._armCelebrate = false;
    this._celebrating = false;
    if (!this._canAct(entry.child.id)) this._screen = "blocked";
    else if (this._needsPin(entry)) this._screen = "pin";
    else this._screen = "child";
  }

  _resetToPicker() {
    clearTimeout(this._celebrateTimer);
    this._screen = "picker";
    this._kid = null;
    this._pin = "";
    this._pinError = "";
    this._idle = 0;
    this._celebrating = false;
    this._armCelebrate = false;
  }

  _toPicker() {
    this._resetToPicker();
    this.requestUpdate();
  }

  _lockSeconds() {
    return Math.max(0, Math.ceil((this._lockedUntil - Date.now()) / 1000));
  }

  _pressDigit(d) {
    if (this._pin.length >= PIN_LENGTH || this._busy || this._lockSeconds() > 0) return;
    this._pin += String(d);
    this._pinError = "";
    if (this._pin.length === PIN_LENGTH) this._submitPin();
  }

  _deleteDigit() {
    this._pin = this._pin.slice(0, -1);
    this._pinError = "";
  }

  async _submitPin() {
    const kid = this._kid;
    const pin = this._pin;
    this._busy = "pin";
    try {
      const res = await this.hass.callWS({ type: "taskmate/kiosk/verify_pin", child_id: kid, pin });
      if (this._kid !== kid || this._screen !== "pin") return;
      if (res && res.ok) {
        this._screen = "child";
        this._pin = "";
        this._idle = 0;
        return;
      }
      const locked = Number(res && res.locked_for) || 0;
      if (locked > 0) this._lockedUntil = Date.now() + locked * 1000;
      this._pinError = locked > 0 ? "" : this._t("kiosk.pin_wrong");
      this._shake = true;
      this._pin = "";
    } catch (err) {
      this._pin = "";
      this._pinError = String(err?.message || err);
    } finally {
      this._busy = "";
      this.requestUpdate();
    }
  }

  async _complete(child, chore) {
    if (this._busy) return;
    this._busy = String(chore.id);
    this._armCelebrate = true;
    try {
      // The per-chore button first, like the child card, so HA automations on
      // it fire; the service when the entity isn't registered yet. Both run
      // the backend's linked-child check against this tablet's user.
      const buttonEntityId = window.__taskmate_find_button
        && window.__taskmate_find_button(this.hass, child.id, "complete", chore.id);
      if (buttonEntityId) {
        await this.hass.callService("button", "press", { entity_id: buttonEntityId });
      } else {
        await this.hass.callService("taskmate", "complete_chore", { chore_id: chore.id, child_id: child.id });
      }
    } catch (err) {
      this._notify(String(err?.message || err));
    } finally {
      this._busy = "";
      this._scheduleStatus(0);
    }
  }

  async _undo(completion) {
    if (this._busy) return;
    this._busy = "undo";
    try {
      // The service takes the child from the stored completion itself.
      await this.hass.callService("taskmate", "undo_chore", {
        completion_id: completion.completion_id || completion.id,
      });
    } catch (err) {
      this._notify(String(err?.message || err));
    } finally {
      this._busy = "";
      this._scheduleStatus(0);
    }
  }

  /** Straight back to the picker once a child finishes their last chore here. */
  _maybeCelebrate() {
    if (!this._armCelebrate || this._celebrating || this._screen !== "child") return;
    const entry = this._entry(this._kid);
    if (!entry) return;
    const { done, total } = this._progress(entry.child);
    if (!total || done < total) return;
    this._armCelebrate = false;
    this._celebrating = true;
    clearTimeout(this._celebrateTimer);
    this._celebrateTimer = setTimeout(() => this._toPicker(), CELEBRATE_MS);
  }

  _tick() {
    const prevMinute = this._now.getMinutes();
    this._now = new Date();
    let dirty = this._now.getMinutes() !== prevMinute;
    if (this._screen === "pin" && this._lockedUntil) {
      if (this._lockSeconds() === 0) this._lockedUntil = 0;
      dirty = true;
    }
    if (this._screen !== "picker") {
      this._idle += 1;
      if (this._idle >= this._timeout()) {
        this._resetToPicker();
      }
      dirty = true;
    }
    if (dirty) this.requestUpdate();
  }

  _toggleFullscreen() {
    if (typeof document === "undefined") return;
    if (document.fullscreenElement) document.exitFullscreen?.();
    else this.requestFullscreen?.()?.catch?.(() => {});
  }

  // ── Render ───────────────────────────────────────────────────────────────

  _face(child, tone, size = "") {
    const avatar = child.avatar || "";
    // The default avatar is a generic silhouette, so a child who never picked
    // one gets their initial instead — easier to tell apart on a picker.
    const icon = avatar.startsWith("mdi:") && avatar !== "mdi:account-circle";
    return html`<div class="km-face ${size}" style="--kc:${tone}">
      ${icon ? html`<ha-icon icon="${avatar}"></ha-icon>` : html`<span>${(child.name || "?").slice(0, 1).toUpperCase()}</span>`}
    </div>`;
  }

  render() {
    if (!this.hass || !this.config) return html``;
    this._applyDesign();
    const attrs = this._attrs();
    const title = this.config.title || "TaskMate";
    const time = this._now.toLocaleTimeString(this.hass.locale?.language || undefined, { hour: "2-digit", minute: "2-digit" });
    const date = this._now.toLocaleDateString(this.hass.locale?.language || undefined, { weekday: "long", day: "numeric", month: "long" });
    const canFullscreen = typeof document !== "undefined" && document.fullscreenEnabled !== false;

    let body;
    // A child removed from the config mid-session falls back to the picker
    // (updated() then resets the state to match).
    const entry = this._kid ? this._entry(this._kid) : null;
    if (this._screen === "pin" && entry) body = this._renderPin(entry);
    else if (this._screen === "child" && entry) body = this._renderChild(entry, attrs);
    else if (this._screen === "blocked" && entry) body = this._renderBlocked(entry);
    else body = this._renderPicker(attrs);

    return html`
      <ha-card class="km">
        <div class="km-top">
          <ha-icon class="km-top-icon" icon="mdi:tablet-dashboard"></ha-icon>
          <span class="km-title">${title}</span>
          <span class="km-clock"><b>${time}</b>${date}</span>
          ${canFullscreen ? html`
            <button class="km-icon-btn" title="${this._fullscreen ? this._t("kiosk.exit_fullscreen") : this._t("kiosk.fullscreen")}"
                    aria-label="${this._fullscreen ? this._t("kiosk.exit_fullscreen") : this._t("kiosk.fullscreen")}"
                    @click=${() => this._toggleFullscreen()}>
              <ha-icon icon="${this._fullscreen ? "mdi:fullscreen-exit" : "mdi:fullscreen"}"></ha-icon>
            </button>` : ""}
        </div>
        <div class="km-main">${body}</div>
      </ha-card>
    `;
  }

  _renderPicker(attrs) {
    const entries = this._children();
    const icon = attrs.points_icon || "mdi:star";
    const showProgress = this.config.show_picker_progress !== false;
    const showPoints = this.config.show_points !== false;
    if (!entries.length) {
      return html`<div class="km-empty"><ha-icon icon="mdi:account-group"></ha-icon><p>${this._t("kiosk.no_children")}</p></div>`;
    }
    return html`
      <div class="km-picker">
        <h1>${this._t("kiosk.who")}</h1>
        <div class="km-sub">${this._t("kiosk.tap_face")}</div>
        <div class="km-kids">
          ${entries.map(entry => {
            const { child, tone } = entry;
            const blocked = !this._canAct(child.id);
            const { done, total, phoneRows } = this._progress(child);
            const all = total > 0 && done === total;
            const none = phoneRows.length ? this._t("kiosk.nothing_here") : this._t("kiosk.nothing_today");
            return html`
              <button class="km-kid ${all ? "all-done" : ""} ${blocked ? "blocked" : ""}" style="--kc:${tone}"
                      data-kid="${child.id}" ?disabled=${!this._status} @click=${() => this._openKid(entry)}>
                <div class="km-face-wrap">
                  ${this._face(child, tone)}
                  ${this._needsPin(entry) ? html`<span class="km-lock"><ha-icon icon="mdi:lock"></ha-icon></span>` : ""}
                </div>
                <div class="km-name">${child.name}</div>
                ${blocked
                  ? html`<div class="km-kid-note">${this._t("kiosk.ask_grownup")}</div>`
                  : showProgress ? html`
                    <div class="km-prog">
                      <div class="km-bar"><i style="width:${total ? Math.round((done / total) * 100) : 0}%"></i></div>
                      <small>${!total ? none : all ? this._t("kiosk.all_done_short") : this._t("kiosk.progress", { done, total })}</small>
                    </div>` : ""}
                ${showPoints ? html`<div class="km-pts"><ha-icon icon="${icon}"></ha-icon> ${child.points ?? 0}</div>` : ""}
              </button>`;
          })}
        </div>
        ${this._statusError ? html`<div class="km-error">${this._statusError}</div>` : ""}
      </div>
    `;
  }

  _renderPin(entry) {
    const { child, tone } = entry;
    const locked = this._lockSeconds();
    const shake = this._shake;
    this._shake = false;
    const disabled = locked > 0 || this._busy === "pin";
    return html`
      <div class="km-pin" style="--kc:${tone}">
        <button class="km-ghost km-pin-back" @click=${() => this._toPicker()}>
          <ha-icon class="tm-rtl-flip" icon="mdi:chevron-left"></ha-icon> ${this._t("kiosk.back")}
        </button>
        <div class="km-pin-left">
          ${this._face(child, tone, "big")}
          <h2>${this._t("kiosk.hi", { name: child.name })}</h2>
          <p>${this._t("kiosk.enter_pin")}</p>
          <div class="km-dots ${shake ? "shake" : ""}">
            ${Array.from({ length: PIN_LENGTH }, (_, i) => html`<i class="${i < this._pin.length ? "on" : ""}"></i>`)}
          </div>
          <div class="km-pin-err" role="alert">${locked > 0 ? this._t("kiosk.pin_locked", { seconds: locked }) : this._pinError}</div>
        </div>
        <div class="km-pad">
          ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map(n => html`
            <button class="km-key" ?disabled=${disabled} @click=${() => this._pressDigit(n)}>${n}</button>`)}
          <button class="km-key fn" @click=${() => this._toPicker()}>${this._t("kiosk.cancel")}</button>
          <button class="km-key" ?disabled=${disabled} @click=${() => this._pressDigit(0)}>0</button>
          <button class="km-key fn" aria-label="${this._t("kiosk.delete_digit")}" ?disabled=${disabled}
                  @click=${() => this._deleteDigit()}><ha-icon class="tm-rtl-flip" icon="mdi:backspace-outline"></ha-icon></button>
        </div>
      </div>
    `;
  }

  _renderBlocked(entry) {
    const { child, tone } = entry;
    return html`
      <div class="km-blocked" style="--kc:${tone}">
        ${this._face(child, tone, "big")}
        <h2>${this._t("kiosk.blocked_title", { name: child.name })}</h2>
        <p>${this._t("kiosk.blocked_body", { name: child.name })}</p>
        <button class="km-primary" @click=${() => this._toPicker()}>
          <ha-icon class="tm-rtl-flip" icon="mdi:chevron-left"></ha-icon> ${this._t("kiosk.back")}
        </button>
      </div>
    `;
  }

  _renderChild(entry, attrs) {
    const { child, tone } = entry;
    const icon = attrs.points_icon || "mdi:star";
    const { done, total, rows, phoneRows } = this._progress(child);
    const all = total > 0 && done === total;
    const timeout = this._timeout();
    const left = Math.max(0, timeout - this._idle);
    const showPoints = this.config.show_points !== false;
    const showStreak = this.config.show_streak !== false;
    const showReward = this.config.show_reward_progress !== false;
    const warn = this.config.warn_before_return !== false && left <= WARN_SECONDS && left > 0 && !this._celebrating;
    const earnedToday = (attrs.todays_completions || [])
      .filter(c => String(c.child_id) === String(child.id))
      .reduce((sum, c) => sum + (Number(c.points) || 0), 0);
    const next = showReward ? this._nextReward(child) : null;
    const levelPct = child.level_target ? Math.min(100, Math.round(((child.level_progress || 0) / child.level_target) * 100)) : 0;

    return html`
      <div class="km-child" style="--kc:${tone}">
        <div class="km-head">
          ${this._face(child, tone, "head")}
          <div class="km-grow">
            <div class="km-head-name">${child.name}</div>
            ${showPoints && child.level ? html`
              <div class="km-level">
                <span class="km-level-badge">${this._t("child.level_label", { level: child.level })}</span>
                <span class="km-level-track"><i style="width:${levelPct}%"></i></span>
              </div>` : ""}
          </div>
          ${showPoints ? html`<div class="km-pts-pill"><ha-icon icon="${icon}"></ha-icon> ${child.points ?? 0}</div>` : ""}
          <button class="km-switch" @click=${() => this._toPicker()}>
            <span>${this._t("kiosk.switch", { name: child.name })}</span>
            <span class="km-ring" style="--p:${left / timeout}"><span>${left}</span></span>
          </button>
        </div>

        <div class="km-body">
          <div class="km-list">
            <h3><ha-icon icon="mdi:calendar-check"></ha-icon> ${this._t("kiosk.todays_chores")}</h3>
            ${all ? html`<div class="km-celebrate"><ha-icon icon="mdi:trophy"></ha-icon> ${this._t("kiosk.all_done", { name: child.name })}</div>` : ""}
            ${!total ? html`<div class="km-none">${phoneRows.length ? this._t("kiosk.nothing_here") : this._t("kiosk.nothing_today")}</div>` : ""}
            ${rows.map(row => this._renderRow(child, row, icon))}
            ${phoneRows.length ? html`
              <div class="km-phone-group">
                <h3><ha-icon icon="mdi:cellphone"></ha-icon> ${this._t("kiosk.phone_group")}</h3>
                ${phoneRows.map(row => this._renderRow(child, row, icon))}
              </div>` : ""}
          </div>
          <div class="km-side">
            <div class="km-tile km-center">
              <h3>${this._t("kiosk.today")}</h3>
              <div class="km-big-ring" style="--p:${total ? done / total : 0}">
                <div><b>${done}/${total}</b><small>${this._t("kiosk.chores_done")}</small></div>
              </div>
            </div>
            ${showPoints || showStreak ? html`
              <div class="km-stat2">
                ${showPoints ? html`<div class="km-tile"><b class="gold"><ha-icon icon="${icon}"></ha-icon> +${earnedToday}</b><small>${this._t("kiosk.earned_today")}</small></div>` : ""}
                ${showStreak ? html`<div class="km-tile"><b class="warm"><ha-icon icon="mdi:fire"></ha-icon> ${child.current_streak || 0}</b><small>${this._t("kiosk.day_streak")}</small></div>` : ""}
              </div>` : ""}
            ${next ? html`
              <div class="km-tile">
                <div class="km-reward-row">
                  <ha-icon icon="${next.reward.icon || "mdi:gift"}"></ha-icon>
                  <b class="km-grow">${next.reward.name}</b>
                  <span class="km-dim">${child.points ?? 0} / ${next.cost}</span>
                </div>
                <div class="km-bar"><i style="width:${Math.min(100, Math.round(((Number(child.points) || 0) / next.cost) * 100))}%"></i></div>
                <div class="km-dim km-small">${this._t("kiosk.to_go", { points: next.cost - (Number(child.points) || 0) })}</div>
              </div>` : ""}
          </div>
        </div>

        ${warn ? html`
          <div class="km-idle">
            <div class="km-idle-n" style="--p:${left / WARN_SECONDS}"><span>${left}</span></div>
            <h2>${this._t("kiosk.still_there", { name: child.name })}</h2>
            <p>${this._t("kiosk.going_back")}</p>
            <button class="km-primary" @click=${() => { this._idle = 0; this.requestUpdate(); }}>
              <ha-icon icon="mdi:hand-wave"></ha-icon> ${this._t("kiosk.still_here")}
            </button>
          </div>` : ""}
        ${this._celebrating ? html`
          <div class="km-idle km-party">
            <div class="km-cheer">🎉</div>
            <h2>${this._t("kiosk.all_done", { name: child.name })}</h2>
          </div>` : ""}
      </div>
    `;
  }

  _renderRow(child, row, icon) {
    const { chore, state, completion, team } = row;
    const visual = window.__taskmate_chore_visual ? window.__taskmate_chore_visual(chore) : { kind: "none" };
    const undoable = (state === "done" || state === "wait") ? this._undoable(completion) : null;
    const needsCheck = state === "todo" && chore.requires_approval !== false;
    let action;
    if (state === "todo") {
      action = html`<button class="km-done" ?disabled=${!!this._busy} @click=${() => this._complete(child, chore)}>
        <ha-icon icon="mdi:check-bold"></ha-icon> ${this._t("child.done")}</button>`;
    } else if (state === "done") {
      action = html`<div class="km-done is-done"><ha-icon icon="mdi:check-bold"></ha-icon> ${this._t("child.done")}</div>`;
    } else if (state === "wait") {
      action = html`<div class="km-done is-wait"><ha-icon icon="mdi:timer-sand"></ha-icon><span>${this._t("kiosk.waiting")}</span></div>`;
    } else if (state === "team") {
      action = html`<div class="km-done is-wait"><ha-icon icon="mdi:account-group"></ha-icon><span>${this._t("kiosk.team_waiting", { joined: team.joined, size: team.size })}</span></div>`;
    } else {
      action = html`<div class="km-done is-elsewhere"><ha-icon icon="mdi:cellphone"></ha-icon><span>${this._t("kiosk.do_on_phone")}</span></div>`;
    }
    return html`
      <div class="km-row ${state}">
        <div class="km-row-icon">
          ${visual.kind === "image"
            ? html`<img src="${visual.url}" alt="" loading="lazy">`
            : html`<ha-icon icon="${visual.kind === "icon" ? visual.icon : "mdi:checkbox-marked-circle-outline"}"></ha-icon>`}
        </div>
        <div class="km-row-body">
          <div class="km-row-name">${chore.name}</div>
          <div class="km-row-meta">
            <span class="km-row-pts"><ha-icon icon="${icon}"></ha-icon> ${this._pointsFor(chore)}</span>
            ${needsCheck ? html`<span class="km-tag">${this._t("kiosk.needs_check")}</span>` : ""}
            ${undoable ? html`<button class="km-undo" ?disabled=${!!this._busy}
                                      aria-label="${this._t("child.undo_named", { name: chore.name })}"
                                      @click=${() => this._undo(undoable)}>
                                <ha-icon class="tm-rtl-flip" icon="mdi:undo-variant"></ha-icon> ${this._t("kiosk.undo")}</button>` : ""}
          </div>
        </div>
        ${action}
      </div>
    `;
  }

  static get styles() {
    // Layout classes carry a km- prefix: the shared design kit defines its own
    // .btn and .bar, and its :host([data-tm-design=...]) rules would outrank
    // bare class names here.
    const base = css`
      /* #9b59b6 is DEFAULT_HEADER (a css tag cannot interpolate a plain string). */
      :host { display: block; --km-header: var(--tmd-accent, #9b59b6); }
      :host(:fullscreen) { background: var(--tmd-bg, var(--primary-background-color, #111)); }
      :host(:fullscreen) ha-card { height: 100vh; min-height: 100vh; border-radius: 0; }
      :host(:fullscreen) .km-main { overflow: hidden; }
      ha-card.km {
        container-type: inline-size;
        container-name: km;
        position: relative;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        min-height: var(--km-min-height, 620px);
        font-family: var(--tmd-font-body, inherit);
        background: var(--tmd-bg, var(--ha-card-background, var(--card-background-color, #fff)));
        color: var(--tmd-text, var(--primary-text-color));
        border-radius: var(--tmd-radius, var(--ha-card-border-radius, 12px));
      }
      button { font-family: inherit; }

      /* Top banner — full colour in every design. */
      .km-top {
        display: flex; align-items: center; gap: 12px;
        padding: 12px 20px;
        background: var(--km-header);
        color: var(--tmd-hd-text, #fff);
      }
      .km-top-icon { --mdc-icon-size: 24px; opacity: 0.95; }
      .km-title {
        font-family: var(--tmd-font-display, inherit);
        font-weight: 700; font-size: 1.2rem; flex: 1; min-width: 0;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .km-clock { font-variant-numeric: tabular-nums; opacity: 0.9; white-space: nowrap; }
      .km-clock b { font-size: 1.15rem; margin-inline-end: 8px; }
      .km-icon-btn {
        background: rgba(255, 255, 255, 0.18); border: 0; color: inherit;
        width: 40px; height: 40px; border-radius: 50%;
        display: grid; place-items: center; cursor: pointer;
      }
      .km-main { flex: 1; position: relative; min-height: 0; display: flex; flex-direction: column; }

      /* Faces */
      .km-face {
        width: 128px; height: 128px; border-radius: 50%;
        background: var(--kc); color: #fff;
        display: grid; place-items: center;
        font-size: 60px; font-weight: 800;
        font-family: var(--tmd-font-display, inherit);
        box-shadow: 0 0 0 6px color-mix(in srgb, var(--kc) 25%, transparent);
      }
      .km-face ha-icon { --mdc-icon-size: 72px; }
      .km-face.big { width: 160px; height: 160px; font-size: 76px; }
      .km-face.big ha-icon { --mdc-icon-size: 90px; }
      .km-face.head {
        width: 64px; height: 64px; font-size: 30px;
        background: rgba(255, 255, 255, 0.2);
        border: 3px solid rgba(255, 255, 255, 0.4);
        box-shadow: none;
      }
      .km-face.head ha-icon { --mdc-icon-size: 36px; }

      /* Picker */
      .km-picker {
        flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: 12px; padding: 28px 20px;
      }
      .km-picker h1 {
        margin: 0; font-size: 2.4rem; font-weight: 800;
        font-family: var(--tmd-font-display, inherit);
      }
      .km-sub { color: var(--tmd-dim, var(--secondary-text-color)); font-size: 1.1rem; margin-bottom: 16px; }
      .km-kids { display: flex; gap: 28px; flex-wrap: wrap; justify-content: center; }
      .km-kid {
        width: 230px;
        background: var(--tmd-surface, var(--secondary-background-color, rgba(127, 127, 127, 0.08)));
        color: inherit;
        border: 3px solid var(--tmd-border, transparent);
        border-radius: calc(var(--tmd-radius, 12px) + 12px);
        padding: 24px 18px 20px;
        display: flex; flex-direction: column; align-items: center; gap: 12px;
        cursor: pointer;
        box-shadow: var(--tmd-shadow, 0 6px 24px rgba(0, 0, 0, 0.18));
        transition: transform 0.12s ease, border-color 0.12s ease;
      }
      .km-kid:hover, .km-kid:focus-visible { transform: translateY(-3px); border-color: var(--kc); outline: none; }
      .km-kid.blocked { opacity: 0.6; }
      .km-kid:disabled { cursor: progress; }
      .km-face-wrap { position: relative; }
      .km-lock {
        position: absolute; inset-inline-end: 0; bottom: 4px;
        width: 40px; height: 40px; border-radius: 50%;
        display: grid; place-items: center;
        background: var(--tmd-surface-2, var(--card-background-color, #222));
        color: var(--tmd-text, var(--primary-text-color));
        border: 3px solid var(--tmd-surface, var(--card-background-color, #fff));
      }
      .km-lock ha-icon { --mdc-icon-size: 20px; }
      .km-name { font-size: 1.6rem; font-weight: 800; font-family: var(--tmd-font-display, inherit); }
      .km-kid-note { color: var(--tmd-dim, var(--secondary-text-color)); font-weight: 600; }
      .km-prog { width: 100%; display: flex; flex-direction: column; gap: 6px; align-items: center; }
      .km-prog small { color: var(--tmd-dim, var(--secondary-text-color)); font-size: 0.95rem; }
      .km-kid.all-done .km-prog small { color: var(--tmd-good, var(--success-color, #2e7d32)); font-weight: 700; }
      .km-bar {
        width: 100%; height: 12px; border-radius: 99px; overflow: hidden;
        background: var(--tmd-surface-2, var(--divider-color, rgba(127, 127, 127, 0.25)));
        border: 1px solid var(--tmd-border, transparent);
        box-sizing: border-box;
      }
      .km-bar > i { display: block; height: 100%; border-radius: 99px; background: var(--kc, var(--km-header)); }
      .km-kid.all-done .km-bar > i { background: var(--tmd-good, var(--success-color, #2ecc71)); }
      .km-pts {
        display: flex; align-items: center; gap: 6px;
        font-size: 1.25rem; font-weight: 800;
        color: var(--tmd-gold, #f39c12);
      }
      .km-error { color: var(--tmd-bad, var(--error-color, #c62828)); margin-top: 12px; }

      /* PIN */
      .km-pin {
        flex: 1; position: relative;
        display: grid; grid-template-columns: 1fr 1fr; align-items: center;
        padding: 64px 24px 24px;
      }
      .km-pin-back { position: absolute; inset-inline-start: 18px; top: 16px; }
      .km-pin-left { display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; }
      .km-pin-left h2 { margin: 6px 0 0; font-size: 2rem; font-family: var(--tmd-font-display, inherit); }
      .km-pin-left p { margin: 0; color: var(--tmd-dim, var(--secondary-text-color)); font-size: 1.1rem; }
      .km-dots { display: flex; gap: 16px; margin-top: 6px; }
      .km-dots i {
        width: 22px; height: 22px; border-radius: 50%;
        border: 3px solid var(--tmd-dim, #8a939d); display: block; box-sizing: border-box;
      }
      .km-dots i.on { background: var(--kc); border-color: var(--kc); }
      .km-dots.shake { animation: km-shake 0.4s; }
      @keyframes km-shake { 20%, 60% { transform: translateX(-12px); } 40%, 80% { transform: translateX(12px); } }
      .km-pin-err { color: var(--tmd-bad, var(--error-color, #c62828)); font-weight: 700; min-height: 24px; }
      .km-pad { display: grid; grid-template-columns: repeat(3, 96px); gap: 16px; justify-self: center; }
      .km-key {
        width: 96px; height: 96px; border-radius: 50%; border: 1px solid var(--tmd-border, transparent);
        background: var(--tmd-surface-2, var(--secondary-background-color, rgba(127, 127, 127, 0.15)));
        color: var(--tmd-text, var(--primary-text-color));
        font-size: 2.2rem; font-weight: 600; cursor: pointer;
        display: grid; place-items: center;
      }
      .km-key:active { filter: brightness(0.9); }
      .km-key:disabled { opacity: 0.4; cursor: default; }
      .km-key.fn { background: transparent; border: 0; font-size: 1rem; color: var(--tmd-dim, var(--secondary-text-color)); }
      .km-key.fn ha-icon { --mdc-icon-size: 30px; }

      .km-ghost {
        display: inline-flex; align-items: center; gap: 4px;
        background: transparent; color: var(--tmd-text, var(--primary-text-color));
        border: 1px solid var(--tmd-border, var(--divider-color, rgba(127, 127, 127, 0.4)));
        border-radius: 10px; padding: 8px 14px; font-size: 1rem; cursor: pointer;
      }
      .km-primary {
        display: inline-flex; align-items: center; gap: 8px;
        background: var(--kc, var(--km-header)); color: #fff; border: 0;
        border-radius: 40px; padding: 16px 30px; font-size: 1.2rem; font-weight: 700; cursor: pointer;
      }

      /* Blocked */
      .km-blocked {
        flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
        gap: 12px; padding: 32px; text-align: center;
      }
      .km-blocked h2 { margin: 8px 0 0; font-size: 1.8rem; font-family: var(--tmd-font-display, inherit); }
      .km-blocked p { margin: 0 0 12px; max-width: 560px; color: var(--tmd-dim, var(--secondary-text-color)); font-size: 1.05rem; line-height: 1.5; }

      /* Child view */
      .km-child { flex: 1; position: relative; display: flex; flex-direction: column; min-height: 0; }
      .km-head {
        display: flex; align-items: center; gap: 16px;
        padding: 16px 22px; background: var(--kc); color: #fff;
      }
      .km-grow { flex: 1; min-width: 0; }
      .km-head-name { font-size: 1.8rem; font-weight: 800; line-height: 1.1; font-family: var(--tmd-font-display, inherit); }
      .km-level { display: flex; align-items: center; gap: 8px; margin-top: 6px; }
      .km-level-badge { font-size: 0.8rem; font-weight: 800; background: rgba(255, 255, 255, 0.25); padding: 2px 10px; border-radius: 99px; }
      .km-level-track { width: 120px; height: 6px; border-radius: 99px; background: rgba(255, 255, 255, 0.25); overflow: hidden; }
      .km-level-track i { display: block; height: 100%; background: #fff; }
      .km-pts-pill {
        display: flex; align-items: center; gap: 6px;
        background: rgba(255, 255, 255, 0.18); border: 1px solid rgba(255, 255, 255, 0.3);
        padding: 8px 16px; border-radius: 30px; font-weight: 800; font-size: 1.4rem; white-space: nowrap;
      }
      .km-switch {
        display: flex; align-items: center; gap: 10px;
        background: rgba(0, 0, 0, 0.18); color: #fff;
        border: 2px solid rgba(255, 255, 255, 0.4); border-radius: 40px;
        padding-block: 6px; padding-inline: 16px 8px; font-size: 1rem; font-weight: 700; cursor: pointer;
      }
      .km-ring {
        width: 40px; height: 40px; border-radius: 50%;
        display: grid; place-items: center; font-size: 0.8rem; font-weight: 800; font-variant-numeric: tabular-nums;
        background: conic-gradient(#fff calc(var(--p) * 360deg), rgba(255, 255, 255, 0.25) 0);
      }
      .km-ring span {
        width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center;
        background: color-mix(in srgb, var(--kc) 80%, #000);
      }
      .km-body {
        flex: 1; display: grid; grid-template-columns: 1fr 320px; gap: 20px;
        padding: 16px 22px 22px; min-height: 0;
      }
      /* Scrolls inside the card once its height is fixed (full screen). */
      .km-list { display: flex; flex-direction: column; gap: 10px; min-width: 0; min-height: 0; overflow-y: auto; }
      .km-list h3, .km-side h3 {
        margin: 0 0 2px; font-size: 1.2rem; font-weight: 700; color: var(--kc);
        display: flex; align-items: center; gap: 8px; font-family: var(--tmd-font-display, inherit);
      }
      .km-phone-group { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
      .km-phone-group h3 { color: var(--tmd-dim, var(--secondary-text-color)); }
      .km-none { color: var(--tmd-dim, var(--secondary-text-color)); padding: 20px 4px; font-size: 1.1rem; }
      .km-celebrate {
        display: flex; align-items: center; gap: 12px;
        background: var(--tmd-good, #27ae60); color: #fff;
        border-radius: var(--tmd-radius, 16px); padding: 14px 18px; font-size: 1.1rem; font-weight: 700;
      }
      .km-celebrate ha-icon { --mdc-icon-size: 30px; }
      .km-row {
        display: flex; align-items: center; gap: 14px;
        padding-block: 10px; padding-inline: 14px 12px; min-height: 72px;
        background: var(--tmd-surface, var(--card-background-color, #fff));
        border: 2px solid color-mix(in srgb, var(--kc) 45%, var(--tmd-border, transparent));
        border-radius: var(--tmd-radius, 16px);
        box-shadow: var(--tmd-shadow, none);
      }
      .km-row.done { opacity: 0.72; }
      .km-row.done .km-row-name { text-decoration: line-through; text-decoration-thickness: 2px; }
      .km-row.elsewhere { opacity: 0.55; }
      .km-row-icon {
        width: 50px; height: 50px; min-width: 50px; border-radius: 50%;
        display: grid; place-items: center; overflow: hidden;
        background: color-mix(in srgb, var(--kc) 18%, transparent); color: var(--kc);
      }
      .km-row-icon ha-icon { --mdc-icon-size: 28px; }
      .km-row-icon img { width: 100%; height: 100%; object-fit: cover; }
      .km-row-body { flex: 1; min-width: 0; }
      .km-row-name {
        font-size: 1.3rem; font-weight: 700; line-height: 1.2;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        font-family: var(--tmd-font-display, inherit);
      }
      .km-row-meta { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 4px; }
      .km-row-pts { display: inline-flex; align-items: center; gap: 4px; color: var(--tmd-gold, #e67e22); font-weight: 700; }
      .km-row-pts ha-icon { --mdc-icon-size: 16px; }
      .km-tag {
        font-size: 0.75rem; font-weight: 700; padding: 2px 9px; border-radius: 99px;
        background: color-mix(in srgb, var(--tmd-warn, #f39c12) 18%, transparent);
        color: var(--tmd-text, var(--primary-text-color));
      }
      .km-undo {
        display: inline-flex; align-items: center; gap: 4px;
        background: transparent; color: var(--tmd-text, var(--primary-text-color));
        border: 2px solid var(--kc); border-radius: 99px;
        padding: 3px 12px; font-size: 0.85rem; font-weight: 700; cursor: pointer; min-height: 32px;
      }
      .km-undo ha-icon { --mdc-icon-size: 16px; }
      .km-done {
        min-width: 150px; height: 56px; border-radius: 18px; border: 0; box-sizing: border-box;
        font-size: 1.25rem; font-weight: 800; color: #fff;
        background: var(--tmd-good, #27ae60);
        display: flex; align-items: center; justify-content: center; gap: 8px; cursor: pointer;
        font-family: var(--tmd-font-display, inherit);
      }
      /* Dark ink on the designed styles' "good" colour, as the shared kit does. */
      :host([data-tm-design]:not([data-tm-design="classic"]):not([data-tm-design="graphite"])) button.km-done { color: #06301f; }
      /* Graphite keeps colour for meaning only: its primary action is ink. */
      :host([data-tm-design="graphite"]) button.km-done { background: var(--tmd-text); color: var(--tmd-surface); }
      .km-done:disabled { opacity: 0.55; cursor: default; }
      .km-done.is-done {
        background: transparent; color: var(--tmd-good, #27ae60);
        border: 3px solid var(--tmd-good, #27ae60); cursor: default;
      }
      .km-done.is-wait, .km-done.is-elsewhere {
        background: transparent; cursor: default;
        font-size: 0.9rem; line-height: 1.15; text-align: start; padding: 0 12px; min-width: 180px; max-width: 220px;
        color: var(--tmd-text, var(--primary-text-color));
      }
      .km-done.is-wait { border: 3px dashed var(--tmd-warn, #f39c12); }
      .km-done.is-elsewhere { border: 3px dashed var(--tmd-dim, #8a939d); }
      .km-side { display: flex; flex-direction: column; gap: 14px; }
      .km-tile {
        background: var(--tmd-surface, var(--card-background-color, #fff));
        border: 1px solid var(--tmd-border, var(--divider-color, transparent));
        border-radius: var(--tmd-radius, 18px); padding: 16px;
        box-shadow: var(--tmd-shadow, none);
      }
      .km-center { text-align: center; }
      .km-center h3 { justify-content: center; }
      .km-big-ring {
        width: 150px; height: 150px; border-radius: 50%; margin: 6px auto 2px;
        display: grid; place-items: center;
        background: conic-gradient(var(--tmd-good, #2ecc71) calc(var(--p) * 360deg), var(--tmd-surface-2, rgba(127, 127, 127, 0.25)) 0);
      }
      .km-big-ring > div {
        width: 120px; height: 120px; border-radius: 50%;
        background: var(--tmd-surface, var(--card-background-color, #fff));
        display: grid; place-content: center; text-align: center;
      }
      .km-big-ring b { font-size: 2.2rem; font-weight: 800; line-height: 1; }
      .km-big-ring small { display: block; color: var(--tmd-dim, var(--secondary-text-color)); }
      .km-stat2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
      .km-stat2 .km-tile { text-align: center; padding: 12px; }
      .km-stat2 b { display: flex; align-items: center; justify-content: center; gap: 5px; font-size: 1.5rem; font-weight: 800; }
      .km-stat2 b.gold { color: var(--tmd-gold, #f39c12); }
      .km-stat2 b.warm { color: var(--tmd-bad, #e67e22); }
      .km-stat2 small { color: var(--tmd-dim, var(--secondary-text-color)); }
      .km-reward-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
      .km-reward-row ha-icon { color: var(--tmd-gold, #e67e22); }
      .km-dim { color: var(--tmd-dim, var(--secondary-text-color)); }
      .km-small { font-size: 0.85rem; margin-top: 8px; }

      /* Idle countdown + celebration overlays */
      .km-idle {
        position: absolute; inset: 0; z-index: 3;
        display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;
        /* Frosted in the card's own background, so text stays readable in
           light and dark themes alike. */
        background: color-mix(in srgb, var(--tmd-bg, var(--ha-card-background, var(--card-background-color, #fff))) 88%, transparent);
        backdrop-filter: blur(3px); text-align: center; padding: 20px;
      }
      .km-idle h2 { margin: 0; font-size: 2rem; font-family: var(--tmd-font-display, inherit); }
      .km-idle p { margin: 0; color: var(--tmd-dim, var(--secondary-text-color)); font-size: 1.1rem; }
      .km-idle-n {
        width: 170px; height: 170px; border-radius: 50%;
        display: grid; place-items: center; font-size: 72px; font-weight: 800;
        background: conic-gradient(var(--kc) calc(var(--p) * 360deg), var(--tmd-surface-2, rgba(127, 127, 127, 0.3)) 0);
      }
      .km-idle-n span {
        width: 140px; height: 140px; border-radius: 50%; display: grid; place-items: center;
        background: var(--tmd-surface, var(--card-background-color, #15181c));
      }
      .km-cheer { font-size: 96px; line-height: 1; }

      .km-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px; text-align: center; color: var(--tmd-dim, var(--secondary-text-color)); }
      .km-empty ha-icon { --mdc-icon-size: 56px; opacity: 0.5; }

      @container km (max-width: 760px) {
        .km-body { grid-template-columns: 1fr; }
        .km-pin { grid-template-columns: 1fr; gap: 20px; }
        .km-pad { grid-template-columns: repeat(3, 76px); gap: 12px; }
        .km-key { width: 76px; height: 76px; font-size: 1.8rem; }
        .km-kid { width: 180px; }
        .km-face { width: 100px; height: 100px; font-size: 48px; }
        .km-face.big { width: 120px; height: 120px; }
        .km-clock { display: none; }
        .km-head { flex-wrap: wrap; }
        .km-switch span:first-child { display: none; }
      }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }
}

class TaskMateKioskCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object }, _pins: { type: Object } };
  }

  setConfig(config) { this.config = { ...config }; }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  updated(changedProps) {
    super.updated?.(changedProps);
    if (changedProps.has("hass") && this.hass && !this._pinsRequested) {
      this._pinsRequested = true;
      this.hass.callWS({ type: "taskmate/kiosk/status" })
        .then(res => {
          const pins = {};
          for (const c of (res && res.children) || []) pins[String(c.id)] = !!c.has_pin;
          this._pins = pins;
        })
        .catch(() => { this._pins = {}; });
    }
  }

  _schema() {
    return [
      { name: "entity", selector: { entity: { domain: "sensor" } } },
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
      { name: "timeout", selector: { number: { min: MIN_TIMEOUT, max: MAX_TIMEOUT, step: 5, mode: "box", unit_of_measurement: "s" } } },
      { name: "warn_before_return", selector: { boolean: {} } },
      { name: "show_points", selector: { boolean: {} } },
      { name: "show_streak", selector: { boolean: {} } },
      { name: "show_reward_progress", selector: { boolean: {} } },
      { name: "show_picker_progress", selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => ({
    entity: this._t("kiosk.editor.entity"),
    title: this._t("kiosk.editor.title"),
    card_design: this._t("common.design.field_label"),
    timeout: this._t("kiosk.editor.timeout"),
    warn_before_return: this._t("kiosk.editor.warn_before_return"),
    show_points: this._t("kiosk.editor.show_points"),
    show_streak: this._t("kiosk.editor.show_streak"),
    show_reward_progress: this._t("kiosk.editor.show_reward_progress"),
    show_picker_progress: this._t("kiosk.editor.show_picker_progress"),
  })[entry.name] ?? entry.name;

  _computeHelper = (entry) => ({
    title: this._t("kiosk.editor.title_helper"),
    timeout: this._t("kiosk.editor.timeout_helper"),
    warn_before_return: this._t("kiosk.editor.warn_before_return_helper"),
    show_picker_progress: this._t("kiosk.editor.show_picker_progress_helper"),
  })[entry.name] ?? "";

  /** Every child, configured ones first in their order, each with shown/require_pin. */
  _childRows() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity || "sensor.taskmate_overview")) || {};
    const all = attrs.children || [];
    const configured = Array.isArray(this.config.children) ? this.config.children : null;
    if (!configured) return all.map(c => ({ child: c, shown: !c.is_guest, requirePin: true }));
    const rows = [];
    for (const entry of configured) {
      const child = all.find(c => String(c.id) === String(entry && (entry.child_id ?? entry)));
      if (child && !rows.some(r => r.child.id === child.id)) rows.push({ child, shown: true, requirePin: entry?.require_pin !== false });
    }
    for (const child of all) {
      if (!rows.some(r => r.child.id === child.id)) rows.push({ child, shown: false, requirePin: true });
    }
    return rows;
  }

  _writeChildren(rows) {
    this._dispatch({
      ...this.config,
      children: rows.filter(r => r.shown).map(r => ({ child_id: r.child.id, require_pin: r.requirePin })),
    });
  }

  _toggleShown(index) {
    const rows = this._childRows();
    rows[index] = { ...rows[index], shown: !rows[index].shown };
    this._writeChildren(rows);
  }

  _togglePin(index) {
    const rows = this._childRows();
    rows[index] = { ...rows[index], requirePin: !rows[index].requirePin };
    this._writeChildren(rows);
  }

  _move(index, delta) {
    const rows = this._childRows();
    const target = index + delta;
    if (target < 0 || target >= rows.length) return;
    [rows[index], rows[target]] = [rows[target], rows[index]];
    this._writeChildren(rows);
  }

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || "sensor.taskmate_overview",
      title: this.config.title || "",
      card_design: this.config.card_design || "global",
      timeout: this.config.timeout ?? DEFAULT_TIMEOUT,
      warn_before_return: this.config.warn_before_return !== false,
      show_points: this.config.show_points !== false,
      show_streak: this.config.show_streak !== false,
      show_reward_progress: this.config.show_reward_progress !== false,
      show_picker_progress: this.config.show_picker_progress !== false,
    };
    const rows = this._childRows();
    const pins = this._pins || {};
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._schema()}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}
      ></ha-form>
      ${this._renderColourPicker()}
      <div class="kiosk-children">
        <div class="kiosk-heading">${this._t("kiosk.editor.children_heading")}</div>
        <div class="kiosk-hint">${this._t("kiosk.editor.children_hint")}</div>
        ${rows.map((row, i) => {
          const hasPin = !!pins[String(row.child.id)];
          return html`
            <div class="kiosk-child ${row.shown ? "" : "hidden"}">
              <input type="checkbox" .checked=${row.shown}
                     aria-label="${this._t("kiosk.editor.show_child", { name: row.child.name })}"
                     @change=${() => this._toggleShown(i)}>
              <div class="kiosk-child-name">
                <b>${row.child.name}</b>
                <small>${hasPin ? html`<span class="mask">••••</span> ${this._t("kiosk.editor.pin_set")}` : this._t("kiosk.editor.no_pin")}</small>
              </div>
              <label class="kiosk-pin-toggle">
                <span>${this._t("kiosk.editor.require_pin")}</span>
                <ha-switch .checked=${row.requirePin && hasPin} ?disabled=${!row.shown || !hasPin}
                           @change=${() => this._togglePin(i)}></ha-switch>
              </label>
              <button class="kiosk-move" title="${this._t("kiosk.editor.move_up")}" aria-label="${this._t("kiosk.editor.move_up")}"
                      ?disabled=${i === 0} @click=${() => this._move(i, -1)}><ha-icon icon="mdi:chevron-up"></ha-icon></button>
              <button class="kiosk-move" title="${this._t("kiosk.editor.move_down")}" aria-label="${this._t("kiosk.editor.move_down")}"
                      ?disabled=${i === rows.length - 1} @click=${() => this._move(i, 1)}><ha-icon icon="mdi:chevron-down"></ha-icon></button>
            </div>`;
        })}
        <div class="kiosk-hint">${this._t("kiosk.editor.pin_note")}</div>
      </div>
    `;
  }

  _renderColourPicker() {
    const d = window.__taskmate_design;
    if (!d || !d.colourPicker) return html``;
    const current = this.config.header_color || DEFAULT_HEADER;
    return d.colourPicker({
      defaultValue: DEFAULT_HEADER, current,
      label: this._t("common.editor.header_colour"),
      helper: this._t("common.editor.header_colour_helper"),
      resetLabel: this._t("common.reset"),
      onInput: (v) => this._set("header_color", v),
      onPreset: (v) => this._set("header_color", v),
      onReset: () => this._set("header_color", undefined),
    });
  }

  _formChanged(e) {
    const values = e.detail.value || {};
    const next = { ...this.config };
    for (const [key, value] of Object.entries(values)) {
      if (value === "" || value === null || value === undefined) delete next[key];
      else if (key === "card_design" && value === "global") delete next[key];
      else if (key === "timeout") {
        if (clampTimeout(value) === DEFAULT_TIMEOUT) delete next[key];
        else next[key] = clampTimeout(value);
      } else if (typeof value === "boolean" && key !== "entity") {
        // Every toggle defaults to on: store only the "off" choice.
        if (value) delete next[key];
        else next[key] = false;
      } else next[key] = value;
    }
    this._dispatch(next);
  }

  _set(key, value) {
    const next = { ...this.config, [key]: value };
    if (value === undefined || value === "" || value === null) delete next[key];
    this._dispatch(next);
  }

  _dispatch(config) {
    this.config = config;
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config }, bubbles: true, composed: true,
    }));
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-form { display: block; margin-bottom: 16px; }
      /* The shared header-colour picker's look, as every card editor carries it. */
      .colour-field {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 12px 16px;
        border: 1px solid var(--outline-color, var(--divider-color, #e0e0e0));
        border-radius: 4px;
        background: var(--mdc-text-field-fill-color, var(--card-background-color));
      }
      .colour-field-label {
        font-size: 0.82rem;
        color: var(--primary-color);
        font-weight: 500;
      }
      .colour-field-body {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }
      .colour-swatch-wrapper {
        position: relative;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        overflow: hidden;
        cursor: pointer;
        border: 2px solid var(--divider-color, #e0e0e0);
        flex-shrink: 0;
      }
      .colour-swatch-wrapper input[type="color"] {
        position: absolute;
        inset: 0;
        opacity: 0;
        cursor: pointer;
        border: 0;
        padding: 0;
      }
      .colour-swatch-preview { position: absolute; inset: 0; pointer-events: none; }
      .colour-hex {
        font-family: var(--code-font-family, monospace);
        font-size: 0.85rem;
        color: var(--secondary-text-color);
        min-width: 70px;
      }
      .colour-presets { display: flex; gap: 6px; flex-wrap: wrap; }
      .preset-swatch {
        width: 22px;
        height: 22px;
        border-radius: 50%;
        cursor: pointer;
        border: 2px solid var(--divider-color, #e0e0e0);
        transition: transform 0.1s;
        padding: 0;
      }
      .preset-swatch:hover { transform: scale(1.15); }
      .preset-swatch.active {
        border-color: var(--primary-text-color);
        box-shadow: 0 0 0 2px var(--primary-color);
      }
      .colour-reset {
        font-size: 0.78rem;
        color: var(--secondary-text-color);
        background: none;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        padding: 4px 10px;
        cursor: pointer;
        margin-inline-start: auto;
      }
      .colour-helper {
        color: var(--secondary-text-color);
        font-size: 0.82rem;
        line-height: 1.3;
      }
      .kiosk-children { margin-top: 16px; display: flex; flex-direction: column; gap: 6px; }
      .kiosk-heading { font-weight: 600; color: var(--primary-color); }
      .kiosk-hint { font-size: 12px; color: var(--secondary-text-color); }
      .kiosk-child {
        display: grid; grid-template-columns: 28px 1fr auto 36px 36px; gap: 8px; align-items: center;
        padding: 6px 0; border-top: 1px solid var(--divider-color);
      }
      .kiosk-child.hidden .kiosk-child-name { opacity: 0.5; }
      .kiosk-child input { width: 18px; height: 18px; accent-color: var(--primary-color); }
      .kiosk-child-name { display: flex; flex-direction: column; min-width: 0; }
      .kiosk-child-name small { color: var(--secondary-text-color); font-size: 12px; }
      .kiosk-child-name .mask { letter-spacing: 3px; }
      .kiosk-pin-toggle { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--secondary-text-color); }
      .kiosk-move {
        width: 36px; height: 36px; border-radius: 50%; border: 0; background: transparent;
        color: var(--primary-text-color); cursor: pointer; display: grid; place-items: center;
      }
      .kiosk-move:disabled { opacity: 0.3; cursor: default; }
    `;
  }
}

customElements.define("taskmate-kiosk-card", TaskMateKioskCard);
customElements.define("taskmate-kiosk-card-editor", TaskMateKioskCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-kiosk-card",
  name: "TaskMate Kiosk",
  description: "Shared wall-tablet view: each child taps their face (optional PIN) to see and tick off their own chores",
  preview: false,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-kiosk-card", "overview"),
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-kiosk-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE KIOSK CARD %c v" + _tmVersion + " ",
  "background:#9b59b6;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
