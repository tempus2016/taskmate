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

  // Default companion entity ids. TaskMate is a single-instance integration
  // (config_flow enforces unique_id == DOMAIN), but these are only the ids
  // Home Assistant generates by default: since 2026.6 a new entity on a device
  // with an area gets the area in front ("sensor.familie_taskmate_bounties"),
  // and users rename entities. The overview sensor publishes the real ids as
  // `companion_entities`, keyed by the part after "sensor.taskmate_" (#1018);
  // these defaults are the fallback when that map is missing.
  const COMPANIONS = [
    "sensor.taskmate_chores",
    "sensor.taskmate_chore_availability",
    "sensor.taskmate_rewards",
    "sensor.taskmate_activity",
    "sensor.taskmate_incentives",
    // Full pending-approvals lists (chore_completions / reward_claims). These
    // are NOT filtered to today, so approval cards pointed at the overview
    // entity can still surface a completion left pending from a previous day.
    // Named "Pending Approvals", but it carries no _attr_has_entity_name, so
    // the TaskMate device name still prefixes its entity id. This entry was
    // missing that prefix and so matched nothing at all, silently dropping
    // chore_completions and mandatory_misses from every merge (#798).
    "sensor.taskmate_pending_approvals",
    // The bounty board (#931): `bounties` for the bounty card.
    "sensor.taskmate_bounties",
    // Chore auctions (#982): `auctions`, a digest with no bid amounts. The
    // auction card re-fetches its own view over the WebSocket when it moves.
    "sensor.taskmate_auctions",
    // The Today page's chore board (#1017): `chore_board` for the board card.
    "sensor.taskmate_chore_board",
  ];

  // Attributes a companion must NOT contribute to the merge, because another
  // sensor already owns that name for different data (#834).
  //
  // sensor.taskmate_pending_approvals publishes both the full lists and a
  // scalar count of each. Its `pending_reward_claims` count collides with
  // sensor.taskmate_rewards' `pending_reward_claims` LIST, and the approvals
  // sensor merges last, so the number won — every card that did
  // `claims.filter(...)` / `claims.some(...)` threw as soon as a claim was
  // pending, blanking the card. Zero pending claims hid it: the cards' own
  // `|| []` fallback catches a count of 0 because it is falsy, so the crash
  // only appeared once a child actually claimed something.
  //
  // Nothing reads these counts through the resolver — the admin panel takes
  // its badge counts from the taskmate/get_state WebSocket call and the cards
  // derive theirs from the lists' length. They stay readable directly off
  // sensor.taskmate_pending_approvals for templates and automations.
  const COMPANION_SKIP_KEYS = {
    "sensor.taskmate_pending_approvals": [
      "pending_chore_completions",
      "pending_reward_claims",
      "pending_mandatory_misses",
    ],
  };

  const DEFAULT_PREFIX = "sensor.taskmate_";
  const OVERVIEW_ENTITY = "sensor.taskmate_overview";

  // The overview's entity map (#1018). Looked up under its default id first,
  // then on whichever state carries it, in case the overview was renamed too.
  function entityMap(hass) {
    const ov = hass.states[OVERVIEW_ENTITY];
    if (ov && ov.attributes && ov.attributes.companion_entities) return ov.attributes;
    for (const id in hass.states) {
      const st = hass.states[id];
      if (st && st.attributes && st.attributes.companion_entities) return st.attributes;
    }
    return null;
  }

  // [defaultId, realId] for every companion, cached per hass.states object.
  let _idCache = { stateRef: null, pairs: null, badges: null };

  function resolvedIds(hass) {
    if (_idCache.stateRef !== hass.states) {
      const map = entityMap(hass);
      const real = (map && map.companion_entities) || {};
      _idCache = {
        stateRef: hass.states,
        pairs: COMPANIONS.map((id) => [id, real[id.slice(DEFAULT_PREFIX.length)] || id]),
        badges: (map && map.badge_entities) || {},
      };
    }
    return _idCache;
  }

  function mergedAttributes(hass, primaryEntityId) {
    if (!hass || !hass.states) return {};
    const merged = {};
    const primary = hass.states[primaryEntityId];
    if (primary && primary.attributes) {
      Object.assign(merged, primary.attributes);
    }
    for (const [defaultId, id] of resolvedIds(hass).pairs) {
      const s = hass.states[id];
      if (!s || !s.attributes) continue;
      const skip = COMPANION_SKIP_KEYS[defaultId];
      if (!skip) {
        Object.assign(merged, s.attributes);
        continue;
      }
      for (const [key, value] of Object.entries(s.attributes)) {
        if (!skip.includes(key)) merged[key] = value;
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
   * The children a family-wide card lists (#1061). Grown-ups' profiles stay
   * out unless the card sets show_adults, and when shown they follow the
   * kids. A card pinned to one child_id gets the full list back, so an adult
   * can still have a card of their own.
   */
  function familyChildren(children, config) {
    const list = Array.isArray(children) ? children : [];
    if (!list.some(c => c && c.is_adult) || (config && config.child_id)) return list;
    const kids = list.filter(c => !c.is_adult);
    return config && config.show_adults === true ? kids.concat(list.filter(c => c.is_adult)) : kids;
  }

  window.__taskmate_family_children = familyChildren;

  /**
   * The editor's "Show grown-ups" toggle, as ha-form schema entries. Only
   * offered once the family has an adult profile (or the card already has
   * the option set), so everyone else's editor stays as it was.
   */
  function adultsEditorField(hass, config) {
    const attrs = (config && config.entity && resolveAttrs(hass, config.entity)) || {};
    const hasAdult = (attrs.children || []).some(c => c && c.is_adult);
    return hasAdult || (config && config.show_adults) ? [{ name: "show_adults", selector: { boolean: {} } }] : [];
  }

  window.__taskmate_adults_field = adultsEditorField;

  /**
   * A child's badges sensor state, by child id, from the overview's entity
   * map (#1018). Null when the map doesn't list one — callers fall back to
   * guessing from the default entity id.
   */
  function badgesState(hass, childId) {
    if (!hass || !hass.states || childId == null) return null;
    const id = resolvedIds(hass).badges[String(childId)];
    return (id && hass.states[id]) || null;
  }

  window.__taskmate_badges_state = badgesState;

  /**
   * Non-admin parent role (#661). True for Home Assistant admins and for users
   * the admin has designated as TaskMate parents (published as the
   * parent_user_ids attribute on sensor.taskmate_overview). Parents get the
   * day-to-day controls (approve/reject, complete-on-behalf, undo) without HA
   * admin rights. Admin remains the only tier that can open the admin panel or
   * change configuration.
   */
  function isTaskmateParent(hass) {
    if (!hass || !hass.user) return false;
    if (hass.user.is_admin) return true;
    let ids;
    const ov = hass.states && hass.states["sensor.taskmate_overview"];
    if (ov && ov.attributes && Array.isArray(ov.attributes.parent_user_ids)) {
      ids = ov.attributes.parent_user_ids;
    } else if (hass.states) {
      // Overview sensor renamed: find whichever taskmate sensor carries the list.
      for (const st of Object.values(hass.states)) {
        if (st && st.attributes && Array.isArray(st.attributes.parent_user_ids)) {
          ids = st.attributes.parent_user_ids;
          break;
        }
      }
    }
    return Array.isArray(ids) && ids.includes(hass.user.id);
  }

  window.__taskmate_is_parent = isTaskmateParent;

  /**
   * Stable id of a badge entry from the badges sensor.
   *
   * ChildBadgesSensor publishes earned/available entries keyed `badge_id`, but
   * several card templates were written against `b.id` — undefined on those
   * entries, so every "is this the badge that was just earned?" test compared
   * against the string "undefined" and never matched (#752). Read the id
   * through this helper so both spellings work.
   */
  function badgeId(badge) {
    if (!badge) return "";
    const id = badge.badge_id != null ? badge.badge_id : badge.id;
    return id != null ? String(id) : "";
  }

  window.__taskmate_badge_id = badgeId;

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

  // HA's RTL flag for the language, as taskmate-design.js direction() reads it.
  function isRTL(hass) {
    const meta = hass.translationMetadata && hass.translationMetadata.translations;
    const entry = meta && hass.language && meta[hass.language];
    return entry ? !!entry.isRTL : undefined;
  }

  function hasRelevantChange(oldHass, newHass, primaryEntityId) {
    if (!oldHass || !oldHass.states || !newHass || !newHass.states) return true;
    // A language change (#994) keeps the same states object, but every card
    // renders translated strings and stamps dir from the language.
    if (oldHass.language !== newHass.language) return true;
    if (isRTL(oldHass) !== isRTL(newHass)) return true;
    if (oldHass.states === newHass.states) return false;

    if (primaryEntityId) {
      if (oldHass.states[primaryEntityId] !== newHass.states[primaryEntityId]) return true;
    }

    for (const [, id] of resolvedIds(newHass).pairs) {
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

  /**
   * Set times (several times a day). A chore with `times` comes up at set
   * times of day and is ticked off once per time. The chores sensor carries
   * the times and, per child, which ones are done or pending
   * (`time_done`); the clock decides the rest:
   *   now     open, can be ticked
   *   later   not open yet
   *   missed  closed without a tick
   *   done / pending  ticked (pending = waiting for approval)
   * The window closes at `end` plus the chore's claim allowance, capped at
   * midnight, matching the backend. Shared by every card so the states never
   * disagree between the child card, the kiosk and the weekly card.
   */
  function _hhmm(value) {
    const m = /^(\d{1,2}):(\d{2})$/.exec(String(value || ""));
    if (!m) return null;
    const h = Number(m[1]);
    const mm = Number(m[2]);
    return h > 23 || mm > 59 ? null : h * 60 + mm;
  }

  function nowMinutes(hass, now) {
    const tz = (hass && hass.config && hass.config.time_zone) || Intl.DateTimeFormat().resolvedOptions().timeZone;
    try {
      const parts = new Intl.DateTimeFormat("en-US", { timeZone: tz, hour: "numeric", minute: "numeric", hourCycle: "h23" })
        .formatToParts(now || new Date());
      const get = (t) => Number((parts.find((p) => p.type === t) || {}).value || 0);
      return (get("hour") % 24) * 60 + get("minute");
    } catch (_e) {
      const d = now || new Date();
      return d.getHours() * 60 + d.getMinutes();
    }
  }

  function setTimeStates(chore, childId, hass, now) {
    const times = (chore && Array.isArray(chore.times)) ? chore.times : [];
    if (!times.length) return [];
    const done = ((chore.time_done || {})[String(childId)]) || {};
    const minutes = nowMinutes(hass, now);
    const grace = Math.max(0, Number(chore.claim_allowance_minutes) || 0);
    return times.map((t) => {
      const opens = _hhmm(t.start);
      const ends = _hhmm(t.end);
      const closes = Math.min((ends == null ? 0 : ends) + grace, 24 * 60);
      let state;
      if (done[t.id] === "done") state = "done";
      else if (done[t.id] === "pending") state = "pending";
      else if (opens != null && minutes < opens) state = "later";
      else if (minutes >= closes) state = "missed";
      else state = "now";
      return { time: t, state, opens: t.start, closes: `${String(Math.floor(closes / 60) % 24).padStart(2, "0")}:${String(closes % 60).padStart(2, "0")}` };
    });
  }

  /** The time a single-row (pills) view acts on: the open one, else the next
   *  to come, else a missed one (the day finished with a miss, so the row
   *  must not read as done), else the last of the day (every time done). */
  function setTimeFocus(entries) {
    if (!entries || !entries.length) return null;
    return entries.find((e) => e.state === "now")
      || entries.find((e) => e.state === "later")
      || entries.find((e) => e.state === "missed")
      || entries[entries.length - 1];
  }

  /** "rows" or "pills": a card's own `set_times_layout` wins, else the
   *  family setting on the overview sensor. */
  function setTimesLayout(attrs, config) {
    const own = config && config.set_times_layout;
    if (own === "rows" || own === "pills") return own;
    const fam = attrs && attrs.settings && attrs.settings.set_times_layout;
    const top = attrs && attrs.set_times_layout;
    return (fam || top) === "pills" ? "pills" : "rows";
  }

  window.__taskmate_set_times = {
    states: setTimeStates,
    focus: setTimeFocus,
    layout: setTimesLayout,
    nowMinutes,
  };

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
