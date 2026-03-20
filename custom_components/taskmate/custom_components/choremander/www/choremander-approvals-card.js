/**
 * Choremander Approvals Card
 * A custom Lovelace card for managing pending chore approvals
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class ChoremanderApprovalsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _loading: { type: Object },
    };
  }

  constructor() {
    super();
    this._loading = {};
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
        padding-bottom: 12px;
        border-bottom: 1px solid var(--divider-color);
        margin-bottom: 16px;
      }

      .card-title {
        font-size: 1.2em;
        font-weight: 500;
        color: var(--primary-text-color);
      }

      .pending-count {
        background: var(--primary-color);
        color: var(--text-primary-color);
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 0.9em;
        font-weight: 500;
      }

      .day-group {
        margin-bottom: 20px;
      }

      .day-header {
        font-size: 0.95em;
        font-weight: 600;
        color: var(--primary-text-color);
        margin-bottom: 12px;
        padding: 8px 12px;
        background: var(--secondary-background-color);
        border-radius: 8px;
      }

      .time-group {
        margin-left: 8px;
        margin-bottom: 12px;
      }

      .time-header {
        font-size: 0.85em;
        font-weight: 500;
        color: var(--secondary-text-color);
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .time-header ha-icon {
        --mdi-icon-size: 16px;
      }

      .approval-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px;
        margin-bottom: 8px;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        transition: box-shadow 0.2s ease;
      }

      .approval-item:hover {
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
      }

      .approval-item.loading {
        opacity: 0.6;
        pointer-events: none;
      }

      .item-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
        flex: 1;
        min-width: 0;
      }

      .chore-name {
        font-weight: 500;
        color: var(--primary-text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .item-details {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 0.85em;
        color: var(--secondary-text-color);
      }

      .child-name {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .points-badge {
        display: flex;
        align-items: center;
        gap: 4px;
        background: var(--accent-color, #ffc107);
        color: var(--text-primary-color, #000);
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 500;
      }

      .points-badge ha-icon {
        --mdi-icon-size: 14px;
      }

      .action-buttons {
        display: flex;
        gap: 8px;
      }

      .action-buttons.left {
        margin-right: 12px;
      }

      .action-buttons.right {
        margin-left: 12px;
      }

      .action-button {
        border: none;
        border-radius: 50%;
        width: 36px;
        height: 36px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
      }

      .action-button:hover {
        transform: scale(1.1);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
      }

      .action-button:active {
        transform: scale(0.95);
      }

      .action-button.approve {
        background: #4caf50;
        color: white;
      }

      .action-button.reject {
        background: #f44336;
        color: white;
      }

      .action-button ha-icon {
        --mdi-icon-size: 20px;
      }

      .action-button.loading {
        opacity: 0.6;
        cursor: not-allowed;
      }

      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        color: var(--secondary-text-color);
        text-align: center;
      }

      .empty-state ha-icon {
        --mdi-icon-size: 48px;
        margin-bottom: 16px;
        opacity: 0.5;
      }

      .empty-state .message {
        font-size: 1.1em;
        margin-bottom: 4px;
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
        padding: 40px 20px;
        color: var(--error-color);
        text-align: center;
      }

      .error-state ha-icon {
        --mdi-icon-size: 48px;
        margin-bottom: 16px;
      }

      .loading-spinner {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 40px;
      }

      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }

      .spinner {
        width: 40px;
        height: 40px;
        border: 3px solid var(--divider-color);
        border-top-color: var(--primary-color);
        border-radius: 50%;
        animation: spin 1s linear infinite;
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity (pending_approvals sensor)");
    }
    this.config = {
      title: "Pending Approvals",
      ...config,
    };
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("choremander-approvals-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.pending_approvals",
      title: "Pending Approvals",
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

    const completions = entity.attributes.chore_completions || [];
    const filteredCompletions = this._filterByChild(completions);
    const groupedByDay = this._groupByDay(filteredCompletions);
    const totalPending = filteredCompletions.length;

    return html`
      <ha-card>
        <div class="card-header">
          <span class="card-title">${this.config.title}</span>
          ${totalPending > 0
            ? html`<span class="pending-count">${totalPending}</span>`
            : ""}
        </div>

        ${totalPending === 0
          ? this._renderEmptyState()
          : this._renderApprovals(groupedByDay)}
      </ha-card>
    `;
  }

  _filterByChild(completions) {
    if (!this.config.child_id) {
      return completions;
    }
    return completions.filter(
      (c) => c.child_id === this.config.child_id
    );
  }

  _groupByDay(completions) {
    const groups = {};

    completions.forEach((completion) => {
      const date = new Date(completion.completed_at);
      const dayKey = this._getDayKey(date);

      if (!groups[dayKey]) {
        groups[dayKey] = {
          label: this._getDayLabel(date),
          date: date,
          timeCategories: {},
        };
      }

      const timeCategory = completion.time_category || "anytime";
      if (!groups[dayKey].timeCategories[timeCategory]) {
        groups[dayKey].timeCategories[timeCategory] = [];
      }
      groups[dayKey].timeCategories[timeCategory].push(completion);
    });

    // Sort groups by date (most recent first)
    const sortedGroups = Object.entries(groups).sort(
      ([, a], [, b]) => b.date - a.date
    );

    return sortedGroups;
  }

  _getTimezone() {
    // Get timezone from Home Assistant config, fallback to browser timezone
    return this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  }

  _getLocale() {
    // Get locale from Home Assistant, fallback to browser locale
    return this.hass?.locale?.language || this.hass?.language || navigator.language || "en";
  }

  _formatDateInTimezone(date, options = {}) {
    const timezone = this._getTimezone();
    const locale = this._getLocale();
    return date.toLocaleDateString(locale, { ...options, timeZone: timezone });
  }

  _getDatePartsInTimezone(date) {
    const timezone = this._getTimezone();
    // Get year, month, day in the HA timezone
    const formatter = new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    // en-CA formats as YYYY-MM-DD
    const dateStr = formatter.format(date);
    const [year, month, day] = dateStr.split("-").map(Number);
    return { year, month, day };
  }

  _getDayKey(date) {
    // Use HA timezone to determine the day key
    const { year, month, day } = this._getDatePartsInTimezone(date);
    return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  _getDayLabel(date) {
    const timezone = this._getTimezone();

    // Get today's date parts in HA timezone
    const now = new Date();
    const todayParts = this._getDatePartsInTimezone(now);
    const dateParts = this._getDatePartsInTimezone(date);

    // Calculate yesterday in HA timezone
    const yesterdayDate = new Date(now);
    yesterdayDate.setDate(yesterdayDate.getDate() - 1);
    const yesterdayParts = this._getDatePartsInTimezone(yesterdayDate);

    // Compare date parts
    const isToday =
      dateParts.year === todayParts.year &&
      dateParts.month === todayParts.month &&
      dateParts.day === todayParts.day;

    const isYesterday =
      dateParts.year === yesterdayParts.year &&
      dateParts.month === yesterdayParts.month &&
      dateParts.day === yesterdayParts.day;

    if (isToday) {
      return "Today";
    } else if (isYesterday) {
      return "Yesterday";
    } else {
      return this._formatDateInTimezone(date, {
        month: "short",
        day: "numeric",
      });
    }
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

  _getTimeCategoryOrder(category) {
    const order = {
      morning: 0,
      afternoon: 1,
      evening: 2,
      night: 3,
      anytime: 4,
    };
    return order[category] !== undefined ? order[category] : 5;
  }

  _renderEmptyState() {
    return html`
      <div class="empty-state">
        <ha-icon icon="mdi:check-circle-outline"></ha-icon>
        <div class="message">All caught up!</div>
        <div class="submessage">No pending approvals</div>
      </div>
    `;
  }

  _renderApprovals(groupedByDay) {
    return html`
      ${groupedByDay.map(
        ([dayKey, dayGroup]) => html`
          <div class="day-group">
            <div class="day-header">${dayGroup.label}</div>
            ${this._renderTimeCategories(dayGroup.timeCategories)}
          </div>
        `
      )}
    `;
  }

  _renderTimeCategories(timeCategories) {
    const sortedCategories = Object.entries(timeCategories).sort(
      ([a], [b]) => this._getTimeCategoryOrder(a) - this._getTimeCategoryOrder(b)
    );

    return html`
      ${sortedCategories.map(
        ([category, completions]) => html`
          <div class="time-group">
            <div class="time-header">
              <ha-icon icon="${this._getTimeCategoryIcon(category)}"></ha-icon>
              ${this._getTimeCategoryLabel(category)}
            </div>
            ${completions.map((completion) => this._renderApprovalItem(completion))}
          </div>
        `
      )}
    `;
  }

  _renderApprovalItem(completion) {
    const isLoading = this._loading[completion.completion_id];

    return html`
      <div class="approval-item ${isLoading ? "loading" : ""}">
        <div class="action-buttons left">
          <button
            class="action-button reject ${isLoading ? "loading" : ""}"
            @click="${() => this._handleReject(completion)}"
            title="Reject"
            ?disabled="${isLoading}"
          >
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
        </div>
        <div class="item-info">
          <span class="chore-name">${completion.chore_name}</span>
          <div class="item-details">
            <span class="child-name">
              <ha-icon icon="mdi:account"></ha-icon>
              ${completion.child_name}
            </span>
            <span class="points-badge">
              <ha-icon icon="mdi:star"></ha-icon>
              ${completion.points}
            </span>
          </div>
        </div>
        <div class="action-buttons right">
          <button
            class="action-button approve ${isLoading ? "loading" : ""}"
            @click="${() => this._handleApprove(completion)}"
            title="Approve"
            ?disabled="${isLoading}"
          >
            <ha-icon icon="mdi:check"></ha-icon>
          </button>
        </div>
      </div>
    `;
  }

  async _handleApprove(completion) {
    await this._callService("approve_chore", completion.completion_id);
  }

  async _handleReject(completion) {
    await this._callService("reject_chore", completion.completion_id);
  }

  async _callService(service, completionId) {
    this._loading = { ...this._loading, [completionId]: true };
    this.requestUpdate();

    try {
      await this.hass.callService("choremander", service, {
        completion_id: completionId,
      });
    } catch (error) {
      console.error(`Failed to call ${service}:`, error);
      // Show error toast if available
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: "Choremander Error",
          message: `Failed to ${service.replace("_", " ")}: ${error.message}`,
          notification_id: `choremander_error_${completionId}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [completionId]: false };
      this.requestUpdate();
    }
  }
}

// Card Editor
class ChoremanderApprovalsCardEditor extends LitElement {
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
          placeholder="sensor.pending_approvals"
        />
        <small>The pending approvals sensor entity</small>
      </div>

      <div class="form-group">
        <label>Title</label>
        <input
          type="text"
          .value="${this.config.title || ""}"
          @input="${this._titleChanged}"
          placeholder="Pending Approvals"
        />
      </div>

      <div class="form-group">
        <label>Child ID (optional)</label>
        <input
          type="text"
          .value="${this.config.child_id || ""}"
          @input="${this._childIdChanged}"
          placeholder="Leave empty to show all children"
        />
        <small>Filter approvals to a specific child</small>
      </div>
    `;
  }

  _entityChanged(e) {
    this._updateConfig("entity", e.target.value);
  }

  _titleChanged(e) {
    this._updateConfig("title", e.target.value);
  }

  _childIdChanged(e) {
    this._updateConfig("child_id", e.target.value || undefined);
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
customElements.define(
  "choremander-approvals-card",
  ChoremanderApprovalsCard
);
customElements.define(
  "choremander-approvals-card-editor",
  ChoremanderApprovalsCardEditor
);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "choremander-approvals-card",
  name: "Choremander Approvals",
  description: "A card to manage pending chore approvals for Choremander",
  preview: true,
});

console.info(
  "%c CHOREMANDER-APPROVALS-CARD %c Loaded ",
  "background: #4CAF50; color: white; font-weight: bold;",
  "background: #ddd; color: #333;"
);
