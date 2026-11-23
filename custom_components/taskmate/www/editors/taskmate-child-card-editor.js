/**
 * TaskMate child card editor (visual card editor).
 *
 * Loaded on demand by taskmate-child-card.js getConfigElement(), so a dashboard
 * never downloads or parses it until someone opens the card editor.
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

/** The label of a select field's option, or undefined. */
const byValue = (field, value) => field?.selector?.select?.options?.find((o) => o.value === value)?.label;

// Card Editor
class TaskMateChildCardEditor extends LitElement {
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
      :host { display: block; padding: 4px 0; }
      ha-form { display: block; margin-bottom: 16px; }
      ha-expansion-panel { display: block; margin-bottom: 12px; }
      ha-expansion-panel ha-form { margin-bottom: 0; }
      .section-body { display: flex; flex-direction: column; gap: 16px; padding: 12px 0 8px; }
      .nested { margin-inline-start: 32px; }
    `;
  }

  setConfig(config) {
    this.config = config;
  }

  _timeCategoryEditorOptions(overviewEntity) {
    const builtinLabels = {
      morning: this._t('child.editor.time_category_morning'),
      afternoon: this._t('child.editor.time_category_afternoon'),
      evening: this._t('child.editor.time_category_evening'),
      night: this._t('child.editor.time_category_night'),
    };
    const periods = overviewEntity?.attributes?.time_periods;
    const periodOptions = Array.isArray(periods) && periods.length
      ? periods.filter(p => p && p.id).map(p => ({
          value: p.id,
          label: p.label || builtinLabels[p.id] || p.id,
        }))
      : Object.entries(builtinLabels).map(([value, label]) => ({ value, label }));
    return [
      { value: 'current', label: this._t('child.editor.time_category_current') },
      ...periodOptions,
      { value: 'anytime', label: this._t('child.editor.time_category_anytime') },
      { value: 'all', label: this._t('child.editor.time_category_all') },
    ];
  }

  _buildSchema() {
    const overviewEntity = this.config?.entity
      ? this.hass?.states?.[this.config.entity]
      : null;
    const children = overviewEntity?.attributes?.children || [];

    return [
      { name: 'entity', selector: { entity: { domain: 'sensor' } } },
      {
        name: 'child_id',
        selector: {
          select: {
            options: [
              { value: '', label: this._t('child.editor.select_child') },
              ...children.map((c) => ({ value: c.id, label: c.name })),
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'time_category',
        selector: {
          select: {
            options: this._timeCategoryEditorOptions(overviewEntity),
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
              : [{ value: 'global', label: this._t('common.design.use_global') }],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'density',
        selector: {
          select: {
            options: [
              { value: 'normal', label: this._t('child.editor.density_normal') },
              { value: 'compact', label: this._t('child.editor.density_compact') },
            ],
            mode: 'dropdown',
          },
        },
      },
      { name: 'seasonal', selector: { boolean: {} } },
      {
        name: 'due_days_mode',
        selector: {
          select: {
            options: [
              { value: 'hide', label: this._t('child.editor.due_days_hide') },
              { value: 'dim', label: this._t('child.editor.due_days_dim') },
              { value: 'show', label: this._t('child.editor.due_days_show') },
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'recurrence_done_mode',
        selector: {
          select: {
            options: [
              { value: 'dim', label: this._t('child.editor.recurrence_dim') },
              { value: 'hide', label: this._t('child.editor.recurrence_hide') },
              { value: 'show', label: this._t('child.editor.recurrence_show') },
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'first_come_claimed_mode',
        selector: {
          select: {
            options: [
              { value: 'hide', label: this._t('child.editor.first_come_hide') },
              { value: 'dim', label: this._t('child.editor.first_come_dim') },
              { value: 'show', label: this._t('child.editor.first_come_show') },
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'dependency_mode',
        selector: {
          select: {
            options: [
              { value: 'hide', label: this._t('child.editor.dependency_hide') },
              { value: 'dim', label: this._t('child.editor.dependency_dim') },
              { value: 'show', label: this._t('child.editor.dependency_show') },
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'elapsed_time_mode',
        selector: {
          select: {
            options: [
              { value: 'dim', label: this._t('child.editor.elapsed_dim') },
              { value: 'hide', label: this._t('child.editor.elapsed_hide') },
              { value: 'show', label: this._t('child.editor.elapsed_show') },
            ],
            mode: 'dropdown',
          },
        },
      },
      {
        name: 'set_times_layout',
        selector: {
          select: {
            options: [
              { value: 'family', label: this._t('common.set_times.layout_family') },
              { value: 'rows', label: this._t('common.set_times.layout_rows') },
              { value: 'pills', label: this._t('common.set_times.layout_pills') },
            ],
            mode: 'dropdown',
          },
        },
      },
      { name: 'sort_available_first', selector: { boolean: {} } },
      { name: 'include_anytime_chores', selector: { boolean: {} } },
      { name: 'show_countdown', selector: { boolean: {} } },
      { name: 'show_minutes_left', selector: { boolean: {} } },
      { name: 'show_help_button', selector: { boolean: {} } },
      { name: 'show_mood', selector: { boolean: {} } },
      { name: 'show_weekly_goal', selector: { boolean: {} } },
      { name: 'show_personal_bests', selector: { boolean: {} } },
      { name: 'show_boost_alert', selector: { boolean: {} } },
      { name: 'show_appeals', selector: { boolean: {} } },
      { name: 'show_screen_time', selector: { boolean: {} } },
      { name: 'show_description', selector: { boolean: {} } },
      { name: 'pre_reader', selector: { boolean: {} } },
      { name: 'pre_reader_labels', selector: { boolean: {} } },
      { name: 'pre_reader_points', selector: { boolean: {} } },
      { name: 'show_tour', selector: { boolean: {} } },
      { name: 'show_parent_actions', selector: { boolean: {} } },
      { name: 'debug', selector: { boolean: {} } },
    ];
  }

  /**
   * The editor's collapsible sections (fields picked from _buildSchema() by
   * name). The first three fields always show; Appearance starts open.
   */
  _sections() {
    const byName = Object.fromEntries(this._buildSchema().map((f) => [f.name, f]));
    const pick = (...names) => names.map((n) => byName[n]);
    return {
      top: pick('entity', 'child_id', 'time_category'),
      appearance: pick('card_design', 'density'),
      appearanceMore: pick('seasonal', 'show_description', 'set_times_layout'),
      which: pick('sort_available_first', 'include_anytime_chores', 'due_days_mode', 'recurrence_done_mode',
        'first_come_claimed_mode', 'dependency_mode', 'elapsed_time_mode'),
      kid: pick('show_countdown', 'show_minutes_left', 'show_help_button', 'show_mood', 'show_weekly_goal',
        'show_personal_bests', 'show_boost_alert', 'show_screen_time', 'show_tour', 'pre_reader'),
      kidNested: pick('pre_reader_labels'),
      advanced: pick('show_parent_actions', 'show_appeals', 'pre_reader_points', 'debug'),
    };
  }

  _onOff(on, name) {
    return this._t(on ? 'common.editor.summary_on' : 'common.editor.summary_off', { name });
  }

  _modeWord(value) {
    return ['hide', 'dim', 'show'].includes(value) ? this._t(`common.editor.summary_value_${value}`) : value;
  }

  /** One-line summaries shown under each section title, from the form data. */
  _summaries(data, sections) {
    const join = (parts) => parts.filter(Boolean).join(' · ');
    const design = data.card_design === 'global'
      ? this._t('common.editor.summary_global_design')
      : (byValue(sections.appearance[0], data.card_design) || data.card_design);
    const kidToggles = sections.kid.filter((f) => f.name !== 'pre_reader');
    const which = [
      data.sort_available_first ? this._t('child.editor.summary_available_first') : '',
      this._t('child.editor.summary_not_due', { value: this._modeWord(data.due_days_mode) }),
      this._t('common.editor.summary_missed', { value: this._modeWord(data.elapsed_time_mode) }),
    ].filter(Boolean);
    return {
      appearance: join([
        design,
        byValue(sections.appearance[1], data.density) || data.density,
        this._t(this.config.header_color ? 'common.editor.summary_header_custom' : 'common.editor.summary_header_default'),
        this._onOff(data.seasonal, this._t('common.editor.summary_seasonal')),
      ]),
      which: join([...which, this._t('common.editor.summary_more', { count: sections.which.length - which.length })]),
      kid: join([
        this._t('common.editor.summary_count_on', { on: kidToggles.filter((f) => data[f.name]).length, total: kidToggles.length }),
        this._onOff(data.pre_reader, this._t('child.editor.summary_picture_mode')),
      ]),
      advanced: join([
        this._onOff(data.show_parent_actions, this._t('common.editor.summary_parent_actions')),
        this._onOff(data.show_appeals, this._t('child.editor.summary_appeals')),
        this._onOff(data.debug, this._t('child.editor.summary_debug')),
      ]),
    };
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      child_id: this._t('child.editor.child'),
      time_category: this._t('child.editor.time_category'),
      card_design: this._t('common.design.field_label'),
      density: this._t('child.editor.density'),
      seasonal: this._t('child.editor.seasonal'),
      due_days_mode: this._t('child.editor.chores_not_due_today'),
      recurrence_done_mode: this._t('child.editor.recurring_when_completed'),
      first_come_claimed_mode: this._t('child.editor.first_come_when_completed'),
      dependency_mode: this._t('child.editor.dependency_mode'),
      elapsed_time_mode: this._t('child.editor.missed_time_chores'),
      set_times_layout: this._t('common.set_times.layout_label'),
      sort_available_first: this._t('child.editor.sort_available_first'),
      include_anytime_chores: this._t('child.editor.include_anytime_chores'),
      show_countdown: this._t('child.editor.show_countdown'),
      show_minutes_left: this._t('child.editor.show_minutes_left'),
      show_help_button: this._t('child.editor.show_help_button'),
      show_mood: this._t('child.editor.show_mood'),
      show_weekly_goal: this._t('child.editor.show_weekly_goal'),
      show_personal_bests: this._t('child.editor.show_personal_bests'),
      show_boost_alert: this._t('child.editor.show_boost_alert'),
      show_appeals: this._t('child.editor.show_appeals'),
      show_screen_time: this._t('child.editor.show_screen_time'),
      show_description: this._t('child.editor.show_description'),
      pre_reader: this._t('child.editor.pre_reader'),
      pre_reader_labels: this._t('child.editor.pre_reader_labels'),
      pre_reader_points: this._t('child.editor.pre_reader_points'),
      show_tour: this._t('child.editor.show_tour'),
      show_parent_actions: this._t('common.editor.show_parent_actions'),
      debug: this._t('child.editor.show_debug'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('child.editor.child_helper'),
      time_category: this._t('child.editor.time_category_helper'),
      density: this._t('child.editor.density_helper'),
      seasonal: this._t('child.editor.seasonal_helper'),
      show_tour: this._t('child.editor.show_tour_helper'),
      pre_reader_labels: this._t('child.editor.pre_reader_labels_helper'),
      due_days_mode: this._t('child.editor.due_days_helper'),
      recurrence_done_mode: this._t('child.editor.recurrence_helper'),
      first_come_claimed_mode: this._t('child.editor.first_come_helper'),
      dependency_mode: this._t('child.editor.dependency_helper'),
      elapsed_time_mode: this._t('child.editor.elapsed_helper'),
      set_times_layout: this._t('common.set_times.layout_helper'),
      sort_available_first: this._t('child.editor.sort_available_first_helper'),
      include_anytime_chores: this._t('child.editor.include_anytime_chores_helper'),
      show_parent_actions: this._t('common.editor.show_parent_actions_helper'),
    };
    return helpers[entry.name] ?? '';
  };

  render() {
    if (!this.hass || !this.config) return html``;

    const data = {
      entity: this.config.entity || '',
      child_id: this.config.child_id || '',
      time_category: this.config.time_category || 'morning',
      card_design: this.config.card_design || 'global',
      density: this.config.density || 'normal',
      seasonal: this.config.seasonal !== false,
      due_days_mode: this.config.due_days_mode || 'hide',
      recurrence_done_mode: this.config.recurrence_done_mode || 'dim',
      first_come_claimed_mode: this.config.first_come_claimed_mode || 'hide',
      dependency_mode: this.config.dependency_mode || 'hide',
      elapsed_time_mode: this.config.elapsed_time_mode || 'dim',
      set_times_layout: this.config.set_times_layout || 'family',
      sort_available_first: this.config.sort_available_first !== false,
      include_anytime_chores: this.config.include_anytime_chores !== false,
      show_countdown: this.config.show_countdown !== false,
      show_minutes_left: this.config.show_minutes_left !== false,
      show_help_button: this.config.show_help_button !== false,
      show_mood: this.config.show_mood !== false,
      show_weekly_goal: this.config.show_weekly_goal !== false,
      show_personal_bests: this.config.show_personal_bests !== false,
      show_boost_alert: this.config.show_boost_alert !== false,
      show_appeals: this.config.show_appeals !== false,
      show_screen_time: this.config.show_screen_time !== false,
      show_description: this.config.show_description === true,
      pre_reader: this.config.pre_reader === true,
      pre_reader_labels: this.config.pre_reader_labels === true,
      pre_reader_points: this.config.pre_reader_points === true,
      show_tour: this.config.show_tour !== false,
      show_parent_actions: this.config.show_parent_actions !== false,
      debug: this.config.debug === true,
    };

    const sections = this._sections();
    const summary = this._summaries(data, sections);
    const form = (schema, disabled = false) => html`
      <ha-form
        .hass=${this.hass}
        .data=${data}
        .schema=${schema}
        .disabled=${disabled}
        .computeLabel=${this._computeLabel}
        .computeHelper=${this._computeHelper}
        @value-changed=${this._formChanged}
      ></ha-form>`;
    const section = (title, secondary, icon, body, expanded = false) => html`
      <ha-expansion-panel outlined .header=${title} .secondary=${secondary} .expanded=${expanded}>
        <ha-icon slot="leading-icon" .icon=${icon}></ha-icon>
        <div class="section-body">${body}</div>
      </ha-expansion-panel>`;

    return html`
      ${form(sections.top)}
      ${section(this._t('common.editor.section_appearance'), summary.appearance, 'mdi:palette-outline', html`
        ${form(sections.appearance)}
        ${this._renderColourPicker('header_color', '#9b59b6')}
        ${form(sections.appearanceMore)}`, true)}
      ${section(this._t('common.editor.section_which_chores'), summary.which, 'mdi:filter-variant', form(sections.which))}
      ${section(this._t('common.editor.section_kid_features'), summary.kid, 'mdi:human-child', html`
        ${form(sections.kid)}
        <div class="nested">${form(sections.kidNested, !data.pre_reader)}</div>`)}
      ${section(this._t('common.editor.section_advanced'), summary.advanced, 'mdi:cog-outline', form(sections.advanced))}
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
      // Reset drops the key, so the child's own colour (#1078) applies again.
      onReset: () => this._updateConfig(key, undefined),
    });
  }

  _formChanged(e) {
    const newValues = e.detail.value || {};
    const newConfig = { ...this.config };
    for (const [key, value] of Object.entries(newValues)) {
      const defaults = {
        show_countdown: true, show_minutes_left: true, show_help_button: true, show_mood: true, show_weekly_goal: true,
        show_personal_bests: true, show_boost_alert: true, show_appeals: true, show_screen_time: true,
        show_tour: true, debug: false, density: 'normal', seasonal: true,
        time_category: 'morning', due_days_mode: 'hide',
        recurrence_done_mode: 'dim', elapsed_time_mode: 'dim',
        first_come_claimed_mode: 'hide', set_times_layout: 'family', sort_available_first: true,
      };
      // Options the child's stage (#1262) fills in stay out of the YAML
      // until the parent actually sets them, so the stage keeps working.
      const stageKey = ['pre_reader', 'show_description', 'show_roulette', 'show_confetti'].includes(key);
      if (stageKey && !(key in this.config) && value === false) continue;
      if (value === '' || value === null || value === undefined) {
        delete newConfig[key];
      } else if (key === 'card_design' && value === 'global') {
        delete newConfig[key];
      } else if (defaults[key] !== undefined && value === defaults[key]) {
        delete newConfig[key];
      } else {
        newConfig[key] = value;
      }
    }
    this._dispatchConfig(newConfig);
  }

  _updateConfig(key, value) {
    const newConfig = { ...this.config, [key]: value };
    if (value === undefined || value === '') delete newConfig[key];
    this._dispatchConfig(newConfig);
  }

  _dispatchConfig(newConfig) {
    this.dispatchEvent(new CustomEvent('config-changed', {
      detail: { config: newConfig }, bubbles: true, composed: true,
    }));
  }
}

if (!customElements.get("taskmate-child-card-editor")) {
  customElements.define("taskmate-child-card-editor", TaskMateChildCardEditor);
}
