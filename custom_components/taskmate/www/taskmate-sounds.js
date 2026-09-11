/**
 * TaskMate shared sound engine.
 *
 * Single home for every completion sound, so the child card, the admin panel
 * and the config-flow preview module all behave identically. Before this
 * existed the six synthesised sounds were copy-pasted into two files that had
 * already drifted apart (one still knew only about a long-gone "fart"/"fart_long"
 * pair while the real list had moved to fart1..fart10).
 *
 * Three kinds of sound:
 *   synthesised — generated on the fly via Web Audio API, no files needed
 *   built-in files — the CC0 fart mp3s shipped in this www folder
 *   custom — user-uploaded, referenced as "custom:<file>" (#856)
 *
 * A custom sound is resolved through a lookup table the caller passes in (the
 * `custom_sounds` attribute of sensor.taskmate_chores), because its URL is
 * signed server-side — a bare Audio() carries no bearer token and would 401
 * against the auth-gated serve view.
 *
 * Mirrors window.__taskmate_design: exposed globally, no ES module imports.
 */
(function () {
  "use strict";

  // Base URL for files shipped inside the integration's www folder. Registered
  // by frontend.py as a static path. NOT /local/, which maps to config/www and
  // is where these files have never lived — that mismatch silently 404'd every
  // fart sound until #856.
  const FILE_BASE = "/taskmate";

  const CUSTOM_PREFIX = "custom:";
  const FART_COUNT = 10;

  // Built-in names, mirroring COMPLETION_SOUND_OPTIONS in const.py.
  const BUILTIN = [
    "none", "coin", "levelup", "fanfare", "chime", "powerup", "undo",
    "fart1", "fart2", "fart3", "fart4", "fart5", "fart6", "fart7",
    "fart8", "fart9", "fart10", "fart_random",
  ];

  // One shared AudioContext per page. Browsers cap how many a page may create,
  // and each card minting its own used to leak one per card instance.
  let audioContext = null;

  function getAudioContext() {
    if (!audioContext) {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      if (!Ctor) return null;
      audioContext = new Ctor();
    }
    // Autoplay policy: a context created before any user gesture starts
    // suspended and stays silent until resumed.
    if (audioContext.state === "suspended") audioContext.resume();
    return audioContext;
  }

  function playCoinSound(ctx, startTime) {
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
  function playLevelUpSound(ctx, startTime) {
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
  function playFanfareSound(ctx, startTime) {
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
  function playChimeSound(ctx, startTime) {
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
  function playPowerUpSound(ctx, startTime) {
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
  function playUndoSound(ctx, startTime) {
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
   * Play an audio file by URL. Used for the shipped fart mp3s and for
   * user-uploaded custom sounds.
   */
  function playUrl(url) {
    try {
      const audio = new Audio(url);
      audio.volume = 1.0;
      audio.play().catch(() => { /* autoplay blocked until a user gesture */ });
    } catch (e) { /* no Audio support */ }
  }

  function playFile(filename) {
    playUrl(`${FILE_BASE}/${filename}`);
  }

  /** True for a well-formed "custom:<32hex>.<ext>" value. Mirrors sounds.is_custom_sound. */
  function isCustom(name) {
    return typeof name === "string"
      && name.startsWith(CUSTOM_PREFIX)
      && /^[0-9a-f]{32}\.(mp3|ogg|wav|m4a)$/.test(name.slice(CUSTOM_PREFIX.length));
  }

  /**
   * Resolve a custom sound value to its signed URL via the lookup table.
   * `customSounds` is the list delivered on sensor.taskmate_chores.
   */
  function customUrl(name, customSounds) {
    if (!isCustom(name) || !Array.isArray(customSounds)) return null;
    const hit = customSounds.find(s => s && s.value === name);
    return (hit && hit.url) || null;
  }

  /**
   * Play a completion sound by name.
   *
   * @param {string} name - built-in name, or "custom:<file>"
   * @param {Array}  customSounds - optional lookup table for custom sounds
   */
  function play(name, customSounds) {
    if (!name || name === "none") return;

    if (isCustom(name)) {
      const url = customUrl(name, customSounds);
      // A dangling reference (sound deleted, or a card whose sensor data
      // predates the upload) stays silent rather than playing the wrong thing.
      if (url) playUrl(url);
      return;
    }

    if (name === "fart_random") {
      playFile(`fart${Math.floor(Math.random() * FART_COUNT) + 1}.mp3`);
      return;
    }
    if (/^fart([1-9]|10)$/.test(name)) {
      playFile(`${name}.mp3`);
      return;
    }

    const ctx = getAudioContext();
    if (!ctx) return;
    const now = ctx.currentTime;
    try {
      switch (name) {
        case "coin":    playCoinSound(ctx, now); break;
        case "levelup": playLevelUpSound(ctx, now); break;
        case "fanfare": playFanfareSound(ctx, now); break;
        case "chime":   playChimeSound(ctx, now); break;
        case "powerup": playPowerUpSound(ctx, now); break;
        case "undo":    playUndoSound(ctx, now); break;
        default:        playCoinSound(ctx, now); break;
      }
    } catch (e) { /* a failed sound must never break a completion */ }
  }

  window.__taskmate_sounds = { BUILTIN, CUSTOM_PREFIX, play, isCustom, customUrl, getAudioContext };
})();
