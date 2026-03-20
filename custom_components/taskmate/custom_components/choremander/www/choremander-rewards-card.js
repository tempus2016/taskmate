/**
 * Choremander Rewards Card
 * A Lovelace card for displaying available rewards.
 * Shows rewards in a vertical list with star cost, name, description, and progress gauges.
 * Supports regular rewards, Jackpot rewards, and Dynamic rewards (goal-based pricing).
 *
 * Version: 0.0.7
 * Last Updated: 2026-01-07
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class ChoremanderRewardsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
    };
  }

  static get styles() {
    return css`
      :host {
        display: block;
        --reward-purple: #9b59b6;
        --reward-purple-light: #a569bd;
        --reward-gold: #f1c40f;
        --reward-gold-dark: #d4a80a;
        --text-primary: var(--primary-text-color, #212121);
        --text-secondary: var(--secondary-text-color, #757575);
        --card-bg: var(--card-background-color, #fff);
        --divider: var(--divider-color, #e0e0e0);
      }

      ha-card {
        overflow: hidden;
      }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 20px;
        background: linear-gradient(135deg, var(--reward-purple) 0%, var(--reward-purple-light) 100%);
        color: white;
      }

      .header-content {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .header-icon {
        --mdc-icon-size: 32px;
        opacity: 0.95;
      }

      .header-title {
        font-size: 1.3rem;
        font-weight: 600;
      }

      .reward-count {
        background: rgba(255, 255, 255, 0.2);
        padding: 4px 12px;
        border-radius: 16px;
        font-size: 0.9rem;
        font-weight: 500;
      }

      .card-content {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      /* Individual reward row */
      .reward-row {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        padding: 16px;
        background: var(--card-bg);
        border: 1px solid var(--divider);
        border-radius: 12px;
        transition: box-shadow 0.2s ease, transform 0.15s ease;
      }

      .reward-row:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        transform: translateY(-1px);
      }

      /* Cost badge - prominently displayed */
      .cost-badge {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-width: 70px;
        padding: 12px 8px;
        background: linear-gradient(135deg, var(--reward-gold) 0%, var(--reward-gold-dark) 100%);
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(241, 196, 15, 0.3);
        flex-shrink: 0;
      }

      .cost-badge ha-icon {
        --mdc-icon-size: 24px;
        color: white;
        filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.2));
        margin-bottom: 4px;
      }

      .cost-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: white;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
        line-height: 1;
      }

      .cost-label {
        font-size: 0.65rem;
        font-weight: 600;
        color: rgba(255, 255, 255, 0.9);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 2px;
      }

      /* Reward details */
      .reward-details {
        display: flex;
        flex-direction: column;
        gap: 6px;
        flex: 1;
        min-width: 0;
        padding-top: 4px;
      }

      .reward-name {
        font-size: 1.15rem;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1.3;
      }

      .reward-description {
        font-size: 0.9rem;
        color: var(--text-secondary);
        line-height: 1.4;
      }

      /* Child assignment indicator */
      .assigned-children {
        display: flex;
        flex-wrap: wrap;
        gap: 4px;
        margin-top: 4px;
      }

      .child-badge {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        background: rgba(155, 89, 182, 0.15);
        border-radius: 12px;
        font-size: 0.75rem;
        color: var(--reward-purple);
        font-weight: 500;
      }

      .child-badge.all-children {
        background: rgba(46, 204, 113, 0.15);
        color: #27ae60;
      }

      /* Progress bar styles */
      .progress-section {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: 8px;
        width: 100%;
      }

      .progress-bar-container {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
      }

      .progress-bar {
        flex: 1;
        height: 14px;
        background: rgba(0, 0, 0, 0.08);
        border-radius: 7px;
        overflow: hidden;
        position: relative;
        border: 2px solid rgba(52, 152, 219, 0.4);
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      .progress-fill {
        height: 100%;
        border-radius: 7px;
        background: linear-gradient(90deg, #3498db 0%, #2ecc71 100%);
        transition: width 0.4s ease;
        position: relative;
        overflow: hidden;
      }

      .progress-fill::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 50%;
        height: 100%;
        background: linear-gradient(
          90deg,
          transparent,
          rgba(255, 255, 255, 0.4),
          transparent
        );
        animation: shimmer 2s infinite;
      }

      @keyframes shimmer {
        0% { left: -100%; }
        100% { left: 200%; }
      }

      .progress-text {
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--text-secondary);
        white-space: nowrap;
        min-width: 70px;
        text-align: right;
      }

      /* Jackpot reward styles */
      .reward-row.jackpot {
        border: 2px solid var(--reward-gold);
        background: linear-gradient(135deg, rgba(241, 196, 15, 0.08) 0%, rgba(255, 255, 255, 0) 100%);
        position: relative;
        overflow: hidden;
      }

      .reward-row.jackpot::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(
          45deg,
          transparent 40%,
          rgba(241, 196, 15, 0.1) 50%,
          transparent 60%
        );
        animation: jackpot-shine 40s ease-in-out infinite;
        pointer-events: none;
      }

      /* Shine 3 times (each ~2.5s = 7.5s total), then wait ~32.5s before repeating */
      @keyframes jackpot-shine {
        0% { transform: translateX(-100%); }
        2.5% { transform: translateX(100%); }
        5% { transform: translateX(-100%); }
        7.5% { transform: translateX(100%); }
        10% { transform: translateX(-100%); }
        12.5% { transform: translateX(100%); }
        15%, 100% { transform: translateX(-100%); opacity: 0; }
      }

      .jackpot-label {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 10px;
        background: linear-gradient(135deg, var(--reward-gold) 0%, #e67e22 100%);
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 700;
        color: white;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
        box-shadow: 0 2px 6px rgba(241, 196, 15, 0.4);
      }

      .jackpot-label span {
        font-size: 0.8rem;
      }

      /* Multi-child progress bar for jackpot */
      .jackpot-progress-bar {
        flex: 1;
        height: 18px;
        background: rgba(0, 0, 0, 0.08);
        border-radius: 9px;
        overflow: hidden;
        position: relative;
        display: flex;
        border: 2px solid rgba(241, 196, 15, 0.5);
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
      }

      .jackpot-segment {
        height: 100%;
        transition: width 0.4s ease;
        position: relative;
        overflow: hidden;
      }

      .jackpot-segment::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(
          90deg,
          transparent,
          rgba(255, 255, 255, 0.4),
          transparent
        );
        animation: jackpot-segment-shimmer 40s infinite;
      }

      /* Shimmer 3 times then wait ~30s before repeating */
      @keyframes jackpot-segment-shimmer {
        0% { left: -100%; }
        2.5% { left: 200%; }
        5% { left: -100%; }
        7.5% { left: 200%; }
        10% { left: -100%; }
        12.5% { left: 200%; }
        15%, 100% { left: -100%; opacity: 0; }
      }

      .jackpot-segment:first-child {
        border-radius: 9px 0 0 9px;
      }

      .jackpot-segment:last-child {
        border-radius: 0 9px 9px 0;
      }

      .jackpot-segment:only-child {
        border-radius: 9px;
      }

      /* Fun kid-friendly colors for segments */
      .jackpot-segment.color-0 { background: linear-gradient(180deg, #ff6b9d 0%, #e91e63 100%); }
      .jackpot-segment.color-1 { background: linear-gradient(180deg, #64b5f6 0%, #2196f3 100%); }
      .jackpot-segment.color-2 { background: linear-gradient(180deg, #81c784 0%, #4caf50 100%); }
      .jackpot-segment.color-3 { background: linear-gradient(180deg, #ffb74d 0%, #ff9800 100%); }
      .jackpot-segment.color-4 { background: linear-gradient(180deg, #ba68c8 0%, #9c27b0 100%); }
      .jackpot-segment.color-5 { background: linear-gradient(180deg, #4dd0e1 0%, #00bcd4 100%); }

      .jackpot-breakdown {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 4px;
        font-size: 0.8rem;
        color: var(--text-secondary);
      }

      .jackpot-child-contribution {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        padding: 2px 8px;
        background: rgba(0, 0, 0, 0.05);
        border-radius: 10px;
        font-weight: 500;
      }

      .jackpot-child-contribution .color-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      .jackpot-child-contribution .color-dot.color-0 { background: #e91e63; }
      .jackpot-child-contribution .color-dot.color-1 { background: #2196f3; }
      .jackpot-child-contribution .color-dot.color-2 { background: #4caf50; }
      .jackpot-child-contribution .color-dot.color-3 { background: #ff9800; }
      .jackpot-child-contribution .color-dot.color-4 { background: #9c27b0; }
      .jackpot-child-contribution .color-dot.color-5 { background: #00bcd4; }

      .jackpot-total {
        font-weight: 700;
        color: var(--reward-gold-dark);
        padding: 2px 8px;
        background: rgba(241, 196, 15, 0.15);
        border-radius: 10px;
      }

      /* Cost badge for jackpot - special styling */
      .reward-row.jackpot .cost-badge {
        background: linear-gradient(135deg, var(--reward-gold) 0%, #e67e22 100%);
        box-shadow: 0 3px 10px rgba(241, 196, 15, 0.4);
      }

      /* Dynamic reward styles */
      .reward-row.dynamic {
        border: 1px dashed rgba(52, 152, 219, 0.5);
      }

      .cost-badge.dynamic-cost {
        background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
        box-shadow: 0 2px 8px rgba(52, 152, 219, 0.3);
        position: relative;
      }

      .dynamic-indicator {
        font-size: 0.9rem;
        margin-top: 2px;
        filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
      }

      /* Reward icon (if available) */
      .reward-icon-container {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--reward-purple) 0%, var(--reward-purple-light) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .reward-icon-container ha-icon {
        --mdc-icon-size: 24px;
        color: white;
      }

      /* Empty state */
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 48px 24px;
        color: var(--text-secondary);
        text-align: center;
      }

      .empty-state ha-icon {
        --mdc-icon-size: 56px;
        margin-bottom: 16px;
        opacity: 0.5;
        color: var(--reward-purple);
      }

      .empty-state .message {
        font-size: 1.1rem;
        font-weight: 500;
        margin-bottom: 4px;
        color: var(--text-primary);
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
        color: var(--error-color, #f44336);
        text-align: center;
      }

      .error-state ha-icon {
        --mdc-icon-size: 48px;
        margin-bottom: 16px;
      }

      /* Responsive adjustments */
      @media (max-width: 400px) {
        .card-header {
          padding: 14px 16px;
        }

        .header-title {
          font-size: 1.15rem;
        }

        .card-content {
          padding: 12px;
          gap: 10px;
        }

        .reward-row {
          padding: 12px;
          gap: 12px;
        }

        .cost-badge {
          min-width: 60px;
          padding: 10px 6px;
        }

        .cost-badge ha-icon {
          --mdc-icon-size: 20px;
        }

        .cost-value {
          font-size: 1.2rem;
        }

        .reward-name {
          font-size: 1.05rem;
        }

        .reward-description {
          font-size: 0.85rem;
        }

        .reward-icon-container {
          width: 38px;
          height: 38px;
        }

        .reward-icon-container ha-icon {
          --mdc-icon-size: 20px;
        }
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity (choremander overview sensor)");
    }
    this.config = {
      title: "Rewards",
      child_id: null, // Optional: filter rewards for a specific child
      show_child_badges: true, // Show which children can claim each reward
      ...config,
    };
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("choremander-rewards-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.choremander_overview",
      title: "Rewards",
      child_id: null,
      show_child_badges: true,
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

    const allRewards = entity.attributes.rewards || [];
    const children = entity.attributes.children || [];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Stars";

    // Filter rewards based on child_id if configured
    let rewards = allRewards;
    if (this.config.child_id) {
      rewards = allRewards.filter((reward) => {
        const assignedTo = reward.assigned_to || [];
        // Show reward if assigned_to is empty (available to all) OR contains the child_id
        return assignedTo.length === 0 || assignedTo.includes(this.config.child_id);
      });
    }

    // Sort rewards: jackpot first, then by calculated cost ascending within each group
    const sortedRewards = [...rewards].sort((a, b) => {
      // Jackpot rewards come first
      if (a.is_jackpot && !b.is_jackpot) return -1;
      if (!a.is_jackpot && b.is_jackpot) return 1;
      // Within same type, sort by calculated cost ascending
      const aCost = this._getDisplayCost(a, children);
      const bCost = this._getDisplayCost(b, children);
      return aCost - bCost;
    });

    // Create a map of child IDs to names for badge display
    const childMap = {};
    children.forEach((child) => {
      childMap[child.id] = child.name;
    });

    return html`
      <ha-card>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:gift-outline"></ha-icon>
            <span class="header-title">${this.config.title}</span>
          </div>
          ${rewards.length > 0
            ? html`<span class="reward-count">${rewards.length} ${rewards.length === 1 ? "reward" : "rewards"}</span>`
            : ""}
        </div>

        <div class="card-content">
          ${sortedRewards.length === 0
            ? this._renderEmptyState()
            : sortedRewards.map((reward) => this._renderRewardRow(reward, pointsIcon, pointsName, childMap, children))}
        </div>
      </ha-card>
    `;
  }

  _renderEmptyState() {
    return html`
      <div class="empty-state">
        <ha-icon icon="mdi:gift-off-outline"></ha-icon>
        <div class="message">No Rewards Available</div>
        <div class="submessage">Add rewards in Choremander settings</div>
      </div>
    `;
  }

  _renderRewardRow(reward, pointsIcon, pointsName, childMap, children) {
    const rewardIcon = reward.icon || "mdi:gift";
    const hasDescription = reward.description && reward.description.trim().length > 0;
    const assignedTo = reward.assigned_to || [];
    const showChildBadges = this.config.show_child_badges !== false;
    const isJackpot = reward.is_jackpot || false;
    // Dynamic pricing is the default (override_point_value = false means dynamic)
    const isDynamicPricing = !reward.override_point_value;
    // Use per-child calculated cost
    const displayCost = this._getDisplayCost(reward, children);

    // Get relevant children for this reward
    const relevantChildren = assignedTo.length === 0
      ? children
      : children.filter(c => assignedTo.includes(c.id));

    // Calculate progress
    let currentStars = 0;
    let childContributions = [];

    if (isJackpot) {
      // Jackpot: calculate weighted contributions based on each child's expected share
      const childDailyPoints = reward.child_daily_points || {};
      const daysToGoal = reward.days_to_goal || 30;
      const totalDailyPoints = Object.values(childDailyPoints).reduce((sum, dp) => sum + dp, 0);

      relevantChildren.forEach((child, index) => {
        const points = child.points || 0;
        const dailyPoints = childDailyPoints[child.id] || 0;
        const expectedContribution = dailyPoints * daysToGoal;

        // Calculate weighted progress (0-100% of their expected share)
        let weightedProgress = 0;
        if (expectedContribution > 0) {
          weightedProgress = Math.min((points / expectedContribution) * 100, 100);
        }

        // Their "share" of the total goal (what % of the jackpot they're responsible for)
        let shareOfGoal = 0;
        if (totalDailyPoints > 0) {
          shareOfGoal = (dailyPoints / totalDailyPoints) * 100;
        }

        currentStars += points;
        childContributions.push({
          name: child.name,
          points: points,
          colorIndex: index % 6,
          expectedContribution: Math.round(expectedContribution),
          weightedProgress: weightedProgress,
          shareOfGoal: shareOfGoal,
          dailyPoints: dailyPoints
        });
      });
    } else {
      // Regular reward: show progress for filtered child or first assigned child
      if (this.config.child_id) {
        const filteredChild = children.find(c => c.id === this.config.child_id);
        currentStars = filteredChild ? (filteredChild.points || 0) : 0;
      } else if (relevantChildren.length > 0) {
        currentStars = relevantChildren[0].points || 0;
      }
    }

    const percentage = Math.min((currentStars / displayCost) * 100, 100);

    return html`
      <div class="reward-row ${isJackpot ? 'jackpot' : ''} ${isDynamicPricing ? 'dynamic' : ''}">
        <div class="cost-badge ${isDynamicPricing ? 'dynamic-cost' : ''}">
          <ha-icon icon="${pointsIcon}"></ha-icon>
          <span class="cost-value">${displayCost}</span>
          <span class="cost-label">${pointsName}</span>
          ${isDynamicPricing ? html`<span class="dynamic-indicator" title="Goal-based reward (${reward.days_to_goal || 30} days)">&#127919;</span>` : ''}
        </div>
        <div class="reward-details">
          ${isJackpot ? html`<div class="jackpot-label"><span>&#127920;</span> JACKPOT</div>` : ''}
          <div class="reward-name">${reward.name}</div>
          ${hasDescription
            ? html`<div class="reward-description">${reward.description}</div>`
            : ""}

          ${isJackpot
            ? this._renderJackpotProgress(reward, childContributions, currentStars, pointsIcon, displayCost)
            : this._renderRegularProgress(currentStars, displayCost, percentage, pointsIcon)}

          ${showChildBadges && !isJackpot
            ? html`
                <div class="assigned-children">
                  ${assignedTo.length === 0
                    ? html`<span class="child-badge all-children">All Children</span>`
                    : assignedTo.map(
                        (childId) =>
                          html`<span class="child-badge">${childMap[childId] || childId}</span>`
                      )}
                </div>
              `
            : ""}
        </div>
        <div class="reward-icon-container">
          <ha-icon icon="${rewardIcon}"></ha-icon>
        </div>
      </div>
    `;
  }

  _renderRegularProgress(currentStars, cost, percentage, pointsIcon) {
    return html`
      <div class="progress-section">
        <div class="progress-bar-container">
          <div class="progress-bar">
            <div class="progress-fill" style="width: ${percentage}%"></div>
          </div>
          <span class="progress-text">${currentStars}/${cost} <ha-icon icon="${pointsIcon}" style="--mdc-icon-size: 14px;"></ha-icon></span>
        </div>
      </div>
    `;
  }

  /**
   * Get the display cost for a reward based on child context.
   * For non-jackpot rewards, each child has their own calculated cost.
   * For jackpot rewards, all children share the same cost.
   */
  _getDisplayCost(reward, children) {
    const calculatedCosts = reward.calculated_costs || {};

    // If override_point_value is true, use manual cost
    if (reward.override_point_value) {
      return reward.cost;
    }

    // If filtering by a specific child, get that child's cost
    if (this.config.child_id && calculatedCosts[this.config.child_id]) {
      return calculatedCosts[this.config.child_id];
    }

    // For jackpot rewards, all children have the same cost - return first value
    if (reward.is_jackpot) {
      const costs = Object.values(calculatedCosts);
      if (costs.length > 0) {
        return costs[0];
      }
    }

    // For non-jackpot without specific child filter, get the first relevant child's cost
    const assignedTo = reward.assigned_to || [];
    if (assignedTo.length === 0) {
      // Available to all children - get first child's cost
      if (children.length > 0 && calculatedCosts[children[0].id]) {
        return calculatedCosts[children[0].id];
      }
    } else {
      // Get first assigned child's cost
      for (const childId of assignedTo) {
        if (calculatedCosts[childId]) {
          return calculatedCosts[childId];
        }
      }
    }

    // Fallback to manual cost
    return reward.cost;
  }

  _renderJackpotProgress(reward, childContributions, totalStars, pointsIcon, displayCost) {
    const cost = displayCost || reward.cost;

    // For weighted display: each child's segment shows their progress toward their expected share
    // The meter shows how much of their "responsibility" each child has fulfilled
    const hasWeightedData = childContributions.some(c => c.expectedContribution > 0);

    // Calculate weighted segments - each segment width = (child's share of goal) * (their progress %)
    // This way, if a child has 50% share and is at 100% progress, they fill 50% of the bar
    const segments = childContributions.map((contrib) => {
      let width = 0;
      if (hasWeightedData && contrib.shareOfGoal > 0) {
        // Weighted: segment width = share of goal * progress percentage
        // e.g., 40% share at 50% progress = 20% of bar filled
        width = (contrib.shareOfGoal / 100) * (contrib.weightedProgress / 100) * 100;
      } else {
        // Fallback: raw contribution relative to cost
        width = Math.min((contrib.points / cost) * 100, 100);
      }
      return {
        ...contrib,
        width: width
      };
    });

    // Calculate total percentage for display
    const totalPercentage = Math.min((totalStars / cost) * 100, 100);

    return html`
      <div class="progress-section">
        <div class="progress-bar-container">
          <div class="jackpot-progress-bar">
            ${segments.map((seg) => html`
              <div class="jackpot-segment color-${seg.colorIndex}"
                   style="width: ${seg.width}%"></div>
            `)}
          </div>
          <span class="progress-text">${totalStars}/${cost} <ha-icon icon="${pointsIcon}" style="--mdc-icon-size: 14px;"></ha-icon></span>
        </div>
        <div class="jackpot-breakdown">
          ${childContributions.map((contrib) => html`
            <span class="jackpot-child-contribution" title="${hasWeightedData ? `Expected: ${contrib.expectedContribution}, Progress: ${Math.round(contrib.weightedProgress)}%` : ''}">
              <span class="color-dot color-${contrib.colorIndex}"></span>
              ${contrib.name}: ${hasWeightedData ? html`${Math.round(contrib.weightedProgress)}%` : html`${contrib.points} <ha-icon icon="${pointsIcon}" style="--mdc-icon-size: 12px;"></ha-icon>`}
            </span>
          `)}
          ${childContributions.length > 1 ? html`
            <span class="jackpot-total">${totalStars}/${cost} total</span>
          ` : ''}
        </div>
      </div>
    `;
  }
}

// Card Editor for visual configuration in Lovelace UI
class ChoremanderRewardsCardEditor extends LitElement {
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

      .form-group input[type="text"]:focus,
      .form-group select:focus {
        outline: none;
        border-color: var(--primary-color);
      }

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

      .form-group label input[type="checkbox"] {
        margin-right: 8px;
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

    // Get children from the entity for the dropdown
    const entity = this.config.entity ? this.hass.states[this.config.entity] : null;
    const children = entity?.attributes?.children || [];

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
          placeholder="Rewards"
        />
        <small>Card title displayed in the header (default: "Rewards")</small>
      </div>

      <div class="form-group">
        <label>Filter by Child</label>
        <select @change="${this._childIdChanged}">
          <option value="" ?selected="${!this.config.child_id}">All Children</option>
          ${children.map(
            (child) => html`
              <option value="${child.id}" ?selected="${this.config.child_id === child.id}">
                ${child.name}
              </option>
            `
          )}
        </select>
        <small>Only show rewards available to this child (leave empty for all rewards)</small>
      </div>

      <div class="form-group">
        <label>
          <input
            type="checkbox"
            ?checked="${this.config.show_child_badges !== false}"
            @change="${this._showChildBadgesChanged}"
          />
          Show child assignment badges
        </label>
        <small>Display which children can claim each reward</small>
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
    const value = e.target.value;
    this._updateConfig("child_id", value || null);
  }

  _showChildBadgesChanged(e) {
    this._updateConfig("show_child_badges", e.target.checked);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === undefined || value === "" || value === null) {
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
customElements.define("choremander-rewards-card", ChoremanderRewardsCard);
customElements.define("choremander-rewards-card-editor", ChoremanderRewardsCardEditor);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "choremander-rewards-card",
  name: "Choremander Rewards Card",
  description: "A card displaying available rewards with star costs",
  preview: true,
});

console.info(
  "%c CHOREMANDER-REWARDS-CARD %c v0.0.7 ",
  "background: #9b59b6; color: white; font-weight: bold; border-radius: 4px 0 0 4px;",
  "background: #f1c40f; color: #333; font-weight: bold; border-radius: 0 4px 4px 0;"
);
