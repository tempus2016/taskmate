/**
 * TaskMate Reorder Card
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

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateReorderCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _saving: { type: Boolean },
      _localChoreOrder: { type: Object },
      _hasChanges: { type: Boolean },
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
    this._saving = false;
    this._localChoreOrder = {};
    this._hasChanges = false;
  }

  static get styles() {
    return css`
      :host {
        display: block;
      }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, var(--primary-color));
        color: var(--text-primary-color, #fff);
        gap: 12px;
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
        flex: 1;
      }

      .header-icon {
        --mdc-icon-size: 22px;
        opacity: 0.9;
        flex-shrink: 0;
        color: var(--text-primary-color, #fff);
      }

      .card-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--text-primary-color, #fff);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .child-name {
        font-size: 0.8rem;
        font-weight: 600;
        color: rgba(255,255,255,0.85);
        padding: 3px 10px;
        background: rgba(255,255,255,0.15);
        border-radius: 12px;
        white-space: nowrap;
        flex-shrink: 0;
      }

      .save-button {
        background: rgba(255,255,255,0.15);
        color: var(--text-primary-color, #fff);
        border: 1px solid rgba(255,255,255,0.3);
        border-radius: 8px;
        padding: 7px 14px;
        font-size: 0.85rem;
        font-weight: 600;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 6px;
        transition: background 0.2s ease, transform 0.15s ease;
        white-space: nowrap;
        flex-shrink: 0;
      }

      .save-button:hover:not(:disabled) {
        background: rgba(255,255,255,0.25);
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
        0%, 100% { box-shadow: 0 0 0 0 rgba(255,255,255,0.3); }
        50% { box-shadow: 0 0 0 6px rgba(255,255,255,0); }
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
        color: #ca8a04;
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

      .chore-item.drag-over {
        border-color: var(--primary-color);
        background: var(--secondary-background-color);
        box-shadow: 0 0 0 2px var(--primary-color);
      }

      .chore-item.dragging {
        opacity: 0.4;
        cursor: grabbing;
      }

      .drag-handle {
        cursor: grab;
        color: var(--secondary-text-color);
        display: flex;
        align-items: center;
        padding: 4px;
        touch-action: none;
      }

      .drag-handle ha-icon {
        --mdc-icon-size: 20px;
      }

      .drag-handle:active {
        cursor: grabbing;
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
      .card-body {
        padding: 16px;
      }

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
      throw new Error("Please define an entity (TaskMate overview sensor)");
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
    return document.createElement("taskmate-reorder-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.taskmate_overview",
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

    if (entity.state === "unavailable" || entity.state === "unknown") {
      return;
    }

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const child = children.find((c) => c.id === this.config.child_id)
      || (!this.config.child_id && children[0]);
    if (!child) return;

    // Only initialize if we don't have local changes
    if (!this._hasChanges) {
      const serverOrder = child.chore_order || [];
      // Build a map of time_category -> ordered chore IDs
      const chores = attrs.chores || [];
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
    const keys = {
      morning: 'common.morning',
      afternoon: 'common.afternoon',
      evening: 'common.evening',
      night: 'common.night',
      anytime: 'common.anytime',
    };
    return keys[category] ? this._t(keys[category]) : category;
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

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const child = children.find((c) => c.id === this.config.child_id)
      || (!this.config.child_id && children[0]);

    if (!child) {
      return html`
        <ha-card>
          <div class="error-state">
            <ha-icon icon="mdi:account-alert"></ha-icon>
            <div>${this._t('reorder.child_not_found', { child_id: this.config.child_id })}</div>
          </div>
        </ha-card>
      `;
    }

    const chores = attrs.chores || [];
    const childChores = this._getChoresForChild(chores, child.id);

    if (childChores.length === 0) {
      return html`
        <ha-card>
          <div class="card-header">
            <div class="header-left">
              <ha-icon class="header-icon" icon="mdi:sort"></ha-icon>
              <span class="card-title">${this.config.title || this._t('reorder.default_title')}</span>
              <span class="child-name">${child.name}</span>
            </div>
          </div>
          <div class="empty-state">
            <ha-icon icon="mdi:clipboard-text-off"></ha-icon>
            <div class="message">${this._t('reorder.no_chores_assigned')}</div>
            <div class="submessage">${this._t('reorder.add_chores_first')}</div>
          </div>
        </ha-card>
      `;
    }

    const timeCategories = ["morning", "afternoon", "evening", "night", "anytime"];
    const pointsIcon = attrs.points_icon || "mdi:star";

    const headerColor = _safeColor(this.config.header_color, '');
    const headerStyle = headerColor
      ? `--taskmate-header-bg: ${headerColor};`
      : '';

    return html`
      <ha-card>
        ${headerStyle ? html`<style>:host { ${headerStyle} }</style>` : ''}
        <div class="card-header">
          <div class="header-left">
            <ha-icon class="header-icon" icon="mdi:sort"></ha-icon>
            <span class="card-title">${this.config.title || this._t('reorder.default_title')}</span>
            <span class="child-name">${child.name}</span>
          </div>
          <button
            class="save-button ${this._saving ? "saving" : ""} ${this._hasChanges ? "has-changes" : ""}"
            @click="${this._handleSave}"
            ?disabled="${this._saving || !this._hasChanges}"
          >
            <ha-icon icon="${this._saving ? "mdi:loading" : "mdi:content-save"}"></ha-icon>
            ${this._saving ? this._t('reorder.saving') : this._t('reorder.save_order')}
          </button>
        </div>

        <div class="card-body">
        ${this._hasChanges
          ? html`
              <div class="status-bar">
                <span class="status-text unsaved">${this._t('reorder.unsaved_changes')}</span>
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
                <span class="count">${allCategoryChores.length !== 1 ? this._t('reorder.chore_count_plural', { count: allCategoryChores.length }) : this._t('reorder.chore_count', { count: allCategoryChores.length })}</span>
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
      <div
        class="chore-item"
        draggable="true"
        data-index="${index}"
        data-category="${category}"
        @dragstart="${(e) => this._onDragStart(e, category, index)}"
        @dragover="${(e) => this._onDragOver(e)}"
        @dragenter="${(e) => this._onDragEnter(e)}"
        @dragleave="${(e) => this._onDragLeave(e)}"
        @drop="${(e) => this._onDrop(e, category, index)}"
        @dragend="${(e) => this._onDragEnd(e)}"
        @touchstart="${(e) => this._onTouchStart(e, category, index)}"
        @touchmove="${(e) => this._onTouchMove(e)}"
        @touchend="${(e) => this._onTouchEnd(e, category)}"
      >
        <div class="drag-handle" title="${this._t('reorder.drag_to_reorder')}">
          <ha-icon icon="mdi:drag-vertical"></ha-icon>
        </div>
        <span class="order-number">${index + 1}</span>
        <ha-icon class="chore-icon" icon="${chore.icon || "mdi:broom"}"></ha-icon>
        <div class="chore-info">
          <span class="chore-name">${chore.name}</span>
          <span class="chore-points">
            <ha-icon icon="${pointsIcon}"></ha-icon>
            ${chore.points} ${this._t('common.points').toLowerCase()}
          </span>
        </div>
        <div class="reorder-buttons">
          <button
            class="reorder-button"
            @click="${() => this._moveChore(category, index, -1)}"
            ?disabled="${isFirst}"
            title="${this._t('reorder.move_up')}"
          >
            <ha-icon icon="mdi:arrow-up"></ha-icon>
          </button>
          <button
            class="reorder-button"
            @click="${() => this._moveChore(category, index, 1)}"
            ?disabled="${isLast}"
            title="${this._t('reorder.move_down')}"
          >
            <ha-icon icon="mdi:arrow-down"></ha-icon>
          </button>
        </div>
      </div>
    `;
  }

  // -- Drag and Drop (mouse/pointer) --
  _onDragStart(e, category, index) {
    this._dragState = { category, index };
    e.dataTransfer.effectAllowed = "move";
    e.currentTarget.classList.add("dragging");
  }

  _onDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }

  _onDragEnter(e) {
    e.currentTarget.classList.add("drag-over");
  }

  _onDragLeave(e) {
    e.currentTarget.classList.remove("drag-over");
  }

  _onDrop(e, category, toIndex) {
    e.preventDefault();
    e.currentTarget.classList.remove("drag-over");
    if (!this._dragState) return;
    const { category: fromCategory, index: fromIndex } = this._dragState;
    if (fromCategory === category && fromIndex !== toIndex) {
      this._swapChores(category, fromIndex, toIndex);
    }
    this._dragState = null;
  }

  _onDragEnd(e) {
    e.currentTarget.classList.remove("dragging", "drag-over");
    this._dragState = null;
  }

  // -- Touch drag (mobile) --
  _onTouchStart(e, category, index) {
    this._touchState = { category, index, startY: e.touches[0].clientY };
  }

  _onTouchMove(e) {
    e.preventDefault(); // prevent scroll while dragging
    if (!this._touchState) return;
    const touch = e.touches[0];
    const el = this.shadowRoot?.elementFromPoint(touch.clientX, touch.clientY);
    if (!el) return;
    const item = el.closest(".chore-item");
    this.shadowRoot.querySelectorAll(".chore-item").forEach(i => i.classList.remove("drag-over"));
    if (item) item.classList.add("drag-over");
  }

  _onTouchEnd(e, category) {
    if (!this._touchState) return;
    const touch = e.changedTouches[0];
    const el = this.shadowRoot?.elementFromPoint(touch.clientX, touch.clientY);
    this.shadowRoot?.querySelectorAll(".chore-item").forEach(i => i.classList.remove("drag-over"));
    const item = el ? el.closest(".chore-item") : null;
    if (item) {
      const toIndex = parseInt(item.dataset.index, 10);
      const { index: fromIndex } = this._touchState;
      if (!isNaN(toIndex) && fromIndex !== toIndex) {
        this._swapChores(category, fromIndex, toIndex);
      }
    }
    this._touchState = null;
  }

  _swapChores(category, fromIndex, toIndex) {
    const order = [...(this._localChoreOrder[category] || [])];
    const item = order.splice(fromIndex, 1)[0];
    order.splice(toIndex, 0, item);
    this._localChoreOrder = { ...this._localChoreOrder, [category]: order };
    this._hasChanges = true;
    this.requestUpdate();
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

      await this.hass.callService("taskmate", "set_chore_order", {
        child_id: this.config.child_id,
        chore_order: fullOrder,
      });

      this._hasChanges = false;

      // Show success feedback
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: this._t('reorder.notification.save_success_title'),
          message: this._t('reorder.notification.save_success_message'),
          notification_id: "taskmate_reorder_success",
        });

        // Auto-dismiss after 3 seconds
        setTimeout(() => {
          this.hass.callService("persistent_notification", "dismiss", {
            notification_id: "taskmate_reorder_success",
          });
        }, 3000);
      }
    } catch (error) {
      console.error("Failed to save chore order:", error);
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: this._t('reorder.notification.save_error_title'),
          message: this._t('reorder.notification.save_error_message', { error: error.message }),
          notification_id: "taskmate_reorder_error",
        });
      }
    } finally {
      this._saving = false;
      this.requestUpdate();
    }
  }
}

// Card Editor
class TaskMateReorderCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-form { display: block; margin-bottom: 16px; }
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

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  _buildSchema() {
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const children = entity?.attributes?.children || [];
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('reorder.editor.select_child') },
              ...children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
      { name: 'title', selector: { text: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      child_id: this._t('reorder.editor.child'),
      title: this._t('common.editor.card_title'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('reorder.editor.child_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      child_id: this.config.child_id || '',
      title: this.config.title || '',
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
      ${this._renderColourPicker('header_color', '')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = ['#16a085', '#e67e22', '#3498db', '#9b59b6', '#f1c40f', '#e74c3c', '#34495e'];
    const isActive = (c) => current && c.toLowerCase() === current.toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${this._t('common.editor.header_colour')}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current || '#16a085'}
              @input=${(e) => this._updateConfig(key, e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current || '#16a085'}"></span>
          </label>
          <span class="colour-hex">${current || this._t('common.default')}</span>
          <div class="colour-presets">
            ${presets.map((p) => html`
              <button class="preset-swatch ${isActive(p) ? 'active' : ''}"
                style="background:${p}"
                title=${p}
                @click=${(e) => { e.preventDefault(); this._updateConfig(key, p); }}
              ></button>
            `)}
          </div>
          <button class="colour-reset"
            @click=${(e) => { e.preventDefault(); this._updateConfig(key, ''); }}
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
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === undefined || value === "") delete newConfig[key];
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

// Register the cards
customElements.define("taskmate-reorder-card", TaskMateReorderCard);
customElements.define("taskmate-reorder-card-editor", TaskMateReorderCardEditor);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-reorder-card",
  name: "TaskMate Reorder Card",
  description: "A card for reordering chores per child, organized by time category",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-reorder-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE REORDER CARD %c v" + _tmVersion + " ",
  "background:#03a9f4;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
