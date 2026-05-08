
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
    this._badgeEventUnsub = null;
  }

  connectedCallback() {
    super.connectedCallback();
    this._subscribeBadgeEvents();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._stopTimerTick();
    this._badgeEventUnsub?.();
    this._badgeEventUnsub = null;
  }

  updated(changedProperties) {
    super.updated(changedProperties);
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const sessions = attrs.active_timed_sessions || [];
    const hasRunning = sessions.some(s => s.state === 'running' && s.child_id === this.config?.child_id);
    if (hasRunning && !this._timerInterval) {
      this._timerInterval = setInterval(() => { this._timerTick++; this.requestUpdate(); }, 1000);
    } else if (!hasRunning && this._timerInterval) {
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

  _subscribeBadgeEvents() {
    if (!this.hass?.connection) return;
    this.hass.connection.subscribeEvents((event) => {
      const data = event.data || {};
      const configChild = this.config?.child_id;
      if (configChild && data.child_id && String(data.child_id) !== String(configChild)) return;
      if (data.badge_id) {
        this._justEarnedBadge = String(data.badge_id);
        this.requestUpdate();
        setTimeout(() => { this._justEarnedBadge = null; this.requestUpdate(); }, 1800);
      }
    }, "taskmate_badge_earned").then(unsub => {
      this._badgeEventUnsub = unsub;
    }).catch(() => {});
  }

  _tierColor(tier) {
    return {
      bronze: '#cd7f32',
      silver: '#c0c0c0',
      gold: '#f1c40f',
      platinum: '#67e8f9',
    }[tier] || '#888';
  }

  _openBadgesView() {
    const slug = this.config?.child_id
      ? String(this.config.child_id).toLowerCase().replace(/\s+/g, '_')
      : '';
    window.history.pushState(null, '', `/taskmate-admin?section=badges${slug ? '&child=' + slug : ''}`);
    window.dispatchEvent(new PopStateEvent('popstate'));
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
        case 'fart_random':
          // Pick a random fart sound (1-10)
          const randomFartNum = Math.floor(Math.random() * 10) + 1;
          this._playAudioFile(`fart${randomFartNum}.mp3`);
          break;
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
    return css`
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

      /* Chore number wrapper (icon removed) */
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

      .chore-card.completed .chore-icon-container {
        background: rgba(255, 255, 255, 0.8);
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
    `;
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
    const child = children.find(c => c.id === this.config.child_id);

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
    const childSlug = String(this.config.child_id).toLowerCase().replace(/[^a-z0-9]+/g, '_');
    const badgesEntityId = `sensor.taskmate_badges_${childSlug}`;
    const badgesEntity = this.hass.states[badgesEntityId];
    const earnedBadges = (badgesEntity?.attributes?.earned) || [];
    const showBadges = this.config.show_badges !== false && earnedBadges.length > 0;

    // Get pending points for this child
    const pendingPoints = child.pending_points || 0;

    // Get today's completions for this child (with timezone-aware filtering as fallback)
    // The backend provides todays_completions, but we also apply client-side filtering
    // to ensure timezone correctness matches the HA frontend timezone
    const allCompletions = attrs.todays_completions || attrs.completions || [];
    const todaysCompletions = this._filterCompletionsForToday(allCompletions);

    // Debug logging to help troubleshoot daily limit issues
    if (allCompletions.length > 0 || todaysCompletions.length > 0) {
    }

    return html`
      <ha-card>
        <style>:host { --taskmate-header-bg: ${this.config.header_color || '#9b59b6'}; }</style>
        <div class="card-header">
          <div class="header-left">
            <div class="avatar-container">
              <ha-icon icon="${avatar}"></ha-icon>
            </div>
            <div class="child-name-container">
              <div class="child-name">${child.name}</div>
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

        ${showBadges ? html`
          <div class="badge-strip" @click=${() => this._openBadgesView()} title="${this._t('badges.label')}">
            <span class="badge-strip-label">${this._t('badges.label')}</span>
            ${earnedBadges.slice(0, 5).map(b => html`
              <div class="badge-mini tier-${b.tier} ${this._justEarnedBadge && String(this._justEarnedBadge) === String(b.id) ? 'just-earned' : ''}"
                style="--t: ${this._tierColor(b.tier)}">
                <ha-icon icon="${b.icon || 'mdi:medal'}"></ha-icon>
              </div>
            `)}
            ${earnedBadges.length > 5 ? html`<span class="badge-strip-more">+${earnedBadges.length - 5} →</span>` : ''}
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
                ${childChores.map((chore, index) => html`
                  ${chore.task_type === 'timed'
                    ? this._renderTimedChoreCard(chore, child, pointsIcon, todaysCompletions, index)
                    : html`
                      ${this._renderChoreCard(chore, child, pointsIcon, todaysCompletions, index)}
                      ${this._renderBonusSubtasks(chore, child, pointsIcon, todaysCompletions)}
                    `}
                `)}
              `}
        </div>

        ${this._celebrating ? this._renderCelebration() : ""}
        ${this._confetti.length > 0 ? this._renderConfetti() : ""}

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

  _filterAndSortChores(chores, child) {
    const childId = String(child.id || "");
    const childName = child.name;
    const choreOrder = child.chore_order || [];

    // Debug logging to diagnose assignment filtering issues

    // Get today's day of week from sensor (set by backend) or compute client-side
    const entity = this.hass?.states?.[this.config.entity];
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config.entity)) || entity?.attributes || {};
    const todayDow = entity?.attributes?.today_day_of_week ||
      new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();

    const dueDaysMode = this.config.due_days_mode || 'hide';
    const showDueDaysOnly = this.config.show_due_days_only !== false;
    const elapsedTimeMode = this.config.elapsed_time_mode || 'dim';

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

      // Dynamic assignment (alternating / random): only the currently-active child
      // sees the chore. The backend caches today's pick in assignment_current_child_id.
      // Once any eligible pool member has completed the chore today (e.g. a parent
      // credited the off-rotation child), the chore is done for the whole pool and
      // should disappear for everyone — including today's active child.
      const assignmentMode = chore.assignment_mode || 'everyone';
      if (assignmentMode !== 'everyone' && isAssignedToChild) {
        const activeId = chore.assignment_current_child_id ? String(chore.assignment_current_child_id) : '';
        isAssignedToChild = activeId !== '' && activeId === String(childId);
        if (isAssignedToChild) {
          const poolIds = assignedToStrings.length > 0
            ? assignedToStrings
            : (attrs.children || []).map(c => String(c.id));
          const poolSet = new Set(poolIds);
          const dailyLimit = chore.daily_limit || 1;
          const allTodayCompletions = attrs.todays_completions || [];
          const poolCompletionsToday = allTodayCompletions.filter(
            comp => comp.chore_id === chore.id && (poolSet.has(String(comp.child_id)) || comp.child_id === "__parent__")
          ).length;
          if (poolCompletionsToday >= dailyLimit) {
            isAssignedToChild = false;
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

  _getTimeBoundaries() {
    const attrs = (window.__taskmate_attrs && window.__taskmate_attrs(this.hass, this.config?.entity))
      || this.hass?.states?.[this.config?.entity]?.attributes || {};
    const tb = attrs.time_boundaries || {};
    return {
      morning:   [this._parseHHMM(tb.morning_start, 6, 0),   this._parseHHMM(tb.morning_end, 12, 0)],
      afternoon: [this._parseHHMM(tb.afternoon_start, 12, 0), this._parseHHMM(tb.afternoon_end, 17, 0)],
      evening:   [this._parseHHMM(tb.evening_start, 17, 0),   this._parseHHMM(tb.evening_end, 21, 0)],
      night:     [this._parseHHMM(tb.night_start, 21, 0),     this._parseHHMM(tb.night_end, 23, 59)],
    };
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
    const b = this._getTimeBoundaries();
    if (now >= b.night[0])     return 'night';
    if (now >= b.evening[0])   return 'evening';
    if (now >= b.afternoon[0]) return 'afternoon';
    return 'morning';
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
    const order = ['morning', 'afternoon', 'evening', 'night'];
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
    const order = { morning: 0, afternoon: 1, evening: 2, night: 3 };
    const choreIndex = order[cat];
    if (choreIndex === undefined) return false;
    const currentIndex = order[this._getCurrentTimePeriod()];
    if (currentIndex <= choreIndex) return false;
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
    // Convert back to UTC ms
    const tomorrowUTC = new Date(tomorrow.toLocaleString("en-US", { timeZone: tz }));
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

  _renderChoreCard(chore, child, pointsIcon, todaysCompletions = [], choreIndex = 0) {
    const isLoading = this._loading[chore.id];
    const isCelebrating = this._celebrating === chore.id;

    // Check how many times this chore was completed today by this child
    // Both pending (awaiting approval) AND approved completions count toward the daily limit
    const childCompletionsToday = todaysCompletions.filter(
      (comp) => comp.chore_id === chore.id && (comp.child_id === child.id || comp.child_id === "__parent__") && !comp.bonus_subtask_id
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
      // Calculate how many optimistic completions we've tracked that aren't yet in the data
      const optimisticCount = optimisticData.count || 1;

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

    // Debug logging to help troubleshoot daily limit issues
    if (childCompletionsToday.length > 0 || isCompletedForToday || hasOptimisticCompletion) {
    }

    // Check if the most recent completion is pending approval
    const hasPendingCompletion = childCompletionsToday.some((comp) => !comp.approved) || hasOptimisticCompletion;

    // Chore number (1-indexed for display) and color class (cycle through 8 colors)
    const choreNumber = choreIndex + 1;
    const colorClass = `color-${choreIndex % 8}`;

    // Click handler for the entire row
    const notDueToday = chore._hasDueDays && !chore._isDueToday && this.config.due_days_mode === 'dim';
    const recurrenceDoneMode = this.config.recurrence_done_mode || 'dim';
    const notAvailableRecurrence = chore._isRecurring && !chore._isAvailableForChild && recurrenceDoneMode === 'dim';
    // Elapsed: only dim incomplete chores — completed ones keep their green "done" style
    const elapsedTimeMode = this.config.elapsed_time_mode || 'dim';
    const timeElapsed = chore._isTimeElapsed && !isCompletedForToday && elapsedTimeMode === 'dim';
    const isLockedPreview = !!chore._isLockedPreview && !isCompletedForToday;
    const periodStartHour = isLockedPreview
      ? (this._getPeriodHours(chore.time_category)?.[0] ?? null)
      : null;
    const lockedUntilLabel = isLockedPreview && periodStartHour !== null
      ? this._t('child.chore_locked_until', { time: `${String(Math.floor(periodStartHour)).padStart(2, '0')}:${String(Math.round((periodStartHour % 1) * 60)).padStart(2, '0')}` })
      : '';
    const handleRowClick = () => {
      if (isLoading) return;
      if (notDueToday) return;  // Dim mode — not interactive
      if (notAvailableRecurrence) return;  // Recurrence window not open — not interactive
      if (isLockedPreview) return;  // Next-period preview — not yet claimable
      if (timeElapsed) return;  // Time period passed — not interactive
      if (isCompletedForToday) {
        this._handleUndo(chore, child, childCompletionsToday);
      } else {
        this._handleComplete(chore, child);
      }
    };
    const isInteractive = !(isLoading || notDueToday || notAvailableRecurrence || isLockedPreview || timeElapsed);
    const handleRowKeyDown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleRowClick();
      }
    };

    const titleText = isLockedPreview
      ? (lockedUntilLabel || this._t('child.chore_locked_until_generic'))
      : notDueToday
        ? this._t('child.not_scheduled_for_today')
        : timeElapsed
          ? this._t('child.time_has_passed')
          : isCompletedForToday
            ? this._t('child.click_to_undo')
            : this._t('child.click_to_complete');

    return html`
      <div
        class="chore-card ${isLoading ? "loading" : ""} ${isCelebrating ? "celebrating" : ""} ${isCompletedForToday ? "completed" : ""} ${notDueToday ? "not-due-today" : ""} ${notAvailableRecurrence ? "recurrence-unavailable" : ""} ${timeElapsed ? "time-elapsed" : ""} ${isLockedPreview ? "chore-locked" : ""}"
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
            <div class="chore-number-badge ${colorClass}">${choreNumber}</div>
          </div>
          <div class="chore-details">
            <div class="chore-name">${chore.name}</div>
            ${this.config.show_description && chore.description ? html`
              <div class="chore-description">${chore.description}</div>
            ` : ''}
            ${chore._isRecurring && !chore._isAvailableForChild ? html`
              <div class="recurrence-label">
                <ha-icon icon="mdi:clock-outline"></ha-icon>
                ${chore.recurrence ? chore.recurrence.replace(/_/g, ' ') : this._t('child.recurring')}
              </div>
            ` : ''}
            <div class="chore-points">
              <ha-icon icon="${pointsIcon}"></ha-icon>
              +${chore.points}
              ${dailyLimit > 1 ? html`<span style="font-size: 0.8em; opacity: 0.7;">(${completionsToday}/${dailyLimit})</span>` : ''}
            </div>
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
            <div class="chore-number-badge ${colorClass}">${choreNumber}</div>
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
            <button class="timer-btn start" @click="${handleStart}" ?disabled="${isLoading}">
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
            <button class="timer-btn resume" @click="${handleStart}" ?disabled="${isLoading}">
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
        if (isLoading || bonusDone) return;
        this._handleCompleteBonusSubtask(chore, subtask, child);
      };

      return html`
        <div
          class="chore-card bonus-subtask ${bonusDone ? 'completed' : ''} ${isLoading ? 'loading' : ''}"
          role="button"
          tabindex="${bonusDone ? '-1' : '0'}"
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

  async _handleComplete(chore, child) {
    const key = `${chore.id}_${child.id}`;
    const dailyLimit = chore.daily_limit || 1;

    // Check if already loading for this chore (prevent double-clicks during loading)
    if (this._loading[chore.id]) {
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
      const buttonEntityId = window.__taskmate_find_button
        && window.__taskmate_find_button(this.hass, child.id, "complete", chore.id);
      if (buttonEntityId) {
        await this.hass.callService("button", "press", { entity_id: buttonEntityId });
      } else {
        await this.hass.callService("taskmate", "complete_chore", {
          chore_id: chore.id,
          child_id: child.id,
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

  async _handleUndo(chore, child, childCompletionsToday) {
    // Check if already loading for this chore (prevent double-clicks during loading)
    if (this._loading[chore.id]) {
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

      // Show error notification
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: this._t('child.error_title'),
          message: this._t('child.error_undo', { message: error.message }),
          notification_id: `taskmate_undo_error_${chore.id}`,
        });
      }
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
            options: [
              { value: 'morning', label: this._t('child.editor.time_category_morning') },
              { value: 'afternoon', label: this._t('child.editor.time_category_afternoon') },
              { value: 'evening', label: this._t('child.editor.time_category_evening') },
              { value: 'night', label: this._t('child.editor.time_category_night') },
              { value: 'anytime', label: this._t('child.editor.time_category_anytime') },
              { value: 'all', label: this._t('child.editor.time_category_all') },
            ],
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
      { name: 'debug', selector: { boolean: {} } },
    ];
  }

  _computeLabel = (entry) => {
    const labels = {
      entity: this._t('common.editor.overview_entity'),
      child_id: this._t('child.editor.child'),
      time_category: this._t('child.editor.time_category'),
      due_days_mode: this._t('child.editor.chores_not_due_today'),
      recurrence_done_mode: this._t('child.editor.recurring_when_completed'),
      elapsed_time_mode: this._t('child.editor.missed_time_chores'),
      show_countdown: this._t('child.editor.show_countdown'),
      show_description: this._t('child.editor.show_description'),
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
      due_days_mode: this.config.due_days_mode || 'hide',
      recurrence_done_mode: this.config.recurrence_done_mode || 'dim',
      elapsed_time_mode: this.config.elapsed_time_mode || 'dim',
      show_countdown: this.config.show_countdown !== false,
      show_description: this.config.show_description === true,
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
    const current = this.config[key] || defaultValue;
    const presets = ['#9b59b6', '#e67e22', '#27ae60', '#3498db', '#f1c40f', '#e74c3c', '#34495e'];
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
      const defaults = {
        show_countdown: true, show_description: false, debug: false,
        time_category: 'morning', due_days_mode: 'hide',
        recurrence_done_mode: 'dim', elapsed_time_mode: 'dim',
      };
      if (value === '' || value === null || value === undefined) {
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