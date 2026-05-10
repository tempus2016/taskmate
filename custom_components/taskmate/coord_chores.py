"""Chore operations mixin for TaskMateCoordinator."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from .models import Chore, ChoreCompletion

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class ChoresMixin:
    """Mixin providing chore CRUD and completion logic."""

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

        # Cyclical: A → B → … → unassigned → back to A.
        # skip_count < pool_size  → advance to next child
        # skip_count == pool_size → unassigned (no child today)
        # skip_count >  pool_size → reset to 0, back to original assignee
        if chore.skip_count >= len(pool):
            chore.skip_count = 0
        else:
            chore.skip_count += 1

        self.storage.update_chore(chore)

        if chore.skip_count == len(pool):
            chore.assignment_current_child_id = ""
        else:
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

        # Check daily limit (only count parent completions, not bonus sub-tasks)
        all_completions = self.storage.get_completions()
        todays_completions_count = 0
        for comp in all_completions:
            if comp.chore_id == chore_id and comp.child_id == child_id and not comp.bonus_subtask_id:
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
            await self._async_notify_pending_approval(child.name, chore.name, chore.points, completion_id=completion.id)

        await self.async_refresh()

        # Trigger badge evaluation for auto-approved chores (no parent sign-off needed)
        if not chore.requires_approval and getattr(self, "badges", None):
            await self.badges.evaluate_for_child(child_id, "manual")

        return completion

    async def async_parent_complete_chore(self, chore_id: str) -> ChoreCompletion:
        """Mark a chore as completed by the parent — zero points, advances recurrence."""
        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")

        if not getattr(chore, 'enabled', True):
            raise ValueError(f"Chore '{chore.name}' is disabled")

        schedule_mode = getattr(chore, 'schedule_mode', 'specific_days')
        if schedule_mode == 'one_shot':
            raise ValueError(
                f"Chore '{chore.name}' is a one-shot chore and cannot be parent-completed"
            )

        now = dt_util.now()

        # Determine child pool — empty assigned_to means all children
        assigned = getattr(chore, 'assigned_to', []) or []
        if assigned:
            child_ids = list(assigned)
        else:
            child_ids = [c.id for c in self.storage.get_children()]

        if not child_ids:
            raise ValueError(f"Chore '{chore.name}' has no children to suppress")

        completion = ChoreCompletion(
            chore_id=chore_id,
            child_id="__parent__",
            completed_at=now,
            approved=True,
            approved_at=now,
            points_awarded=0,
        )

        self.storage.add_completion(completion)

        # Update last_completed for ALL children in the pool so the chore
        # disappears from their views until the next recurrence window.
        for cid in child_ids:
            self.storage.set_last_completed(chore_id, cid, now.isoformat())

        await self.storage.async_save()
        await self.async_refresh()

        return completion

    async def async_complete_bonus_subtask(
        self, chore_id: str, bonus_subtask_id: str, child_id: str
    ) -> ChoreCompletion:
        """Complete a bonus sub-task (only available after parent chore is completed today)."""
        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")

        subtask = next((b for b in chore.bonus_subtasks if b.id == bonus_subtask_id), None)
        if not subtask:
            raise ValueError(f"Bonus sub-task {bonus_subtask_id} not found on chore '{chore.name}'")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        now = dt_util.now()
        today = dt_util.as_local(now).date()

        # Gate check: parent chore must be completed today
        all_completions = self.storage.get_completions()
        parent_done_today = any(
            c.chore_id == chore_id
            and c.child_id == child_id
            and not c.bonus_subtask_id
            and dt_util.as_local(c.completed_at).date() == today
            for c in all_completions
        )
        if not parent_done_today:
            raise ValueError(
                f"Cannot complete bonus sub-task '{subtask.name}' — "
                f"parent chore '{chore.name}' must be completed first today."
            )

        # Duplicate check: bonus sub-task not already completed today
        already_done = any(
            c.chore_id == chore_id
            and c.child_id == child_id
            and c.bonus_subtask_id == bonus_subtask_id
            and dt_util.as_local(c.completed_at).date() == today
            for c in all_completions
        )
        if already_done:
            raise ValueError(
                f"Bonus sub-task '{subtask.name}' already completed today."
            )

        completion = ChoreCompletion(
            chore_id=chore_id,
            child_id=child_id,
            completed_at=now,
            approved=not chore.requires_approval,
            points_awarded=subtask.points if not chore.requires_approval else 0,
            bonus_subtask_id=bonus_subtask_id,
        )

        if not chore.requires_approval:
            total_awarded = await self._award_points(child, subtask.points, skip_streak=True)
            completion.approved = True
            completion.approved_at = dt_util.now()
            completion.points_awarded = total_awarded

        self.storage.add_completion(completion)
        await self.storage.async_save()

        if chore.requires_approval:
            await self._async_notify_pending_approval(
                child.name, f"{chore.name} › {subtask.name}", subtask.points, completion_id=completion.id
            )

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
                    is_bonus = bool(completion.bonus_subtask_id)
                    if is_bonus:
                        subtask = next(
                            (b for b in chore.bonus_subtasks if b.id == completion.bonus_subtask_id), None
                        )
                        pts = subtask.points if subtask else 0
                    elif completion.timed_duration_seconds > 0 and chore.task_type == "timed":
                        rate_seconds = chore.timed_rate_minutes * 60
                        pts = (completion.timed_duration_seconds // rate_seconds) * chore.timed_rate_points
                    else:
                        pts = chore.points
                    total_awarded = await self._award_points(
                        child, pts, completion_date=comp_date, skip_streak=is_bonus
                    )
                    completion.approved = True
                    completion.approved_at = dt_util.now()
                    completion.points_awarded = total_awarded
                    self.storage.update_completion(completion)

                    # One-shot: disable for this child on approval (parent completions only)
                    if not is_bonus and getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot':
                        if completion.child_id not in chore.disabled_for:
                            chore.disabled_for.append(completion.child_id)
                        self._check_one_shot_fully_disabled(chore)
                        self.storage.update_chore(chore)

                    await self.storage.async_save()
                    await self.async_refresh()

                    # Trigger badge evaluation after approval awards points/chore count/streak
                    if getattr(self, "badges", None):
                        await self.badges.evaluate_for_child(completion.child_id, "manual")

                    # All-chores-done celebration — fire once per child per day
                    today_iso = dt_util.now().date().isoformat()
                    flag_key = f"all_done_{child.id}_{today_iso}"
                    flags = self.storage._data.setdefault("all_done_flags", {})
                    if flag_key not in flags and not self.notifications._has_outstanding_chores_today(child.id):
                        flags[flag_key] = True
                        await self.notifications.fire(
                            "all_chores_done",
                            {"child_name": child.name, "child_id": child.id},
                        )
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
                        child.points = max(0, child.points - completion.points_awarded)
                        child.total_points_earned = max(0, child.total_points_earned - completion.points_awarded)
                        child.total_chores_completed = max(0, child.total_chores_completed - 1)

                        # Only reverse streak for parent completions
                        if not completion.bonus_subtask_id:
                            child.current_streak = max(0, child.current_streak - 1)

                        self.storage.update_child(child)
                break

        if target_completion:
            is_parent = not target_completion.bonus_subtask_id

            # Cascade: if rejecting a parent completion, also reverse any bonus sub-task
            # completions for the same chore/child on the same day
            if is_parent:
                comp_date = dt_util.as_local(target_completion.completed_at).date()
                bonus_completions = [
                    c for c in completions
                    if c.chore_id == target_completion.chore_id
                    and c.child_id == target_completion.child_id
                    and c.bonus_subtask_id
                    and c.id != completion_id
                    and dt_util.as_local(c.completed_at).date() == comp_date
                ]
                if bonus_completions:
                    child = self.get_child(target_completion.child_id)
                    for bc in bonus_completions:
                        if bc.points_awarded > 0 and child:
                            child.points = max(0, child.points - bc.points_awarded)
                            child.total_points_earned = max(0, child.total_points_earned - bc.points_awarded)
                            child.total_chores_completed = max(0, child.total_chores_completed - 1)
                        self.storage.remove_completion(bc.id)
                    if child:
                        self.storage.update_child(child)

            # Undo last_completed store so recurrence window resets correctly (parent only)
            if is_parent:
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

    async def async_set_chore_order(self, child_id: str, chore_order: list[str]) -> None:
        """Set the chore order for a child."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        child.chore_order = chore_order
        self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_set_global_chore_order(self, chore_order: list[str]) -> None:
        """Set the global chore display order."""
        self.storage.set_chore_display_order(chore_order)
        await self.storage.async_save()
        await self.async_refresh()

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
        from .models import TaskGroup
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
