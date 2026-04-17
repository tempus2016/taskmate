/**
 * TaskMate Reward Progress Card
 * Full-screen motivational display showing a single reward's progress.
 * Designed for wall tablets as a persistent motivation display.
 *
 * Version: 1.0.0
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));
const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

class TaskMateRewardProgressCard extends LitElement {
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

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #7d3c98);
        color: white;
        gap: 12px;
      }

      .header-content { display: flex; align-items: center; gap: 10px; min-width: 0; }
      .header-icon { --mdc-icon-size: 26px; opacity: 0.9; flex-shrink: 0; }
      .header-title {
        font-size: 1.1rem; font-weight: 600;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }

      .card-content { padding: 20px 18px; }

      /* Reward hero section */
      .reward-hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        padding: 12px 0 20px;
        gap: 10px;
      }

      .reward-icon-wrap {
        width: 90px;
        height: 90px;
        border-radius: 50%;
        background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 6px 24px rgba(155,89,182,0.35);
        animation: hero-float 3s ease-in-out infinite;
      }

      @keyframes hero-float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-6px); }
      }

      .reward-icon-wrap ha-icon { --mdc-icon-size: 52px; color: white; }

      .reward-name {
        font-size: 1.6rem;
        font-weight: 700;
        color: var(--primary-text-color);
        line-height: 1.2;
      }

      .reward-description {
        font-size: 0.9rem;
        color: var(--secondary-text-color);
        max-width: 280px;
      }

      /* Children progress blocks */
      .children-section {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }

      .child-progress-block {
        background: var(--secondary-background-color, #f8f8f8);
        border-radius: 16px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 10px;
      }

      .child-progress-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
      }

      .child-progress-left {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
      }

      .child-avatar {
        width: 40px;
        height: 40px;
        min-width: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%);
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .child-avatar ha-icon { --mdc-icon-size: 24px; color: white; }

      .child-progress-name {
        font-size: 1rem;
        font-weight: 600;
        color: var(--primary-text-color);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .child-points-label {
        font-size: 0.8rem;
        color: var(--secondary-text-color);
      }

      .child-progress-cost {
        text-align: right;
        flex-shrink: 0;
      }

      .cost-label {
        font-size: 0.75rem;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      .cost-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: #9b59b6;
        display: flex;
        align-items: center;
        gap: 3px;
        justify-content: flex-end;
      }

      .cost-value ha-icon { --mdc-icon-size: 16px; color: #f1c40f; }

      /* Big animated progress bar */
      .big-progress-wrap {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }

      .big-progress-bar {
        height: 22px;
        background: var(--divider-color, #e0e0e0);
        border-radius: 11px;
        overflow: hidden;
        position: relative;
      }

      .big-progress-fill {
        height: 100%;
        border-radius: 11px;
        transition: width 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
        position: relative;
        overflow: hidden;
      }

      .big-progress-fill::after {
        content: '';
        position: absolute;
        top: 0; left: -100%;
        width: 60%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        animation: shimmer 2s infinite;
      }

      @keyframes shimmer {
        0% { left: -100%; }
        100% { left: 200%; }
      }

      .big-progress-fill.affordable {
        background: linear-gradient(90deg, #27ae60, #2ecc71);
      }

      .big-progress-fill.close {
        background: linear-gradient(90deg, #e67e22, #f39c12);
      }

      .big-progress-fill.far {
        background: linear-gradient(90deg, #9b59b6, #a569bd);
      }

      .big-progress-fill.complete {
        background: linear-gradient(90deg, #27ae60, #1abc9c);
      }

      .progress-stat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.82rem;
      }

      .progress-have {
        font-weight: 600;
        color: var(--primary-text-color);
      }

      .progress-need {
        color: var(--secondary-text-color);
      }

      .progress-pct {
        font-weight: 700;
        font-size: 0.95rem;
      }

      .progress-pct.affordable { color: #27ae60; }
      .progress-pct.close { color: #e67e22; }
      .progress-pct.far { color: #9b59b6; }

      /* Can afford badge */
      .can-afford-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: rgba(46,204,113,0.15);
        color: #27ae60;
        border-radius: 20px;
        padding: 5px 12px;
        font-size: 0.85rem;
        font-weight: 700;
        animation: pulse-green 2s ease-in-out infinite;
        align-self: center;
      }

      .can-afford-badge ha-icon { --mdc-icon-size: 16px; }

      @keyframes pulse-green {
        0%, 100% { box-shadow: 0 0 0 0 rgba(46,204,113,0.3); }
        50% { box-shadow: 0 0 0 6px rgba(46,204,113,0); }
      }

      /* Jackpot section */
      .jackpot-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: linear-gradient(135deg, #f39c12, #f1c40f);
        color: white;
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        align-self: flex-start;
      }

      .jackpot-badge ha-icon { --mdc-icon-size: 14px; }

      .jackpot-pool {
        display: flex;
        flex-direction: column;
        gap: 8px;
        background: rgba(241,196,15,0.08);
        border: 1px solid rgba(241,196,15,0.25);
        border-radius: 12px;
        padding: 12px;
      }

      .jackpot-pool-title {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.06em;
      }

      .jackpot-contributors {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .jackpot-contributor {
        display: flex;
        align-items: center;
        gap: 6px;
        background: var(--card-background-color, #fff);
        border-radius: 20px;
        padding: 4px 10px 4px 6px;
        font-size: 0.82rem;
        font-weight: 600;
        color: var(--primary-text-color);
      }

      .jackpot-contributor .mini-avatar {
        width: 22px; height: 22px;
        border-radius: 50%;
        background: linear-gradient(135deg, #f39c12, #f1c40f);
        display: flex; align-items: center; justify-content: center;
      }

      .jackpot-contributor .mini-avatar ha-icon { --mdc-icon-size: 13px; color: white; }

      /* Error / empty */
      .error-state, .empty-state {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 40px 20px;
        color: var(--secondary-text-color); text-align: center;
      }
      .error-state { color: var(--error-color, #f44336); }
      .error-state ha-icon, .empty-state ha-icon { --mdc-icon-size: 48px; margin-bottom: 12px; opacity: 0.5; }

      /* Responsive */
      @media (max-width: 480px) {
        .card-content { padding: 14px 12px; }
        .reward-icon-wrap { width: 70px; height: 70px; }
        .reward-icon-wrap ha-icon { --mdc-icon-size: 40px; }
        .reward-name { font-size: 1.3rem; }
        .big-progress-bar { height: 18px; border-radius: 9px; }
        .child-progress-block { padding: 12px; }
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error(this._t('reward_progress.error.entity_required'));
    this.config = {
      title: null,
      reward_id: null,
      child_id: null,
            header_color: '#7d3c98',
    ...config,
    };
  }

  getCardSize() { return 5; }
  static getConfigElement() { return document.createElement("taskmate-reward-progress-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Reward Goal" };
  }

  render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div></ha-card>`;
    if (entity.state === "unavailable" || entity.state === "unknown") return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>${this._t('reward_progress.unavailable')}</div></div></ha-card>`;

    const rewards = entity.attributes.rewards || [];
    const children = entity.attributes.children || [];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Points";

    // Pick reward
    let reward = this.config.reward_id
      ? rewards.find(r => r.id === this.config.reward_id)
      : rewards[0];

    if (!reward) return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:gift-outline"></ha-icon><div>${this._t('reward_progress.no_rewards')}</div></div></ha-card>`;

    // Which children to show
    let showChildren = children;
    if (this.config.child_id) showChildren = children.filter(c => c.id === this.config.child_id);
    if (reward.assigned_to?.length) showChildren = showChildren.filter(c => reward.assigned_to.includes(c.id));
    if (!showChildren.length) showChildren = children;

    const isJackpot = reward.is_jackpot;

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#7d3c98'}; }</style>
        <div class="card-header">
          <div class="header-content">
            <ha-icon class="header-icon" icon="mdi:trophy-outline"></ha-icon>
            <span class="header-title">${this.config.title || this._t('reward_progress.default_title')}</span>
          </div>
        </div>
        <div class="card-content">
          <div class="reward-hero">
            <div class="reward-icon-wrap">
              <ha-icon icon="${reward.icon || 'mdi:gift'}"></ha-icon>
            </div>
            <div class="reward-name">${reward.name}</div>
            ${reward.description ? html`<div class="reward-description">${reward.description}</div>` : ''}
            ${isJackpot ? html`
              <div class="jackpot-badge">
                <ha-icon icon="mdi:star-shooting"></ha-icon>
                ${this._t('reward_progress.jackpot_reward')}
              </div>
            ` : ''}
          </div>

          ${isJackpot
            ? this._renderJackpot(reward, showChildren, pointsIcon, pointsName)
            : html`
              <div class="children-section">
                ${showChildren.map(child => this._renderChildProgress(child, reward, pointsIcon, pointsName))}
              </div>
            `}
        </div>
      </ha-card>
    `;
  }

  _renderChildProgress(child, reward, pointsIcon, pointsName) {
    const cost = reward.calculated_costs?.[child.id] ?? reward.cost;
    const have = child.points || 0;
    const pct = Math.min(100, Math.round((have / cost) * 100));
    const canAfford = have >= cost;
    const close = pct >= 70;
    const cls = canAfford ? "complete" : close ? "close" : "far";
    const pctCls = canAfford ? "affordable" : close ? "close" : "far";

    return html`
      <div class="child-progress-block">
        <div class="child-progress-header">
          <div class="child-progress-left">
            <div class="child-avatar">
              <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
            </div>
            <div>
              <div class="child-progress-name">${child.name}</div>
              <div class="child-points-label">${have} ${pointsName}</div>
            </div>
          </div>
          <div class="child-progress-cost">
            <div class="cost-label">${this._t('common.goal')}</div>
            <div class="cost-value">
              <ha-icon icon="${pointsIcon}"></ha-icon>
              ${cost}
            </div>
          </div>
        </div>

        <div class="big-progress-wrap">
          <div class="big-progress-bar">
            <div class="big-progress-fill ${cls}" style="width: ${pct}%"></div>
          </div>
          <div class="progress-stat-row">
            <span class="progress-have">${have} / ${cost} ${pointsName}</span>
            ${canAfford
              ? html`<span class="progress-need">${this._t('reward_progress.ready_to_claim_emoji')}</span>`
              : html`<span class="progress-need">${this._t('reward_progress.more_needed', { amount: cost - have })}</span>`}
            <span class="progress-pct ${pctCls}">${pct}%</span>
          </div>
        </div>

        ${canAfford ? html`
          <div class="can-afford-badge">
            <ha-icon icon="mdi:check-circle"></ha-icon>
            ${this._t('reward_progress.ready_to_claim')}
          </div>
        ` : ''}
      </div>
    `;
  }

  _renderJackpot(reward, children, pointsIcon, pointsName) {
    const cost = reward.calculated_costs
      ? Object.values(reward.calculated_costs)[0] ?? reward.cost
      : reward.cost;

    const totalHave = children.reduce((s, c) => s + (c.points || 0), 0);
    const pct = Math.min(100, Math.round((totalHave / cost) * 100));
    const canAfford = totalHave >= cost;
    const close = pct >= 70;
    const cls = canAfford ? "complete" : close ? "close" : "far";
    const pctCls = canAfford ? "affordable" : close ? "close" : "far";

    return html`
      <div class="children-section">
        <div class="child-progress-block">
          <div class="jackpot-pool">
            <div class="jackpot-pool-title">${this._t('reward_progress.combined_points_pool')}</div>
            <div class="jackpot-contributors">
              ${children.map(child => html`
                <div class="jackpot-contributor">
                  <div class="mini-avatar">
                    <ha-icon icon="${child.avatar || 'mdi:account-circle'}"></ha-icon>
                  </div>
                  <span>${child.name}: ${child.points}</span>
                </div>
              `)}
            </div>
          </div>

          <div class="child-progress-header" style="margin-top:4px">
            <div>
              <div class="child-progress-name">${this._t('reward_progress.total_pool')}</div>
              <div class="child-points-label">${totalHave} ${pointsName} ${this._t('reward_progress.combined')}</div>
            </div>
            <div class="child-progress-cost">
              <div class="cost-label">${this._t('common.goal')}</div>
              <div class="cost-value">
                <ha-icon icon="${pointsIcon}"></ha-icon>
                ${cost}
              </div>
            </div>
          </div>

          <div class="big-progress-wrap">
            <div class="big-progress-bar">
              <div class="big-progress-fill ${cls}" style="width: ${pct}%"></div>
            </div>
            <div class="progress-stat-row">
              <span class="progress-have">${totalHave} / ${cost} ${pointsName}</span>
              ${canAfford
                ? html`<span class="progress-need">${this._t('reward_progress.ready')}</span>`
                : html`<span class="progress-need">${this._t('reward_progress.more_needed', { amount: cost - totalHave })}</span>`}
              <span class="progress-pct ${pctCls}">${pct}%</span>
            </div>
          </div>

          ${canAfford ? html`
            <div class="can-afford-badge">
              <ha-icon icon="mdi:check-circle"></ha-icon>
              ${this._t('reward_progress.ready_to_claim')}
            </div>
          ` : ''}
        </div>
      </div>
    `;
  }
}

class TaskMateRewardProgressCardEditor extends LitElement {
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
    const entity = this.config?.entity ? this.hass?.states?.[this.config.entity] : null;
    const rewards = entity?.attributes?.rewards || [];
    const children = entity?.attributes?.children || [];
    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      { name: 'title', selector: { text: {} } },
      {
        name: 'reward_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('reward_progress.editor.first_available') },
              ...rewards.map((r) => ({ value: r.id, label: r.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('reward_progress.editor.child_filter_all') },
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
      entity: this._t('common.editor.overview_entity'),
      title: this._t('common.editor.card_title'),
      reward_id: this._t('reward_progress.editor.reward_to_display'),
      child_id: this._t('common.editor.filter_by_child'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      reward_id: this._t('reward_progress.editor.reward_helper'),
      child_id: this._t('reward_progress.editor.child_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;
    const data = {
      entity: this.config.entity || '',
      title: this.config.title || '',
      reward_id: this.config.reward_id || '',
      child_id: this.config.child_id || '',
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
      ${this._renderColourPicker('header_color', '#7d3c98')}
    `;
  }

  _renderColourPicker(key, defaultValue) {
    const current = this.config[key] || defaultValue;
    const presets = [defaultValue, '#e67e22', '#27ae60', '#3498db', '#f1c40f', '#e74c3c', '#34495e'];
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
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }

  _update(key, value) {
    const cfg = { ...this.config, [key]: value };
    if (!value) delete cfg[key];
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: cfg }, bubbles: true, composed: true }));
  }
}

customElements.define("taskmate-reward-progress-card", TaskMateRewardProgressCard);
customElements.define("taskmate-reward-progress-card-editor", TaskMateRewardProgressCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-reward-progress-card",
  name: "TaskMate Reward Progress",
  description: "Full-screen motivational reward progress display",
  preview: true,
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-reward-progress-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE REWARD PROGRESS CARD %c v" + _tmVersion + " ",
  "background:#7d3c98;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
