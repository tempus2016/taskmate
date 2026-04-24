/**
 * TaskMate admin panel — sidebar entry at /taskmate-admin.
 *
 * Stage 2a: tab shell + working Children CRUD.
 * Other tabs render a "coming soon" placeholder; they land in subsequent
 * alpha releases on this branch.
 *
 * Vanilla HTMLElement — no LitElement dependency.
 */

const PANEL_VERSION = "3.5.0-alpha.3";

const TABS = [
  { id: "children",  label: "Children" },
  { id: "chores",    label: "Chores" },
  { id: "rewards",   label: "Rewards" },
  { id: "penalties", label: "Penalties" },
  { id: "bonuses",   label: "Bonuses" },
  { id: "groups",    label: "Groups" },
  { id: "settings",  label: "⚙",  title: "Settings" },
];

class TaskMatePanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._state = null;
    this._error = null;
    this._loading = false;
    this._activeTab = "children";
    this._dialog = null;        // { kind: "child", mode: "add"|"edit", data }
    this._rendered = false;
    this._onClick = this._onClick.bind(this);
    this._onInput = this._onInput.bind(this);
    this._onChange = this._onChange.bind(this);
    this._onKeyDown = this._onKeyDown.bind(this);
  }

  // ---- HA-injected properties ----------------------------------------------
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
    // Render toasts outside the innerHTML tree so hiding them doesn't
    // tear down the current dialog's <input>s and blur what the user is typing.
    const existing = this.querySelector(".tm-toast");
    if (existing) existing.remove();
    const node = document.createElement("div");
    node.className = `tm-toast tm-toast-${kind}`;
    node.textContent = text;
    this.appendChild(node);
    setTimeout(() => {
      if (node.isConnected) node.remove();
    }, 3500);
  }

  // ---- event delegation ------------------------------------------------
  _onClick(e) {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const act = t.dataset.act;

    // Tab switching
    if (act === "tab") {
      this._activeTab = t.dataset.tab;
      this._render();
      return;
    }

    // Dialog open / close
    if (act === "close-dialog" || act === "scrim") {
      this._dialog = null;
      this._render();
      return;
    }

    // Children
    if (act === "add-child") {
      this._dialog = { kind: "child", mode: "add", data: { name: "", avatar: "mdi:account-circle", availability_entity: "" } };
      this._render();
      return;
    }
    if (act === "edit-child") {
      const child = (this._state.children || []).find(c => c.id === t.dataset.id);
      if (!child) return;
      this._dialog = { kind: "child", mode: "edit", data: { id: child.id, name: child.name || "", avatar: child.avatar || "mdi:account-circle", availability_entity: child.availability_entity || "" } };
      this._render();
      return;
    }
    if (act === "delete-child") {
      const id = t.dataset.id;
      const child = (this._state.children || []).find(c => c.id === id);
      if (!child) return;
      if (!confirm(`Delete "${child.name}"?\n\nThis also removes all of their completion history, reward claims, points transactions, and pool allocations. Chores assigned to them will be updated. This cannot be undone.`)) return;
      this._doRemoveChild(id);
      return;
    }
    if (act === "save-child") {
      this._doSaveChild();
      return;
    }
    if (act === "retry") {
      this._fetchState();
      return;
    }
  }

  _onInput(e) {
    if (!this._dialog) return;
    const t = e.target;
    if (!t.dataset || !t.dataset.field) return;
    this._dialog.data[t.dataset.field] = t.value;
    // no re-render; live-bound fields shouldn't cause full rerender per keystroke
  }

  _onChange(e) {
    if (!this._dialog) return;
    const t = e.target;
    if (!t.dataset || !t.dataset.field) return;
    this._dialog.data[t.dataset.field] = t.value;
  }

  _onKeyDown(e) {
    if (e.key === "Escape" && this._dialog) {
      this._dialog = null;
      this._render();
    }
  }

  // ---- child actions ---------------------------------------------------
  async _doSaveChild() {
    const d = this._dialog.data;
    if (!d.name || !d.name.trim()) {
      this._showToast("err", "Name is required");
      return;
    }
    let payload;
    if (this._dialog.mode === "add") {
      payload = {
        type: "taskmate/add_child",
        name: d.name.trim(),
        avatar: d.avatar || "mdi:account-circle",
        availability_entity: d.availability_entity || "",
      };
    } else {
      payload = {
        type: "taskmate/update_child",
        child_id: d.id,
        name: d.name.trim(),
        avatar: d.avatar || "mdi:account-circle",
        availability_entity: d.availability_entity || "",
      };
    }
    const wasAdd = this._dialog.mode === "add";
    const { ok, err } = await this._callWS(payload);
    if (!ok) {
      this._showToast("err", `Save failed: ${err}`);
      return;
    }
    this._dialog = null;
    await this._fetchState();
    this._showToast("ok", wasAdd ? "Child added" : "Child updated");
  }

  async _doRemoveChild(child_id) {
    const { ok, err } = await this._callWS({ type: "taskmate/remove_child", child_id });
    if (!ok) {
      this._showToast("err", `Delete failed: ${err}`);
      return;
    }
    await this._fetchState();
    this._showToast("ok", "Deleted");
  }

  // ---- rendering -------------------------------------------------------
  _render() {
    this._rendered = true;
    // Preserve any existing toast across re-renders (it's a transient DOM
    // node appended outside the shell — see _showToast).
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
    if (this._loading && !this._state) {
      return `<div class="tm-card">Loading…</div>`;
    }
    if (this._error) {
      return `
        <div class="tm-card tm-card-error">
          <h2>Failed to load state</h2>
          <p>${this._esc(this._error)}</p>
          <button class="tm-btn" data-act="retry">Retry</button>
        </div>
      `;
    }
    if (!this._state) {
      return `<div class="tm-card">No state yet.</div>`;
    }

    switch (this._activeTab) {
      case "children":  return this._renderChildrenTab();
      case "chores":    return this._placeholderTab("Chores",    "alpha.4");
      case "rewards":   return this._placeholderTab("Rewards",   "alpha.5");
      case "penalties": return this._placeholderTab("Penalties", "alpha.6");
      case "bonuses":   return this._placeholderTab("Bonuses",   "alpha.6");
      case "groups":    return this._placeholderTab("Groups",    "alpha.7");
      case "settings":  return this._placeholderTab("Settings",  "alpha.7");
      default:          return `<div class="tm-card">Unknown tab</div>`;
    }
  }

  _placeholderTab(name, when) {
    return `
      <div class="tm-card tm-card-info">
        <h2>${this._esc(name)} — coming in the next alpha</h2>
        <p>This tab will be wired up in <code>v3.5.0-${when}</code>. For now, continue to use
           <strong>Settings → Devices &amp; Services → TaskMate → Configure</strong> for ${this._esc(name.toLowerCase())}.</p>
      </div>
    `;
  }

  // -- Children tab ------------------------------------------------------
  _renderChildrenTab() {
    const children = this._state.children || [];
    const pointsName = (this._state.settings && this._state.settings.points_name) || "points";
    return `
      <div class="tm-toolbar">
        <div class="tm-title-sub">Manage the children in your family. Their points balance and history stay intact when you edit details.</div>
        <button class="tm-btn" data-act="add-child">+ Add child</button>
      </div>

      ${children.length === 0 ? `
        <div class="tm-card tm-empty">
          <h2>No children yet</h2>
          <p>Add your first child to get started. You can assign chores and rewards to them on the next tabs.</p>
          <button class="tm-btn" data-act="add-child">+ Add child</button>
        </div>
      ` : `
        <div class="tm-grid">
          ${children.map(c => this._renderChildCard(c, pointsName)).join("")}
          <button class="tm-add-tile" data-act="add-child">
            <span class="tm-add-plus">+</span>
            Add child
          </button>
        </div>
      `}
    `;
  }

  _renderChildCard(child, pointsName) {
    const avatar = child.avatar || "mdi:account-circle";
    const availability = child.availability_entity || "";
    const points = child.points || 0;
    const total = child.total_points_earned || 0;
    const completions = child.total_chores_completed || 0;
    return `
      <article class="tm-card tm-child-card">
        <header class="tm-child-head">
          <div class="tm-avatar">${this._mdi(avatar)}</div>
          <div class="tm-child-name">
            <h3>${this._esc(child.name || "(unnamed)")}</h3>
            <div class="tm-sub">
              ${availability ? `Availability: <code>${this._esc(availability)}</code>` : `<em>No availability sensor</em>`}
            </div>
          </div>
        </header>
        <div class="tm-stats">
          <div class="tm-stat">
            <strong>${this._fmtNum(points)}</strong>
            <span>spendable ${this._esc(pointsName)}</span>
          </div>
          <div class="tm-stat">
            <strong>${this._fmtNum(total)}</strong>
            <span>earned all-time</span>
          </div>
          <div class="tm-stat">
            <strong>${this._fmtNum(completions)}</strong>
            <span>chores done</span>
          </div>
        </div>
        <footer class="tm-child-foot">
          <button class="tm-btn tm-btn-ghost" data-act="edit-child" data-id="${this._esc(child.id)}">Edit</button>
          <button class="tm-btn tm-btn-danger" data-act="delete-child" data-id="${this._esc(child.id)}">Delete</button>
        </footer>
      </article>
    `;
  }

  // -- Dialogs -----------------------------------------------------------
  _renderDialog() {
    if (this._dialog.kind === "child") return this._renderChildDialog();
    return "";
  }

  _renderChildDialog() {
    const d = this._dialog.data;
    const title = this._dialog.mode === "add" ? "Add child" : "Edit child";
    return `
      <div class="tm-scrim" data-act="scrim">
        <div class="tm-dialog" onclick="event.stopPropagation()">
          <header class="tm-dialog-head">
            <h2>${title}</h2>
            <button class="tm-icon-btn" data-act="close-dialog" title="Close">&times;</button>
          </header>
          <div class="tm-dialog-body">
            <label class="tm-field">
              <span class="tm-field-label">Name</span>
              <input type="text" data-field="name" value="${this._esc(d.name || "")}" placeholder="e.g. Malia" autofocus>
            </label>
            <label class="tm-field">
              <span class="tm-field-label">Avatar (MDI icon)</span>
              <input type="text" data-field="avatar" value="${this._esc(d.avatar || "mdi:account-circle")}" placeholder="mdi:account-circle">
              <span class="tm-field-hint">Any Material Design icon, e.g. <code>mdi:face-woman</code>, <code>mdi:face-man</code>.</span>
            </label>
            <label class="tm-field">
              <span class="tm-field-label">Availability sensor <span class="tm-field-opt">(optional)</span></span>
              <input type="text" data-field="availability_entity" value="${this._esc(d.availability_entity || "")}" placeholder="binary_sensor.malia_home">
              <span class="tm-field-hint">HA entity that tells TaskMate whether this child is available. States <code>on</code>, <code>home</code>, <code>available</code>, <code>present</code>, <code>true</code> mean available. Leave blank to treat as always available.</span>
            </label>
          </div>
          <footer class="tm-dialog-foot">
            <button class="tm-btn tm-btn-ghost" data-act="close-dialog">Cancel</button>
            <button class="tm-btn" data-act="save-child">Save</button>
          </footer>
        </div>
      </div>
    `;
  }

  // ---- helpers ---------------------------------------------------------
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
    // Render an mdi: name as an <ha-icon>. HA's <ha-icon> custom element is
    // globally registered by the frontend and tolerates us creating it before
    // it's upgraded — it'll upgrade and render on its own.
    const safe = this._esc(name || "mdi:account-circle");
    return `<ha-icon icon="${safe}"></ha-icon>`;
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
      .tm-card h2 { margin: 0 0 12px; font-size: 18px; font-weight: 500; }
      .tm-card p { margin: 8px 0; color: var(--secondary-text-color, #9aa0a6); }
      .tm-card code { background: var(--code-editor-background-color, #0e1115); padding: 2px 6px; border-radius: 4px; font-size: 12px; }
      .tm-card-info { border-left: 3px solid var(--primary-color, #03a9f4); }
      .tm-card-error { border-left: 3px solid var(--error-color, #ef5350); color: var(--error-color, #ef5350); }
      .tm-empty { text-align: center; padding: 40px 24px; }

      .tm-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
      .tm-child-card { margin-bottom: 0; display: flex; flex-direction: column; }
      .tm-child-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
      .tm-avatar { width: 48px; height: 48px; border-radius: 50%; background: var(--secondary-background-color, #242830); display: grid; place-items: center; flex-shrink: 0; font-size: 28px; color: var(--primary-color, #03a9f4); }
      .tm-avatar ha-icon { --mdc-icon-size: 28px; }
      .tm-child-name { min-width: 0; flex: 1; }
      .tm-child-name h3 { margin: 0; font-size: 17px; font-weight: 600; }
      .tm-sub { color: var(--secondary-text-color, #9aa0a6); font-size: 12px; margin-top: 2px; word-break: break-all; }
      .tm-sub code { background: var(--code-editor-background-color, #0e1115); padding: 1px 6px; border-radius: 4px; font-size: 11px; }

      .tm-stats { display: flex; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
      .tm-stat { background: var(--secondary-background-color, #242830); padding: 8px 12px; border-radius: 8px; flex: 1; min-width: 80px; }
      .tm-stat strong { display: block; font-size: 20px; font-weight: 600; color: var(--primary-color, #03a9f4); }
      .tm-stat span { font-size: 11px; color: var(--secondary-text-color, #9aa0a6); text-transform: uppercase; letter-spacing: 0.5px; }

      .tm-child-foot { display: flex; gap: 8px; margin-top: auto; padding-top: 12px; border-top: 1px solid var(--divider-color, #2a2e36); }

      .tm-add-tile { display: grid; place-items: center; gap: 6px; background: transparent; border: 2px dashed var(--divider-color, #2a2e36); border-radius: 12px; color: var(--secondary-text-color, #9aa0a6); cursor: pointer; min-height: 180px; font-size: 14px; font-family: inherit; transition: border-color .15s, color .15s, background .15s; }
      .tm-add-tile:hover { border-color: var(--primary-color, #03a9f4); color: var(--primary-color, #03a9f4); background: rgba(3,169,244,0.06); }
      .tm-add-plus { font-size: 32px; line-height: 1; }

      .tm-btn { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #001a26); border: 0; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500; font-family: inherit; }
      .tm-btn:hover { filter: brightness(1.1); }
      .tm-btn:disabled { opacity: 0.5; cursor: not-allowed; }
      .tm-btn-ghost { background: transparent; color: var(--primary-text-color, #e1e3e6); border: 1px solid var(--divider-color, #2a2e36); }
      .tm-btn-ghost:hover { background: var(--secondary-background-color, #242830); filter: none; }
      .tm-btn-danger { background: transparent; color: var(--error-color, #ef5350); border: 1px solid rgba(239,83,80,0.4); }
      .tm-btn-danger:hover { background: rgba(239,83,80,0.1); filter: none; }

      .tm-icon-btn { width: 36px; height: 36px; border: 0; background: transparent; border-radius: 50%; cursor: pointer; display: grid; place-items: center; color: var(--secondary-text-color, #9aa0a6); font-size: 22px; line-height: 1; font-family: inherit; }
      .tm-icon-btn:hover { background: var(--secondary-background-color, #242830); color: var(--primary-text-color, #e1e3e6); }

      /* Dialog */
      .tm-scrim { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: flex-start; justify-content: center; padding: 60px 20px; z-index: 100; overflow-y: auto; }
      .tm-dialog { background: var(--card-background-color, #1c1f24); border: 1px solid var(--divider-color, #2a2e36); border-radius: 12px; width: 100%; max-width: 520px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); display: flex; flex-direction: column; max-height: calc(100vh - 120px); }
      .tm-dialog-head { padding: 16px 20px; border-bottom: 1px solid var(--divider-color, #2a2e36); display: flex; align-items: center; }
      .tm-dialog-head h2 { margin: 0; font-size: 18px; font-weight: 500; flex: 1; }
      .tm-dialog-body { padding: 16px 20px; overflow-y: auto; }
      .tm-dialog-foot { padding: 14px 20px; border-top: 1px solid var(--divider-color, #2a2e36); display: flex; justify-content: flex-end; gap: 10px; }

      .tm-field { display: block; margin-bottom: 16px; }
      .tm-field-label { display: block; color: var(--secondary-text-color, #9aa0a6); font-size: 12px; margin-bottom: 6px; }
      .tm-field-opt { color: var(--secondary-text-color, #6a7079); font-weight: normal; }
      .tm-field input[type=text] { width: 100%; background: var(--secondary-background-color, #242830); border: 1px solid var(--divider-color, #2a2e36); border-radius: 8px; padding: 9px 12px; color: var(--primary-text-color, #e1e3e6); font-size: 14px; box-sizing: border-box; font-family: inherit; }
      .tm-field input[type=text]:focus { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: -1px; border-color: transparent; }
      .tm-field-hint { display: block; color: var(--secondary-text-color, #6a7079); font-size: 12px; margin-top: 6px; }
      .tm-field-hint code { background: var(--code-editor-background-color, #0e1115); padding: 1px 5px; border-radius: 3px; font-size: 11px; }

      /* Toast */
      .tm-toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); padding: 10px 18px; border-radius: 8px; font-size: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.4); z-index: 200; }
      .tm-toast-ok { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #001a26); }
      .tm-toast-err { background: var(--error-color, #ef5350); color: white; }

      /* Narrow / mobile */
      @media (max-width: 700px) {
        .tm-body { padding: 16px; }
        .tm-toolbar { flex-direction: column; align-items: stretch; }
        .tm-dialog { max-width: none; }
        .tm-scrim { padding: 0; }
        .tm-dialog { border-radius: 0; max-height: 100vh; height: 100vh; }
      }
    </style>`;
  }
}

customElements.define("taskmate-panel", TaskMatePanel);
