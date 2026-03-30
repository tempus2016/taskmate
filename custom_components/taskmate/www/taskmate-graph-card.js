/**
 * TaskMate Points Graph Card
 * Line graph tracking points earned per day or cumulative total.
 * Configurable time range, per-child or combined view, toggle between modes.
 *
 * Version: 1.0.0
 * Last Updated: 2026-03-18
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

// Child colors — matches the streak/jackpot palette
const CHILD_COLORS = [
  { line: "#9b59b6", fill: "rgba(155,89,182,0.15)" },
  { line: "#3498db", fill: "rgba(52,152,219,0.15)" },
  { line: "#2ecc71", fill: "rgba(46,204,113,0.15)" },
  { line: "#e67e22", fill: "rgba(230,126,34,0.15)" },
  { line: "#e74c3c", fill: "rgba(231,76,60,0.15)" },
  { line: "#1abc9c", fill: "rgba(26,188,156,0.15)" },
];

class TaskMateGraphCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _mode: { type: String }, // "daily" | "cumulative"
    };
  }

  constructor() {
    super();
    this._mode = "daily";
  }

  static get styles() {
    return css`
      :host {
        display: block;
        --gr-purple: #9b59b6;
        --gr-purple-light: #a569bd;
        --gr-gold: #f1c40f;
        --gr-green: #2ecc71;
        --gr-blue: #3498db;
      }

      ha-card { overflow: hidden; }

      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #d35400);
        color: white;
        gap: 12px;
      }

      .header-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
      .header-icon { --mdc-icon-size: 26px; opacity: 0.9; flex-shrink: 0; }
      .header-title { font-size: 1.15rem; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

      .mode-toggle {
        display: flex;
        background: rgba(255,255,255,0.12);
        border-radius: 20px;
        padding: 3px;
        gap: 2px;
        flex-shrink: 0;
      }

      .mode-btn {
        background: none;
        border: none;
        color: rgba(255,255,255,0.6);
        padding: 4px 10px;
        border-radius: 16px;
        font-size: 0.75rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        white-space: nowrap;
      }

      .mode-btn.active {
        background: rgba(255,255,255,0.2);
        color: white;
      }

      .mode-btn:hover:not(.active) {
        color: rgba(255,255,255,0.85);
      }

      .card-content {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }

      /* Legend */
      .legend {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 16px;
        padding: 0 4px;
      }

      .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.8rem;
        color: var(--secondary-text-color);
        font-weight: 500;
      }

      .legend-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      /* SVG chart container */
      .chart-wrap {
        position: relative;
        width: 100%;
        min-height: 180px;
      }

      /* Tooltip */
      .tooltip {
        position: absolute;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 0.8rem;
        color: var(--primary-text-color);
        box-shadow: 0 4px 16px rgba(0,0,0,0.15);
        pointer-events: none;
        z-index: 10;
        white-space: nowrap;
        display: none;
      }

      .tooltip.visible { display: block; }

      .tooltip-date {
        font-weight: 700;
        margin-bottom: 4px;
        color: var(--secondary-text-color);
        font-size: 0.75rem;
      }

      .tooltip-row {
        display: flex;
        align-items: center;
        gap: 6px;
        margin: 2px 0;
      }

      .tooltip-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      /* Empty / error */
      .error-state, .empty-state {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; padding: 40px 20px;
        color: var(--secondary-text-color); text-align: center;
      }
      .error-state { color: var(--error-color, #f44336); }
      .error-state ha-icon, .empty-state ha-icon { --mdc-icon-size: 48px; margin-bottom: 12px; opacity: 0.5; }
      .empty-state .message { font-size: 1rem; color: var(--primary-text-color); }
      .empty-state .submessage { font-size: 0.85rem; margin-top: 4px; }

      @media (max-width: 480px) {
        .card-header { padding: 12px 14px; }
        .header-title { font-size: 1rem; }
        .mode-btn { padding: 3px 8px; font-size: 0.7rem; }
        .card-content { padding: 12px; }
      }
    `;
  }

  setConfig(config) {
    if (!config.entity) throw new Error("Please define an entity");
    this.config = {
      title: "Points Graph",
      child_id: null,
      days: 14,
            header_color: '#d35400',
    ...config,
    };
  }

  getCardSize() { return 4; }
  static getConfigElement() { return document.createElement("taskmate-graph-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.taskmate_overview", title: "Points Graph", days: 14 };
  }

  render() {
    try {
      return this._render();
    } catch(e) {
      console.error("[TaskMateGraph] Render error:", e);
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>Graph error: ${e.message}</div></div></ha-card>`;
    }
  }

  _render() {
    if (!this.hass || !this.config) return html``;

    const entity = this.hass.states[this.config.entity];
    if (!entity) {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>Entity not found: ${this.config.entity}</div></div></ha-card>`;
    }
    if (entity.state === "unavailable" || entity.state === "unknown") {
      return html`<ha-card><div class="error-state"><ha-icon icon="mdi:alert-circle"></ha-icon><div>TaskMate is unavailable</div></div></ha-card>`;
    }

    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    let children = entity.attributes.children || [];
    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Points";
    const days = Math.max(3, Math.min(90, this.config.days || 14));

    // Filter to specific child if configured
    if (this.config.child_id) {
      children = children.filter(c => c.id === this.config.child_id);
    }

    // Get all completions (approved only for points)
    const allCompletions = [
      ...(entity.attributes.recent_completions || entity.attributes.todays_completions || []),
    ].filter(c => c.approved);

    // Get manual transactions
    const allTransactions = entity.attributes.recent_transactions || [];

    // Build chore points map
    const chorePointsMap = {};
    (entity.attributes.chores || []).forEach(ch => { chorePointsMap[ch.id] = ch.points || 0; });

    // Build date range
    const dateRange = this._buildDateRange(days, tz);

    // Build per-child data series
    const series = children.map((child, idx) => {
      const color = CHILD_COLORS[idx % CHILD_COLORS.length];
      const dailyPoints = this._buildDailyPoints(
        child.id, dateRange, allCompletions, allTransactions, chorePointsMap, tz
      );
      const cumulativePoints = this._buildCumulative(dailyPoints);
      return { child, color, dailyPoints, cumulativePoints };
    });

    if (series.length === 0) {
      return html`<ha-card><div class="empty-state"><ha-icon icon="mdi:account-group"></ha-icon><div>No children found</div></div></ha-card>`;
    }

    const dataKey = this._mode === "daily" ? "dailyPoints" : "cumulativePoints";
    const hasData = series.some(s => s[dataKey].some(v => v > 0));

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#d35400'}; }</style>
        <div class="card-header">
          <div class="header-left">
            <ha-icon class="header-icon" icon="mdi:chart-line"></ha-icon>
            <span class="header-title">${this.config.title}</span>
          </div>
          <div class="mode-toggle">
            <button
              class="mode-btn ${this._mode === 'daily' ? 'active' : ''}"
              @click="${() => { this._mode = 'daily'; this.requestUpdate(); }}"
            >Daily</button>
            <button
              class="mode-btn ${this._mode === 'cumulative' ? 'active' : ''}"
              @click="${() => { this._mode = 'cumulative'; this.requestUpdate(); }}"
            >Total</button>
          </div>
        </div>

        <div class="card-content">
          ${series.length > 1 ? html`
            <div class="legend">
              ${series.map(s => html`
                <div class="legend-item">
                  <div class="legend-dot" style="background: ${s.color.line};"></div>
                  <span>${s.child.name}</span>
                </div>
              `)}
            </div>
          ` : ''}

          ${hasData
            ? this._renderChart(series, dateRange, dataKey, pointsName)
            : html`
              <div class="empty-state">
                <ha-icon icon="mdi:chart-line-variant"></ha-icon>
                <div class="message">No data yet</div>
                <div class="submessage">Complete and approve chores to see the graph</div>
              </div>
            `}
        </div>
      </ha-card>
      <div class="tooltip" id="graph-tooltip-${this._tooltipId}"></div>
    `;
  }

  get _tooltipId() {
    if (!this.__tid) this.__tid = Math.random().toString(36).slice(2, 8);
    return this.__tid;
  }

  _renderChart(series, dateRange, dataKey, pointsName) {
    // Store for canvas drawing after render
    this._chartData = { series, dateRange, dataKey, pointsName };

    return html`
      <div class="chart-wrap"
        @mousemove="${(e) => this._onChartInteract(e, false)}"
        @mouseleave="${() => this._hideTooltip()}"
        @touchmove="${(e) => this._onChartInteract(e, true)}"
        @touchend="${() => this._hideTooltip()}"
      >
        <canvas
          id="chart-canvas-${this._tooltipId}"
          height="180"
          style="width:100%;height:180px;display:block;"
        ></canvas>
        <div id="hover-line-${this._tooltipId}" style="
          position: absolute; top: 16px; width: 1px;
          height: 136px; background: var(--divider-color, #ccc);
          pointer-events: none; display: none;
        "></div>
      </div>
    `;
  }

  updated() {
    this._drawCanvas();
  }

  _drawCanvas() {
    if (!this._chartData) return;
    const canvas = this.shadowRoot?.querySelector(`#chart-canvas-${this._tooltipId}`);
    if (!canvas) return;

    const { series, dateRange, dataKey } = this._chartData;
    const DPR = window.devicePixelRatio || 1;
    const W = canvas.offsetWidth || 300;
    const H = 180;

    canvas.width = W * DPR;
    canvas.height = H * DPR;

    const ctx = canvas.getContext('2d');
    ctx.scale(DPR, DPR);

    const PAD = { top: 16, right: 16, bottom: 28, left: 36 };
    const innerW = W - PAD.left - PAD.right;
    const innerH = H - PAD.top - PAD.bottom;
    const n = dateRange.length;

    const allValues = series.flatMap(s => s[dataKey]);
    const maxVal = Math.max(1, ...allValues);
    const niceMax = this._niceMax(maxVal);
    const yTicks = this._yTicks(niceMax);

    const xPos = (i) => PAD.left + (i / Math.max(n - 1, 1)) * innerW;
    const yPos = (v) => PAD.top + innerH - (v / niceMax) * innerH;

    // Store for tooltip use
    this._xPos = xPos;
    this._PAD = PAD;
    this._innerH = innerH;
    this._canvasW = W;

    // Get computed colours from CSS
    const style = getComputedStyle(this);
    const gridColor = style.getPropertyValue('--divider-color').trim() || '#e0e0e0';
    const textColor = style.getPropertyValue('--secondary-text-color').trim() || '#888';

    ctx.clearRect(0, 0, W, H);

    // Y grid lines and labels
    ctx.font = '10px sans-serif';
    ctx.textBaseline = 'middle';
    for (const tick of yTicks) {
      const y = yPos(tick);
      ctx.strokeStyle = gridColor;
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 3]);
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(W - PAD.right, y);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = textColor;
      ctx.textAlign = 'right';
      ctx.fillText(tick, PAD.left - 4, y);
    }

    // Zero line (solid)
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(PAD.left, yPos(0));
    ctx.lineTo(W - PAD.right, yPos(0));
    ctx.stroke();

    // Area fills
    for (const s of series) {
      const data = s[dataKey];
      ctx.beginPath();
      ctx.moveTo(xPos(0), yPos(data[0]));
      for (let i = 1; i < n; i++) ctx.lineTo(xPos(i), yPos(data[i]));
      ctx.lineTo(xPos(n - 1), yPos(0));
      ctx.lineTo(xPos(0), yPos(0));
      ctx.closePath();
      ctx.fillStyle = s.color.fill;
      ctx.fill();
    }

    // Lines
    for (const s of series) {
      const data = s[dataKey];
      ctx.strokeStyle = s.color.line;
      ctx.lineWidth = 2.5;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.moveTo(xPos(0), yPos(data[0]));
      for (let i = 1; i < n; i++) ctx.lineTo(xPos(i), yPos(data[i]));
      ctx.stroke();
    }

    // Dots
    for (const s of series) {
      const data = s[dataKey];
      for (let i = 0; i < n; i++) {
        if (data[i] > 0) {
          ctx.beginPath();
          ctx.arc(xPos(i), yPos(data[i]), 3.5, 0, Math.PI * 2);
          ctx.fillStyle = s.color.line;
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      }
    }

    // X axis labels
    const labelEvery = n <= 7 ? 1 : n <= 14 ? 2 : n <= 31 ? 4 : 7;
    ctx.fillStyle = textColor;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.font = '10px sans-serif';
    dateRange.forEach((d, i) => {
      if (i % labelEvery === 0 || i === n - 1) {
        ctx.fillText(this._shortDate(d), xPos(i), H - 4);
      }
    });
  }

  _onChartInteract(e, isTouch) {
    if (!this._chartData || !this._xPos) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = isTouch ? e.touches[0]?.clientX : e.clientX;
    if (clientX === undefined) return;
    if (isTouch) e.preventDefault();
    const xPx = clientX - rect.left;

    const { series, dateRange, dataKey, pointsName } = this._chartData;
    const n = dateRange.length;
    const xPos = this._xPos;

    // Scale pixel position to canvas coordinate space
    const scaledX = (xPx / rect.width) * this._canvasW;

    let nearest = 0;
    let minDist = Infinity;
    for (let i = 0; i < n; i++) {
      const dist = Math.abs(xPos(i) - scaledX);
      if (dist < minDist) { minDist = dist; nearest = i; }
    }

    const date = dateRange[nearest];
    const tooltip = this.shadowRoot?.querySelector(`#graph-tooltip-${this._tooltipId}`);
    const hoverLine = this.shadowRoot?.querySelector(`#hover-line-${this._tooltipId}`);

    if (hoverLine) {
      const lineX = (xPos(nearest) / this._canvasW) * rect.width;
      hoverLine.style.left = `${lineX}px`;
      hoverLine.style.display = 'block';
    }

    if (!tooltip) return;
    const dateLabel = this._formatTooltipDate(date);
    let html_content = `<div class="tooltip-date">${dateLabel}</div>`;
    series.forEach(s => {
      const val = s[dataKey][nearest] || 0;
      html_content += `<div class="tooltip-row"><div class="tooltip-dot" style="background:${s.color.line}"></div><span>${series.length > 1 ? s.child.name + ': ' : ''}${val} ${pointsName}</span></div>`;
    });
    tooltip.innerHTML = html_content;
    tooltip.classList.add('visible');

    const tipW = 150;
    let left = (xPos(nearest) / this._canvasW) * rect.width - tipW / 2;
    left = Math.max(4, Math.min(left, rect.width - tipW - 4));
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${this._PAD.top}px`;
  }

  _hideTooltip() {
    const tooltip = this.shadowRoot?.querySelector(`#graph-tooltip-${this._tooltipId}`);
    const hoverLine = this.shadowRoot?.querySelector(`#hover-line-${this._tooltipId}`);
    if (tooltip) tooltip.classList.remove('visible');
    if (hoverLine) hoverLine.style.display = 'none';
  }

  // ── Data helpers ─────────────────────────────────────────────

  _buildDateRange(days, tz) {
    const range = [];
    const today = new Date();
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      range.push(d.toLocaleDateString("en-CA", { timeZone: tz }));
    }
    return range;
  }

  _buildDailyPoints(childId, dateRange, completions, transactions, chorePointsMap, tz) {
    const byDay = {};
    dateRange.forEach(d => { byDay[d] = 0; });

    // Approved chore completions
    completions
      .filter(c => c.child_id === childId)
      .forEach(c => {
        const day = new Date(c.completed_at).toLocaleDateString("en-CA", { timeZone: tz });
        if (day in byDay) {
          byDay[day] += c.points !== undefined ? c.points : (chorePointsMap[c.chore_id] || 0);
        }
      });

    // Manual transactions (positive only for points earned; include removes too if desired)
    transactions
      .filter(t => t.child_id === childId)
      .forEach(t => {
        const day = new Date(t.created_at).toLocaleDateString("en-CA", { timeZone: tz });
        if (day in byDay) {
          byDay[day] += t.points || 0; // negative for removals
        }
      });

    return dateRange.map(d => Math.max(0, byDay[d]));
  }

  _buildCumulative(dailyPoints) {
    let running = 0;
    return dailyPoints.map(v => { running += v; return running; });
  }

  _niceMax(val) {
    if (val <= 10) return 10;
    if (val <= 20) return 20;
    if (val <= 50) return 50;
    const magnitude = Math.pow(10, Math.floor(Math.log10(val)));
    return Math.ceil(val / magnitude) * magnitude;
  }

  _yTicks(max) {
    const count = 4;
    const step = max / count;
    return Array.from({ length: count + 1 }, (_, i) => Math.round(i * step));
  }

  _shortDate(dateStr) {
    const d = new Date(dateStr + "T12:00:00");
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }

  _formatTooltipDate(dateStr) {
    const d = new Date(dateStr + "T12:00:00");
    const today = new Date().toLocaleDateString("en-CA");
    const yesterday = new Date(Date.now() - 86400000).toLocaleDateString("en-CA");
    if (dateStr === today) return "Today";
    if (dateStr === yesterday) return "Yesterday";
    return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  }
}

// ── Card Editor ──────────────────────────────────────────────
class TaskMateGraphCardEditor extends LitElement {
  static get properties() {
    return { hass: { type: Object }, config: { type: Object } };
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-textfield { width: 100%; margin-bottom: 16px; }
      .form-row { margin-bottom: 16px; }
      .form-label {
        display: block;
        font-size: 0.85rem;
        font-weight: 500;
        color: var(--primary-text-color);
        margin-bottom: 6px;
        padding: 0 2px;
      }
      .form-select {
        width: 100%;
        padding: 10px 12px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 1rem;
        box-sizing: border-box;
        cursor: pointer;
        appearance: auto;
      }
      .form-select:focus {
        outline: none;
        border-color: var(--primary-color);
      }
      .form-helper {
        display: block;
        font-size: 0.78rem;
        color: var(--secondary-text-color);
        margin-top: 4px;
        padding: 0 2px;
      }
    `;
  }

  setConfig(config) { this.config = config; }

  render() {
    if (!this.hass || !this.config) return html``;
    const entity = this.config.entity ? this.hass.states[this.config.entity] : null;
    const children = entity?.attributes?.children || [];

    return html`
      <ha-textfield
        label="Overview Entity"
        .value="${this.config.entity || ""}"
        @change="${e => this._updateConfig('entity', e.target.value)}"
        helper="The TaskMate overview sensor entity"
        helperPersistent
        placeholder="sensor.taskmate_overview"
      ></ha-textfield>

      <ha-textfield
        label="Title"
        .value="${this.config.title || ""}"
        @change="${e => this._updateConfig('title', e.target.value)}"
        placeholder="Points Graph"
      ></ha-textfield>

      <ha-textfield
        label="Days to show"
        type="number"
        .value="${String(this.config.days || 14)}"
        @change="${e => this._updateConfig('days', parseInt(e.target.value) || 14)}"
        helper="Number of days to display (3–90)"
        helperPersistent
      ></ha-textfield>

      <div class="form-row">
        <label class="form-label">Filter by Child (optional)</label>
        <select
          class="form-select"
          .value="${this.config.child_id || ""}"
          @change="${e => this._updateConfig('child_id', e.target.value || null)}"
        >
          <option value="" ?selected="${!this.config.child_id}">All Children</option>
          ${children.map(c => html`
            <option value="${c.id}" ?selected="${this.config.child_id === c.id}">${c.name}</option>
          `)}
        </select>
        <span class="form-helper">Show one child's line or all children together</span>
      </div>
        <span class="field-helper">Card header background colour</span>
      </div>
      <div class="field-row">
        <label class="field-label">Header Colour</label>
        <div style="display:flex;align-items:center;gap:10px;">
          <input
            type="color"
            .value=${this.config.header_color || '#d35400'}
            @input=${e => this._updateConfig('header_color', e.target.value)}
            style="width:48px;height:36px;padding:2px;border:1px solid var(--divider-color,#e0e0e0);border-radius:6px;cursor:pointer;"
          />
          <span style="font-size:13px;color:var(--secondary-text-color);">${this.config.header_color || '#d35400'}</span>
          <button
            style="font-size:11px;color:var(--secondary-text-color);background:none;border:1px solid var(--divider-color,#e0e0e0);border-radius:4px;padding:3px 8px;cursor:pointer;"
            @click=${() => this._updateConfig('header_color', '#d35400')}
          >Reset</button>
        </div>
        <span class="field-helper">Card header background colour</span>
      </div>
    `;
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === null || value === "" || value === undefined) delete newConfig[key];
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

customElements.define("taskmate-graph-card", TaskMateGraphCard);
customElements.define("taskmate-graph-card-editor", TaskMateGraphCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-graph-card",
  name: "TaskMate Points Graph",
  description: "Line graph tracking daily or cumulative points over time",
  preview: true,
});

console.info(
  "%c TASKMATE-GRAPH-CARD %c v1.0.0 ",
  "background: #2c3e50; color: white; font-weight: bold; border-radius: 4px 0 0 4px;",
  "background: #9b59b6; color: white; font-weight: bold; border-radius: 0 4px 4px 0;"
);
