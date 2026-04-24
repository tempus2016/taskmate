"""Data coordinator for TaskMate integration."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
import hashlib
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_CALENDAR_PROJECTION_DAYS,
    DOMAIN,
    MAX_CALENDAR_PROJECTION_DAYS,
    MIN_CALENDAR_PROJECTION_DAYS,
)
from .models import Bonus, Child, Chore, ChoreCompletion, Penalty, PoolAllocation, Reward, RewardClaim, PointsTransaction
from .storage import TaskMateStorage

_LOGGER = logging.getLogger(__name__)


class TaskMateCoordinator(DataUpdateCoordinator):
    """Coordinator to manage TaskMate data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.storage = TaskMateStorage(hass, entry_id)
        self.entry_id = entry_id
        self._unsub_midnight: Callable[[], None] | None = None
        self._unsub_prune: Callable[[], None] | None = None
        self._unsub_availability: Callable[[], None] | None = None

    async def async_initialize(self) -> None:
        """Initialize the coordinator."""
        await self.storage.async_load()
        await self.async_refresh()
        # Schedule midnight streak check at 00:00:05
        self._unsub_midnight = async_track_time_change(
            self.hass, self._async_midnight_streak_check, hour=0, minute=0, second=5
        )
        # Schedule daily history pruning at 00:01:00
        self._unsub_prune = async_track_time_change(
            self.hass, self._async_scheduled_prune, hour=0, minute=1, second=0
        )
        # Re-evaluate availability-aware chore assignments when any HA entity
        # state changes. The callback filters cheaply on entity id so only
        # relevant flips trigger a recompute.
        self._unsub_availability = self.hass.bus.async_listen(
            "state_changed", self._availability_state_changed
        )

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and clean up listeners."""
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None
        if self._unsub_prune:
            self._unsub_prune()
            self._unsub_prune = None
        if self._unsub_availability:
            self._unsub_availability()
            self._unsub_availability = None

    @callback
    def _async_midnight_streak_check(self, now: datetime) -> None:
        """Scheduled callback at midnight to check and reset streaks if needed."""
        self.hass.async_create_task(self._async_check_streaks())
        self.hass.async_create_task(self._async_expire_one_shot_chores())
        self.hass.async_create_task(self._async_expire_rewards())
        # Rotate assignment_current_child_id and publish today's events to every configured calendar
        self.hass.async_create_task(self._async_refresh_assignments_and_publish())
        # Check for perfect week bonus every Monday at midnight
        if now.weekday() == 0:
            self.hass.async_create_task(self._async_check_perfect_week())

    @callback
    def _async_scheduled_prune(self, now: datetime) -> None:
        """Scheduled callback to prune old completion history."""
        days = int(self.storage.get_setting("history_days", "90"))
        self.hass.async_create_task(self.async_prune_history(days))

    @callback
    def _availability_state_changed(self, event: Any) -> None:
        """Cheap bus-filter: only dispatch a re-eval when a tracked availability entity changes."""
        data = getattr(event, "data", None) or {}
        entity_id = data.get("entity_id")
        if not entity_id:
            return
        tracked = {
            c.availability_entity
            for c in self.storage.get_children()
            if getattr(c, "availability_entity", "")
        }
        if entity_id not in tracked:
            return
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

    async def _async_check_perfect_week(self) -> None:
        """Award perfect week bonus to children who completed at least one chore every day last week."""
        perfect_week_enabled = self.storage.get_setting("perfect_week_enabled", "true") == "true"
        if not perfect_week_enabled:
            return

        try:
            perfect_week_bonus = int(self.storage.get_setting("perfect_week_bonus", "50"))
        except (ValueError, TypeError):
            perfect_week_bonus = 50

        today = dt_util.now().date()
        # Should only run on Monday — last week is Mon(today-7) to Sun(today-1)
        if today.weekday() != 0:
            _LOGGER.debug("Perfect week check skipped (not Monday)")
            return

        last_monday = today - timedelta(days=7)
        last_week_dates = {(last_monday + timedelta(days=i)).isoformat() for i in range(7)}
        week_key = last_monday.isoformat()

        all_completions = self.storage.get_completions()
        children = self.storage.get_children()
        changed = False

        for child in children:
            awarded_weeks = list(getattr(child, 'awarded_perfect_weeks', None) or [])

            # Skip if already awarded for this week
            if week_key in awarded_weeks:
                continue

            # Get all days this child had at least one completion last week
            # (count both approved and pending — don't penalise for slow parent approval)
            completed_days = set()
            for comp in all_completions:
                if comp.child_id != child.id:
                    continue
                try:
                    comp_local = dt_util.as_local(comp.completed_at)
                    comp_date_str = comp_local.date().isoformat()
                    if comp_date_str in last_week_dates:
                        completed_days.add(comp_date_str)
                except (ValueError, TypeError, AttributeError):
                    continue

            if completed_days == last_week_dates:
                # Perfect week!
                child.awarded_perfect_weeks = awarded_weeks + [week_key]
                child.points += perfect_week_bonus
                child.total_points_earned += perfect_week_bonus
                self.storage.update_child(child)

                transaction = PointsTransaction(
                    child_id=child.id,
                    points=perfect_week_bonus,
                    reason=f"Perfect week bonus! ({last_monday.strftime('%d %b')} – {(today - timedelta(days=1)).strftime('%d %b')})",
                    created_at=dt_util.now(),
                )
                self.storage.add_points_transaction(transaction)
                changed = True
                _LOGGER.info(
                    "Perfect week bonus (%d pts) awarded to %s for week of %s",
                    perfect_week_bonus, child.name, week_key,
                )

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    async def _async_check_streaks(self) -> None:
        """Check all children's streaks and reset/pause if they missed yesterday.

        Behaviour depends on streak_reset_mode setting:
        - "reset" (default): streak goes back to 0 on missed day
        - "pause": streak is preserved but not incremented until they complete again
        """
        today = dt_util.now().date()
        yesterday = today - timedelta(days=1)
        yesterday_str = yesterday.isoformat()
        today_str = today.isoformat()

        streak_mode = self.storage.get_setting("streak_reset_mode", "reset")

        children = self.storage.get_children()
        changed = False

        for child in children:
            last_date_str = getattr(child, "last_completion_date", None)
            if last_date_str is None:
                continue  # No completions yet, nothing to do

            # If last completion was today or yesterday, streak is fine
            if last_date_str in (yesterday_str, today_str):
                continue

            # They missed a day
            if (child.current_streak or 0) > 0:
                if streak_mode == "pause":
                    # Preserve the streak value but mark it as paused
                    # We do this by leaving current_streak as-is — _award_points
                    # will NOT increment it (gap detected) but won't reset either
                    # We need a flag so _award_points knows to resume not reset
                    child.streak_paused = True
                    _LOGGER.info(
                        "Streak paused for %s (last completion: %s, mode=pause)",
                        child.name, last_date_str
                    )
                else:
                    # Default: reset to 0
                    child.current_streak = 0
                    child.streak_paused = False
                    _LOGGER.info(
                        "Streak reset for %s (last completion: %s, mode=reset)",
                        child.name, last_date_str
                    )
                self.storage.update_child(child)
                changed = True

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from storage."""
        return {
            "children": self.storage.get_children(),
            "chores": self.storage.get_chores(),
            "rewards": self.storage.get_rewards(),
            "completions": self.storage.get_completions(),
            "pending_completions": self.storage.get_pending_completions(),
            "reward_claims": self.storage.get_reward_claims(),
            "pending_reward_claims": self.storage.get_pending_reward_claims(),
            "points_transactions": self.storage.get_points_transactions(),
            "points_name": self.storage.get_points_name(),
            "points_icon": self.storage.get_points_icon(),
            "settings": self.storage._data.get("settings", {}),
            "penalties": self.storage.get_penalties(),
            "bonuses": self.storage.get_bonuses(),
            "pool_allocations": self.storage.get_pool_allocations(),
        }

    # Child operations
    async def async_add_child(
        self,
        name: str,
        avatar: str = "mdi:account-circle",
        availability_entity: str = "",
    ) -> Child:
        """Add a new child."""
        child = Child(name=name, avatar=avatar, availability_entity=availability_entity)
        self.storage.add_child(child)
        await self.storage.async_save()
        await self.async_refresh()
        return child

    async def async_update_child(self, child: Child) -> None:
        """Update a child."""
        self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_child(self, child_id: str) -> None:
        """Remove a child and all associated data."""
        self.storage.remove_child(child_id)
        self.storage.remove_completions_for_child(child_id)
        self.storage.remove_reward_claims_for_child(child_id)
        self.storage.remove_transactions_for_child(child_id)
        self.storage.remove_last_completed_for_child(child_id)
        self.storage.remove_pool_allocations_for_child(child_id)
        # Remove child from chore assigned_to lists
        for chore in self.storage.get_chores():
            if child_id in chore.assigned_to:
                chore.assigned_to.remove(child_id)
                self.storage.update_chore(chore)
        await self.storage.async_save()
        await self.async_refresh()

    def get_child(self, child_id: str) -> Child | None:
        """Get a child by ID."""
        return self.storage.get_child(child_id)

    # Chore operations
    async def async_add_chore(
        self,
        name: str,
        points: int = 10,
        description: str = "",
        assigned_to: list[str] | None = None,
        requires_approval: bool = True,
        time_category: str = "anytime",
        claim_allowance_minutes: int = 0,
        daily_limit: int = 1,
        completion_sound: str = "coin",
        schedule_mode: str = "specific_days",
        due_days: list[str] | None = None,
        recurrence: str = "weekly",
        recurrence_day: str = "",
        recurrence_start: str = "",
        first_occurrence_mode: str = "available_immediately",
        visibility_entity: str = "",
        visibility_state: str = "on",
        visibility_operator: str = "equals",
        created_date: str = "",
        assignment_mode: str = "everyone",
        assignment_rotation_anchor: str = "",
        publish_calendar_entities: list[str] | None = None,
        require_availability: bool = False,
        manual_start_child_id: str = "",
    ) -> Chore:
        """Add a new chore."""
        # One-shot chores: force daily_limit=1, set created_date to today
        if schedule_mode == "one_shot":
            daily_limit = 1
            if not created_date:
                created_date = dt_util.as_local(dt_util.now()).date().isoformat()

        resolved_mode = assignment_mode if assignment_mode in ("everyone", "alternating", "random", "balanced") else "everyone"
        today = dt_util.as_local(dt_util.now()).date()

        # Apply manual start: for alternating, reorder pool + reset anchor so the
        # chosen child is day-0 of the rotation. For random/balanced, we pin the
        # cached assignment below after the chore is constructed.
        pool = list(assigned_to or [])
        if manual_start_child_id and resolved_mode == "alternating" and manual_start_child_id in pool:
            pool = [manual_start_child_id] + [c for c in pool if c != manual_start_child_id]
            assignment_rotation_anchor = today.isoformat()

        chore = Chore(
            name=name,
            points=points,
            description=description,
            assigned_to=pool,
            requires_approval=requires_approval,
            time_category=time_category,
            claim_allowance_minutes=max(0, int(claim_allowance_minutes or 0)),
            daily_limit=daily_limit,
            completion_sound=completion_sound,
            schedule_mode=schedule_mode,
            due_days=due_days or [],
            recurrence=recurrence,
            recurrence_day=recurrence_day,
            recurrence_start=recurrence_start,
            first_occurrence_mode=first_occurrence_mode,
            visibility_entity=visibility_entity,
            visibility_state=visibility_state,
            visibility_operator=visibility_operator,
            created_date=created_date,
            assignment_mode=resolved_mode,
            assignment_rotation_anchor=assignment_rotation_anchor,
            publish_calendar_entities=list(publish_calendar_entities or []),
            require_availability=require_availability,
        )
        # Cache today's active child so the card can show it immediately
        active = self._compute_active_children(chore, today)
        if active and chore.assignment_mode != "everyone":
            chore.assignment_current_child_id = active[0]
        # For random/balanced manual-start, override today's cached child so
        # the parent sees the chosen child immediately.
        if manual_start_child_id and resolved_mode in ("random", "balanced"):
            resolved_pool = self._chore_assignment_pool(chore) if chore.assigned_to else [c.id for c in self.storage.get_children()]
            if manual_start_child_id in resolved_pool:
                chore.assignment_current_child_id = manual_start_child_id
        self.storage.add_chore(chore)
        # Publish to any configured calendars ASAP — before save so we persist the last_date stamp
        await self._publish_chore_to_calendars(chore, today)
        await self.storage.async_save()
        await self.async_refresh()
        return chore

    async def async_add_chores_bulk(
        self,
        chore_names: list[str],
        points: int = 10,
        icon: str = "mdi:broom",
        due_days: list[str] | None = None,
        assigned_to: list[str] | None = None,
        requires_approval: bool = True,
        time_category: str = "anytime",
        claim_allowance_minutes: int = 0,
        daily_limit: int = 1,
        schedule_mode: str = "specific_days",
        completion_sound: str = "coin",
        visibility_entity: str = "",
        visibility_state: str = "on",
        visibility_operator: str = "equals",
            ) -> list[Chore]:
        """Add multiple chores at once with shared settings."""
        chores = []
        for name in chore_names:
            name = name.strip()
            if not name:
                continue
            chore = Chore(
                name=name,
                points=points,
                description="",
                due_days=due_days or [],
                assigned_to=assigned_to or [],
                requires_approval=requires_approval,
                time_category=time_category,
                claim_allowance_minutes=max(0, int(claim_allowance_minutes or 0)),
                daily_limit=daily_limit,
                schedule_mode=schedule_mode,
                completion_sound=completion_sound,
                visibility_entity=visibility_entity,
                visibility_state=visibility_state,
                visibility_operator=visibility_operator,
                            )
            self.storage.add_chore(chore)
            chores.append(chore)

        if chores:
            await self.storage.async_save()
            await self.async_refresh()
        return chores

    async def async_update_chore(self, chore: Chore) -> None:
        """Update a chore."""
        today = dt_util.as_local(dt_util.now()).date()
        # Capture pre-update state before storage is mutated below.
        existing = self.storage.get_chore(chore.id)
        prev_entities = list(getattr(existing, "publish_calendar_entities", []) or []) if existing else []
        prev_name = (existing.name if existing else "") or ""
        # Persist the incoming chore so _compute_daily_assignments sees the
        # latest pool / mode / etc. when applying group policies.
        self.storage.update_chore(chore)
        daily = self._compute_daily_assignments(today)
        if getattr(chore, "assignment_mode", "everyone") != "everyone":
            chore.assignment_current_child_id = daily.get(chore.id, "")
        else:
            chore.assignment_current_child_id = ""
        # Any edit to a chore with calendar publishing can shift which dates
        # project to which child (new assignment_mode, anchor, due_days,
        # recurrence, rename, time_category, entity list, etc.), so purge the
        # entire horizon from both the old and new calendar sets and let the
        # following publish pass re-write the projection.
        new_entities = list(chore.publish_calendar_entities or [])
        cleanup_entities = list({*prev_entities, *new_entities})
        if cleanup_entities:
            # Pass both the previous and current names so cleanup can fall back
            # to summary-prefix matching when an integration's get_events
            # response omits the description marker we use as primary key.
            extra_prefixes = []
            if prev_name and prev_name != chore.name:
                extra_prefixes.append(f"{prev_name} — ")
            extra_prefixes.append(f"{chore.name} — ")
            await self._cleanup_chore_from_calendars(
                chore, cleanup_entities, today, summary_prefixes=extra_prefixes,
            )
        self.storage.update_chore(chore)
        await self._publish_chore_to_calendars(chore, today)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_chore(self, chore_id: str) -> None:
        """Remove a chore and all associated data."""
        existing = self.storage.get_chore(chore_id)
        if existing is not None and getattr(existing, "publish_calendar_entities", []):
            await self._cleanup_chore_from_calendars(existing)
        self.storage.remove_chore(chore_id)
        self.storage.remove_completions_for_chore(chore_id)
        self.storage.remove_last_completed_for_chore(chore_id)
        # Strip chore from any task group it belonged to.
        self.storage.remove_chore_from_task_groups(chore_id)
        # Remove chore from children's chore_order lists
        for child in self.storage.get_children():
            if chore_id in child.chore_order:
                child.chore_order.remove(chore_id)
                self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()

    def get_chore(self, chore_id: str) -> Chore | None:
        """Get a chore by ID."""
        return self.storage.get_chore(chore_id)

    async def async_skip_chore(self, chore_id: str) -> Chore:
        """Advance today's rotation pointer past the current assignee.

        Ephemeral: the skip applies only today. Tomorrow's midnight refresh
        clears `skip_date` / `skip_count` so the rotation resumes its normal
        schedule. Skip creates no completion record; the pool-wide daily_limit
        count is unaffected.
        """
        chore = self.storage.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Unknown chore: {chore_id}")
        mode = getattr(chore, "assignment_mode", "everyone")
        if mode == "everyone":
            raise ValueError("Skip is not supported for 'everyone' assignment mode")

        # Reject skipping a sticky group follower — the group would drift.
        group = self.storage.get_task_group_for_chore(chore_id)
        if group and group.policy == "sticky" and group.chore_ids and group.chore_ids[0] != chore_id:
            raise ValueError(
                "Cannot skip a sticky group follower; skip the leader chore instead"
            )

        pool = self._chore_assignment_pool(chore)
        if len(pool) <= 1:
            raise ValueError("Skip requires a rotation pool of 2 or more children")

        today = dt_util.as_local(dt_util.now()).date()
        today_iso = today.isoformat()

        # Reset stale skip state.
        if getattr(chore, "skip_date", "") != today_iso:
            chore.skip_date = today_iso
            chore.skip_count = 0

        # Clamp: a full pool's worth of skips returns to the original child, so
        # anything beyond pool_size-1 is a no-op.
        if chore.skip_count >= len(pool) - 1:
            return chore
        chore.skip_count += 1

        # Recompute with the group-aware map so sticky followers shift too.
        self.storage.update_chore(chore)
        daily = self._compute_daily_assignments(today)
        chore.assignment_current_child_id = daily.get(chore_id, "")
        self.storage.update_chore(chore)

        # Propagate to sticky followers (their cached current_child_id shifts
        # when the leader shifts).
        if group and group.policy == "sticky" and group.chore_ids and group.chore_ids[0] == chore_id:
            for follower_id in group.chore_ids[1:]:
                follower = self.storage.get_chore(follower_id)
                if not follower:
                    continue
                desired = daily.get(follower_id, "")
                if getattr(follower, "assignment_current_child_id", "") != desired:
                    follower.assignment_current_child_id = desired
                    self.storage.update_chore(follower)

        await self.storage.async_save()
        await self.async_refresh()
        return chore

    async def async_set_chore_manual_start(self, chore_id: str, child_id: str) -> Chore:
        """Set the chore's rotation to start with the given child today.

        - alternating: reorder `assigned_to` so the chosen child is day-0, and
          reset the rotation anchor to today.
        - random / balanced: override today's cached assignment only; the
          deterministic hash takes over tomorrow.
        """
        chore = self.storage.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Unknown chore: {chore_id}")
        mode = getattr(chore, "assignment_mode", "everyone")
        if mode == "everyone":
            raise ValueError("Manual start is not supported for 'everyone' assignment mode")

        pool = self._chore_assignment_pool(chore)
        if child_id not in pool:
            raise ValueError(f"Child {child_id} is not in this chore's pool")

        today = dt_util.as_local(dt_util.now()).date()

        if mode == "alternating":
            # Reorder only when assigned_to is explicit; fallback pool ordering
            # matches storage.get_children() order, which we preserve by
            # materializing assigned_to to the full pool here.
            chore.assigned_to = [child_id] + [c for c in pool if c != child_id]
            chore.assignment_rotation_anchor = today.isoformat()

        # Any previous skip is wiped — manual start is an explicit reset.
        chore.skip_date = ""
        chore.skip_count = 0

        if mode in ("random", "balanced"):
            chore.assignment_current_child_id = child_id
        else:
            chore.assignment_current_child_id = child_id

        self.storage.update_chore(chore)
        await self.storage.async_save()
        await self.async_refresh()
        return chore

    # Task group operations

    def get_task_groups(self):
        """Return all task groups."""
        return self.storage.get_task_groups()

    def get_task_group(self, group_id: str):
        """Return a task group by ID."""
        return self.storage.get_task_group(group_id)

    def get_task_group_for_chore(self, chore_id: str):
        """Return the (at most one) task group containing the given chore."""
        return self.storage.get_task_group_for_chore(chore_id)

    def _validate_task_group_members(self, chore_ids: list[str], exclude_group_id: str = "") -> None:
        """Raise ValueError if any chore can't legally join a group.

        Rules:
        - chore must exist.
        - chore.assignment_mode must be a rotation mode (not 'everyone').
        - chore must not already belong to a different group.
        """
        seen: set[str] = set()
        for chore_id in chore_ids:
            if chore_id in seen:
                raise ValueError(f"Duplicate chore in group: {chore_id}")
            seen.add(chore_id)
            chore = self.storage.get_chore(chore_id)
            if not chore:
                raise ValueError(f"Unknown chore: {chore_id}")
            if getattr(chore, "assignment_mode", "everyone") == "everyone":
                raise ValueError(
                    f"Chore '{chore.name}' uses 'everyone' mode and cannot join a group"
                )
            existing_group = self.storage.get_task_group_for_chore(chore_id)
            if existing_group and existing_group.id != exclude_group_id:
                raise ValueError(
                    f"Chore '{chore.name}' already belongs to group '{existing_group.name}'"
                )

    async def async_add_task_group(self, name: str, policy: str, chore_ids: list[str] | None = None):
        """Create a task group."""
        from .models import TaskGroup  # local import to avoid top-level cycles
        if policy not in ("sticky", "spread"):
            raise ValueError(f"Unknown task group policy: {policy}")
        chore_ids = list(chore_ids or [])
        self._validate_task_group_members(chore_ids)
        group = TaskGroup(name=name, policy=policy, chore_ids=chore_ids)
        self.storage.add_task_group(group)
        await self.storage.async_save()
        await self.async_refresh()
        return group

    async def async_update_task_group(
        self,
        group_id: str,
        name: str | None = None,
        policy: str | None = None,
        chore_ids: list[str] | None = None,
    ):
        """Update an existing task group."""
        group = self.storage.get_task_group(group_id)
        if not group:
            raise ValueError(f"Unknown task group: {group_id}")
        if policy is not None:
            if policy not in ("sticky", "spread"):
                raise ValueError(f"Unknown task group policy: {policy}")
            group.policy = policy
        if name is not None:
            group.name = name
        if chore_ids is not None:
            new_chore_ids = list(chore_ids)
            self._validate_task_group_members(new_chore_ids, exclude_group_id=group_id)
            group.chore_ids = new_chore_ids
        self.storage.update_task_group(group)
        await self.storage.async_save()
        await self.async_refresh()
        return group

    async def async_remove_task_group(self, group_id: str) -> None:
        """Delete a task group."""
        self.storage.remove_task_group(group_id)
        await self.storage.async_save()
        await self.async_refresh()

    # Reward operations

    def get_reward(self, reward_id: str) -> Reward | None:
        """Get a reward by ID."""
        return self.storage.get_reward(reward_id)

    def is_pool_mode_claim(self, claim: "RewardClaim") -> bool:
        """True if the claim is covered by pool allocations (points already deducted).

        Pool-mode claims must NOT be counted against a child's spendable balance,
        because their cost was already removed from child.points at allocation time.
        """
        reward = self.get_reward(claim.reward_id)
        if not reward:
            return False
        if getattr(reward, "is_jackpot", False):
            return self.storage.get_total_allocated_for_reward(claim.reward_id) >= reward.cost
        alloc = self.storage.get_pool_allocation(claim.child_id, claim.reward_id)
        return bool(alloc and alloc.allocated_points >= reward.cost)

    # ── Chore completion operations ───────────────────────────────────────────

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
        if hasattr(state_obj, 'attributes') and state_obj.attributes:
            for attr_value in state_obj.attributes.values():
                if str(attr_value).lower() == parsed_state.lower():
                    return True

        return False

    _AVAILABLE_STATES: frozenset[str] = frozenset({
        "on", "home", "available", "present", "true",
    })

    def _is_child_available(self, child_id: str) -> bool:
        """Return True if the child's availability entity reports them as available.

        Rules:
          - Empty/missing availability_entity on the child → True (no opinion).
          - Entity not registered, or state is unavailable/unknown/None → True
            (fail-open; don't block on a broken sensor).
          - State (case-insensitive) in {"on", "home", "available", "present",
            "true"} → True. Everything else (e.g. "off", "not_home", "away")
            → False.
        """
        child = self.storage.get_child(child_id)
        if not child:
            return True
        entity_id = getattr(child, "availability_entity", "") or ""
        if not entity_id:
            return True
        state_obj = self.hass.states.get(entity_id)
        if state_obj is None:
            return True
        raw = getattr(state_obj, "state", None)
        if raw is None:
            return True
        value = str(raw).strip().lower()
        if value in ("unavailable", "unknown", "none", ""):
            return True
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
        mode = getattr(chore, "assignment_mode", "everyone")
        require_availability = getattr(chore, "require_availability", False)

        if mode not in ("alternating", "random", "balanced"):
            assigned = list(chore.assigned_to or [])
            if require_availability and assigned:
                filtered = [cid for cid in assigned if self._is_child_available(cid)]
                return filtered if filtered else assigned
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
            return [self._skip_unavailable(pool, idx, require_availability)]

        if mode == "random":
            # random: stable per (chore.id, date) so the frontend and backend agree
            digest = hashlib.sha256(f"{chore.id}:{today.toordinal()}".encode()).digest()
            idx = (int.from_bytes(digest[:8], "big") + skip_offset) % len(pool)
            return [self._skip_unavailable(pool, idx, require_availability)]

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
        return [self._skip_unavailable(pool, idx, require_availability)]

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
            if mode == "everyone":
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

    def _apply_sticky_policy(
        self, group, chore_by_id: dict[str, Chore], result: dict[str, str]
    ) -> None:
        """Force followers onto the leader chore's assignee (when in pool)."""
        leader_id = group.chore_ids[0]
        leader_child = result.get(leader_id)
        if not leader_child:
            return
        for follower_id in group.chore_ids[1:]:
            follower = chore_by_id.get(follower_id)
            if not follower:
                continue
            if getattr(follower, "assignment_mode", "everyone") == "everyone":
                continue
            pool = self._chore_assignment_pool(follower)
            if leader_child in pool:
                result[follower_id] = leader_child
            else:
                _LOGGER.debug(
                    "STICKY fallback: leader %s assigned to %s not in follower %s pool",
                    leader_id, leader_child, follower_id,
                )

    def _apply_spread_policy(
        self, group, chore_by_id: dict[str, Chore], result: dict[str, str]
    ) -> None:
        """Assign group members to distinct children; wraps when pool < group size."""
        used: set[str] = set()
        for chore_id in group.chore_ids:
            chore = chore_by_id.get(chore_id)
            if not chore:
                continue
            if getattr(chore, "assignment_mode", "everyone") == "everyone":
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
        child. If none of the pool is available (or the skip is disabled), return
        the originally picked child so the chore is still visible to someone.
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
            "Availability skip: no available child in pool %s for chore, "
            "falling back to original pick %s",
            pool, original,
        )
        return original

    # time_category -> (start_time, end_time). None means "anytime" -> all-day event.
    _TIME_CATEGORY_WINDOWS: dict[str, tuple[time, time] | None] = {
        "morning":   (time(6, 0),  time(12, 0)),
        "afternoon": (time(12, 0), time(17, 0)),
        "evening":   (time(17, 0), time(21, 0)),
        "night":     (time(21, 0), time(23, 59)),
        "anytime":   None,
    }

    def _time_category_window(self, category: str, today: date) -> tuple[datetime, datetime] | None:
        """Return (start, end) datetimes for a time_category, or None for all-day."""
        window = self._TIME_CATEGORY_WINDOWS.get(category or "anytime")
        if window is None:
            return None
        start_t, end_t = window
        return datetime.combine(today, start_t), datetime.combine(today, end_t)

    def _chore_event_marker(self, chore: Chore) -> str:
        """Marker stitched into the event description so we can find our own events."""
        return f"taskmate:chore:{chore.id}"

    def _calendar_projection_days(self) -> int:
        """Return the configured projection horizon, clamped to the allowed range."""
        try:
            raw = int(float(self.storage.get_setting(
                "calendar_projection_days", str(DEFAULT_CALENDAR_PROJECTION_DAYS)
            )))
        except (TypeError, ValueError):
            raw = DEFAULT_CALENDAR_PROJECTION_DAYS
        return max(MIN_CALENDAR_PROJECTION_DAYS, min(MAX_CALENDAR_PROJECTION_DAYS, raw))

    _SCHEDULE_DOW = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

    def _is_chore_scheduled_for_date(self, chore: Chore, day: date) -> bool:
        """Return True if the chore's schedule places it on `day`.

        Mirrors the client-side `_isChoreScheduledOn` in taskmate-calendar-card.js
        so the HA calendar projection matches what the card shows. Does not
        consult completion state — this is purely the recurrence/schedule math.
        """
        if not getattr(chore, "enabled", True):
            return False

        schedule_mode = getattr(chore, "schedule_mode", "specific_days")
        created_iso = getattr(chore, "created_date", "") or ""

        if schedule_mode == "one_shot":
            return bool(created_iso) and created_iso == day.isoformat()

        if created_iso:
            try:
                if day < date.fromisoformat(created_iso):
                    return False
            except ValueError:
                pass

        if schedule_mode == "specific_days":
            due_days = list(getattr(chore, "due_days", []) or [])
            if not due_days:
                return True
            return self._SCHEDULE_DOW[day.weekday()] in due_days

        if schedule_mode != "recurring":
            return False

        recurrence = getattr(chore, "recurrence", "weekly")
        recurrence_day = (getattr(chore, "recurrence_day", "") or "").lower()
        recurrence_start = getattr(chore, "recurrence_start", "") or ""
        day_dow = self._SCHEDULE_DOW[day.weekday()]

        if recurrence_day and recurrence in ("weekly", "every_2_weeks"):
            if recurrence_day != day_dow:
                return False
            if recurrence == "every_2_weeks" and recurrence_start:
                try:
                    anchor = date.fromisoformat(recurrence_start)
                    diff = (day - anchor).days
                    if diff < 0 or (diff // 7) % 2 != 0:
                        return False
                except ValueError:
                    pass
            return True

        if recurrence == "every_2_days" and recurrence_start:
            try:
                anchor = date.fromisoformat(recurrence_start)
                diff = (day - anchor).days
                return diff >= 0 and diff % 2 == 0
            except ValueError:
                return False

        if recurrence == "monthly" and recurrence_start:
            try:
                anchor = date.fromisoformat(recurrence_start)
                if day < anchor:
                    return False
                return day.day == anchor.day
            except ValueError:
                return False

        # Weekly/every_2_weeks without an explicit day: same weekday as today,
        # matching the card's fallback for loosely-scheduled recurrences.
        if recurrence in ("weekly", "every_2_weeks"):
            today = dt_util.as_local(dt_util.now()).date()
            return day.weekday() == today.weekday()

        return False

    def _build_event_payload(self, chore: Chore, day: date, summary: str) -> dict:
        """Build the calendar.create_event payload for one (chore, day)."""
        description = self._chore_event_marker(chore)
        window = self._time_category_window(
            getattr(chore, "time_category", "anytime"), day
        )
        if window is None:
            return {
                "summary": summary,
                "description": description,
                "start_date": day.isoformat(),
                "end_date": (day + timedelta(days=1)).isoformat(),
            }
        start_dt, end_dt = window
        return {
            "summary": summary,
            "description": description,
            "start_date_time": start_dt.isoformat(),
            "end_date_time": end_dt.isoformat(),
        }

    def _child_name_for_day(self, chore: Chore, day: date) -> str:
        """Return the display name for the chore's assignee on `day`."""
        active = self._compute_active_children(chore, day)
        if not active:
            return "Everyone"
        child = self.storage.get_child(active[0])
        return child.name if child else "Everyone"

    async def _publish_chore_to_calendars(self, chore: Chore, today: date | None = None) -> None:
        """Publish assignments for `chore` across the configured projection horizon.

        For every date in [today, today + horizon) that the schedule covers and
        hasn't already been published, computes that date's active child and
        writes an event to each configured calendar. Past entries are pruned
        from `publish_calendar_published_dates` so the list doesn't grow
        unbounded. Fan-out is via asyncio.gather so N entities × M missing
        days scale with the slowest single service call.
        """
        entities = list(getattr(chore, "publish_calendar_entities", []) or [])
        if not entities:
            return

        if today is None:
            today = dt_util.as_local(dt_util.now()).date()
        horizon = self._calendar_projection_days()

        published = set(getattr(chore, "publish_calendar_published_dates", []) or [])
        # Prune stale entries (strictly before today) so the list stays small.
        published = {iso for iso in published if iso >= today.isoformat()}

        pending: list[tuple[date, dict]] = []
        for offset in range(horizon):
            day = today + timedelta(days=offset)
            day_iso = day.isoformat()
            if day_iso in published:
                continue
            if not self._is_chore_scheduled_for_date(chore, day):
                continue
            summary = f"{chore.name} — {self._child_name_for_day(chore, day)}"
            pending.append((day, self._build_event_payload(chore, day, summary)))

        if not pending and not published.symmetric_difference(
            getattr(chore, "publish_calendar_published_dates", []) or []
        ):
            # Nothing to publish and nothing pruned — leave the chore untouched
            # so the caller doesn't write the record out for no reason.
            return

        async def _call(entity_id: str, payload: dict) -> None:
            try:
                await self.hass.services.async_call(
                    "calendar",
                    "create_event",
                    {"entity_id": entity_id, **payload},
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001 - HA service errors vary
                _LOGGER.warning(
                    "TaskMate: failed to publish chore %s to calendar %s: %s",
                    chore.name,
                    entity_id,
                    err,
                )

        tasks = [_call(e, payload) for day, payload in pending for e in entities]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            for day, _ in pending:
                published.add(day.isoformat())

        chore.publish_calendar_published_dates = sorted(published)

    async def _cleanup_chore_from_calendars(
        self,
        chore: Chore,
        entities: list[str] | None = None,
        today: date | None = None,
        summary_prefixes: list[str] | None = None,
    ) -> None:
        """Best-effort delete of the chore's own events from each configured calendar.

        Uses a description marker (`taskmate:chore:<id>`) stitched in at create
        time to re-identify events. Covers today through today+horizon+7 so the
        full projection range is cleaned up on edit/delete. Failure modes
        (unavailable calendar, integration without delete_event support,
        response service disabled) are caught and logged; cleanup never blocks
        the caller.
        """
        ents = list(entities if entities is not None else getattr(chore, "publish_calendar_entities", []) or [])
        if not ents:
            return

        if today is None:
            today = dt_util.as_local(dt_util.now()).date()
        window_days = max(30, self._calendar_projection_days() + 7)
        window_start = datetime.combine(today, time(0, 0)).isoformat()
        window_end = datetime.combine(today + timedelta(days=window_days), time(0, 0)).isoformat()
        marker = self._chore_event_marker(chore)
        # Fallback summary prefixes: covers integrations whose get_events
        # response omits or strips the description field. Default to the
        # current chore's name so deletes still work for unedited chores.
        prefixes = list(summary_prefixes or [f"{chore.name} — "])

        def _matches(event: dict) -> bool:
            if marker in (event.get("description") or ""):
                return True
            summary = event.get("summary") or ""
            return any(summary.startswith(p) for p in prefixes if p)

        async def _purge(entity_id: str) -> None:
            try:
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        "entity_id": entity_id,
                        "start_date_time": window_start,
                        "end_date_time": window_end,
                    },
                    blocking=True,
                    return_response=True,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "TaskMate: could not list events on %s for cleanup: %s",
                    entity_id,
                    err,
                )
                return

            events = []
            if isinstance(response, dict):
                bucket = response.get(entity_id, response)
                if isinstance(bucket, dict):
                    events = bucket.get("events", []) or []
                elif isinstance(bucket, list):
                    events = bucket

            for event in events:
                if not _matches(event):
                    continue
                uid = event.get("uid") or event.get("recurrence_id") or event.get("id")
                if not uid:
                    continue
                try:
                    await self.hass.services.async_call(
                        "calendar",
                        "delete_event",
                        {"entity_id": entity_id, "uid": uid},
                        blocking=True,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "TaskMate: failed to delete event %s from %s: %s",
                        uid,
                        entity_id,
                        err,
                    )

        await asyncio.gather(*(_purge(e) for e in ents), return_exceptions=True)
        chore.publish_calendar_published_dates = []

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

    def _is_rotation_done_today(self, chore) -> bool:
        """Return True when a non-everyone-mode chore has been completed
        enough times today (across the whole rotation pool) to fill its
        daily_limit. Once that quota is met the chore is "done for the
        rotation" and should disappear from every pool member's list — not
        just the child who happened to complete it. Returns False for
        everyone-mode chores since they don't share a single daily quota.
        """
        if getattr(chore, 'assignment_mode', 'everyone') == 'everyone':
            return False
        pool = set(self._chore_assignment_pool(chore))
        if not pool:
            return False
        today = dt_util.as_local(dt_util.now()).date()
        completions_today = 0
        for comp in self.storage.get_completions():
            if comp.chore_id != chore.id:
                continue
            if comp.child_id not in pool:
                continue
            comp_dt = comp.completed_at
            try:
                if hasattr(comp_dt, 'astimezone'):
                    comp_dt = dt_util.as_local(comp_dt)
                comp_date = comp_dt.date() if hasattr(comp_dt, 'date') else None
            except (AttributeError, TypeError, ValueError):
                continue
            if comp_date == today:
                completions_today += 1
        daily_limit = getattr(chore, 'daily_limit', 1) or 1
        return completions_today >= daily_limit

    def is_chore_available_for_child(self, chore, child_id: str) -> bool:
        """Check if a recurring chore is available for a child to complete.

        Mode A (specific_days): day filtering is handled by the child card.

        Mode B (recurring): checks rolling window from last completion date
        (midnight-rounded). Window lengths in days per recurrence type.

        Both modes also check visibility_entity if configured.
        """
        # Check if chore is globally disabled (soft-disabled one-shot chores)
        if not getattr(chore, 'enabled', True):
            return False

        # Check per-child disabling (one-shot chores completed by this child)
        disabled_for = getattr(chore, 'disabled_for', [])
        if child_id in disabled_for:
            return False

        # Dynamic assignment — only the active child(ren) see alternating/random chores
        if getattr(chore, 'assignment_mode', 'everyone') != 'everyone':
            active = self._compute_active_children(chore)
            if child_id not in active:
                return False
            # Once anyone in the rotation pool has completed it today (e.g. a
            # parent ticked it off for the off-rotation child), the chore is
            # done for the whole pool — including today's active child.
            if self._is_rotation_done_today(chore):
                return False

        # Check visibility entity first — if not visible, chore is not available
        visibility_entity = getattr(chore, 'visibility_entity', '')
        visibility_state = getattr(chore, 'visibility_state', 'on')
        visibility_operator = getattr(chore, 'visibility_operator', 'equals')
        if not self._is_visibility_entity_active(visibility_entity, visibility_state, visibility_operator):
            return False

        schedule_mode = getattr(chore, 'schedule_mode', 'specific_days')

        # One-shot chores: only available on the day they were created
        if schedule_mode == 'one_shot':
            created_date = getattr(chore, 'created_date', '')
            if created_date:
                today = dt_util.as_local(dt_util.now()).date()
                try:
                    if date.fromisoformat(created_date) != today:
                        return False
                except ValueError:
                    pass
            return True

        if schedule_mode != 'recurring':
            return True

        recurrence = getattr(chore, 'recurrence', 'weekly')
        first_occurrence_mode = getattr(chore, 'first_occurrence_mode', 'available_immediately')
        recurrence_day = getattr(chore, 'recurrence_day', '')
        recurrence_start = getattr(chore, 'recurrence_start', '')

        now = dt_util.now()
        today = dt_util.as_local(now).date()

        window_days = {
            'every_2_days': 2,
            'weekly': 7,
            'every_2_weeks': 14,
            'monthly': 30,
            'every_3_months': 90,
            'every_6_months': 180,
        }.get(recurrence, 7)

        record = self.storage.get_last_completed(chore.id, child_id)
        current_iso = record.get('current')

        if not current_iso:
            # Never completed — apply first_occurrence_mode
            if first_occurrence_mode == 'wait_for_first_occurrence':
                if recurrence == 'every_2_days' and recurrence_start:
                    try:
                        start_date = date.fromisoformat(recurrence_start)
                        if start_date > today:
                            return False
                    except ValueError:
                        pass
                elif recurrence_day:
                    day_map = {
                        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                        'friday': 4, 'saturday': 5, 'sunday': 6
                    }
                    target_dow = day_map.get(recurrence_day.lower())
                    if target_dow is not None and today.weekday() != target_dow:
                        return False
            return True

        try:
            last_dt = date.fromisoformat(current_iso[:10])
        except (ValueError, TypeError):
            return True

        # every_2_days with anchor — check alignment
        if recurrence == 'every_2_days' and recurrence_start:
            try:
                anchor = date.fromisoformat(recurrence_start)
                days_since_anchor = (today - anchor).days
                if days_since_anchor < 0:
                    return False
                if days_since_anchor % 2 != 0:
                    return False
                return last_dt < today
            except ValueError:
                pass

        # weekly/every_2_weeks with specific day — only available on that day
        if recurrence_day and recurrence in ('weekly', 'every_2_weeks'):
            day_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            target_dow = day_map.get(recurrence_day.lower())
            if target_dow is not None and today.weekday() != target_dow:
                return False

        days_since = (today - last_dt).days
        return days_since >= window_days

    async def async_complete_chore(self, chore_id: str, child_id: str) -> ChoreCompletion:
        """Mark a chore as completed by a child."""
        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        now = dt_util.now()
        today = dt_util.as_local(now).date()

        # Check recurrence window for Mode B chores
        if getattr(chore, 'schedule_mode', 'specific_days') == 'recurring':
            if not self.is_chore_available_for_child(chore, child_id):
                recurrence = getattr(chore, 'recurrence', 'weekly')
                raise ValueError(
                    f"Chore '{chore.name}' is not available yet. "
                    f"Recurrence: {recurrence.replace('_', ' ')}."
                )

        # Check availability for one-shot chores
        if getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot':
            if not self.is_chore_available_for_child(chore, child_id):
                raise ValueError(
                    f"Chore '{chore.name}' is not available (one-shot chore already completed or expired)."
                )

        # Check daily limit
        all_completions = self.storage.get_completions()
        todays_completions_count = 0
        for comp in all_completions:
            if comp.chore_id == chore_id and comp.child_id == child_id:
                comp_dt = comp.completed_at
                if isinstance(comp_dt, str):
                    try:
                        comp_dt = datetime.fromisoformat(comp_dt)
                    except (ValueError, TypeError):
                        continue
                if isinstance(comp_dt, datetime):
                    comp_dt = dt_util.as_local(comp_dt)
                    if comp_dt.date() == today:
                        todays_completions_count += 1

        daily_limit = getattr(chore, 'daily_limit', 1)
        if todays_completions_count >= daily_limit:
            raise ValueError(
                f"Daily limit reached for chore '{chore.name}'. "
                f"Already completed {todays_completions_count} time(s) today (limit: {daily_limit})"
            )

        completion = ChoreCompletion(
            chore_id=chore_id,
            child_id=child_id,
            completed_at=now,
            approved=not chore.requires_approval,
            points_awarded=chore.points if not chore.requires_approval else 0,
        )

        if not chore.requires_approval:
            total_awarded = await self._award_points(child, chore.points)
            completion.approved = True
            completion.approved_at = dt_util.now()
            completion.points_awarded = total_awarded

        self.storage.add_completion(completion)

        # Update last_completed store (window starts at completion time, midnight-rounded)
        self.storage.set_last_completed(chore_id, child_id, now.isoformat())

        # One-shot: if auto-approved (no approval needed), disable for this child immediately
        if getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot' and not chore.requires_approval:
            if child_id not in chore.disabled_for:
                chore.disabled_for.append(child_id)
            self._check_one_shot_fully_disabled(chore)
            self.storage.update_chore(chore)

        await self.storage.async_save()

        # Fire approval notification if chore requires parent sign-off
        if chore.requires_approval:
            await self._async_notify_pending_approval(child.name, chore.name, chore.points)

        await self.async_refresh()
        return completion

    async def async_approve_chore(self, completion_id: str) -> None:
        """Approve a chore completion."""
        completions = self.storage.get_completions()
        for completion in completions:
            if completion.id == completion_id:
                chore = self.get_chore(completion.chore_id)
                child = self.get_child(completion.child_id)

                if chore and child:
                    comp_date = dt_util.as_local(completion.completed_at).date()
                    total_awarded = await self._award_points(child, chore.points, completion_date=comp_date)
                    completion.approved = True
                    completion.approved_at = dt_util.now()
                    completion.points_awarded = total_awarded
                    self.storage.update_completion(completion)

                    # One-shot: disable for this child on approval
                    if getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot':
                        if completion.child_id not in chore.disabled_for:
                            chore.disabled_for.append(completion.child_id)
                        self._check_one_shot_fully_disabled(chore)
                        self.storage.update_chore(chore)

                    await self.storage.async_save()
                    await self.async_refresh()
                else:
                    _LOGGER.warning(
                        "Cannot approve completion %s: chore (%s) or child (%s) not found",
                        completion_id, completion.chore_id, completion.child_id,
                    )
                return
        _LOGGER.warning("Completion %s not found for approval", completion_id)

    async def async_reject_chore(self, completion_id: str) -> None:
        """Reject a chore completion and fully reverse all awards if already granted."""
        completions = self.storage.get_completions()
        target_completion = None
        for completion in completions:
            if completion.id == completion_id:
                target_completion = completion
                if completion.points_awarded > 0:
                    child = self.get_child(completion.child_id)
                    if child:
                        # Reverse base + weekend bonus points
                        child.points = max(0, child.points - completion.points_awarded)
                        child.total_points_earned = max(0, child.total_points_earned - completion.points_awarded)
                        child.total_chores_completed = max(0, child.total_chores_completed - 1)

                        # Reverse streak: decrement (but don't go below 0)
                        child.current_streak = max(0, child.current_streak - 1)

                        self.storage.update_child(child)
                break

        # Undo last_completed store so recurrence window resets correctly
        if target_completion:
            self.storage.undo_last_completed(
                target_completion.chore_id, target_completion.child_id
            )

            # One-shot: re-enable for this child on rejection
            chore = self.get_chore(target_completion.chore_id)
            if chore and getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot':
                if target_completion.child_id in chore.disabled_for:
                    chore.disabled_for.remove(target_completion.child_id)
                chore.enabled = True
                self.storage.update_chore(chore)

        self.storage.remove_completion(completion_id)
        await self.storage.async_save()
        await self.async_refresh()

    def _check_one_shot_fully_disabled(self, chore) -> None:
        """Check if a one-shot chore should be fully disabled (all children done)."""
        if chore.assigned_to:
            target_children = set(chore.assigned_to)
        else:
            # assigned_to=[] means all children
            target_children = {c.id for c in self.storage.get_children()}

        if target_children and target_children.issubset(set(chore.disabled_for)):
            chore.enabled = False

    async def _async_expire_one_shot_chores(self) -> None:
        """Soft-disable one-shot chores whose created_date is before today."""
        today = dt_util.as_local(dt_util.now()).date()
        changed = False

        for chore in self.storage.get_chores():
            if getattr(chore, 'schedule_mode', 'specific_days') != 'one_shot':
                continue
            if not getattr(chore, 'enabled', True):
                continue
            created_date = getattr(chore, 'created_date', '')
            if not created_date:
                continue
            try:
                if date.fromisoformat(created_date) < today:
                    chore.enabled = False
                    self.storage.update_chore(chore)
                    changed = True
                    _LOGGER.info(
                        "One-shot chore '%s' expired (created %s, today %s)",
                        chore.name, created_date, today.isoformat(),
                    )
            except ValueError:
                continue

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    async def _async_expire_rewards(self) -> None:
        """Refund pool allocations on any reward whose expires_at is past.

        The reward row itself is kept in storage so the sensor can surface the
        "Expired" state and existing claim history stays intact.
        """
        changed = False
        for reward in self.storage.get_rewards():
            if not self._reward_is_expired(reward):
                continue
            allocations_before = [
                a for a in self.storage.get_pool_allocations()
                if a.reward_id == reward.id and a.allocated_points > 0
            ]
            if not allocations_before:
                continue
            self._refund_all_pool_allocations(reward, "Pool refund (reward expired)")
            changed = True
            _LOGGER.info(
                "Reward '%s' expired on %s — refunded %d pool allocation(s)",
                reward.name, reward.expires_at, len(allocations_before),
            )

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    # ── Reward operations ─────────────────────────────────────────────────────

    async def async_add_reward(
        self,
        name: str,
        cost: int = 50,
        description: str = "",
        icon: str = "mdi:gift",
        assigned_to: list[str] | None = None,
        is_jackpot: bool = False,
        pool_enabled: bool = False,
        quantity: int | None = None,
        expires_at: str | None = None,
    ) -> Reward:
        """Add a new reward."""
        reward = Reward(
            name=name,
            cost=cost,
            description=description,
            icon=icon,
            assigned_to=assigned_to or [],
            is_jackpot=is_jackpot,
            pool_enabled=pool_enabled,
            quantity=quantity,
            expires_at=expires_at,
        )
        self.storage.add_reward(reward)
        await self.storage.async_save()
        await self.async_refresh()
        return reward

    async def async_update_reward(self, reward: Reward) -> None:
        """Update a reward.

        If the cost is reduced below any existing pool allocation, the excess is
        refunded to the contributing children's wallets so over-allocated pools
        can't appear as e.g. 11/10. If the edit makes the reward unavailable
        (quantity set to 0, or expires_at moved into the past) any pool
        allocations on that reward are refunded in full.
        """
        old = self.get_reward(reward.id)
        self.storage.update_reward(reward)
        if old and reward.cost < old.cost:
            self._refund_pool_excess(reward, "Pool refund (reward cost reduced)")
        became_unavailable = (
            self._reward_is_unavailable(reward)
            and old is not None
            and not self._reward_is_unavailable(old)
        )
        if became_unavailable:
            reason = (
                "Pool refund (reward expired)"
                if self._reward_is_expired(reward)
                else "Pool refund (reward sold out)"
            )
            self._refund_all_pool_allocations(reward, reason)
        await self.storage.async_save()
        await self.async_refresh()

    @staticmethod
    def _reward_is_sold_out(reward: Reward) -> bool:
        """True if the reward has a stock count and it's been exhausted."""
        return reward.quantity is not None and reward.quantity <= 0

    @staticmethod
    def _reward_is_expired(reward: Reward) -> bool:
        """True if the reward has an expiry date and it's on/before today."""
        if not reward.expires_at:
            return False
        try:
            deadline = date.fromisoformat(reward.expires_at)
        except (TypeError, ValueError):
            return False
        return deadline <= dt_util.now().date()

    @classmethod
    def _reward_is_unavailable(cls, reward: Reward) -> bool:
        """True if the reward cannot currently be claimed or allocated to."""
        return cls._reward_is_sold_out(reward) or cls._reward_is_expired(reward)

    def _refund_all_pool_allocations(self, reward: Reward, reason: str) -> None:
        """Refund every pool allocation on `reward` back to its contributor.

        Used when a reward becomes unavailable (sold out or expired) while
        children still have points earmarked for it. Reuses the existing
        per-allocation refund helper so the PointsTransaction audit trail
        stays consistent with cost-reduction refunds.
        """
        allocations = [
            a for a in self.storage.get_pool_allocations()
            if a.reward_id == reward.id and a.allocated_points > 0
        ]
        for alloc in allocations:
            self._apply_pool_refund(alloc, alloc.allocated_points, reward, reason)

    def _refund_pool_excess(self, reward: Reward, reason: str) -> None:
        """Trim any pool allocations on `reward` that exceed its cost.

        Non-jackpot: each allocation is capped at the reward's cost individually.
        Jackpot: allocations are trimmed starting from the newest contributor
        until the combined total matches the cost.
        """
        allocations = [
            a for a in self.storage.get_pool_allocations()
            if a.reward_id == reward.id and a.allocated_points > 0
        ]
        if not allocations:
            return

        if reward.is_jackpot:
            overshoot = sum(a.allocated_points for a in allocations) - reward.cost
            if overshoot <= 0:
                return
            for alloc in sorted(allocations, key=lambda a: a.id, reverse=True):
                if overshoot <= 0:
                    break
                refund = min(alloc.allocated_points, overshoot)
                self._apply_pool_refund(alloc, refund, reward, reason)
                overshoot -= refund
        else:
            for alloc in allocations:
                if alloc.allocated_points > reward.cost:
                    self._apply_pool_refund(
                        alloc, alloc.allocated_points - reward.cost, reward, reason
                    )

    def _apply_pool_refund(
        self, allocation: "PoolAllocation", refund: int, reward: Reward, reason: str
    ) -> None:
        """Refund `refund` points from `allocation` back to the child's wallet.

        Updates or removes the allocation record and writes an audit transaction.
        """
        if refund <= 0:
            return
        child = self.get_child(allocation.child_id)
        if not child:
            return
        child.points += refund
        self.storage.update_child(child)

        remaining = allocation.allocated_points - refund
        if remaining <= 0:
            self.storage.remove_pool_allocation(allocation.child_id, allocation.reward_id)
        else:
            self.storage.upsert_pool_allocation(PoolAllocation(
                child_id=allocation.child_id,
                reward_id=allocation.reward_id,
                allocated_points=remaining,
                id=allocation.id,
            ))

        self.storage.add_points_transaction(PointsTransaction(
            child_id=allocation.child_id,
            points=refund,
            reason=f"{reason}: {reward.name}",
            created_at=dt_util.now(),
        ))

    async def async_remove_reward(self, reward_id: str) -> None:
        """Remove a reward and clean up any pending claims and pool allocations referencing it."""
        self.storage.remove_reward_claims_for_reward(reward_id)
        self.storage.remove_pool_allocations_for_reward(reward_id)
        self.storage.remove_reward(reward_id)
        await self.storage.async_save()
        await self.async_refresh()

    async def _async_notify_pending_approval(
        self, child_name: str, chore_name: str, points: int
    ) -> None:
        """Fire a persistent notification and optional notify service when a chore needs approval."""
        points_name = self.storage.get_points_name()
        message = (
            f"{child_name} completed '{chore_name}' (+{points} {points_name}) "
            f"and is waiting for your approval."
        )
        notification_id = (
            f"taskmate_approval_{child_name}_{chore_name}".replace(" ", "_").lower()
        )
        await self._async_fire_approval_notification(message, notification_id)

    async def _async_notify_pending_reward_claim(
        self, child_name: str, reward_name: str, cost: int
    ) -> None:
        """Fire a persistent notification and optional notify service when a reward claim needs approval."""
        points_name = self.storage.get_points_name()
        message = (
            f"{child_name} claimed '{reward_name}' ({cost} {points_name}) "
            f"and is waiting for your approval."
        )
        notification_id = (
            f"taskmate_reward_claim_{child_name}_{reward_name}".replace(" ", "_").lower()
        )
        await self._async_fire_approval_notification(message, notification_id)

    async def _async_fire_approval_notification(
        self, message: str, notification_id: str
    ) -> None:
        """Shared helper: create a persistent notification and (optionally) call a notify.* service."""
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "TaskMate — Approval Needed",
                    "message": message,
                    "notification_id": notification_id,
                },
                blocking=False,
            )
        )

        notify_service = self.storage.get_setting("notify_service", "")
        if notify_service:
            domain, service = (
                notify_service.split(".", 1) if "." in notify_service
                else ("notify", notify_service)
            )
            # Only allow notify domain to prevent arbitrary service invocation
            if domain != "notify":
                _LOGGER.warning(
                    "TaskMate: notify_service must use the 'notify' domain, got '%s'",
                    domain,
                )
            else:
                try:
                    await self.hass.services.async_call(
                        domain,
                        service,
                        {"title": "TaskMate ✅", "message": message},
                        blocking=False,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "TaskMate: failed to send notification via %s: %s",
                        notify_service, err
                    )

    async def async_claim_reward(self, reward_id: str, child_id: str) -> RewardClaim:
        """Child claims a reward — creates a pending claim awaiting parent approval.

        Two modes are supported:
          * Wallet mode (default): requires child.points (minus committed) to cover cost
          * Pool mode: if pool allocations exist for this (child, reward) and they fill the
            reward's cost, the claim is a "redeem" — no wallet check needed. For jackpot
            rewards the pool total across all contributing children must reach the cost.
        """
        reward = self.get_reward(reward_id)
        if not reward:
            raise ValueError(f"Reward {reward_id} not found")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        if self._reward_is_sold_out(reward):
            raise ValueError(f"Reward '{reward.name}' is sold out")
        if self._reward_is_expired(reward):
            raise ValueError(f"Reward '{reward.name}' has expired")

        # Cost is always static
        effective_cost = reward.cost

        # Detect pool mode: a filled pool allocation for this (child, reward) is sufficient,
        # or for jackpots the summed pool across all children reaches cost.
        pool_filled = False
        if reward.is_jackpot:
            pool_total = self.storage.get_total_allocated_for_reward(reward_id)
            if pool_total >= effective_cost:
                pool_filled = True
        else:
            allocation = self.storage.get_pool_allocation(child_id, reward_id)
            if allocation and allocation.allocated_points >= effective_cost:
                pool_filled = True

        if not pool_filled:
            # Wallet mode: verify child has enough uncommitted points.
            # Pool-mode pending claims already had their cost deducted at allocation time,
            # so they are skipped here to avoid double-counting against the wallet.
            pending_claims = self.storage.get_pending_reward_claims()
            committed = 0
            for c in pending_claims:
                if c.child_id == child_id and not self.is_pool_mode_claim(c):
                    pending_reward = self.get_reward(c.reward_id)
                    if pending_reward:
                        committed += pending_reward.cost
            available_points = child.points - committed

            if available_points < effective_cost:
                raise ValueError(
                    f"Not enough points. Need {effective_cost}, have {available_points} available"
                )

        claim = RewardClaim(
            reward_id=reward_id,
            child_id=child_id,
            claimed_at=dt_util.now(),
        )

        self.storage.add_reward_claim(claim)
        await self.storage.async_save()
        await self.async_refresh()
        await self._async_notify_pending_reward_claim(
            child.name, reward.name, reward.cost
        )
        return claim

    async def async_approve_reward(self, claim_id: str) -> None:
        """Approve a reward claim and deduct points from the child.

        If a pool allocation exists for this (child, reward) pair with enough points,
        the deduction consumes the pool allocation first (pool mode). Otherwise the
        wallet-mode path deducts directly from child.points.
        """
        claims = self.storage.get_reward_claims()
        for claim in claims:
            if claim.id == claim_id:
                if claim.approved:
                    _LOGGER.warning("Reward claim %s already approved, ignoring", claim_id)
                    return

                reward = self.get_reward(claim.reward_id)
                child = self.get_child(claim.child_id)
                if not reward or not child:
                    raise ValueError(f"Reward or child not found for claim {claim_id}")

                # Cost is always static
                effective_cost = reward.cost

                # Detect pool mode: either a direct allocation, or a filled jackpot pool.
                pool_alloc = self.storage.get_pool_allocation(claim.child_id, claim.reward_id)
                is_pool_mode = False
                if reward.is_jackpot:
                    pool_total = self.storage.get_total_allocated_for_reward(claim.reward_id)
                    if pool_total >= effective_cost:
                        is_pool_mode = True
                elif pool_alloc and pool_alloc.allocated_points >= effective_cost:
                    is_pool_mode = True

                if is_pool_mode:
                    # Pool mode: points were already deducted from child.points at allocation
                    # time — approving the redeem just clears the allocation record(s).
                    # Refund any over-allocation first (e.g. left over from a prior cost reduction)
                    # so the child doesn't lose points beyond the reward's actual cost.
                    self._refund_pool_excess(reward, "Pool refund on redeem")
                    if reward.is_jackpot:
                        jackpot_allocs = [
                            a for a in self.storage.get_pool_allocations()
                            if a.reward_id == claim.reward_id and a.allocated_points > 0
                        ]
                        for alloc in jackpot_allocs:
                            self.storage.remove_pool_allocation(alloc.child_id, alloc.reward_id)
                    else:
                        self.storage.remove_pool_allocation(claim.child_id, claim.reward_id)
                else:
                    # Wallet mode: deduct directly from child.points
                    if child.points < effective_cost:
                        raise ValueError(
                            f"Not enough points to approve. Need {effective_cost}, have {child.points}"
                        )
                    child.points -= effective_cost
                    self.storage.update_child(child)

                if reward.quantity is not None:
                    reward.quantity = max(0, reward.quantity - 1)
                    self.storage.update_reward(reward)
                    if reward.quantity == 0:
                        # Last unit claimed — refund any points other children
                        # still have earmarked for this reward's pool.
                        self._refund_all_pool_allocations(
                            reward, "Pool refund (reward sold out)"
                        )

                claim.approved = True
                claim.approved_at = dt_util.now()
                self.storage.update_reward_claim(claim)
                await self.storage.async_save()
                await self.async_refresh()
                return
        _LOGGER.warning("Reward claim %s not found for approval", claim_id)

    async def async_reject_reward(self, claim_id: str) -> None:
        """Reject a reward claim — no refund needed as points were never deducted."""
        self.storage.remove_reward_claim(claim_id)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_allocate_points_to_pool(
        self, child_id: str, reward_id: str, points: int
    ) -> PoolAllocation:
        """Move `points` from a child's spendable balance into a reward pool.

        Deducts immediately from child.points so the visible balance reflects the
        commitment. The matching PoolAllocation record tracks the earmarked total
        for each (child, reward) pair. Requested points are capped silently at the
        pool's remaining capacity and the child's spendable balance.
        Allocations are locked — there is no matching "withdraw" operation.
        """
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        reward = self.get_reward(reward_id)
        if not reward:
            raise ValueError(f"Reward {reward_id} not found")

        if self._reward_is_sold_out(reward):
            raise ValueError(f"Reward '{reward.name}' is sold out")
        if self._reward_is_expired(reward):
            raise ValueError(f"Reward '{reward.name}' has expired")

        if points < 1:
            raise ValueError("Points to allocate must be at least 1")

        # Spendable balance = child.points − points committed to other pending claims.
        # (Already-allocated points are no longer part of child.points, so we do NOT
        # subtract total_allocated here — they've been deducted at allocation time.)
        # Pool-mode pending claims are also skipped — their cost was already removed
        # from child.points at allocation time, so counting it again would block the
        # child from allocating to any other pool reward while one awaits approval.
        pending_claims = self.storage.get_pending_reward_claims()
        committed = 0
        for c in pending_claims:
            if c.child_id == child_id and not self.is_pool_mode_claim(c):
                pending_reward = self.get_reward(c.reward_id)
                if pending_reward:
                    committed += pending_reward.cost
        spendable = child.points - committed

        if spendable < 1:
            raise ValueError(f"No spendable points available for {child.name}")

        # Compute remaining pool capacity
        existing = self.storage.get_pool_allocation(child_id, reward_id)
        current_child_allocation = existing.allocated_points if existing else 0
        if reward.is_jackpot:
            room_left = reward.cost - self.storage.get_total_allocated_for_reward(reward_id)
        else:
            room_left = reward.cost - current_child_allocation

        if room_left <= 0:
            raise ValueError(f"Pool for reward '{reward.name}' is already full")

        capped_points = min(points, spendable, room_left)

        # Deduct from the visible balance; the allocation record holds the earmarked points.
        child.points -= capped_points
        self.storage.update_child(child)

        allocation = PoolAllocation(
            child_id=child_id,
            reward_id=reward_id,
            allocated_points=current_child_allocation + capped_points,
            id=existing.id if existing else PoolAllocation(child_id, reward_id).id,
        )
        self.storage.upsert_pool_allocation(allocation)

        # Audit trail: negative transaction showing the deduction
        transaction = PointsTransaction(
            child_id=child_id,
            points=-capped_points,
            reason=f"Allocated to pool: {reward.name}",
            created_at=dt_util.now(),
        )
        self.storage.add_points_transaction(transaction)

        await self.storage.async_save()
        await self.async_refresh()
        return allocation

    # Penalty operations
    async def async_add_penalty(
        self,
        name: str,
        points: int,
        description: str = "",
        icon: str = "mdi:alert-circle-outline",
        assigned_to: list | None = None,
    ):
        """Create a new penalty definition."""
        penalty = Penalty(
            name=name,
            points=points,
            description=description,
            icon=icon,
            assigned_to=assigned_to or [],
        )
        self.storage.add_penalty(penalty)
        await self.storage.async_save()
        await self.async_refresh()
        return penalty

    async def async_update_penalty(self, penalty) -> None:
        """Update an existing penalty definition."""
        self.storage.update_penalty(penalty)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_penalty(self, penalty_id: str) -> None:
        """Delete a penalty definition."""
        self.storage.remove_penalty(penalty_id)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_apply_penalty(self, penalty_id: str, child_id: str) -> None:
        """Apply a penalty — deducts the penalty's points from the child."""
        penalty = self.storage.get_penalty(penalty_id)
        if not penalty:
            raise ValueError(f"Penalty {penalty_id} not found")
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        await self.async_remove_points(child_id, penalty.points, reason=f"Penalty: {penalty.name}")

    # Bonus operations
    async def async_add_bonus(
        self,
        name: str,
        points: int,
        description: str = "",
        icon: str = "mdi:star-circle-outline",
        assigned_to: list | None = None,
    ):
        """Create a new bonus definition."""
        bonus = Bonus(
            name=name,
            points=points,
            description=description,
            icon=icon,
            assigned_to=assigned_to or [],
        )
        self.storage.add_bonus(bonus)
        await self.storage.async_save()
        await self.async_refresh()
        return bonus

    async def async_update_bonus(self, bonus) -> None:
        """Update an existing bonus definition."""
        self.storage.update_bonus(bonus)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_bonus(self, bonus_id: str) -> None:
        """Delete a bonus definition."""
        self.storage.remove_bonus(bonus_id)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_apply_bonus(self, bonus_id: str, child_id: str) -> None:
        """Apply a bonus — awards the bonus's points to the child."""
        bonus = self.storage.get_bonus(bonus_id)
        if not bonus:
            raise ValueError(f"Bonus {bonus_id} not found")
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        await self.async_add_points(child_id, bonus.points, reason=f"Bonus: {bonus.name}")

    # Points operations
    async def async_add_points(self, child_id: str, points: int, reason: str = "") -> None:
        """Add points to a child (bonus)."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        child.points += points
        child.total_points_earned += points
        self.storage.update_child(child)
        # Log the manual transaction
        transaction = PointsTransaction(
            child_id=child_id,
            points=points,
            reason=reason,
            created_at=dt_util.now(),
        )
        self.storage.add_points_transaction(transaction)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_points(self, child_id: str, points: int, reason: str = "") -> None:
        """Remove points from a child (penalty)."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        actual_deducted = min(points, child.points)  # Can't go below 0
        child.points = max(0, child.points - points)
        self.storage.update_child(child)
        # Log the manual transaction (negative points)
        transaction = PointsTransaction(
            child_id=child_id,
            points=-actual_deducted,
            reason=reason,
            created_at=dt_util.now(),
        )
        self.storage.add_points_transaction(transaction)
        await self.storage.async_save()
        await self.async_refresh()

    # ── Bonus points constants ────────────────────────────────────────────────
    DEFAULT_STREAK_MILESTONES = "3:5, 7:10, 14:20, 30:50, 60:100, 100:200"

    @staticmethod
    def parse_milestone_setting(value: str) -> dict[int, int]:
        """Parse 'days:points, days:points' string into {days: points} dict."""
        if not value or not value.strip():
            return {}
        result = {}
        for part in value.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" not in part:
                raise ValueError(
                    f"Invalid format '{part}' — use 'days:points' pairs, e.g. '7:10, 14:20'"
                )
            days_str, points_str = part.split(":", 1)
            try:
                days = int(days_str.strip())
                points = int(points_str.strip())
            except ValueError:
                raise ValueError(
                    f"Invalid numbers in '{part}' — days and points must be whole numbers"
                )
            if days < 1:
                raise ValueError(f"Days must be at least 1, got {days}")
            if points < 1:
                raise ValueError(f"Points must be at least 1, got {points}")
            if days in result:
                raise ValueError(f"Duplicate milestone for {days} days")
            result[days] = points
        return result

    async def _award_points(
        self,
        child: Child,
        points: int,
        completion_date: date | None = None,
    ) -> int:
        """Award points to a child, update streak, and apply bonus systems.

        Returns the total points awarded (base + weekend bonus), excluding
        milestone bonuses (which are logged as separate transactions).
        """
        now = dt_util.now()
        today = now.date()
        effective_date = completion_date or today
        effective_date_str = effective_date.isoformat()
        last_date_str = getattr(child, 'last_completion_date', None)

        # ── Weekend multiplier ──────────────────────────────────────────────
        # Applied to base chore points only, based on completion date
        try:
            multiplier = float(self.storage.get_setting("weekend_multiplier", "2.0"))
        except (ValueError, TypeError):
            multiplier = 2.0

        weekend_bonus = 0
        if effective_date.weekday() in (5, 6) and multiplier > 1.0:
            weekend_bonus = round(points * (multiplier - 1.0))

        total_points = points + weekend_bonus
        child.points += total_points
        child.total_points_earned += total_points
        child.total_chores_completed += 1

        if weekend_bonus > 0:
            _LOGGER.info(
                "Weekend multiplier (%.1fx) applied for %s: +%d bonus on top of %d",
                multiplier, child.name, weekend_bonus, points,
            )
            # Log weekend bonus as a separate transaction for activity history
            transaction = PointsTransaction(
                child_id=child.id,
                points=weekend_bonus,
                reason=f"Weekend bonus (×{multiplier:.0f})",
                created_at=now,
            )
            self.storage.add_points_transaction(transaction)

        # ── Streak tracking ─────────────────────────────────────────────────
        streak_mode = self.storage.get_setting("streak_reset_mode", "reset")
        streak_paused = getattr(child, "streak_paused", False)
        streak_before = child.current_streak or 0
        streak_reset_occurred = False

        if last_date_str is None:
            child.current_streak = 1
            child.streak_paused = False
        elif last_date_str == effective_date_str:
            pass  # Already completed on this date — streak unchanged
        else:
            try:
                last_date = date.fromisoformat(last_date_str)
                yesterday = effective_date - timedelta(days=1)
                if last_date == yesterday:
                    child.current_streak = streak_before + 1
                    child.streak_paused = False
                elif streak_mode == "pause" or streak_paused:
                    child.streak_paused = False
                    _LOGGER.debug("Streak resumed for %s at %d", child.name, child.current_streak)
                else:
                    child.current_streak = 1
                    child.streak_paused = False
                    streak_reset_occurred = True
            except (ValueError, TypeError):
                child.current_streak = 1
                child.streak_paused = False
                streak_reset_occurred = True

        child.last_completion_date = effective_date_str

        if child.current_streak > (child.best_streak or 0):
            child.best_streak = child.current_streak

        # ── Streak milestone bonus ──────────────────────────────────────────
        milestones_enabled = self.storage.get_setting("streak_milestones_enabled", "true") == "true"
        if milestones_enabled and child.current_streak > 0:
            # Parse custom milestone config
            milestone_setting = self.storage.get_setting(
                "streak_milestones", self.DEFAULT_STREAK_MILESTONES
            )
            try:
                milestones = self.parse_milestone_setting(milestone_setting)
            except ValueError:
                milestones = self.parse_milestone_setting(self.DEFAULT_STREAK_MILESTONES)

            # Clear milestones on reset so kids can re-earn them
            if streak_reset_occurred:
                child.streak_milestones_achieved = []

            achieved = set(child.streak_milestones_achieved or [])
            milestone_bonus = 0
            for days, bonus_pts in milestones.items():
                if child.current_streak >= days and days not in achieved:
                    milestone_bonus += bonus_pts
                    achieved.add(days)
                    _LOGGER.info(
                        "Streak milestone %d days reached for %s: +%d bonus",
                        days, child.name, bonus_pts,
                    )

            child.streak_milestones_achieved = sorted(achieved)

            if milestone_bonus > 0:
                child.points += milestone_bonus
                child.total_points_earned += milestone_bonus
                transaction = PointsTransaction(
                    child_id=child.id,
                    points=milestone_bonus,
                    reason=f"Streak milestone bonus ({child.current_streak} day streak!)",
                    created_at=now,
                )
                self.storage.add_points_transaction(transaction)

        self.storage.update_child(child)
        return total_points

    async def async_prune_history(self, days: int = 90) -> None:
        """Prune completion history older than specified days."""
        cutoff = dt_util.now() - timedelta(days=days)
        all_completions = self.storage.get_completions()
        before = len(all_completions)

        # Keep completions newer than cutoff OR unapproved (pending)
        to_keep = [
            c for c in all_completions
            if c.completed_at >= cutoff or not c.approved
        ]

        if len(to_keep) < before:
            self.storage.replace_completions(to_keep)
            await self.storage.async_save()
            await self.async_refresh()
            _LOGGER.info(
                "Pruned %d completions older than %d days",
                before - len(to_keep), days
            )

    # Child chore order operations
    async def async_set_chore_order(self, child_id: str, chore_order: list[str]) -> None:
        """Set the chore order for a child."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        child.chore_order = chore_order
        self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_set_setting(self, key: str, value: str) -> None:
        """Update a generic setting."""
        self.storage.set_setting(key, value)
        await self.storage.async_save()
        await self.async_refresh()

    # Settings
    async def async_set_points_settings(self, name: str, icon: str) -> None:
        """Update points settings."""
        self.storage.set_points_name(name)
        self.storage.set_points_icon(icon)
        await self.storage.async_save()
        await self.async_refresh()
