/**
 * TaskMate sound preview bridge.
 *
 * Loaded on every HA frontend page (see GLOBAL_MODULES in frontend.py) so the
 * `taskmate.preview_sound` service can make a browser actually play something.
 *
 * This file used to carry a second, hand-maintained copy of every synthesised
 * sound plus a MutationObserver that scanned the document for anything looking
 * like a sound dropdown. Both had rotted: the copy still only knew the
 * long-removed "fart"/"fart_long" names while the real list had moved on to
 * fart1..fart10, and the scan could never reach the admin panel's sound picker
 * because that lives inside a shadow root. The panel now previews sounds
 * directly through window.__taskmate_sounds, so all that is gone; playback
 * lives in taskmate-sounds.js and this file is just the event bridge.
 */

(function () {
  "use strict";

  function play(sound) {
    const engine = window.__taskmate_sounds;
    if (engine && sound) engine.play(sound, window.__taskmate_custom_sounds || []);
  }

  function onPreview(e) {
    const sound = (e.detail && (e.detail.sound || (e.detail.data && e.detail.data.sound))) || null;
    if (sound) play(sound);
  }

  if (!window._taskmateConfigSoundsInit) {
    window._taskmateConfigSoundsInit = true;
    document.addEventListener("taskmate_preview_sound", onPreview);
    window.addEventListener("taskmate_preview_sound", onPreview);
  }
})();
