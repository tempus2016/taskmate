"""Chore operations mixin for TaskMateCoordinator."""
from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date, datetime
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from . import photos
from .models import Chore, ChoreCompletion, PointsTransaction

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


def _add_months(d: date, months: int) -> date:
    """Step a date forward by calendar months, clamping to the month's last day."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


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
        difficulty: str = "medium",
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

        resolved_mode = (
            assignment_mode
            if assignment_mode in ("everyone", "alternating", "random", "balanced", "first_come", "unassigned")
            else "everyone"
        )
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
            difficulty=difficulty if difficulty in ("easy", "medium", "hard") else "medium",
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
        if active and chore.assignment_mode not in ("everyone", "first_come"):
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

    # ── Sibling chore swaps ──────────────────────────────────────────────
    async def async_request_swap(self, chore_id: str, requester_id: str) -> str:
        """A child requests to take over today's rotation assignment of a chore."""
        from .models import generate_id
        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")
        if getattr(chore, "assignment_mode", "everyone") in ("everyone", "unassigned"):
            raise ValueError("Only rotation chores can be swapped")
        requester = self.get_child(requester_id)
        if not requester:
            raise ValueError(f"Child {requester_id} not found")
        current = getattr(chore, "assignment_current_child_id", "") or ""
        if current == requester_id:
            raise ValueError("Chore is already assigned to that child today")
        req = {
            "id": generate_id(),
            "chore_id": chore_id,
            "requester_id": requester_id,
            "from_child_id": current,
            "created_at": dt_util.now().isoformat(),
            "status": "pending",
        }
        self.storage.add_swap_request(req)
        await self.storage.async_save()
        await self.async_refresh()
        return req["id"]

    async def async_approve_swap(self, req_id: str) -> None:
        """Approve a swap — reassign today's chore to the requester."""
        req = next((r for r in self.storage.get_swap_requests()
                    if r.get("id") == req_id and r.get("status") == "pending"), None)
        if not req:
            raise ValueError(f"Swap request {req_id} not found")
        chore = self.get_chore(req["chore_id"])
        if chore:
            chore.assignment_current_child_id = req["requester_id"]
            self.storage.update_chore(chore)
        self.storage.update_swap_request(req_id, status="approved")
        self.hass.bus.async_fire("taskmate_swap_approved", {
            "chore_id": req["chore_id"], "requester_id": req["requester_id"],
            "from_child_id": req.get("from_child_id", ""),
            "timestamp": dt_util.now().isoformat(),
        })
        await self.storage.async_save()
        await self.async_refresh()

    async def async_reject_swap(self, req_id: str) -> None:
        """Reject (and remove) a pending swap request."""
        self.storage.remove_swap_request(req_id)
        await self.storage.async_save()
        await self.async_refresh()

    def _apply_time_adjustment(self, chore, base: int, completed_at) -> int:
        """Apply a chore's early-bonus / late-penalty based on completion time."""
        due = getattr(chore, "due_time", "") or ""
        if not due:
            return base
        try:
            dh, dm = (int(x) for x in due.split(":"))
        except (ValueError, AttributeError):
            return base
        t = dt_util.as_local(completed_at)
        if (t.hour * 60 + t.minute) <= (dh * 60 + dm):
            return base + int(getattr(chore, "early_bonus", 0) or 0)
        return max(0, base - int(getattr(chore, "late_penalty", 0) or 0))

    async def async_clone_chore(self, chore_id: str) -> Chore:
        """Duplicate an existing chore (config only), returning the new chore.

        The clone copies every configuration field but gets a fresh id, a
        "(copy)" name, fresh bonus-subtask ids, and a clean runtime state
        (no skip/assignment/calendar-publish carry-over, enabled, nothing
        disabled-for).
        """
        source = self.get_chore(chore_id)
        if not source:
            raise ValueError(f"Chore {chore_id} not found")

        data = source.to_dict()
        data.pop("id", None)
        for sub in data.get("bonus_subtasks", []) or []:
            sub.pop("id", None)  # fresh ids for the copied subtasks
        # Reset per-run / ephemeral state so the clone starts clean.
        data["assignment_current_child_id"] = ""
        data["skip_date"] = ""
        data["skip_count"] = 0
        data["publish_calendar_published_dates"] = []
        data["disabled_for"] = []
        data["enabled"] = True

        today = dt_util.as_local(dt_util.now()).date()
        if data.get("schedule_mode") == "one_shot":
            data["created_date"] = today.isoformat()

        clone = Chore.from_dict(data)
        clone.name = f"{source.name} (copy)"

        self.storage.add_chore(clone)
        # Cache today's active child so the card shows it immediately.
        active = self._compute_active_children(clone, today)
        if active and clone.assignment_mode not in ("everyone", "first_come"):
            clone.assignment_current_child_id = active[0]
        await self._publish_chore_to_calendars(clone, today)
        await self.storage.async_save()
        await self.async_refresh()
        return clone

    async def async_bulk_chore_action(
        self, action: str, chore_ids: list[str], assigned_to: list[str] | None = None
    ) -> int:
        """Apply a bulk action to several chores at once. Returns count affected.

        action: "delete" | "enable" | "disable" | "reassign".
        """
        ids = list(dict.fromkeys(chore_ids or []))
        if not ids:
            return 0
        if action not in ("delete", "enable", "disable", "reassign"):
            raise ValueError(f"Unknown bulk action {action}")
        count = 0
        for cid in ids:
            chore = self.storage.get_chore(cid)
            if not chore:
                continue
            if action == "delete":
                self.storage.remove_chore(cid)
            elif action == "enable":
                chore.enabled = True
                chore.disabled_for = []
                self.storage.update_chore(chore)
            elif action == "disable":
                chore.enabled = False
                self.storage.update_chore(chore)
            elif action == "reassign":
                chore.assigned_to = list(assigned_to or [])
                self.storage.update_chore(chore)
            count += 1
        await self.storage.async_save()
        await self.async_refresh()
        return count

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

        chore.assignment_current_child_id = child_id

        self.storage.update_chore(chore)
        await self.storage.async_save()
        await self.async_refresh()
        return chore

    async def async_complete_chore(self, chore_id: str, child_id: str, as_parent: bool = False, photo_url: str = "") -> ChoreCompletion | None:
        """Mark a chore as completed by a child.

        When ``as_parent`` is True the completion auto-approves (the parent is the
        approver) and points are awarded immediately, even for approval-required
        chores. All eligibility validations below still apply.

        Expected "soft" rejections (daily limit reached, first-come race lost,
        rotation not-your-turn / already done today, chore not available yet) are
        normal control flow — they log at debug and return ``None`` rather than
        raising, so they don't spam the HA log at ERROR. Only genuinely bad input
        (unknown chore/child) raises.
        """
        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        # Security: photo_url must be one of OUR upload URLs
        # (/api/taskmate/photo/<uuid>.<ext>). The service accepts it as a free
        # string, so reject foreign/crafted values (e.g. "javascript:..." or an
        # external https URL) before they are stored and later rendered into an
        # href/src in the parent's approval views. An invalid value is dropped to
        # "" — which also means it can't satisfy a require_photo chore below.
        if photo_url and not photos.is_taskmate_photo_url(photo_url):
            _LOGGER.warning(
                "Ignoring invalid photo_url for chore %s (not a TaskMate photo URL)",
                chore_id,
            )
            photo_url = ""

        now = dt_util.now()
        today = dt_util.as_local(now).date()

        # Rotation modes (first_come / alternating / random / balanced) share a
        # SINGLE daily quota across the whole pool. Enforce it here at completion
        # time, not just in the card UI — otherwise a caller can award every pool
        # member by completing the chore once per child_id (one call each).
        assignment_mode = getattr(chore, 'assignment_mode', 'everyone')
        if assignment_mode != 'everyone':
            if self._is_rotation_done_today(chore):
                _LOGGER.debug(
                    "complete_chore no-op: '%s' already completed today (rotation quota filled)",
                    chore.name,
                )
                return None
            # A child may only complete the chore when they are today's active
            # assignee. Parents (as_parent) may complete on behalf of any pool
            # member — e.g. ticking it off for the off-rotation child. first_come
            # keeps its competitive semantics (every pool member may race).
            if not as_parent and assignment_mode != 'first_come':
                if child_id not in self._compute_active_children(chore):
                    _LOGGER.debug(
                        "complete_chore no-op: '%s' not assigned to %s today",
                        chore.name, child.name,
                    )
                    return None

        # Check recurrence window for Mode B chores
        if getattr(chore, 'schedule_mode', 'specific_days') == 'recurring':
            if not self.is_chore_available_for_child(chore, child_id):
                _LOGGER.debug(
                    "complete_chore no-op: '%s' not available yet (recurrence window)",
                    chore.name,
                )
                return None

        # Check availability for one-shot chores
        if getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot':
            if not self.is_chore_available_for_child(chore, child_id):
                _LOGGER.debug(
                    "complete_chore no-op: '%s' not available (one-shot done or expired)",
                    chore.name,
                )
                return None

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
            _LOGGER.debug(
                "complete_chore no-op: daily limit reached for '%s' (%d/%d today)",
                chore.name, todays_completions_count, daily_limit,
            )
            return None

        # A photo-required chore always goes through parent approval (unless a
        # parent is completing on behalf), so the evidence gets reviewed.
        requires_photo = bool(getattr(chore, "require_photo", False))
        # A child cannot complete a photo-required chore without attaching a photo.
        # Enforced here (not just in the card) so the per-chore button entity,
        # automations and Dev Tools can't bypass it. Parents-on-behalf are exempt
        # — they are the reviewer. ValueError is surfaced as a clean
        # ServiceValidationError by the service layer.
        if requires_photo and not as_parent and not (photo_url or "").strip():
            raise ValueError("This chore requires a photo as evidence.")
        auto_approve = as_parent or (not chore.requires_approval and not requires_photo)
        effective_points = self._apply_time_adjustment(
            chore, self.effective_chore_points(chore), now
        )

        completion = ChoreCompletion(
            chore_id=chore_id,
            child_id=child_id,
            completed_at=now,
            approved=auto_approve,
            points_awarded=effective_points if auto_approve else 0,
            photo_url=photo_url or "",
        )

        if auto_approve:
            total_awarded = await self._award_points(child, effective_points, chore_id=chore_id)
            completion.approved = True
            completion.approved_at = dt_util.now()
            completion.points_awarded = total_awarded

        self.storage.add_completion(completion)

        self.hass.bus.async_fire(
            "taskmate_chore_completed",
            {
                "child_id": child.id,
                "child_name": child.name,
                "chore_id": chore.id,
                "chore_name": chore.name,
                "points": effective_points,
                "difficulty": getattr(chore, "difficulty", "medium"),
                "timestamp": dt_util.now().isoformat(),
            },
        )

        # Update last_completed store (window starts at completion time, midnight-rounded)
        self.storage.set_last_completed(chore_id, child_id, now.isoformat())

        # One-shot: if auto-approved, disable for this child immediately
        if getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot' and auto_approve:
            if child_id not in chore.disabled_for:
                chore.disabled_for.append(child_id)
            self._check_one_shot_fully_disabled(chore)
            self.storage.update_chore(chore)

        await self.storage.async_save()

        # Fire approval notification only if it stays pending
        if not auto_approve:
            await self._async_notify_pending_approval(child.name, chore.name, chore.points, completion_id=completion.id)

        await self.async_refresh()

        # Trigger badge evaluation for anything that auto-approved
        if auto_approve and getattr(self, "badges", None):
            await self.badges.evaluate_for_child(child_id, "manual")

        # Auto-approved completions skip the parent-approval path, so they must
        # run the same post-approval progression hooks here — otherwise quest
        # steps and challenges only advance for approval-required chores (#558).
        if auto_approve:
            if hasattr(self, "_async_advance_quests"):
                await self._async_advance_quests(child_id, chore_id)
            if hasattr(self, "_async_evaluate_challenges"):
                await self._async_evaluate_challenges(child_id)

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

        # Clear today's cached current assignee for rotation-mode chores so
        # the "Current" column / child-stats card stops pointing at the
        # original child. The pointer recomputes at the next midnight refresh.
        if getattr(chore, "assignment_mode", "everyone") != "everyone":
            if getattr(chore, "assignment_current_child_id", ""):
                chore.assignment_current_child_id = ""
                self.storage.update_chore(chore)

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
                if completion.approved:
                    _LOGGER.debug(
                        "Completion %s already approved, ignoring duplicate approval",
                        completion_id,
                    )
                    return
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
                        pts = (completion.timed_duration_seconds // rate_seconds) * chore.timed_rate_points if rate_seconds > 0 else 0
                    else:
                        pts = self._apply_time_adjustment(
                            chore, self.effective_chore_points(chore), completion.completed_at
                        )
                    total_awarded = await self._award_points(
                        child, pts, completion_date=comp_date, skip_streak=is_bonus,
                        chore_id=completion.chore_id,
                    )
                    completion.approved = True
                    completion.approved_at = dt_util.now()
                    completion.points_awarded = total_awarded
                    self.storage.update_completion(completion)

                    self.hass.bus.async_fire(
                        "taskmate_chore_approved",
                        {
                            "child_id": completion.child_id,
                            "chore_id": completion.chore_id,
                            "completion_id": completion.id,
                            "timestamp": dt_util.now().isoformat(),
                        },
                    )

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

                    # Advance any chore-chain quests (parent completions only)
                    if not is_bonus and hasattr(self, "_async_advance_quests"):
                        await self._async_advance_quests(completion.child_id, completion.chore_id)

                    # Evaluate daily/weekly challenges (parent completions only)
                    if not is_bonus and hasattr(self, "_async_evaluate_challenges"):
                        await self._async_evaluate_challenges(completion.child_id)

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
                        await self._celebrate(
                            child, "all_chores_done",
                            f"{child.name} finished every chore today!", tier=1,
                        )
                else:
                    _LOGGER.warning(
                        "Cannot approve completion %s: chore (%s) or child (%s) not found",
                        completion_id, completion.chore_id, completion.child_id,
                    )
                return
        _LOGGER.warning("Completion %s not found for approval", completion_id)

    def _reverse_completion_awards(self, target_completion, completions) -> list:
        """Reverse every point/streak/counter award granted by an approved completion.

        Shared by ``async_reject_chore`` (which then deletes the record) and
        ``async_undo_chore_approval`` (which reverts it to pending). Performs the
        child-stat reversal, the bonus-subtask cascade, the recurrence-window
        reset and one-shot re-enable, and **returns the cascaded bonus-subtask
        completions** so the caller can dispose of them as it sees fit. It does
        NOT remove or modify the completion records themselves.
        """
        completion = target_completion
        if completion.points_awarded > 0:
            child = self.get_child(completion.child_id)
            if child:
                child.points = max(0, child.points - completion.points_awarded)
                child.total_points_earned = max(0, child.total_points_earned - completion.points_awarded)
                child.total_chores_completed = max(0, child.total_chores_completed - 1)

                # Only reverse streak for parent completions, and only
                # when this was the child's sole completion that day —
                # streaks are day-based, not per-completion
                if not completion.bonus_subtask_id:
                    reject_date = dt_util.as_local(completion.completed_at).date()
                    other_same_day = any(
                        c.id != completion.id
                        and c.child_id == completion.child_id
                        and not c.bonus_subtask_id
                        and dt_util.as_local(c.completed_at).date() == reject_date
                        for c in completions
                    )
                    if not other_same_day:
                        child.current_streak = max(0, child.current_streak - 1)
                        if getattr(child, "last_completion_date", None) == reject_date.isoformat():
                            remaining = [
                                dt_util.as_local(c.completed_at).date()
                                for c in completions
                                if c.id != completion.id
                                and c.child_id == completion.child_id
                                and not c.bonus_subtask_id
                            ]
                            child.last_completion_date = (
                                max(remaining).isoformat() if remaining else None
                            )
                        # Reverse any streak milestones this completion unlocked.
                        # Milestone bonuses are logged as separate transactions
                        # (not part of points_awarded), so dropping the streak
                        # below a previously-achieved milestone must refund it.
                        achieved = list(child.streak_milestones_achieved or [])
                        lost = [d for d in achieved if d > child.current_streak]
                        if lost:
                            try:
                                milestones = self.parse_milestone_setting(
                                    self.storage.get_setting(
                                        "streak_milestones", self.DEFAULT_STREAK_MILESTONES
                                    )
                                )
                            except ValueError:
                                milestones = self.parse_milestone_setting(
                                    self.DEFAULT_STREAK_MILESTONES
                                )
                            refund = sum(milestones.get(d, 0) for d in lost)
                            if refund > 0:
                                child.points = max(0, child.points - refund)
                                child.total_points_earned = max(
                                    0, child.total_points_earned - refund
                                )
                                child.career_score = (
                                    child.total_points_earned
                                    - child.total_penalties_received
                                )
                                self.storage.add_points_transaction(
                                    PointsTransaction(
                                        child_id=child.id,
                                        points=-refund,
                                        reason="Streak milestone reversed",
                                        created_at=dt_util.now(),
                                    )
                                )
                            child.streak_milestones_achieved = sorted(
                                d for d in achieved if d <= child.current_streak
                            )

                self.storage.update_child(child)

        bonus_completions: list = []
        is_parent = not target_completion.bonus_subtask_id
        if is_parent:
            # Cascade: reverse any bonus sub-task completions for the same
            # chore/child on the same day (caller disposes of the records).
            comp_date = dt_util.as_local(target_completion.completed_at).date()
            bonus_completions = [
                c for c in completions
                if c.chore_id == target_completion.chore_id
                and c.child_id == target_completion.child_id
                and c.bonus_subtask_id
                and c.id != target_completion.id
                and dt_util.as_local(c.completed_at).date() == comp_date
            ]
            if bonus_completions:
                child = self.get_child(target_completion.child_id)
                for bc in bonus_completions:
                    if bc.points_awarded > 0 and child:
                        child.points = max(0, child.points - bc.points_awarded)
                        child.total_points_earned = max(0, child.total_points_earned - bc.points_awarded)
                        child.total_chores_completed = max(0, child.total_chores_completed - 1)
                if child:
                    self.storage.update_child(child)

            # Undo last_completed store so recurrence window resets correctly
            self.storage.undo_last_completed(
                target_completion.chore_id, target_completion.child_id
            )

            # One-shot: re-enable for this child
            chore = self.get_chore(target_completion.chore_id)
            if chore and getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot':
                if target_completion.child_id in chore.disabled_for:
                    chore.disabled_for.remove(target_completion.child_id)
                chore.enabled = True
                self.storage.update_chore(chore)

        return bonus_completions

    async def async_reject_chore(self, completion_id: str) -> None:
        """Reject a chore completion and fully reverse all awards if already granted."""
        completions = self.storage.get_completions()
        target_completion = next(
            (c for c in completions if c.id == completion_id), None
        )

        if target_completion:
            bonus_completions = self._reverse_completion_awards(
                target_completion, completions
            )
            for bc in bonus_completions:
                self.storage.remove_completion(bc.id)

        self.storage.remove_completion(completion_id)
        # The completion record is gone, so its evidence photo is now orphaned —
        # delete it (best-effort; foreign/blank URLs are ignored).
        if target_completion and getattr(target_completion, "photo_url", ""):
            await photos.async_delete_photo(self.hass, target_completion.photo_url)
        await self.storage.async_save()
        await self.async_refresh()

        if target_completion:
            child = self.get_child(target_completion.child_id)
            chore = self.get_chore(target_completion.chore_id)
            self.hass.bus.async_fire("taskmate_chore_rejected", {
                "child_id": target_completion.child_id,
                "child_name": getattr(child, "name", ""),
                "chore_id": target_completion.chore_id,
                "chore_name": getattr(chore, "name", ""),
                "completion_id": completion_id,
                "timestamp": dt_util.now().isoformat(),
            })

    async def async_undo_chore_approval(self, completion_id: str) -> None:
        """Undo an accidental approval: reverse the awards and return the
        completion to *pending* so it re-enters the approval queue.

        Distinct from reject (which deletes the child's submission): undo treats
        the completion as still valid, just not-yet-approved. It does NOT notify
        the child — it is a parent correcting their own slip. Derived
        weekend/streak bonuses and earned badges are not separately reversed
        (same limitation as reject — see audit ERR-3).
        """
        completions = self.storage.get_completions()
        target = next((c for c in completions if c.id == completion_id), None)
        if not target:
            raise ValueError(f"Completion {completion_id} not found")
        if not target.approved:
            raise ValueError("Completion is not approved; nothing to undo")

        bonus_completions = self._reverse_completion_awards(target, completions)
        for bc in bonus_completions:
            bc.approved = False
            bc.approved_at = None
            bc.points_awarded = 0
            self.storage.update_completion(bc)

        target.approved = False
        target.approved_at = None
        target.points_awarded = 0
        self.storage.update_completion(target)

        await self.storage.async_save()
        await self.async_refresh()

        child = self.get_child(target.child_id)
        chore = self.get_chore(target.chore_id)
        self.hass.bus.async_fire("taskmate_chore_approval_undone", {
            "child_id": target.child_id,
            "child_name": getattr(child, "name", ""),
            "chore_id": target.chore_id,
            "chore_name": getattr(chore, "name", ""),
            "completion_id": completion_id,
            "timestamp": dt_util.now().isoformat(),
        })

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

        # Vacation / pause mode: while away, all chores are hidden. Covers the
        # global static range, the family vacation calendar, and this child's
        # own availability sensor (per-child vacation).
        if self._is_child_on_vacation(self.storage.get_child(child_id)):
            return False

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
        }.get(recurrence, 7)

        record = self.storage.get_last_completed(chore.id, child_id)
        current_iso = record.get('current')

        if not current_iso:
            # Never completed — a future recurrence anchor always defers
            # availability, regardless of first_occurrence_mode
            if recurrence_start:
                try:
                    if date.fromisoformat(recurrence_start) > today:
                        return False
                except ValueError:
                    pass
            if first_occurrence_mode == 'wait_for_first_occurrence' and recurrence_day:
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

        # Month-based recurrences use real calendar months so availability
        # matches the calendar projection (a "monthly" chore re-opens on the
        # same day next month, not after a fixed 30 days)
        month_steps = {'monthly': 1, 'every_3_months': 3, 'every_6_months': 6}.get(recurrence)
        if month_steps:
            return today >= _add_months(last_dt, month_steps)

        days_since = (today - last_dt).days
        return days_since >= window_days

    async def _async_expire_dated_chores(self) -> None:
        """Soft-disable any enabled chore whose expires_on date has passed."""
        today = dt_util.as_local(dt_util.now()).date()
        changed = False
        for chore in self.storage.get_chores():
            if not getattr(chore, "enabled", True):
                continue
            expires_on = getattr(chore, "expires_on", "")
            if not expires_on:
                continue
            try:
                if date.fromisoformat(expires_on) < today:
                    chore.enabled = False
                    self.storage.update_chore(chore)
                    changed = True
                    _LOGGER.info(
                        "Chore '%s' expired (expires_on %s, today %s)",
                        chore.name, expires_on, today.isoformat(),
                    )
            except ValueError:
                continue
        if changed:
            await self.storage.async_save()
            await self.async_refresh()

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
