/**
 * TaskMate Rewards Card
 * A Lovelace card for displaying available rewards.
 * Shows rewards in a vertical list with star cost, name, description, and progress gauges.
 * Supports regular rewards, Jackpot rewards, and (v3.0+) Pool Mode "savings jar" rewards.
 *
 * Version: 0.1.3
 * Last Updated: 2026-04-17
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateRewardsCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _loading: { type: Object },
      _selectedChildId: { type: String },
      _pendingClaim: { type: Object },
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

  constructor() {
    super();
    this._loading = {};
    this._selectedChildId = null;
    this._pendingClaim = null;
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  static get styles() {
    const base = css`
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
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #e67e22);
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

      /* ── Child tabs (shown when no child_id is pinned and 2+ children) ── */
      .child-tabs {
        display: flex;
        gap: 6px;
        padding: 12px 16px 0;
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
        background: var(--divider, rgba(0, 0, 0, 0.08));
        border: 2px solid transparent;
        cursor: pointer;
        font-size: 0.9rem;
        font-weight: 500;
        white-space: nowrap;
        color: var(--text-secondary, #666);
        transition: all 0.15s;
      }
      .child-tab ha-icon { --mdc-icon-size: 18px; }
      .child-tab.selected {
        background: color-mix(in srgb, var(--taskmate-header-bg, #e67e22) 16%, transparent);
        border-color: var(--taskmate-header-bg, #e67e22);
        color: var(--taskmate-header-bg, #e67e22);
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
        background: var(--divider-color, #e0e0e0);
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
        background: var(--divider-color, #e0e0e0);
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
        background: color-mix(in srgb, var(--primary-text-color, #212121) 8%, transparent);
        border-radius: 10px;
        font-weight: 500;
      }

      .jackpot-child-contribution .color-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      .jackpot-child-contribution ha-icon {
        --mdc-icon-size: 13px;
        vertical-align: middle;
        position: relative;
        top: -1px;
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

      /* Reward icon + claim button wrapper */
      /* Child picker shown when no child_id configured */
      .child-picker-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 16px;
        background: var(--secondary-background-color, #f5f5f5);
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }

      .child-picker-label {
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        white-space: nowrap;
      }

      .child-picker-select {
        flex: 1;
        padding: 5px 8px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 6px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 0.85rem;
        cursor: pointer;
      }

      .reward-right-col {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        flex-shrink: 0;
      }

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

      /* Pending approval state */
      .reward-row.pending-approval {
        opacity: 0.6;
        border-left: 3px solid #e67e22;
      }

      .pending-label {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: rgba(230,126,34,0.12);
        color: #e67e22;
        border-radius: 8px;
        padding: 3px 8px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 4px;
      }

      .pending-label ha-icon { --mdc-icon-size: 12px; }

      /* Availability badges (low stock / sold out / expiring / expired) */
      .availability-badges { display: inline-flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
      .availability-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 8px;
        padding: 3px 8px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.02em;
      }
      .availability-badge.badge-sold-out {
        background: rgba(189,195,199,0.25);
        color: var(--secondary-text-color, #757575);
      }
      .availability-badge.badge-expired {
        background: color-mix(in srgb, var(--secondary-text-color, #757575) 18%, transparent);
        color: var(--secondary-text-color, #757575);
      }
      .availability-badge.badge-low-stock {
        background: rgba(231,76,60,0.15);
        color: #c0392b;
      }
      .availability-badge.badge-expiring-soon {
        background: rgba(243,156,18,0.18);
        color: #d35400;
      }
      .reward-row.unavailable { opacity: 0.55; }

      /* Claim button */
      .claim-btn {
        width: 42px; height: 42px;
        border-radius: 50%; border: none; cursor: pointer;
        background: linear-gradient(135deg, #9b59b6, #8e44ad);
        color: white;
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 3px 10px rgba(155,89,182,0.35);
        transition: transform 0.15s, box-shadow 0.15s;
        flex-shrink: 0;
      }

      .claim-btn:hover { transform: scale(1.08); box-shadow: 0 4px 14px rgba(155,89,182,0.45); }
      .claim-btn:active { transform: scale(0.96); }
      .claim-btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
      .claim-btn ha-icon { --mdc-icon-size: 22px; }

      .claim-btn.cant-afford {
        background: linear-gradient(135deg, #bdc3c7, #95a5a6);
        box-shadow: none;
        cursor: not-allowed;
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
          padding: 14px 18px;
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

      /* v3.0 Pool Mode styles */
      .spendable-banner {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 14px;
        margin: 8px 14px 0 14px;
        background: linear-gradient(135deg, rgba(52, 152, 219, 0.15), rgba(46, 204, 113, 0.12));
        border-radius: 10px;
        border: 1px solid rgba(52, 152, 219, 0.25);
      }

      .spendable-banner ha-icon {
        color: var(--reward-purple);
        --mdc-icon-size: 22px;
      }

      .spendable-banner .spendable-label {
        color: var(--text-secondary);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      .spendable-banner .spendable-value {
        font-weight: 700;
        font-size: 1.15rem;
        color: var(--text-primary);
        margin-left: auto;
      }

      .spendable-banner .spendable-of {
        font-weight: 400;
        color: var(--text-secondary);
        font-size: 0.82rem;
        margin-left: 4px;
      }

      /* Pool Mode controls — render BELOW the progress bar, full width */
      .pool-controls {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        justify-content: flex-start;
        margin-top: 4px;
      }

      .pool-controls-redeem {
        justify-content: flex-start;
      }

      .alloc-btn {
        flex: 1 1 0;
        min-width: 56px;
        padding: 7px 10px;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        background: linear-gradient(135deg, #3498db, #2980b9);
        color: white;
        font-weight: 700;
        font-size: 0.9rem;
        transition: transform 0.1s, opacity 0.1s, box-shadow 0.15s;
        box-shadow: 0 1px 3px rgba(52, 152, 219, 0.3);
      }

      .alloc-btn:hover:not(:disabled) {
        transform: scale(1.04);
        box-shadow: 0 2px 6px rgba(52, 152, 219, 0.5);
      }

      .alloc-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }

      /* Custom-amount deposit (#559): sits beside the quick buttons, wraps
         below them on narrow widths. */
      .deposit-custom {
        display: flex;
        align-items: stretch;
        gap: 6px;
        margin-left: auto;
        flex: 0 0 auto;
      }
      .deposit-custom input {
        width: 72px;
        min-width: 0;
        padding: 7px 8px;
        border-radius: 8px;
        border: 1px solid var(--divider-color, rgba(0, 0, 0, 0.18));
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color, #111);
        font-size: 0.9rem;
        font-weight: 600;
        text-align: center;
      }
      .deposit-custom input:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      .deposit-custom .alloc-btn.deposit-add {
        flex: 0 0 auto;
        min-width: 0;
      }
      /* Hide the number spinners for a cleaner look */
      .deposit-custom input::-webkit-outer-spin-button,
      .deposit-custom input::-webkit-inner-spin-button {
        -webkit-appearance: none;
        margin: 0;
      }
      .deposit-custom input[type="number"] { -moz-appearance: textfield; }

      .redeem-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        flex: 1 1 auto;
        padding: 9px 18px;
        border-radius: 20px;
        border: none;
        cursor: pointer;
        background: linear-gradient(135deg, #2ecc71, #27ae60);
        color: white;
        font-weight: 700;
        font-size: 0.95rem;
        box-shadow: 0 3px 10px rgba(46, 204, 113, 0.35);
        animation: pulse-green 1.6s ease-in-out infinite;
      }

      .redeem-btn ha-icon {
        --mdc-icon-size: 18px;
      }

      @keyframes pulse-green {
        0%, 100% { box-shadow: 0 3px 10px rgba(46, 204, 113, 0.35); transform: scale(1); }
        50% { box-shadow: 0 3px 18px rgba(46, 204, 113, 0.65); transform: scale(1.02); }
      }

      .pool-locked-note {
        font-size: 0.72rem;
        color: var(--text-secondary);
        font-style: italic;
        margin-top: 4px;
      }

      .confirm-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
      }
      .confirm-dialog {
        background: var(--card-background-color, #fff);
        border-radius: 16px;
        padding: 24px;
        max-width: 320px;
        width: 90%;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .confirm-dialog .dialog-icon {
        display: flex;
        justify-content: center;
        --mdc-icon-size: 48px;
        color: var(--reward-purple);
      }
      .confirm-dialog .dialog-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: var(--primary-text-color);
        text-align: center;
      }
      .confirm-dialog .dialog-body {
        font-size: 0.9rem;
        color: var(--secondary-text-color);
        text-align: center;
        line-height: 1.5;
      }
      .confirm-dialog .dialog-buttons {
        display: flex;
        gap: 10px;
      }
      .confirm-dialog button {
        flex: 1;
        padding: 10px;
        border: none;
        border-radius: 8px;
        font-size: 0.95rem;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
      }
      .confirm-dialog button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      }
      .confirm-dialog button:active {
        transform: scale(0.97);
      }
      .confirm-dialog .btn-cancel {
        background: var(--secondary-background-color, #f5f5f5);
        color: var(--primary-text-color);
      }
      .confirm-dialog .btn-confirm {
        background: linear-gradient(135deg, var(--reward-purple) 0%, var(--reward-purple-light) 100%);
        color: white;
      }
      .dialog-points-summary {
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 8px;
        padding: 10px 14px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        font-size: 0.9rem;
        text-align: left;
      }
      .dialog-points-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: var(--primary-text-color);
      }
      .dialog-points-row.cost {
        color: var(--secondary-text-color);
        border-top: 1px solid var(--divider-color, #e0e0e0);
        padding-top: 6px;
      }
      .dialog-points-row.remaining {
        font-weight: 700;
        border-top: 1px solid var(--divider-color, #e0e0e0);
        padding-top: 6px;
        color: var(--reward-purple);
      }
      .points-val {
        display: flex;
        align-items: center;
        gap: 2px;
        font-weight: 600;
      }

      /* ── Designed (playroom / console / cleanpro) — shared .tmd kit comes
         from taskmate-design.js styles(); only card-specific layout below. ── */
      .rw-list { display: flex; flex-direction: column; gap: 11px; }
      /* #604: default is fluid — the list grows to fit every reward. Opt into a
         fixed 360px scroll region with expand_to_fit: false. */
      .rw-list.rw-scroll { max-height: 360px; overflow-y: auto; }
      .rw-jackpot-label { align-self: flex-start; background: var(--tmd-gold); color: #3a2e26;
                          border-color: transparent; font-weight: 800; text-transform: uppercase;
                          letter-spacing: 0.04em; font-size: 10.5px; margin-bottom: 2px; }
      .rw-badges { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
      .rw-badge { font-size: 11px; padding: 2px 8px; }
      .rw-badge-all { background: color-mix(in srgb, var(--tmd-good) 16%, transparent);
                      color: var(--tmd-good); border-color: transparent; }
      .rw-tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 2px; }
      .rw-sel { background: var(--tmd-surface-2); border: 1px solid var(--tmd-border);
                border-radius: var(--tmd-radius-sm); padding: 9px 12px; }
      .rw-sel-name { flex: 1; min-width: 0; font-weight: 800; }
      .rw-card { background: var(--tmd-surface-2); border: 1px solid var(--tmd-border);
                 border-radius: var(--tmd-radius-sm); padding: 13px; display: flex;
                 flex-direction: column; gap: 9px; }
      .rw-card.rw-unavail { opacity: 0.55; }
      .rw-jackpot { border: 2px dashed var(--tmd-accent);
                    background: color-mix(in srgb, var(--tmd-accent) 9%, var(--tmd-surface-2)); }
      .rw-top { align-items: flex-start; }
      .rw-emoji { font-size: 28px; line-height: 1; flex: none; }
      .rw-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 3px; }
      .rw-name { font-weight: 800; font-size: 15px; }
      .rw-desc { font-size: 12px; }
      .rw-avail { align-self: flex-start; font-size: 11px; }
      .rw-avail-warn { background: color-mix(in srgb, var(--tmd-warn) 16%, transparent);
                       color: var(--tmd-warn); }
      .rw-avail-bad { background: color-mix(in srgb, var(--tmd-bad) 16%, transparent);
                      color: var(--tmd-bad); }
      .rw-cost { flex: none; align-self: flex-start; background: var(--tmd-gold);
                 color: #3a2e26; border-color: transparent; font-weight: 800; }
      .rw-pool-bar { height: 14px; display: flex; gap: 0; padding: 0; }
      .rw-pool-bar > i { border-radius: 0; }
      .rw-pool-foot { flex-wrap: wrap; gap: 6px; }
      .rw-contrib { gap: 5px; font-size: 11px; }
      .rw-foot { gap: 8px; }
      .rw-status { font-size: 12px; }
      .rw-status-good { color: var(--tmd-good); font-weight: 800; }
      .rw-pool-btns { gap: 6px; flex-wrap: wrap; align-items: center; }
      .rw-pool-btns .deposit-custom { margin-left: auto; gap: 6px; }
      .rw-deposit-input {
        width: 70px;
        min-width: 0;
        padding: 7px 8px;
        border-radius: var(--tmd-radius-sm);
        border: 1px solid var(--tmd-border);
        background: var(--tmd-surface);
        color: var(--tmd-text);
        font-size: 13px;
        font-weight: 700;
        text-align: center;
      }
      .rw-deposit-input:disabled { opacity: 0.4; cursor: not-allowed; }
      .rw-deposit-input::-webkit-outer-spin-button,
      .rw-deposit-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
      .rw-deposit-input[type="number"] { -moz-appearance: textfield; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error(this._t('rewards.error.entity_required'));
    }
    this.config = {
      title: null,
      child_id: null, // Optional: filter rewards for a specific child
      show_child_badges: true, // Show which children can claim each reward
      enable_pool_mode: false, // v3.0: "savings jar" allocation mode (opt-in per card)
      expand_to_fit: true, // #604: grow the card to fit all rewards (designed styles). false = fixed 360px scroll.
      deposit_amounts: [1, 5, 10], // #559: quick-deposit button amounts for pool/jackpot rewards
      header_color: '#e67e22',
      ...config,
    };
  }

  getCardSize() {
    return 3;
  }

  static getConfigElement() {
    return document.createElement("taskmate-rewards-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.taskmate_overview",
      title: "Rewards",
      child_id: null,
      show_child_badges: true,
      enable_pool_mode: false,
    };
  }

  willUpdate() {
    // #547: when the card isn't pinned to a child via config.child_id, default the
    // in-card selection to the first child so the claim button renders (and the
    // child tabs have a selection). Without this, childId stays null and no claim
    // button is ever shown, making rewards impossible to claim.
    if (this.hass && this.config && !this.config.child_id && !this._selectedChildId) {
      const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
        || this.hass.states?.[this.config.entity]?.attributes || {};
      const kids = attrs.children || [];
      if (kids.length) this._selectedChildId = kids[0].id;
    }
  }

  _selectChild(id) {
    this._selectedChildId = id;
  }

  // Classic child picker — shown only when no child_id is pinned and 2+ children.
  _renderChildTabs(children) {
    if (this.config.child_id || children.length <= 1) return html``;
    const activeId = this._selectedChildId || children[0]?.id;
    return html`
      <div class="child-tabs">
        ${children.map((c) => html`
          <div class="child-tab ${activeId === c.id ? 'selected' : ''}"
               @click=${() => this._selectChild(c.id)}>
            <ha-icon icon="${c.avatar || 'mdi:account-circle'}"></ha-icon>
            ${c.name}
          </div>
        `)}
      </div>
    `;
  }

  // Designed-style child picker (reuses the .btn sm button styling).
  _designChildTabs(children) {
    if (this.config.child_id || children.length <= 1) return html``;
    const activeId = this._selectedChildId || children[0]?.id;
    return html`
      <div class="row rw-tabs">
        ${children.map((c) => html`
          <button class="btn sm ${activeId === c.id ? 'good' : 'ghost'}"
                  @click=${() => this._selectChild(c.id)}>${c.name}</button>
        `)}
      </div>
    `;
  }

  render() {
    if (!this.hass || !this.config) {
      return html``;
    }

    const design = window.__taskmate_design
      ? window.__taskmate_design.apply(this, this.hass, this.config, this.config.entity)
      : "classic";
    if (design !== "classic") return this._renderDesigned(design);

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
    const allRewards = attrs.rewards || [];
    const children = attrs.children || [];
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t("common.stars");

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

    // Card-level override: when true, every reward on this card is treated as a pool reward.
    // Otherwise each reward decides for itself via reward.pool_enabled.
    const cardForcesPool = this.config.enable_pool_mode === true;
    const activeChildId = this.config.child_id || this._selectedChildId;
    const activeChild = activeChildId ? children.find((c) => c.id === activeChildId) : null;
    // Show the spendable banner when any visible reward is in pool mode
    const anyPoolReward = sortedRewards.some(
      (r) => cardForcesPool || r.pool_enabled === true || r.is_jackpot
    );

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, '#e67e22')}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:gift-outline"></ha-icon>
            <span class="header-title">${this.config.title || this._t('rewards.default_title')}</span>
          </div>
          ${rewards.length > 0
            ? html`<span class="reward-count">${rewards.length === 1 ? this._t('rewards.reward_count_singular', { count: rewards.length }) : this._t('rewards.reward_count_plural', { count: rewards.length })}</span>`
            : ""}
        </div>

        ${this._renderChildTabs(children)}

        ${anyPoolReward && activeChild ? this._renderSpendableBanner(activeChild, pointsIcon, pointsName) : ''}

        <div class="card-content">
          ${sortedRewards.length === 0
            ? this._renderEmptyState()
            : sortedRewards.map((reward) => this._renderRewardRow(reward, pointsIcon, pointsName, childMap, children))}
        </div>
      </ha-card>

      ${this._pendingClaim ? html`
        <div class="confirm-overlay" @click="${this._cancelClaim}">
          <div class="confirm-dialog" @click="${(e) => e.stopPropagation()}">
            <ha-icon class="dialog-icon" icon="mdi:gift-outline"></ha-icon>
            <div class="dialog-title">${this._t('rewards.confirm_title')}</div>
            <div class="dialog-body">
              ${(() => {
                const r = this._pendingClaim;
                const child = r._child;
                const cost = r.cost;
                // Pool/jackpot redemptions spend POOLED points, not the claiming
                // child's wallet. Showing the child's balance vs the full cost
                // produced a nonsensical negative "Remaining" (#557). Use the pool
                // total (jackpot: summed across all children; savings-jar: this
                // child's allocation) so the calculation reflects the pooled points.
                const isJackpot = r.is_jackpot === true;
                const isPoolRedeem = isJackpot || r.pool_enabled === true || this.config.enable_pool_mode === true;
                let currentPoints;
                let availableLabel;
                if (isPoolRedeem) {
                  const poolAllocations = r.pool_allocations || {};
                  currentPoints = isJackpot
                    ? (typeof r.jackpot_pool_total === 'number' ? r.jackpot_pool_total : 0)
                    : (child ? (poolAllocations[child.id] || 0) : 0);
                  availableLabel = this._t('rewards.confirm_pool_total');
                } else {
                  currentPoints = child ? (typeof child.spendable_balance === 'number' ? child.spendable_balance : (child.points || 0)) : null;
                  availableLabel = this._t('rewards.confirm_your_points', { name: pointsName });
                }
                const remaining = currentPoints !== null ? currentPoints - cost : null;
                return html`
                  <div style="margin-bottom: 12px;">${this._t('rewards.confirm_body', { name: r.name })}</div>
                  ${currentPoints !== null ? html`
                    <div class="dialog-points-summary">
                      <div class="dialog-points-row">
                        <span>${availableLabel}</span>
                        <span class="points-val">
                          <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:14px;"></ha-icon>
                          ${currentPoints}
                        </span>
                      </div>
                      <div class="dialog-points-row cost">
                        <span>${this._t('rewards.confirm_cost')}</span>
                        <span class="points-val">
                          <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:14px;"></ha-icon>
                          −${cost}
                        </span>
                      </div>
                      <div class="dialog-points-row remaining">
                        <span>${this._t('rewards.confirm_remaining')}</span>
                        <span class="points-val">
                          <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:14px;"></ha-icon>
                          ${remaining}
                        </span>
                      </div>
                    </div>
                  ` : ''}
                `;
              })()}
            </div>
            <div class="dialog-buttons">
              <button class="btn-cancel" @click="${this._cancelClaim}">${this._t('common.cancel')}</button>
              <button class="btn-confirm" @click="${this._confirmClaim}">${this._t('rewards.confirm_claim_btn')}</button>
            </div>
          </div>
        </div>
      ` : ""}
    `;
  }

  _renderSpendableBanner(child, pointsIcon, pointsName) {
    const spendable = typeof child.spendable_balance === 'number' ? child.spendable_balance : (child.points || 0);
    const gross = child.points || 0;
    // Only show "/ gross" when points are reserved by a pending claim.
    const detail = spendable !== gross
      ? html`<span class="spendable-of">/ ${gross} ${pointsName}</span>`
      : html`<span class="spendable-of">${pointsName}</span>`;
    return html`
      <div class="spendable-banner">
        <ha-icon icon="${pointsIcon}"></ha-icon>
        <span class="spendable-label">${this._t('rewards.spendable_balance')}</span>
        <span class="spendable-value">
          ${spendable}
          ${detail}
        </span>
      </div>
    `;
  }

  _renderEmptyState() {
    return html`
      <div class="empty-state">
        <ha-icon icon="mdi:gift-off-outline"></ha-icon>
        <div class="message">${this._t('rewards.empty_title')}</div>
        <div class="submessage">${this._t('rewards.empty_subtitle')}</div>
      </div>
    `;
  }

  _renderRewardRow(reward, pointsIcon, pointsName, childMap, children) {
    const rewardIcon = reward.icon || "mdi:gift";
    const hasDescription = reward.description && reward.description.trim().length > 0;
    const assignedTo = reward.assigned_to || [];
    const showChildBadges = this.config.show_child_badges !== false;
    const isJackpot = reward.is_jackpot || false;
    // Pool mode is enabled per-reward (reward.pool_enabled) OR forced on via card config.
    const cardForcesPool = this.config.enable_pool_mode === true;
    // Jackpot rewards are always pool-mode (#552): everyone deposits into the
    // shared jar and it's redeemed when full. Combined points only work via the
    // pool, so jackpots never show the single-child claim button.
    const enablePoolMode = cardForcesPool || reward.pool_enabled === true || isJackpot;
    // All costs are static — just use reward.cost
    const displayCost = this._getDisplayCost(reward, children);

    // Get relevant children for this reward
    const relevantChildren = assignedTo.length === 0
      ? children
      : children.filter(c => assignedTo.includes(c.id));

    // Determine active child context
    const childId = this.config?.child_id || this._selectedChildId;
    const relevantChild = childId
      ? children.find(c => c.id === childId)
      : relevantChildren[0];

    // Pool allocations for this reward (v3.0). Falls back to empty dict in wallet mode.
    const poolAllocations = reward.pool_allocations || {};
    const jackpotPoolTotal = typeof reward.jackpot_pool_total === 'number' ? reward.jackpot_pool_total : 0;

    // Calculate progress
    let currentStars = 0;
    let childContributions = [];

    if (isJackpot) {
      const sharePerChild = relevantChildren.length > 0
        ? Math.round(displayCost / relevantChildren.length)
        : displayCost;

      relevantChildren.forEach((child, index) => {
        // In pool mode, show allocated points only; in wallet mode show wallet points
        const points = enablePoolMode
          ? (poolAllocations[child.id] || 0)
          : (child.points || 0);
        const shareOfGoal = relevantChildren.length > 0 ? (100 / relevantChildren.length) : 100;
        const weightedProgress = sharePerChild > 0 ? Math.min((points / sharePerChild) * 100, 100) : 0;

        currentStars += points;
        childContributions.push({
          name: child.name,
          points: points,
          colorIndex: index % 6,
          expectedContribution: sharePerChild,
          weightedProgress: weightedProgress,
          shareOfGoal: shareOfGoal,
        });
      });
    } else {
      if (enablePoolMode) {
        // Pool mode: show this child's allocation for this reward
        currentStars = childId ? (poolAllocations[childId] || 0) : 0;
      } else if (this.config.child_id) {
        const filteredChild = children.find(c => c.id === this.config.child_id);
        currentStars = filteredChild ? (filteredChild.points || 0) : 0;
      } else if (relevantChildren.length > 0) {
        currentStars = relevantChildren[0].points || 0;
      }
    }

    const percentage = displayCost > 0 ? Math.min((currentStars / displayCost) * 100, 100) : 0;

    // Pending claim check
    const pcAttrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity)) || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const pendingClaims = pcAttrs.pending_reward_claims || [];
    const hasPendingClaim = pendingClaims.some(c =>
      c.reward_id === reward.id && (!childId || c.child_id === childId)
    );

    // Pool mode affordability / redeem state
    const spendable = relevantChild
      ? (typeof relevantChild.spendable_balance === 'number'
          ? relevantChild.spendable_balance
          : (relevantChild.points || 0) - (relevantChild.committed_points || 0))
      : 0;
    const poolFull = enablePoolMode && (
      isJackpot ? jackpotPoolTotal >= displayCost : currentStars >= displayCost
    );

    // Wallet mode: affordability based on gross − committed
    const committedPoints = relevantChild?.committed_points || 0;
    const availablePoints = (relevantChild?.points || 0) - committedPoints;
    const canAfford = relevantChild && availablePoints >= displayCost;
    const isLoading = this._loading[reward.id];
    const isAllocLoading = this._loading[`${reward.id}_alloc`];

    // Availability (quantity / expiration)
    const isSoldOut = reward.is_sold_out === true;
    const isExpired = reward.is_expired === true;
    const isUnavailable = isSoldOut || isExpired;
    const daysUntilExpiry = (typeof reward.days_until_expiry === 'number')
      ? reward.days_until_expiry
      : null;
    const availabilityBadge = this._renderAvailabilityBadge(reward, isSoldOut, isExpired, daysUntilExpiry);

    // Pool-mode controls render below the progress bar (full width) rather than
    // in the right column, so the progress bar keeps its full width.
    const showPoolControls = enablePoolMode && childId && !hasPendingClaim && !isUnavailable;

    return html`
      <div class="reward-row ${isJackpot ? 'jackpot' : ''} ${hasPendingClaim ? 'pending-approval' : ''} ${enablePoolMode ? 'pool-mode' : ''} ${isUnavailable ? 'unavailable' : ''}">
        <div class="cost-badge">
          <ha-icon icon="${pointsIcon}"></ha-icon>
          <span class="cost-value">${displayCost}</span>
          <span class="cost-label">${pointsName}</span>
        </div>
        <div class="reward-details">
          ${isJackpot ? html`<div class="jackpot-label"><span>&#127920;</span> ${this._t('rewards.jackpot')}</div>` : ''}
          <div class="reward-name">${reward.name}</div>
          ${availabilityBadge}
          ${hasDescription
            ? html`<div class="reward-description">${reward.description}</div>`
            : ""}

          ${isJackpot
            ? this._renderJackpotProgress(reward, childContributions, currentStars, pointsIcon, displayCost)
            : this._renderRegularProgress(currentStars, displayCost, percentage, pointsIcon)}

          ${showPoolControls
            ? this._renderPoolControls(reward, relevantChild, spendable, poolFull, isAllocLoading, isLoading)
            : ''}

          ${hasPendingClaim ? html`
            <div class="pending-label">
              <ha-icon icon="mdi:clock-outline"></ha-icon>
              ${this._t('rewards.awaiting_approval')}
            </div>
          ` : ''}

          ${showChildBadges && !isJackpot
            ? html`
                <div class="assigned-children">
                  ${assignedTo.length === 0
                    ? html`<span class="child-badge all-children">${this._t('rewards.all_children')}</span>`
                    : assignedTo.map(
                        (cid) =>
                          html`<span class="child-badge">${childMap[cid] || cid}</span>`
                      )}
                </div>
              `
            : ""}
        </div>
        <div class="reward-right-col">
          ${!enablePoolMode && !hasPendingClaim && childId && !isUnavailable ? html`
            <button
              class="claim-btn ${!canAfford ? 'cant-afford' : ''}"
              ?disabled="${!canAfford || isLoading}"
              @click="${(e) => { e.stopPropagation(); this._promptClaim(reward, relevantChild); }}"
              title="${canAfford ? this._t('rewards.claim_reward') : this._t('rewards.not_enough_points')}"
            >
              <ha-icon icon="${isLoading ? 'mdi:loading' : rewardIcon}"></ha-icon>
            </button>
          ` : html`
            <div class="reward-icon-container" title="${isUnavailable ? this._t('rewards.unavailable_hint') : ''}">
              <ha-icon icon="${rewardIcon}"></ha-icon>
            </div>
          `}
        </div>
      </div>
    `;
  }

  _renderAvailabilityBadge(reward, isSoldOut, isExpired, daysUntilExpiry) {
    if (isExpired) {
      return html`<div class="availability-badge badge-expired">${this._t('rewards.expired')}</div>`;
    }
    if (isSoldOut) {
      return html`<div class="availability-badge badge-sold-out">${this._t('rewards.sold_out')}</div>`;
    }
    const badges = [];
    if (typeof reward.quantity === 'number' && reward.quantity > 0 && reward.quantity <= 3) {
      badges.push(html`<div class="availability-badge badge-low-stock">${this._t('rewards.only_n_left', { count: reward.quantity })}</div>`);
    }
    if (typeof daysUntilExpiry === 'number' && daysUntilExpiry >= 0 && daysUntilExpiry <= 7) {
      const label = daysUntilExpiry === 0
        ? this._t('rewards.expires_today')
        : (daysUntilExpiry === 1
            ? this._t('rewards.expires_in_days', { count: daysUntilExpiry })
            : this._t('rewards.expires_in_days_plural', { count: daysUntilExpiry }));
      badges.push(html`<div class="availability-badge badge-expiring-soon">${label}</div>`);
    }
    if (badges.length === 0) return '';
    return html`<div class="availability-badges">${badges}</div>`;
  }

  _renderPoolControls(reward, child, spendable, poolFull, isAllocLoading, isRedeemLoading) {
    if (poolFull) {
      return html`
        <div class="pool-controls pool-controls-redeem">
          <button
            class="redeem-btn"
            ?disabled="${isRedeemLoading}"
            @click="${(e) => { e.stopPropagation(); this._handleRedeem(reward, child); }}"
            title="${this._t('rewards.redeem')}"
          >
            <ha-icon icon="${isRedeemLoading ? 'mdi:loading' : 'mdi:check-circle'}"></ha-icon>
            ${this._t('rewards.redeem')}
          </button>
        </div>
      `;
    }
    const amounts = this._quickDepositAmounts();
    return html`
      <div class="pool-controls">
        ${amounts.map((amt) => {
          const disabled = !child || spendable < amt || isAllocLoading;
          const tooltip = this._depositTooltip({ child, spendable, amt, isAllocLoading });
          return html`
            <button
              class="alloc-btn"
              ?disabled="${disabled}"
              @click="${(e) => { e.stopPropagation(); this._handleAllocate(reward, child, amt); }}"
              title="${tooltip}"
              aria-label="${tooltip}"
            >+${amt}</button>
          `;
        })}
        ${this._renderCustomDeposit(reward, child, spendable, isAllocLoading)}
      </div>
    `;
  }

  _depositTooltip({ child, spendable, amt, isAllocLoading }) {
    if (isAllocLoading) return this._t('rewards.deposit_disabled_loading');
    if (!child) return this._t('rewards.deposit_disabled_no_child');
    if (spendable < amt) {
      return this._t('rewards.deposit_disabled_insufficient', { spendable });
    }
    return this._t('rewards.deposit_points', { amount: amt });
  }

  /**
   * Quick-deposit button amounts from config.deposit_amounts (#559). Sanitised
   * to positive integers (deduped, order preserved); falls back to [1, 5, 10]
   * when unset or invalid so existing cards are unaffected.
   */
  _quickDepositAmounts() {
    const raw = this.config && this.config.deposit_amounts;
    if (Array.isArray(raw)) {
      const cleaned = [];
      for (const v of raw) {
        const n = Math.floor(Number(v));
        if (Number.isFinite(n) && n >= 1 && !cleaned.includes(n)) cleaned.push(n);
      }
      if (cleaned.length) return cleaned;
    }
    return [1, 5, 10];
  }

  /**
   * Deposit a typed custom amount (#559). The <input> is uncontrolled — we read
   * it from the DOM on submit so keystrokes don't trigger re-renders (which
   * would steal focus). The backend silently caps the amount to the child's
   * spendable balance and the pool's remaining room.
   */
  _handleCustomDeposit(reward, child, e) {
    const wrap = e.target.closest(".deposit-custom");
    const input = wrap && wrap.querySelector("input");
    if (!input) return;
    const amount = Math.floor(Number(input.value));
    if (!Number.isFinite(amount) || amount < 1) return;
    input.value = "";
    this._handleAllocate(reward, child, amount);
  }

  /**
   * The "type any amount + Add" control shown beside the quick-deposit buttons.
   * Shared by the classic and designed layouts; `cls` carries layout-specific
   * button/input classes so each matches its surrounding style.
   */
  _renderCustomDeposit(reward, child, spendable, isAllocLoading, cls = {}) {
    if (!child) return "";
    const disabled = spendable < 1 || isAllocLoading;
    const inputCls = cls.input || "";
    const btnCls = cls.button || "alloc-btn";
    const submit = (e) => { e.stopPropagation(); this._handleCustomDeposit(reward, child, e); };
    return html`
      <span class="deposit-custom">
        <input
          type="number" min="1" inputmode="numeric"
          class="${inputCls}"
          placeholder="${this._t('rewards.deposit_custom_placeholder')}"
          aria-label="${this._t('rewards.deposit_custom_label')}"
          ?disabled="${disabled}"
          @click="${(e) => e.stopPropagation()}"
          @keydown="${(e) => { if (e.key === 'Enter') { e.preventDefault(); submit(e); } }}"
        >
        <button
          class="${btnCls} deposit-add"
          ?disabled="${disabled}"
          @click="${submit}"
          title="${this._t('rewards.deposit_custom_add')}"
        >${this._t('rewards.deposit_custom_add')}</button>
      </span>
    `;
  }

  _promptClaim(reward, child) {
    if (!child || !reward) return;
    this._pendingClaim = { ...reward, _child: child };
  }

  _cancelClaim() {
    this._pendingClaim = null;
  }

  async _confirmClaim() {
    const pending = this._pendingClaim;
    if (!pending) return;
    const child = pending._child;
    this._pendingClaim = null;
    return this._handleClaim(pending, child);
  }

  async _handleClaim(reward, child) {
    if (!child || !reward) return;
    if (this._loading[reward.id]) return;
    this._loading = { ...this._loading, [reward.id]: true };
    this.requestUpdate();
    try {
      // Prefer pressing the per-child/per-reward button entity so HA
      // state-trigger automations on button.taskmate_<child>_claim_<reward>
      // fire. Falls back to the service call if the entity isn't registered.
      const buttonEntityId = window.__taskmate_find_button
        && window.__taskmate_find_button(this.hass, child.id, "claim", reward.id);
      if (buttonEntityId) {
        await this.hass.callService("button", "press", { entity_id: buttonEntityId });
      } else {
        await this.hass.callService("taskmate", "claim_reward", {
          reward_id: reward.id,
          child_id: child.id,
        });
      }
    } catch (e) {
      console.error("Failed to claim reward:", e);
      if (this.hass && this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: this._t('approvals.error_title'),
          message: this._t('approvals.error_failed_service', {
            service: "claim reward",
            message: e && e.message ? e.message : String(e),
          }),
          notification_id: `taskmate_reward_claim_${reward.id}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [reward.id]: false };
      this.requestUpdate();
    }
  }

  async _handleAllocate(reward, child, points) {
    if (!child || !reward) return;
    const key = `${reward.id}_alloc`;
    if (this._loading[key]) return;
    this._loading = { ...this._loading, [key]: true };
    this.requestUpdate();
    try {
      await this.hass.callService("taskmate", "allocate_points_to_pool", {
        child_id: child.id,
        reward_id: reward.id,
        points,
      });
    } catch (e) {
      console.error("Failed to allocate points to pool:", e);
      if (this.hass && this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: this._t('approvals.error_title'),
          message: this._t('approvals.error_failed_service', {
            service: "allocate_points_to_pool",
            message: e && e.message ? e.message : String(e),
          }),
          notification_id: `taskmate_pool_alloc_${reward.id}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [key]: false };
      this.requestUpdate();
    }
  }

  async _handleRedeem(reward, child) {
    return this._promptClaim(reward, child);
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
    // All reward costs are static — just return reward.cost
    // calculated_costs is still provided by the sensor for jackpot display purposes
    const calculatedCosts = reward.calculated_costs || {};

    if (this.config.child_id && calculatedCosts[this.config.child_id]) {
      return calculatedCosts[this.config.child_id];
    }

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
        width = cost > 0 ? Math.min((contrib.points / cost) * 100, 100) : 0;
      }
      return {
        ...contrib,
        width: width
      };
    });

    // Calculate total percentage for display
    const totalPercentage = cost > 0 ? Math.min((totalStars / cost) * 100, 100) : 0;

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
            <span class="jackpot-child-contribution">
              <span class="color-dot color-${contrib.colorIndex}"></span>
              <strong>${contrib.name}</strong>:
              ${contrib.points}
              <ha-icon icon="${pointsIcon}" style="--mdc-icon-size: 12px;"></ha-icon>
              ${hasWeightedData && contrib.expectedContribution > 0 ? html`
                <span class="jackpot-pct">(${Math.round(contrib.weightedProgress)}%)</span>
              ` : ''}
            </span>
          `)}
        </div>
      </div>
    `;
  }

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns (§card-rewards). FIXED COSTS ONLY —
     never any dynamic/surge pricing. All existing claim/pool/confirm logic is
     preserved: designed buttons call the SAME handlers as classic.
  ══════════════════════════════════════════════════════════════════════ */

  _designTone(i) { return `var(--tmd-c${(i % 6) + 1})`; }

  _av(child, tone, size) {
    const a = (child && child.avatar) || "";
    const inner = a.startsWith("mdi:")
      ? html`<ha-icon icon="${a}"></ha-icon>`
      : a
        ? html`<img src="${a}" alt="${child.name}">`
        : ((child && child.name) || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
    return html`<div class="av" style="--av:${size}px;--ac:${tone}">${inner}</div>`;
  }

  /**
   * Compute all per-reward display data once, mirroring the classic
   * _renderRewardRow calculations. FIXED COST is reward.cost (via
   * _getDisplayCost — static only). Returns everything the designed rows need.
   */
  _rewardData(reward, children) {
    const assignedTo = reward.assigned_to || [];
    const isJackpot = reward.is_jackpot || false;
    const cardForcesPool = this.config.enable_pool_mode === true;
    // Jackpot rewards are always pool-mode (#552): everyone deposits into the
    // shared jar and it's redeemed when full. Combined points only work via the
    // pool, so jackpots never show the single-child claim button.
    const enablePoolMode = cardForcesPool || reward.pool_enabled === true || isJackpot;
    const displayCost = this._getDisplayCost(reward, children);

    const relevantChildren = assignedTo.length === 0
      ? children
      : children.filter(c => assignedTo.includes(c.id));

    const childId = this.config?.child_id || this._selectedChildId;
    const relevantChild = childId
      ? children.find(c => c.id === childId)
      : relevantChildren[0];

    const poolAllocations = reward.pool_allocations || {};
    const jackpotPoolTotal = typeof reward.jackpot_pool_total === 'number' ? reward.jackpot_pool_total : 0;

    let currentStars = 0;
    const childContributions = [];

    if (isJackpot) {
      const sharePerChild = relevantChildren.length > 0
        ? Math.round(displayCost / relevantChildren.length)
        : displayCost;
      relevantChildren.forEach((child, index) => {
        const points = enablePoolMode
          ? (poolAllocations[child.id] || 0)
          : (child.points || 0);
        currentStars += points;
        childContributions.push({
          name: child.name,
          child,
          points,
          tone: this._designTone(index),
        });
      });
    } else if (enablePoolMode) {
      currentStars = childId ? (poolAllocations[childId] || 0) : 0;
    } else if (this.config.child_id) {
      const fc = children.find(c => c.id === this.config.child_id);
      currentStars = fc ? (fc.points || 0) : 0;
    } else if (relevantChildren.length > 0) {
      currentStars = relevantChildren[0].points || 0;
    }

    const percentage = displayCost > 0 ? Math.min((currentStars / displayCost) * 100, 100) : 0;

    const pcAttrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const pendingClaims = pcAttrs.pending_reward_claims || [];
    const hasPendingClaim = pendingClaims.some(c =>
      c.reward_id === reward.id && (!childId || c.child_id === childId)
    );

    const spendable = relevantChild
      ? (typeof relevantChild.spendable_balance === 'number'
          ? relevantChild.spendable_balance
          : (relevantChild.points || 0) - (relevantChild.committed_points || 0))
      : 0;
    const poolFull = enablePoolMode && (
      isJackpot ? jackpotPoolTotal >= displayCost : currentStars >= displayCost
    );

    const committedPoints = relevantChild?.committed_points || 0;
    const availablePoints = (relevantChild?.points || 0) - committedPoints;
    const canAfford = !!relevantChild && availablePoints >= displayCost;

    const isSoldOut = reward.is_sold_out === true;
    const isExpired = reward.is_expired === true;
    const isUnavailable = isSoldOut || isExpired;
    const daysUntilExpiry = (typeof reward.days_until_expiry === 'number')
      ? reward.days_until_expiry : null;

    return {
      reward, isJackpot, enablePoolMode, displayCost, relevantChildren, relevantChild,
      childId, currentStars, childContributions, percentage, hasPendingClaim,
      spendable, poolFull, canAfford, isSoldOut, isExpired, isUnavailable, daysUntilExpiry,
      showClaim: !enablePoolMode && !hasPendingClaim && childId && !isUnavailable,
      showPoolControls: enablePoolMode && childId && !hasPendingClaim && !isUnavailable,
    };
  }

  /** Designed availability chip label/tone for a reward, or null. */
  _designAvail(d) {
    if (d.isExpired) return { label: this._t('rewards.expired'), tone: 'muted' };
    if (d.isSoldOut) return { label: this._t('rewards.sold_out'), tone: 'muted' };
    if (typeof d.reward.quantity === 'number' && d.reward.quantity > 0 && d.reward.quantity <= 3) {
      return { label: this._t('rewards.only_n_left', { count: d.reward.quantity }), tone: 'bad' };
    }
    if (typeof d.daysUntilExpiry === 'number' && d.daysUntilExpiry >= 0 && d.daysUntilExpiry <= 7) {
      const label = d.daysUntilExpiry === 0
        ? this._t('rewards.expires_today')
        : (d.daysUntilExpiry === 1
            ? this._t('rewards.expires_in_days', { count: d.daysUntilExpiry })
            : this._t('rewards.expires_in_days_plural', { count: d.daysUntilExpiry }));
      return { label, tone: 'warn' };
    }
    return null;
  }

  _renderDesigned(design) {
    const entity = this.hass.states[this.config.entity];
    const hd = _safeColor(this.config.header_color, '#e67e22');

    if (!entity) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${this._designHeader(0, hd)}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div>
      </ha-card>`;
    }

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const allRewards = attrs.rewards || [];
    const children = attrs.children || [];
    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t("common.stars");

    let rewards = allRewards;
    if (this.config.child_id) {
      rewards = allRewards.filter((reward) => {
        const assignedTo = reward.assigned_to || [];
        return assignedTo.length === 0 || assignedTo.includes(this.config.child_id);
      });
    }

    const sortedRewards = [...rewards].sort((a, b) => {
      if (a.is_jackpot && !b.is_jackpot) return -1;
      if (!a.is_jackpot && b.is_jackpot) return 1;
      return this._getDisplayCost(a, children) - this._getDisplayCost(b, children);
    });

    const cardForcesPool = this.config.enable_pool_mode === true;
    const activeChildId = this.config.child_id || this._selectedChildId;
    const activeChild = activeChildId ? children.find((c) => c.id === activeChildId) : null;
    const anyPoolReward = sortedRewards.some((r) => cardForcesPool || r.pool_enabled === true || r.is_jackpot);

    const header = this._designHeader(rewards.length, hd);

    const body = sortedRewards.length === 0
      ? html`<div class="tmd-empty">${this._t('rewards.empty_title')}<br>${this._t('rewards.empty_subtitle')}</div>`
      : html`
        ${this._designChildTabs(children)}
        ${(anyPoolReward && activeChild) || activeChild
          ? this._designChildSelector(activeChild, pointsIcon, pointsName, design)
          : ''}
        <div class="rw-list ${this.config.expand_to_fit === false ? 'rw-scroll' : ''}">
          ${sortedRewards.map((r) => this._designRewardRow(r, children, pointsIcon, pointsName, design))}
        </div>`;

    return html`
      <ha-card class="tmd" style="--hd:${hd}">
        ${header}
        <div class="tmd-bd">${body}</div>
      </ha-card>
      ${this._renderConfirmDialog(pointsIcon, pointsName)}
    `;
  }

  _designHeader(count, hd) {
    return html`
      <div class="tmd-hd">
        <span class="ic">🎁</span>
        <span class="tt">${this.config.title || this._t('rewards.default_title')}${count
          ? html`<small>${count === 1
              ? this._t('rewards.reward_count_singular', { count })
              : this._t('rewards.reward_count_plural', { count })}</small>` : ''}</span>
      </div>`;
  }

  _designChildSelector(child, pointsIcon, pointsName, design) {
    const spendable = typeof child.spendable_balance === 'number'
      ? child.spendable_balance : (child.points || 0);
    return html`
      <div class="row rw-sel" style="--ac:${this._designTone(0)}">
        ${this._av(child, this._designTone(0), 38)}
        <div class="rw-sel-name">${child.name}</div>
        <span class="chip soft">
          <span style="color:var(--tmd-gold)">⭐</span>
          ${this._t('rewards.spendable_balance')}: ${spendable}
        </span>
      </div>`;
  }

  _designRewardRow(reward, children, pointsIcon, pointsName, design) {
    const d = this._rewardData(reward, children);
    const tone = this._designTone((reward.id || reward.name || '').length);
    const isLoading = this._loading[reward.id];
    const avail = this._designAvail(d);
    const emoji = "🎁";

    // Child-assignment badges — honour show_child_badges (default on), classic-parity:
    // only for non-jackpot rewards; "all children" chip when unassigned.
    const showChildBadges = this.config.show_child_badges !== false;
    const assignedTo = reward.assigned_to || [];
    const childMap = {};
    children.forEach((c) => { childMap[c.id] = c.name; });
    const badges = showChildBadges && !d.isJackpot
      ? (assignedTo.length === 0
          ? html`<span class="chip soft rw-badge rw-badge-all">${this._t('rewards.all_children')}</span>`
          : assignedTo.map((cid) => html`<span class="chip rw-badge">${childMap[cid] || cid}</span>`))
      : '';

    const costBadge = html`<span class="chip rw-cost">⭐ ${d.displayCost} ${pointsName}</span>`;

    const bar = d.isJackpot
      ? html`<div class="bar rw-pool-bar">
          ${d.childContributions.map((c) => {
            const w = d.displayCost > 0 ? Math.min((c.points / d.displayCost) * 100, 100) : 0;
            return html`<i style="width:${w}%;background:${c.tone}"></i>`;
          })}
        </div>`
      : html`<div class="bar"><i style="width:${d.percentage}%;${d.canAfford ? 'background:var(--tmd-good)' : ''}"></i></div>`;

    const claimBtn = d.showClaim
      ? html`<button class="btn sm ${d.canAfford ? 'good' : ''}"
          ?disabled="${!d.canAfford || isLoading}"
          @click="${(e) => { e.stopPropagation(); this._promptClaim(reward, d.relevantChild); }}"
          title="${d.canAfford ? this._t('rewards.claim_reward') : this._t('rewards.not_enough_points')}"
        >${this._t('rewards.claim_reward')}</button>`
      : '';

    const poolControls = d.showPoolControls
      ? (d.poolFull
        ? html`<button class="btn sm good"
            ?disabled="${isLoading}"
            @click="${(e) => { e.stopPropagation(); this._handleRedeem(reward, d.relevantChild); }}"
          >${this._t('rewards.redeem')}</button>`
        : html`<span class="row rw-pool-btns">
            ${this._quickDepositAmounts().map((amt, i, arr) => {
              const disabled = !d.relevantChild || d.spendable < amt || this._loading[`${reward.id}_alloc`];
              return html`<button class="btn sm ${i === arr.length - 1 ? '' : 'ghost'}"
                ?disabled="${disabled}"
                title="${this._depositTooltip({ child: d.relevantChild, spendable: d.spendable, amt, isAllocLoading: this._loading[`${reward.id}_alloc`] })}"
                @click="${(e) => { e.stopPropagation(); this._handleAllocate(reward, d.relevantChild, amt); }}"
              >+${amt}</button>`;
            })}
            ${this._renderCustomDeposit(reward, d.relevantChild, d.spendable, this._loading[`${reward.id}_alloc`], { button: 'btn sm', input: 'rw-deposit-input' })}
          </span>`)
      : '';

    const statusLine = d.hasPendingClaim
      ? html`<span class="muted rw-status">⏳ ${this._t('rewards.awaiting_approval')}</span>`
      : d.canAfford && d.showClaim
        ? html`<span class="rw-status rw-status-good">${this._t('reward_progress.ready_to_claim')}</span>`
        : html`<span class="muted rw-status">${d.currentStars} / ${d.displayCost}</span>`;

    return html`
      <div class="rw-card ${d.isJackpot ? 'rw-jackpot' : ''} ${d.isUnavailable ? 'rw-unavail' : ''}"
           style="--ac:${tone}">
        <div class="row rw-top">
          <span class="rw-emoji">${emoji}</span>
          <div class="rw-info">
            ${d.isJackpot ? html`<span class="chip rw-jackpot-label">🎰 ${this._t('rewards.jackpot')}</span>` : ''}
            <div class="rw-name">${reward.name}</div>
            ${reward.description ? html`<div class="muted rw-desc">${reward.description}</div>` : ''}
            ${avail ? html`<span class="chip soft rw-avail rw-avail-${avail.tone}">${avail.label}</span>` : ''}
            ${badges ? html`<div class="rw-badges">${badges}</div>` : ''}
          </div>
          ${costBadge}
        </div>
        ${bar}
        ${d.isJackpot ? html`
          <div class="row rw-pool-foot">
            ${d.childContributions.map((c) => html`
              <span class="chip rw-contrib">${this._av(c.child, c.tone, 16)} ${c.points}</span>`)}
          </div>` : ''}
        <div class="row rw-foot">
          ${statusLine}
          <span style="flex:1"></span>
          ${claimBtn}${poolControls}
        </div>
      </div>`;
  }

  /** The confirm dialog markup, shared by classic + designed paths. */
  _renderConfirmDialog(pointsIcon, pointsName) {
    if (!this._pendingClaim) return '';
    return html`
      <div class="confirm-overlay" @click="${this._cancelClaim}">
        <div class="confirm-dialog" @click="${(e) => e.stopPropagation()}">
          <ha-icon class="dialog-icon" icon="mdi:gift-outline"></ha-icon>
          <div class="dialog-title">${this._t('rewards.confirm_title')}</div>
          <div class="dialog-body">
            ${(() => {
              const r = this._pendingClaim;
              const child = r._child;
              const currentPoints = child ? (typeof child.spendable_balance === 'number' ? child.spendable_balance : (child.points || 0)) : null;
              const cost = r.cost;
              const remaining = currentPoints !== null ? currentPoints - cost : null;
              return html`
                <div style="margin-bottom: 12px;">${this._t('rewards.confirm_body', { name: r.name })}</div>
                ${currentPoints !== null ? html`
                  <div class="dialog-points-summary">
                    <div class="dialog-points-row">
                      <span>${this._t('rewards.confirm_your_points', { name: pointsName })}</span>
                      <span class="points-val">
                        <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:14px;"></ha-icon>
                        ${currentPoints}
                      </span>
                    </div>
                    <div class="dialog-points-row cost">
                      <span>${this._t('rewards.confirm_cost')}</span>
                      <span class="points-val">
                        <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:14px;"></ha-icon>
                        −${cost}
                      </span>
                    </div>
                    <div class="dialog-points-row remaining">
                      <span>${this._t('rewards.confirm_remaining')}</span>
                      <span class="points-val">
                        <ha-icon icon="${pointsIcon}" style="--mdc-icon-size:14px;"></ha-icon>
                        ${remaining}
                      </span>
                    </div>
                  </div>
                ` : ''}
              `;
            })()}
          </div>
          <div class="dialog-buttons">
            <button class="btn-cancel" @click="${this._cancelClaim}">${this._t('common.cancel')}</button>
            <button class="btn-confirm" @click="${this._confirmClaim}">${this._t('rewards.confirm_claim_btn')}</button>
          </div>
        </div>
      </div>`;
  }
}

// Card Editor for visual configuration in Lovelace UI
class TaskMateRewardsCardEditor extends LitElement {
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

      .colour-field {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 12px 16px;
        border: 1px solid var(--outline-color, var(--divider-color, #e0e0e0));
        border-radius: 4px;
        background: var(--mdc-text-field-fill-color, var(--card-background-color));
      }
      .colour-field-label {
        font-size: 0.82rem;
        color: var(--primary-color);
        font-weight: 500;
      }
      .colour-field-body {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }
      .colour-swatch-wrapper {
        position: relative;
        width: 36px;
        height: 36px;
        border-radius: 50%;
        overflow: hidden;
        cursor: pointer;
        border: 2px solid var(--divider-color, #e0e0e0);
        flex-shrink: 0;
      }
      .colour-swatch-wrapper input[type="color"] {
        position: absolute;
        inset: 0;
        opacity: 0;
        cursor: pointer;
        border: 0;
        padding: 0;
      }
      .colour-swatch-preview { position: absolute; inset: 0; pointer-events: none; }
      .colour-hex {
        font-family: var(--code-font-family, monospace);
        font-size: 0.85rem;
        color: var(--secondary-text-color);
        min-width: 70px;
      }
      .colour-presets { display: flex; gap: 6px; flex-wrap: wrap; }
      .preset-swatch {
        width: 22px;
        height: 22px;
        border-radius: 50%;
        cursor: pointer;
        border: 2px solid var(--divider-color, #e0e0e0);
        transition: transform 0.1s;
        padding: 0;
      }
      .preset-swatch:hover { transform: scale(1.15); }
      .preset-swatch.active {
        border-color: var(--primary-text-color);
        box-shadow: 0 0 0 2px var(--primary-color);
      }
      .colour-reset {
        font-size: 0.78rem;
        color: var(--secondary-text-color);
        background: none;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        padding: 4px 10px;
        cursor: pointer;
        margin-left: auto;
      }
      .colour-helper {
        color: var(--secondary-text-color);
        font-size: 0.82rem;
        line-height: 1.3;
      }
    `;
  }

  setConfig(config) {
    this.config = config;
  }

  // Build the ha-form schema based on the current state (e.g. child list from the entity).
  _buildSchema() {
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const children = entity?.attributes?.children || [];

    const childOptions = [
      { value: '__all__', label: this._t('rewards.editor.filter_by_child_all') },
      ...children.map((c) => ({ value: c.id, label: c.name })),
    ];

    return [
      {
        name: 'entity',
        selector: { entity: { domain: 'sensor' } },
      },
      {
        name: 'title',
        selector: { text: {} },
      },
      {
        name: 'child_id',
        selector: { select: { options: childOptions, mode: 'dropdown' } },
      },
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
      {
        name: 'show_child_badges',
        selector: { boolean: {} },
      },
      {
        name: 'enable_pool_mode',
        selector: { boolean: {} },
      },
      {
        name: 'expand_to_fit',
        selector: { boolean: {} },
      },
    ];
  }

  _computeLabel = (schemaEntry) => {
    const labels = {
      entity: this._t('rewards.editor.entity'),
      title: this._t('rewards.editor.title'),
      child_id: this._t('rewards.editor.filter_by_child'),
      card_design: this._t('common.design.field_label'),
      show_child_badges: this._t('rewards.editor.show_child_badges'),
      enable_pool_mode: this._t('rewards.editor.enable_pool_mode'),
      expand_to_fit: this._t('rewards.editor.expand_to_fit'),
    };
    return labels[schemaEntry.name] ?? schemaEntry.name;
  };

  _computeHelper = (schemaEntry) => {
    const helpers = {
      entity: this._t('rewards.editor.entity_helper'),
      title: this._t('rewards.editor.title_helper'),
      child_id: this._t('rewards.editor.filter_by_child_helper'),
      show_child_badges: this._t('rewards.editor.show_child_badges_helper'),
      enable_pool_mode: this._t('rewards.editor.enable_pool_mode_helper'),
      expand_to_fit: this._t('rewards.editor.expand_to_fit_helper'),
    };
    return helpers[schemaEntry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) {
      return html``;
    }
    // ha-form treats missing keys as empty; normalise for consistent values.
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      child_id: this.config.child_id || '__all__',
      card_design: this.config.card_design || 'global',
      show_child_badges: this.config.show_child_badges !== false,
      enable_pool_mode: this.config.enable_pool_mode === true,
      expand_to_fit: this.config.expand_to_fit !== false,
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
      ${this._renderColourPicker('header_color', '#e67e22')}
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
    // Merge into config, removing keys that are empty/default so the YAML stays clean.
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      if (
        value === '' || value === null || value === undefined
        || (key === 'child_id' && value === '__all__')
      ) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (key === 'show_child_badges' && value === true) {
        // Default is true — omit to keep config minimal
        delete newConfig[key];
      } else if (key === 'enable_pool_mode' && value === false) {
        delete newConfig[key];
      } else if (key === 'expand_to_fit' && value === true) {
        // Default is true (fluid) — omit to keep config minimal
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this._dispatchConfig(newConfig);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === undefined || value === '' || value === null) {
      delete newConfig[key];
    }
    this._dispatchConfig(newConfig);
  }

  _dispatchConfig(newConfig) {
    this.dispatchEvent(
      new CustomEvent('config-changed', {
        detail: { config: newConfig },
        bubbles: true,
        composed: true,
      })
    );
  }
}

// Register the cards
customElements.define("taskmate-rewards-card", TaskMateRewardsCard);
customElements.define("taskmate-rewards-card-editor", TaskMateRewardsCardEditor);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-rewards-card",
  name: "TaskMate Rewards Card",
  description: "A card displaying available rewards with star costs",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-rewards-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE REWARDS CARD %c v" + _tmVersion + " ",
  "background:#e67e22;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
