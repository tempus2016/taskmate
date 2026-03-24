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
    };
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
      });
    } catch (e) {
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
        background: color-mix(in srgb, var(--fun-blue) 10%, var(--card-background-color, #fff));
      }

      .chore-card:nth-child(even) {
        border-color: var(--fun-pink);
        background: color-mix(in srgb, var(--fun-pink) 10%, var(--card-background-color, #fff));
      }

      .chore-card:nth-child(3n) {
        border-color: var(--fun-green);
        background: color-mix(in srgb, var(--fun-green) 10%, var(--card-background-color, #fff));
      }

      .chore-card:nth-child(4n) {
        border-color: var(--fun-orange);
        background: color-mix(in srgb, var(--fun-orange) 10%, var(--card-background-color, #fff));
      }

      /* Touch/hover feedback - works for both touch and mouse */
      .chore-card:active {
        transform: scale(0.98);
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
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

      .recurrence-label {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--secondary-text-color);
        background: rgba(0,0,0,0.06);
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
        background: rgba(0,0,0,0.06);
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
    `;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("Please define an entity (taskmate overview sensor)");
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
      show_countdown: true,          // Show midnight reset countdown below section title
      show_due_days_only: true,      // Whether to apply due_days filtering at all
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
            <div>Entity not found: ${this.config.entity}</div>
          </div>
        </ha-card>
      `;
    }

    // Get child info
    const children = entity.attributes.children || [];
    const child = children.find(c => c.id === this.config.child_id);

    if (!child) {
      return html`
        <ha-card>
          <div class="error-state">
            <ha-icon icon="mdi:account-alert"></ha-icon>
            <div>Child not found: ${this.config.child_id}</div>
          </div>
        </ha-card>
      `;
    }

    // Get chores for this child and time category
    const allChores = entity.attributes.chores || [];

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

    const pointsIcon = entity.attributes.points_icon || "mdi:star";
    const pointsName = entity.attributes.points_name || "Stars";

    // Avatar now in children array directly
    const avatar = child.avatar || "mdi:account-circle";

    // Get pending points for this child
    const pendingPoints = child.pending_points || 0;

    // Get today's completions for this child (with timezone-aware filtering as fallback)
    // The backend provides todays_completions, but we also apply client-side filtering
    // to ensure timezone correctness matches the HA frontend timezone
    const allCompletions = entity.attributes.todays_completions || entity.attributes.completions || [];
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
                  <div class="stars-label waiting-stars">Pending</div>
                </div>
              ` : ''}
            </div>
          </div>
        </div>

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
                ${childChores.map((chore, index) => this._renderChoreCard(chore, child, pointsIcon, todaysCompletions, index))}
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
    const todayDow = entity?.attributes?.today_day_of_week ||
      new Date().toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();

    const dueDaysMode = this.config.due_days_mode || 'hide';
    const showDueDaysOnly = this.config.show_due_days_only !== false;

    // First, filter chores for this child and time category
    const filteredChores = chores.filter(chore => {
      // Check time category
      const matchesTime =
        this.config.time_category === "all" ||
        chore.time_category === this.config.time_category ||
        chore.time_category === "anytime";

      // Check assignment
      let assignedTo = chore.assigned_to;
      if (!Array.isArray(assignedTo)) assignedTo = [];
      const assignedToStrings = assignedTo.map(id => String(id));
      const isAssignedToAll = assignedToStrings.length === 0;
      const isAssignedToChild = isAssignedToAll || assignedToStrings.includes(childId);

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

      return matchesTime && isAssignedToChild;
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
    const labels = {
      morning: "Morning",
      afternoon: "Afternoon",
      evening: "Evening",
      night: "Night",
      anytime: "Anytime",
      all: "All",
    };
    return labels[category] || category;
  }

  _getDynamicTitle() {
    const category = this.config.time_category;
    const titles = {
      morning: "Morning Chores",
      afternoon: "Afternoon Chores",
      evening: "Evening Chores",
      night: "Night Chores",
      anytime: "Today's Chores",
      all: "Today's Chores",
    };
    return titles[category] || "Today's Chores";
  }

  _getTimezone() {
    // Get timezone from Home Assistant config, fallback to browser timezone
    return this.hass?.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone;
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
      label = `Chores reset in ${hours}h ${mins}m`;
    } else if (mins > 0) {
      label = `Chores reset in ${mins}m`;
    } else {
      label = "Chores resetting soon!";
    }
    return { label, soon };
  }

  _renderEmptyState() {
    return html`
      <div class="empty-state">
        <ha-icon icon="mdi:party-popper"></ha-icon>
        <div class="message">All Done!</div>
        <div class="submessage">No chores right now. Great job!</div>
      </div>
    `;
  }

  _renderChoreCard(chore, child, pointsIcon, todaysCompletions = [], choreIndex = 0) {
    const isLoading = this._loading[chore.id];
    const isCelebrating = this._celebrating === chore.id;

    // Check how many times this chore was completed today by this child
    // Both pending (awaiting approval) AND approved completions count toward the daily limit
    const childCompletionsToday = todaysCompletions.filter(
      (comp) => comp.chore_id === chore.id && comp.child_id === child.id
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
    const handleRowClick = () => {
      if (isLoading) return;
      if (notDueToday) return;  // Dim mode — not interactive
      if (isCompletedForToday) {
        this._handleUndo(chore, child, childCompletionsToday);
      } else {
        this._handleComplete(chore, child);
      }
    };

    return html`
      <div
        class="chore-card ${isLoading ? "loading" : ""} ${isCelebrating ? "celebrating" : ""} ${isCompletedForToday ? "completed" : ""} ${notDueToday ? "not-due-today" : ""} ${notAvailableRecurrence ? "recurrence-unavailable" : ""}"
        @click="${handleRowClick}"
        title="${notDueToday ? 'Not scheduled for today' : isCompletedForToday ? 'Click to undo' : 'Click to complete'}"
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
                ${chore.recurrence ? chore.recurrence.replace(/_/g, ' ') : 'Recurring'}
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
            : html`<ha-icon icon="mdi:check-bold"></ha-icon>`}
        </div>
      </div>
    `;
  }

  _renderCelebration() {
    const entity = this.hass.states[this.config.entity];
    const pointsIcon = entity?.attributes?.points_icon || "mdi:star";
    const celebratingChore = (entity?.attributes?.chores || []).find(
      c => c.id === this._celebrating
    );
    const points = celebratingChore?.points || 0;

    return html`
      <div class="celebration-overlay" @click="${this._closeCelebration}">
        <div class="celebration-content" @click="${(e) => e.stopPropagation()}">
          <div class="celebration-stars">&#127775;&#127775;&#127775;</div>
          <div class="celebration-title">AWESOME!</div>
          <div class="celebration-message">You did it! Keep up the great work!</div>
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
    const entity = this.hass.states[this.config.entity];
    const allCompletions = entity?.attributes?.todays_completions || [];
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

    try {
      await this.hass.callService("taskmate", "complete_chore", {
        chore_id: chore.id,
        child_id: child.id,
      });

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
      setTimeout(() => {
        const newOptimistic = { ...this._optimisticCompletions };
        delete newOptimistic[key];
        this._optimisticCompletions = newOptimistic;
        this.requestUpdate();
      }, 30000);

    } catch (error) {
      console.error("Failed to complete chore:", error);

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
          title: "Oops!",
          message: `Something went wrong: ${error.message}`,
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

      // Clear any optimistic completion data for this chore/child
      const key = `${chore.id}_${child.id}`;
      const newOptimistic = { ...this._optimisticCompletions };
      delete newOptimistic[key];
      this._optimisticCompletions = newOptimistic;

    } catch (error) {
      console.error("Failed to undo chore completion:", error);

      // Show error notification
      if (this.hass.callService) {
        this.hass.callService("persistent_notification", "create", {
          title: "Oops!",
          message: `Couldn't undo: ${error.message}`,
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

  static get styles() {
    return css`
      :host { display: block; padding: 4px 0; }

      ha-textfield { width: 100%; margin-bottom: 8px; }

      .field-row { margin-bottom: 16px; }

      .field-label {
        display: block;
        font-size: 12px;
        font-weight: 500;
        color: var(--secondary-text-color);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
        padding: 0 4px;
      }

      .field-select {
        display: block;
        width: 100%;
        padding: 10px 12px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color);
        font-size: 14px;
        font-family: var(--mdc-typography-body1-font-family, Roboto, sans-serif);
        box-sizing: border-box;
        cursor: pointer;
        appearance: auto;
        transition: border-color 0.15s;
      }

      .field-select:focus {
        outline: none;
        border-color: var(--primary-color, #3498db);
        border-width: 2px;
      }

      .field-helper {
        display: block;
        font-size: 11px;
        color: var(--secondary-text-color);
        margin-top: 5px;
        padding: 0 4px;
        line-height: 1.4;
      }

      .check-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 12px;
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: 4px;
        background: var(--card-background-color, #fff);
        cursor: pointer;
        user-select: none;
        margin-bottom: 4px;
        transition: background 0.15s;
      }

      .check-row:hover { background: var(--secondary-background-color, #f5f5f5); }

      .check-row input[type="checkbox"] {
        width: 18px;
        height: 18px;
        cursor: pointer;
        flex-shrink: 0;
        accent-color: var(--primary-color, #3498db);
        margin: 0;
      }

      .check-label {
        font-size: 14px;
        color: var(--primary-text-color);
        font-family: var(--mdc-typography-body1-font-family, Roboto, sans-serif);
        flex: 1;
        line-height: 1.3;
      }

      .section-divider {
        height: 1px;
        background: var(--divider-color, #e0e0e0);
        margin: 16px 0;
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

    // Get children from overview entity
    const overviewEntity = this.hass.states[this.config.entity];
    const children = overviewEntity?.attributes?.children || [];

    return html`
      <ha-textfield
        label="Overview Entity"
        .value="${this.config.entity || ''}"
        @change="${this._entityChanged}"
        helper="The TaskMate overview sensor entity"
        helperPersistent
        placeholder="sensor.taskmate_overview"
      ></ha-textfield>

      <div class="field-row">
        <label class="field-label">Child</label>
        <select class="field-select" @change="${this._childIdChanged}">
          <option value="">Select a child...</option>
          ${children.map(child => html`
            <option value="${child.id}" ?selected="${this.config.child_id === child.id}">${child.name}</option>
          `)}
        </select>
        <span class="field-helper">Which child is this card for?</span>
      </div>

      <div class="field-row">
        <label class="field-label">Time Category</label>
        <select class="field-select" @change="${this._timeCategoryChanged}">
          <option value="morning" ?selected="${this.config.time_category === 'morning'}">Morning Chores</option>
          <option value="afternoon" ?selected="${this.config.time_category === 'afternoon'}">Afternoon Chores</option>
          <option value="evening" ?selected="${this.config.time_category === 'evening'}">Evening Chores</option>
          <option value="night" ?selected="${this.config.time_category === 'night'}">Night Chores</option>
          <option value="anytime" ?selected="${this.config.time_category === 'anytime'}">Today's Chores (Anytime)</option>
          <option value="all" ?selected="${this.config.time_category === 'all'}">Today's Chores (All)</option>
        </select>
        <span class="field-helper">Which time of day to show chores for — also sets the card title</span>
      </div>

      <div class="field-row">
        <label class="field-label">Chores Not Due Today</label>
        <select class="field-select" @change="${e => this._updateConfig('due_days_mode', e.target.value)}">
          <option value="hide" ?selected="${(this.config.due_days_mode || 'hide') === 'hide'}">Hide — don't show</option>
          <option value="dim" ?selected="${this.config.due_days_mode === 'dim'}">Dim — show greyed out, non-interactive</option>
          <option value="show" ?selected="${this.config.due_days_mode === 'show'}">Show — show normally regardless</option>
        </select>
        <span class="field-helper">Applies to chores with due_days set when today isn't scheduled</span>
      </div>

      <div class="field-row">
        <label class="field-label">Recurring Chores — When Completed</label>
        <select class="field-select" @change="${e => this._updateConfig('recurrence_done_mode', e.target.value)}">
          <option value="dim" ?selected="${(this.config.recurrence_done_mode || 'dim') === 'dim'}">Dim — show greyed out, non-interactive</option>
          <option value="hide" ?selected="${this.config.recurrence_done_mode === 'hide'}">Hide — don't show until available again</option>
          <option value="show" ?selected="${this.config.recurrence_done_mode === 'show'}">Show — show normally regardless</option>
        </select>
        <span class="field-helper">What to show when a recurring chore has been completed and the window hasn't reset yet</span>
      </div>

      <div class="section-divider"></div>

      <label class="check-row">
        <input type="checkbox"
          ?checked="${this.config.show_countdown !== false}"
          @change="${e => this._updateConfig('show_countdown', e.target.checked)}"
        />
        <span class="check-label">Show reset countdown beside "Today's Chores"</span>
      </label>

      <label class="check-row">
        <input type="checkbox"
          ?checked="${this.config.show_description === true}"
          @change="${e => this._updateConfig('show_description', e.target.checked)}"
        />
        <span class="check-label">Show chore description</span>
      </label>

      <label class="check-row">
        <input type="checkbox"
          ?checked="${this.config.debug === true}"
          @change="${this._debugChanged}"
        />
        <span class="check-label">Show debug panel</span>
      </label>
        <span class="field-helper">Card header background colour</span>
      </div>
      <div class="field-row">
        <label class="field-label">Header Colour</label>
        <div style="display:flex;align-items:center;gap:10px;">
          <input
            type="color"
            .value=${this.config.header_color || '#9b59b6'}
            @input=${e => this._updateConfig('header_color', e.target.value)}
            style="width:48px;height:36px;padding:2px;border:1px solid var(--divider-color,#e0e0e0);border-radius:6px;cursor:pointer;"
          />
          <span style="font-size:13px;color:var(--secondary-text-color);">${this.config.header_color || '#9b59b6'}</span>
          <button
            style="font-size:11px;color:var(--secondary-text-color);background:none;border:1px solid var(--divider-color,#e0e0e0);border-radius:4px;padding:3px 8px;cursor:pointer;"
            @click=${() => this._updateConfig('header_color', '#9b59b6')}
          >Reset</button>
        </div>
        <span class="field-helper">Card header background colour</span>
      </div>
    `;
  }

  _entityChanged(e) {
    this._updateConfig("entity", e.target.value);
  }

  _childIdChanged(e) {
    this._updateConfig("child_id", e.target.value);
  }

  _timeCategoryChanged(e) {
    this._updateConfig("time_category", e.target.value);
  }

  _debugChanged(e) {
    this._updateConfig("debug", e.target.checked);
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
