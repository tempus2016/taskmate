/**
 * TaskMate Points Card
 * A parent-friendly Lovelace card for managing children's points/stars.
 * Allows adding or removing points with optional reasons.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const DESIGN_HEADER = "#8e44ad";

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMatePointsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _loading: { type: Object },
      _dialog: { type: Object },
      _notification: { type: Object },
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
    this._loading = {};
    this._dialog = null;
    this._notification = null;
    this._notificationTimer = null;
  }

  static get styles() {
    const base = css`
      :host {
        display: block;
        --card-primary-color: var(--primary-color, #5c6bc0);
        --card-success-color: var(--success-color, #4caf50);
        --card-error-color: var(--error-color, #db4437);
        --card-warning-color: var(--warning-color, #ff9800);
        --text-primary: var(--primary-text-color, #212121);
        --text-secondary: var(--secondary-text-color, #757575);
      }

      ha-card {
        overflow: hidden;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, var(--primary-color));
        color: var(--text-primary-color, #fff);
      }

      .header-content {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .header-icon {
        --mdc-icon-size: 32px;
        opacity: 0.9;
      }

      .header-title {
        font-size: 1.3rem;
        font-weight: 500;
      }

      .card-content {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      /* Child row styles */
      .child-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 16px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 12px;
        transition: box-shadow 0.2s ease;
      }

      .child-row:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      .child-row.loading {
        opacity: 0.6;
        pointer-events: none;
      }

      .child-info {
        display: flex;
        align-items: center;
        gap: 12px;
        flex: 1;
        min-width: 0;
      }

      .child-avatar {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        background: var(--card-primary-color);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .child-avatar ha-icon {
        --mdc-icon-size: 28px;
        color: var(--text-primary-color, #fff);
      }

      .child-details {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }

      .child-name {
        font-weight: 500;
        font-size: 1.1rem;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .child-points {
        display: flex;
        align-items: center;
        gap: 4px;
        font-size: 0.95rem;
        color: var(--card-warning-color);
        font-weight: 600;
      }

      .child-points ha-icon {
        --mdc-icon-size: 18px;
        color: #ca8a04;
      }

      /* Action buttons */
      .action-buttons {
        display: flex;
        gap: 8px;
        flex-shrink: 0;
      }

      .action-button {
        width: 44px;
        height: 44px;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        font-size: 1.5rem;
        font-weight: bold;
      }

      .action-button:hover {
        transform: scale(1.1);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
      }

      .action-button:active {
        transform: scale(0.95);
      }

      .action-button.remove {
        background: var(--error-color, #db4437);
        color: var(--text-primary-color, #fff);
      }

      .action-button.add {
        background: var(--success-color, #4caf50);
        color: var(--text-primary-color, #fff);
      }

      .action-button ha-icon {
        --mdc-icon-size: 24px;
      }

      .action-button.loading {
        opacity: 0.6;
        cursor: not-allowed;
      }

      /* Quick point buttons */
      .quick-buttons {
        display: flex;
        flex-direction: column;
        gap: 6px;
        flex-shrink: 0;
      }

      .quick-buttons-row {
        display: flex;
        gap: 5px;
        align-items: center;
        justify-content: flex-end;
      }

      .quick-btn {
        border: none;
        border-radius: 8px;
        padding: 5px 9px;
        font-size: 0.78rem;
        font-weight: 700;
        cursor: pointer;
        transition: transform 0.12s ease, box-shadow 0.12s ease;
        white-space: nowrap;
        min-width: 36px;
        text-align: center;
        line-height: 1.4;
      }

      .quick-btn:hover {
        transform: scale(1.08);
        box-shadow: 0 2px 8px rgba(0,0,0,0.18);
      }

      .quick-btn:active { transform: scale(0.95); }

      .quick-btn.add {
        background: var(--success-color, #4caf50);
        color: var(--text-primary-color, #fff);
      }

      .quick-btn.remove {
        background: var(--error-color, #db4437);
        color: var(--text-primary-color, #fff);
      }

      .quick-btn.custom {
        background: var(--secondary-background-color, #f5f5f5);
        color: var(--primary-text-color);
        border: 1px solid var(--divider-color, #e0e0e0);
        font-size: 0.72rem;
      }

      .quick-btn.custom:hover {
        background: var(--divider-color, #e0e0e0);
      }

      .quick-row-label {
        font-size: 0.65rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--secondary-text-color);
        text-align: right;
        margin-bottom: 1px;
      }

      /* Dialog overlay */
      .dialog-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        animation: fade-in 0.2s ease;
      }

      @keyframes fade-in {
        from { opacity: 0; }
        to { opacity: 1; }
      }

      .dialog-content {
        background: var(--card-background-color, white);
        border-radius: 16px;
        padding: 24px;
        min-width: 0;
        max-width: min(400px, calc(100vw - 24px));
        box-shadow: var(--ha-card-box-shadow, 0 8px 32px rgba(0, 0, 0, 0.2));
        animation: slide-up 0.3s ease;
      }

      @keyframes slide-up {
        from {
          transform: translateY(20px);
          opacity: 0;
        }
        to {
          transform: translateY(0);
          opacity: 1;
        }
      }

      .dialog-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
      }

      .dialog-header .icon-container {
        width: 48px;
        height: 48px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .dialog-header .icon-container.add {
        background: var(--success-color, #4caf50);
      }

      .dialog-header .icon-container.remove {
        background: var(--error-color, #db4437);
      }

      .dialog-header .icon-container ha-icon {
        --mdc-icon-size: 28px;
        color: var(--text-primary-color, #fff);
      }

      .dialog-header-text {
        flex: 1;
      }

      .dialog-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 2px;
      }

      .dialog-subtitle {
        font-size: 0.9rem;
        color: var(--text-secondary);
      }

      .dialog-form {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .form-group {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .form-group label {
        font-size: 0.9rem;
        font-weight: 500;
        color: var(--text-secondary);
      }

      .form-group input,
      .form-group textarea {
        padding: 12px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        font-size: 1rem;
        background: var(--card-background-color, white);
        color: var(--text-primary);
        transition: border-color 0.2s ease;
      }

      .form-group input:focus,
      .form-group textarea:focus {
        outline: none;
        border-color: var(--card-primary-color);
      }

      .form-group input[type="number"] {
        font-size: 1.3rem;
        font-weight: 600;
        text-align: center;
      }

      .form-group textarea {
        resize: vertical;
        min-height: 60px;
      }

      .points-label {
        font-size: 0.85rem;
        color: var(--text-secondary);
        text-align: center;
        margin-top: 4px;
      }

      .dialog-actions {
        display: flex;
        gap: 12px;
        margin-top: 8px;
      }

      .dialog-button {
        flex: 1;
        padding: 12px 16px;
        border: none;
        border-radius: 8px;
        font-size: 1rem;
        font-weight: 500;
        cursor: pointer;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
      }

      .dialog-button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      }

      .dialog-button:active {
        transform: translateY(0);
      }

      .dialog-button.cancel {
        background: var(--secondary-background-color, #f5f5f5);
        color: var(--text-secondary);
      }

      .dialog-button.confirm {
        color: var(--text-primary-color, #fff);
      }

      .dialog-button.confirm.add {
        background: var(--success-color, #4caf50);
      }

      .dialog-button.confirm.remove {
        background: var(--error-color, #db4437);
      }

      .dialog-button.loading {
        opacity: 0.6;
        cursor: not-allowed;
      }

      /* Notification toast */
      .notification {
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        max-width: calc(100vw - 24px);
        white-space: normal;
        padding: 12px 24px;
        border-radius: 8px;
        color: var(--text-primary-color, #fff);
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 8px;
        box-shadow: var(--ha-card-box-shadow, 0 4px 16px rgba(0, 0, 0, 0.2));
        z-index: 10000;
        animation: slide-up-notification 0.3s ease;
      }

      @keyframes slide-up-notification {
        from {
          transform: translate(-50%, 20px);
          opacity: 0;
        }
        to {
          transform: translate(-50%, 0);
          opacity: 1;
        }
      }

      .notification.success {
        background: var(--success-color, #4caf50);
      }

      .notification.error {
        background: var(--error-color, #db4437);
      }

      .notification ha-icon {
        --mdc-icon-size: 20px;
      }

      /* Empty state */
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        color: var(--text-secondary);
        text-align: center;
      }

      .empty-state ha-icon {
        --mdc-icon-size: 48px;
        margin-bottom: 16px;
        opacity: 0.5;
      }

      .empty-state .message {
        font-size: 1.1rem;
        margin-bottom: 4px;
      }

      .empty-state .submessage {
        font-size: 0.9rem;
        opacity: 0.8;
      }

      /* Error state */
      .error-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        color: var(--card-error-color);
        text-align: center;
      }

      .error-state ha-icon {
        --mdc-icon-size: 48px;
        margin-bottom: 16px;
      }

      /* Responsive adjustments */
      @media (max-width: 400px) {
        .child-row {
          padding: 10px 12px;
        }

        .child-avatar {
          width: 40px;
          height: 40px;
        }

        .child-avatar ha-icon {
          --mdc-icon-size: 24px;
        }

        .child-name {
          font-size: 1rem;
        }

        .action-button {
          width: 38px;
          height: 38px;
        }

        .action-button ha-icon {
          --mdc-icon-size: 20px;
        }

        .dialog-content {
          min-width: 280px;
          padding: 20px;
        }
      }

      /* ── Designed styles (playroom / console / cleanpro) ── */
      /* Shared .tmd kit + tokens come from taskmate-design.js styles(). */
      .pc-grid { display: flex; flex-direction: column; gap: 10px; }
      .pc-row {
        display: flex;
        align-items: center;
        gap: 11px;
        background: var(--tmd-surface-2);
        border-radius: 18px;
        padding: 11px 13px;
      }
      .pc-row.loading { opacity: 0.55; pointer-events: none; }
      .pc-mid { flex: 1; min-width: 0; }
      .pc-name { font-weight: 800; font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .pc-pts { font-family: var(--tmd-font-display); font-weight: 800; font-size: 22px; line-height: 1; color: var(--tmd-accent); }
      .pc-pts span { font-size: 12px; margin-left: 2px; }
      .pc-sub { font-size: 11px; }

      /* Console list variant */
      .cn-row { border: 1px solid var(--tmd-border); border-radius: 10px; padding: 10px 11px; }
      .cn-name { font-weight: 700; }
      .cn-cur { font-size: 11px; }

      /* Clean Pro flat-row variant */
      .cp-grid { display: flex; flex-direction: column; }
      .cp-row { background: transparent; border-radius: 0; padding: 11px 2px; }
      .cp-row + .cp-row { border-top: 1px solid var(--tmd-border); }
      .cp-name { flex: 1; min-width: 0; font-weight: 600; }
      .cp-num { width: 46px; text-align: right; font-size: 16px; }

      .pc-quick { gap: 7px; flex-wrap: wrap; }
      .pc-reason { margin-top: 12px; cursor: pointer; }
      .pc-reason.con { gap: 8px; }

      /* Per-child quick add/remove chips (all designed styles) */
      .pc-actions { display: flex; flex-direction: column; gap: 5px; align-items: flex-end; flex-shrink: 0; }
      .pc-qrow { display: flex; gap: 4px; align-items: center; justify-content: flex-end; flex-wrap: wrap; }
      .pc-qchip {
        font: inherit;
        font-family: var(--tmd-font-display);
        font-weight: 800;
        font-size: 12px;
        line-height: 1.3;
        border: 0;
        cursor: pointer;
        padding: 4px 9px;
        min-width: 30px;
        text-align: center;
        border-radius: 999px;
        color: #fff;
      }
      .pc-qchip:disabled { opacity: 0.5; cursor: not-allowed; }
      .pc-qchip.add { background: var(--tmd-good); }
      .pc-qchip.remove { background: var(--tmd-bad); }
      :host([data-tm-design="console"]) .pc-qchip.add {
        color: #06301f;
        box-shadow: 0 0 10px color-mix(in srgb, var(--tmd-good) 45%, transparent);
      }
      :host([data-tm-design="console"]) .pc-qchip.remove {
        color: #3a0d0d;
        box-shadow: 0 0 10px color-mix(in srgb, var(--tmd-bad) 45%, transparent);
      }
      .pc-qchip.more {
        background: var(--tmd-surface-2);
        color: var(--tmd-text);
        border: 1px solid var(--tmd-border);
        padding: 4px 8px;
      }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity (taskmate overview sensor)");
    }
    this.config = {
      title: "Manage Points",
    ...config,
    };
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("taskmate-points-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.taskmate_overview",
      title: "Manage Points",
    };
  }

  render() {
    if (!this.hass || !this.config) {
      return html``;
    }

    const entity = this.hass.states[this.config.entity];

    if (!entity) {
      return html`
        <ha-card>
          <div class="error-state">
            <ha-icon icon="mdi:alert-circle"></ha-icon>
            <div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div>
          </div>
        </ha-card>
      `;
    }

    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`
        <ha-card>
          <div class="error-state">
            <ha-icon icon="mdi:alert-circle"></ha-icon>
            <div>${this._t('common.unavailable')}</div>
          </div>
        </ha-card>
      `;
    }

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t("common.stars");

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") {
      return this._renderDesigned(design, children, pointsName, pointsIcon);
    }

    const _hc = _safeColor(this.config.header_color, '');
    const headerStyle = _hc
      ? `--taskmate-header-bg: ${_hc};`
      : '';

    return html`
      <ha-card>
        ${headerStyle ? html`<style>:host { ${headerStyle} }</style>` : ''}
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="${pointsIcon}"></ha-icon>
            <span class="header-title">${this.config.title || this._t('points_card.default_title')}</span>
          </div>
        </div>

        <div class="card-content">
          ${children.length === 0
            ? this._renderEmptyState()
            : children.map((child) =>
                this._renderChildRow(child, pointsIcon, pointsName)
              )}
        </div>

        ${this._dialog ? this._renderDialog() : ""}
        ${this._notification ? this._renderNotification() : ""}
      </ha-card>
    `;
  }

  _renderEmptyState() {
    return html`
      <div class="empty-state">
        <ha-icon icon="mdi:account-group"></ha-icon>
        <div class="message">${this._t('points_card.empty_title')}</div>
        <div class="submessage">${this._t('points_card.empty_subtitle')}</div>
      </div>
    `;
  }

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns (frag/02-points.html).
     Classic branch above is untouched; these only ADD an alternate render.
  ══════════════════════════════════════════════════════════════════════ */

  _designTone(i) { return `var(--tmd-c${(i % 6) + 1})`; }

  _childAvatarValue(child) {
    const childEntityId = Object.keys(this.hass.states).find(
      (eid) => this.hass.states[eid].attributes?.child_id === child.id
    );
    const childEntity = childEntityId ? this.hass.states[childEntityId] : null;
    return childEntity?.attributes?.avatar || "mdi:account-circle";
  }

  _av(child, tone, size) {
    const a = this._childAvatarValue(child);
    const inner = a.startsWith("mdi:")
      ? html`<ha-icon icon="${a}"></ha-icon>`
      : a
        ? html`<img src="${a}" alt="${child.name}">`
        : (child.name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
    return html`<div class="av" style="--av:${size}px;--ac:${tone}">${inner}</div>`;
  }

  _renderDesigned(design, children, pointsName, pointsIcon) {
    const hd = _safeColor(this.config.header_color, DESIGN_HEADER);

    const header = design === "console"
      ? html`<div class="tmd-hd">
          <span class="ic">⚡</span>
          <span class="tt">${this.config.title || this._t('points_card.default_title')}</span>
          ${children.length ? html`<span class="pill">${children.length}</span>` : ""}
        </div>`
      : html`<div class="tmd-hd">
          <span class="ic">${design === "cleanpro" ? "±" : "✨"}</span>
          <span class="tt">${this.config.title || this._t('points_card.default_title')}</span>
        </div>`;

    const body = children.length === 0
      ? html`<div class="tmd-empty">${this._t('points_card.empty_title')}</div>`
      : design === "console"  ? this._designConsole(children, pointsName, pointsIcon)
      : design === "cleanpro" ? this._designCleanpro(children, pointsName, pointsIcon)
      :                         this._designPlayroom(children, pointsName, pointsIcon);

    return html`
      <ha-card class="tmd" style="--hd:${hd}">
        ${header}
        <div class="tmd-bd">${body}</div>
        ${this._dialog ? this._renderDialog() : ""}
        ${this._notification ? this._renderNotification() : ""}
      </ha-card>`;
  }

  /**
   * Per-child quick add/remove buttons, honouring quick_add_amounts,
   * quick_remove_amounts and show_dialog. Mirrors the classic _renderChildRow
   * quick-button block (same handlers: _quickAdjust + _openDialog).
   */
  _designQuickActions(child, pointsName, pointsIcon, isLoading) {
    const addAmounts = Array.isArray(this.config.quick_add_amounts)
      ? this.config.quick_add_amounts : [1, 5, 10];
    const removeAmounts = Array.isArray(this.config.quick_remove_amounts)
      ? this.config.quick_remove_amounts : [1, 5, 10];
    const showDialog = this.config.show_dialog !== false;
    return html`
      <div class="pc-actions">
        <div class="pc-qrow">
          ${addAmounts.map(amt => html`
            <button class="pc-qchip add" ?disabled="${isLoading}"
              @click="${(e) => { e.stopPropagation(); this._quickAdjust(child, 'add', amt); }}"
              title="${this._t('points_card.quick_add_title', { amount: amt, pointsName })}">+${amt}</button>`)}
          ${showDialog ? html`
            <button class="pc-qchip more" ?disabled="${isLoading}"
              @click="${(e) => { e.stopPropagation(); this._openDialog(child, 'add', pointsIcon, pointsName); }}"
              title="${this._t('points_card.quick_custom_title')}">⋯</button>` : ""}
        </div>
        <div class="pc-qrow">
          ${removeAmounts.map(amt => html`
            <button class="pc-qchip remove" ?disabled="${isLoading}"
              @click="${(e) => { e.stopPropagation(); this._quickAdjust(child, 'remove', amt); }}"
              title="${this._t('points_card.quick_remove_title', { amount: amt, pointsName })}">−${amt}</button>`)}
          ${showDialog ? html`
            <button class="pc-qchip more" ?disabled="${isLoading}"
              @click="${(e) => { e.stopPropagation(); this._openDialog(child, 'remove', pointsIcon, pointsName); }}"
              title="${this._t('points_card.quick_custom_title')}">⋯</button>` : ""}
        </div>
      </div>`;
  }

  _designPlayroom(children, pointsName, pointsIcon) {
    return html`
      <div class="pc-grid">
        ${children.map((child, i) => {
          const tone = this._designTone(i);
          const isLoading = this._loading[child.id];
          return html`
            <div class="pc-row ${isLoading ? "loading" : ""}" style="--ac:${tone}">
              ${this._av(child, tone, 46)}
              <div class="pc-mid">
                <div class="pc-name">${child.name}</div>
                <div class="pc-pts">${child.points}<span>⭐</span></div>
              </div>
              ${this._designQuickActions(child, pointsName, pointsIcon, isLoading)}
            </div>`;
        })}
      </div>`;
  }

  _designConsole(children, pointsName, pointsIcon) {
    return html`
      <div class="pc-grid">
        ${children.map((child, i) => {
          const tone = this._designTone(i);
          const isLoading = this._loading[child.id];
          return html`
            <div class="pc-row cn-row ${isLoading ? "loading" : ""}" style="--ac:${tone}">
              ${this._av(child, tone, 36)}
              <div class="pc-mid">
                <div class="cn-name">${child.name}</div>
                <div class="num muted cn-cur">${(child.points + ' ' + pointsName).toUpperCase()}</div>
              </div>
              ${this._designQuickActions(child, pointsName, pointsIcon, isLoading)}
            </div>`;
        })}
      </div>`;
  }

  _designCleanpro(children, pointsName, pointsIcon) {
    return html`
      <div class="pc-grid cp-grid">
        ${children.map((child, i) => {
          const tone = this._designTone(i);
          const isLoading = this._loading[child.id];
          return html`
            <div class="pc-row cp-row ${isLoading ? "loading" : ""}" style="--ac:${tone}">
              ${this._av(child, tone, 38)}
              <div class="cp-name">${child.name}</div>
              <div class="num cp-num">${child.points}</div>
              ${this._designQuickActions(child, pointsName, pointsIcon, isLoading)}
            </div>`;
        })}
      </div>`;
  }

  _renderChildRow(child, pointsIcon, pointsName) {
    const isLoading = this._loading[child.id];

    // Get child entity for avatar
    const childEntityId = Object.keys(this.hass.states).find(
      (eid) => this.hass.states[eid].attributes?.child_id === child.id
    );
    const childEntity = childEntityId ? this.hass.states[childEntityId] : null;
    const avatar = childEntity?.attributes?.avatar || "mdi:account-circle";

    return html`
      <div class="child-row ${isLoading ? "loading" : ""}">
        <div class="child-info">
          <div class="child-avatar">
            <ha-icon icon="${avatar}"></ha-icon>
          </div>
          <div class="child-details">
            <div class="child-name">${child.name}</div>
            <div class="child-points">
              <ha-icon icon="${pointsIcon}"></ha-icon>
              ${child.points} ${pointsName}
            </div>
          </div>
        </div>
        <div class="quick-buttons">
          ${(() => {
            const addAmounts = Array.isArray(this.config.quick_add_amounts)
              ? this.config.quick_add_amounts : [1, 5, 10];
            const removeAmounts = Array.isArray(this.config.quick_remove_amounts)
              ? this.config.quick_remove_amounts : [1, 5, 10];
            return html`
              <div class="quick-row-label">${this._t('points_card.quick_label_add', { pointsName })}</div>
              <div class="quick-buttons-row">
                ${addAmounts.map(amt => html`
                  <button class="quick-btn add" ?disabled="${isLoading}"
                    @click="${(e) => { e.stopPropagation(); this._quickAdjust(child, 'add', amt); }}"
                    title="${this._t('points_card.quick_add_title', { amount: amt, pointsName })}">+${amt}</button>
                `)}
                ${this.config.show_dialog !== false ? html`
                  <button class="quick-btn custom" ?disabled="${isLoading}"
                    @click="${() => this._openDialog(child, 'add', pointsIcon, pointsName)}"
                    title="${this._t('points_card.quick_custom_title')}">&#x22EF;</button>
                ` : ''}
              </div>
              <div class="quick-row-label">${this._t('points_card.quick_label_remove', { pointsName })}</div>
              <div class="quick-buttons-row">
                ${removeAmounts.map(amt => html`
                  <button class="quick-btn remove" ?disabled="${isLoading}"
                    @click="${(e) => { e.stopPropagation(); this._quickAdjust(child, 'remove', amt); }}"
                    title="${this._t('points_card.quick_remove_title', { amount: amt, pointsName })}">&#x2212;${amt}</button>
                `)}
                ${this.config.show_dialog !== false ? html`
                  <button class="quick-btn custom" ?disabled="${isLoading}"
                    @click="${() => this._openDialog(child, 'remove', pointsIcon, pointsName)}"
                    title="${this._t('points_card.quick_custom_title')}">&#x22EF;</button>
                ` : ''}
              </div>
            `;
          })()}
        </div>
      </div>
    `;
  }

  _renderDialog() {
    const { child, action, pointsName } = this._dialog;
    const isAdd = action === "add";
    const isLoading = this._loading[`dialog_${child.id}`];

    return html`
      <div class="dialog-overlay" @click="${this._closeDialog}">
        <div class="dialog-content" @click="${(e) => e.stopPropagation()}">
          <div class="dialog-header">
            <div class="icon-container ${action}">
              <ha-icon icon="${isAdd ? "mdi:plus" : "mdi:minus"}"></ha-icon>
            </div>
            <div class="dialog-header-text">
              <div class="dialog-title">
                ${isAdd ? this._t('points_card.dialog_add_title', { pointsName }) : this._t('points_card.dialog_remove_title', { pointsName })}
              </div>
              <div class="dialog-subtitle">${this._t('points_card.dialog_subtitle', { childName: child.name })}</div>
            </div>
          </div>

          <div class="dialog-form">
            <div class="form-group">
              <ha-textfield
                id="points-input"
                label="${this._t('points_card.dialog_points_label', { pointsName })}"
                type="number"
                min="1"
                max="100"
                value="1"
                style="width:100%;"
                helper="${this._t('points_card.dialog_points_helper')}"
                helperPersistent
                @keydown="${(e) => this._handleKeyDown(e, child, action)}"
              ></ha-textfield>
            </div>

            <div class="form-group">
              <ha-textfield
                id="reason-input"
                label="${this._t('points_card.dialog_reason_label')}"
                placeholder="${this._t('points_card.dialog_reason_placeholder')}"
                maxlength="200"
                style="width:100%;"
                @keydown="${(e) => this._handleKeyDown(e, child, action)}"
              ></ha-textfield>
            </div>

            <div class="dialog-actions">
              <button
                class="dialog-button cancel"
                @click="${this._closeDialog}"
                ?disabled="${isLoading}"
              >
                ${this._t('common.cancel')}
              </button>
              <button
                class="dialog-button confirm ${action} ${isLoading ? "loading" : ""}"
                @click="${() => this._confirmAction(child, action)}"
                ?disabled="${isLoading}"
              >
                ${isLoading ? this._t('points_card.dialog_loading') : isAdd ? this._t('points_card.dialog_confirm_add') : this._t('points_card.dialog_confirm_remove')}
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  _renderNotification() {
    const { message, type } = this._notification;

    return html`
      <div class="notification ${type}">
        <ha-icon
          icon="${type === "success" ? "mdi:check-circle" : "mdi:alert-circle"}"
        ></ha-icon>
        ${message}
      </div>
    `;
  }

  async _quickAdjust(child, action, amount) {
    const key = `quick_${child.id}_${action}_${amount}`;
    if (this._loading[key]) return;

    this._loading = { ...this._loading, [key]: true };
    this.requestUpdate();

    const entity = this.hass.states[this.config.entity];
    const pointsName = entity?.attributes?.points_name || this._t('common.points');
    const service = action === 'add' ? 'add_points' : 'remove_points';

    try {
      await this.hass.callService('taskmate', service, {
        child_id: child.id,
        points: amount,
      });
      const sign = action === 'add' ? '+' : '−';
      this._showNotification(this._t('points_card.notification_quick', { sign, amount, pointsName, childName: child.name }), 'success');
    } catch (error) {
      this._showNotification(this._t('points_card.notification_failed', { message: error.message }), 'error');
    } finally {
      this._loading = { ...this._loading, [key]: false };
      this.requestUpdate();
    }
  }

  _openDialog(child, action, pointsIcon, pointsName) {
    if (this._dialogKeyHandler) {
      document.removeEventListener("keydown", this._dialogKeyHandler);
    }
    this._dialog = { child, action, pointsIcon, pointsName };
    this._dialogKeyHandler = (e) => {
      if (e.key === "Escape") this._closeDialog();
    };
    document.addEventListener("keydown", this._dialogKeyHandler);
    this.requestUpdate();

    // Focus the points input after dialog renders
    requestAnimationFrame(() => {
      const input = this.shadowRoot.querySelector("#points-input");
      if (input) {
        input.focus();
        input.select();
      }
    });
  }

  _closeDialog() {
    this._dialog = null;
    if (this._dialogKeyHandler) {
      document.removeEventListener("keydown", this._dialogKeyHandler);
      this._dialogKeyHandler = null;
    }
    this.requestUpdate();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._dialogKeyHandler) {
      document.removeEventListener("keydown", this._dialogKeyHandler);
      this._dialogKeyHandler = null;
    }
    if (this._notificationTimer) {
      clearTimeout(this._notificationTimer);
      this._notificationTimer = null;
    }
  }

  _handleKeyDown(e, child, action) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      this._confirmAction(child, action);
    } else if (e.key === "Escape") {
      this._closeDialog();
    }
  }

  async _confirmAction(child, action) {
    const pointsInput = this.shadowRoot.querySelector("#points-input");
    const reasonInput = this.shadowRoot.querySelector("#reason-input");

    const points = parseInt(pointsInput?.value) || 1;
    const reason = reasonInput?.value?.trim() || undefined;

    // Validate points
    if (points < 1 || points > 100) {
      this._showNotification(this._t('points_card.validation_range'), "error");
      return;
    }

    this._loading = { ...this._loading, [`dialog_${child.id}`]: true };
    this.requestUpdate();

    const service = action === "add" ? "add_points" : "remove_points";
    const serviceData = {
      child_id: child.id,
      points: points,
    };

    if (reason) {
      serviceData.reason = reason;
    }

    try {
      await this.hass.callService("taskmate", service, serviceData);

      // Get points name from entity
      const entity = this.hass.states[this.config.entity];
      const pointsName = entity?.attributes?.points_name || this._t("common.points");
      const pointsLabel = points === 1 ? pointsName.replace(/s$/, "") : pointsName;

      const message =
        action === "add"
          ? this._t('points_card.notification_added', { points, pointsLabel, childName: child.name })
          : this._t('points_card.notification_removed', { points, pointsLabel, childName: child.name });

      this._showNotification(message, "success");
      this._closeDialog();
    } catch (error) {
      console.error(`Failed to ${action} points:`, error);
      this._showNotification(
        this._t('points_card.notification_failed_action', { action, message: error.message }),
        "error"
      );
    } finally {
      this._loading = { ...this._loading, [`dialog_${child.id}`]: false };
      this.requestUpdate();
    }
  }

  _showNotification(message, type) {
    this._notification = { message, type };
    this.requestUpdate();

    // Auto-hide after 3s. Track the timer so it is cleared on re-trigger and
    // on disconnect — avoids requestUpdate() on a detached element (ERR-4).
    if (this._notificationTimer) clearTimeout(this._notificationTimer);
    this._notificationTimer = setTimeout(() => {
      this._notificationTimer = null;
      this._notification = null;
      this.requestUpdate();
    }, 3000);
  }
}

// Card Editor
class TaskMatePointsCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  static get styles() {
    return css`
      :host { display: block; padding: 4px 0; }
      ha-form { display: block; margin-bottom: 16px; }
      .amounts-preview { display: flex; flex-wrap: wrap; gap: 5px; margin: 4px 0 16px; }
      .preview-btn { padding: 3px 9px; border-radius: 6px; font-size: 0.8rem; font-weight: 700; border: none; }
      .preview-btn.add { background: var(--success-color, #4caf50); color: var(--text-primary-color, #fff); }
      .preview-btn.remove { background: var(--error-color, #db4437); color: var(--text-primary-color, #fff); }
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

  _parseAmounts(str, defaults) {
    if (!str) return defaults;
    return str.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n) && n > 0);
  }

  _amountsToString(arr) {
    return Array.isArray(arr) ? arr.join(', ') : '';
  }

  _buildSchema() {
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'card_design',
        selector: {
          select: {
            options: window.__taskmate_design
              ? window.__taskmate_design.editorOptions(this._t.bind(this))
              : [{ value: 'global', label: 'Use global default' }],
            mode: 'dropdown',
          },
        },
      },
      { name: 'quick_add_amounts', selector: { text: {} } },
      { name: 'quick_remove_amounts', selector: { text: {} } },
      { name: 'show_dialog', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('points_card.editor.entity_label'),
      title: this._t('points_card.editor.title_label'),
      card_design: this._t('common.design.field_label'),
      quick_add_amounts: this._t('points_card.editor.add_buttons_label'),
      quick_remove_amounts: this._t('points_card.editor.remove_buttons_label'),
      show_dialog: this._t('points_card.editor.show_dialog_label'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('points_card.editor.entity_helper'),
      quick_add_amounts: this._t('points_card.editor.add_buttons_helper'),
      quick_remove_amounts: this._t('points_card.editor.remove_buttons_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;

    const addAmounts = this.config.quick_add_amounts || [1, 5, 10];
    const removeAmounts = this.config.quick_remove_amounts || [1, 5, 10];

    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      card_design: this.config.card_design || 'global',
      quick_add_amounts: this._amountsToString(addAmounts),
      quick_remove_amounts: this._amountsToString(removeAmounts),
      show_dialog: this.config.show_dialog !== false,
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
      <div class="amounts-preview">
        ${addAmounts.map(a => html`<span class="preview-btn add">+${a}</span>`)}
        ${removeAmounts.map(a => html`<span class="preview-btn remove">−${a}</span>`)}
      </div>
      ${this._renderColourPicker('header_color', '')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const d = window.__taskmate_design;
    const current = this.config[key] || defaultValue;
    if (!d || !d.colourPicker) return html``;
    return d.colourPicker({
      defaultValue, current,
      label: this._t('common.editor.header_colour'),
      helper: this._t('common.editor.header_colour_helper'),
      resetLabel: this._t('common.reset'),
      onInput: (v) => this._updateConfig(key, v),
      onPreset: (v) => this._updateConfig(key, v),
      onReset: () => this._updateConfig(key, defaultValue),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (value === '' || value === null || value === undefined) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (key === 'show_dialog' && value === true) {
        delete newConfig[key];
      } else if (key === 'quick_add_amounts' || key === 'quick_remove_amounts') {
        const parsed = this._parseAmounts(value, null);
        if (parsed && parsed.length) newConfig[key] = parsed;
        else delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === undefined || value === '') delete newConfig[key];
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

// Register the cards
customElements.define("taskmate-points-card", TaskMatePointsCard);
customElements.define(
  "taskmate-points-card-editor",
  TaskMatePointsCardEditor
);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-points-card",
  name: "TaskMate Points Card",
  description: "A parent-friendly card to add or remove points from children",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-points-card", "overview"),
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-points-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE POINTS CARD %c v" + _tmVersion + " ",
  "background:#03a9f4;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
