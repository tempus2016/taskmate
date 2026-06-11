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

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

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
    const entityId = this.config?.entity || "sensor.taskmate_overview";
    if (window.__taskmate_attrs) {
      return window.__taskmate_attrs(this.hass, entityId);
    }
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
    return this._getAttrs().points_name || this._t("common.stars");
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
      this._showToast(this._t('penalties.toast_applied', { points: penalty.points, pointsName: this._getPointsName(), childName: child.name }));
      // Flash the row
      const row = this.shadowRoot.querySelector(`[data-penalty-id="${penalty.id}"]`);
      if (row) {
        row.classList.add("flashing");
        setTimeout(() => row.classList.remove("flashing"), 700);
      }
    } catch (e) {
      this._showToast(this._t('penalties.toast_apply_failed'));
    } finally {
      this._loading = { ...this._loading, [key]: false };
    }
  }

  _showToast(msg) {
    this._toast = null;
    clearTimeout(this._toastTimer);
    // Force re-render with new toast
    this._toastTimer = setTimeout(() => {
      this._toast = msg;
      this._toastTimer = setTimeout(() => { this._toast = null; }, 2700);
    }, 10);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    clearTimeout(this._toastTimer);
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
      this._showToast(this._t('penalties.toast_save_failed'));
    }
  }

  async _deletePenalty(id) {
    try {
      await this.hass.callService("taskmate", "remove_penalty", { penalty_id: id });
    } catch (e) {
      this._showToast(this._t('penalties.toast_delete_failed'));
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
      this._showToast(this._t('penalties.toast_add_failed'));
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
            <button class="edit-btn" title="${this._t('penalties.btn_edit_title')}" aria-label="${this._t('penalties.btn_edit_title')}" @click=${() => this._startEdit(p)}>
              <ha-icon icon="mdi:pencil"></ha-icon>
            </button>
            <button class="edit-btn delete" title="${this._t('penalties.btn_delete_title')}" aria-label="${this._t('penalties.btn_delete_title')}" @click=${() => this._deletePenalty(p.id)}>
              <ha-icon icon="mdi:trash-can-outline"></ha-icon>
            </button>
          </div>
        ` : html`
          <button class="apply-btn"
                  ?disabled=${isLoading || !child}
                  @click=${() => this._applyPenalty(p)}>
            ${isLoading
              ? html`<ha-icon icon="mdi:loading" class="spin"></ha-icon>`
              : html`<ha-icon icon="mdi:minus-circle-outline"></ha-icon> ${this._t('common.apply')}`
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
            <label>${this._t('penalties.form_name_label')}</label>
            <input type="text" .value=${p.name}
              @input=${e => this._editingPenalty = { ...p, name: e.target.value }} />
          </div>
          <div class="form-field" style="flex:1">
            <label>${this._t('penalties.form_points_label')}</label>
            <input type="number" min="1" .value=${p.points}
              @input=${e => this._editingPenalty = { ...p, points: e.target.value }} />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>${this._t('penalties.form_icon_label')}</label>
            <input type="text" .value=${p.icon || "mdi:alert-circle-outline"}
              @input=${e => this._editingPenalty = { ...p, icon: e.target.value }} />
          </div>
        </div>
        <div class="form-row full">
          <div class="form-field">
            <label>${this._t('penalties.form_description_label')}</label>
            <input type="text" .value=${p.description || ""}
              @input=${e => this._editingPenalty = { ...p, description: e.target.value }} />
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-cancel" @click=${this._cancelEdit}>${this._t('common.cancel')}</button>
          <button class="btn-save" @click=${this._saveEdit}>${this._t('common.save')}</button>
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
            <label>${this._t('penalties.form_name_label')}</label>
            <input type="text" placeholder="${this._t('penalties.form_name_placeholder')}" .value=${f.name}
              @input=${e => this._newForm = { ...f, name: e.target.value }} />
          </div>
          <div class="form-field" style="flex:1">
            <label>${this._t('penalties.form_points_label')}</label>
            <input type="number" min="1" placeholder="10" .value=${f.points}
              @input=${e => this._newForm = { ...f, points: e.target.value }} />
          </div>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>${this._t('penalties.form_icon_label')}</label>
            <input type="text" .value=${f.icon}
              @input=${e => this._newForm = { ...f, icon: e.target.value }} />
          </div>
        </div>
        <div class="form-row full">
          <div class="form-field">
            <label>${this._t('penalties.form_description_label')}</label>
            <input type="text" placeholder="${this._t('penalties.form_description_placeholder')}"
              @input=${e => this._newForm = { ...f, description: e.target.value }} />
          </div>
        </div>
        <div class="form-actions">
          <button class="btn-cancel" @click=${() => this._showNewForm = false}>${this._t('common.cancel')}</button>
          <button class="btn-save" @click=${this._saveNew}>${this._t('penalties.add_penalty')}</button>
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
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, '#e74c3c')}; }</style>
        <div class="card-header">
          <div class="header-left">
            <ha-icon class="header-icon" icon="mdi:alert-circle-outline"></ha-icon>
            <span class="header-title">${this.config.title || this._t('penalties.default_title')}</span>
          </div>
          <div class="header-actions">
            ${penalties.length ? html`
              <span class="penalty-count">${penalties.length}</span>
            ` : ""}
            <button class="icon-btn ${this._editMode ? "active" : ""}" title="${this._t('penalties.manage_title')}"
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
              <div class="empty-title">${this._t('penalties.empty_title')}</div>
              <div class="empty-sub">${this._t('penalties.empty_sub')}</div>
            </div>
          ` : ""}

          ${visible.map(p => this._renderPenaltyRow(p))}

          ${this._editMode ? html`
            ${this._showNewForm
              ? this._renderNewForm()
              : html`
                <button class="add-penalty-btn" @click=${this._openNewForm}>
                  <ha-icon icon="mdi:plus"></ha-icon>
                  ${this._t('penalties.new_penalty')}
                </button>
              `}
          ` : ""}

          ${child && !this._editMode ? html`
            <div style="text-align:center; font-size:0.8rem; color:var(--text-secondary); padding-top:4px;">
              ${this._t('penalties.applying_to', { childName: child.name, points: child.points, pointsName: this._getPointsName() })}
            </div>
          ` : ""}
        </div>
      </ha-card>

      ${this._toast ? html`<div class="toast">${this._toast}</div>` : ""}
    `;
  }
}

class TaskMatePenaltiesCardEditor extends LitElement {
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
      .info-note { font-size: 0.85rem; color: var(--secondary-text-color); background: var(--secondary-background-color, #f5f5f5); border-radius: 8px; padding: 10px 14px; line-height: 1.4; margin-bottom: 16px; display: flex; gap: 10px; align-items: flex-start; }
      .info-note ha-icon { flex-shrink: 0; color: var(--primary-color); --mdc-icon-size: 20px; margin-top: 1px; }
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
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      title: this._t('common.editor.card_title'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
    };
    return html`
      <div class="info-note">
        <ha-icon icon="mdi:information-outline"></ha-icon>
        <span>${this._t('penalties.editor.manage_note')}</span>
      </div>
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${this._buildSchema()}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}
      ></ha-form>
      ${this._renderColourPicker('header_color', '#e74c3c')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, '#e67e22', '#27ae60', '#3498db', '#9b59b6', '#f1c40f', '#34495e'];
    const isActive = (c) => c.toLowerCase() === current.toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${this._t('common.editor.header_colour')}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current}
              @input=${(e) => this._update(key, e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current}"></span>
          </label>
          <span class="colour-hex">${current}</span>
          <div class="colour-presets">
            ${presets.map((p) => html`
              <button class="preset-swatch ${isActive(p) ? 'active' : ''}"
                style="background:${p}"
                title=${p}
                @click=${(e) => { e.preventDefault(); this._update(key, p); }}
              ></button>
            `)}
          </div>
          <button class="colour-reset"
            @click=${(e) => { e.preventDefault(); this._update(key, defaultValue); }}
          >${this._t('common.reset')}</button>
        </div>
        <div class="colour-helper">${this._t('common.editor.header_colour_helper')}</div>
      </div>
    `;
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === '' || value === null || value === undefined) delete newConfig[key];
      else newConfig[key] = value;
    }
    this._fire(newConfig);
  }

  _update(key, value) {
    this._fire({ ...this.config, [key]: value });
  }

  _fire(config) {
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
  }
}

customElements.define("taskmate-penalties-card", TaskMatePenaltiesCard);
customElements.define("taskmate-penalties-card-editor", TaskMatePenaltiesCardEditor);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-penalties-card",
  name: "TaskMate Penalties",
  description: "Apply point-deduction penalties to children",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-penalties-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE PENALTIES CARD %c v" + _tmVersion + " ",
  "background:#922b21;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
