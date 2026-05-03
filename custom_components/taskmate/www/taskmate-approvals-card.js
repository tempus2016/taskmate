/**
 * TaskMate Approvals Card
 * A custom Lovelace card for managing pending chore approvals
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateApprovalsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _loading: { type: Object },
    };
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass")) {
      return window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity);
    }
    return true;
  }

  constructor() {
    super();
    this._loading = {};
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
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
        background: var(--taskmate-header-bg, #27ae60);
        color: white;
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
        color: white;
        opacity: 0.9;
        flex-shrink: 0;
      }

      .card-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: white;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .pending-count {
        background: #e74c3c;
        color: white;
        border-radius: 12px;
        padding: 3px 10px;
        font-size: 0.82rem;
        font-weight: 700;
        flex-shrink: 0;
      }

      .card-content { padding: 16px; }

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

      .duration-badge {
        display: flex;
        align-items: center;
        gap: 4px;
        background: rgba(26, 188, 156, 0.15);
        color: #1abc9c;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 500;
        font-size: 0.85em;
      }
      .duration-badge ha-icon {
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
      title: "",
      header_color: '#27ae60',
      ...config,
    };
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("taskmate-approvals-card-editor");
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
            <div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div>
          </div>
        </ha-card>
      `;
    }

    // Support both the pending_approvals sensor (chore_completions)
    // and the overview sensor (todays_completions filtered to unapproved).
    // The resolver is used so pending_reward_claims / todays_completions
    // resolve from their new companion sensors when the card is pointed at
    // the overview entity.
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    let completions = entity.attributes.chore_completions;
    if (!completions) {
      completions = (attrs.todays_completions || []).filter(c => !c.approved);
    }
    const filteredCompletions = this._filterByChild(completions);
    const groupedByDay = this._groupByDay(filteredCompletions);

    // Pending reward claims: supported via either the pending_approvals sensor
    // (reward_claims attribute) or the rewards sensor (pending_reward_claims).
    let rewardClaims =
      entity.attributes.reward_claims ||
      attrs.pending_reward_claims ||
      [];
    const filteredClaims = this._filterClaimsByChild(rewardClaims);

    const totalPending = filteredCompletions.length + filteredClaims.length;

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#27ae60'}; }</style>
        <div class="card-header">
          <div class="header-left">
            <ha-icon class="header-icon" icon="mdi:check-circle-outline"></ha-icon>
            <span class="card-title">${this.config.title || this._t('approvals.default_title')}</span>
          </div>
          ${totalPending > 0 ? html`<span class="pending-count">${totalPending}</span>` : ""}
        </div>

        <div class="card-content">
          ${totalPending === 0
            ? this._renderEmptyState()
            : html`
                ${filteredClaims.length > 0 ? this._renderRewardClaims(filteredClaims) : ''}
                ${filteredCompletions.length > 0 ? this._renderApprovals(groupedByDay) : ''}
              `}
        </div>
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

  _filterClaimsByChild(claims) {
    if (!this.config.child_id) return claims;
    return claims.filter((c) => c.child_id === this.config.child_id);
  }

  _renderRewardClaims(claims) {
    return html`
      <div class="day-group">
        <div class="day-header">
          <ha-icon icon="mdi:gift-outline" style="--mdc-icon-size: 18px; vertical-align: -3px; margin-right: 6px;"></ha-icon>
          ${this._t('approvals.reward_claims_section') || 'Reward claims'}
        </div>
        ${claims.map((claim) => this._renderClaimItem(claim))}
      </div>
    `;
  }

  _renderClaimItem(claim) {
    const claimId = claim.claim_id || claim.id;
    const isLoading = this._loading[claimId];
    const rewardName = claim.reward_name || '';
    const childName = claim.child_name || '';
    const cost = claim.cost ?? 0;

    return html`
      <div class="approval-item ${isLoading ? 'loading' : ''}">
        <div class="action-buttons left">
          <button
            class="action-button reject ${isLoading ? 'loading' : ''}"
            @click="${() => this._handleRejectReward(claimId)}"
            title="${this._t('approvals.reject')}"
            ?disabled="${isLoading}"
          >
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
        </div>
        <div class="item-info">
          <span class="chore-name">
            <ha-icon icon="${claim.reward_icon || 'mdi:gift'}" style="--mdc-icon-size: 16px; vertical-align: -3px; margin-right: 4px;"></ha-icon>
            ${rewardName}
          </span>
          <div class="item-details">
            <span class="child-name">
              <ha-icon icon="mdi:account"></ha-icon>
              ${childName}
            </span>
            <span class="points-badge">
              <ha-icon icon="mdi:star"></ha-icon>
              ${cost}
            </span>
          </div>
        </div>
        <div class="action-buttons right">
          <button
            class="action-button approve ${isLoading ? 'loading' : ''}"
            @click="${() => this._handleApproveReward(claimId)}"
            title="${this._t('approvals.approve')}"
            ?disabled="${isLoading}"
          >
            <ha-icon icon="mdi:check"></ha-icon>
          </button>
        </div>
      </div>
    `;
  }

  async _handleApproveReward(claimId) {
    await this._callClaimService('approve_reward', claimId);
  }

  async _handleRejectReward(claimId) {
    await this._callClaimService('reject_reward', claimId);
  }

  async _callClaimService(service, claimId) {
    this._loading = { ...this._loading, [claimId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService('taskmate', service, { claim_id: claimId });
    } catch (error) {
      console.error(`Failed to call ${service}:`, error);
      if (this.hass.callService) {
        this.hass.callService('persistent_notification', 'create', {
          title: this._t('approvals.error_title'),
          message: this._t('approvals.error_failed_service', {
            service: service.replace('_', ' '),
            message: error.message,
          }),
          notification_id: `taskmate_error_${claimId}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [claimId]: false };
      this.requestUpdate();
    }
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
      return this._t('common.today');
    } else if (isYesterday) {
      return this._t('common.yesterday');
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
    const keyMap = {
      morning: 'common.morning',
      afternoon: 'common.afternoon',
      evening: 'common.evening',
      night: 'common.night',
      anytime: 'common.anytime',
    };
    return keyMap[category] ? this._t(keyMap[category]) : category;
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
        <div class="message">${this._t('approvals.all_caught_up')}</div>
        <div class="submessage">${this._t('approvals.no_pending_approvals')}</div>
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
            title="${this._t('approvals.reject')}"
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
            ${completion.timed_duration_seconds > 0 ? html`
              <span class="duration-badge">
                <ha-icon icon="mdi:timer-outline"></ha-icon>
                ${Math.floor(completion.timed_duration_seconds / 60)} min
              </span>
            ` : ''}
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
            title="${this._t('approvals.approve')}"
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
      await this.hass.callService("taskmate", service, {
        completion_id: completionId,
      });
    } catch (error) {
      console.error(`Failed to call ${service}:`, error);
      // Show error toast if available
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: this._t('approvals.error_title'),
          message: this._t('approvals.error_failed_service', { service: service.replace("_", " "), message: error.message }),
          notification_id: `taskmate_error_${completionId}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [completionId]: false };
      this.requestUpdate();
    }
  }
}

// Card Editor
class TaskMateApprovalsCardEditor extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
    };
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
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

  setConfig(config) {
    this.config = config;
  }

  _buildSchema() {
    const overviewEntity = this.config?.entity
      ? this.hass?.states?.[this.config.entity]
      : null;
    const children = overviewEntity?.attributes?.children || [];
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '__all__', label: this._t('common.editor.filter_by_child_all') },
              ...children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.entity'),
      title: this._t('common.title'),
      child_id: this._t('approvals.editor.child_id'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('approvals.editor.entity_helper'),
      child_id: this._t('approvals.editor.child_id_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      child_id: this.config.child_id || '__all__',
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
      ${this._renderColourPicker('header_color', '#27ae60')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, '#e67e22', '#3498db', '#9b59b6', '#f1c40f', '#e74c3c', '#34495e'];
    const isActive = (c) => c.toLowerCase() === current.toLowerCase();
    return html`
      <div class="colour-field">
        <span class="colour-field-label">${this._t('common.editor.header_colour')}</span>
        <div class="colour-field-body">
          <label class="colour-swatch-wrapper">
            <input type="color" .value=${current}
              @input=${(e) => this._updateConfig(key, e.target.value)} />
            <span class="colour-swatch-preview" style="background:${current}"></span>
          </label>
          <span class="colour-hex">${current}</span>
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
            @click=${(e) => { e.preventDefault(); this._updateConfig(key, defaultValue); }}
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
      if (
        value === '' || value === null || value === undefined
        || (key === 'child_id' && value === '__all__')
      ) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
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
  "taskmate-approvals-card",
  TaskMateApprovalsCard
);
customElements.define(
  "taskmate-approvals-card-editor",
  TaskMateApprovalsCardEditor
);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-approvals-card",
  name: "TaskMate Approvals",
  description: "A card to manage pending chore approvals for TaskMate",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-approvals-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE APPROVALS CARD %c v" + _tmVersion + " ",
  "background:#27ae60;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
