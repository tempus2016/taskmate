/**
 * TaskMate admin panel — sidebar entry at /taskmate.
 *
 * Stage 1: minimal element that confirms the panel registers, the JS module
 * loads, and the WebSocket round-trip works. The full multi-tab UI lands in
 * subsequent commits on this branch.
 *
 * Vanilla HTMLElement (no LitElement dependency) — keeps the panel robust
 * against load-order issues when navigating directly to /taskmate before any
 * Lovelace view has been opened.
 */

const PANEL_VERSION = "3.5.0-alpha.1";

class TaskMatePanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._state = null;
    this._error = null;
    this._loading = false;
    this._rendered = false;
  }

  set hass(value) {
    const first = this._hass === null;
    this._hass = value;
    if (first) {
      this._fetchState();
    }
    if (!this._rendered) {
      this._render();
    }
  }
  get hass() { return this._hass; }

  // panel-custom also injects narrow/route/panel — we accept but ignore for now
  set narrow(_v) {}
  set route(_v) {}
  set panel(_v) {}

  connectedCallback() {
    if (!this._rendered) this._render();
  }

  async _fetchState() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    this._error = null;
    this._render();
    try {
      this._state = await this._hass.callWS({ type: "taskmate/get_state" });
    } catch (err) {
      this._error = (err && err.message) || String(err);
      this._state = null;
    } finally {
      this._loading = false;
      this._render();
    }
  }

  _render() {
    this._rendered = true;
    const counts = this._state ? {
      children:    (this._state.children || []).length,
      chores:      (this._state.chores || []).length,
      rewards:     (this._state.rewards || []).length,
      penalties:   (this._state.penalties || []).length,
      bonuses:     (this._state.bonuses || []).length,
      task_groups: (this._state.task_groups || []).length,
    } : null;

    this.innerHTML = `
      <style>
        :host, taskmate-panel { display: block; height: 100%; background: var(--primary-background-color, #111418); color: var(--primary-text-color, #e1e3e6); }
        .tm-shell { display: flex; flex-direction: column; height: 100%; font-family: var(--paper-font-body1_-_font-family, sans-serif); }
        .tm-appbar { height: 56px; background: var(--app-header-background-color, #1a1d22); color: var(--app-header-text-color, #fff); display: flex; align-items: center; gap: 12px; padding: 0 16px; flex-shrink: 0; border-bottom: 1px solid var(--divider-color, #2a2e36); }
        .tm-appbar h1 { margin: 0; font-size: 20px; font-weight: 400; flex: 1; }
        .tm-chip { background: rgba(255,255,255,0.1); padding: 4px 10px; border-radius: 999px; font-size: 12px; }
        .tm-body { flex: 1; overflow: auto; padding: 24px; max-width: 900px; margin: 0 auto; width: 100%; box-sizing: border-box; }
        .tm-card { background: var(--card-background-color, #1c1f24); border: 1px solid var(--divider-color, #2a2e36); border-radius: 12px; padding: 20px 24px; margin-bottom: 16px; }
        .tm-card h2 { margin: 0 0 12px; font-size: 18px; font-weight: 500; }
        .tm-banner { background: rgba(3,169,244,0.08); border: 1px solid rgba(3,169,244,0.25); color: var(--primary-color, #03a9f4); padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; }
        .tm-counts { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; }
        .tm-count { background: var(--secondary-background-color, #242830); padding: 12px; border-radius: 8px; text-align: center; }
        .tm-count strong { display: block; font-size: 24px; color: var(--primary-color, #03a9f4); }
        .tm-count span { font-size: 12px; color: var(--secondary-text-color, #9aa0a6); text-transform: uppercase; letter-spacing: 0.5px; }
        .tm-error { color: var(--error-color, #ef5350); }
        .tm-btn { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #001a26); border: 0; padding: 8px 16px; border-radius: 8px; cursor: pointer; font-size: 14px; }
        .tm-btn:hover { filter: brightness(1.1); }
        pre { background: var(--code-editor-background-color, #0e1115); padding: 12px; border-radius: 8px; overflow: auto; font-size: 11px; max-height: 300px; }
      </style>
      <div class="tm-shell">
        <div class="tm-appbar">
          <h1>TaskMate</h1>
          <span class="tm-chip">v${PANEL_VERSION}</span>
        </div>
        <div class="tm-body">
          <div class="tm-banner">
            <strong>Stage 1 preview</strong> — backend wiring is in place. The full multi-tab admin UI (Children · Chores · Rewards · Penalties · Bonuses · Groups · Settings) lands in the next commits on this branch. Pull updates via HACS ⋮ → Redownload.
          </div>

          ${this._loading ? `
            <div class="tm-card">Loading state…</div>
          ` : this._error ? `
            <div class="tm-card tm-error">
              <h2>Failed to load state</h2>
              <p>${this._escape(this._error)}</p>
              <button class="tm-btn" id="tm-retry">Retry</button>
            </div>
          ` : counts ? `
            <div class="tm-card">
              <h2>Storage snapshot</h2>
              <div class="tm-counts">
                <div class="tm-count"><strong>${counts.children}</strong><span>Children</span></div>
                <div class="tm-count"><strong>${counts.chores}</strong><span>Chores</span></div>
                <div class="tm-count"><strong>${counts.rewards}</strong><span>Rewards</span></div>
                <div class="tm-count"><strong>${counts.penalties}</strong><span>Penalties</span></div>
                <div class="tm-count"><strong>${counts.bonuses}</strong><span>Bonuses</span></div>
                <div class="tm-count"><strong>${counts.task_groups}</strong><span>Groups</span></div>
              </div>
              <p style="margin-top: 16px; color: var(--secondary-text-color, #9aa0a6); font-size: 13px;">
                Currency: <code>${this._escape(this._state.settings.points_name)}</code> &middot;
                Icon: <code>${this._escape(this._state.settings.points_icon)}</code>
              </p>
              <details style="margin-top: 16px;">
                <summary style="cursor: pointer; color: var(--secondary-text-color, #9aa0a6);">Raw state (JSON)</summary>
                <pre>${this._escape(JSON.stringify(this._state, null, 2))}</pre>
              </details>
            </div>
          ` : `
            <div class="tm-card">No state yet.</div>
          `}
        </div>
      </div>
    `;

    const retry = this.querySelector("#tm-retry");
    if (retry) retry.addEventListener("click", () => this._fetchState());
  }

  _escape(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
}

customElements.define("taskmate-panel", TaskMatePanel);
