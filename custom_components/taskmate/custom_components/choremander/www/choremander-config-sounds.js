/**
 * Choremander Config Flow Sound Preview
 * Plays sound preview when the completion_sound dropdown value changes
 * in the config flow (add/edit chore screens).
 */

(function() {
  'use strict';

  // Audio context for sound preview (lazy initialized)
  let audioContext = null;

  /**
   * Get or create AudioContext
   */
  function getAudioContext() {
    if (!audioContext) {
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === 'suspended') {
      audioContext.resume();
    }
    return audioContext;
  }

  // ============== SOUND IMPLEMENTATIONS ==============
  // These are copies from choremander-child-card.js to keep this file standalone

  function playCoinSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.3;

    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.connect(gain1);
    gain1.connect(masterGain);
    osc1.frequency.value = 1318.5;
    osc1.type = 'square';
    gain1.gain.setValueAtTime(0.5, startTime);
    gain1.gain.exponentialRampToValueAtTime(0.01, startTime + 0.1);
    osc1.start(startTime);
    osc1.stop(startTime + 0.1);

    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.connect(gain2);
    gain2.connect(masterGain);
    osc2.frequency.value = 1975.5;
    osc2.type = 'square';
    gain2.gain.setValueAtTime(0.5, startTime + 0.08);
    gain2.gain.exponentialRampToValueAtTime(0.01, startTime + 0.25);
    osc2.start(startTime + 0.08);
    osc2.stop(startTime + 0.25);
  }

  function playLevelUpSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.25;

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

    const chordNotes = [523.25, 659.25, 783.99];
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

  function playFanfareSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.2;

    const pattern = [
      { freq: 392.00, duration: 0.1, delay: 0 },
      { freq: 392.00, duration: 0.1, delay: 0.12 },
      { freq: 392.00, duration: 0.15, delay: 0.24 },
      { freq: 329.63, duration: 0.15, delay: 0.42 },
      { freq: 392.00, duration: 0.15, delay: 0.6 },
      { freq: 523.25, duration: 0.4, delay: 0.78 },
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

  function playChimeSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.3;

    const fundamental = 880;
    const harmonics = [1, 2, 3, 4.2];

    harmonics.forEach((harmonic, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(masterGain);
      osc.frequency.value = fundamental * harmonic;
      osc.type = 'sine';

      const amplitude = 0.5 / (i + 1);
      const decayTime = 0.8 / (i + 1);

      gain.gain.setValueAtTime(amplitude, startTime);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + decayTime);
      osc.start(startTime);
      osc.stop(startTime + decayTime + 0.1);
    });
  }

  function playPowerUpSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.25;

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

    const sparkleNotes = [1318.5, 1567.98, 1975.5];
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

  function playUndoSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.25;

    const osc1 = ctx.createOscillator();
    const gain1 = ctx.createGain();
    osc1.connect(gain1);
    gain1.connect(masterGain);
    osc1.type = 'triangle';
    osc1.frequency.setValueAtTime(311.13, startTime);
    osc1.frequency.exponentialRampToValueAtTime(233.08, startTime + 0.25);
    gain1.gain.setValueAtTime(0.6, startTime);
    gain1.gain.exponentialRampToValueAtTime(0.3, startTime + 0.2);
    gain1.gain.exponentialRampToValueAtTime(0.01, startTime + 0.3);
    osc1.start(startTime);
    osc1.stop(startTime + 0.35);

    const osc2 = ctx.createOscillator();
    const gain2 = ctx.createGain();
    osc2.connect(gain2);
    gain2.connect(masterGain);
    osc2.type = 'triangle';
    osc2.frequency.setValueAtTime(233.08, startTime + 0.3);
    osc2.frequency.exponentialRampToValueAtTime(155.56, startTime + 0.7);
    gain2.gain.setValueAtTime(0.5, startTime + 0.3);
    gain2.gain.exponentialRampToValueAtTime(0.25, startTime + 0.55);
    gain2.gain.exponentialRampToValueAtTime(0.01, startTime + 0.75);
    osc2.start(startTime + 0.3);
    osc2.stop(startTime + 0.8);

    const osc3 = ctx.createOscillator();
    const gain3 = ctx.createGain();
    osc3.connect(gain3);
    gain3.connect(masterGain);
    osc3.type = 'sine';
    osc3.frequency.setValueAtTime(116.54, startTime + 0.5);
    gain3.gain.setValueAtTime(0.15, startTime + 0.5);
    gain3.gain.exponentialRampToValueAtTime(0.01, startTime + 0.8);
    osc3.start(startTime + 0.5);
    osc3.stop(startTime + 0.85);
  }

  function playFartSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.9;

    const noiseLength = ctx.sampleRate * 0.5;
    const noiseBuffer = ctx.createBuffer(1, noiseLength, ctx.sampleRate);
    const noiseData = noiseBuffer.getChannelData(0);

    let lastOut = 0;
    for (let i = 0; i < noiseLength; i++) {
      const white = Math.random() * 2 - 1;
      noiseData[i] = (lastOut + (0.04 * white)) / 1.04;
      lastOut = noiseData[i];
      noiseData[i] *= 8;
    }

    const noiseSource = ctx.createBufferSource();
    noiseSource.buffer = noiseBuffer;

    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(200, startTime);
    filter.frequency.exponentialRampToValueAtTime(80, startTime + 0.4);
    filter.Q.value = 2;

    const noiseGain = ctx.createGain();
    noiseGain.gain.setValueAtTime(0, startTime);
    noiseGain.gain.linearRampToValueAtTime(1.0, startTime + 0.01);
    noiseGain.gain.setValueAtTime(1.0, startTime + 0.15);
    noiseGain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.45);

    noiseSource.connect(filter);
    filter.connect(noiseGain);
    noiseGain.connect(masterGain);
    noiseSource.start(startTime);
    noiseSource.stop(startTime + 0.5);

    const bass = ctx.createOscillator();
    const bassGain = ctx.createGain();
    bass.type = 'sawtooth';
    bass.frequency.setValueAtTime(80, startTime);
    bass.frequency.exponentialRampToValueAtTime(40, startTime + 0.4);
    bassGain.gain.setValueAtTime(0, startTime);
    bassGain.gain.linearRampToValueAtTime(0.8, startTime + 0.02);
    bassGain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.45);
    bass.connect(bassGain);
    bassGain.connect(masterGain);
    bass.start(startTime);
    bass.stop(startTime + 0.5);

    const flap = ctx.createOscillator();
    const flapGain = ctx.createGain();
    flap.type = 'square';
    flap.frequency.setValueAtTime(25, startTime);
    flap.frequency.exponentialRampToValueAtTime(12, startTime + 0.4);
    flapGain.gain.setValueAtTime(0.6, startTime);
    flapGain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.4);
    flap.connect(flapGain);
    flapGain.connect(masterGain);
    flap.start(startTime);
    flap.stop(startTime + 0.45);

    const sub = ctx.createOscillator();
    const subGain = ctx.createGain();
    sub.type = 'sine';
    sub.frequency.setValueAtTime(50, startTime);
    sub.frequency.exponentialRampToValueAtTime(25, startTime + 0.3);
    subGain.gain.setValueAtTime(0.7, startTime);
    subGain.gain.exponentialRampToValueAtTime(0.01, startTime + 0.35);
    sub.connect(subGain);
    subGain.connect(masterGain);
    sub.start(startTime);
    sub.stop(startTime + 0.4);
  }

  function playFartLongSound(ctx, startTime) {
    const masterGain = ctx.createGain();
    masterGain.connect(ctx.destination);
    masterGain.gain.value = 0.85;

    const noiseLength = ctx.sampleRate * 2.0;
    const noiseBuffer = ctx.createBuffer(1, noiseLength, ctx.sampleRate);
    const noiseData = noiseBuffer.getChannelData(0);

    let lastOut = 0;
    for (let i = 0; i < noiseLength; i++) {
      const white = Math.random() * 2 - 1;
      noiseData[i] = (lastOut + (0.05 * white)) / 1.05;
      lastOut = noiseData[i];
      noiseData[i] *= 7;
    }

    const noiseSource = ctx.createBufferSource();
    noiseSource.buffer = noiseBuffer;

    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(250, startTime);
    filter.frequency.linearRampToValueAtTime(180, startTime + 0.3);
    filter.frequency.linearRampToValueAtTime(280, startTime + 0.5);
    filter.frequency.linearRampToValueAtTime(150, startTime + 0.9);
    filter.frequency.linearRampToValueAtTime(220, startTime + 1.2);
    filter.frequency.exponentialRampToValueAtTime(60, startTime + 1.8);
    filter.Q.value = 3;

    const noiseGain = ctx.createGain();
    noiseGain.gain.setValueAtTime(0, startTime);
    noiseGain.gain.linearRampToValueAtTime(1.0, startTime + 0.02);
    noiseGain.gain.linearRampToValueAtTime(0.7, startTime + 0.4);
    noiseGain.gain.linearRampToValueAtTime(1.0, startTime + 0.6);
    noiseGain.gain.linearRampToValueAtTime(0.5, startTime + 1.0);
    noiseGain.gain.linearRampToValueAtTime(0.9, startTime + 1.3);
    noiseGain.gain.exponentialRampToValueAtTime(0.01, startTime + 1.9);

    noiseSource.connect(filter);
    filter.connect(noiseGain);
    noiseGain.connect(masterGain);
    noiseSource.start(startTime);
    noiseSource.stop(startTime + 2.0);

    const bass = ctx.createOscillator();
    const bassGain = ctx.createGain();
    bass.type = 'sawtooth';
    bass.frequency.setValueAtTime(90, startTime);
    bass.frequency.linearRampToValueAtTime(70, startTime + 0.5);
    bass.frequency.linearRampToValueAtTime(100, startTime + 0.8);
    bass.frequency.linearRampToValueAtTime(50, startTime + 1.3);
    bass.frequency.exponentialRampToValueAtTime(30, startTime + 1.8);
    bassGain.gain.setValueAtTime(0.8, startTime);
    bassGain.gain.exponentialRampToValueAtTime(0.01, startTime + 1.85);
    bass.connect(bassGain);
    bassGain.connect(masterGain);
    bass.start(startTime);
    bass.stop(startTime + 1.9);

    const flutter = ctx.createOscillator();
    const flutterGain = ctx.createGain();
    flutter.type = 'square';
    flutter.frequency.setValueAtTime(35, startTime);
    flutter.frequency.linearRampToValueAtTime(20, startTime + 0.8);
    flutter.frequency.linearRampToValueAtTime(28, startTime + 1.0);
    flutter.frequency.exponentialRampToValueAtTime(6, startTime + 1.8);
    flutterGain.gain.setValueAtTime(0.7, startTime);
    flutterGain.gain.exponentialRampToValueAtTime(0.01, startTime + 1.8);
    flutter.connect(flutterGain);
    flutterGain.connect(masterGain);
    flutter.start(startTime);
    flutter.stop(startTime + 1.85);

    const sub = ctx.createOscillator();
    const subGain = ctx.createGain();
    sub.type = 'sine';
    sub.frequency.setValueAtTime(45, startTime);
    sub.frequency.exponentialRampToValueAtTime(20, startTime + 1.7);
    subGain.gain.setValueAtTime(0.6, startTime);
    subGain.gain.exponentialRampToValueAtTime(0.01, startTime + 1.75);
    sub.connect(subGain);
    subGain.connect(masterGain);
    sub.start(startTime);
    sub.stop(startTime + 1.8);

    const squeakTimes = [0.5, 1.2];
    squeakTimes.forEach((delay) => {
      const squeak = ctx.createOscillator();
      const squeakGain = ctx.createGain();
      squeak.type = 'triangle';
      squeak.frequency.setValueAtTime(180, startTime + delay);
      squeak.frequency.exponentialRampToValueAtTime(120, startTime + delay + 0.15);
      squeakGain.gain.setValueAtTime(0.4, startTime + delay);
      squeakGain.gain.exponentialRampToValueAtTime(0.01, startTime + delay + 0.15);
      squeak.connect(squeakGain);
      squeakGain.connect(masterGain);
      squeak.start(startTime + delay);
      squeak.stop(startTime + delay + 0.2);
    });
  }

  /**
   * Play a sound by name
   */
  function playSound(soundName) {
    if (!soundName || soundName === 'none') {
      console.debug('[Choremander Config] No sound to play');
      return;
    }

    try {
      const ctx = getAudioContext();
      const now = ctx.currentTime;

      switch (soundName) {
        case 'coin': playCoinSound(ctx, now); break;
        case 'levelup': playLevelUpSound(ctx, now); break;
        case 'fanfare': playFanfareSound(ctx, now); break;
        case 'chime': playChimeSound(ctx, now); break;
        case 'powerup': playPowerUpSound(ctx, now); break;
        case 'undo': playUndoSound(ctx, now); break;
        case 'fart': playFartSound(ctx, now); break;
        case 'fart_long': playFartLongSound(ctx, now); break;
        default:
          console.warn(`[Choremander Config] Unknown sound: ${soundName}`);
          playCoinSound(ctx, now);
      }
    } catch (e) {
      console.warn('[Choremander Config] Error playing sound:', e);
    }
  }

  // Valid sound names
  const VALID_SOUNDS = ['coin', 'levelup', 'fanfare', 'chime', 'powerup', 'undo', 'fart', 'fart_long', 'none'];

  /**
   * Map display text to sound value
   */
  function textToSoundValue(text) {
    if (!text) return null;
    const normalized = text.toLowerCase().trim().replace(/\s+/g, '_');
    const map = {
      'no_sound': 'none',
      'no sound': 'none',
      'coin': 'coin',
      'levelup': 'levelup',
      'level_up': 'levelup',
      'fanfare': 'fanfare',
      'chime': 'chime',
      'powerup': 'powerup',
      'power_up': 'powerup',
      'undo': 'undo',
      'fart': 'fart',
      'fart_long': 'fart_long',
    };
    return map[normalized] || (VALID_SOUNDS.includes(normalized) ? normalized : null);
  }

  /**
   * Attach change listener to a select element
   */
  function attachSoundChangeListener(element) {
    if (element.dataset.choremanderSoundListener) return;
    element.dataset.choremanderSoundListener = 'true';

    // Listen for various change events
    const handleChange = (e) => {
      const value = e.target?.value || e.detail?.value;
      const soundValue = textToSoundValue(value) || value;

      console.debug('[Choremander Config] Sound changed to:', soundValue);

      if (soundValue && soundValue !== 'none' && VALID_SOUNDS.includes(soundValue)) {
        playSound(soundValue);
      }
    };

    element.addEventListener('change', handleChange);
    element.addEventListener('value-changed', handleChange);
    element.addEventListener('selected', handleChange);
    element.addEventListener('click', (e) => {
      // For dropdown items being clicked
      const item = e.target.closest('mwc-list-item, ha-list-item, [role="option"]');
      if (item) {
        const value = item.value || item.getAttribute('value') || item.textContent;
        const soundValue = textToSoundValue(value);
        if (soundValue && soundValue !== 'none') {
          setTimeout(() => playSound(soundValue), 50);
        }
      }
    });

    console.debug('[Choremander Config] Attached sound change listener to element');
  }

  /**
   * Find sound selectors and attach listeners
   */
  function findAndEnhanceSoundSelectors() {
    // Look for any select/dropdown that might be for sounds
    const selectors = document.querySelectorAll('ha-select, mwc-select, ha-combo-box, select');

    selectors.forEach(selector => {
      // Check if this selector has sound-related options
      const options = selector.querySelectorAll('mwc-list-item, ha-list-item, option, [role="option"]');
      let isSoundSelector = false;

      options.forEach(opt => {
        const text = (opt.value || opt.getAttribute('value') || opt.textContent || '').toLowerCase();
        if (VALID_SOUNDS.some(s => text.includes(s))) {
          isSoundSelector = true;
        }
      });

      // Also check the selector's current value
      const currentValue = (selector.value || '').toLowerCase();
      if (VALID_SOUNDS.some(s => currentValue.includes(s))) {
        isSoundSelector = true;
      }

      if (isSoundSelector) {
        attachSoundChangeListener(selector);

        // Also attach to inner elements if present
        const innerSelect = selector.shadowRoot?.querySelector('select, mwc-menu, mwc-list');
        if (innerSelect) {
          attachSoundChangeListener(innerSelect);
        }
      }
    });

    // Also look for ha-selector elements (HA's custom form selectors)
    document.querySelectorAll('ha-selector').forEach(haSelector => {
      const innerSelect = haSelector.shadowRoot?.querySelector('ha-select, mwc-select') ||
                         haSelector.querySelector('ha-select, mwc-select');
      if (innerSelect) {
        const options = innerSelect.querySelectorAll('mwc-list-item, [role="option"]');
        let isSoundSelector = false;
        options.forEach(opt => {
          const text = (opt.value || opt.textContent || '').toLowerCase();
          if (VALID_SOUNDS.some(s => text.includes(s))) {
            isSoundSelector = true;
          }
        });
        if (isSoundSelector) {
          attachSoundChangeListener(innerSelect);
        }
      }
    });
  }

  /**
   * Watch for DOM changes and enhance new sound selectors
   */
  function startObserver() {
    const observer = new MutationObserver((mutations) => {
      let shouldScan = false;

      mutations.forEach((mutation) => {
        if (mutation.addedNodes.length > 0) {
          shouldScan = true;
        }
      });

      if (shouldScan) {
        // Debounce scanning
        clearTimeout(window._choremanderScanTimeout);
        window._choremanderScanTimeout = setTimeout(findAndEnhanceSoundSelectors, 100);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });

    console.debug('[Choremander Config] Sound change observer started');
  }

  // Initialize
  function init() {
    findAndEnhanceSoundSelectors();
    startObserver();

    // Periodic scan to catch dynamically loaded content
    setInterval(findAndEnhanceSoundSelectors, 2000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.addEventListener('load', () => setTimeout(init, 500));

  console.info('[Choremander] Config sound preview module loaded - sounds will play on selection change');
})();
