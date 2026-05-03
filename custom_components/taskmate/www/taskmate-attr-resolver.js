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

  /**
   * Event-driven update guard for LitElement cards.
   *
   * HA sets a new `hass` object on every card whenever ANY entity changes.
   * Cards that don't filter will re-render for every light toggle, thermostat
   * update, etc. This helper compares only TaskMate-relevant entities so
   * cards skip renders that can't possibly change their output.
   *
   * Usage inside a card class:
   *   shouldUpdate(changedProps) {
   *     if (changedProps.has("hass")) {
   *       return window.__taskmate_hasChanged(changedProps.get("hass"), this.hass, this.config?.entity);
   *     }
   *     return true;
   *   }
   */
  const TASKMATE_BUTTON_PREFIX = "button.taskmate_";

  function hasRelevantChange(oldHass, newHass, primaryEntityId) {
    if (!oldHass || !oldHass.states || !newHass || !newHass.states) return true;
    if (oldHass.states === newHass.states) return false;

    if (primaryEntityId) {
      if (oldHass.states[primaryEntityId] !== newHass.states[primaryEntityId]) return true;
    }

    for (const id of COMPANIONS) {
      if (oldHass.states[id] !== newHass.states[id]) return true;
    }

    for (const id in newHass.states) {
      if (id.startsWith(TASKMATE_BUTTON_PREFIX)) {
        if (oldHass.states[id] !== newHass.states[id]) return true;
      }
    }

    return false;
  }

  window.__taskmate_hasChanged = hasRelevantChange;

  /**
   * Find the entity id of a TaskMate button by (child_id, action, target_id).
   *
   * TaskMate creates per-child/per-chore and per-child/per-reward button
   * entities. Lovelace cards used to call the backend services directly
   * (e.g. taskmate.complete_chore), which bypassed the button entity and
   * left its last_pressed state unchanged — so HA state-trigger automations
   * on button.taskmate_<child>_complete_<chore> never fired. Cards now
   * resolve the matching button entity and call button.press, making the
   * card and the HA entity the same code path.
   *
   * action: "complete" (chore) | "claim" (reward)
   * target_id: chore_id or reward_id
   */
  function findButtonEntity(hass, childId, action, targetId) {
    if (!hass || !hass.states || !childId || !targetId) return null;
    const targetKey = action === "claim" ? "reward_id" : "chore_id";
    for (const [entityId, state] of Object.entries(hass.states)) {
      if (!entityId.startsWith("button.taskmate_")) continue;
      const attrs = state && state.attributes;
      if (!attrs) continue;
      if (attrs.child_id !== childId) continue;
      if (attrs[targetKey] !== targetId) continue;
      // Disambiguate chore complete vs reward claim — both carry child_id,
      // but only one of chore_id / reward_id.
      if (action === "claim" && !("reward_id" in attrs)) continue;
      if (action === "complete" && !("chore_id" in attrs)) continue;
      return entityId;
    }
    return null;
  }

  window.__taskmate_find_button = findButtonEntity;

  // Cold-cache fix: if any TaskMate cards already mounted before this module
  // finished loading, they fell back to entity.attributes (overview-only) and
  // rendered empty chore lists. Walk the DOM (crossing shadow roots, since HA
  // nests Lovelace inside several shadow trees) and force a re-render now
  // that window.__taskmate_attrs is defined.
  function _refreshTaskMateCards() {
    const stack = [document];
    while (stack.length) {
      const node = stack.pop();
      if (!node) continue;
      if (node.tagName && node.tagName.startsWith("TASKMATE-")) {
        if (typeof node.requestUpdate === "function") {
          try { node.requestUpdate(); } catch (_e) { /* ignore */ }
        }
      }
      if (node.shadowRoot) stack.push(node.shadowRoot);
      const children = node.children;
      if (children) {
        for (let i = 0; i < children.length; i++) stack.push(children[i]);
      }
    }
  }
  queueMicrotask(_refreshTaskMateCards);
})();
