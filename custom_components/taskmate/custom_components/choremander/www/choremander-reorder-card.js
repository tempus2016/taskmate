/**
 * Choremander Reorder Card
 * A Lovelace card for reordering chores per child, organized by time category.
 * Clean, parent-friendly UI for managing chore order.
 *
 * Version: 2.0.0 - Fixed child assignment filtering
 * Last Updated: 2025-12-31
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class ChoremanderReorderCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _saving: { type: Boolean },
      _localChoreOrder: { type: Object },
      _hasChanges: { type: Boolean },
    };
  }

  constructor() {
    super();
    this._saving = false;
    this._localChoreOrder = {};
    this._hasChanges = false;
  }

  static get styles() {
    return css`
      :host {
        display: block;
      }

      ha-card {
        padding: 16px;
      }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--divider-color);
        margin-bottom: 16px;
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .card-title {
        font-size: 1.3em;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .child-name {
        font-size: 1em;
        color: var(--secondary-text-color);
        padding: 4px 12px;
        background: var(--secondary-background-color);
        border-radius: 16px;
      }

      .save-button {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border: none;
        border-radius: 8px;
        padding: 8px 20px;
        font-size: 0.95em;
        font-weight: 500;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
        transition: background 0.2s ease, transform 0.15s ease;
      }

      .save-button:hover:not(:disabled) {
        background: var(--primary-color);
        filter: brightness(1.1);
        transform: scale(1.02);
      }

      .save-button:active:not(:disabled) {
        transform: scale(0.98);
      }

      .save-button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .save-button.has-changes {
        animation: pulse-save 2s ease-in-out infinite;
      }

      @keyframes pulse-save {
        0%, 100% { box-shadow: 0 0 0 0 rgba(var(--rgb-primary-color), 0.4); }
        50% { box-shadow: 0 0 0 8px rgba(var(--rgb-primary-color), 0); }
      }

      .save-button ha-icon {
        --mdc-icon-size: 18px;
      }

      .save-button.saving ha-icon {
        animation: spin 1s linear infinite;
      }

      @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }

      .time-category-section {
        margin-bottom: 24px;
      }

      .time-category-section:last-child {
        margin-bottom: 0;
      }

      .time-category-header {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px;
        background: var(--secondary-background-color);
        border-radius: 10px;
        margin-bottom: 12px;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .time-category-header ha-icon {
        --mdc-icon-size: 22px;
        color: var(--primary-color);
      }

      .time-category-header .count {
        margin-left: auto;
        font-size: 0.85em;
        color: var(--secondary-text-color);
        background: var(--card-background-color);
        padding: 2px 10px;
        border-radius: 12px;
      }

      .chores-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding-left: 8px;
      }

      .chore-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 10px;
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
      }

      .chore-item:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        border-color: var(--primary-color);
      }

      .order-number {
        min-width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-radius: 50%;
        font-size: 0.85em;
        font-weight: 600;
      }

      .chore-icon {
        --mdc-icon-size: 24px;
        color: var(--secondary-text-color);
      }

      .chore-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }

      .chore-name {
        font-weight: 500;
        color: var(--primary-text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .chore-points {
        font-size: 0.85em;
        color: var(--secondary-text-color);
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .chore-points ha-icon {
        --mdc-icon-size: 14px;
        color: #ffc107;
      }

      .reorder-buttons {
        display: flex;
        gap: 4px;
      }

      .reorder-button {
        width: 36px;
        height: 36px;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: background 0.15s ease, border-color 0.15s ease, transform 0.1s ease;
      }

      .reorder-button:hover:not(:disabled) {
        background: var(--secondary-background-color);
        border-color: var(--primary-color);
      }

      .reorder-button:active:not(:disabled) {
        transform: scale(0.92);
      }

      .reorder-button:disabled {
        opacity: 0.3;
        cursor: not-allowed;
      }

      .reorder-button ha-icon {
        --mdc-icon-size: 20px;
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 48px 24px;
        color: var(--secondary-text-color);
        text-align: center;
      }

      .empty-state ha-icon {
        --mdc-icon-size: 56px;
        margin-bottom: 16px;
        opacity: 0.5;
      }

      .empty-state .message {
        font-size: 1.1em;
        margin-bottom: 8px;
        color: var(--primary-text-color);
      }

      .empty-state .submessage {
        font-size: 0.9em;
        opacity: 0.8;
      }

      .error-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 48px 24px;
        color: var(--error-color);
        text-align: center;
      }

      .error-state ha-icon {
        --mdc-icon-size: 48px;
        margin-bottom: 16px;
      }

      /* Status indicator */
      .status-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 12px;
        background: var(--secondary-background-color);
        border-radius: 8px;
        margin-bottom: 16px;
        font-size: 0.85em;
      }

      .status-text {
        color: var(--secondary-text-color);
      }

      .status-text.unsaved {
        color: var(--warning-color, #ff9800);
        font-weight: 500;
      }

      .status-text.saved {
        color: var(--success-color, #4caf50);
      }

      /* Responsive adjustments */
      @media (max-width: 500px) {
        .card-header {
          flex-direction: column;
          align-items: stretch;
          gap: 12px;
        }

        .header-left {
          justify-content: space-between;
        }

        .save-button {
          width: 100%;
          justify-content: center;
        }

        .chore-item {
          padding: 10px 12px;
        }

        .reorder-button {
          width: 32px;
          height: 32px;
        }
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity (Choremander overview sensor)");
    }
    if (!config.child_id) {
      throw new Error("Please define a child_id");
    }
    this.config = {
      title: "Reorder Chores",
      ...config,
    };
  }

  getCardSize() {
    return 4;
  }

  static getConfigElement() {
    return document.createElement("choremander-reorder-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.choremander_overview",
      child_id: "",
      title: "Reorder Chores",
    };
  }

  updated(changedProperties) {
    super.updated(changedProperties);

    // Initialize local chore order from server data when hass changes
    if (changedProperties.has("hass") && this.hass && this.config) {
      this._initializeLocalOrder();
    }
  }

  _initializeLocalOrder() {
    const entity = this.hass.states[this.config.entity];
    if (!entity) return;

    const children = entity.attributes.children || [];
    const child = children.find((c) => c.id === this.config.child_id);
    if (!child) return;

    // Only initialize if we don't have local changes
    if (!this._hasChanges) {
      const serverOrder = child.chore_order || [];
      // Build a map of time_category -> ordered chore IDs
      const chores = entity.attributes.chores || [];
      const childChores = this._getChoresForChild(chores, child.id);

      const newLocalOrder = {};
      const timeCategories = ["morning", "afternoon", "evening", "night", "anytime"];

      for (const category of timeCategories) {
        const categoryChores = childChores.filter(
          (c) => c.time_category === category
        );

        // Sort by server order
        const sorted = this._sortChoresByOrder(categoryChores, serverOrder);
        newLocalOrder[category] = sorted.map((c) => c.id);
      }

      this._localChoreOrder = newLocalOrder;
    }
  }

  _getChoresForChild(chores, childId) {
    // Ensure childId is a string for consistent comparison
    const childIdStr = String(childId || "");

    return chores.filter((chore) => {
      // Ensure assigned_to is always an array
      let assignedTo = chore.assigned_to;
      if (!Array.isArray(assignedTo)) {
        assignedTo = [];
      }

      // Convert all assigned_to values to strings for consistent comparison
      const assignedToStrings = assignedTo.map(id => String(id));

      // If no assignments, show to all children. Otherwise, check if child is assigned.
      const isAssignedToAll = assignedToStrings.length === 0;
      const isAssignedToChild = isAssignedToAll || assignedToStrings.includes(childIdStr);

      return isAssignedToChild;
    });
  }

  _sortChoresByOrder(chores, choreOrder) {
    if (!choreOrder || choreOrder.length === 0) {
      return [...chores];
    }

    return [...chores].sort((a, b) => {
      const indexA = choreOrder.indexOf(a.id);
      const indexB = choreOrder.indexOf(b.id);

      if (indexA !== -1 && indexB !== -1) {
        return indexA - indexB;
      }
      if (indexA !== -1) return -1;
      if (indexB !== -1) return 1;
      return 0;
    });
  }

  _getTimeCategoryIcon(category) {
    const icons = {
      morning: "mdi:weather-sunset-up",
      afternoon: "mdi:weather-sunny",
      evening: "mdi:weather-sunset-down",
      night: "mdi:weather-night",
      anytime: "mdi:clock-outline",
    };
    return icons[category] || icons.anytime;
  }

  _getTimeCategoryLabel(category) {
    const labels = {
      morning: "Morning",
      afternoon: "Afternoon",
      evening: "Evening",
      night: "Night",
      anytime: "Anytime",
    };
    return labels[category] || category;
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
    const child = children.find((c) => c.id === this.config.child_id);

    if (!child) {
      return html`
        <ha-card>
          <div class="error-state">
            <ha-icon icon="mdi:account-alert"></ha-icon>
            <div>Child not found: ${this.config.child_id}</div>
          </div>
        </ha-card>
      `;
    }

    const chores = entity.attributes.chores || [];
    const childChores = this._getChoresForChild(chores, child.id);

    if (childChores.length === 0) {
      return html`
        <ha-card>
          <div class="card-header">
            <div class="header-left">
              <span class="card-title">${this.config.title}</span>
              <span class="child-name">${child.name}</span>
            </div>
          </div>
          <div class="empty-state">
            <ha-icon icon="mdi:clipboard-text-off"></ha-icon>
            <div class="message">No chores assigned</div>
            <div class="submessage">Add chores to this child first</div>
          </div>
        </ha-card>
      `;
    }

    const timeCategories = ["morning", "afternoon", "evening", "night", "anytime"];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";

    return html`
      <ha-card>
        <div class="card-header">
          <div class="header-left">
            <span class="card-title">${this.config.title}</span>
            <span class="child-name">${child.name}</span>
          </div>
          <button
            class="save-button ${this._saving ? "saving" : ""} ${this._hasChanges ? "has-changes" : ""}"
            @click="${this._handleSave}"
            ?disabled="${this._saving || !this._hasChanges}"
          >
            <ha-icon icon="${this._saving ? "mdi:loading" : "mdi:content-save"}"></ha-icon>
            ${this._saving ? "Saving..." : "Save Order"}
          </button>
        </div>

        ${this._hasChanges
          ? html`
              <div class="status-bar">
                <span class="status-text unsaved">You have unsaved changes</span>
              </div>
            `
          : ""}

        ${timeCategories.map((category) => {
          const categoryChoreIds = this._localChoreOrder[category] || [];
          const categoryChores = categoryChoreIds
            .map((id) => chores.find((c) => c.id === id))
            .filter((c) => c);

          // Also include any chores in this category that aren't in the order yet
          const orderedIds = new Set(categoryChoreIds);
          const missingChores = childChores.filter(
            (c) => c.time_category === category && !orderedIds.has(c.id)
          );
          const allCategoryChores = [...categoryChores, ...missingChores];

          if (allCategoryChores.length === 0) {
            return "";
          }

          return html`
            <div class="time-category-section">
              <div class="time-category-header">
                <ha-icon icon="${this._getTimeCategoryIcon(category)}"></ha-icon>
                ${this._getTimeCategoryLabel(category)}
                <span class="count">${allCategoryChores.length} chore${allCategoryChores.length !== 1 ? "s" : ""}</span>
              </div>
              <div class="chores-list">
                ${allCategoryChores.map((chore, index) =>
                  this._renderChoreItem(chore, index, allCategoryChores.length, category, pointsIcon)
                )}
              </div>
            </div>
          `;
        })}
      </ha-card>
    `;
  }

  _renderChoreItem(chore, index, total, category, pointsIcon) {
    const isFirst = index === 0;
    const isLast = index === total - 1;

    return html`
      <div class="chore-item">
        <span class="order-number">${index + 1}</span>
        <ha-icon class="chore-icon" icon="${chore.icon || "mdi:broom"}"></ha-icon>
        <div class="chore-info">
          <span class="chore-name">${chore.name}</span>
          <span class="chore-points">
            <ha-icon icon="${pointsIcon}"></ha-icon>
            ${chore.points} points
          </span>
        </div>
        <div class="reorder-buttons">
          <button
            class="reorder-button"
            @click="${() => this._moveChore(category, index, -1)}"
            ?disabled="${isFirst}"
            title="Move up"
          >
            <ha-icon icon="mdi:arrow-up"></ha-icon>
          </button>
          <button
            class="reorder-button"
            @click="${() => this._moveChore(category, index, 1)}"
            ?disabled="${isLast}"
            title="Move down"
          >
            <ha-icon icon="mdi:arrow-down"></ha-icon>
          </button>
        </div>
      </div>
    `;
  }

  _moveChore(category, currentIndex, direction) {
    const newIndex = currentIndex + direction;
    const categoryOrder = [...(this._localChoreOrder[category] || [])];

    if (newIndex < 0 || newIndex >= categoryOrder.length) {
      return;
    }

    // Swap the items
    const temp = categoryOrder[currentIndex];
    categoryOrder[currentIndex] = categoryOrder[newIndex];
    categoryOrder[newIndex] = temp;

    this._localChoreOrder = {
      ...this._localChoreOrder,
      [category]: categoryOrder,
    };
    this._hasChanges = true;
    this.requestUpdate();
  }

  async _handleSave() {
    if (this._saving || !this._hasChanges) {
      return;
    }

    this._saving = true;
    this.requestUpdate();

    try {
      // Combine all category orders into a single flat array
      const timeCategories = ["morning", "afternoon", "evening", "night", "anytime"];
      const fullOrder = [];

      for (const category of timeCategories) {
        const categoryOrder = this._localChoreOrder[category] || [];
        fullOrder.push(...categoryOrder);
      }

      await this.hass.callService("choremander", "set_chore_order", {
        child_id: this.config.child_id,
        chore_order: fullOrder,
      });

      this._hasChanges = false;

      // Show success feedback
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: "Chore Order Saved",
          message: "The chore order has been updated successfully.",
          notification_id: "choremander_reorder_success",
        });

        // Auto-dismiss after 3 seconds
        setTimeout(() => {
          this.hass.callService("persistent_notification", "dismiss", {
            notification_id: "choremander_reorder_success",
          });
        }, 3000);
      }
    } catch (error) {
      console.error("Failed to save chore order:", error);
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: "Error Saving Order",
          message: `Failed to save chore order: ${error.message}`,
          notification_id: "choremander_reorder_error",
        });
      }
    } finally {
      this._saving = false;
      this.requestUpdate();
    }
  }
}

// Card Editor
class ChoremanderReorderCardEditor extends LitElement {
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

      .form-group input,
      .form-group select {
        width: 100%;
        padding: 8px;
        border: 1px solid var(--divider-color);
        border-radius: 4px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        font-size: 1em;
        box-sizing: border-box;
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

    // Get children from overview entity
    const overviewEntity = this.hass.states[this.config.entity];
    const children = overviewEntity?.attributes?.children || [];

    return html`
      <div class="form-group">
        <label>Overview Entity</label>
        <input
          type="text"
          .value="${this.config.entity || ""}"
          @input="${this._entityChanged}"
          placeholder="sensor.choremander_overview"
        />
        <small>The Choremander overview sensor entity</small>
      </div>

      <div class="form-group">
        <label>Child</label>
        <select @change="${this._childIdChanged}">
          <option value="">Select a child...</option>
          ${children.map(
            (child) => html`
              <option value="${child.id}" ?selected="${this.config.child_id === child.id}">
                ${child.name}
              </option>
            `
          )}
        </select>
        <small>Which child to manage chore order for</small>
      </div>

      <div class="form-group">
        <label>Card Title</label>
        <input
          type="text"
          .value="${this.config.title || ""}"
          @input="${this._titleChanged}"
          placeholder="Reorder Chores"
        />
        <small>Optional custom title for the card</small>
      </div>
    `;
  }

  _entityChanged(e) {
    this._updateConfig("entity", e.target.value);
  }

  _childIdChanged(e) {
    this._updateConfig("child_id", e.target.value);
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
customElements.define("choremander-reorder-card", ChoremanderReorderCard);
customElements.define("choremander-reorder-card-editor", ChoremanderReorderCardEditor);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "choremander-reorder-card",
  name: "Choremander Reorder Card",
  description: "A card for reordering chores per child, organized by time category",
  preview: true,
});

console.info(
  "%c CHOREMANDER-REORDER-CARD %c Loaded ",
  "background: #3498db; color: white; font-weight: bold; border-radius: 4px 0 0 4px;",
  "background: #2ecc71; color: white; font-weight: bold; border-radius: 0 4px 4px 0;"
);
