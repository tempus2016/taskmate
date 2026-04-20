/**
 * TaskMate attribute resolver.
 *
 * The overview sensor used to expose every data slice (chores, rewards,
 * recent activity, penalties, bonuses) as attributes of
 * sensor.taskmate_overview. That payload routinely exceeded Home Assistant's
 * 16 KB recorder limit, so the data is now split across companion sensors
 * (sensor.taskmate_chores, _rewards, _activity, _incentives).
 *
 * To keep existing Lovelace dashboards working unchanged, every card reads
 * attributes through window.__taskmate_attrs(hass, primaryEntityId), which
 * returns a merged attribute object: primary attributes plus each companion
 * sensor's attributes overlaid on top. If a companion sensor is missing
 * (e.g. older backend), its keys fall back to the primary sensor's
 * attributes. Cards therefore do not need to know which sensor owns which
 * attribute — lookup is transparent.
 */

(function () {
  "use strict";

  // Fixed companion entity ids. TaskMate is a single-instance integration
  // (config_flow enforces unique_id == DOMAIN), so these ids are stable.
  const COMPANIONS = [
    "sensor.taskmate_chores",
    "sensor.taskmate_chore_availability",
    "sensor.taskmate_rewards",
    "sensor.taskmate_activity",
    "sensor.taskmate_incentives",
  ];

  function mergedAttributes(hass, primaryEntityId) {
    if (!hass || !hass.states) return {};
    const merged = {};
    const primary = hass.states[primaryEntityId];
    if (primary && primary.attributes) {
      Object.assign(merged, primary.attributes);
    }
    for (const id of COMPANIONS) {
      const s = hass.states[id];
      if (s && s.attributes) {
        Object.assign(merged, s.attributes);
      }
    }
    return merged;
  }

  // Cache merged attributes per hass/primary tuple so repeated card renders
  // during a single Home Assistant state update don't rebuild the object.
  let _cache = { stateRef: null, byPrimary: new Map() };

  function resolveAttrs(hass, primaryEntityId) {
    if (!hass) return {};
    if (_cache.stateRef !== hass.states) {
      _cache = { stateRef: hass.states, byPrimary: new Map() };
    }
    if (!_cache.byPrimary.has(primaryEntityId)) {
      _cache.byPrimary.set(primaryEntityId, mergedAttributes(hass, primaryEntityId));
    }
    return _cache.byPrimary.get(primaryEntityId);
  }

  window.__taskmate_attrs = resolveAttrs;
})();
