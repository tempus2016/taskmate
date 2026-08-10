"""Assignment operations mixin for TaskMateCoordinator."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import date
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .models import Chore, optional_float

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class AssignmentsMixin:
    """Mixin providing assignment rotation, availability, and visibility logic."""

    def _refresh_tracked_availability_entities(self) -> None:
        """Rebuild the cached set of external entities TaskMate reacts to.

        Two groups, kept apart because they trigger different work:

          * child availability/unavailability entities — a change here can
            re-assign a rotation chore, so it schedules a re-evaluation;
          * chore visibility and weather entities — a change here only alters
            what's *visible*, so it just invalidates the sensor attribute cache.

        Children and chores only change via mutations (which trigger a
        coordinator refresh), so this is rebuilt on refresh rather than on
        every bus state_changed event — which fires for every entity in HA
        (PERF-5).
        """
        availability: set[str] = set()
        for c in self.storage.get_children():
            if getattr(c, "availability_entity", ""):
                availability.add(c.availability_entity)
            if getattr(c, "unavailability_entity", ""):
                availability.add(c.unavailability_entity)
        self._tracked_availability_entities = availability

        visibility: set[str] = set()
        for chore in self.storage.get_chores():
            if getattr(chore, "visibility_entity", ""):
                visibility.add(chore.visibility_entity)
            if getattr(chore, "weather_entity", ""):
                visibility.add(chore.weather_entity)
        self._tracked_visibility_entities = visibility

    @callback
    def _availability_state_changed(self, event: Any) -> None:
        """Cheap bus-filter: react only when a tracked entity changes.

        Decorated @callback so it runs on the event loop (a plain listener runs
        in the executor, where async_create_task raises) and reads the cached
        tracked-entity sets rather than rescanning all children per event.
        """
        data = getattr(event, "data", None) or {}
        entity_id = data.get("entity_id")
        if not entity_id:
            return

        is_availability = entity_id in getattr(self, "_tracked_availability_entities", set())
        is_visibility = entity_id in getattr(self, "_tracked_visibility_entities", set())
        if not (is_availability or is_visibility):
            return

        # The data snapshot is reused while storage.data_version is unchanged,
        # so without this the chores/availability sensors would keep serving
        # attributes computed against the old entity state.
        self.external_state_version += 1

        if is_availability:
            self.hass.async_create_task(self._async_reevaluate_availability())

    async def _async_reevaluate_availability(self) -> None:
        """Re-run assignment for require_availability chores when availability flips.

        Skips chores that already have a completion today so we don't phantom-
        reassign a chore a child already ticked off. Only non-`everyone` modes
        cache a single current child on the chore; `everyone` mode resolves
        availability at read-time via `_compute_active_children`.
        """
        today = dt_util.as_local(dt_util.now()).date()
        completions_today: set[str] = set()
        for comp in self.storage.get_completions():
            try:
                comp_date = dt_util.as_local(comp.completed_at).date()
            except (AttributeError, TypeError, ValueError):
                continue
            if comp_date == today:
                completions_today.add(comp.chore_id)

        # Use the group-aware daily map so sticky/spread policies are honored
        # when an availability flip causes a shift.
        daily = self._compute_daily_assignments(today)

        changed = False
        for chore in self.storage.get_chores():
            if not getattr(chore, "require_availability", False):
                continue
            if getattr(chore, "assignment_mode", "everyone") == "everyone":
                continue
            if chore.id in completions_today:
                continue
            desired = daily.get(chore.id, "")
            if getattr(chore, "assignment_current_child_id", "") != desired:
                chore.assignment_current_child_id = desired
                self.storage.update_chore(chore)
                changed = True

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    _AVAILABLE_STATES: frozenset[str] = frozenset(
        {
            "on",
            "home",
            "available",
            "present",
            "true",
        }
    )

    def _is_visibility_entity_active(
        self, visibility_entity: str, visibility_state: str, visibility_operator: str = "equals"
    ) -> bool:
        """Check if a visibility entity matches the desired state.

        Args:
            visibility_entity: Entity ID to check (e.g. 'binary_sensor.dishwasher')
            visibility_state: State value to compare (e.g. 'on', '123', '10', '>=10', '<20')
            visibility_operator: Comparison operator: equals, gte, lte, gt, lt, not_equals

        Returns True if entity matches visibility_state with the specified operator.
        Defaults to visible if entity doesn't exist.
        """
        if not visibility_entity or visibility_operator == "none":
            return True

        # Default empty operator/state to sensible values
        if not visibility_operator:
            visibility_operator = "equals"
        if not visibility_state:
            visibility_state = "on"

        # Get entity state from Home Assistant
        state_obj = self.hass.states.get(visibility_entity)
        if state_obj is None:
            # Entity doesn't exist, treat as visible
            _LOGGER.debug(
                "Visibility entity '%s' not found, defaulting to visible",
                visibility_entity,
            )
            return True

        entity_state = state_obj.state

        # Parse operator from visibility_state if embedded (e.g. ">=10", "<20")
        parsed_operator = visibility_operator
        parsed_state = visibility_state

        if visibility_state.startswith(">="):
            parsed_operator = "gte"
            parsed_state = visibility_state[2:]
        elif visibility_state.startswith("<="):
            parsed_operator = "lte"
            parsed_state = visibility_state[2:]
        elif visibility_state.startswith(">"):
            parsed_operator = "gt"
            parsed_state = visibility_state[1:]
        elif visibility_state.startswith("<"):
            parsed_operator = "lt"
            parsed_state = visibility_state[1:]
        elif visibility_state.startswith("!="):
            parsed_operator = "not_equals"
            parsed_state = visibility_state[2:]

        # Try numeric comparison if operator is not "equals"
        if parsed_operator != "equals":
            try:
                threshold = float(parsed_state)
                entity_value = float(entity_state)

                if parsed_operator == "gte":
                    return entity_value >= threshold
                elif parsed_operator == "lte":
                    return entity_value <= threshold
                elif parsed_operator == "gt":
                    return entity_value > threshold
                elif parsed_operator == "lt":
                    return entity_value < threshold
                elif parsed_operator == "not_equals":
                    return entity_value != threshold
            except (ValueError, TypeError):
                # If conversion fails, fall through to string matching
                pass

        # Check state (case-insensitive exact match)
        if entity_state.lower() == parsed_state.lower():
            return True

        # Check attributes for a matching value
        if hasattr(state_obj, "attributes") and state_obj.attributes:
            for attr_value in state_obj.attributes.values():
                if str(attr_value).lower() == parsed_state.lower():
                    return True

        return False

    # Reasons a weather-gated chore is currently hidden. Returned by
    # _weather_block_reason so the panel and sensor can explain the gap
    # rather than silently dropping the chore off the list.
    WEATHER_REASON_CONDITION = "condition"
    WEATHER_REASON_TEMP_LOW = "temp_low"
    WEATHER_REASON_TEMP_HIGH = "temp_high"
    WEATHER_REASON_WIND = "wind"

    def weather_block_reason(self, chore) -> str | None:
        """Return why the weather blocks this chore right now, else ``None``.

        Fail-open at every step: no entity configured, an entity that doesn't
        exist, an unavailable/unknown state, or a missing attribute all mean
        "not blocked". A weather integration going offline must never silently
        hide the family's chores.
        """
        entity_id = (getattr(chore, "weather_entity", "") or "").strip()
        if not entity_id:
            return None

        state_obj = self.hass.states.get(entity_id)
        if state_obj is None or state_obj.state in ("unavailable", "unknown", None, ""):
            _LOGGER.debug(
                "Weather entity '%s' unavailable, not blocking chore '%s'",
                entity_id,
                getattr(chore, "name", ""),
            )
            return None

        blocked = [str(c).lower() for c in (getattr(chore, "weather_block_conditions", []) or [])]
        if blocked and state_obj.state.lower() in blocked:
            return self.WEATHER_REASON_CONDITION

        attrs = getattr(state_obj, "attributes", {}) or {}

        temp = optional_float(attrs.get("temperature"))
        if temp is not None:
            temp_min = optional_float(getattr(chore, "weather_temp_min", None))
            if temp_min is not None and temp < temp_min:
                return self.WEATHER_REASON_TEMP_LOW
            temp_max = optional_float(getattr(chore, "weather_temp_max", None))
            if temp_max is not None and temp > temp_max:
                return self.WEATHER_REASON_TEMP_HIGH

        wind = optional_float(attrs.get("wind_speed"))
        if wind is not None:
            wind_max = optional_float(getattr(chore, "weather_wind_max", None))
            if wind_max is not None and wind > wind_max:
                return self.WEATHER_REASON_WIND

        return None

    def _is_weather_ok_for_chore(self, chore) -> bool:
        """True when current weather permits this chore (or no gate is set)."""
        return self.weather_block_reason(chore) is None

    def _is_child_available(self, child_id: str) -> bool:
        """Return True when the child should receive chores today.

        Two-step evaluation:
          1. availability_entity  — fail-open; if inverted, _AVAILABLE_STATES means BUSY.
             Inversion only applies to real states, not broken/missing sensors.
          2. unavailability_entity — neutral when missing; _AVAILABLE_STATES means BUSY.
        Final = step1 AND NOT step2.
        """
        child = self.storage.get_child(child_id)
        if not child:
            return True

        # Step 1: availability sensor (fail-open when broken/missing)
        avail_ok = True
        entity_id = getattr(child, "availability_entity", "") or ""
        if entity_id:
            raw = self._read_entity_active(entity_id)
            if raw is not None:
                avail_ok = raw
                if getattr(child, "availability_inverted", False):
                    avail_ok = not avail_ok

        # Step 2: unavailability sensor (neutral when broken/missing)
        busy = False
        unav_id = getattr(child, "unavailability_entity", "") or ""
        if unav_id:
            raw = self._read_entity_active(unav_id)
            if raw is not None:
                busy = raw

        return avail_ok and not busy

    def _read_entity_active(self, entity_id: str) -> bool | None:
        """Read an entity's state and return True if it's in _AVAILABLE_STATES,
        False if it's a real state not in the set, or None if the entity is
        missing/broken (unavailable/unknown/None) so callers can apply their
        own default.
        """
        state_obj = self.hass.states.get(entity_id)
        if state_obj is None:
            return None
        raw = getattr(state_obj, "state", None)
        if raw is None:
            return None
        value = str(raw).strip().lower()
        if value in ("unavailable", "unknown", "none", ""):
            return None
        return value in self._AVAILABLE_STATES

    def _chore_assignment_pool(self, chore: Chore) -> list[str]:
        """Resolve the ordered pool of child IDs this chore rotates through.

        Prefers the chore's `assigned_to` list. When empty, falls back to every
        stored child so "Everyone"-style chores can still alternate/randomize.
        """
        pool = [cid for cid in (chore.assigned_to or []) if self.storage.get_child(cid)]
        if pool:
            return pool
        return [child.id for child in self.storage.get_children()]

    def _compute_active_children(self, chore: Chore, today: date | None = None) -> list[str]:
        """Return the child IDs the chore is active for today.

        - everyone: whatever `assigned_to` already said (empty = all children).
        - alternating: one child picked by `(today - anchor).days % len(pool)`.
        - random: one child picked by a deterministic per-day+chore-id hash.
        - balanced: today's balanced-mode chores sharing this pool are evenly
          split across the pool via a round-robin anchored by the date — so 10
          chores across 2 children always land 5/5 (11 lands 6/5, etc.).

        When `chore.skip_date` matches today, `chore.skip_count` is added to the
        computed rotation index so the pointer advances past any children the
        parent has skipped. Stale skip state (skip_date != today) is ignored at
        read time and cleared during the midnight refresh.
        """
        # PERF-1: the active set depends only on the chore for "today" (the
        # availability matrix calls this per chore × child). Memoize per chore
        # within an availability build scope. Skip when an explicit `today` is
        # passed (callers that probe other days must not read today's cache).
        cache = getattr(self, "_avail_cache", None)
        if cache is not None and today is None:
            cached = cache["active"].get(chore.id)
            if cached is None:
                cached = self._compute_active_children_uncached(chore, None)
                cache["active"][chore.id] = cached
            return cached
        return self._compute_active_children_uncached(chore, today)

    def _compute_active_children_uncached(self, chore: Chore, today: date | None = None) -> list[str]:
        mode = getattr(chore, "assignment_mode", "everyone")
        require_availability = getattr(chore, "require_availability", False)

        if mode == "unassigned":
            return []

        if mode == "first_come":
            # Competitive: every child in the resolved pool sees it until the
            # first completion fills the shared quota (see _is_rotation_done_today).
            pool = self._chore_assignment_pool(chore)
            if require_availability:
                return [cid for cid in pool if self._is_child_available(cid)]
            return pool

        if mode not in ("alternating", "random", "balanced"):
            assigned = list(chore.assigned_to or [])
            if require_availability and assigned:
                return [cid for cid in assigned if self._is_child_available(cid)]
            return assigned

        pool = self._chore_assignment_pool(chore)
        if not pool:
            return []

        if today is None:
            today = dt_util.as_local(dt_util.now()).date()

        # Skip offset only applies when the skip was recorded today.
        skip_offset = 0
        if getattr(chore, "skip_date", "") == today.isoformat():
            skip_offset = int(getattr(chore, "skip_count", 0) or 0)

        if mode == "alternating":
            anchor_iso = getattr(chore, "assignment_rotation_anchor", "") or ""
            try:
                anchor = date.fromisoformat(anchor_iso) if anchor_iso else today
            except ValueError:
                anchor = today
            offset = (today - anchor).days
            idx = (offset + skip_offset) % len(pool)
            picked = self._skip_unavailable(pool, idx, require_availability)
            return [picked] if picked else []

        if mode == "random":
            # random: stable per (chore.id, date) so the frontend and backend agree
            digest = hashlib.sha256(f"{chore.id}:{today.toordinal()}".encode()).digest()
            idx = (int.from_bytes(digest[:8], "big") + skip_offset) % len(pool)
            picked = self._skip_unavailable(pool, idx, require_availability)
            return [picked] if picked else []

        # balanced: group today's balanced-mode chores that share this exact pool,
        # sort them by id for determinism, then round-robin across the pool. A
        # per-day start offset rotates who gets the "first" chore so no child is
        # always the one doing chore #1.
        pool_key = tuple(sorted(pool))
        group_ids = sorted(
            c.id
            for c in self.storage.get_chores()
            if getattr(c, "assignment_mode", "everyone") == "balanced"
            and tuple(sorted(self._chore_assignment_pool(c))) == pool_key
        )
        try:
            position = group_ids.index(chore.id)
        except ValueError:
            position = 0
        start_digest = hashlib.sha256(f"balanced:{pool_key}:{today.toordinal()}".encode()).digest()
        start = int.from_bytes(start_digest[:4], "big") % len(pool)
        idx = (start + position + skip_offset) % len(pool)
        picked = self._skip_unavailable(pool, idx, require_availability)
        return [picked] if picked else []

    def _compute_daily_assignments(self, today: date | None = None) -> dict[str, str]:
        """Compute today's assignment per rotation-mode chore, honoring groups.

        Returns a map of chore_id -> child_id. Only chores with a non-everyone
        assignment_mode are present. Task group policies (sticky / spread) are
        applied on top of the per-chore raw pick.
        """
        if today is None:
            today = dt_util.as_local(dt_util.now()).date()

        chores = self.storage.get_chores()
        chore_by_id: dict[str, Chore] = {c.id: c for c in chores}

        # Step 1: raw per-chore picks for rotation modes.
        result: dict[str, str] = {}
        for chore in chores:
            mode = getattr(chore, "assignment_mode", "everyone")
            if mode in ("everyone", "first_come"):
                continue
            active = self._compute_active_children(chore, today)
            if active:
                result[chore.id] = active[0]

        # Step 2: apply group policies.
        for group in self.storage.get_task_groups():
            if not group.chore_ids:
                continue
            if group.policy == "sticky":
                self._apply_sticky_policy(group, chore_by_id, result)
            elif group.policy == "spread":
                self._apply_spread_policy(group, chore_by_id, result)

        return result

    def _apply_sticky_policy(self, group, chore_by_id: dict[str, Chore], result: dict[str, str]) -> None:
        """Force followers onto the leader chore's assignee (when in pool)."""
        leader_id = group.chore_ids[0]
        leader_child = result.get(leader_id)
        if not leader_child:
            return
        for follower_id in group.chore_ids[1:]:
            follower = chore_by_id.get(follower_id)
            if not follower:
                continue
            if getattr(follower, "assignment_mode", "everyone") in ("everyone", "first_come"):
                continue
            pool = self._chore_assignment_pool(follower)
            if leader_child in pool:
                result[follower_id] = leader_child
            else:
                _LOGGER.debug(
                    "STICKY fallback: leader %s assigned to %s not in follower %s pool",
                    leader_id,
                    leader_child,
                    follower_id,
                )

    def _apply_spread_policy(self, group, chore_by_id: dict[str, Chore], result: dict[str, str]) -> None:
        """Assign group members to distinct children; wraps when pool < group size."""
        used: set[str] = set()
        for chore_id in group.chore_ids:
            chore = chore_by_id.get(chore_id)
            if not chore:
                continue
            if getattr(chore, "assignment_mode", "everyone") in ("everyone", "first_come"):
                continue
            pool = self._chore_assignment_pool(chore)
            if not pool:
                continue
            # Wrap: once every child in this pool has been used, start over.
            if len(used) >= len(pool) or all(p in used for p in pool):
                used = set()
            raw = result.get(chore_id) or pool[0]
            if raw not in used:
                result[chore_id] = raw
                used.add(raw)
                continue
            # Walk pool from raw pick looking for an unused child.
            try:
                start_idx = pool.index(raw)
            except ValueError:
                start_idx = 0
            picked = raw
            for step in range(len(pool)):
                cid = pool[(start_idx + step) % len(pool)]
                if cid not in used:
                    picked = cid
                    break
            result[chore_id] = picked
            used.add(picked)

    def _skip_unavailable(self, pool: list[str], start_idx: int, enabled: bool) -> str:
        """Walk forward from `start_idx` through `pool` looking for an available
        child. If the skip is disabled, return the originally picked child.
        If enabled and no child is available, return ``""`` so callers can hide
        the chore entirely.
        """
        original = pool[start_idx]
        if not enabled:
            return original
        size = len(pool)
        # Cache per-call so the same child isn't queried twice in a scan.
        cache: dict[str, bool] = {}

        def available(cid: str) -> bool:
            if cid not in cache:
                cache[cid] = self._is_child_available(cid)
            return cache[cid]

        for step in range(size):
            cid = pool[(start_idx + step) % size]
            if available(cid):
                return cid
        _LOGGER.debug(
            "Availability skip: no available child in pool %s for chore, hiding chore (all children unavailable)",
            pool,
        )
        return ""

    def _is_rotation_done_today(self, chore) -> bool:
        """Return True when a non-everyone-mode chore has been completed
        enough times today (across the whole rotation pool) to fill its
        daily_limit. Once that quota is met the chore is "done for the
        rotation" and should disappear from every pool member's list — not
        just the child who happened to complete it. Returns False for
        everyone-mode chores since they don't share a single daily quota.

        Exception: bonus sub-tasks render inside the parent chore card, so
        hiding the chore would also hide any pending bonus sub-tasks. If the
        active child still has uncompleted bonus sub-tasks for today, keep
        the chore visible (return False) so they remain reachable.
        """
        if getattr(chore, "assignment_mode", "everyone") == "everyone":
            return False
        # PERF-1: result depends only on the chore; memoize per availability build.
        cache = getattr(self, "_avail_cache", None)
        if cache is not None and chore.id in cache["rotation_done"]:
            return cache["rotation_done"][chore.id]
        result = self._is_rotation_done_today_uncached(chore)
        if cache is not None:
            cache["rotation_done"][chore.id] = result
        return result

    def _is_rotation_done_today_uncached(self, chore) -> bool:
        pool = set(self._chore_assignment_pool(chore))
        if not pool:
            return False
        today = dt_util.as_local(dt_util.now()).date()
        active_child_id = getattr(chore, "assignment_current_child_id", "") or ""
        completions_today = 0
        completed_bonus_ids_today: set[str] = set()
        for comp in self._cached_completions():
            if comp.chore_id != chore.id:
                continue
            comp_dt = comp.completed_at
            try:
                if hasattr(comp_dt, "astimezone"):
                    comp_dt = dt_util.as_local(comp_dt)
                comp_date = comp_dt.date() if hasattr(comp_dt, "date") else None
            except (AttributeError, TypeError, ValueError):
                continue
            if comp_date != today:
                continue
            bonus_id = getattr(comp, "bonus_subtask_id", None)
            if bonus_id:
                # Bonus completions don't count toward the parent's daily
                # quota; track them only to decide whether the active child
                # still has bonus work pending.
                if active_child_id and comp.child_id == active_child_id:
                    completed_bonus_ids_today.add(bonus_id)
                continue
            # Parent completions count toward the quota. A `__parent__`
            # sentinel covers the whole rotation for today.
            if comp.child_id in pool or comp.child_id == "__parent__":
                completions_today += 1
        # first_come is a single-winner race: clamp any mis-configured quota to 1.
        if getattr(chore, "assignment_mode", "everyone") == "first_come":
            daily_limit = 1
        else:
            daily_limit = getattr(chore, "daily_limit", 1) or 1
        if completions_today < daily_limit:
            return False
        bonus_subtasks = getattr(chore, "bonus_subtasks", None) or []
        if bonus_subtasks and active_child_id:
            for bst in bonus_subtasks:
                bst_id = getattr(bst, "id", None)
                if bst_id and bst_id not in completed_bonus_ids_today:
                    return False
        return True

    async def _async_refresh_assignments_and_publish(self) -> None:
        """Recompute today's active child per chore and publish to calendars.

        Runs at midnight. All chores are processed concurrently so the runtime
        is bounded by the slowest single publish, not the sum across chores.

        Also clears stale skip state (skip_date != today) so yesterday's skip
        doesn't bleed into the new day.
        """
        today = dt_util.as_local(dt_util.now()).date()
        today_iso = today.isoformat()
        chores = self.storage.get_chores()
        if not chores:
            return

        # Clear stale skip state in-memory (persisted via update_chore below).
        for chore in chores:
            if getattr(chore, "skip_date", "") and chore.skip_date != today_iso:
                chore.skip_date = ""
                chore.skip_count = 0

        # Group-aware daily assignment map.
        daily = self._compute_daily_assignments(today)

        async def _process(chore: Chore) -> bool:
            dirty = False
            mode = getattr(chore, "assignment_mode", "everyone")
            desired = daily.get(chore.id, "") if mode != "everyone" else ""
            if getattr(chore, "assignment_current_child_id", "") != desired:
                chore.assignment_current_child_id = desired
                dirty = True
            before = list(getattr(chore, "publish_calendar_published_dates", []) or [])
            await self._publish_chore_to_calendars(chore, today)
            if list(getattr(chore, "publish_calendar_published_dates", []) or []) != before:
                dirty = True
            # Always persist if skip state was cleared above.
            if getattr(chore, "skip_date", "") == "" and getattr(chore, "skip_count", 0) == 0:
                stored = self.storage.get_chore(chore.id)
                if stored and (stored.skip_date or stored.skip_count):
                    dirty = True
            if dirty:
                self.storage.update_chore(chore)
            return dirty

        results = await asyncio.gather(*(_process(c) for c in chores), return_exceptions=True)
        if any(r is True for r in results):
            await self.storage.async_save()
            await self.async_refresh()
