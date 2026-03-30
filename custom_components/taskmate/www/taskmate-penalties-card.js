/**
 * TaskMate Penalties Card
 * Apply point-deduction penalties to children (e.g. "Not going to bed").
 * Parents can manage penalty definitions and tap to apply them instantly.
 *
 * Version: 0.0.1
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMatePenaltiesCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _selectedChildId: { type: String },
      _editMode: { type: Boolean },
      _loading: { type: Object },
      _editingPenalty: { type: Object },   // penalty being edited (null = none)
      _showNewForm: { type: Boolean },
      _toast: { type: String },
      _newForm: { type: Object },
    };
  }

  constructor() {
    super();
    this._selectedChildId = null;
    this._editMode = false;
    this._loading = {};
    this._editingPenalty = null;
    this._showNewForm = false;
    this._toast = null;
    this._newForm = { name: "", points: "", description: "", icon: "mdi:alert-circle-outline" };
  }

  setConfig(config) {
    this.config = config;
  }

  static getConfigElement() {
    return document.createElement("taskmate-penalties-card-editor");
  }

  static getStubConfig() {
    return { entity: "sensor.taskmate_overview" };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        --penalty-red: #e74c3c;
        --penalty-red-dark: #c0392b;
        --penalty-red-light: rgba(231, 76, 60, 0.12);
        --text-primary: var(--primary-text-color, #212121);
        --text-secondary: var(--secondary-text-color, #757575);
        --card-bg: var(--card-background-color, #fff);
        --divider: var(--divider-color, #e0e0e0);
      }

      ha-card { overflow: hidden; }

      /* ── Header ── */
      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, var(--penalty-red));
        color: white;
      }
      .header-left { display: flex; align-items: center; gap: 12px; }
      .header-icon { --mdc-icon-size: 32px; opacity: 0.95; }
      .header-title { font-size: 1.3rem; font-weight: 600; }
      .penalty-count {
        background: rgba(255,255,255,0.2);
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.9rem;
        font-weight: 500;
      }
      .header-actions { display: flex; gap: 8px; }
      .icon-btn {
        background: rgba(255,255,255,0.18);
        border: none;
        color: white;
        border-radius: 50%;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: background 0.2s;
        --mdc-icon-size: 20px;
      }
      .icon-btn:hover { background: rgba(255,255,255,0.32); }
      .icon-btn.active { background: rgba(255,255,255,0.35); }

      /* ── Child tabs ── */
      .child-tabs {
        display: flex;
        gap: 6px;
        padding: 10px 16px 0;
        overflow-x: auto;
        scrollbar-width: none;
      }
      .child-tabs::-webkit-scrollbar { display: none; }
      .child-tab {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 20px;
        background: var(--divider);
        border: 2px solid transparent;
        cursor: pointer;
        font-size: 0.9rem;
        font-weight: 500;
        white-space: nowrap;
        color: var(--text-secondary);
        transition: all 0.15s;
      }
      .child-tab ha-icon { --mdc-icon-size: 18px; }
      .child-tab.selected {
        background: var(--penalty-red-light);
        border-color: var(--penalty-red);
        color: var(--penalty-red);
      }

      /* ── Card body ── */
      .card-content {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }

      /* ── Penalty tile ── */
      .penalty-row {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 14px 16px;
        background: var(--card-bg);
        border: 1px solid var(--divider);
        border-radius: 12px;
        transition: box-shadow 0.2s, transform 0.15s;
      }
      .penalty-row:hover { box-shadow: 0 3px 10px rgba(0,0,0,0.09); transform: translateY(-1px); }

      /* Flash animation when penalty is applied */
      @keyframes flash-red {
        0%   { background: var(--penalty-red-light); }
        40%  { background: rgba(231,76,60,0.25); }
        100% { background: var(--card-bg); }
      }
      .penalty-row.flashing { animation: flash-red 0.6s ease forwards; }

      /* Points badge */
      .points-badge {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-width: 64px;
        padding: 10px 8px;
        background: linear-gradient(135deg, var(--penalty-red) 0%, var(--penalty-red-dark) 100%);
        border-radius: 10px;
        flex-shrink: 0;
        box-shadow: 0 2px 6px rgba(231,76,60,0.3);
      }
      .points-badge ha-icon { --mdc-icon-size: 20px; color: white; margin-bottom: 2px; }
      .points-value { font-size: 1.3rem; font-weight: 700; color: white; line-height: 1; }
      .points-label { font-size: 0.62rem; font-weight: 600; color: rgba(255,255,255,0.88); text-transform: uppercase; letter-spacing: 0.4px; margin-top: 2px; }

      /* Penalty info */
      .penalty-info { flex: 1; min-width: 0; }
      .penalty-name { font-size: 1.05rem; font-weight: 600; color: var(--text-primary); }
      .penalty-description { font-size: 0.85rem; color: var(--text-secondary); margin-top: 2px; }

      /* Apply button */
      .apply-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        padding: 8px 16px;
        background: var(--penalty-red);
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 0.9rem;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s, transform 0.1s;
        white-space: nowrap;
        flex-shrink: 0;
        --mdc-icon-size: 16px;
      }
      .apply-btn:hover { background: var(--penalty-red-dark); }
      .apply-btn:active { transform: scale(0.97); }
      .apply-btn:disabled { opacity: 0.55; cursor: default; }

      /* Edit mode actions */
      .edit-actions { display: flex; gap: 6px; flex-shrink: 0; }
      .edit-btn {
        background: none;
        border: 1px solid var(--divider);
        border-radius: 8px;
        width: 34px;
        height: 34px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        color: var(--text-secondary);
        --mdc-icon-size: 18px;
        transition: all 0.15s;
      }
      .edit-btn:hover { background: var(--divider); color: var(--text-primary); }
      .edit-btn.delete:hover { background: var(--penalty-red-light); color: var(--penalty-red); border-color: var(--penalty-red); }

      /* Inline edit form */
      .edit-form {
        background: var(--ha-card-background, #f5f5f5);
        border: 1px solid var(--divider);
        border-radius: 12px;
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        margin-top: -4px;
      }
      .form-row { display: flex; gap: 10px; }
      .form-row.full { flex-direction: column; }
      .form-field {
        display: flex;
        flex-direction: column;
        gap: 4px;
        flex: 1;
      }
      .form-field label { font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.4px; }
      .form-field input {
        padding: 8px 10px;
        border: 1px solid var(--divider);
        border-radius: 8px;
        font-size: 0.95rem;
        background: var(--card-bg);
        color: var(--text-primary);
        width: 100%;
        box-sizing: border-box;
      }
      .form-field input:focus { outline: 2px solid var(--penalty-red); border-color: transparent; }
      .form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
      .btn-save {
        padding: 8px 18px;
        background: var(--penalty-red);
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 0.9rem;
        font-weight: 600;
        cursor: pointer;
      }
      .btn-save:hover { background: var(--penalty-red-dark); }
      .btn-cancel {
        padding: 8px 14px;
        background: none;
        color: var(--text-secondary);
        border: 1px solid var(--divider);
        border-radius: 8px;
        font-size: 0.9rem;
        cursor: pointer;
      }
      .btn-cancel:hover { background: var(--divider); }

      /* Add new button */
      .add-penalty-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 12px;
        border: 2px dashed var(--divider);
        border-radius: 12px;
        background: none;
        color: var(--text-secondary);
        cursor: pointer;
        font-size: 0.95rem;
        font-weight: 500;
        transition: all 0.15s;
        --mdc-icon-size: 20px;
      }
      .add-penalty-btn:hover { border-color: var(--penalty-red); color: var(--penalty-red); background: var(--penalty-red-light); }

      /* Empty state */
      .empty-state {
        text-align: center;
        padding: 32px 16px;
        color: var(--text-secondary);
      }
      .empty-state ha-icon { --mdc-icon-size: 48px; opacity: 0.35; display: block; margin: 0 auto 12px; }
      .empty-state .empty-title { font-size: 1rem; font-weight: 600; margin-bottom: 4px; }
      .empty-state .empty-sub { font-size: 0.85rem; }

      /* Toast */
      .toast {
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%) translateY(0);
        background: #333;
        color: white;
        padding: 10px 20px;
        border-radius: 24px;
        font-size: 0.92rem;
        font-weight: 500;
        z-index: 9999;
        pointer-events: none;
        animation: toast-in 0.25s ease, toast-out 0.3s ease 2s forwards;
        white-space: nowrap;
      }
      @keyframes toast-in {
        from { opacity: 0; transform: translateX(-50%) translateY(12px); }
        to   { opacity: 1; transform: translateX(-50%) translateY(0); }
      }
      @keyframes toast-out {
        to { opacity: 0; transform: translateX(-50%) translateY(8px); }
      }
    `;
  }

  _getState() {
    const entityId = this.config?.entity || "sensor.taskmate_overview";
    return this.hass?.states[entityId];
  }

  _getAttrs() {
    return this._getState()?.attributes || {};
  }

  _getChildren() {
    return this._getAttrs().children || [];
  }

  _getPenalties() {
    return this._getAttrs().penalties || [];
  }

  _getSelectedChild() {
    const children = this._getChildren();
    if (!children.length) return null;
    if (this._selectedChildId) return children.find(c => c.id === this._selectedChildId) || children[0];
    return children[0];
  }

  _getPointsName() {
    return this._getAttrs().points_name || "Stars";
  }

  _getVisiblePenalties() {
    const child = this._getSelectedChild();
    if (!child) return this._getPenalties();
    return this._getPenalties().filter(p =>
      !p.assigned_to?.length || p.assigned_to.includes(child.id)
    );
  }

  _selectChild(id) {
    this._selectedChildId = id;
    this._editingPenalty = null;
    this._showNewForm = false;
  }

  async _applyPenalty(penalty) {
    const child = this._getSelectedChild();
    if (!child) return;
    const key = penalty.id;
    if (this._loading[key]) return;
    this._loading = { ...this._loading, [key]: true };

    try {
      await this.hass.callService("taskmate", "apply_penalty", {
        penalty_id: penalty.id,
        child_id: child.id,
      });
      this._showToast(`-${penalty.points} ${this._getPointsName()} from ${child.name}`);
      // Flash the row
      const row = this.shadowRoot.querySelector(`[data-penalty-id="${penalty.id}"]`);
      if (row) {
        row.classList.add("flashing");
        setTimeout(() => row.classList.remove("flashing"), 700);
      }
    } catch (e) {
      this._showToast("Failed to apply penalty");
    } finally {
      this._loading = { ...this._loading, [key]: false };
    }
  }

  _showToast(msg) {
    this._toast = null;
    // Force re-render with new toast
    setTimeout(() => {
      this._toast = msg;
      setTimeout(() => { this._toast = null; }, 2700);
    }, 10);
  }

  _startEdit(penalty) {
    this._editingPenalty = { ...penalty };
    this._showNewForm = false;
  }

  _cancelEdit() {
    this._editingPenalty = null;
  }

  async _saveEdit() {
    if (!this._editingPenalty?.name || !this._editingPenalty?.points) return;
    try {
      await this.hass.callService("taskmate", "update_penalty", {
        penalty_id: this._editingPenalty.id,
        name: this._editingPenalty.name,
        points: parseInt(this._editingPenalty.points, 10),
        description: this._editingPenalty.description || "",
        icon: this._editingPenalty.icon || "mdi:alert-circle-outline",
      });
      this._editingPenalty = null;
    } catch (e) {
      this._showToast("Failed to save changes");
    }
  }

  async _deletePenalty(id) {
    try {
      await this.hass.callService("taskmate", "remove_penalty", { penalty_id: id });
    } catch (e) {
      this._showToast("Failed to delete penalty");
    }
  }

  _openNewForm() {
    this._showNewForm = true;
    this._editingPenalty = null;
    this._newForm = { name: "", points: "", description: "", icon: "mdi:alert-circle-outline" };
  }

  async _saveNew() {
    if (!this._newForm.name || !this._newForm.points) return;
    try {
      await this.hass.callService("taskmate", "add_penalty", {
        name: this._newForm.name,
        points: parseInt(this._newForm.points, 10),
        description: this._newForm.description || "",
        icon: this._newForm.icon || "mdi:alert-circle-outline",
      });
      this._showNewForm = false;
    } catch (e) {
      this._showToast("Failed to add penalty");
    }
  }

  _renderChildTabs() {
    const children = this._getChildren();
    if (children.length <= 1) return html``;
    const selected = this._getSelectedChild();
    return html`
      <div class="child-tabs">
        ${children.map(c => html`
          <div class="child-tab ${selected?.id === c.id ? "selected" : ""}"
               @click=${() => this._selectChild(c.id)}>
            <ha-icon icon="${c.avatar || "mdi:account-circle"}"></ha-icon>
            ${c.name}
          </div>
        `)}
      </div>
    `;
  }

  _renderPenaltyRow(p) {
    const isEditing = this._editingPenalty?.id === p.id;
    const isLoading = this._loading[p.id];
    const child = this._getSelectedChild();
    const pointsName = this._getPointsName();

    return html`
      <div class="penalty-row" data-penalty-id="${p.id}">
        <div class="points-badge">
          <ha-icon icon="${p.icon || "mdi:alert-circle-outline"}"></ha-icon>
          <div class="points-value">${p.points}</div>
          <div class="points-label">${pointsName}</div>
        </div>

        <div class="penalty-info">
          <div class="penalty-name">${p.name}</div>
          ${p.description ? html`<div class="penalty-description">${p.description}</div>` : ""}
        </div>

        ${this._editMode ? html`
          <div class="edit-actions">
            <button class="edit-btn" title="Edit" @click=${() => this._startEdit(p)}>
              <ha-icon icon="mdi:pencil"></ha-icon>
            </button>
            <button class="edit-btn delete" title="Delete" @click=${() => this._deletePenalty(p.id)}>
              <ha-icon icon="mdi:trash-can-outline"></ha-icon>
            </button>
          </div>
        ` : html`
          <button class="apply-btn"
                  ?disabled=${isLoading || !child}
                  @click=${() => this._applyPenalty(p)}>
            ${isLoading
              ? html`<ha-icon icon="mdi:loading" class="spin"></ha-icon>`
              : html`<ha-icon icon="mdi:minus-circle-outline"></ha-icon> Apply`
            }
          </button>
        `}
      </div>
      ${isEditing ? this._renderEditForm() : ""}
    `;
  }

  _renderEditForm() {
    const p = this._editingPenalty;
    return html`
      <div class="edit-form">
        <div class="form-row">
          <div class="form-field" style="flex:2">
            <label>Name</label>
            <input type="text" .value=${p.name}
              @input=${e => this._editingPenalty = { ...p, name: e.target.value }} />
          </div>
          <div class="form-field" style="flex:1">
            <label>Points</label>
            <input type="number" min="1" .value=${p.points}
              @input=${e => this._editingPenalty = { ...p, points: e.target.value }} />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>Icon (MDI)</label>
            <input type="text" .value=${p.icon || "mdi:alert-circle-outline"}
              @input=${e => this._editingPenalty = { ...p, icon: e.target.value }} />
          </div>
        </div>
        <div class="form-row full">
          <div class="form-field">
            <label>Description (optional)</label>
            <input type="text" .value=${p.description || ""}
              @input=${e => this._editingPenalty = { ...p, description: e.target.value }} />
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-cancel" @click=${this._cancelEdit}>Cancel</button>
          <button class="btn-save" @click=${this._saveEdit}>Save</button>
        </div>
      </div>
    `;
  }

  _renderNewForm() {
    const f = this._newForm;
    return html`
      <div class="edit-form">
        <div class="form-row">
          <div class="form-field" style="flex:2">
            <label>Name</label>
            <input type="text" placeholder="e.g. Not going to bed" .value=${f.name}
              @input=${e => this._newForm = { ...f, name: e.target.value }} />
          </div>
          <div class="form-field" style="flex:1">
            <label>Points</label>
            <input type="number" min="1" placeholder="10" .value=${f.points}
              @input=${e => this._newForm = { ...f, points: e.target.value }} />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>Icon (MDI)</label>
            <input type="text" .value=${f.icon}
              @input=${e => this._newForm = { ...f, icon: e.target.value }} />
          </div>
        </div>
        <div class="form-row full">
          <div class="form-field">
            <label>Description (optional)</label>
            <input type="text" placeholder="Short description"
              @input=${e => this._newForm = { ...f, description: e.target.value }} />
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-cancel" @click=${() => this._showNewForm = false}>Cancel</button>
          <button class="btn-save" @click=${this._saveNew}>Add Penalty</button>
        </div>
      </div>
    `;
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const penalties = this._getPenalties();
    const visible = this._getVisiblePenalties();
    const child = this._getSelectedChild();

    return html`
      <ha-card>
        <div class="card-header">
          <div class="header-left">
            <ha-icon class="header-icon" icon="mdi:alert-circle-outline"></ha-icon>
            <span class="header-title">${this.config.title || "Penalties"}</span>
          </div>
          <div class="header-actions">
            ${penalties.length ? html`
              <span class="penalty-count">${penalties.length}</span>
            ` : ""}
            <button class="icon-btn ${this._editMode ? "active" : ""}" title="Manage penalties"
                    @click=${() => { this._editMode = !this._editMode; this._editingPenalty = null; this._showNewForm = false; }}>
              <ha-icon icon="mdi:pencil"></ha-icon>
            </button>
          </div>
        </div>

        ${this._renderChildTabs()}

        <div class="card-content">
          ${visible.length === 0 && !this._showNewForm ? html`
            <div class="empty-state">
              <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
              <div class="empty-title">No penalties yet</div>
              <div class="empty-sub">Tap the pencil icon to add penalties</div>
            </div>
          ` : ""}

          ${visible.map(p => this._renderPenaltyRow(p))}

          ${this._editMode ? html`
            ${this._showNewForm
              ? this._renderNewForm()
              : html`
                <button class="add-penalty-btn" @click=${this._openNewForm}>
                  <ha-icon icon="mdi:plus"></ha-icon>
                  New Penalty
                </button>
              `}
          ` : ""}

          ${child && !this._editMode ? html`
            <div style="text-align:center; font-size:0.8rem; color:var(--text-secondary); padding-top:4px;">
              Applying to <strong>${child.name}</strong>
              &mdash; current balance: <strong>${child.points} ${this._getPointsName()}</strong>
            </div>
          ` : ""}
        </div>
      </ha-card>

      ${this._toast ? html`<div class="toast">${this._toast}</div>` : ""}
    `;
  }
}

customElements.define("taskmate-penalties-card", TaskMatePenaltiesCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-penalties-card",
  name: "TaskMate Penalties",
  description: "Apply point-deduction penalties to children",
  preview: false,
});
