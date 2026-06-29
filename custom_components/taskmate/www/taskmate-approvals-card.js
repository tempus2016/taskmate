/**
 * TaskMate Approvals Card
 * A custom Lovelace card for managing pending chore approvals
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Security defense-in-depth: only ever emit our own auth-gated photo endpoint
// into an href/src. The backend already rejects foreign/crafted photo_url
// values, but guard here too so a stored bad value can never become a
// javascript:/external link in a parent's browser.
const tmSafePhotoUrl = (u) =>
  typeof u === "string" && u.startsWith("/api/taskmate/photo/") ? u : "";

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

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
      return window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
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
    const base = css`
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
        --mdc-icon-size: 16px;
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

      .approval-photo {
        display: inline-block;
        margin-top: 4px;
        line-height: 0;
      }
      .approval-photo img {
        width: 48px;
        height: 48px;
        object-fit: cover;
        border-radius: 8px;
        border: 1px solid var(--divider-color, #e0e0e0);
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
        --mdc-icon-size: 14px;
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
        --mdc-icon-size: 14px;
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

      /* Mandatory-miss review actions (#532) */
      .action-button.penalty {
        background: var(--fun-red, #e74c3c);
        color: white;
      }

      .action-button.postpone {
        background: var(--fun-orange, #e67e22);
        color: white;
      }

      .action-button.dismiss {
        background: var(--fun-green, #2ecc71);
        color: white;
      }

      .approval-item.mandatory {
        border-left: 5px solid var(--fun-red, #e74c3c);
      }

      .approval-item.mandatory .penalty-note {
        display: block;
        margin-top: 2px;
        font-size: 0.78rem;
        font-weight: 700;
        color: var(--fun-red, #e74c3c);
      }

      .approval-item.mandatory .penalty-note.none {
        color: var(--secondary-text-color, #888);
        font-weight: 600;
      }

      .action-button ha-icon {
        --mdc-icon-size: 20px;
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
        --mdc-icon-size: 48px;
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
        --mdc-icon-size: 48px;
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

      /* ── Designed styles (playroom / console / cleanpro) ──
         Shared .tmd kit + design tokens come from taskmate-design.js styles().
         Only card-specific layout classes are declared here. */
      .ap-group-label { font-weight: 800; font-size: 12px; text-transform: uppercase;
        letter-spacing: .04em; margin: 4px 0 9px; }
      .ap-group-label + .ap-group-label { margin-top: 14px; }

      /* Playroom — soft cards */
      .ap-pl-item { background: var(--tmd-surface-2); border-radius: 18px; padding: 12px; }
      .ap-pl-item + .ap-pl-item { margin-top: 11px; }
      .ap-pl-title { font-weight: 800; }
      .ap-pl-sub { font-size: 12.5px; }
      .ap-pl-photo { width: 46px; height: 46px; border-radius: 14px; overflow: hidden;
        display: grid; place-items: center; background: var(--tmd-accent); color: #fff;
        font-size: 20px; flex: none; }
      .ap-pl-photo img { width: 100%; height: 100%; object-fit: cover; }
      .ap-gold { background: var(--tmd-gold); border-color: transparent; color: #3a2e26; }

      /* Console — compact HUD rows */
      .ap-cn-item { background: var(--tmd-surface-2); border: 1px solid var(--tmd-border);
        border-radius: 10px; padding: 11px; }
      .ap-cn-item + .ap-cn-item { margin-top: 9px; }
      .ap-cn-title { font-weight: 700; }
      .ap-cn-sub { font-size: 11px; }
      .ap-cn-photo { width: 34px; height: 34px; border-radius: 8px; overflow: hidden;
        background: #0b1424; border: 1px solid var(--tmd-border); display: grid;
        place-items: center; font-size: 15px; color: var(--tmd-accent); flex: none; }
      .ap-cn-photo img { width: 100%; height: 100%; object-fit: cover; }

      /* Clean Pro — divided list */
      .ap-cp-item { padding: 10px 0; }
      .ap-cp-title { font-weight: 600; }
      .ap-cp-sub { font-size: 12px; }
      .ap-cp-photo { width: 32px; height: 32px; border-radius: 8px; overflow: hidden;
        background: var(--tmd-surface-2); border: 1px solid var(--tmd-border); display: grid;
        place-items: center; font-size: 14px; flex: none; }
      .ap-cp-photo img { width: 100%; height: 100%; object-fit: cover; }
      .ap-gold-soft { color: var(--tmd-gold); }

      .ap-d-photo-link { line-height: 0; text-decoration: none; }

      /* Scrollable list (parity with classic content) */
      .ap-d-scroll { max-height: 360px; overflow-y: auto; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
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
      entity: "sensor.taskmate_overview",
      title: "Pending Approvals",
    };
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

    // Support both the pending_approvals sensor (chore_completions)
    // and the overview sensor (todays_completions filtered to unapproved).
    // The resolver is used so pending_reward_claims / todays_completions
    // resolve from their new companion sensors when the card is pointed at
    // the overview entity.
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    // Prefer the full pending list (chore_completions, resolved from the
    // pending_approvals companion sensor) so approvals left pending from a
    // previous day still appear after a recurring chore resets at midnight.
    // Fall back to today's completions only on older backends that don't
    // expose chore_completions via the resolver.
    let completions = attrs.chore_completions;
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

    // Missed mandatory chores awaiting parent review (#532)
    const misses = this._filterMissesByChild(attrs.mandatory_misses || []);

    const totalPending = filteredCompletions.length + filteredClaims.length + misses.length;

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, '#27ae60')}; }</style>
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
                ${misses.length > 0 ? this._renderMandatoryMisses(misses) : ''}
                ${filteredClaims.length > 0 ? this._renderRewardClaims(filteredClaims) : ''}
                ${filteredCompletions.length > 0 ? this._renderApprovals(groupedByDay) : ''}
              `}
        </div>
      </ha-card>
    `;
  }

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns/frag/11-approvals.html.
     Wraps the SAME data + handlers as the classic path.
  ══════════════════════════════════════════════════════════════════════ */

  _designTone(i) { return `var(--tmd-c${(i % 6) + 1})`; }

  _av(name, avatar, tone, size) {
    const a = avatar || "";
    const inner = a.startsWith("mdi:")
      ? html`<ha-icon icon="${a}"></ha-icon>`
      : a
        ? html`<img src="${a}" alt="${name || ''}">`
        : (name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
    return html`<div class="av" style="--av:${size}px;--ac:${tone}">${inner}</div>`;
  }

  // Resolve a child's avatar from the overview sensor's children list (the
  // completion/claim payloads don't carry an avatar field).
  _childAvatar(childId) {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
    const child = (attrs.children || []).find(c => c.id === childId);
    return child ? child.avatar : null;
  }

  // Flatten all pending items into a single ordered, day/time-grouped list so
  // the designed views can render approvals, reward claims and mandatory misses
  // together while reusing every existing handler.
  _designItems() {
    const entity = this.hass.states[this.config.entity];
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};

    let completions = attrs.chore_completions;
    if (!completions) completions = (attrs.todays_completions || []).filter(c => !c.approved);
    const filteredCompletions = this._filterByChild(completions);

    const rewardClaims = entity.attributes.reward_claims || attrs.pending_reward_claims || [];
    const filteredClaims = this._filterClaimsByChild(rewardClaims);

    const misses = this._filterMissesByChild(attrs.mandatory_misses || []);

    const items = [];

    misses.forEach((miss) => {
      const penalty = miss.penalty_points ?? 0;
      items.push({
        kind: "miss",
        id: miss.id,
        title: miss.chore_name || "",
        childName: miss.child_name || "",
        childId: miss.child_id,
        points: penalty,
        penalty,
        sortTime: 0,
      });
    });

    filteredClaims.forEach((claim) => {
      const claimId = claim.claim_id || claim.id;
      items.push({
        kind: "claim",
        id: claimId,
        title: claim.reward_name || "",
        childName: claim.child_name || "",
        childId: claim.child_id,
        points: claim.cost ?? 0,
        icon: claim.reward_icon || "mdi:gift",
        sortTime: claim.claimed_at ? new Date(claim.claimed_at).getTime() : 1,
      });
    });

    filteredCompletions.forEach((c) => {
      items.push({
        kind: "completion",
        completion: c,
        id: c.completion_id,
        title: c.chore_name || "",
        childName: c.child_name || "",
        childId: c.child_id,
        points: c.points,
        photo: c.photo_url || "",
        completedAt: c.completed_at,
        timeCategory: c.time_category || "anytime",
        sortTime: c.completed_at ? new Date(c.completed_at).getTime() : 2,
      });
    });

    return items;
  }

  // Group designed items by day label, then by time-category, mirroring the
  // classic _groupByDay/_renderTimeCategories ordering. Non-completion items
  // (misses/claims) bucket under "Today" so they stay visible at the top.
  _designGrouped(items) {
    const groups = new Map();
    const todayLabel = this._t('common.today');
    items.forEach((it) => {
      let dayLabel = todayLabel;
      let cat = "anytime";
      if (it.kind === "completion" && it.completedAt) {
        dayLabel = this._getDayLabel(new Date(it.completedAt));
        cat = it.timeCategory || "anytime";
      }
      if (!groups.has(dayLabel)) groups.set(dayLabel, new Map());
      const cats = groups.get(dayLabel);
      if (!cats.has(cat)) cats.set(cat, []);
      cats.get(cat).push(it);
    });
    // Build ordered list of { dayLabel, sub, items[] } sections.
    const sections = [];
    for (const [dayLabel, cats] of groups) {
      const ordered = [...cats.entries()].sort(
        ([a], [b]) => this._getTimeCategoryOrder(a) - this._getTimeCategoryOrder(b)
      );
      for (const [cat, list] of ordered) {
        const sub = cat === "anytime" ? dayLabel : `${dayLabel} · ${this._getTimeCategoryLabel(cat)}`;
        sections.push({ label: sub, items: list });
      }
    }
    return sections;
  }

  _renderDesigned(design) {
    const entity = this.hass.states[this.config.entity];
    const hd = _safeColor(this.config.header_color, '#27ae60');

    if (!entity) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${this._designHeader(hd, 0)}
        <div class="tmd-bd"><div class="tmd-empty">${this._t('common.entity_not_found', { entity: this.config.entity })}</div></div>
      </ha-card>`;
    }

    const items = this._designItems();
    const sections = this._designGrouped(items);

    let body;
    if (!items.length) {
      body = html`<div class="tmd-empty">${this._t('approvals.no_pending_approvals')}</div>`;
    } else {
      const rowFn =
        design === "playroom" ? (it, i) => this._apPlayroom(it, i) :
        design === "console"  ? (it, i) => this._apConsole(it, i) :
                                (it, i) => this._apCleanpro(it, i);
      let idx = 0;
      body = html`<div class="ap-d-scroll">${sections.map((sec) => html`
        <div class="ap-group-label muted">${sec.label}</div>
        ${sec.items.map((it) => rowFn(it, idx++))}
      `)}</div>`;
    }

    return html`<ha-card class="tmd" style="--hd:${hd}">
      ${this._designHeader(hd, items.length)}
      <div class="tmd-bd">${body}</div>
    </ha-card>`;
  }

  _designHeader(hd, count) {
    const title = this.config.title || this._t('approvals.default_title');
    return html`
      <div class="tmd-hd">
        <span class="ic">✅</span>
        <span class="tt">${title}</span>
        ${count > 0 ? html`<span class="cnt">${count}</span>` : ""}
      </div>`;
  }

  // Approve/reject (or miss-review) buttons wired to the EXISTING handlers,
  // varying only label/shape per design.
  _designActions(it, shape) {
    const isLoading = !!this._loading[it.id];
    if (it.kind === "completion") {
      const approve = () => this._handleApprove(it.completion);
      const reject = () => this._handleReject(it.completion);
      return this._apActionPair(approve, reject, isLoading, shape);
    }
    if (it.kind === "claim") {
      const approve = () => this._handleApproveReward(it.id);
      const reject = () => this._handleRejectReward(it.id);
      return this._apActionPair(approve, reject, isLoading, shape);
    }
    // mandatory miss: apply penalty (if any) / postpone / dismiss
    if (shape === "round") {
      return html`
        ${it.penalty > 0 ? html`<button class="btn bad sm round" ?disabled="${isLoading}"
          title="${this._t('approvals.apply_penalty')}"
          @click="${() => this._handleApplyPenalty(it.id)}">!</button>` : ""}
        <button class="btn ghost sm round" ?disabled="${isLoading}"
          title="${this._t('approvals.postpone')}"
          @click="${() => this._handlePostpone(it.id)}">⏲</button>
        <button class="btn good sm round" ?disabled="${isLoading}"
          title="${this._t('approvals.dismiss')}"
          @click="${() => this._handleDismiss(it.id)}">✓</button>`;
    }
    const sm = shape === "sm" ? "sm" : "";
    return html`
      ${it.penalty > 0 ? html`<button class="btn bad ${sm}" ?disabled="${isLoading}"
        @click="${() => this._handleApplyPenalty(it.id)}">${this._t('approvals.apply_penalty')}</button>` : ""}
      <button class="btn ghost ${sm}" ?disabled="${isLoading}"
        @click="${() => this._handlePostpone(it.id)}">${this._t('approvals.postpone')}</button>
      <button class="btn good ${sm}" ?disabled="${isLoading}"
        @click="${() => this._handleDismiss(it.id)}">${this._t('approvals.dismiss')}</button>`;
  }

  _apActionPair(approve, reject, isLoading, shape) {
    if (shape === "round") {
      return html`
        <button class="btn good sm round" ?disabled="${isLoading}"
          title="${this._t('approvals.approve')}" @click="${approve}">✓</button>
        <button class="btn bad sm round" ?disabled="${isLoading}"
          title="${this._t('approvals.reject')}" @click="${reject}">✕</button>`;
    }
    if (shape === "ghost") {
      return html`
        <button class="btn good sm" ?disabled="${isLoading}" @click="${approve}">${this._t('approvals.approve')}</button>
        <button class="btn ghost sm" ?disabled="${isLoading}" @click="${reject}">${this._t('approvals.reject')}</button>`;
    }
    return html`
      <button class="btn good" style="flex:1" ?disabled="${isLoading}" @click="${approve}">👍 ${this._t('approvals.approve')}</button>
      <button class="btn bad" style="flex:1" ?disabled="${isLoading}" @click="${reject}">👎 ${this._t('approvals.reject')}</button>`;
  }

  _apPhotoDesigned(it, cls, fallback) {
    const photoUrl = tmSafePhotoUrl(it.photo);
    if (it.kind !== "completion" || !photoUrl) {
      return it.kind === "claim" && it.icon
        ? html`<div class="${cls}"><ha-icon icon="${it.icon}"></ha-icon></div>`
        : "";
    }
    return html`<a class="ap-d-photo-link" href="${photoUrl}" target="_blank" rel="noopener"
      title="${this._t('approvals.view_photo') || 'View photo'}"><div class="${cls}"><img src="${photoUrl}" alt=""></div></a>`;
  }

  _apPlayroom(it, i) {
    const tone = this._designTone(i);
    return html`
      <div class="ap-pl-item" style="--ac:${tone}">
        <div class="row">
          ${this._av(it.childName, this._childAvatar(it.childId), tone, 40)}
          <div style="flex:1;min-width:0">
            <div class="ap-pl-title">${it.title}</div>
            <div class="muted ap-pl-sub">${it.childName}</div>
          </div>
          ${this._apPhotoDesigned(it, "ap-pl-photo")}
          <div class="chip ap-gold">+${it.points} ⭐</div>
        </div>
        <div class="row" style="margin-top:11px;gap:8px">
          ${this._designActions(it, "full")}
        </div>
      </div>`;
  }

  _apConsole(it, i) {
    const tone = this._designTone(i);
    return html`
      <div class="row ap-cn-item" style="--ac:${tone}">
        ${this._av(it.childName, this._childAvatar(it.childId), tone, 34)}
        <div style="flex:1;min-width:0">
          <div class="ap-cn-title">${it.title}</div>
          <div class="muted num ap-cn-sub">${(it.childName || '').toUpperCase()} · +${it.points} XP</div>
        </div>
        ${this._apPhotoDesigned(it, "ap-cn-photo")}
        ${this._designActions(it, "round")}
      </div>`;
  }

  _apCleanpro(it, i) {
    const tone = this._designTone(i);
    const time = it.completedAt
      ? new Date(it.completedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "";
    return html`
      <div class="row ap-cp-item" style="--ac:${tone}">
        ${this._av(it.childName, this._childAvatar(it.childId), tone, 38)}
        <div style="flex:1;min-width:0">
          <div class="ap-cp-title">${it.title}</div>
          <div class="muted ap-cp-sub">${it.childName}${time ? html` · ${time}` : ""}</div>
        </div>
        ${this._apPhotoDesigned(it, "ap-cp-photo")}
        <span class="chip soft ap-gold-soft">+${it.points}</span>
        ${this._designActions(it, "ghost")}
      </div>`;
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
          ${this._t('approvals.reward_claims_section')}
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
    if (this._loading[claimId]) return;
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

  // ---- mandatory-miss review (#532) ------------------------------------
  _filterMissesByChild(misses) {
    if (!this.config.child_id) return misses;
    return misses.filter((m) => m.child_id === this.config.child_id);
  }

  _renderMandatoryMisses(misses) {
    return html`
      <div class="day-group">
        <div class="day-header">
          <ha-icon icon="mdi:alert-octagon-outline" style="--mdc-icon-size: 18px; vertical-align: -3px; margin-right: 6px;"></ha-icon>
          ${this._t('approvals.mandatory_section')}
        </div>
        ${misses.map((miss) => this._renderMissItem(miss))}
      </div>
    `;
  }

  _renderMissItem(miss) {
    const missId = miss.id;
    const isLoading = this._loading[missId];
    const choreName = miss.chore_name || '';
    const childName = miss.child_name || '';
    const penalty = miss.penalty_points ?? 0;

    return html`
      <div class="approval-item mandatory ${isLoading ? 'loading' : ''}">
        <div class="item-info">
          <span class="chore-name">
            <ha-icon icon="mdi:alert-circle-outline" style="--mdc-icon-size: 16px; vertical-align: -3px; margin-right: 4px;"></ha-icon>
            ${choreName}
          </span>
          <div class="item-details">
            <span class="child-name">
              <ha-icon icon="mdi:account"></ha-icon>
              ${childName}
            </span>
          </div>
          ${penalty > 0
            ? html`<span class="penalty-note">${this._t('approvals.penalty_points', { points: penalty })}</span>`
            : html`<span class="penalty-note none">${this._t('approvals.no_penalty')}</span>`}
        </div>
        <div class="action-buttons right">
          ${penalty > 0 ? html`
            <button
              class="action-button penalty ${isLoading ? 'loading' : ''}"
              @click="${() => this._handleApplyPenalty(missId)}"
              title="${this._t('approvals.apply_penalty')}"
              ?disabled="${isLoading}"
            >
              <ha-icon icon="mdi:alert-circle"></ha-icon>
            </button>
          ` : ''}
          <button
            class="action-button postpone ${isLoading ? 'loading' : ''}"
            @click="${() => this._handlePostpone(missId)}"
            title="${this._t('approvals.postpone')}"
            ?disabled="${isLoading}"
          >
            <ha-icon icon="mdi:clock-plus-outline"></ha-icon>
          </button>
          <button
            class="action-button dismiss ${isLoading ? 'loading' : ''}"
            @click="${() => this._handleDismiss(missId)}"
            title="${this._t('approvals.dismiss')}"
            ?disabled="${isLoading}"
          >
            <ha-icon icon="mdi:check"></ha-icon>
          </button>
        </div>
      </div>
    `;
  }

  async _handleApplyPenalty(missId) {
    await this._callMissService('apply_mandatory_penalty', missId);
  }

  async _handlePostpone(missId) {
    await this._callMissService('postpone_mandatory_chore', missId);
  }

  async _handleDismiss(missId) {
    await this._callMissService('dismiss_mandatory_chore', missId);
  }

  async _callMissService(service, missId) {
    if (this._loading[missId]) return;
    this._loading = { ...this._loading, [missId]: true };
    this.requestUpdate();
    try {
      await this.hass.callService('taskmate', service, { miss_id: missId });
    } catch (error) {
      console.error(`Failed to call ${service}:`, error);
      if (this.hass.callService) {
        this.hass.callService('persistent_notification', 'create', {
          title: this._t('approvals.error_title'),
          message: this._t('approvals.error_failed_service', {
            service: service.replace(/_/g, ' '),
            message: error.message,
          }),
          notification_id: `taskmate_error_${missId}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [missId]: false };
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

  // User-defined periods from the overview sensor; legacy fixed four when
  // the integration hasn't published time_periods yet.
  _getTimePeriods() {
    const entity = this.hass?.states?.[this.config?.entity];
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || entity?.attributes || {};
    if (Array.isArray(attrs.time_periods) && attrs.time_periods.length) {
      return attrs.time_periods.filter(p => p && p.id);
    }
    return [
      { id: "morning",   label: "", icon: "mdi:weather-sunset-up" },
      { id: "afternoon", label: "", icon: "mdi:weather-sunny" },
      { id: "evening",   label: "", icon: "mdi:weather-sunset-down" },
      { id: "night",     label: "", icon: "mdi:weather-night" },
    ];
  }

  _getTimeCategoryIcon(category) {
    const period = this._getTimePeriods().find(p => p.id === category);
    if (period && period.icon) return period.icon;
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
    const period = this._getTimePeriods().find(p => p.id === category);
    if (period && period.label) return period.label;
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
    const ids = this._getTimePeriods().map(p => p.id);
    const idx = ids.indexOf(category);
    if (idx >= 0) return idx;
    return category === "anytime" ? ids.length : ids.length + 1;
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
                ${this._t('approvals.timed_duration', {count: Math.floor(completion.timed_duration_seconds / 60)})}
              </span>
            ` : ''}
            <span class="points-badge">
              <ha-icon icon="mdi:star"></ha-icon>
              ${completion.points}
            </span>
          </div>
          ${tmSafePhotoUrl(completion.photo_url) ? html`
            <a class="approval-photo" href="${tmSafePhotoUrl(completion.photo_url)}" target="_blank" rel="noopener"
               title="${this._t('approvals.view_photo') || 'View photo'}">
              <img src="${tmSafePhotoUrl(completion.photo_url)}" alt="" loading="lazy">
            </a>
          ` : ''}
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
    if (this._loading[completionId]) return;
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
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.entity'),
      title: this._t('common.title'),
      child_id: this._t('approvals.editor.child_id'),
      card_design: this._t('common.design.field_label'),
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
      card_design: this.config.card_design || 'global',
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
      if (
        value === '' || value === null || value === undefined
        || (key === 'child_id' && value === '__all__')
        || (key === 'card_design' && value === 'global')
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
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-approvals-card", "overview"),
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
