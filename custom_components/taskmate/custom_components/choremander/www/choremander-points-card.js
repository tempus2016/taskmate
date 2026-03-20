/**
 * Choremander Points Card
 * A parent-friendly Lovelace card for managing children's points/stars.
 * Allows adding or removing points with optional reasons.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class ChoremanderPointsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _loading: { type: Object },
      _dialog: { type: Object },
      _notification: { type: Object },
    };
  }

  constructor() {
    super();
    this._loading = {};
    this._dialog = null;
    this._notification = null;
  }

  static get styles() {
    return css`
      :host {
        display: block;
        --card-primary-color: var(--primary-color, #5c6bc0);
        --card-success-color: var(--success-color, #4caf50);
        --card-error-color: var(--error-color, #f44336);
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
        padding: 16px;
        background: linear-gradient(135deg, var(--card-primary-color) 0%, #7986cb 100%);
        color: white;
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
        background: linear-gradient(135deg, var(--card-primary-color) 0%, #7986cb 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .child-avatar ha-icon {
        --mdc-icon-size: 28px;
        color: white;
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
        color: #ffd700;
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
        background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
        color: white;
      }

      .action-button.add {
        background: linear-gradient(135deg, #66bb6a 0%, #43a047 100%);
        color: white;
      }

      .action-button ha-icon {
        --mdc-icon-size: 24px;
      }

      .action-button.loading {
        opacity: 0.6;
        cursor: not-allowed;
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
        min-width: 300px;
        max-width: 400px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
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
        background: linear-gradient(135deg, #66bb6a 0%, #43a047 100%);
      }

      .dialog-header .icon-container.remove {
        background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
      }

      .dialog-header .icon-container ha-icon {
        --mdc-icon-size: 28px;
        color: white;
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
        color: white;
      }

      .dialog-button.confirm.add {
        background: linear-gradient(135deg, #66bb6a 0%, #43a047 100%);
      }

      .dialog-button.confirm.remove {
        background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
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
        padding: 12px 24px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 8px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
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
        background: linear-gradient(135deg, #66bb6a 0%, #43a047 100%);
      }

      .notification.error {
        background: linear-gradient(135deg, #ef5350 0%, #e53935 100%);
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
    `;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity (choremander overview sensor)");
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
    return document.createElement("choremander-points-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.choremander_overview",
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
            <div>Entity not found: ${this.config.entity}</div>
          </div>
        </ha-card>
      `;
    }

    const children = entity.attributes.children || [];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Stars";

    return html`
      <ha-card>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="${pointsIcon}"></ha-icon>
            <span class="header-title">${this.config.title}</span>
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
        <div class="message">No Children Found</div>
        <div class="submessage">Add children in Choremander settings</div>
      </div>
    `;
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
        <div class="action-buttons">
          <button
            class="action-button remove"
            @click="${() => this._openDialog(child, "remove", pointsIcon, pointsName)}"
            title="Remove ${pointsName}"
            ?disabled="${isLoading}"
          >
            <ha-icon icon="mdi:minus"></ha-icon>
          </button>
          <button
            class="action-button add"
            @click="${() => this._openDialog(child, "add", pointsIcon, pointsName)}"
            title="Add ${pointsName}"
            ?disabled="${isLoading}"
          >
            <ha-icon icon="mdi:plus"></ha-icon>
          </button>
        </div>
      </div>
    `;
  }

  _renderDialog() {
    const { child, action, pointsIcon, pointsName } = this._dialog;
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
                ${isAdd ? "Add" : "Remove"} ${pointsName}
              </div>
              <div class="dialog-subtitle">for ${child.name}</div>
            </div>
          </div>

          <div class="dialog-form">
            <div class="form-group">
              <label>Number of ${pointsName}</label>
              <input
                type="number"
                id="points-input"
                min="1"
                max="100"
                value="1"
                @keydown="${(e) => this._handleKeyDown(e, child, action)}"
              />
              <div class="points-label">Enter 1-100</div>
            </div>

            <div class="form-group">
              <label>Reason (optional)</label>
              <textarea
                id="reason-input"
                placeholder="e.g., Great behavior, Helped a sibling..."
                @keydown="${(e) => this._handleKeyDown(e, child, action)}"
              ></textarea>
            </div>

            <div class="dialog-actions">
              <button
                class="dialog-button cancel"
                @click="${this._closeDialog}"
                ?disabled="${isLoading}"
              >
                Cancel
              </button>
              <button
                class="dialog-button confirm ${action} ${isLoading ? "loading" : ""}"
                @click="${() => this._confirmAction(child, action)}"
                ?disabled="${isLoading}"
              >
                ${isLoading ? "..." : isAdd ? "Add" : "Remove"}
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

  _openDialog(child, action, pointsIcon, pointsName) {
    this._dialog = { child, action, pointsIcon, pointsName };
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
    this.requestUpdate();
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
      this._showNotification("Please enter a number between 1 and 100", "error");
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
      await this.hass.callService("choremander", service, serviceData);

      // Get points name from entity
      const entity = this.hass.states[this.config.entity];
      const pointsName = entity?.attributes?.points_name || "points";
      const pointsLabel = points === 1 ? pointsName.replace(/s$/, "") : pointsName;

      const message =
        action === "add"
          ? `Added ${points} ${pointsLabel} to ${child.name}`
          : `Removed ${points} ${pointsLabel} from ${child.name}`;

      this._showNotification(message, "success");
      this._closeDialog();
    } catch (error) {
      console.error(`Failed to ${action} points:`, error);
      this._showNotification(
        `Failed to ${action} points: ${error.message}`,
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

    // Auto-hide notification after 3 seconds
    setTimeout(() => {
      this._notification = null;
      this.requestUpdate();
    }, 3000);
  }
}

// Card Editor
class ChoremanderPointsCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
    };
  }

  static get styles() {
    return css`
      .form-group {
        margin-bottom: 16px;
      }

      .form-group label {
        display: block;
        margin-bottom: 4px;
        font-weight: 500;
      }

      .form-group input {
        width: 100%;
        padding: 8px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font-size: 1em;
        box-sizing: border-box;
      }

      .form-group input:focus {
        outline: none;
        border-color: var(--primary-color);
      }

      .form-group small {
        display: block;
        margin-top: 4px;
        color: var(--secondary-text-color);
        font-size: 0.85em;
      }
    `;
  }

  setConfig(config) {
    this.config = config;
  }

  render() {
    if (!this.hass || !this.config) {
      return html``;
    }

    return html`
      <div class="form-group">
        <label>Entity</label>
        <input
          type="text"
          .value="${this.config.entity || ""}"
          @input="${this._entityChanged}"
          placeholder="sensor.choremander_overview"
        />
        <small>The Choremander overview sensor entity</small>
      </div>

      <div class="form-group">
        <label>Title</label>
        <input
          type="text"
          .value="${this.config.title || ""}"
          @input="${this._titleChanged}"
          placeholder="Manage Points"
        />
        <small>Card title displayed in the header</small>
      </div>
    `;
  }

  _entityChanged(e) {
    this._updateConfig("entity", e.target.value);
  }

  _titleChanged(e) {
    this._updateConfig("title", e.target.value);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === undefined || value === "") {
      delete newConfig[key];
    }
    const event = new CustomEvent("config-changed", {
      detail: { config: newConfig },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }
}

// Register the cards
customElements.define("choremander-points-card", ChoremanderPointsCard);
customElements.define(
  "choremander-points-card-editor",
  ChoremanderPointsCardEditor
);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "choremander-points-card",
  name: "Choremander Points Card",
  description: "A parent-friendly card to add or remove points from children",
  preview: true,
});

console.info(
  "%c CHOREMANDER-POINTS-CARD %c Loaded ",
  "background: #5c6bc0; color: white; font-weight: bold; border-radius: 4px 0 0 4px;",
  "background: #7986cb; color: white; font-weight: bold; border-radius: 0 4px 4px 0;"
);
