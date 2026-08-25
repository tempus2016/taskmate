
/**
 * TaskMate Child Card
 * A FUN, kid-friendly Lovelace card for completing chores!
 * Designed for children ages 5-10 with big buttons, bright colors, and celebrations!
 *
 * Version: 0.0.1 - Checkbox-style completion
 * Last Updated: 2026-01-01
 *
 * Features:
 * - Fun synthesized completion sounds (coin, levelup, fanfare, chime, powerup, undo)
 * - No external sound files needed - all sounds generated via Web Audio API
 * - Per-chore sound configuration
 * - Card-level default_sound and undo_sound config options
 * - Chore numbers with colorful, kid-friendly badges
 * - Clickable chore rows with checkbox visual indicator
 */

const LitElement = customElements.get("hui-masonry-view")
  ? Object.getPrototypeOf(customElements.get("hui-masonry-view"))
  : Object.getPrototypeOf(customElements.get("hui-view"));

const html = LitElement.prototype.html;
const css = LitElement.prototype.css;

const _safeColor = (c, d) => (typeof c === "string" && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : d);

class TaskMateChildCard extends LitElement {
  static get properties() {
    return {
      hass: { type: Object },
      config: { type: Object },
      _loading: { type: Object },
      _celebrating: { type: String },
      _confetti: { type: Array },
      _optimisticCompletions: { type: Object },
      _earnedBadges: { type: Array },
      _justEarnedBadge: { type: String },
      _avatarPickerOpen: { type: Boolean },
      _photoCapture: { type: Object },
    };
  }

  shouldUpdate(changedProps) {
    if (changedProps.has("hass")) {
      const flashed = this._trackEarnedBadges();
      const relevant = window.__taskmate_hasChanged
        ? window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity)
        : true;
      return flashed || relevant;
    }
    return true;
  }

  constructor() {
    super();
    this._loading = {};
    this._celebrating = null;
    this._confetti = [];
    // Optimistic completions: track chores that were just completed
    // These are used to immediately hide the DONE button before the server confirms
    this._optimisticCompletions = {};
    // Audio context for generating sounds (lazy initialized)
    this._audioContext = null;
    // Timer intervals for live counters (timed tasks)
    this._timerInterval = null;
    this._timerTick = 0;
    // Badge strip state
    this._earnedBadges = [];
    this._justEarnedBadge = null;
    this._seenBadgeIds = null;
    this._justEarnedTimeout = null;
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopTimerTick();
    if (this._justEarnedTimeout) {
      clearTimeout(this._justEarnedTimeout);
      this._justEarnedTimeout = null;
    }
    if (this._audioContext) {
      this._audioContext.close().catch(() => {});
      this._audioContext = null;
    }
  }

  updated(changedProperties) {
    super.updated(changedProperties);
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const sessions = attrs.active_timed_sessions || [];
    const hasRunning = sessions.some(s => s.state === 'running' && s.child_id === this.config?.child_id);
    // A reactive chore's countdown (#674) has to keep ticking too, otherwise it
    // sits on a stale minute until the next coordinator push.
    const now = Date.now();
    const hasDeadline = (attrs.chores || []).some(c => {
      if (!c.deadline_at) return false;
      const at = new Date(c.deadline_at).getTime();
      return !Number.isNaN(at) && at > now;
    });
    if ((hasRunning || hasDeadline) && !this._timerInterval) {
      this._timerInterval = setInterval(() => { this._timerTick++; this.requestUpdate(); }, 1000);
    } else if (!hasRunning && !hasDeadline && this._timerInterval) {
      this._stopTimerTick();
    }
  }

  _stopTimerTick() {
    if (this._timerInterval) {
      clearInterval(this._timerInterval);
      this._timerInterval = null;
    }
  }

  _t(key, params) {
    const fn = window.__taskmate_localize;
    return fn ? fn(this.hass, key, params) : key;
  }

  /* Newly-earned badges are detected by diffing this child's badges sensor
     `earned` list across hass updates (#752). The card used to subscribe to the
     custom `taskmate_badge_earned` event, but Home Assistant refuses a
     custom-event subscription from a non-admin user — logging an error every
     time — so the strip never lit up for a child. `state_changed` is
     allowlisted for everyone, so the diff works for every user. */
  _trackEarnedBadges() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const child = (attrs.children || []).find(c => c.id === this.config?.child_id)
      || (!this.config?.child_id && (attrs.children || [])[0]);
    const earned = this._resolveBadgesEntity(child)?.attributes?.earned;
    if (!Array.isArray(earned)) return false;
    const ids = new Set(earned.map(b => window.__taskmate_badge_id(b)).filter(Boolean));

    // First observation is the baseline — never flash a badge earned earlier.
    if (this._seenBadgeIds === null) {
      this._seenBadgeIds = ids;
      return false;
    }
    const fresh = [...ids].filter(id => !this._seenBadgeIds.has(id));
    this._seenBadgeIds = ids;
    if (!fresh.length) return false;

    this._justEarnedBadge = fresh[0];
    clearTimeout(this._justEarnedTimeout);
    this._justEarnedTimeout = setTimeout(() => {
      this._justEarnedBadge = null;
      this.requestUpdate();
    }, 1800);
    return true;
  }

  _tierColor(tier) {
    return {
      bronze: '#cd7f32',
      silver: '#c0c0c0',
      gold: '#f1c40f',
      platinum: '#67e8f9',
    }[tier] || '#888';
  }

  _badgeKeydown(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this._openBadgesView();
    }
  }

  _openBadgesView() {
    const slug = this.config?.child_id
      ? String(this.config.child_id).toLowerCase().replace(/\s+/g, '_')
      : '';
    window.history.pushState(null, '', `/taskmate-admin?section=badges${slug ? '&child=' + slug : ''}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
  }

  _toggleAvatarPicker() {
    this._avatarPickerOpen = !this._avatarPickerOpen;
    this.requestUpdate();
  }

  _renderAvatarPicker(child, options) {
    return html`
      <div class="avatar-picker">
        ${options.map(o => html`
          <button class="avatar-opt ${o.unlocked ? '' : 'locked'} ${o.icon === child.avatar ? 'current' : ''}"
                  ?disabled=${!o.unlocked}
                  title="${o.unlocked ? (o.label || '') : (this._t('child.avatar_locked') + (o.requirement ? ' — ' + o.requirement : ''))}"
                  @click=${o.unlocked ? () => this._chooseAvatar(child, o.icon) : null}>
            <ha-icon icon="${o.unlocked ? o.icon : 'mdi:lock'}"></ha-icon>
            ${o.label ? html`<span>${o.label}</span>` : ''}
          </button>
        `)}
      </div>
    `;
  }

  async _chooseAvatar(child, icon) {
    this._avatarPickerOpen = false;
    this.requestUpdate();
    if (icon === child.avatar) return;
    try {
      await this.hass.callService('taskmate', 'choose_avatar', {
        child_id: this.config.child_id,
        icon,
      });
    } catch (err) {
      if (this.hass.callService) {
        this.hass.callService('persistent_notification', 'create', {
          title: 'TaskMate',
          message: this._t('child.avatar_change_failed'),
        });
      }
    }
  }

  /**
   * Get or create the AudioContext (lazy initialization)
   * Must be called after user interaction due to browser autoplay policies
   */
  _getAudioContext() {
    if (!this._audioContext) {
      this._audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    // Resume if suspended (required after user interaction)
    if (this._audioContext.state === 'suspended') {
      this._audioContext.resume();
    }
    return this._audioContext;
  }

  /**
   * Play a completion sound using Web Audio API
   * Generates fun synthesized sounds - no external files needed!
   * @param {string} soundName - Name of the sound to play (coin, levelup, fanfare, chime, powerup)
   */
  _playSound(soundName) {
    // Don't play if sound is "none" or not specified
    if (!soundName || soundName === 'none') {
      return;
    }

    try {
      const ctx = this._getAudioContext();
      const now = ctx.currentTime;

      switch (soundName) {
        case 'coin':
          this._playCoinSound(ctx, now);
          break;
        case 'levelup':
          this._playLevelUpSound(ctx, now);
          break;
        case 'fanfare':
          this._playFanfareSound(ctx, now);
          break;
        case 'chime':
          this._playChimeSound(ctx, now);
          break;
        case 'powerup':
          this._playPowerUpSound(ctx, now);
          break;
        case 'undo':
          this._playUndoSound(ctx, now);
          break;
        case 'fart1':
          this._playAudioFile('fart1.mp3');
          break;
        case 'fart2':
          this._playAudioFile('fart2.mp3');
          break;
        case 'fart3':
          this._playAudioFile('fart3.mp3');
          break;
        case 'fart4':
          this._playAudioFile('fart4.mp3');
          break;
        case 'fart5':
          this._playAudioFile('fart5.mp3');
          break;
        case 'fart6':
          this._playAudioFile('fart6.mp3');
          break;
        case 'fart7':
          this._playAudioFile('fart7.mp3');
          break;
        case 'fart8':
          this._playAudioFile('fart8.mp3');
          break;
        case 'fart9':
          this._playAudioFile('fart9.mp3');
          break;
        case 'fart10':
          this._playAudioFile('fart10.mp3');
          break;
        case 'fart_random': {
          // Pick a random fart sound (1-10)
          const randomFartNum = Math.floor(Math.random() * 10) + 1;
          this._playAudioFile(`fart${randomFartNum}.mp3`);
          break;
        }
        default:
          this._playCoinSound(ctx, now);
      }
    } catch (e) {
    }
  }

  /**
   * Coin collect sound - classic video game coin pickup
   * Two quick ascending tones
   */
  _playCoinSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.3;

    // First tone (E6)
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.connect(gain1);
    gain1.connect(masterGain);
    osc1.frequency.value = 1318.5; // E6
    osc1.type = 'square';
    gain1.gain.setValueAtTime(0.5, startTime);
    gain1.gain.exponentialRampToValueAtTime(0.01, startTime + 0.1);
    osc1.start(startTime);
    osc1.stop(startTime + 0.1);

    // Second tone (B6) - higher
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.connect(gain2);
    gain2.connect(masterGain);
    osc2.frequency.value = 1975.5; // B6
    osc2.type = 'square';
    gain2.gain.setValueAtTime(0.5, startTime + 0.08);
    gain2.gain.exponentialRampToValueAtTime(0.01, startTime + 0.25);
    osc2.start(startTime + 0.08);
    osc2.stop(startTime + 0.25);
  }

  /**
   * Level up sound - triumphant ascending arpeggio
   */
  _playLevelUpSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.25;

    // C major arpeggio going up: C5, E5, G5, C6
    const notes = [523.25, 659.25, 783.99, 1046.5];
    const duration = 0.12;

    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(masterGain);
      osc.frequency.value = freq;
      osc.type = 'square';

      const noteStart = startTime + i * duration;
      gain.gain.setValueAtTime(0.6, noteStart);
      gain.gain.exponentialRampToValueAtTime(0.01, noteStart + duration + 0.1);
      osc.start(noteStart);
      osc.stop(noteStart + duration + 0.15);
    });

    // Final sustained chord
    const chordNotes = [523.25, 659.25, 783.99]; // C major chord
    const chordStart = startTime + notes.length * duration;
    chordNotes.forEach((freq) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(masterGain);
      osc.frequency.value = freq;
      osc.type = 'triangle';
      gain.gain.setValueAtTime(0.3, chordStart);
      gain.gain.exponentialRampToValueAtTime(0.01, chordStart + 0.5);
      osc.start(chordStart);
      osc.stop(chordStart + 0.55);
    });
  }

  /**
   * Fanfare sound - celebratory trumpet-like fanfare
   */
  _playFanfareSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.2;

    // Fanfare pattern: G4, G4, G4, E4, G4, C5 (classic celebration pattern)
    const pattern = [
      { freq: 392.00, duration: 0.1, delay: 0 },      // G4
      { freq: 392.00, duration: 0.1, delay: 0.12 },   // G4
      { freq: 392.00, duration: 0.15, delay: 0.24 },  // G4
      { freq: 329.63, duration: 0.15, delay: 0.42 },  // E4
      { freq: 392.00, duration: 0.15, delay: 0.6 },   // G4
      { freq: 523.25, duration: 0.4, delay: 0.78 },   // C5 (long final note)
    ];

    pattern.forEach(({ freq, duration, delay }) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(masterGain);

      osc.frequency.value = freq;
      osc.type = 'sawtooth';

      const noteStart = startTime + delay;
      gain.gain.setValueAtTime(0.5, noteStart);
      gain.gain.setValueAtTime(0.5, noteStart + duration * 0.8);
      gain.gain.exponentialRampToValueAtTime(0.01, noteStart + duration);

      osc.start(noteStart);
      osc.stop(noteStart + duration + 0.05);
    });
  }

  /**
   * Chime sound - simple pleasant bell chime
   */
  _playChimeSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.3;

    // Bell-like sound using multiple harmonics
    const fundamental = 880; // A5
    const harmonics = [1, 2, 3, 4.2]; // Slight inharmonicity for bell-like quality

    harmonics.forEach((harmonic, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(masterGain);

      osc.frequency.value = fundamental * harmonic;
      osc.type = 'sine';

      // Higher harmonics decay faster
      const amplitude = 0.5 / (i + 1);
      const decayTime = 0.8 / (i + 1);

      gain.gain.setValueAtTime(amplitude, startTime);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + decayTime);

      osc.start(startTime);
      osc.stop(startTime + decayTime + 0.1);
    });
  }

  /**
   * Power up sound - ascending sweep with sparkle
   */
  _playPowerUpSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.25;

    // Ascending sweep
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.connect(gain1);
    gain1.connect(masterGain);
    osc1.type = 'sawtooth';
    osc1.frequency.setValueAtTime(200, startTime);
    osc1.frequency.exponentialRampToValueAtTime(1200, startTime + 0.3);
    gain1.gain.setValueAtTime(0.4, startTime);
    gain1.gain.exponentialRampToValueAtTime(0.01, startTime + 0.35);
    osc1.start(startTime);
    osc1.stop(startTime + 0.4);

    // Sparkle notes at the end
    const sparkleNotes = [1318.5, 1567.98, 1975.5]; // E6, G6, B6
    sparkleNotes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(masterGain);
      osc.frequency.value = freq;
      osc.type = 'sine';

      const noteStart = startTime + 0.25 + i * 0.05;
      gain.gain.setValueAtTime(0.3, noteStart);
      gain.gain.exponentialRampToValueAtTime(0.01, noteStart + 0.2);
      osc.start(noteStart);
      osc.stop(noteStart + 0.25);
    });
  }

  /**
   * Undo sound - sad descending "womp womp" style
   * Two descending tones that sound disappointed/sad
   */
  _playUndoSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.25;

    // First "womp" - descending tone
    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.connect(gain1);
    gain1.connect(masterGain);
    osc1.type = 'triangle';
    osc1.frequency.setValueAtTime(311.13, startTime);  // Eb4
    osc1.frequency.exponentialRampToValueAtTime(233.08, startTime + 0.25);  // Bb3
    gain1.gain.setValueAtTime(0.6, startTime);
    gain1.gain.exponentialRampToValueAtTime(0.3, startTime + 0.2);
    gain1.gain.exponentialRampToValueAtTime(0.01, startTime + 0.3);
    osc1.start(startTime);
    osc1.stop(startTime + 0.35);

    // Second "womp" - even lower descending tone (the sad part)
    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.connect(gain2);
    gain2.connect(masterGain);
    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(233.08, startTime + 0.3);  // Bb3
    osc2.frequency.exponentialRampToValueAtTime(155.56, startTime + 0.7);  // Eb3
    gain2.gain.setValueAtTime(0.5, startTime + 0.3);
    gain2.gain.exponentialRampToValueAtTime(0.25, startTime + 0.55);
    gain2.gain.exponentialRampToValueAtTime(0.01, startTime + 0.75);
    osc2.start(startTime + 0.3);
    osc2.stop(startTime + 0.8);

    // Optional: add a subtle low vibrato for extra sadness
    const osc3 = ctx.createOscillator();
    const gain3 = ctx.createGain();
    osc3.connect(gain3);
    gain3.connect(masterGain);
    osc3.type = 'sine';
    osc3.frequency.setValueAtTime(116.54, startTime + 0.5);  // Bb2 (sub bass)
    gain3.gain.setValueAtTime(0.15, startTime + 0.5);
    gain3.gain.exponentialRampToValueAtTime(0.01, startTime + 0.8);
    osc3.start(startTime + 0.5);
    osc3.stop(startTime + 0.85);
  }

  /**
   * Play an audio file from the www folder
   * Used for fart sounds (real audio files, not synthesized)
   * CC0 public domain from BigSoundBank.com
   * @param {string} filename - The audio file name (e.g., 'fart1.mp3')
   */
  _playAudioFile(filename) {
    try {
      // Build the URL to the audio file in the www folder
      const audio = new Audio(`/local/taskmate/${filename}`);
      audio.volume = 1.0;
      audio.play().catch(e => {
        console.warn(`[TaskMate] Failed to play ${filename}:`, e);
      });
    } catch (e) {
      console.warn(`[TaskMate] Error preparing audio ${filename}:`, e);
    }
  }

  static get styles() {
    const base = css`
      :host {
        display: block;
        --fun-pink: #ff6b9d;
        --fun-purple: #9b59b6;
        --fun-blue: #3498db;
        --fun-green: #2ecc71;
        --fun-yellow: #f1c40f;
        --fun-orange: #e67e22;
        --fun-red: #e74c3c;
        --fun-cyan: #1abc9c;
      }

      ha-card { overflow: hidden; }

      /* ── Header — matches overview/weekly/streak card style ── */
      .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 18px;
        background: var(--taskmate-header-bg, #9b59b6);
        color: white;
        gap: 12px;
        min-width: 0;
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 0;
        flex: 1;
      }

      .avatar-container {
        width: 48px;
        height: 48px;
        min-width: 48px;
        border-radius: 50%;
        background: rgba(255,255,255,0.15);
        border: 2px solid rgba(255,255,255,0.3);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .avatar-container ha-icon {
        --mdc-icon-size: 30px;
        color: white;
      }

      .avatar-clickable { cursor: pointer; position: relative; }
      .avatar-edit-dot {
        position: absolute; bottom: -2px; right: -2px;
        width: 18px; height: 18px; border-radius: 50%;
        background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center;
      }

      /* Designed-header avatar wrapper: mirror of the classic avatar-container
         so the picker works under every design, not just classic. The picker
         itself (.avatar-picker) is absolute, so the header is the positioned
         anchor. Base styles here win over the shared kit's .tmd-hd because the
         card includes them after the kit in static styles(). */
      .tmd-hd { position: relative; }
      .tmd-av-wrap { position: relative; display: inline-flex; align-items: center; flex: none; }
      .tmd-av-wrap.avatar-clickable { cursor: pointer; }
      .tmd-av-edit {
        position: absolute; bottom: -2px; right: -2px;
        width: 15px; height: 15px; border-radius: 50%;
        background: var(--tmd-accent, #7c3aed); color: #fff;
        display: grid; place-items: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
      }
      .tmd-av-edit ha-icon { --mdc-icon-size: 10px; color: #fff; }
      .avatar-edit-dot ha-icon { --mdc-icon-size: 12px; color: white; }
      .avatar-picker {
        position: absolute; z-index: 20; margin-top: 56px;
        background: var(--card-background-color, #fff);
        border: 1px solid var(--divider-color, rgba(0,0,0,0.12));
        border-radius: 12px; padding: 10px; box-shadow: 0 8px 24px rgba(0,0,0,0.18);
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; max-width: 280px;
      }
      .avatar-opt {
        display: flex; flex-direction: column; align-items: center; gap: 2px;
        border: 1px solid var(--divider-color, rgba(0,0,0,0.12)); border-radius: 10px;
        background: var(--secondary-background-color, #f5f5f5);
        padding: 8px 4px; cursor: pointer; color: var(--primary-text-color, #222);
        font-size: 10px; line-height: 1.1;
      }
      .avatar-opt ha-icon { --mdc-icon-size: 24px; color: var(--primary-text-color, #222); }
      .avatar-opt.current { border-color: var(--primary-color, #9b59b6); box-shadow: 0 0 0 2px var(--primary-color, #9b59b6) inset; }
      .avatar-opt.locked { opacity: 0.45; cursor: not-allowed; }

      .child-name-container {
        min-width: 0;
        flex: 1;
        overflow: hidden;
      }

      .child-name {
        font-size: 1.15rem;
        font-weight: 700;
        color: white;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .child-level {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-top: 4px;
      }
      .level-badge {
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: .03em;
        color: white;
        background: rgba(255, 255, 255, 0.25);
        padding: 1px 8px;
        border-radius: 999px;
        white-space: nowrap;
      }
      .level-xp-track {
        flex: 1;
        max-width: 90px;
        height: 5px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.25);
        overflow: hidden;
      }
      .level-xp-fill {
        height: 100%;
        border-radius: 999px;
        background: white;
        transition: width 0.4s ease;
      }

      /* Points pill — right side of header, compact like overview card */
      .points-display {
        display: flex;
        align-items: center;
        gap: 6px;
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.25);
        padding: 6px 12px;
        border-radius: 20px;
        flex-shrink: 0;
        white-space: nowrap;
      }

      .stars-row {
        display: flex;
        align-items: center;
        gap: 6px;
      }

      .stars-section {
        display: flex;
        align-items: center;
        gap: 4px;
        min-width: 0;
        flex-shrink: 1;
      }

      .stars-value {
        font-size: 1.1rem;
        font-weight: 800;
        line-height: 1;
        display: flex;
        align-items: center;
        gap: 3px;
        white-space: nowrap;
        color: white;
      }

      .stars-value.my-stars { color: white; }

      .stars-value.waiting-stars {
        color: rgba(255,255,255,0.75);
        font-size: 0.9rem;
      }

      .stars-value ha-icon { --mdc-icon-size: 16px; flex-shrink: 0; }

      .stars-value.my-stars ha-icon { color: var(--fun-yellow); }
      .stars-value.waiting-stars ha-icon { color: var(--fun-orange); }

      .stars-label {
        font-size: 0.6rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        white-space: nowrap;
        color: rgba(255,255,255,0.7);
        display: none;
      }

      .stars-divider {
        width: 1px;
        height: 18px;
        background: rgba(255,255,255,0.35);
        margin: 0 4px;
        flex-shrink: 0;
      }

      /* Chores container */
      .chores-container {
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        background: var(--card-background-color, #fff);
        min-height: 100px;
      }

      .section-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: var(--fun-purple);
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
        padding: 4px 0;
      }

      .section-title ha-icon { --mdc-icon-size: 28px; }

      .section-title-text { flex: 1; }

      /* Individual chore card - optimized for tablet touch, ENTIRE ROW IS CLICKABLE */
      .chore-card {
        background: var(--card-background-color, #fff);
        border-radius: 20px;
        padding: 16px 18px;
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
        flex-wrap: nowrap;
        gap: 12px;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
        border: 3px solid transparent;
        transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
        position: relative;
        overflow: hidden;
        min-height: 68px;
        -webkit-user-select: none;
        user-select: none;
        -webkit-tap-highlight-color: transparent;
        cursor: pointer;
        box-sizing: border-box;
      }

      .chore-card:nth-child(odd) {
        border-color: var(--fun-blue);
        background: var(--card-background-color, #fff);
        background: color-mix(in srgb, var(--fun-blue) 10%, var(--card-background-color, #fff));
      }

      .chore-card:nth-child(even) {
        border-color: var(--fun-pink);
        background: var(--card-background-color, #fff);
        background: color-mix(in srgb, var(--fun-pink) 10%, var(--card-background-color, #fff));
      }

      .chore-card:nth-child(3n) {
        border-color: var(--fun-green);
        background: var(--card-background-color, #fff);
        background: color-mix(in srgb, var(--fun-green) 10%, var(--card-background-color, #fff));
      }

      .chore-card:nth-child(4n) {
        border-color: var(--fun-orange);
        background: var(--card-background-color, #fff);
        background: color-mix(in srgb, var(--fun-orange) 10%, var(--card-background-color, #fff));
      }

      /* Touch/hover feedback - works for both touch and mouse */
      .chore-card:active {
        transform: scale(0.98);
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
      }
      .chore-card:focus {
        outline: none;
      }
      .chore-card:focus-visible {
        outline: 2px solid var(--primary-color, #2196f3);
        outline-offset: 2px;
      }

      @media (hover: hover) {
        .chore-card:hover {
          transform: scale(1.02);
          box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
        }
      }

      .chore-card.loading {
        opacity: 0.6;
        pointer-events: none;
      }

      .chore-card.celebrating {
        animation: celebrate-wiggle 0.5s ease-in-out;
      }

      @keyframes celebrate-wiggle {
        0%, 100% { transform: rotate(0deg); }
        25% { transform: rotate(-3deg); }
        75% { transform: rotate(3deg); }
      }

      .chore-info {
        display: flex;
        align-items: center;
        gap: 12px;
        flex: 1;
        min-width: 0;
        overflow: hidden;
      }

      /* Chore number wrapper — holds the number-or-picture badge */
      .chore-number-wrapper {
        display: flex;
        align-items: center;
        gap: 12px;
        position: relative;
      }

      /* Fun chore number badge */
      .chore-number-badge {
        width: 38px;
        height: 38px;
        min-width: 38px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.3rem;
        font-weight: 800;
        color: white;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.2);
        box-shadow: 0 3px 8px rgba(0, 0, 0, 0.2), inset 0 2px 4px rgba(255, 255, 255, 0.3);
        transform: rotate(-5deg);
        transition: transform 0.2s ease;
        font-family: 'Comic Sans MS', 'Chalkboard SE', 'Marker Felt', sans-serif;
        flex-shrink: 0;
      }

      /* A chore picture sits where the digit would, so it has to carry the
         same white-on-colour weight the numeral gets from its text-shadow. */
      /* Uploaded chore pictures (#750). min-width/min-height:0 is load-bearing:
         grid and flex items default to min-*:auto, whose content-based minimum
         is the image's intrinsic aspect ratio, so without it a PORTRAIT photo
         overflows a square slot (measured 64x90 in a 64x64 pre-reader tile)
         because that minimum beats height:100%. Landscape photos hide it. */
      .chore-badge-img {
        width: 100%; height: 100%; min-width: 0; min-height: 0;
        object-fit: cover; border-radius: inherit; display: block;
      }
      .tmd-glyph-img {
        width: 1.4em; height: 1.4em; min-width: 0; min-height: 0;
        object-fit: cover; border-radius: 6px; display: block;
      }
      .pre-tile-icon img {
        width: 100%; height: 100%; min-width: 0; min-height: 0;
        object-fit: cover; border-radius: 12px; display: block;
      }

      .chore-number-badge ha-icon {
        --mdc-icon-size: 22px;
        color: #fff;
        filter: drop-shadow(1px 1px 2px rgba(0, 0, 0, 0.25));
      }

      .chore-card:hover .chore-number-badge {
        transform: rotate(5deg) scale(1.1);
      }

      /* Cycle through fun colors for number badges */
      .chore-number-badge.color-0 { background: linear-gradient(135deg, #ff6b9d 0%, #ff4081 100%); } /* Pink */
      .chore-number-badge.color-1 { background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); } /* Blue */
      .chore-number-badge.color-2 { background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%); } /* Green */
      .chore-number-badge.color-3 { background: linear-gradient(135deg, #e67e22 0%, #d35400 100%); } /* Orange */
      .chore-number-badge.color-4 { background: linear-gradient(135deg, #9b59b6 0%, #8e44ad 100%); } /* Purple */
      .chore-number-badge.color-5 { background: linear-gradient(135deg, #1abc9c 0%, #16a085 100%); } /* Teal */
      .chore-number-badge.color-6 { background: linear-gradient(135deg, #f1c40f 0%, #f39c12 100%); } /* Yellow */
      .chore-number-badge.color-7 { background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%); } /* Red */

      /* Completed state for number badge */
      .chore-card.completed .chore-number-badge {
        filter: saturate(0.5);
        opacity: 0.7;
      }

      /* Checkbox for chore completion */
      .chore-checkbox {
        width: 40px;
        height: 40px;
        min-width: 40px;
        border-radius: 10px;
        border: 3px solid var(--divider-color, #bdc3c7);
        background: var(--card-background-color, #fff);
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
        flex-shrink: 0;
        align-self: center;
      }

      .chore-checkbox ha-icon {
        --mdc-icon-size: 24px;
        color: transparent;
        transition: all 0.2s ease;
      }

      /* Unchecked state - hover effect */
      .chore-card:not(.completed):hover .chore-checkbox {
        border-color: var(--fun-green);
        background: rgba(46, 204, 113, 0.1);
      }

      /* Checked state */
      .chore-card.completed .chore-checkbox {
        border-color: var(--fun-green);
        background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%);
        box-shadow: 0 3px 10px rgba(46, 204, 113, 0.4);
      }

      .chore-card.completed .chore-checkbox ha-icon {
        color: white;
      }

      .chore-details {
        display: flex;
        flex-direction: column;
        gap: 6px;
        flex: 1;
        min-width: 0; /* Allow text truncation */
      }

      .chore-name {
        font-size: 1.2rem;
        font-weight: 700;
        color: var(--primary-text-color);
        line-height: 1.2;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .chore-description {
        font-size: 0.82rem;
        color: var(--secondary-text-color);
        line-height: 1.3;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        margin-top: 1px;
      }

      .difficulty-badge {
        display: inline-block;
        align-self: flex-start;
        font-size: 0.68rem;
        font-weight: 600;
        text-transform: capitalize;
        padding: 1px 8px;
        border-radius: 9px;
        margin-top: 2px;
      }
      .difficulty-easy { background: rgba(76, 175, 80, 0.16); color: #2e7d32; }
      .difficulty-hard { background: rgba(244, 67, 54, 0.16); color: #c62828; }
      .difficulty-medium { background: rgba(255, 152, 0, 0.16); color: #ef6c00; }

      .swap-section { margin-top: 14px; }
      .swap-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 8px 12px;
        border: 1px dashed var(--divider-color, #e0e0e0);
        border-radius: 12px;
        margin-bottom: 6px;
      }
      .swap-info { min-width: 0; }
      .swap-info .chore-name { font-size: 1rem; }
      .swap-info .chore-points { font-size: 0.8rem; opacity: 0.8; }
      .swap-btn {
        flex-shrink: 0;
        border: none;
        border-radius: 10px;
        padding: 8px 14px;
        font-weight: 600;
        cursor: pointer;
        background: var(--primary-color, #9b59b6);
        color: #fff;
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      .swap-btn[disabled] { opacity: 0.6; cursor: default; }
      .swap-btn.requested { background: var(--success-color, #4caf50); }

      .chore-points {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 1rem;
        color: var(--fun-orange);
        font-weight: 600;
        margin-top: 2px;
      }

      .chore-points ha-icon {
        --mdc-icon-size: 18px;
        color: var(--fun-yellow);
      }

      @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }

      /* Chore not due today — dimmed/greyed */
      .chore-card.not-due-today {
        opacity: 0.45;
        filter: grayscale(0.6);
        pointer-events: none;
      }

      /* Recurring chore not yet available — dimmed/greyed */
      .chore-card.recurrence-unavailable {
        opacity: 0.45;
        filter: grayscale(0.6);
        pointer-events: none;
      }

      /* Time period elapsed without completion — dimmed/greyed */
      .chore-card.time-elapsed {
        opacity: 0.45;
        filter: grayscale(0.6);
        pointer-events: none;
      }

      /* First-come chore claimed by a sibling today — dimmed/greyed, same
         treatment as recurrence-unavailable (first_come_done_mode: dim) */
      .chore-card.first-come-unavailable {
        opacity: 0.45;
        filter: grayscale(0.6);
        pointer-events: none;
      }

      .first-come-label {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        background: color-mix(in srgb, var(--primary-text-color, #212121) 8%, transparent);
        border-radius: 8px;
        padding: 1px 6px;
        margin-top: 3px;
      }

      .first-come-label ha-icon { --mdc-icon-size: 12px; }

      /* Locked preview — chore is visible but not yet claimable because its
         time-of-day window has not started. Dim with a padlock badge. */
      .chore-card.chore-locked {
        opacity: 0.55;
        filter: grayscale(0.5);
        cursor: not-allowed;
      }
      .chore-card.chore-locked .chore-lock-icon {
        color: var(--secondary-text-color);
      }

      .recurrence-label {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        background: color-mix(in srgb, var(--primary-text-color, #212121) 8%, transparent);
        border-radius: 8px;
        padding: 1px 6px;
        margin-top: 3px;
      }

      .recurrence-label ha-icon { --mdc-icon-size: 12px; }

      /* Dependency-blocked (#793). Under dim the row stays readable so a child
         can see what unlocks next; show leaves it looking normal, but either
         way the tap is refused in the handler. */
      .chore-card.dependency-blocked {
        opacity: 0.5;
        filter: grayscale(0.5);
      }
      .dependency-label {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--secondary-text-color);
      }
      .dependency-label ha-icon { --mdc-icon-size: 12px; }


      /* Recurring chore not yet available — dimmed/greyed */
      .chore-card.recurrence-unavailable {
        opacity: 0.45;
        filter: grayscale(0.6);
        pointer-events: none;
      }

      .recurrence-label {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        background: color-mix(in srgb, var(--primary-text-color, #212121) 8%, transparent);
        border-radius: 8px;
        padding: 1px 6px;
        margin-top: 3px;
      }

      .recurrence-label ha-icon {
        --mdc-icon-size: 12px;
      }

      /* Chore card in completed state - faded green styling */
      .chore-card.completed {
        opacity: 0.75;
        border-style: dashed;
        border-color: var(--fun-green) !important;
        background: linear-gradient(135deg,
          rgba(46, 204, 113, 0.25) 0%,
          rgba(39, 174, 96, 0.35) 100%) !important;
        filter: saturate(0.7);
      }

      .chore-card.completed .chore-name {
        color: var(--primary-text-color);
        opacity: 0.7;
      }

      .chore-card.completed .chore-points {
        color: var(--primary-text-color);
        opacity: 0.6;
      }

      /* Bonus sub-task cards */
      .chore-card.bonus-subtask {
        margin-left: 24px;
        border-left: 3px solid var(--fun-amber, #f39c12);
        background: linear-gradient(135deg,
          rgba(243, 156, 18, 0.08) 0%,
          rgba(241, 196, 15, 0.12) 100%);
        padding: 8px 12px;
        min-height: unset;
      }

      .chore-card.bonus-subtask .bonus-badge {
        background: linear-gradient(135deg, #f39c12, #f1c40f) !important;
        width: 22px;
        height: 22px;
        min-width: 22px;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .chore-card.bonus-subtask .bonus-badge ha-icon {
        color: #fff;
      }

      .bonus-name {
        font-size: 0.88em;
      }

      .bonus-label {
        font-size: 0.65em;
        font-weight: 700;
        letter-spacing: 0.5px;
        color: #f39c12;
        background: rgba(243, 156, 18, 0.15);
        padding: 1px 5px;
        border-radius: 3px;
        margin-left: 6px;
      }

      .chore-card.bonus-subtask.completed {
        border-color: var(--fun-green) !important;
        border-left: 3px solid var(--fun-green);
      }

      /* Mandatory chores (#532): red border + tint + left spine + badge. */
      .chore-card.mandatory {
        border-color: var(--fun-red) !important;
        background: color-mix(in srgb, var(--fun-red) 9%, var(--card-background-color, #fff)) !important;
      }
      .chore-card.mandatory::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 6px;
        background: var(--fun-red);
      }
      /* Pre-reader mode (#683) — picture-only, huge targets */
      .pre-reader-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
        gap: 14px;
        padding: 4px 0 8px;
      }
      .pre-tile {
        position: relative;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center; gap: 8px;
        min-height: 140px; padding: 16px 10px;
        border: 3px solid var(--divider-color, #e0e0e0);
        border-radius: 26px;
        background: var(--card-background-color, #fff);
        font-family: inherit; cursor: pointer;
        transition: transform 0.12s ease, border-color 0.12s ease;
      }
      .pre-tile:active { transform: scale(0.96); }
      .pre-tile:focus-visible { outline: 4px solid var(--primary-color); outline-offset: 3px; }
      .pre-tile-icon ha-icon { --mdc-icon-size: 64px; color: var(--primary-color); }
      .pre-tile-stars { display: flex; gap: 2px; }
      .pre-tile-stars ha-icon { --mdc-icon-size: 18px; color: #f1c40f; }
      .pre-tile-points {
        display: flex; align-items: center; gap: 4px;
        font-size: 1.15rem; font-weight: 700; color: var(--primary-text-color);
      }
      .pre-tile-points ha-icon { --mdc-icon-size: 20px; color: #f1c40f; }
      .pre-tile-label {
        font-size: 0.85rem; font-weight: 700; text-align: center;
        color: var(--secondary-text-color); line-height: 1.2;
      }
      .pre-tile.done {
        border-color: var(--success-color, #2ecc71);
        background: rgba(46, 204, 113, 0.10);
      }
      .pre-tile.done .pre-tile-icon ha-icon { opacity: 0.35; }
      .pre-tile.done .pre-tile-stars { opacity: 0.35; }
      .pre-tile.done .pre-tile-points { opacity: 0.35; }
      .pre-tile-tick {
        position: absolute; inset: 0;
        display: grid; place-items: center;
        pointer-events: none;
      }
      .pre-tile-tick ha-icon {
        --mdc-icon-size: 72px;
        color: var(--success-color, #2ecc71);
      }
      .pre-tile.locked { opacity: 0.4; cursor: default; }
      .pre-tile.loading { opacity: 0.6; }

      /* Chore roulette (#677) */
      .roulette {
        display: flex; flex-direction: column; gap: 8px;
        margin: 4px 0 12px;
      }
      /* The --tmd-* tokens only resolve under a designed style; the fallbacks
         are the original classic values, so classic is unchanged. */
      .roulette-btn {
        display: inline-flex; align-items: center; justify-content: center; gap: 8px;
        background: var(--tmd-accent, linear-gradient(135deg, #8e44ad, #c0392b));
        color: #fff; border: 0;
        border-radius: var(--tmd-radius-sm, 14px);
        padding: 12px 16px;
        font-family: var(--tmd-font-display, inherit); font-size: 0.95rem;
        font-weight: 800; cursor: pointer; width: 100%;
      }
      .roulette-btn:disabled { opacity: 0.55; cursor: default; }
      .roulette-btn.is-spinning ha-icon { animation: tm-roulette-spin 0.6s linear infinite; }
      @keyframes tm-roulette-spin { to { transform: rotate(360deg); } }
      .roulette-result {
        display: flex; align-items: center; gap: 8px;
        background: color-mix(in srgb, var(--tmd-accent, #8e44ad) 12%, transparent);
        border: 1px solid color-mix(in srgb, var(--tmd-accent, #8e44ad) 35%, transparent);
        border-radius: var(--tmd-radius-sm, 12px); padding: 8px 12px;
      }
      .roulette-mult {
        background: var(--tmd-accent, #8e44ad); color: #fff;
        border-radius: var(--tmd-radius-sm, 8px); padding: 2px 8px;
        font-weight: 900; font-size: 0.85rem;
      }
      .roulette-name { flex: 1; font-weight: 700; font-size: 0.95rem; }
      .roulette-worth {
        display: inline-flex; align-items: center; gap: 4px;
        font-weight: 800; color: var(--tmd-accent, #8e44ad);
      }
      .roulette-worth ha-icon { --mdc-icon-size: 16px; }
      .roulette-spent {
        text-align: center; font-size: 0.8rem;
        color: var(--tmd-dim, var(--secondary-text-color)); opacity: 0.8;
      }

      /* Reactive-chore countdown (#674). Amber by default, red under 5 min.
         On its own line, not inline in .chore-name — that name ellipsises, and
         a long one clipped the badge down to just the bonus. */
      .deadline-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-top: 4px;
        align-self: flex-start;
        background: rgba(255, 152, 0, 0.18);
        color: #ef6c00;
        font-size: 0.62rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        border-radius: 8px;
        padding: 2px 7px;
        white-space: nowrap;
        width: fit-content;
      }
      .deadline-badge.deadline-urgent {
        background: var(--fun-red);
        color: #fff;
      }
      .deadline-bonus {
        opacity: 0.85;
        font-weight: 900;
      }

      .mandatory-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: var(--fun-red);
        color: #fff;
        font-size: 0.62rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        border-radius: 8px;
        padding: 2px 7px;
        margin-left: 8px;
        vertical-align: middle;
        white-space: nowrap;
      }

      /* Reset countdown — inline beside section title */
      .reset-countdown {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        background: var(--secondary-background-color, #f5f5f5);
        border-radius: 20px;
        padding: 2px 8px 2px 6px;
        white-space: nowrap;
        flex-shrink: 0;
      }

      .reset-countdown ha-icon {
        --mdc-icon-size: 12px;
        flex-shrink: 0;
      }

      .reset-countdown.soon {
        color: var(--fun-orange);
        background: rgba(230,126,34,0.12);
        font-weight: 700;
      }

      /* Empty state */
      .empty-state {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px 20px;
        text-align: center;
      }

      .empty-state ha-icon {
        --mdc-icon-size: 80px;
        color: var(--fun-green);
        margin-bottom: 16px;
        animation: bounce 1s ease infinite;
      }

      @keyframes bounce {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-10px); }
      }

      .empty-state .message {
        font-size: 1.6rem;
        font-weight: bold;
        color: var(--fun-purple);
        margin-bottom: 8px;
      }

      .empty-state .submessage {
        font-size: 1.1rem;
        color: var(--secondary-text-color);
      }

      /* Celebration overlay */
      .celebration-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        animation: fade-in 0.3s ease;
      }

      /* ── Photo-evidence badge on chore rows ── */
      .photo-badge {
        display: inline-flex; align-items: center; gap: 4px;
        background: var(--fun-orange); color: #fff;
        font-size: 0.66rem; font-weight: 700;
        border-radius: 999px; padding: 2px 8px; white-space: nowrap;
      }

      /* ── Photo-evidence capture overlay ── */
      .photo-overlay {
        position: fixed; inset: 0; background: rgba(20, 20, 30, 0.72);
        display: flex; align-items: center; justify-content: center;
        z-index: 10000; padding: 18px; animation: fade-in 0.2s ease;
      }
      .photo-sheet {
        background: var(--card-background-color, #fff);
        border-radius: 22px; width: 100%; max-width: 330px;
        padding: 20px 18px 18px; text-align: center;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
        animation: pop-in 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55);
      }
      .photo-title { font-size: 1.15rem; font-weight: 800; color: var(--fun-purple); }
      .photo-for { font-size: 0.85rem; color: var(--secondary-text-color, #6b7280); margin: 2px 0 16px; }
      .photo-dropzone {
        border: 2px dashed var(--fun-purple); border-radius: 16px;
        padding: 26px 14px; cursor: pointer;
        background: color-mix(in srgb, var(--fun-purple) 6%, var(--card-background-color, #fff));
      }
      .photo-dropzone-icon { font-size: 2.6rem; line-height: 1; }
      .photo-dropzone-label { margin-top: 8px; font-weight: 700; color: var(--fun-purple); }
      .photo-dropzone-hint { font-size: 0.72rem; color: var(--secondary-text-color, #6b7280); margin-top: 4px; }
      .photo-preview {
        position: relative; border-radius: 14px; overflow: hidden;
        background: #000; aspect-ratio: 4 / 3;
        display: flex; align-items: center; justify-content: center;
      }
      .photo-preview img { width: 100%; height: 100%; object-fit: cover; display: block; }
      .photo-size-tag {
        position: absolute; bottom: 8px; right: 8px;
        background: rgba(0, 0, 0, 0.6); color: #fff;
        font-size: 0.66rem; padding: 3px 8px; border-radius: 999px;
      }
      .photo-btn-row { display: flex; gap: 10px; margin-top: 16px; }
      .photo-btn {
        flex: 1; border: none; border-radius: 14px; padding: 13px 10px;
        font-weight: 800; font-size: 0.95rem; cursor: pointer;
      }
      .photo-btn.ghost { background: var(--secondary-background-color, #f5f5f5); color: var(--primary-text-color, #33373d); }
      .photo-btn.primary { background: var(--fun-green); color: #fff; }
      .photo-cancel {
        background: none; border: none; cursor: pointer;
        color: var(--secondary-text-color, #9aa0a6); font-size: 0.85rem;
        margin-top: 10px; width: 100%; padding: 4px;
      }
      .photo-error {
        background: color-mix(in srgb, var(--fun-red) 12%, var(--card-background-color, #fff));
        color: var(--fun-red); border-radius: 12px; padding: 10px;
        font-size: 0.82rem; font-weight: 600; margin-top: 12px;
      }
      .photo-uploading { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 18px 0; }
      .photo-uploading-label { font-weight: 700; color: var(--fun-purple); }
      .photo-spinner {
        width: 42px; height: 42px; border-radius: 50%;
        border: 4px solid var(--secondary-background-color, #eee);
        border-top-color: var(--fun-purple); animation: photo-spin 1s linear infinite;
      }
      @keyframes photo-spin { to { transform: rotate(360deg); } }

      @keyframes fade-in {
        from { opacity: 0; }
        to { opacity: 1; }
      }

      .celebration-content {
        background: var(--card-background-color, #fff);
        border-radius: 30px;
        padding: 40px 50px;
        text-align: center;
        animation: pop-in 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55);
        position: relative;
        overflow: hidden;
      }

      @keyframes pop-in {
        from {
          transform: scale(0);
          opacity: 0;
        }
        to {
          transform: scale(1);
          opacity: 1;
        }
      }

      .celebration-stars {
        font-size: 4rem;
        margin-bottom: 16px;
        animation: star-bounce 0.6s ease infinite;
      }

      @keyframes star-bounce {
        0%, 100% { transform: scale(1) rotate(0deg); }
        50% { transform: scale(1.2) rotate(10deg); }
      }

      .celebration-title {
        font-size: 2.5rem;
        font-weight: bold;
        color: var(--fun-purple);
        margin-bottom: 8px;
      }

      .celebration-message {
        font-size: 1.3rem;
        color: var(--secondary-text-color);
        margin-bottom: 16px;
      }

      .celebration-points {
        font-size: 1.8rem;
        font-weight: bold;
        color: var(--fun-orange);
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
      }

      .celebration-points ha-icon {
        --mdc-icon-size: 28px;
        color: var(--fun-yellow);
      }

      /* Confetti */
      .confetti-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 10000;
        overflow: hidden;
      }

      .confetti {
        position: absolute;
        width: 10px;
        height: 10px;
        animation: confetti-fall 3s linear forwards;
      }

      @keyframes confetti-fall {
        0% {
          transform: translateY(-100px) rotate(0deg);
          opacity: 1;
        }
        100% {
          transform: translateY(100vh) rotate(720deg);
          opacity: 0;
        }
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

      /* ── Responsive — header and chore cards always stay horizontal ── */

      /* Small phones ≤380px */
      @media (max-width: 380px) {
        .card-header { padding: 10px 12px; gap: 8px; }
        .avatar-container { width: 36px; height: 36px; min-width: 36px; }
        .avatar-container ha-icon { --mdc-icon-size: 22px; }
        .chores-container { padding: 10px; gap: 8px; }
        .section-title { font-size: 1rem; margin-bottom: 4px; }
        .chore-card { padding: 10px 12px; gap: 8px; min-height: 54px; flex-wrap: nowrap; }
        .chore-info { flex: 1; min-width: 0; overflow: hidden; }
        .chore-number-badge { width: 30px; height: 30px; min-width: 30px; font-size: 1rem; }
        .chore-number-badge ha-icon { --mdc-icon-size: 18px; }
        .chore-name { font-size: 0.95rem; }
        .chore-points { font-size: 0.82rem; }
        .chore-checkbox { width: 34px; height: 34px; min-width: 34px; border-radius: 8px; }
        .chore-checkbox ha-icon { --mdc-icon-size: 20px; }
      }

      /* Standard phones 381–600px */
      @media (min-width: 381px) and (max-width: 600px) {
        .card-header { padding: 12px 14px; gap: 10px; }
        .avatar-container { width: 40px; height: 40px; min-width: 40px; }
        .avatar-container ha-icon { --mdc-icon-size: 26px; }
        .chores-container { padding: 12px; gap: 9px; }
        .section-title { font-size: 1.05rem; margin-bottom: 6px; }
        .chore-card { padding: 12px 14px; gap: 10px; min-height: 58px; flex-wrap: nowrap; }
        .chore-info { flex: 1; min-width: 0; overflow: hidden; }
        .chore-number-badge { width: 34px; height: 34px; min-width: 34px; font-size: 1.1rem; }
        .chore-name { font-size: 1rem; }
        .chore-checkbox { width: 36px; height: 36px; min-width: 36px; }
        .chore-checkbox ha-icon { --mdc-icon-size: 22px; }
      }

      /* Landscape phones */
      @media (max-width: 900px) and (max-height: 500px) {
        .card-header { padding: 8px 14px; }
        .chores-container { padding: 8px; gap: 6px; }
        .chore-card { padding: 8px 12px; min-height: 48px; flex-wrap: nowrap; }
        .chore-name { font-size: 0.95rem; }
      }

      /* Tablets 601–1023px */
      @media (min-width: 601px) and (max-width: 1023px) {
        .chore-card { padding: 14px 16px; flex-wrap: nowrap; }
        .chore-name { font-size: 1.1rem; }
      }

      /* Desktop ≥1024px — keep compact, never inflate */
      @media (min-width: 1024px) {
        .chores-container { padding: 16px; gap: 10px; }
        .section-title { font-size: 1.2rem; }
        .chore-card { padding: 14px 18px; min-height: 62px; flex-wrap: nowrap; }
        .chore-number-badge { width: 36px; height: 36px; min-width: 36px; font-size: 1.15rem; }
        .chore-name { font-size: 1.05rem; }
        .chore-points { font-size: 0.92rem; }
        .chore-checkbox { width: 38px; height: 38px; min-width: 38px; border-radius: 9px; }
        .chore-checkbox ha-icon { --mdc-icon-size: 22px; }
      }

      /* ── Timed task card ─── */
      .timed-chore-card {
        border-radius: 20px;
        padding: 16px 18px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
        border: 3px solid var(--fun-cyan);
        background: color-mix(in srgb, var(--fun-cyan) 10%, var(--card-background-color, #fff));
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        -webkit-user-select: none;
        user-select: none;
      }
      .timed-chore-card.loading { opacity: 0.6; pointer-events: none; }

      .timed-top-row {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .timed-rate {
        margin-left: auto;
        font-size: 0.8rem;
        font-weight: 700;
        color: var(--fun-cyan);
        background: rgba(26, 188, 156, 0.12);
        padding: 4px 10px;
        border-radius: 12px;
        white-space: nowrap;
      }
      .timer-display {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        padding: 10px 16px;
        background: var(--secondary-background-color, rgba(0, 0, 0, 0.03));
        border-radius: 14px;
      }
      .timer-counter {
        font-family: 'SF Mono', 'Fira Code', 'Courier New', monospace;
        font-size: 2rem;
        font-weight: 700;
        color: var(--primary-text-color);
        letter-spacing: 0.05em;
        min-width: 100px;
        text-align: center;
      }
      .timer-counter.running { color: var(--fun-green); }
      .timer-counter.paused { color: var(--fun-orange); }
      .timer-points-live {
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--fun-orange);
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .timer-points-live ha-icon { --mdc-icon-size: 18px; color: var(--fun-yellow); }
      .recording-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--fun-green);
        animation: pulse-dot 1.5s ease-in-out infinite;
      }
      @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.4; transform: scale(0.7); }
      }
      .paused-badge {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        color: var(--fun-orange);
        background: rgba(230, 126, 34, 0.12);
        padding: 3px 8px;
        border-radius: 6px;
        letter-spacing: 0.03em;
      }
      .timer-actions {
        display: flex;
        gap: 10px;
        justify-content: center;
      }
      .timer-btn {
        border: none;
        border-radius: 14px;
        padding: 12px 24px;
        font-size: 1rem;
        font-weight: 700;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        transition: transform 0.1s ease, box-shadow 0.15s ease;
        -webkit-user-select: none;
        user-select: none;
        -webkit-tap-highlight-color: transparent;
      }
      .timer-btn:active { transform: scale(0.95); }
      .timer-btn.start, .timer-btn.resume {
        background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%);
        color: white;
        box-shadow: 0 4px 12px rgba(46, 204, 113, 0.35);
        flex: 1;
      }
      .timer-btn.start:hover, .timer-btn.resume:hover {
        box-shadow: 0 6px 16px rgba(46, 204, 113, 0.5);
        transform: scale(1.02);
      }
      .timer-btn.pause {
        background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%);
        color: white;
        box-shadow: 0 4px 12px rgba(243, 156, 18, 0.35);
        flex: 1;
      }
      .timer-btn.pause:hover {
        box-shadow: 0 6px 16px rgba(243, 156, 18, 0.5);
        transform: scale(1.02);
      }
      .timer-btn.stop {
        background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
        color: white;
        box-shadow: 0 4px 12px rgba(231, 76, 60, 0.35);
        padding: 12px 20px;
      }
      .timer-btn.stop:hover {
        box-shadow: 0 6px 16px rgba(231, 76, 60, 0.5);
        transform: scale(1.02);
      }
      .btn-icon { font-size: 1.2rem; }
      .daily-cap-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.75rem;
        color: var(--secondary-text-color);
        padding: 0 4px;
      }
      .cap-track {
        flex: 1;
        height: 6px;
        background: var(--divider-color, rgba(0, 0, 0, 0.06));
        border-radius: 3px;
        overflow: hidden;
      }
      .cap-fill {
        height: 100%;
        border-radius: 3px;
        background: linear-gradient(90deg, var(--fun-cyan), var(--fun-green));
        transition: width 0.3s ease;
      }
      .cap-fill.warning {
        background: linear-gradient(90deg, var(--fun-orange), var(--fun-red));
      }
      .cap-label {
        font-weight: 600;
        white-space: nowrap;
      }
      .cap-label.near-cap { color: var(--fun-red); font-weight: 700; }

      /* ── Badge strip ── */
      .badge-strip {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 16px;
        cursor: pointer;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .vacation-banner {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 16px;
        background: linear-gradient(135deg, #ffe9b3, #ffd27f);
        color: #6b4e00;
        font-weight: 700;
        font-size: 1rem;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .vacation-banner ha-icon { --mdc-icon-size: 24px; }
      .badge-strip:hover { background: var(--secondary-background-color, rgba(0,0,0,0.03)); }
      .badge-strip-label {
        font-size: 11px;
        color: var(--secondary-text-color);
        margin-right: 2px;
        white-space: nowrap;
      }
      .badge-mini {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        --mdc-icon-size: 16px;
        color: #1a1a1a;
        border: 2px solid var(--t);
        background: var(--t);
        flex-shrink: 0;
      }
      .badge-mini.just-earned { animation: badge-earn-pulse 1.6s ease-out; }
      @keyframes badge-earn-pulse {
        0%   { transform: scale(0.6); }
        50%  { transform: scale(1.15); box-shadow: 0 0 0 12px rgba(255,255,255,0.0); }
        100% { transform: scale(1); }
      }
      .badge-strip-more {
        font-size: 11px;
        color: var(--primary-color);
        margin-left: 2px;
        white-space: nowrap;
      }

      /* ── Next badge progress (#780) ── */
      .next-badge {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 16px;
        cursor: pointer;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .next-badge:hover { background: var(--secondary-background-color, rgba(0,0,0,0.03)); }
      .next-badge:focus-visible {
        outline: 2px solid var(--primary-color);
        outline-offset: -2px;
      }
      .next-badge-icon {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        --mdc-icon-size: 16px;
        color: #1a1a1a;
        border: 2px dashed var(--t);
        background: transparent;
        flex-shrink: 0;
        opacity: 0.85;
      }
      .next-badge-body { flex: 1; min-width: 0; }
      .next-badge-top {
        display: flex;
        align-items: baseline;
        gap: 6px;
        margin-bottom: 5px;
      }
      .next-badge-label {
        font-size: 11px;
        color: var(--secondary-text-color);
        white-space: nowrap;
      }
      .next-badge-name {
        font-size: 12.5px;
        font-weight: 700;
        color: var(--primary-text-color);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .next-badge-count {
        margin-left: auto;
        font-size: 11px;
        font-weight: 700;
        color: var(--secondary-text-color);
        white-space: nowrap;
      }
      .next-badge-bar {
        height: 6px;
        border-radius: 3px;
        background: var(--divider-color, #e0e0e0);
        overflow: hidden;
      }
      .next-badge-bar i {
        display: block;
        height: 100%;
        border-radius: 3px;
        transition: width 0.4s ease;
      }

      /* ══════════════════════════════════════════════════════════════════
         DESIGNED STYLES (playroom / console / cleanpro)
         Shared .tmd kit + tokens come from taskmate-design.js styles().
         Only card-specific layout classes live here.
         Ported from docs/design/redesigns/frag/03-child.html.
      ══════════════════════════════════════════════════════════════════ */
      .tmd-chores { display: grid; gap: 11px; }
      .tmd-chore {
        display: flex; align-items: center; gap: 10px;
        background: var(--tmd-surface-2);
        border-radius: 18px; padding: 11px 13px;
      }
      .tmd-chore .num-badge {
        width: 30px; height: 30px; border-radius: 12px; flex: none;
        display: grid; place-items: center;
        font-family: var(--tmd-font-display); font-weight: 800; color: #fff;
        background: var(--ac, var(--tmd-accent));
      }
      .tmd-chore .ch-emoji { font-size: 22px; flex: none; }
      .tmd-chore .ch-mid { flex: 1; min-width: 0; }
      .tmd-chore .ch-name {
        font-weight: 800; font-size: 15px;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .tmd-chore.done .ch-name { text-decoration: line-through; }
      .tmd-chore.done { opacity: 0.6; }
      .tmd-chore .done-chip {
        background: transparent; border-color: transparent; color: var(--tmd-good);
      }

      /* Console — quest log rows */
      .tmd-quest {
        display: flex; align-items: center; gap: 10px;
        background: var(--tmd-surface-2); border: 1px solid var(--tmd-border);
        border-radius: 8px; padding: 10px 11px;
      }
      .tmd-quest .q-num { width: 22px; font-size: 14px; color: var(--tmd-accent); }
      .tmd-quest .q-emoji { font-size: 19px; flex: none; }
      .tmd-quest .q-mid { flex: 1; min-width: 0; }
      .tmd-quest .q-name {
        font-weight: 700;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .tmd-quest.done { opacity: 0.55; }
      .tmd-quest.done .q-name { text-decoration: line-through; }
      .tmd-quest .q-xp { font-size: 11px; color: var(--tmd-gold); }
      .tmd-quest .q-cleared { font-size: 11px; color: var(--tmd-good); }

      /* Clean Pro — tidy checklist */
      .tmd-checklist { display: grid; gap: 0; }
      .tmd-check {
        display: flex; align-items: center; gap: 10px; padding: 11px 2px;
      }
      .tmd-check + .tmd-check { border-top: 1px solid var(--tmd-border); }
      .tmd-check .c-num {
        width: 26px; height: 26px; border-radius: 8px; flex: none;
        display: grid; place-items: center; font-size: 12px;
        font-family: var(--tmd-font-display); font-weight: 800; color: #fff;
        background: var(--ac, var(--tmd-accent));
      }
      .tmd-check .c-emoji { font-size: 18px; flex: none; }
      .tmd-check .c-mid { flex: 1; min-width: 0; }
      .tmd-check .c-name {
        font-weight: 600;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
      }
      .tmd-check.done { opacity: 0.55; }
      .tmd-check.done .c-name { text-decoration: line-through; }
      .tmd-check .c-pts { background: transparent; }
      .tmd-check .c-done {
        background: transparent; border-color: transparent; color: var(--tmd-good);
      }

      /* Designed: shared chore meta (mandatory / photo / description / dim states) */
      .tmd-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-top: 3px; }
      .tmd-tag {
        display: inline-flex; align-items: center; gap: 3px;
        font-size: 10.5px; font-weight: 800; line-height: 1;
        padding: 3px 7px; border-radius: 999px;
        background: var(--tmd-surface-2); color: var(--tmd-dim);
        border: 1px solid var(--tmd-border);
      }
      .tmd-tag.mandatory { background: color-mix(in srgb, var(--tmd-bad) 16%, transparent); color: var(--tmd-bad); border-color: transparent; }
      .tmd-tag.photo { background: color-mix(in srgb, var(--tmd-accent) 14%, transparent); color: var(--tmd-accent); border-color: transparent; }
      .tmd-desc { font-size: 11.5px; color: var(--tmd-dim); margin-top: 3px; white-space: normal; line-height: 1.3; }
      .tmd-chore.mandatory, .tmd-quest.mandatory, .tmd-check.mandatory {
        box-shadow: inset 3px 0 0 0 var(--tmd-bad);
        padding-left: 20px;
      }
      .tmd-chore.dimmed, .tmd-quest.dimmed, .tmd-check.dimmed { opacity: 0.5; }
      /* Clickable done-state chips (tap to undo) */
      .tmd-undochip { cursor: pointer; font: inherit; font-weight: 800; line-height: 1; }
      .tmd-undochip:hover { filter: brightness(0.97); }
      .tmd-undochip[disabled] { opacity: 0.6; cursor: default; }
      .q-undo { background: var(--tmd-surface-2); color: var(--tmd-dim); border: 1px solid var(--tmd-border); padding: 7px 10px; font-size: 14px; }

      /* Designed: an explicit chore picture in the glyph slot. The emoji it
         replaces is sized by font-size, which an ha-icon ignores, so each row
         type restates its own size. Inherits the row accent so the icon reads
         as part of the style rather than a pasted-in glyph. */
      .tmd-glyph-icon { color: var(--ac, var(--tmd-accent)); display: block; }
      .tmd-chore .ch-emoji .tmd-glyph-icon { --mdc-icon-size: 22px; }
      .tmd-quest .q-emoji .tmd-glyph-icon { --mdc-icon-size: 19px; }
      .tmd-check .c-emoji .tmd-glyph-icon { --mdc-icon-size: 18px; }

      /* Designed: pending-points + countdown chips on the header/section */
      .tmd-pending {
        margin-left: auto; display: inline-flex; align-items: center; gap: 4px;
        font-size: 11px; font-weight: 800; padding: 4px 9px; border-radius: 999px;
        background: rgba(255,255,255,.22); color: #fff;
      }
      .tmd-section {
        display: flex; align-items: center; gap: 8px; margin-bottom: 11px;
        font-family: var(--tmd-font-display); font-weight: 800; font-size: 14px; color: var(--tmd-text);
      }
      .tmd-countdown {
        margin-left: auto; display: inline-flex; align-items: center; gap: 4px;
        font-size: 11px; font-weight: 700; color: var(--tmd-dim);
      }
      .tmd-countdown.soon { color: var(--tmd-warn); }

      /* Designed: badge strip */
      .tmd-badges {
        display: flex; align-items: center; gap: 7px; flex-wrap: wrap;
        padding: 9px 11px; margin-bottom: 11px;
        background: var(--tmd-surface-2); border: 1px solid var(--tmd-border);
        border-radius: var(--tmd-radius-sm); cursor: pointer;
      }
      .tmd-badges .lbl { font-size: 11px; font-weight: 800; color: var(--tmd-dim); text-transform: uppercase; letter-spacing: .04em; }
      .tmd-badge-mini {
        width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center;
        background: var(--t, var(--tmd-accent)); color: #fff;
      }
      .tmd-badge-mini ha-icon { --mdc-icon-size: 16px; color: #fff; }
      .tmd-badges .more { font-size: 11px; font-weight: 800; color: var(--tmd-accent); }

      /* Designed: next badge progress (#780) */
      .tmd-next-badge {
        display: flex; align-items: center; gap: 9px;
        padding: 9px 11px; margin-bottom: 11px;
        background: var(--tmd-surface-2); border: 1px solid var(--tmd-border);
        border-radius: var(--tmd-radius-sm); cursor: pointer;
      }
      .tmd-next-badge:focus-visible { outline: 2px solid var(--tmd-accent); outline-offset: 1px; }
      .tmd-next-badge .ic {
        width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center;
        border: 2px dashed var(--t, var(--tmd-accent)); color: var(--tmd-dim); flex-shrink: 0;
      }
      .tmd-next-badge .ic ha-icon { --mdc-icon-size: 15px; }
      .tmd-next-badge .bd { flex: 1; min-width: 0; }
      .tmd-next-badge .top { display: flex; align-items: baseline; gap: 6px; margin-bottom: 5px; }
      .tmd-next-badge .lbl {
        font-size: 11px; font-weight: 800; color: var(--tmd-dim);
        text-transform: uppercase; letter-spacing: .04em; white-space: nowrap;
      }
      .tmd-next-badge .nm {
        font-size: 12.5px; font-weight: 700; color: var(--tmd-text);
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .tmd-next-badge .cnt {
        margin-left: auto; font-size: 11px; font-weight: 800;
        color: var(--tmd-dim); white-space: nowrap;
      }
      .tmd-next-badge .bar {
        height: 6px; border-radius: 999px; background: var(--tmd-border); overflow: hidden;
      }
      .tmd-next-badge .bar i {
        display: block; height: 100%; border-radius: 999px; transition: width .4s ease;
      }
      /* Playroom is chunkier, console squares everything off, accessible needs
         a solid ring rather than a dashed one to stay legible. */
      :host([data-tm-design="playroom"]) .tmd-next-badge .bar { height: 8px; }
      :host([data-tm-design="console"]) .tmd-next-badge .bar,
      :host([data-tm-design="console"]) .tmd-next-badge .bar i { border-radius: 0; }
      :host([data-tm-design="accessible"]) .tmd-next-badge .ic { border-style: solid; }
      :host([data-tm-design="accessible"]) .tmd-next-badge .bar { height: 10px; }
      :host([data-tm-design="accessible"]) .tmd-next-badge .nm,
      :host([data-tm-design="accessible"]) .tmd-next-badge .cnt { font-size: 14px; }

      /* Designed: vacation banner + swappable section */
      .tmd-vacation {
        display: flex; align-items: center; gap: 7px; padding: 9px 11px; margin-bottom: 11px;
        background: color-mix(in srgb, var(--tmd-warn) 16%, transparent); color: var(--tmd-warn);
        border-radius: var(--tmd-radius-sm); font-weight: 700; font-size: 12.5px;
      }
      .tmd-swaps { margin-top: 12px; }
    `;
    const tokens = window.__taskmate_design && window.__taskmate_design.styles
      ? window.__taskmate_design.styles() : null;
    return tokens ? [tokens, base] : base;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity");
    }
    if (!config.child_id) {
      throw new Error("Please define a child_id");
    }
    this.config = {
      time_category: "anytime",
      debug: false,
      default_sound: "coin",
      undo_sound: "undo",
      due_days_mode: "hide",         // "hide" = hide chores not due today, "dim" = show greyed out
      elapsed_time_mode: "dim",      // "dim" | "hide" | "show" — chores whose time period has passed without completion
      show_countdown: true,          // Show midnight reset countdown below section title
      show_due_days_only: true,      // Whether to apply due_days filtering at all
      show_badges: true,             // Show badge strip between points and chores
      show_next_badge: true,         // Show progress toward the closest unearned badge
            header_color: '#9b59b6',
    ...config,
    };
  }

  getCardSize() {
    return 4;
  }

  static getConfigElement() {
    return document.createElement("taskmate-child-card-editor");
  }

  static getStubConfig() {
    return {
      entity: "sensor.taskmate_overview",
      child_id: "",
      time_category: "morning",
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

    // Get child info
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const child = children.find(c => c.id === this.config.child_id)
      || (!this.config.child_id && children[0]);

    if (!child) {
      return html`
        <ha-card>
          <div class="error-state">
            <ha-icon icon="mdi:account-alert"></ha-icon>
            <div>${this._t('child.child_not_found', { child_id: this.config.child_id })}</div>
          </div>
        </ha-card>
      `;
    }

    // Get chores for this child and time category
    const allChores = attrs.chores || [];

    // Log raw data for debugging assignment issues

    // DEBUG: Create debug info object for visible debugging
    const debugInfo = {
      configChildId: this.config.child_id,
      foundChildId: child.id,
      foundChildName: child.name,
      totalChores: allChores.length,
      sampleChores: allChores.slice(0, 3).map(c => ({
        name: c.name,
        assigned_to: c.assigned_to,
        assigned_to_type: typeof c.assigned_to,
        isArray: Array.isArray(c.assigned_to)
      }))
    };

    const childChores = this._filterAndSortChores(allChores, child);

    // Log the filtering result

    // Store debug info for rendering
    this._debugInfo = {
      ...debugInfo,
      filteredCount: childChores.length
    };

    const pointsIcon = attrs.points_icon || "mdi:star";
    const pointsName = attrs.points_name || this._t('common.stars');

    // Avatar now in children array directly
    const avatar = child.avatar || "mdi:account-circle";

    // Resolve badges sensor entity for this child
    const badgesEntity = this._resolveBadgesEntity(child);
    const earnedBadges = (badgesEntity?.attributes?.earned) || [];
    const showBadges = this.config.show_badges !== false && earnedBadges.length > 0;
    const nextBadge = this._nextBadge(badgesEntity);

    // Get pending points for this child
    const pendingPoints = child.pending_points || 0;

    // Get today's completions for this child (with timezone-aware filtering as fallback)
    // The backend provides todays_completions, but we also apply client-side filtering
    // to ensure timezone correctness matches the HA frontend timezone
    const allCompletions = attrs.todays_completions || attrs.completions || [];
    const todaysCompletions = this._filterCompletionsForToday(allCompletions);

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${_safeColor(this.config.header_color, '#9b59b6')}; }</style>
        <div class="card-header">
          <div class="header-left">
            ${(() => {
              const opts = child.avatar_options || [];
              const unlocked = opts.filter(o => o.unlocked);
              const canChange = this.config.allow_avatar_change !== false && unlocked.length > 1;
              return html`
                <div class="avatar-container ${canChange ? 'avatar-clickable' : ''}"
                     @click=${canChange ? () => this._toggleAvatarPicker() : null}
                     title="${canChange ? this._t('child.avatar_change') : ''}">
                  <ha-icon icon="${avatar}"></ha-icon>
                  ${canChange ? html`<span class="avatar-edit-dot"><ha-icon icon="mdi:pencil"></ha-icon></span>` : ''}
                </div>
                ${canChange && this._avatarPickerOpen ? this._renderAvatarPicker(child, opts) : ''}
              `;
            })()}
            <div class="child-name-container">
              <div class="child-name">${child.name}</div>
              ${child.level ? html`
                <div class="child-level" title="${child.level_progress || 0} / ${child.level_target || 100} XP">
                  <span class="level-badge">${this._t('child.level_label', { level: child.level })}</span>
                  <div class="level-xp-track">
                    <div class="level-xp-fill" style="width: ${Math.max(0, Math.min(100, Math.round(((child.level_progress || 0) / (child.level_target || 100)) * 100)))}%"></div>
                  </div>
                </div>
              ` : ''}
            </div>
          </div>
          <div class="points-display">
            <div class="stars-row">
              <div class="stars-section">
                <div class="stars-value my-stars">
                  <ha-icon icon="${pointsIcon}"></ha-icon>
                  ${child.points}
                </div>
                <div class="stars-label my-stars">${pointsName}</div>
              </div>
              ${pendingPoints > 0 ? html`
                <div class="stars-divider"></div>
                <div class="stars-section">
                  <div class="stars-value waiting-stars">
                    <ha-icon icon="mdi:timer-sand"></ha-icon>
                    +${pendingPoints}
                  </div>
                  <div class="stars-label waiting-stars">${this._t('common.pending')}</div>
                </div>
              ` : ''}
            </div>
          </div>
        </div>

        ${attrs.vacation_active ? html`
          <div class="vacation-banner">
            <ha-icon icon="mdi:palm-tree"></ha-icon>
            <span>${this._t('child.on_vacation')}${attrs.vacation_name ? ` · ${attrs.vacation_name}` : ''}</span>
          </div>
        ` : ''}

        ${showBadges ? html`
          <div class="badge-strip" @click=${() => this._openBadgesView()} title="${this._t('badges.label')}">
            <span class="badge-strip-label">${this._t('badges.label')}</span>
            ${earnedBadges.slice(0, 5).map(b => html`
              <div class="badge-mini tier-${b.tier} ${this._justEarnedBadge === window.__taskmate_badge_id(b) ? 'just-earned' : ''}"
                style="--t: ${this._tierColor(b.tier)}">
                <ha-icon icon="${b.icon || 'mdi:medal'}"></ha-icon>
              </div>
            `)}
            ${earnedBadges.length > 5 ? html`<span class="badge-strip-more">+${earnedBadges.length - 5} →</span>` : ''}
          </div>
        ` : ''}

        ${nextBadge ? html`
          <div class="next-badge" role="button" tabindex="0"
            aria-label="${this._t('badges.next_up')} — ${nextBadge.name} ${nextBadge.label}"
            @click=${() => this._openBadgesView()}
            @keydown=${(e) => this._badgeKeydown(e)}>
            <div class="next-badge-icon" style="--t: ${this._tierColor(nextBadge.badge.tier)}">
              <ha-icon icon="${nextBadge.badge.icon || 'mdi:trophy-outline'}"></ha-icon>
            </div>
            <div class="next-badge-body">
              <div class="next-badge-top">
                <span class="next-badge-label">${this._t('badges.next_up')}</span>
                <span class="next-badge-name">${nextBadge.name}</span>
                <span class="next-badge-count">${nextBadge.label}</span>
              </div>
              <div class="next-badge-bar" role="progressbar"
                aria-valuenow="${nextBadge.pct}" aria-valuemin="0" aria-valuemax="100">
                <i style="width: ${nextBadge.pct}%; background: ${this._tierColor(nextBadge.badge.tier)}"></i>
              </div>
            </div>
          </div>
        ` : ''}

        <div class="chores-container">
          ${childChores.length === 0
            ? this._renderEmptyState()
            : html`
                <div class="section-title">
                  <ha-icon icon="${this._getTimeCategoryIcon(this.config.time_category)}"></ha-icon>
                  <span class="section-title-text">${this._getDynamicTitle()}</span>
                  ${this.config.show_countdown !== false ? (() => {
                    const countdown = this._getMidnightCountdown();
                    return countdown ? html`
                      <div class="reset-countdown ${countdown.soon ? 'soon' : ''}">
                        <ha-icon icon="mdi:clock-outline"></ha-icon>
                        <span>${countdown.label}</span>
                      </div>
                    ` : '';
                  })() : ''}
                </div>
                ${this._renderRoulette(child, childChores, pointsIcon)}
                ${this.config.pre_reader === true ? html`
                  <div class="pre-reader-grid">
                    ${childChores.map((chore) =>
                      this._renderPreReaderTile(chore, child, pointsIcon, todaysCompletions))}
                  </div>
                ` : childChores.map((chore, index) => html`
                  ${chore.task_type === 'timed'
                    ? this._renderTimedChoreCard(chore, child, pointsIcon, todaysCompletions, index)
                    : html`
                      ${this._renderChoreCard(chore, child, pointsIcon, todaysCompletions, index)}
                      ${this._renderBonusSubtasks(chore, child, pointsIcon, todaysCompletions)}
                    `}
                `)}
              `}
        </div>

        ${this._renderSwappable(allChores, child, pointsIcon)}

        ${this._celebrating ? this._renderCelebration() : ""}
        ${this._confetti.length > 0 ? this._renderConfetti() : ""}
        ${this._renderPhotoCapture()}
        <input type="file" id="tm-photo-input" accept="image/*" capture="environment"
               style="display:none" @change="${this._onPhotoSelected}">

        ${this.config.debug === true ? html`
          <!-- DEBUG PANEL -->
          <div style="margin-top: 20px; padding: 10px; background: #333; color: #0f0; font-family: monospace; font-size: 11px; border-radius: 8px;">
            <div><strong>DEBUG INFO:</strong></div>
            <div>Config child_id: "${this.config.child_id}"</div>
            <div>Found child.id: "${this._debugInfo?.foundChildId}"</div>
            <div>Found child.name: "${this._debugInfo?.foundChildName}"</div>
            <div>Total chores: ${this._debugInfo?.totalChores}</div>
            <div>Filtered chores: ${this._debugInfo?.filteredCount}</div>
            <div style="margin-top: 5px;"><strong>Sample chores assigned_to:</strong></div>
            ${(this._debugInfo?.sampleChores || []).map(c => html`
              <div>- ${c.name}: ${JSON.stringify(c.assigned_to)} (isArray: ${c.isArray})</div>
            `)}
          </div>
        ` : ""}
      </ha-card>
    `;
  }

  /* ══════════════════════════════════════════════════════════════════════
     DESIGNED STYLES (playroom / console / cleanpro) — see taskmate-design.js
     Ported from docs/design/redesigns/frag/03-child.html.
     Reuses the real chore data + the existing complete/undo handlers, and the
     classic sub-renderers for timed chores, bonus subtasks, celebration,
     confetti and photo capture — so sounds/timers/photo/swap/badges all run in
     designed mode too. Honours every setConfig + editor option.
  ══════════════════════════════════════════════════════════════════════ */

  // The per-child badges sensor is entity-id'd from the child NAME
  // ("TaskMate <Name> Badges" → sensor.taskmate_<name>_badges), NOT the
  // child_id — so resolve it robustly or the badge strip never finds it.
  _resolveBadgesEntity(child) {
    if (!this.hass || !child) return null;
    const slug = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    const nameSlug = slug(child.name);
    const candidates = [
      `sensor.taskmate_${nameSlug}_badges`,
      `sensor.taskmate_badges_${slug(this.config.child_id)}`,
    ];
    for (const id of candidates) if (this.hass.states[id]) return this.hass.states[id];
    if (nameSlug) {
      for (const eid in this.hass.states) {
        if (/^sensor\.taskmate_.*_badges$/.test(eid) && eid.includes(nameSlug)) return this.hass.states[eid];
      }
    }
    return null;
  }

  /* The single closest unearned badge (#780) — the kid-facing "next up" line.
     `available[]` is already sorted by nothing in particular, so pick the
     highest progress_pct. Badges nobody has started (0%) are skipped: a bar
     stuck at zero is noise, not motivation. Returns null when there is
     nothing worth showing. */
  _nextBadge(badgesEntity) {
    if (this.config.show_next_badge === false) return null;
    const available = badgesEntity?.attributes?.available || [];
    let best = null;
    for (const b of available) {
      const pct = Math.max(0, Math.min(100, Number(b.progress_pct) || 0));
      if (pct <= 0) continue;
      if (!best || pct > best.pct) best = { badge: b, pct };
    }
    if (!best) return null;
    const c = best.badge.closest_criterion;
    // Older backends (and criteria-free, manual-award badges) have no
    // closest_criterion — fall back to the percentage.
    best.label = c && c.target ? `${c.current} / ${c.target}` : `${best.pct}%`;
    best.name = this._badgeName(best.badge);
    return best;
  }

  // Built-in badge names arrive from the sensor in English; the localised
  // name lives under badge.name_<suffix> (same scheme as the panel).
  _badgeName(b) {
    const id = b.badge_id || "";
    if (!id.startsWith("builtin.")) return b.name;
    const key = "badge.name_" + id.slice("builtin.".length);
    const t = this._t(key);
    return t !== key ? t : b.name;
  }

  _designTone(i) { return `var(--tmd-c${(i % 6) + 1})`; }

  _av(child, tone, size) {
    const a = child.avatar || "";
    const inner = a.startsWith("mdi:")
      ? html`<ha-icon icon="${a}"></ha-icon>`
      : a
        ? html`<img src="${a}" alt="${child.name}">`
        : (child.name || "?").split(" ").map(w => w[0]).slice(0, 2).join("").toUpperCase();
    return html`<div class="av" style="--av:${size}px;--ac:${tone}">${inner}</div>`;
  }

  _choreEmoji(chore) {
    const n = `${chore.name || ""} ${chore.icon || ""}`.toLowerCase();
    const map = [
      [/(teeth|brush|tooth)/, "🪥"], [/(bed|sleep)/, "🛏️"],
      [/(dog|pet|cat|feed)/, "🐶"], [/(tidy|clean|sweep|broom)/, "🧹"],
      [/(dish|wash|plate)/, "🍽️"], [/(trash|bin|rubbish|garbage)/, "🗑️"],
      [/(homework|study|read|book)/, "📚"], [/(water|plant|garden)/, "🪴"],
      [/(laundry|clothes|fold)/, "🧺"], [/(shower|bath)/, "🛁"],
      [/(cook|food|kitchen)/, "🍳"], [/(toy|play)/, "🧸"],
      [/(music|practice|piano)/, "🎵"], [/(car|wash)/, "🚗"],
      [/(exercise|run|sport)/, "🏃"], [/(vacuum)/, "🧽"],
    ];
    for (const [re, e] of map) if (re.test(n)) return e;
    return "⭐";
  }

  /** What a designed chore row shows in its glyph slot.
   *
   * An explicit picture wins over the keyword guess (#745) — otherwise
   * choosing mdi:watering-can changed nothing, because _choreEmoji only ever
   * matched on words. The guess stays as the fallback so chores with no
   * picture, which is all of them until someone sets one, look as they did.
   * The icon inherits the row's accent so it reads as part of the style.
   */
  _choreGlyph(chore) {
    const v = window.__taskmate_chore_visual(chore);
    if (v.kind === "image") {
      return html`<img class="tmd-glyph-img" src="${v.url}" alt="" loading="lazy">`;
    }
    if (v.kind === "icon") {
      return html`<ha-icon icon="${v.icon}" class="tmd-glyph-icon"></ha-icon>`;
    }
    return this._choreEmoji(chore);
  }

  /** Mirror of _renderChoreCard's "completed today" detection, designed branch only. */
  _isChoreDone(chore, child, todaysCompletions) {
    // async_parent_complete_chore writes child_id="__parent__" to dismiss a
    // chore for the WHOLE pool with zero points — it never credits a specific
    // child. Every other assignment mode treats that as "done for whoever is
    // looking", which is the intended behavior. first_come is exclusive: a
    // pool-wide dismissal means nobody actually completed it, so it must not
    // read as this child's own done state (green row + live undo chip) for
    // anyone — it should fall through to the locked/dimmed row instead
    // (chore._isFirstComeLocked, set in _filterAndSortChores).
    const isFirstCome = chore.assignment_mode === "first_come";
    const childCompletionsToday = (todaysCompletions || []).filter(
      (comp) => comp.chore_id === chore.id
        && (comp.child_id === child.id || (!isFirstCome && comp.child_id === "__parent__"))
        && !comp.bonus_subtask_id
    );
    let count = childCompletionsToday.length;
    const optimisticKey = `${chore.id}_${child.id}`;
    const opt = this._optimisticCompletions && this._optimisticCompletions[optimisticKey];
    if (opt) {
      const actualTs = childCompletionsToday.map(c => c.completed_at ? new Date(c.completed_at).getTime() : 0);
      const optTs = opt.timestamps || [opt.timestamp || Date.now()];
      for (const t of optTs) {
        if (!actualTs.some(a => Math.abs(a - t) < 2000)) count += 1;
      }
    }
    const done = count >= (chore.daily_limit || 1);
    return { done, completions: childCompletionsToday };
  }

  _renderDesigned(design) {
    const entity = this.hass.states[this.config.entity];
    const hd = _safeColor(this.config.header_color, "#ff7043");

    const header = (title, sub, pill) => html`
      <div class="tmd-hd">
        ${pill || ""}
        <span class="ic">🧒</span>
        <span class="tt">${title}${sub ? html`<small>${sub}</small>` : ""}</span>
      </div>`;

    if (!entity) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${header(this._t("common.entity_not_found", { entity: this.config.entity }))}
        <div class="tmd-bd"><div class="tmd-empty">${this._t("common.entity_not_found", { entity: this.config.entity })}</div></div>
      </ha-card>`;
    }

    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity.attributes || {};
    const children = attrs.children || [];
    const child = children.find(c => c.id === this.config.child_id) || (!this.config.child_id && children[0]);

    if (!child) {
      return html`<ha-card class="tmd" style="--hd:${hd}">
        ${header(this._t("child.child_not_found", { child_id: this.config.child_id }))}
        <div class="tmd-bd"><div class="tmd-empty">${this._t("child.child_not_found", { child_id: this.config.child_id })}</div></div>
      </ha-card>`;
    }

    const allChores = attrs.chores || [];
    const childChores = this._filterAndSortChores(allChores, child);
    const allCompletions = attrs.todays_completions || attrs.completions || [];
    const todaysCompletions = this._filterCompletionsForToday(allCompletions);
    const pointsIcon = attrs.points_icon || "mdi:star";

    const dueDaysMode = this.config.due_days_mode || "hide";
    const elapsedTimeMode = this.config.elapsed_time_mode || "dim";
    const dependencyMode = this.config.dependency_mode || "hide";
    const recurrenceDoneMode = this.config.recurrence_done_mode || "dim";
    const firstComeDoneMode = this.config.first_come_done_mode || "hide";

    // Annotate each chore with done-state + handlers, preserving the classic path's logic.
    const rows = childChores.map((chore, i) => {
      const { done, completions } = this._isChoreDone(chore, child, todaysCompletions);
      const loading = !!this._loading[chore.id];
      // Blocked chores only reach here under dim/show — hide is filtered
      // upstream. Either way the tap must be refused (#793).
      const blocked = !!chore._isDependencyBlocked && !done;
      // Recurring chore still inside its cooldown. Excluded when done so the
      // undo chip stays live, exactly as on the classic row.
      const recLocked = !!chore._isRecurrenceLocked && !done;
      // First-come chore claimed by a different pool member (first_come_done_mode
      // dim/show only — hide is filtered upstream same as recurrence). Never true
      // for the winner's own row: _isFirstComeLocked is only set on siblings.
      const firstComeLocked = !!chore._isFirstComeLocked && !done;
      const onAct = () => {
        if (loading || blocked || recLocked || firstComeLocked) return;
        if (done) this._handleUndo(chore, child, completions);
        else this._handleComplete(chore, child);
      };
      // Mirror the classic chore card's dim states (due-days "dim" / elapsed "dim" /
      // locked preview). "hide" modes are already filtered out upstream.
      const notDueToday = chore._hasDueDays && !chore._isDueToday;
      const dimmed = !done && (
        (notDueToday && dueDaysMode === "dim") ||
        (chore._isTimeElapsed && elapsedTimeMode === "dim") ||
        (blocked && dependencyMode === "dim") ||
        (chore._isRecurrenceLocked && recurrenceDoneMode === "dim") ||
        (chore._isFirstComeLocked && firstComeDoneMode === "dim") ||
        chore._isLockedPreview === true
      );
      return {
        chore, child, done, loading, onAct, index: i, dimmed, blocked, recLocked, firstComeLocked,
        tone: this._designTone(i),
        glyph: this._choreGlyph(chore),
        points: chore.effective_points ?? chore.points,
        timed: chore.task_type === "timed",
        mandatory: chore.mandatory === true,
        photo: chore.require_photo === true,
        pointsIcon,
        todaysCompletions,
      };
    });

    const remaining = rows.filter(r => !r.done).length;
    const tone = this._designTone(children.indexOf(child));

    // Badge strip (show_badges) — resolve the per-child badges sensor like classic.
    const badgesEntity = this._resolveBadgesEntity(child);
    const earnedBadges = (badgesEntity?.attributes?.earned) || [];
    const showBadges = this.config.show_badges !== false && earnedBadges.length > 0;
    const nextBadge = this._nextBadge(badgesEntity);
    const pendingPoints = child.pending_points || 0;
    const countdown = this.config.show_countdown !== false ? this._getMidnightCountdown() : null;

    const sectionLine = rows.length === 0 ? "" : html`
      <div class="tmd-section">
        <span>${this._getDynamicTitle()}</span>
        ${countdown ? html`<span class="tmd-countdown ${countdown.soon ? "soon" : ""}">
          <ha-icon icon="mdi:clock-outline"></ha-icon>${countdown.label}</span>` : ""}
      </div>`;

    // Pre-reader mode replaces the chore list with picture tiles. It has to be
    // handled here as well as in the classic path, or `pre_reader: true` is
    // silently ignored under every designed style — including accessible,
    // which is the one a child who needs picture tiles is most likely on.
    // The tiles keep the designed shell (header, tokens) around them.
    const body = this.config.pre_reader === true
      ? html`
        <div class="pre-reader-grid">
          ${childChores.map((chore) =>
            this._renderPreReaderTile(chore, child, pointsIcon, todaysCompletions))}
        </div>`
      : design === "playroom" ? this._designPlayroom(child, rows, remaining, tone) :
        design === "console"  ? this._designConsole(child, rows, remaining, tone) :
                                this._designCleanpro(child, rows, remaining, tone);

    return html`<ha-card class="tmd" style="--hd:${hd}">
      ${this._designHeaderFull(child, design, remaining, rows.length, tone, pendingPoints)}
      <div class="tmd-bd">
        ${attrs.vacation_active ? html`
          <div class="tmd-vacation">
            <ha-icon icon="mdi:palm-tree"></ha-icon>
            <span>${this._t("child.on_vacation")}${attrs.vacation_name ? ` · ${attrs.vacation_name}` : ""}</span>
          </div>` : ""}
        ${showBadges ? html`
          <div class="tmd-badges" @click=${() => this._openBadgesView()} title="${this._t("badges.label")}">
            <span class="lbl">${this._t("badges.label")}</span>
            ${earnedBadges.slice(0, 5).map(b => html`
              <div class="tmd-badge-mini ${this._justEarnedBadge === window.__taskmate_badge_id(b) ? "just-earned" : ""}"
                style="--t:${this._tierColor(b.tier)}">
                <ha-icon icon="${b.icon || "mdi:medal"}"></ha-icon>
              </div>`)}
            ${earnedBadges.length > 5 ? html`<span class="more">+${earnedBadges.length - 5} →</span>` : ""}
          </div>` : ""}
        ${nextBadge ? html`
          <div class="tmd-next-badge" role="button" tabindex="0"
            aria-label="${this._t("badges.next_up")} — ${nextBadge.name} ${nextBadge.label}"
            @click=${() => this._openBadgesView()}
            @keydown=${(e) => this._badgeKeydown(e)}>
            <div class="ic" style="--t:${this._tierColor(nextBadge.badge.tier)}">
              <ha-icon icon="${nextBadge.badge.icon || "mdi:trophy-outline"}"></ha-icon>
            </div>
            <div class="bd">
              <div class="top">
                <span class="lbl">${this._t("badges.next_up")}</span>
                <span class="nm">${nextBadge.name}</span>
                <span class="cnt">${nextBadge.label}</span>
              </div>
              <div class="bar" role="progressbar"
                aria-valuenow="${nextBadge.pct}" aria-valuemin="0" aria-valuemax="100">
                <i style="width:${nextBadge.pct}%;background:${this._tierColor(nextBadge.badge.tier)}"></i>
              </div>
            </div>
          </div>` : ""}
        ${sectionLine}
        ${this._renderRoulette(child, childChores, pointsIcon)}
        ${body}
        ${this._renderSwappable(allChores, child, pointsIcon)}
      </div>
      ${this._celebrating ? this._renderCelebration() : ""}
      ${this._confetti.length > 0 ? this._renderConfetti() : ""}
      ${this._renderPhotoCapture()}
      <input type="file" id="tm-photo-input" accept="image/*" capture="environment"
             style="display:none" @change="${this._onPhotoSelected}">
    </ha-card>`;
  }

  /** Designed header: avatar/title, remaining pill, pending-points chip. */
  _designHeaderFull(child, design, remaining, total, tone, pendingPoints) {
    const title = design === "console"
      ? `${(child.name || "").toUpperCase()} · ${this._t("child.todays_chores").toUpperCase()}`
      : this._t("points_display.single_title", { name: child.name });
    const sub = design === "console"
      ? (child.level ? `${this._t("child.level_label", { level: child.level })} · ${remaining} ACTIVE` : `${remaining} ACTIVE`)
      : design === "cleanpro" ? `${remaining} / ${total}`
      : `${remaining} · ${this._t("child.todays_chores")}`;
    // Avatar picker: classic makes the avatar tappable; the designed header
    // must too, or the picker only ever works on classic. Same eligibility
    // rule (allow_avatar_change + more than one unlocked option).
    const opts = child.avatar_options || [];
    const canChange = this.config.allow_avatar_change !== false
      && opts.filter(o => o.unlocked).length > 1;
    return html`
      <div class="tmd-hd">
        <div class="tmd-av-wrap ${canChange ? "avatar-clickable" : ""}"
             @click=${canChange ? () => this._toggleAvatarPicker() : null}
             title="${canChange ? this._t("child.avatar_change") : ""}">
          ${this._av(child, tone, 34)}
          ${canChange ? html`<span class="tmd-av-edit"><ha-icon icon="mdi:pencil"></ha-icon></span>` : ""}
        </div>
        <span class="tt">${title}<small>${sub}</small></span>
        ${remaining === 0 && total > 0 ? html`<span class="pill">🎉</span>` : ""}
        ${pendingPoints > 0 ? html`<span class="tmd-pending">
          <ha-icon icon="mdi:timer-sand"></ha-icon>+${pendingPoints}</span>` : ""}
        ${canChange && this._avatarPickerOpen ? this._renderAvatarPicker(child, opts) : ""}
      </div>`;
  }

  /** Shared meta tags (mandatory / photo / description) for a designed chore row. */
  _designChoreMeta(r) {
    const showDesc = this.config.show_description === true && r.chore.description;
    // A blocked chore says what unlocks it here too — the classic row carries
    // the same label, and a dimmed row with no reason is just confusing (#793).
    const depNames = r.blocked ? (r.chore._dependencyNames || []) : [];
    // Same reason label the classic row carries, so a dimmed designed row is
    // not just mysteriously grey (#803).
    const recLabel = r.recLocked
      ? (r.chore.recurrence ? r.chore.recurrence.replace(/_/g, " ") : this._t("child.recurring"))
      : "";
    // Same idea as recLabel, but for a first-come chore a sibling already
    // claimed today — name it when we know who, otherwise a generic label.
    const firstComeLabel = r.firstComeLocked
      ? (r.chore._firstComeCompletedByName
          ? this._t("child.claimed_by_another", { name: r.chore._firstComeCompletedByName })
          : this._t("child.claimed_by_another_generic"))
      : "";
    return html`
      ${r.mandatory || r.photo || depNames.length || recLabel || firstComeLabel ? html`
        <div class="tmd-meta">
          ${r.mandatory ? html`<span class="tmd-tag mandatory">⚠ ${this._t("child.mandatory")}</span>` : ""}
          ${r.photo ? html`<span class="tmd-tag photo">📷 ${this._t("child.photo_needed")}</span>` : ""}
          ${depNames.length ? html`<span class="tmd-tag">🔒 ${this._t("child.blocked_by_dependency", { chores: depNames.join(", ") })}</span>` : ""}
          ${recLabel ? html`<span class="tmd-tag">🕒 ${recLabel}</span>` : ""}
          ${firstComeLabel ? html`<span class="tmd-tag">✅ ${firstComeLabel}</span>` : ""}
        </div>` : ""}
      ${showDesc ? html`<div class="tmd-desc">${r.chore.description}</div>` : ""}`;
  }

  _designHeader(child, tt, sub, tone, pillText) {
    return html`
      <div class="tmd-hd">
        ${this._av(child, tone, 34)}
        <span class="tt">${tt}${sub ? html`<small>${sub}</small>` : ""}</span>
        ${pillText ? html`<span class="pill">${pillText}</span>` : ""}
      </div>`;
  }

  _designDoneBtn(r, label, cls) {
    return html`<button class="btn ${cls || ""}"
      ?disabled=${r.loading || r.blocked || r.recLocked || r.firstComeLocked}
      @click=${(e) => { e.stopPropagation(); r.onAct(); }}>${label}</button>`;
  }

  // Done-state chip is CLICKABLE so a completed chore can be undone (parity
  // with the classic card, where tapping a done chore undoes it). r.onAct()
  // calls _handleUndo when the chore is done.
  _designUndoChip(r, label, cls) {
    return html`<button class="chip ${cls || "done-chip"} tmd-undochip"
      ?disabled=${r.loading}
      title="${this._t("child.tap_to_undo")}"
      @click=${(e) => { e.stopPropagation(); r.onAct(); }}>${label}</button>`;
  }

  /** Render a timed chore inside designed mode, reusing the classic timed card +
   *  its full start/pause/stop/celebration/sound/cap logic. */
  _designTimed(r) {
    return this._renderTimedChoreCard(r.chore, r.child, r.pointsIcon, r.todaysCompletions, r.index);
  }

  /** Bonus subtasks for a designed chore (reuses classic renderer + handlers). */
  _designBonus(r) {
    return this._renderBonusSubtasks(r.chore, r.child, r.pointsIcon, r.todaysCompletions);
  }

  _designPlayroom(child, rows, _remaining, _tone) {
    if (rows.length === 0) return html`<div class="tmd-empty">${this._t("child.all_done")}</div>`;
    return html`<div class="tmd-chores">
      ${rows.map(r => r.timed ? this._designTimed(r) : html`
        <div class="tmd-chore ${r.done ? "done" : ""} ${r.mandatory ? "mandatory" : ""} ${r.dimmed ? "dimmed" : ""}" style="--ac:${r.tone}">
          <div class="num-badge" style="${r.done ? "--ac:var(--tmd-good)" : ""}">${r.done ? "✓" : r.index + 1}</div>
          <span class="ch-emoji">${r.glyph}</span>
          <div class="ch-mid">
            <div class="ch-name">${r.chore.name}</div>
            ${r.done ? "" : html`<div class="chip soft" style="margin-top:3px">+${r.points} ⭐</div>`}
            ${this._designChoreMeta(r)}
          </div>
          ${r.done
            ? this._designUndoChip(r, html`${this._t("child.done") || "Done"}! 🎉`)
            : this._designDoneBtn(r, r.photo ? `📷 ${this._t("child.done") || "DONE"}` : (this._t("child.done") || "DONE"), "good")}
        </div>
        ${this._designBonus(r)}`)}
    </div>`;
  }

  _designConsole(child, rows, _remaining, _tone) {
    if (rows.length === 0) return html`<div class="tmd-empty">${this._t("child.all_done")}</div>`;
    return html`<div class="grid">
      ${rows.map(r => r.timed ? this._designTimed(r) : html`
        <div class="tmd-quest ${r.done ? "done" : ""} ${r.mandatory ? "mandatory" : ""} ${r.dimmed ? "dimmed" : ""}" style="--ac:${r.tone}">
          <div class="num q-num" style="${r.done ? "color:var(--tmd-good)" : ""}">${r.done ? "✓" : String(r.index + 1).padStart(2, "0")}</div>
          <span class="q-emoji">${r.glyph}</span>
          <div class="q-mid">
            <div class="q-name">${r.chore.name}</div>
            ${r.done
              ? html`<div class="num q-cleared">CLEARED</div>`
              : html`<div class="num q-xp">+${r.points} XP</div>`}
            ${this._designChoreMeta(r)}
          </div>
          ${r.done
            ? this._designUndoChip(r, html`↩`, "q-undo")
            : this._designDoneBtn(r, r.photo ? `📷 ${this._t("child.done") || "CLAIM"}` : (this._t("child.done") || "CLAIM"))}
        </div>
        ${this._designBonus(r)}`)}
    </div>`;
  }

  _designCleanpro(child, rows, _remaining, _tone) {
    if (rows.length === 0) return html`<div class="tmd-empty">${this._t("child.all_done")}</div>`;
    return html`<div class="tmd-checklist">
      ${rows.map(r => r.timed ? this._designTimed(r) : html`
        <div class="tmd-check ${r.done ? "done" : ""} ${r.mandatory ? "mandatory" : ""} ${r.dimmed ? "dimmed" : ""}" style="--ac:${r.tone}">
          <div class="c-num" style="${r.done ? "--ac:var(--tmd-good)" : ""}">${r.done ? "✓" : r.index + 1}</div>
          <span class="c-emoji">${r.glyph}</span>
          <div class="c-mid">
            <div class="c-name">${r.chore.name}</div>
            ${this._designChoreMeta(r)}
          </div>
          ${r.done
            ? this._designUndoChip(r, this._t("child.done") || "Completed", "c-done")
            : html`<span class="chip c-pts">+${r.points}</span>
                ${this._designDoneBtn(r, r.photo ? `📷 ${this._t("child.done") || "Done"}` : (this._t("child.done") || "Done"), "sm")}`}
        </div>
        ${this._designBonus(r)}`)}
    </div>`;
  }

  _renderSwappable(allChores, child, pointsIcon) {
    // Rotation chores whose turn belongs to another child today, that this
    // child is in the pool for — the child can ask a parent to swap them in.
    if (this.config.show_swaps === false) return "";
    // "Rotation" chores = single-assignee rotating modes. Mirror the backend
    // (async_request_swap): everything except everyone/unassigned is swappable.
    // We only surface ones currently assigned to another child today that this
    // child is in the pool for.
    const swappable = (allChores || []).filter(c =>
      !["everyone", "unassigned"].includes(c.assignment_mode || "everyone") &&
      c.enabled !== false &&
      c.assignment_current_child_id &&
      c.assignment_current_child_id !== child.id &&
      (!Array.isArray(c.assigned_to) || c.assigned_to.length === 0 || c.assigned_to.includes(child.id))
    );
    if (swappable.length === 0) return "";
    if (!this._swapRequested) this._swapRequested = new Set();
    return html`
      <div class="swap-section">
        <div class="section-title">
          <ha-icon icon="mdi:swap-horizontal"></ha-icon>
          <span class="section-title-text">${this._t('child.swap_section_title') || 'Take over a chore'}</span>
        </div>
        ${swappable.map(c => {
          const key = `swap_${c.id}`;
          const loading = this._loading[key];
          const requested = this._swapRequested.has(c.id);
          return html`
            <div class="swap-row">
              <div class="swap-info">
                <div class="chore-name">${c.name}</div>
                <div class="chore-points"><ha-icon icon="${pointsIcon}"></ha-icon>+${c.effective_points ?? c.points}</div>
              </div>
              <button class="swap-btn ${requested ? 'requested' : ''}"
                      ?disabled=${loading || requested}
                      @click=${() => this._handleRequestSwap(c, child)}>
                ${requested
                  ? html`<ha-icon icon="mdi:check"></ha-icon> ${this._t('child.swap_requested') || 'Requested'}`
                  : (this._t('child.swap_request') || 'Request')}
              </button>
            </div>
          `;
        })}
      </div>
    `;
  }

  async _handleRequestSwap(chore, child) {
    const key = `swap_${chore.id}`;
    if (this._loading[key]) return;
    this._loading = { ...this._loading, [key]: true };
    this.requestUpdate();
    try {
      await this.hass.callService('taskmate', 'request_swap', {
        chore_id: chore.id,
        requester_id: child.id,
      });
      if (!this._swapRequested) this._swapRequested = new Set();
      this._swapRequested.add(chore.id);
    } catch (error) {
      console.error('Failed to request swap:', error);
    } finally {
      this._loading = { ...this._loading, [key]: false };
      this.requestUpdate();
    }
  }

  _filterAndSortChores(chores, child) {
    const childId = String(child.id || "");
    const choreOrder = child.chore_order || [];

    // Get today's day of week from sensor (set by backend) or compute client-side
    const entity = this.hass?.states?.[this.config.entity];
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity?.attributes || {};
    const todayDow = entity?.attributes?.today_day_of_week ||
      new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();

    const dueDaysMode = this.config.due_days_mode || 'hide';
    const showDueDaysOnly = this.config.show_due_days_only !== false;
    const elapsedTimeMode = this.config.elapsed_time_mode || 'dim';
    // Hide by default: the backend simply reports a dependency-blocked chore
    // as unavailable, so hiding is what matches it (#793).
    const dependencyMode = this.config.dependency_mode || 'hide';
    const recurrenceDoneMode = this.config.recurrence_done_mode || 'dim';
    const firstComeDoneMode = this.config.first_come_done_mode || 'hide';
    const allCompletionsToday = attrs.todays_completions || [];
    // Availability comes from the backend's own matrix (#803). The card cannot
    // work a recurrence window out for itself: last_completed is not exposed,
    // `recurrence` is omitted from the payload when it is the default weekly,
    // and the maths is calendar-month aware. A missing matrix (older backend,
    // or a sensor that hasn't published yet) has to read as available, or the
    // card would blank itself.
    const availability = attrs.chore_availability || {};

    // First, filter chores for this child and time category
    const filteredChores = chores.filter(chore => {
      // Check if chore is disabled (one-shot chores that are completed or expired)
      if (chore.enabled === false) return false;
      const disabledFor = chore.disabled_for || [];
      if (disabledFor.includes(childId)) return false;

      // Check time category. The card's configured filter matches as before;
      // on top of that, chores currently in their claim window (including the
      // post-period grace) and any future-period chores are let through so
      // they can render as locked previews or keep claimable during grace.
      const isLockedPreview = this._isChorePreviewLocked(chore);
      const inClaimWindow = this._isChoreInClaimWindow(chore);
      chore._isLockedPreview = isLockedPreview;
      const matchesCardFilter =
        this.config.time_category === "all" ||
        chore.time_category === this.config.time_category ||
        chore.time_category === "anytime";
      const matchesTime = matchesCardFilter || isLockedPreview || inClaimWindow;

      // Check assignment
      let assignedTo = chore.assigned_to;
      if (!Array.isArray(assignedTo)) assignedTo = [];
      const assignedToStrings = assignedTo.map(id => String(id));
      const isAssignedToAll = assignedToStrings.length === 0;
      let isAssignedToChild = isAssignedToAll || assignedToStrings.includes(childId);

      // Dynamic assignment. Rotation modes (alternating / random / balanced):
      // only the currently-active child sees the chore — the backend caches
      // today's pick in assignment_current_child_id. first_come is competitive:
      // the whole pool sees it (there is no single active child) until one
      // member wins the race. Either way, once any eligible pool member has
      // completed the chore today (e.g. a parent credited the off-rotation
      // child), the chore is done for the whole pool and should disappear for
      // everyone — including today's active child.
      const assignmentMode = chore.assignment_mode || 'everyone';
      if (assignmentMode !== 'everyone' && isAssignedToChild) {
        const activeId = chore.assignment_current_child_id ? String(chore.assignment_current_child_id) : '';
        if (assignmentMode !== 'first_come') {
          isAssignedToChild = activeId !== '' && activeId === String(childId);
        }
        if (isAssignedToChild) {
          const poolIds = assignedToStrings.length > 0
            ? assignedToStrings
            : (attrs.children || []).map(c => String(c.id));
          const poolSet = new Set(poolIds);
          // first_come is a single-winner race regardless of any configured limit.
          const dailyLimit = assignmentMode === 'first_come' ? 1 : (chore.daily_limit || 1);
          const allTodayCompletions = attrs.todays_completions || [];
          const poolCompletionsToday = allTodayCompletions.filter(
            comp => comp.chore_id === chore.id && (poolSet.has(String(comp.child_id)) || comp.child_id === "__parent__") && !comp.bonus_subtask_id
          ).length;
          if (poolCompletionsToday >= dailyLimit) {
            // Bonus sub-tasks render inside the parent card; if the active
            // child still has any pending, keep the chore visible so they
            // remain reachable. Only applies to single-active-child rotation
            // modes (mirrors the backend, which guards this on active_child_id).
            const bonusSubtasks = activeId ? (chore.bonus_subtasks || []) : [];
            const completedBonusIds = new Set(
              allTodayCompletions
                .filter(c => c.chore_id === chore.id && String(c.child_id) === activeId && c.bonus_subtask_id)
                .map(c => c.bonus_subtask_id)
            );
            const hasPendingBonus = bonusSubtasks.some(b => b && b.id && !completedBonusIds.has(b.id));
            if (!hasPendingBonus) {
              // first_come_done_mode (#first-come-visibility): by default a
              // claimed first-come chore disappears for the whole pool,
              // winner included — unchanged from prior behaviour. Under
              // dim/show it stays in the list instead: the winner's own row
              // still renders as done via _isChoreDone below, and every
              // other pool member is flagged locked so the render layer can
              // grey it out and refuse taps (the backend rejects the
              // completion anyway).
              if (assignmentMode === 'first_come' && firstComeDoneMode !== 'hide') {
                const completedByThisChild = allTodayCompletions.some(
                  (comp) => comp.chore_id === chore.id
                    && String(comp.child_id) === childId
                    && !comp.bonus_subtask_id
                );
                chore._isFirstComeLocked = !completedByThisChild;
                if (chore._isFirstComeLocked) {
                  const winningCompletion = allTodayCompletions.find(
                    (comp) => comp.chore_id === chore.id && !comp.bonus_subtask_id
                  );
                  const winner = winningCompletion
                    ? (attrs.children || []).find(c => String(c.id) === String(winningCompletion.child_id))
                    : null;
                  chore._firstComeCompletedByName = winner
                    ? winner.name
                    : (winningCompletion && winningCompletion.child_id === '__parent__' ? this._t('child.parent') : '');
                }
              } else {
                isAssignedToChild = false;
              }
            }
          }
        }
      }

      // Check visibility_entity — if set, chore is only visible if entity matches visibility_state
      // Supports exact match, numeric comparisons, and attributes
      const visibilityEntity = chore.visibility_entity || '';
      const visibilityState = chore.visibility_state || 'on';
      const visibilityOperator = chore.visibility_operator || 'equals';
      let visibilityOK = true;
      if (visibilityEntity) {
        const entityState = this.hass?.states?.[visibilityEntity];
        if (entityState) {
          const state = entityState.state;
          let matched = false;

          // Check numeric comparisons if operator is not "equals"
          if (visibilityOperator !== 'equals') {
            try {
              const threshold = parseFloat(visibilityState);
              const value = parseFloat(state);
              if (!isNaN(value) && !isNaN(threshold)) {
                if (visibilityOperator === 'gte') matched = value >= threshold;
                else if (visibilityOperator === 'lte') matched = value <= threshold;
                else if (visibilityOperator === 'gt') matched = value > threshold;
                else if (visibilityOperator === 'lt') matched = value < threshold;
                else if (visibilityOperator === 'not_equals') matched = value !== threshold;
                visibilityOK = matched;
              }
            } catch (e) {
              // Fall through to string matching
            }
          }

          if (!matched) {
            // Check state (case-insensitive matching)
            const stateMatches = state.toLowerCase() === visibilityState.toLowerCase();

            // For not_equals, we want the opposite of equality
            if (visibilityOperator === 'not_equals') {
              visibilityOK = !stateMatches;
            } else {
              // For equals and other operators, match is success
              visibilityOK = stateMatches;
            }

            if (!visibilityOK && visibilityOperator !== 'not_equals') {
              // Check attributes for a matching value (only for equals operator)
              if (entityState.attributes) {
                for (const attrValue of Object.values(entityState.attributes)) {
                  if (String(attrValue).toLowerCase() === visibilityState.toLowerCase()) {
                    visibilityOK = true;
                    break;
                  }
                }
              }
            }
          }
        } else {
          visibilityOK = true; // Entity doesn't exist, default to visible
        }
      }
      chore._visibilityEntity = visibilityEntity;
      chore._visibilityOK = visibilityOK;

      // Check due_days — if chore has due_days set and today isn't one of them
      const dueDays = chore.due_days || [];
      const hasDueDays = dueDays.length > 0;
      const isDueToday = !hasDueDays || dueDays.includes(todayDow);

      // If due_days filtering is on and mode is "hide", exclude not-due chores
      if (showDueDaysOnly && hasDueDays && !isDueToday && dueDaysMode === 'hide') {
        return false;
      }

      // Store due status on chore object for rendering
      chore._isDueToday = isDueToday;
      chore._hasDueDays = hasDueDays;

      // Chore dependencies (#793). Mirrors is_chore_available_for_child():
      // a prerequisite counts as satisfied only when this same child has an
      // approved, non-bonus completion of it today. todays_completions is
      // already scoped to today, so the date check is implicit. A looser rule
      // here would unlock a chore the backend then refuses to complete.
      const dependsOn = Array.isArray(chore.depends_on) ? chore.depends_on : [];
      chore._isDependencyBlocked = dependsOn.length > 0 && !dependsOn.every(
        (depId) => allCompletionsToday.some(
          (comp) => comp.chore_id === depId
            && String(comp.child_id) === childId
            && comp.approved
            && !comp.bonus_subtask_id
        )
      );
      chore._dependencyNames = chore._isDependencyBlocked
        ? dependsOn
            .map((depId) => (chores.find((c) => c.id === depId) || {}).name)
            .filter(Boolean)
        : [];
      if (chore._isDependencyBlocked && dependencyMode === 'hide') return false;

      // Recurring chores in their cooldown window (#803). Both of these are
      // read by the render path, which until now found them undefined.
      chore._isRecurring = (chore.schedule_mode || 'specific_days') === 'recurring';
      const availableNow = (availability[chore.id] || {})[childId] !== false;
      // Completing a recurring chore makes it unavailable at once, so hiding on
      // availability alone would vanish it the instant it is ticked — no done
      // state, no way to undo. The mode is about the days *after* that.
      const completedToday = allCompletionsToday.some(
        (comp) => comp.chore_id === chore.id
          && (String(comp.child_id) === childId || comp.child_id === '__parent__')
          && !comp.bonus_subtask_id
      );
      chore._isRecurrenceLocked = chore._isRecurring && !availableNow && !completedToday;
      if (chore._isRecurrenceLocked && recurrenceDoneMode === 'hide') return false;

      // Mark whether this chore's time period has elapsed (grace-aware).
      chore._isTimeElapsed = this._isTimePeriodElapsed(chore);

      // If elapsed_time_mode is "hide", exclude elapsed-and-incomplete chores at filter stage.
      // Completed chores are handled at render time so we can't check here — use a sentinel.
      if (elapsedTimeMode === 'hide' && chore._isTimeElapsed) {
        return false;
      }

      // Only return chore if visibility entity allows it
      return matchesTime && isAssignedToChild && visibilityOK;
    });

    // Debug: Log the filtered results

    // If no custom order is set, return filtered chores as-is
    if (choreOrder.length === 0) {
      return filteredChores;
    }

    // Sort by the child's custom chore order
    // Chores in the order list appear first, in their specified order
    // Chores not in the order list appear after, in their default order
    return filteredChores.sort((a, b) => {
      const indexA = choreOrder.indexOf(a.id);
      const indexB = choreOrder.indexOf(b.id);

      // If both are in the order list, sort by their position
      if (indexA !== -1 && indexB !== -1) {
        return indexA - indexB;
      }

      // If only one is in the order list, it comes first
      if (indexA !== -1) return -1;
      if (indexB !== -1) return 1;

      // If neither is in the order list, maintain original order
      return 0;
    });
  }

  _getTimeCategoryIcon(category) {
    const period = this._getTimePeriods().find(p => p.id === category);
    if (period) return period.icon;
    const icons = {
      morning: "mdi:weather-sunset-up",
      afternoon: "mdi:weather-sunny",
      evening: "mdi:weather-sunset-down",
      night: "mdi:weather-night",
      anytime: "mdi:clock-outline",
      all: "mdi:clock-outline",
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
      all: 'common.all',
    };
    return keyMap[category] ? this._t(keyMap[category]) : category;
  }

  _getDynamicTitle() {
    const category = this.config.time_category;
    const period = this._getTimePeriods().find(p => p.id === category);
    if (period && period.label) return period.label;
    const keyMap = {
      morning: 'child.morning_chores',
      afternoon: 'child.afternoon_chores',
      evening: 'child.evening_chores',
      night: 'child.night_chores',
      anytime: 'child.todays_chores',
      all: 'child.todays_chores',
    };
    return keyMap[category] ? this._t(keyMap[category]) : this._t('child.todays_chores');
  }

  _getTimezone() {
    // Get timezone from Home Assistant config, fallback to browser timezone
    return this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  }

  // Ordered list of user-defined periods: [{id, label, icon, start, end}]
  // with start/end as decimal hours. Falls back to the legacy fixed four
  // when the integration hasn't published time_periods yet.
  _getTimePeriods() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    if (Array.isArray(attrs.time_periods) && attrs.time_periods.length) {
      return attrs.time_periods
        .filter(p => p && p.id)
        .map(p => ({
          id: p.id,
          label: p.label || "",
          icon: p.icon || "mdi:clock-outline",
          start: this._parseHHMM(p.start, 0, 0),
          end: this._parseHHMM(p.end, 23, 59),
        }))
        .sort((a, b) => a.start - b.start);
    }
    const tb = attrs.time_boundaries || {};
    return [
      { id: "morning",   label: "", icon: "mdi:weather-sunset-up",   start: this._parseHHMM(tb.morning_start, 6, 0),    end: this._parseHHMM(tb.morning_end, 12, 0) },
      { id: "afternoon", label: "", icon: "mdi:weather-sunny",       start: this._parseHHMM(tb.afternoon_start, 12, 0), end: this._parseHHMM(tb.afternoon_end, 17, 0) },
      { id: "evening",   label: "", icon: "mdi:weather-sunset-down", start: this._parseHHMM(tb.evening_start, 17, 0),   end: this._parseHHMM(tb.evening_end, 21, 0) },
      { id: "night",     label: "", icon: "mdi:weather-night",       start: this._parseHHMM(tb.night_start, 21, 0),     end: this._parseHHMM(tb.night_end, 23, 59) },
    ];
  }

  _getTimeBoundaries() {
    const boundaries = {};
    for (const p of this._getTimePeriods()) boundaries[p.id] = [p.start, p.end];
    return boundaries;
  }

  _parseHHMM(str, defH, defM) {
    if (!str) return defH + defM / 60;
    const [h, m] = str.split(':').map(Number);
    if (isNaN(h)) return defH + defM / 60;
    return h + (m || 0) / 60;
  }

  _getCurrentTimePeriod() {
    if (this.config.debug_time_period) return this.config.debug_time_period;
    const tz = this._getTimezone();
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hour: 'numeric', minute: 'numeric', hour12: false,
    }).formatToParts(new Date());
    let hour = parseInt(parts.find(p => p.type === 'hour')?.value, 10);
    const minute = parseInt(parts.find(p => p.type === 'minute')?.value, 10) || 0;
    if (isNaN(hour)) hour = 0;
    if (hour === 24) hour = 0;
    const now = hour + minute / 60;
    const periods = this._getTimePeriods();
    for (let i = periods.length - 1; i >= 0; i--) {
      if (now >= periods[i].start) return periods[i].id;
    }
    // Before the first period starts (e.g. 02:00) we treat it as the first
    // period of the day, matching the legacy pre-morning behaviour.
    return periods[0]?.id || 'morning';
  }

  _getPeriodHours(period) {
    const b = this._getTimeBoundaries();
    const range = b[period];
    if (!range) return null;
    return [range[0], range[1]];
  }

  // Current {hour, minute} in HA timezone. Honours debug_time_period by
  // pinning to the period's start so preview/grace logic remains deterministic.
  _getCurrentHourMinute() {
    if (this.config.debug_time_period) {
      const hours = this._getPeriodHours(this.config.debug_time_period);
      if (hours) return { hour: Math.floor(hours[0]), minute: Math.round((hours[0] % 1) * 60) };
    }
    const tz = this._getTimezone();
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hour: 'numeric', minute: 'numeric', hour12: false,
    }).formatToParts(new Date());
    let hour = parseInt(parts.find(p => p.type === 'hour')?.value, 10);
    const minute = parseInt(parts.find(p => p.type === 'minute')?.value, 10) || 0;
    if (isNaN(hour)) hour = 0;
    if (hour === 24) hour = 0;
    return { hour, minute };
  }

  // True iff the chore's period is strictly later than the current period
  // (any future period today, not just the immediately next one). Never true
  // for "anytime"; no cross-midnight preview.
  _isChorePreviewLocked(chore) {
    const cat = chore?.time_category;
    if (!cat || cat === 'anytime') return false;
    const order = this._getTimePeriods().map(p => p.id);
    const choreIndex = order.indexOf(cat);
    const currentIndex = order.indexOf(this._getCurrentTimePeriod());
    if (choreIndex < 0 || currentIndex < 0) return false;
    return choreIndex > currentIndex;
  }

  // True iff the current HA-local time is within the chore's claim window,
  // i.e. between period start and (period end + claim_allowance_minutes),
  // capped at midnight for night-period chores.
  _isChoreInClaimWindow(chore) {
    const cat = chore?.time_category;
    if (!cat) return false;
    if (cat === 'anytime') return true;
    const hours = this._getPeriodHours(cat);
    if (!hours) return false;
    const [startH, endH] = hours;
    const allowance = Math.max(0, parseInt(chore.claim_allowance_minutes, 10) || 0);
    const startMinutes = startH * 60;
    const endMinutes = Math.min(24 * 60, endH * 60 + allowance);
    const { hour, minute } = this._getCurrentHourMinute();
    const nowMinutes = hour * 60 + minute;
    return nowMinutes >= startMinutes && nowMinutes < endMinutes;
  }

  // Returns true when the chore's time_category period has passed without completion.
  // "anytime" chores never elapse. A chore still inside its claim grace window is
  // not considered elapsed. Already-completed chores are handled at the call site.
  _isTimePeriodElapsed(choreOrCategory) {
    const cat = typeof choreOrCategory === 'string'
      ? choreOrCategory
      : choreOrCategory?.time_category;
    if (!cat || cat === 'anytime') return false;
    const order = {};
    this._getTimePeriods().forEach((p, i) => { order[p.id] = i; });
    const choreIndex = order[cat];
    if (choreIndex === undefined) return false;
    const currentIndex = order[this._getCurrentTimePeriod()];
    if (currentIndex === undefined || currentIndex <= choreIndex) return false;
    if (typeof choreOrCategory === 'object' && this._isChoreInClaimWindow(choreOrCategory)) {
      return false;
    }
    return true;
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

  _isToday(date) {
    const now = new Date();
    const todayParts = this._getDatePartsInTimezone(now);
    const dateParts = this._getDatePartsInTimezone(date);

    return (
      dateParts.year === todayParts.year &&
      dateParts.month === todayParts.month &&
      dateParts.day === todayParts.day
    );
  }

  _filterCompletionsForToday(completions) {
    // Filter completions to only include those completed today (in HA timezone)
    return completions.filter(comp => {
      if (!comp.completed_at) return false;
      const completedDate = new Date(comp.completed_at);
      return this._isToday(completedDate);
    });
  }

  _getMidnightCountdown() {
    const tz = this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    const now = new Date();
    // Get tomorrow midnight in HA timezone
    const tomorrow = new Date(now.toLocaleDateString("en-CA", { timeZone: tz }) + "T00:00:00");
    tomorrow.setDate(tomorrow.getDate() + 1);
    const diffMs = tomorrow - now;
    if (diffMs <= 0) return null;

    const totalMins = Math.floor(diffMs / 60000);
    const hours = Math.floor(totalMins / 60);
    const mins = totalMins % 60;

    const soon = totalMins <= 60; // less than 1 hour
    let label;
    if (hours > 0) {
      label = this._t('child.chores_reset_hours_mins', { hours, mins });
    } else if (mins > 0) {
      label = this._t('child.chores_reset_mins', { mins });
    } else {
      label = this._t('child.chores_resetting_soon');
    }
    return { label, soon };
  }

  _renderEmptyState() {
    return html`
      <div class="empty-state">
        <ha-icon icon="mdi:party-popper"></ha-icon>
        <div class="message">${this._t('child.all_done')}</div>
        <div class="submessage">${this._t('child.no_chores_right_now')}</div>
      </div>
    `;
  }

  /**
   * Countdown badge for a reactive chore (#674) — "empty the washing machine
   * within 30 minutes". Reads the deadline fresh on every render, so it ticks
   * down with the coordinator's updates. Hidden once the chore is done.
   */
  _renderDeadlineBadge(chore, isCompletedForToday) {
    if (!chore.deadline_at || isCompletedForToday) return '';
    const deadline = new Date(chore.deadline_at);
    if (Number.isNaN(deadline.getTime())) return '';
    const msLeft = deadline.getTime() - Date.now();
    if (msLeft <= 0) return '';

    const minsLeft = Math.ceil(msLeft / 60000);
    const label = minsLeft >= 60
      ? this._t('child.deadline_hours', { hours: Math.floor(minsLeft / 60), mins: minsLeft % 60 })
      : this._t('child.deadline_minutes', { mins: minsLeft });
    // Under five minutes is the point at which it's worth shouting about.
    const urgent = minsLeft <= 5;
    const bonus = chore.speed_bonus_points || 0;

    return html`
      <span class="deadline-badge ${urgent ? 'deadline-urgent' : ''}"
            title="${this._t('child.deadline_title')}">
        ⏱ ${label}${bonus ? html` <span class="deadline-bonus">+${bonus}</span>` : ''}
      </span>
    `;
  }

  /**
   * Chore roulette (#677) — an opt-in nudge for the child who has stalled.
   * Only renders when the parent enabled it in settings AND the card opts in,
   * so an existing dashboard never sprouts a new button unasked.
   */
  _renderRoulette(child, childChores, pointsIcon) {
    if (this.config.show_roulette !== true) return '';
    const roulette = child.roulette;
    if (!roulette) return '';  // switched off in settings

    const picked = roulette.chore_id
      ? childChores.find(c => String(c.id) === String(roulette.chore_id))
      : null;
    const spinsLeft = roulette.spins_left ?? 0;
    const multiplier = roulette.multiplier || 2;
    const spinning = this._spinning === child.id;

    return html`
      <div class="roulette">
        ${picked ? html`
          <div class="roulette-result">
            <span class="roulette-mult">×${multiplier}</span>
            <span class="roulette-name">${picked.name}</span>
            <span class="roulette-worth">
              <ha-icon icon="${pointsIcon}"></ha-icon>
              ${Math.round((picked.effective_points ?? picked.points ?? 0) * multiplier)}
            </span>
          </div>
        ` : ''}
        ${spinsLeft > 0 ? html`
          <button class="roulette-btn ${spinning ? 'is-spinning' : ''}"
                  ?disabled=${spinning || childChores.length === 0}
                  @click=${() => this._spinRoulette(child)}>
            <ha-icon icon="mdi:dice-multiple"></ha-icon>
            ${picked
              ? this._t('child.roulette_respin', { count: spinsLeft })
              : this._t('child.roulette_spin', { multiplier })}
          </button>
        ` : html`
          <div class="roulette-spent">${this._t('child.roulette_no_spins')}</div>
        `}
      </div>
    `;
  }

  async _spinRoulette(child) {
    if (this._spinning) return;
    this._spinning = child.id;
    this.requestUpdate();
    try {
      await this.hass.callService('taskmate', 'spin_roulette', { child_id: child.id });
    } catch (err) {
      // "No spins left" / "Nothing left to spin for" arrive here as
      // ServiceValidationError — show them rather than failing silently.
      this.dispatchEvent(new CustomEvent('hass-notification', {
        detail: { message: String(err?.message || err) }, bubbles: true, composed: true,
      }));
    } finally {
      this._spinning = null;
      this.requestUpdate();
    }
  }

  /**
   * Pre-reader mode (#683): a picture-only tile for children who can't read
   * yet. No chore name, no numbers — a big icon, a row of stars for the
   * points, and a huge tick when it's done.
   *
   * `pre_reader_points` (#795) swaps the stars for the value itself, for
   * families whose children can already read a number and who found the
   * rounded star count contradicted the balance on the rest of the dashboard.
   */
  _renderPreReaderTile(chore, child, pointsIcon, todaysCompletions = []) {
    const dailyLimit = chore.daily_limit || 1;
    // Counted the same way the standard row does: pending completions hold a
    // place too, and a parent completing on behalf lands under "__parent__".
    const childCompletionsToday = todaysCompletions.filter(
      (comp) => comp.chore_id === chore.id
        && (comp.child_id === child.id || comp.child_id === "__parent__")
        && !comp.bonus_subtask_id
    );
    const isDone = childCompletionsToday.length >= dailyLimit;
    const isLoading = this._loading[chore.id];
    const available = chore._isAvailableForChild !== false && !chore._isLockedPreview
      && !chore._isDependencyBlocked;

    // Stars, not digits: a 4-year-old can count pictures, not read "+3".
    // The count is deliberately lossy — it rounds and clamps to 1..5 — which
    // is why showing the number instead is opt-in rather than a second row.
    const points = chore.effective_points ?? chore.points ?? 0;
    const stars = Math.max(1, Math.min(5, Math.round(points / 2) || 1));
    const showPoints = this.config.pre_reader_points === true;

    const v = window.__taskmate_chore_visual(chore);
    const icon = (v.kind === "icon" ? v.icon : "")
      || this._getTimeCategoryIcon(chore.time_category)
      || 'mdi:checkbox-marked-circle-outline';

    return html`
      <button
        class="pre-tile ${isDone ? 'done' : ''} ${isLoading ? 'loading' : ''} ${available ? '' : 'locked'}"
        ?disabled=${isLoading || !available}
        aria-label="${chore.name}"
        title="${chore.name}"
        @click=${() => (isDone
          ? this._handleUndo(chore, child, childCompletionsToday)
          : this._handleComplete(chore, child))}
      >
        <div class="pre-tile-icon">
          ${v.kind === "image"
            ? html`<img src="${v.url}" alt="" loading="lazy">`
            : html`<ha-icon icon="${icon}"></ha-icon>`}
        </div>
        ${isDone ? html`<div class="pre-tile-tick"><ha-icon icon="mdi:check-bold"></ha-icon></div>` : ''}
        ${showPoints
          ? html`
            <div class="pre-tile-points">
              <ha-icon icon="${pointsIcon}"></ha-icon>+${points}
            </div>`
          : html`
            <div class="pre-tile-stars">
              ${Array.from({ length: stars }, () => html`<ha-icon icon="mdi:star"></ha-icon>`)}
            </div>`}
        ${this.config.pre_reader_labels === true
          ? html`<div class="pre-tile-label">${chore.name}</div>` : ''}
      </button>
    `;
  }

  /** The coloured badge at the head of a chore row.
   *
   * A chore's picture takes the digit's place when one is set (#745) — the
   * number is only positional, whereas the icon is what a child actually
   * recognises. Chores with no picture keep their number, which is every
   * chore that predates the field. Shared by the standard and timed rows so
   * a picture can't work on one and be invisible on the other.
   */
  _choreNumberBadge(chore, colorClass, choreNumber) {
    const v = window.__taskmate_chore_visual(chore);
    return html`
      <div class="chore-number-badge ${colorClass}">
        ${v.kind === "image"
          ? html`<img class="chore-badge-img" src="${v.url}" alt="" loading="lazy">`
          : v.kind === "icon"
            ? html`<ha-icon icon="${v.icon}"></ha-icon>`
            : choreNumber}
      </div>`;
  }

  _renderChoreCard(chore, child, pointsIcon, todaysCompletions = [], choreIndex = 0) {
    const isLoading = this._loading[chore.id];
    const isCelebrating = this._celebrating === chore.id;

    // Check how many times this chore was completed today by this child
    // Both pending (awaiting approval) AND approved completions count toward the daily limit.
    // Exception: async_parent_complete_chore's child_id="__parent__" dismisses a
    // first_come chore for the whole pool with zero points and no winner — it must
    // not read as THIS child's own done state (green row + live undo chip) for
    // anyone, or every sibling gets a completed chip for a chore none of them did.
    // It should fall through to the locked/dimmed row instead (chore._isFirstComeLocked
    // below). Every other assignment mode keeps the existing __parent__-counts-for-
    // everyone behavior, which is intentional there.
    const isFirstCome = chore.assignment_mode === "first_come";
    const childCompletionsToday = todaysCompletions.filter(
      (comp) => comp.chore_id === chore.id && (comp.child_id === child.id || (!isFirstCome && comp.child_id === "__parent__")) && !comp.bonus_subtask_id
    );
    let completionsToday = childCompletionsToday.length;
    const dailyLimit = chore.daily_limit || 1;

    // Check for optimistic completions (chores just completed but not yet confirmed by HA)
    const optimisticKey = `${chore.id}_${child.id}`;
    const optimisticData = this._optimisticCompletions && this._optimisticCompletions[optimisticKey];
    const hasOptimisticCompletion = !!optimisticData;

    // If we have an optimistic completion, always count it toward the limit
    // This is defensive - we'd rather show "completed" incorrectly than allow double-completions
    // The optimistic completion will be cleaned up once we verify the server state reflects it
    if (hasOptimisticCompletion) {

      // Get timestamps from actual completions for this chore/child today
      const actualTimestamps = childCompletionsToday.map(comp =>
        comp.completed_at ? new Date(comp.completed_at).getTime() : 0
      );

      // Count how many of our optimistic completions are NOT yet reflected in the data
      // An optimistic completion is "reflected" if there's an actual completion within 2 seconds of it
      const optimisticTimestamps = optimisticData.timestamps || [optimisticData.timestamp || Date.now()];
      let unreflectedOptimistic = 0;
      for (const optTs of optimisticTimestamps) {
        const isReflected = actualTimestamps.some(actTs => Math.abs(actTs - optTs) < 2000);
        if (!isReflected) {
          unreflectedOptimistic += 1;
        }
      }

      completionsToday += unreflectedOptimistic;
    }

    const isCompletedForToday = completionsToday >= dailyLimit;


    // Chore number (1-indexed for display) and color class (cycle through 8 colors)
    const choreNumber = choreIndex + 1;
    const colorClass = `color-${choreIndex % 8}`;

    // Click handler for the entire row
    const notDueToday = chore._hasDueDays && !chore._isDueToday && this.config.due_days_mode === 'dim';
    const recurrenceDoneMode = this.config.recurrence_done_mode || 'dim';
    // The tap is refused whenever the chore is locked: async_complete_chore
    // no-ops a recurring chore inside its window, so a clickable row under
    // `show` would just swallow the tap (#805). Only the dim STYLING is
    // mode-gated. Same split dependency_mode uses.
    const recurrenceLocked = !!chore._isRecurrenceLocked && !isCompletedForToday;
    const notAvailableRecurrence = recurrenceLocked && recurrenceDoneMode === 'dim';
    // First-come chore claimed by a sibling today (first_come_done_mode
    // dim/show — hide is filtered upstream). Never true on the winner's own
    // row: _isFirstComeLocked is only set for the other pool members.
    const firstComeDoneMode = this.config.first_come_done_mode || 'hide';
    const firstComeLocked = !!chore._isFirstComeLocked && !isCompletedForToday;
    const notAvailableFirstCome = firstComeLocked && firstComeDoneMode === 'dim';
    // Elapsed: only dim incomplete chores — completed ones keep their green "done" style
    const elapsedTimeMode = this.config.elapsed_time_mode || 'dim';
    const timeElapsed = chore._isTimeElapsed && !isCompletedForToday && elapsedTimeMode === 'dim';
    const isLockedPreview = !!chore._isLockedPreview && !isCompletedForToday;
    // Under dim/show the blocked chore is still on screen, so the tap has to be
    // refused here — the backend would reject the completion anyway (#793).
    // Only `dim` greys it out; `show` is meant to look untouched.
    const depBlocked = !!chore._isDependencyBlocked && !isCompletedForToday;
    const depDimmed = depBlocked && (this.config.dependency_mode || 'hide') === 'dim';
    const periodStartHour = isLockedPreview
      ? (this._getPeriodHours(chore.time_category)?.[0] ?? null)
      : null;
    const lockedUntilLabel = isLockedPreview && periodStartHour !== null
      ? this._t('child.chore_locked_until', { time: `${String(Math.floor(periodStartHour)).padStart(2, '0')}:${String(Math.round((periodStartHour % 1) * 60)).padStart(2, '0')}` })
      : '';
    const handleRowClick = () => {
      if (isLoading) return;
      if (notDueToday) return;  // Dim mode — not interactive
      if (recurrenceLocked) return;  // Recurrence window not open — not interactive
      if (isLockedPreview) return;  // Next-period preview — not yet claimable
      if (depBlocked) return;  // Prerequisite chore not approved yet
      if (timeElapsed) return;  // Time period passed — not interactive
      if (firstComeLocked) return;  // Claimed by another child today — not interactive
      if (isCompletedForToday) {
        this._handleUndo(chore, child, childCompletionsToday);
      } else {
        this._handleComplete(chore, child);
      }
    };
    const isInteractive = !(isLoading || notDueToday || recurrenceLocked || isLockedPreview || depBlocked || timeElapsed || firstComeLocked);
    const handleRowKeyDown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleRowClick();
      }
    };

    const titleText = isLockedPreview
      ? (lockedUntilLabel || this._t('child.chore_locked_until_generic'))
      : depBlocked
        ? this._t('child.blocked_by_dependency', { chores: (chore._dependencyNames || []).join(', ') })
      : notDueToday
        ? this._t('child.not_scheduled_for_today')
        : timeElapsed
          ? this._t('child.time_has_passed')
          : firstComeLocked
            ? (chore._firstComeCompletedByName
                ? this._t('child.claimed_by_another', { name: chore._firstComeCompletedByName })
                : this._t('child.claimed_by_another_generic'))
          : isCompletedForToday
            ? this._t('child.click_to_undo')
            : this._t('child.click_to_complete');

    return html`
      <div
        class="chore-card ${chore.mandatory ? "mandatory" : ""} ${isLoading ? "loading" : ""} ${isCelebrating ? "celebrating" : ""} ${isCompletedForToday ? "completed" : ""} ${notDueToday ? "not-due-today" : ""} ${notAvailableRecurrence ? "recurrence-unavailable" : ""} ${notAvailableFirstCome ? "first-come-unavailable" : ""} ${timeElapsed ? "time-elapsed" : ""} ${isLockedPreview ? "chore-locked" : ""} ${depDimmed ? "dependency-blocked" : ""}"
        role="button"
        tabindex="${isInteractive ? '0' : '-1'}"
        aria-disabled="${isInteractive ? 'false' : 'true'}"
        aria-label="${chore.name}"
        @click="${handleRowClick}"
        @keydown="${handleRowKeyDown}"
        title="${titleText}"
      >
        <div class="chore-info">
          <div class="chore-number-wrapper">
            ${this._choreNumberBadge(chore, colorClass, choreNumber)}
          </div>
          <div class="chore-details">
            <div class="chore-name">${chore.name}${chore.mandatory ? html`<span class="mandatory-badge">⚠ ${this._t('child.mandatory')}</span>` : ''}</div>
            ${this._renderDeadlineBadge(chore, isCompletedForToday)}
            ${chore.difficulty ? html`<span class="difficulty-badge difficulty-${chore.difficulty}">${this._t('child.difficulty_' + chore.difficulty) || chore.difficulty}</span>` : ''}
            ${this.config.show_description && chore.description ? html`
              <div class="chore-description">${chore.description}</div>
            ` : ''}
            ${depBlocked && (chore._dependencyNames || []).length ? html`
              <div class="dependency-label">
                <ha-icon icon="mdi:lock-outline"></ha-icon>
                ${this._t('child.blocked_by_dependency', { chores: chore._dependencyNames.join(', ') })}
              </div>
            ` : ''}
            ${chore._isRecurrenceLocked ? html`
              <div class="recurrence-label">
                <ha-icon icon="mdi:clock-outline"></ha-icon>
                ${chore.recurrence ? chore.recurrence.replace(/_/g, ' ') : this._t('child.recurring')}
              </div>
            ` : ''}
            ${firstComeLocked ? html`
              <div class="first-come-label">
                <ha-icon icon="mdi:check-circle-outline"></ha-icon>
                ${chore._firstComeCompletedByName
                  ? this._t('child.claimed_by_another', { name: chore._firstComeCompletedByName })
                  : this._t('child.claimed_by_another_generic')}
              </div>
            ` : ''}
            <div class="chore-points">
              <ha-icon icon="${pointsIcon}"></ha-icon>
              +${chore.effective_points ?? chore.points}
              ${dailyLimit > 1 ? html`<span style="font-size: 0.8em; opacity: 0.7;">(${completionsToday}/${dailyLimit})</span>` : ''}
            </div>
            ${chore.require_photo && !isCompletedForToday ? html`
              <div class="recurrence-label">
                <span class="photo-badge">📷 ${this._t('child.photo_needed')}</span>
              </div>
            ` : ''}
          </div>
        </div>
        <div class="chore-checkbox">
          ${isLoading
            ? html`<ha-icon icon="mdi:loading" style="animation: spin 1s linear infinite; color: var(--fun-purple);"></ha-icon>`
            : isLockedPreview
              ? html`<ha-icon icon="mdi:lock-clock" class="chore-lock-icon"></ha-icon>`
              : html`<ha-icon icon="mdi:check-bold"></ha-icon>`}
        </div>
      </div>
    `;
  }

  _renderTimedChoreCard(chore, child, pointsIcon, todaysCompletions, choreIndex) {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity))
      || this.hass?.states?.[this.config.entity]?.attributes || {};
    const timedSessions = attrs.active_timed_sessions || [];
    const session = timedSessions.find(s => s.chore_id === chore.id && s.child_id === child.id);
    const state = session ? session.state : 'idle';
    const isLoading = this._loading[`timed_${chore.id}`];

    const colorClass = `color-${choreIndex % 8}`;
    const choreNumber = choreIndex + 1;
    // A blocked timed chore must not be startable under dim/show (#793).
    // Pause/stop stay live so a session already running can still be ended.
    const depBlocked = !!chore._isDependencyBlocked;

    // Calculate elapsed seconds
    let elapsed = session ? (session.total_seconds_today || 0) : 0;
    if (state === 'running' && session && session.current_segment_start) {
      const startMs = new Date(session.current_segment_start).getTime();
      const nowMs = Date.now();
      elapsed += Math.max(0, Math.floor((nowMs - startMs) / 1000));
    }

    // Calculate earned points
    const rateSeconds = (chore.timed_rate_minutes || 5) * 60;
    const ratePoints = chore.timed_rate_points || 10;
    const earnedPoints = Math.floor(elapsed / rateSeconds) * ratePoints;

    // Format time as MM:SS
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    const timeStr = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;

    // Rate display
    const rateLabel = chore.timed_rate_minutes === 1
      ? `${ratePoints} ${this._t('child.pts_per_min')}`
      : `${ratePoints} ${this._t('child.pts_per_n_min', {count: chore.timed_rate_minutes})}`;

    // Daily cap info
    const maxMin = chore.timed_max_daily_minutes || 0;
    const usedMin = Math.floor(elapsed / 60);
    const capPct = maxMin > 0 ? Math.min(100, (elapsed / (maxMin * 60)) * 100) : 0;
    const nearCap = maxMin > 0 && capPct >= 85;

    const handleStart = (e) => {
      if (depBlocked) { e.stopPropagation(); return; }
      e.stopPropagation();
      if (isLoading) return;
      this._loading = { ...this._loading, [`timed_${chore.id}`]: true };
      this.hass.callService('taskmate', 'start_timed_task', {
        chore_id: chore.id, child_id: child.id
      }).then(() => {
        this._loading = { ...this._loading, [`timed_${chore.id}`]: false };
      }).catch(() => {
        this._loading = { ...this._loading, [`timed_${chore.id}`]: false };
      });
    };

    const handlePause = (e) => {
      e.stopPropagation();
      if (isLoading) return;
      this._loading = { ...this._loading, [`timed_${chore.id}`]: true };
      this.hass.callService('taskmate', 'pause_timed_task', {
        chore_id: chore.id, child_id: child.id
      }).then(() => {
        this._loading = { ...this._loading, [`timed_${chore.id}`]: false };
      }).catch(() => {
        this._loading = { ...this._loading, [`timed_${chore.id}`]: false };
      });
    };

    const handleStop = (e) => {
      e.stopPropagation();
      if (isLoading) return;
      this._celebrationPoints = earnedPoints;
      this._loading = { ...this._loading, [`timed_${chore.id}`]: true };
      this.hass.callService('taskmate', 'stop_timed_task', {
        chore_id: chore.id, child_id: child.id
      }).then(() => {
        this._loading = { ...this._loading, [`timed_${chore.id}`]: false };
        const sound = chore.completion_sound || this.config.default_sound || 'coin';
        this._playSound(sound);
        this._celebrating = chore.id;
        this._launchConfetti();
        setTimeout(() => { this._celebrating = null; this._celebrationPoints = null; this.requestUpdate(); }, 2000);
      }).catch(() => {
        this._loading = { ...this._loading, [`timed_${chore.id}`]: false };
      });
    };

    return html`
      <div class="timed-chore-card ${state} ${isLoading ? 'loading' : ''}">
        <div class="timed-top-row">
          <div class="chore-number-wrapper">
            ${this._choreNumberBadge(chore, colorClass, choreNumber)}
          </div>
          <div class="chore-details">
            <div class="chore-name">${chore.name}</div>
          </div>
          <div class="timed-rate">${rateLabel}</div>
        </div>

        ${state !== 'idle' ? html`
          <div class="timer-display">
            ${state === 'running' ? html`<div class="recording-dot"></div>` : ''}
            ${state === 'paused' ? html`<div class="paused-badge">${this._t('child.paused') || 'PAUSED'}</div>` : ''}
            <div class="timer-counter ${state}">${timeStr}</div>
            <div class="timer-points-live">
              <ha-icon icon="${pointsIcon}"></ha-icon>
              ${earnedPoints}
            </div>
          </div>
        ` : ''}

        <div class="timer-actions">
          ${state === 'idle' ? html`
            <button class="timer-btn start" @click="${handleStart}" ?disabled="${isLoading || depBlocked}">
              <span class="btn-icon">&#9654;</span>
              ${this._t('child.start') || 'START'}
            </button>
          ` : ''}
          ${state === 'running' ? html`
            <button class="timer-btn pause" @click="${handlePause}" ?disabled="${isLoading}">
              <span class="btn-icon">&#9208;</span>
              ${this._t('child.pause') || 'PAUSE'}
            </button>
            <button class="timer-btn stop" @click="${handleStop}" ?disabled="${isLoading}">
              <span class="btn-icon">&#9209;</span>
              ${this._t('child.done') || 'DONE'}
            </button>
          ` : ''}
          ${state === 'paused' ? html`
            <button class="timer-btn resume" @click="${handleStart}" ?disabled="${isLoading || depBlocked}">
              <span class="btn-icon">&#9654;</span>
              ${this._t('child.resume') || 'RESUME'}
            </button>
            <button class="timer-btn stop" @click="${handleStop}" ?disabled="${isLoading}">
              <span class="btn-icon">&#9209;</span>
              ${this._t('child.done') || 'DONE'}
            </button>
          ` : ''}
        </div>

        ${maxMin > 0 ? html`
          <div class="daily-cap-bar">
            <span class="cap-label ${nearCap ? 'near-cap' : ''}">${this._t('child.timed_cap_label', {used: usedMin, max: maxMin})}</span>
            <div class="cap-track">
              <div class="cap-fill ${nearCap ? 'warning' : ''}" style="width: ${capPct}%"></div>
            </div>
          </div>
        ` : ''}
      </div>
    `;
  }

  _renderBonusSubtasks(chore, child, pointsIcon, todaysCompletions) {
    const subtasks = chore.bonus_subtasks;
    if (!subtasks || subtasks.length === 0) return '';

    // Check if parent chore is completed today (including optimistic)
    const parentCompletions = todaysCompletions.filter(
      c => c.chore_id === chore.id && (c.child_id === child.id || c.child_id === "__parent__") && !c.bonus_subtask_id
    );
    const optimisticKey = `${chore.id}_${child.id}`;
    const hasOptimistic = this._optimisticCompletions && this._optimisticCompletions[optimisticKey];
    const parentDone = parentCompletions.length > 0 || hasOptimistic;

    if (!parentDone) return '';

    return html`${subtasks.map(subtask => {
      const bonusKey = `${chore.id}_bonus_${subtask.id}_${child.id}`;
      const bonusOptimistic = this._optimisticCompletions && this._optimisticCompletions[bonusKey];
      const bonusDone = todaysCompletions.some(
        c => c.chore_id === chore.id && c.child_id === child.id && c.bonus_subtask_id === subtask.id
      ) || bonusOptimistic;
      const isLoading = this._loading[bonusKey];

      const handleClick = () => {
        if (isLoading) return;
        if (bonusDone) {
          this._handleUndoBonusSubtask(chore, subtask, child, todaysCompletions);
        } else {
          this._handleCompleteBonusSubtask(chore, subtask, child);
        }
      };

      return html`
        <div
          class="chore-card bonus-subtask ${bonusDone ? 'completed' : ''} ${isLoading ? 'loading' : ''}"
          role="button"
          tabindex="0"
          @click="${handleClick}"
          title="${bonusDone ? this._t('child.click_to_undo') : this._t('child.bonus_tooltip', {name: subtask.name})}"
        >
          <div class="chore-info">
            <div class="chore-number-wrapper">
              <div class="chore-number-badge bonus-badge">
                <ha-icon icon="mdi:star-plus" style="--mdc-icon-size:14px"></ha-icon>
              </div>
            </div>
            <div class="chore-details">
              <div class="chore-name bonus-name">${subtask.name}</div>
              <div class="chore-points">
                <ha-icon icon="${pointsIcon}"></ha-icon>
                +${subtask.points}
                <span class="bonus-label">${this._t('child.bonus_label')}</span>
              </div>
            </div>
          </div>
          <div class="chore-checkbox">
            ${isLoading
              ? html`<ha-icon icon="mdi:loading" style="animation: spin 1s linear infinite; color: var(--fun-purple);"></ha-icon>`
              : html`<ha-icon icon="mdi:check-bold"></ha-icon>`}
          </div>
        </div>
      `;
    })}`;
  }

  async _handleCompleteBonusSubtask(chore, subtask, child) {
    const bonusKey = `${chore.id}_bonus_${subtask.id}_${child.id}`;
    this._loading = { ...this._loading, [bonusKey]: true };
    this.requestUpdate();

    // Optimistic completion
    if (!this._optimisticCompletions) this._optimisticCompletions = {};
    this._optimisticCompletions[bonusKey] = { timestamp: Date.now(), count: 1 };

    try {
      await this.hass.callService("taskmate", "complete_bonus_subtask", {
        chore_id: chore.id,
        bonus_subtask_id: subtask.id,
        child_id: child.id,
      });
      this._playSound(chore.completion_sound || this.config.default_sound || "chime");
    } catch (err) {
      delete this._optimisticCompletions[bonusKey];
    }

    this._loading = { ...this._loading, [bonusKey]: false };
    this.requestUpdate();

    // Clear optimistic after 30s
    setTimeout(() => {
      if (this._optimisticCompletions && this._optimisticCompletions[bonusKey]) {
        delete this._optimisticCompletions[bonusKey];
        this.requestUpdate();
      }
    }, 30000);
  }

  /**
   * Undo a completed bonus sub-task (second click on its checkbox). Each
   * sub-task completion carries its own completion_id, so rejecting it reverses
   * only that sub-task's points — the parent chore stays done. Mirrors the
   * parent-only admin gate and reject_chore path used by _handleUndo.
   */
  async _handleUndoBonusSubtask(chore, subtask, child, todaysCompletions) {
    const bonusKey = `${chore.id}_bonus_${subtask.id}_${child.id}`;
    if (this._loading[bonusKey]) return;

    // Undoing removes already-awarded points, so it is parent-only — short-circuit
    // for non-parents with one friendly message instead of a doomed service call.
    if (!window.__taskmate_is_parent(this.hass)) {
      this._notifyUndo(this._t("child.undo_not_allowed"));
      return;
    }

    const clearOptimistic = () => {
      if (this._optimisticCompletions && this._optimisticCompletions[bonusKey]) {
        const next = { ...this._optimisticCompletions };
        delete next[bonusKey];
        this._optimisticCompletions = next;
      }
    };

    // Find the persisted completion record for this sub-task.
    const completion = (todaysCompletions || []).find(
      c => c.chore_id === chore.id && c.child_id === child.id && c.bonus_subtask_id === subtask.id
    );
    const completionId = completion?.completion_id || completion?.id;

    // Only an optimistic tick and nothing on the server yet — just roll back the
    // optimistic state; there is no completion to reject.
    if (!completionId) {
      clearOptimistic();
      this.requestUpdate();
      return;
    }

    this._loading = { ...this._loading, [bonusKey]: true };
    this.requestUpdate();

    try {
      await this.hass.callService("taskmate", "reject_chore", {
        completion_id: completionId,
      });
      this._playSound(this.config.undo_sound || "undo");
      clearOptimistic();
    } catch (error) {
      console.error("Failed to undo bonus sub-task completion:", error);
      const message = this._isUnauthorized(error)
        ? this._t("child.undo_not_allowed")
        : this._t("child.error_undo", { message: error?.message || "" });
      this._notifyUndo(message);
    } finally {
      this._loading = { ...this._loading, [bonusKey]: false };
      this.requestUpdate();
    }
  }

  _renderCelebration() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || this.hass?.states?.[this.config.entity]?.attributes || {};
    const pointsIcon = attrs.points_icon || "mdi:star";
    const celebratingChore = (attrs.chores || []).find(
      c => c.id === this._celebrating
    );
    const completions = attrs.todays_completions || [];
    const latestCompletion = completions.filter(
      c => c.chore_id === this._celebrating && c.child_id === this.config.child_id
    ).pop();
    const points = (this._celebrationPoints != null)
      ? this._celebrationPoints
      : (latestCompletion && latestCompletion.points != null)
        ? latestCompletion.points
        : (celebratingChore?.points || 0);

    return html`
      <div class="celebration-overlay" @click="${this._closeCelebration}">
        <div class="celebration-content" @click="${(e) => e.stopPropagation()}">
          <div class="celebration-stars">&#127775;&#127775;&#127775;</div>
          <div class="celebration-title">${this._t('child.celebration_title')}</div>
          <div class="celebration-message">${this._t('child.celebration_message')}</div>
          <div class="celebration-points">
            <ha-icon icon="${pointsIcon}"></ha-icon>
            +${points}
          </div>
        </div>
      </div>
    `;
  }

  _renderConfetti() {
    const colors = ["#ff6b9d", "#9b59b6", "#3498db", "#2ecc71", "#f1c40f", "#e67e22"];

    return html`
      <div class="confetti-container">
        ${this._confetti.map((piece, index) => html`
          <div
            class="confetti"
            style="
              left: ${piece.x}%;
              animation-delay: ${piece.delay}s;
              background: ${colors[index % colors.length]};
              border-radius: ${piece.round ? '50%' : '0'};
              width: ${piece.size}px;
              height: ${piece.size}px;
            "
          ></div>
        `)}
      </div>
    `;
  }

  async _handleComplete(chore, child, photoUrl = null) {
    const key = `${chore.id}_${child.id}`;
    const dailyLimit = chore.daily_limit || 1;

    // Check if already loading for this chore (prevent double-clicks during loading)
    if (this._loading[chore.id]) {
      return;
    }

    // Photo-evidence chores can't be completed with a plain tap — open the
    // capture overlay first. The overlay uploads the photo and then calls back
    // into this method with a photoUrl, which takes the service path below.
    if (chore.require_photo && !photoUrl) {
      this._openPhotoCapture(chore, child);
      return;
    }

    // Get current completion count including optimistic completions
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || this.hass?.states?.[this.config.entity]?.attributes || {};
    const allCompletions = attrs.todays_completions || [];
    const todaysCompletions = this._filterCompletionsForToday(allCompletions);
    const actualCompletionsToday = todaysCompletions.filter(
      (comp) => comp.chore_id === chore.id && comp.child_id === child.id
    ).length;

    // Count existing optimistic completions for this chore/child
    const existingData = this._optimisticCompletions[key];
    const existingOptimisticCount = existingData?.count || 0;

    // Calculate total completions (actual + optimistic)
    // This is a simplified count - we're being defensive and not trying to dedupe
    const totalCompletions = actualCompletionsToday + existingOptimisticCount;

    // Guard: If daily limit already reached, don't allow another completion
    if (totalCompletions >= dailyLimit) {
      this.requestUpdate(); // Force re-render to show completed state
      return;
    }

    // IMMEDIATELY set optimistic completion BEFORE making the service call
    // This prevents double-clicks even if the button hasn't re-rendered yet
    const now = Date.now();
    const existingTimestamps = existingData?.timestamps || [];
    this._optimisticCompletions = {
      ...this._optimisticCompletions,
      [key]: {
        timestamp: now,
        timestamps: [...existingTimestamps, now],
        count: existingOptimisticCount + 1,
      },
    };

    this._loading = { ...this._loading, [chore.id]: true };
    this.requestUpdate();

    let cleanupTimeout;
    try {
      // Prefer pressing the per-child/per-chore button entity so HA
      // state-trigger automations on button.taskmate_<child>_complete_<chore>
      // fire. Falls back to the service call if the entity isn't registered
      // yet (e.g. right after HA restart).
      // A photo-evidence completion MUST go through the service so it can carry
      // photo_url — a button-entity press cannot. Other chores prefer the button
      // entity so HA state-trigger automations fire.
      const buttonEntityId = photoUrl ? null : (window.__taskmate_find_button
        && window.__taskmate_find_button(this.hass, child.id, "complete", chore.id));
      if (buttonEntityId) {
        await this.hass.callService("button", "press", { entity_id: buttonEntityId });
      } else {
        await this.hass.callService("taskmate", "complete_chore", {
          chore_id: chore.id,
          child_id: child.id,
          ...(photoUrl ? { photo_url: photoUrl } : {}),
        });
      }

      // Trigger celebration!
      this._celebrating = chore.id;
      this._spawnConfetti();

      // Play completion sound!
      // Use the chore's completion_sound, fall back to config default, then to 'coin'
      const soundToPlay = chore.completion_sound || this.config.default_sound || 'coin';
      this._playSound(soundToPlay);

      this.requestUpdate();

      // Auto-close celebration after 2.5 seconds
      setTimeout(() => {
        this._closeCelebration();
      }, 2500);

      // Clean up optimistic completion after 30 seconds (by then HA state should be updated)
      cleanupTimeout = setTimeout(() => {
        const newOptimistic = { ...this._optimisticCompletions };
        delete newOptimistic[key];
        this._optimisticCompletions = newOptimistic;
        this.requestUpdate();
      }, 30000);

    } catch (error) {
      console.error("Failed to complete chore:", error);

      // Cancel the 30-second cleanup timer since we're handling cleanup now
      if (cleanupTimeout) {
        clearTimeout(cleanupTimeout);
      }

      // Remove the optimistic completion since the service call failed
      const newOptimistic = { ...this._optimisticCompletions };
      const currentData = newOptimistic[key];
      if (currentData) {
        // Remove the timestamp we just added
        const newTimestamps = currentData.timestamps.filter(ts => ts !== now);
        if (newTimestamps.length === 0) {
          delete newOptimistic[key];
        } else {
          newOptimistic[key] = {
            ...currentData,
            timestamps: newTimestamps,
            count: newTimestamps.length,
          };
        }
        this._optimisticCompletions = newOptimistic;
      }

      // Show error notification
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: this._t('child.error_title'),
          message: this._t('child.error_complete', { message: error.message }),
          notification_id: `taskmate_error_${chore.id}`,
        });
      }
    } finally {
      this._loading = { ...this._loading, [chore.id]: false };
      this.requestUpdate();
    }
  }

  // ── Photo-evidence capture ────────────────────────────────────────────────

  _openPhotoCapture(chore, child) {
    this._photoCapture = {
      chore, child, step: "pick", previewUrl: "", blob: null,
      sizeKb: 0, error: "",
    };
    this.requestUpdate();
    // Open the picker straight away (still inside the user's tap gesture).
    this.updateComplete.then(() => this._triggerPhotoPicker());
  }

  _triggerPhotoPicker() {
    const input = this.renderRoot && this.renderRoot.querySelector("#tm-photo-input");
    if (input) {
      input.value = "";
      input.click();
    }
  }

  _onPhotoSelected(e) {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file || !this._photoCapture) return;
    if (!file.type || !file.type.startsWith("image/")) {
      this._photoCapture = { ...this._photoCapture, step: "pick",
        error: this._t("child.photo_not_image") };
      this.requestUpdate();
      return;
    }

    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const max = 1280;
      let { width, height } = img;
      if (width > max || height > max) {
        const scale = Math.min(max / width, max / height);
        width = Math.round(width * scale);
        height = Math.round(height * scale);
      }
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      canvas.getContext("2d").drawImage(img, 0, 0, width, height);
      URL.revokeObjectURL(url);
      canvas.toBlob((blob) => {
        if (!blob || !this._photoCapture) {
          this._photoCapture = { ...this._photoCapture, step: "pick",
            error: this._t("child.photo_process_failed") };
          this.requestUpdate();
          return;
        }
        if (this._photoCapture.previewUrl) URL.revokeObjectURL(this._photoCapture.previewUrl);
        this._photoCapture = {
          ...this._photoCapture, step: "preview", blob,
          previewUrl: URL.createObjectURL(blob),
          sizeKb: Math.round(blob.size / 1024), error: "",
        };
        this.requestUpdate();
      }, "image/jpeg", 0.8);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      this._photoCapture = { ...this._photoCapture, step: "pick",
        error: this._t("child.photo_process_failed") };
      this.requestUpdate();
    };
    img.src = url;
  }

  async _confirmPhoto() {
    const cap = this._photoCapture;
    if (!cap || !cap.blob) return;
    this._photoCapture = { ...cap, step: "uploading", error: "" };
    this.requestUpdate();

    // POST the blob with a Bearer token, refreshing the (short-lived) access
    // token if expired. A 401 means the cached token went stale mid-session, so
    // force a refresh and retry once before giving up.
    const postPhoto = async () => {
      const token = this.hass && this.hass.auth && this.hass.auth.data
        && this.hass.auth.data.access_token;
      const fd = new FormData();
      fd.append("file", cap.blob, "evidence.jpg");
      return fetch("/api/taskmate/photo", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
    };

    try {
      if (this.hass && this.hass.auth && this.hass.auth.expired
        && this.hass.auth.refreshAccessToken) {
        try { await this.hass.auth.refreshAccessToken(); } catch (e) { /* surfaced below */ }
      }
      let resp = await postPhoto();
      if (resp.status === 401 && this.hass && this.hass.auth
        && this.hass.auth.refreshAccessToken) {
        await this.hass.auth.refreshAccessToken();
        resp = await postPhoto();
      }
      if (!resp.ok) throw new Error(`upload failed (${resp.status})`);
      const { photo_url: photoUrl } = await resp.json();
      if (!photoUrl) throw new Error("no photo_url in response");

      const { chore, child } = cap;
      this._closePhotoCapture();
      await this._handleComplete(chore, child, photoUrl);
    } catch (err) {
      // Keep the overlay open on the preview so the child can retry.
      if (this._photoCapture) {
        this._photoCapture = { ...this._photoCapture, step: "preview",
          error: this._t("child.photo_upload_failed") };
        this.requestUpdate();
      }
    }
  }

  _retakePhoto() {
    if (!this._photoCapture) return;
    if (this._photoCapture.previewUrl) URL.revokeObjectURL(this._photoCapture.previewUrl);
    this._photoCapture = { ...this._photoCapture, step: "pick",
      previewUrl: "", blob: null, sizeKb: 0, error: "" };
    this.requestUpdate();
    this._triggerPhotoPicker();
  }

  _closePhotoCapture() {
    if (this._photoCapture && this._photoCapture.previewUrl) {
      URL.revokeObjectURL(this._photoCapture.previewUrl);
    }
    this._photoCapture = null;
    this.requestUpdate();
  }

  _renderPhotoCapture() {
    const cap = this._photoCapture;
    if (!cap) return "";
    const chore = cap.chore || {};
    const stop = (e) => e.stopPropagation();
    return html`
      <div class="photo-overlay" @click="${() => this._closePhotoCapture()}">
        <div class="photo-sheet" @click="${stop}">
          <div class="photo-title">📷 ${this._t("child.photo_required_title")}</div>
          <div class="photo-for">${chore.name || ""}</div>

          ${cap.step === "pick" ? html`
            <div class="photo-dropzone" @click="${() => this._triggerPhotoPicker()}">
              <div class="photo-dropzone-icon">📸</div>
              <div class="photo-dropzone-label">${this._t("child.photo_take")}</div>
              <div class="photo-dropzone-hint">${this._t("child.photo_hint")}</div>
            </div>
            ${cap.error ? html`<div class="photo-error">${cap.error}</div>` : ""}
            <button class="photo-cancel" @click="${() => this._closePhotoCapture()}">
              ${this._t("child.photo_cancel")}
            </button>
          ` : ""}

          ${cap.step === "preview" ? html`
            <div class="photo-preview">
              <img src="${cap.previewUrl}" alt="">
              <span class="photo-size-tag">~${cap.sizeKb} KB</span>
            </div>
            <div class="photo-btn-row">
              <button class="photo-btn ghost" @click="${() => this._retakePhoto()}">
                ↺ ${this._t("child.photo_retake")}
              </button>
              <button class="photo-btn primary" @click="${() => this._confirmPhoto()}">
                ✓ ${this._t("child.photo_confirm")}
              </button>
            </div>
            ${cap.error ? html`<div class="photo-error">${cap.error}</div>` : ""}
            <button class="photo-cancel" @click="${() => this._closePhotoCapture()}">
              ${this._t("child.photo_cancel")}
            </button>
          ` : ""}

          ${cap.step === "uploading" ? html`
            <div class="photo-uploading">
              <div class="photo-spinner"></div>
              <div class="photo-uploading-label">${this._t("child.photo_uploading")}</div>
            </div>
          ` : ""}
        </div>
      </div>
    `;
  }

  /** Show a brief, friendly popup (HA snackbar) instead of a raw error. */
  _notifyUndo(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message },
      bubbles: true,
      composed: true,
    }));
  }

  /** True if an error from reject_chore is an authorization/admin rejection. */
  _isUnauthorized(error) {
    const text = `${error?.message || ""} ${error?.code || ""}`.toLowerCase();
    return text.includes("unauthorized") || text.includes("not authorized");
  }

  async _handleUndo(chore, child, childCompletionsToday) {
    // Check if already loading for this chore (prevent double-clicks during loading)
    if (this._loading[chore.id]) {
      return;
    }

    // Undoing a completion removes already-awarded points, so it is parent-only
    // (this mirrors the parent gate on the reject_chore service). For a non-parent
    // user the call always fails with a raw "Unauthorized" — HA shows its own
    // snackbar and we used to add an error notification on top. Short-circuit
    // with one clear, friendly message and never fire the doomed call.
    if (!window.__taskmate_is_parent(this.hass)) {
      this._notifyUndo(this._t("child.undo_not_allowed"));
      return;
    }

    // Find the most recent completion for this chore/child to undo
    // Sort by completed_at descending to get the most recent
    const sortedCompletions = [...childCompletionsToday].sort((a, b) => {
      const dateA = new Date(a.completed_at || 0);
      const dateB = new Date(b.completed_at || 0);
      return dateB - dateA;
    });

    const completionToUndo = sortedCompletions[0];
    // Check for completion_id (from sensor) or id (fallback)
    const completionId = completionToUndo?.completion_id || completionToUndo?.id;
    if (!completionToUndo || !completionId) {
      return;
    }

    this._loading = { ...this._loading, [chore.id]: true };
    this.requestUpdate();

    try {
      // Call the reject_chore service to remove the completion
      await this.hass.callService("taskmate", "reject_chore", {
        completion_id: completionId,
      });

      // Play undo sound (sad/descending tone)
      const undoSoundToPlay = this.config.undo_sound || 'undo';
      this._playSound(undoSoundToPlay);

      // Clear any optimistic completion data for this chore/child (including bonus sub-tasks)
      const key = `${chore.id}_${child.id}`;
      const newOptimistic = { ...this._optimisticCompletions };
      delete newOptimistic[key];
      // Also clear bonus sub-task optimistic completions
      const bonusPrefix = `${chore.id}_bonus_`;
      const bonusSuffix = `_${child.id}`;
      for (const k of Object.keys(newOptimistic)) {
        if (k.startsWith(bonusPrefix) && k.endsWith(bonusSuffix)) delete newOptimistic[k];
      }
      this._optimisticCompletions = newOptimistic;

    } catch (error) {
      console.error("Failed to undo chore completion:", error);

      // Fallback for the rare case an undo still fails (e.g. a parent hit a
      // genuine error). Show a single transient popup, not a sticky bell
      // notification. An auth rejection gets the same friendly wording as the
      // pre-check above.
      const message = this._isUnauthorized(error)
        ? this._t("child.undo_not_allowed")
        : this._t("child.error_undo", { message: error?.message || "" });
      this._notifyUndo(message);
    } finally {
      this._loading = { ...this._loading, [chore.id]: false };
      this.requestUpdate();
    }
  }

  _spawnConfetti() {
    const confetti = [];
    for (let i = 0; i < 50; i++) {
      confetti.push({
        x: Math.random() * 100,
        delay: Math.random() * 0.5,
        size: Math.random() * 8 + 6,
        round: Math.random() > 0.5,
      });
    }
    this._confetti = confetti;

    // Clear confetti after animation
    setTimeout(() => {
      this._confetti = [];
      this.requestUpdate();
    }, 3500);
  }

  _closeCelebration() {
    this._celebrating = null;
    this.requestUpdate();
  }
}

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
              : [{ value: 'global', label: 'Use global default' }],
            mode: 'dropdown',
          },
        },
      },
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
        name: 'first_come_done_mode',
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
      { name: 'show_countdown', selector: { boolean: {} } },
      { name: 'show_description', selector: { boolean: {} } },
      { name: 'pre_reader', selector: { boolean: {} } },
      { name: 'pre_reader_labels', selector: { boolean: {} } },
      { name: 'pre_reader_points', selector: { boolean: {} } },
      { name: 'debug', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      child_id: this._t('child.editor.child'),
      time_category: this._t('child.editor.time_category'),
      card_design: this._t('common.design.field_label'),
      due_days_mode: this._t('child.editor.chores_not_due_today'),
      recurrence_done_mode: this._t('child.editor.recurring_when_completed'),
      first_come_done_mode: this._t('child.editor.first_come_when_completed'),
      dependency_mode: this._t('child.editor.dependency_mode'),
      elapsed_time_mode: this._t('child.editor.missed_time_chores'),
      show_countdown: this._t('child.editor.show_countdown'),
      show_description: this._t('child.editor.show_description'),
      pre_reader: this._t('child.editor.pre_reader'),
      pre_reader_labels: this._t('child.editor.pre_reader_labels'),
      pre_reader_points: this._t('child.editor.pre_reader_points'),
      debug: this._t('child.editor.show_debug'),
    };
    return labels[entry.name] ?? entry.name;
  };

  _computeHelper = (entry) => {
    const helpers = {
      entity: this._t('common.editor.overview_entity_helper'),
      child_id: this._t('child.editor.child_helper'),
      time_category: this._t('child.editor.time_category_helper'),
      due_days_mode: this._t('child.editor.due_days_helper'),
      recurrence_done_mode: this._t('child.editor.recurrence_helper'),
      first_come_done_mode: this._t('child.editor.first_come_helper'),
      dependency_mode: this._t('child.editor.dependency_helper'),
      elapsed_time_mode: this._t('child.editor.elapsed_helper'),
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
      due_days_mode: this.config.due_days_mode || 'hide',
      recurrence_done_mode: this.config.recurrence_done_mode || 'dim',
      first_come_done_mode: this.config.first_come_done_mode || 'hide',
      dependency_mode: this.config.dependency_mode || 'hide',
      elapsed_time_mode: this.config.elapsed_time_mode || 'dim',
      show_countdown: this.config.show_countdown !== false,
      show_description: this.config.show_description === true,
      pre_reader: this.config.pre_reader === true,
      pre_reader_labels: this.config.pre_reader_labels === true,
      pre_reader_points: this.config.pre_reader_points === true,
      debug: this.config.debug === true,
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
      ${this._renderColourPicker('header_color', '#9b59b6')}
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
      const defaults = {
        show_countdown: true, show_description: false, debug: false,
        time_category: 'morning', due_days_mode: 'hide',
        recurrence_done_mode: 'dim', elapsed_time_mode: 'dim',
        first_come_done_mode: 'hide',
      };
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

// Register the cards
customElements.define("taskmate-child-card", TaskMateChildCard);
customElements.define("taskmate-child-card-editor", TaskMateChildCardEditor);

// Register with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: "taskmate-child-card",
  name: "TaskMate Child Card",
  description: "A fun, kid-friendly card for children to complete their chores!",
  preview: true,
  getEntitySuggestion: (hass, entityId) =>
    window.__taskmate_suggest(hass, entityId, "taskmate-child-card", "overview"),
});

// Version is injected by the HA resource URL (?v=x.x.x) and read from the DOM
const _tmVersion = new URLSearchParams(
  Array.from(document.querySelectorAll('script[src*="/taskmate-child-card.js"]'))
    .map(s => s.src.split("?")[1]).find(Boolean) || ""
).get("v") || "?";
console.info(
  "%c TASKMATE CHILD CARD %c v" + _tmVersion + " ",
  "background:#9b59b6;color:white;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "background:#2c3e50;color:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;"
);
