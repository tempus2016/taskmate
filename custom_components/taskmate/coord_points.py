"""Points operations mixin for TaskMateCoordinator."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from . import photos
from .models import Bonus, Child, Penalty, PointsTransaction, generate_id

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class PointsMixin:
    """Mixin providing points, streaks, penalties, bonuses, and notifications."""

    async def _async_check_perfect_week(self) -> None:
        """Award perfect week bonus to children who completed at least one chore every day last week."""
        perfect_week_enabled = self.storage.get_setting("perfect_week_enabled", "true") == "true"
        if not perfect_week_enabled:
            return

        try:
            perfect_week_bonus = int(self.storage.get_setting("perfect_week_bonus", "50"))
        except (ValueError, TypeError):
            perfect_week_bonus = 50

        # #563: require every chore due each day (not just one) to count the day.
        all_mode = self._setting_enabled("perfect_week_requires_all_chores")

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
        chores = [c for c in self.storage.get_chores() if getattr(c, "enabled", True)]
        changed = False

        def _required_dates(child_id: str) -> set[str]:
            """Days last week on which the child had at least one scheduled chore.

            A perfect week shouldn't demand completions on days with nothing
            due (e.g. weekends for weekday-only chores). Rotation-mode chores
            are skipped — who was active on a past day can't be reconstructed.
            """
            req: set[str] = set()
            for d_str in last_week_dates:
                day = date.fromisoformat(d_str)
                for chore in chores:
                    assigned = chore.assigned_to or []
                    if assigned and child_id not in assigned:
                        continue
                    if child_id in getattr(chore, "disabled_for", []):
                        continue
                    if getattr(chore, "assignment_mode", "everyone") not in ("", "everyone"):
                        continue
                    if self._is_chore_scheduled_for_date(chore, day):
                        req.add(d_str)
                        break
            return req

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

            # If no scheduled days can be derived (e.g. rotation-only setups),
            # fall back to requiring a completion on all 7 days as before
            derived_dates = _required_dates(child.id)
            required_dates = derived_dates or last_week_dates
            # #563: when enabled (and the required days could be derived), a day
            # counts only when EVERY chore due that day was done — not just one.
            if all_mode and derived_dates:
                satisfied = all(
                    self._all_due_chores_done(
                        child.id, date.fromisoformat(d), include_rotation=False
                    )
                    for d in derived_dates
                )
            else:
                satisfied = completed_days >= required_dates
            if satisfied:
                # Perfect week!
                child.awarded_perfect_weeks = awarded_weeks + [week_key]
                child.points += perfect_week_bonus
                child.total_points_earned += perfect_week_bonus
                child.career_score = child.total_points_earned - child.total_penalties_received
                self.storage.append_career_score_snapshot(
                    child.id, today.isoformat(), child.career_score
                )
                self.storage.update_child(child)

                transaction = PointsTransaction(
                    child_id=child.id,
                    points=perfect_week_bonus,
                    reason=f"Perfect week bonus! ({last_monday.strftime('%d %b')} – {(today - timedelta(days=1)).strftime('%d %b')})",
                    created_at=dt_util.now(),
                )
                self.storage.add_points_transaction(transaction)
                changed = True

                self.hass.bus.async_fire(
                    "taskmate_perfect_week",
                    {
                        "child_id": child.id,
                        "week_key": week_key,
                        "bonus": perfect_week_bonus,
                        "timestamp": dt_util.now().isoformat(),
                    },
                )

                if getattr(self, "badges", None):
                    await self.badges.evaluate_for_child(child.id, "perfect_week")
                await self._celebrate(
                    child, "perfect_week",
                    f"{child.name} earned a perfect week — +{perfect_week_bonus}!",
                    tier=3, extra={"bonus": perfect_week_bonus},
                )
                _LOGGER.info(
                    "Perfect week bonus (%d pts) awarded to %s for week of %s",
                    perfect_week_bonus, child.name, week_key,
                )

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    def _streak_breaks_after_gap(self, last_date_str: str, today: date) -> bool:
        """True if a genuine (non-vacation) expected day was missed.

        Walks each day strictly between the last completion and today; if any
        is not a vacation day the child missed it and the streak breaks.
        Days inside a vacation period are forgiven.
        """
        try:
            last_date = date.fromisoformat(last_date_str)
        except (TypeError, ValueError):
            return False
        d = last_date + timedelta(days=1)
        while d < today:
            if not self.is_vacation_day(d):
                return True
            d += timedelta(days=1)
        return False

    async def _async_check_streaks(self) -> None:
        """Check all children's streaks and reset/pause if they missed yesterday.

        Behaviour depends on streak_reset_mode setting:
        - "reset" (default): streak goes back to 0 on missed day
        - "pause": streak is preserved but not incremented until they complete again
        """
        today = dt_util.now().date()

        streak_mode = self.storage.get_setting("streak_reset_mode", "reset")

        children = self.storage.get_children()
        changed = False

        for child in children:
            # Frozen while away — static vacation range, the global family
            # calendar, or this child's own availability sensor. Mark the streak
            # paused so it resumes intact on return in BOTH reset and pause
            # modes (the resume path in _award_points honours streak_paused).
            if self._is_child_on_vacation(child, today):
                if (child.current_streak or 0) > 0 and not getattr(child, "streak_paused", False):
                    child.streak_paused = True
                    self.storage.update_child(child)
                    changed = True
                continue

            last_date_str = getattr(child, "last_completion_date", None)
            if last_date_str is None:
                continue  # No completions yet, nothing to do

            # Streak is fine unless a genuine, non-vacation day was missed
            # between the last completion and today.
            if not self._streak_breaks_after_gap(last_date_str, today):
                continue

            # They missed a (non-vacation) day
            if (child.current_streak or 0) > 0:
                # A streak already marked paused (e.g. frozen during an absence)
                # resumes rather than resets, even in reset mode.
                if streak_mode == "pause" or getattr(child, "streak_paused", False):
                    child.streak_paused = True
                    _LOGGER.info(
                        "Streak paused for %s (last completion: %s, mode=%s)",
                        child.name, last_date_str, streak_mode
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

    async def async_add_points(self, child_id: str, points: int, reason: str = "") -> None:
        """Add points to a child (bonus)."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        child.points += points
        child.total_points_earned += points
        child.career_score = child.total_points_earned - child.total_penalties_received
        await self._maybe_level_up(child)
        self.storage.update_child(child)
        self.storage.append_career_score_snapshot(
            child_id, date.today().isoformat(), child.career_score
        )
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

        # Trigger badge evaluation. Skip if this credit came from awarding a badge bonus
        # itself, otherwise we'd recurse back into evaluate_for_child.
        if getattr(self, "badges", None) and not (reason or "").startswith("Badge"):
            await self.badges.evaluate_for_child(child_id, "points_changed")

    async def async_remove_points(self, child_id: str, points: int, reason: str = "") -> None:
        """Remove points from a child (penalty)."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        actual_deducted = min(points, child.points)  # Can't go below 0
        child.points = max(0, child.points - points)
        if reason.startswith("Penalty: "):
            child.total_penalties_received += actual_deducted
            child.career_score = child.total_points_earned - child.total_penalties_received
            self.storage.append_career_score_snapshot(
                child_id, date.today().isoformat(), child.career_score
            )
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

        # Trigger badge evaluation. Skip if this deduction came from a badge revoke
        # path (reason starts with "Badge") to avoid recursion.
        if getattr(self, "badges", None) and not (reason or "").startswith("Badge"):
            await self.badges.evaluate_for_child(child_id, "points_changed")

    # Reason prefixes for *derived* transactions — automatic consequences of
    # other actions. Reversing one in isolation would desync related state, so
    # undo refuses them. NOTE: this is a deny-list because manual add/remove
    # carry arbitrary (or empty) reasons and can't be told apart from free-text
    # by an allow-list. Any NEW derived transaction reason added elsewhere in
    # this file MUST be added here, or it will become wrongly undoable.
    _UNDO_DENY_PREFIXES = (
        "Weekend bonus",
        "Streak milestone bonus",
        "Perfect week bonus",
        "Allocated to pool:",
        "Pool refund",
        "Points decay",
        "Savings interest",
        "Badge",
    )

    async def async_undo_transaction(self, transaction_id: str) -> None:
        """Reverse a discrete points transaction (the inverse of an admin action).

        Reversible: penalties, bonuses, manual add/remove adjustments, and gifts
        (both legs, via ``link_id``). Refused: derived/automatic transactions
        (see ``_UNDO_DENY_PREFIXES``) — reversing them alone would desync state.
        """
        txns = self.storage.get_points_transactions()
        target = next((t for t in txns if t.id == transaction_id), None)
        if not target:
            raise ValueError(f"Transaction {transaction_id} not found")
        reason = target.reason or ""

        if reason.startswith(self._UNDO_DENY_PREFIXES):
            raise ValueError("This action can't be undone")

        # Gifts move spendable balance between two children — reverse every leg
        # sharing the gift's link_id (neither child's earned/penalty totals
        # changed at gift time, so only `points` is adjusted).
        if reason.startswith("Gift to ") or reason.startswith("Gift from "):
            link_id = getattr(target, "link_id", "") or ""
            if not link_id:
                raise ValueError(
                    "This gift predates undo support and can't be reversed automatically."
                )
            for leg in [t for t in txns if (getattr(t, "link_id", "") or "") == link_id]:
                leg_child = self.get_child(leg.child_id)
                if leg_child:
                    leg_child.points = max(0, leg_child.points - leg.points)
                    self.storage.update_child(leg_child)
                self.storage.remove_points_transaction(leg.id)
            await self.storage.async_save()
            await self.async_refresh()
            return

        child = self.get_child(target.child_id)
        if not child:
            raise ValueError(f"Child {target.child_id} not found")

        pts = target.points  # signed: removals < 0, additions > 0
        is_penalty = reason.startswith("Penalty: ")
        child.points = max(0, child.points - pts)
        if is_penalty:
            # Penalty removed points AND raised total_penalties_received.
            child.total_penalties_received = max(0, child.total_penalties_received - abs(pts))
        elif pts > 0:
            # Bonus / manual add raised total_points_earned alongside points.
            child.total_points_earned = max(0, child.total_points_earned - pts)
        # else: a plain (non-penalty) manual removal only touched spendable
        # points, so nothing else to reverse.
        child.career_score = child.total_points_earned - child.total_penalties_received
        self.storage.update_child(child)
        self.storage.append_career_score_snapshot(
            child.id, dt_util.now().date().isoformat(), child.career_score
        )
        self.storage.remove_points_transaction(transaction_id)
        await self.storage.async_save()
        await self.async_refresh()

    # ── Levels / XP ──────────────────────────────────────────────────────
    def _xp_per_level(self) -> int:
        try:
            v = int(float(self.storage.get_setting("level_xp_step", "100")))
        except (ValueError, TypeError):
            v = 100
        return max(1, v)

    def level_for_xp(self, xp: int) -> int:
        """Level derived from cumulative earned points (XP). Level 1 at 0 XP."""
        return max(1, int(xp or 0) // self._xp_per_level() + 1)

    def level_info(self, child) -> dict:
        """{level, progress, target} for a child's current XP."""
        step = self._xp_per_level()
        xp = int(getattr(child, "total_points_earned", 0) or 0)
        lvl = xp // step + 1
        return {"level": lvl, "progress": xp - (lvl - 1) * step, "target": step}

    async def _celebrate(
        self, child, kind: str, message: str, tier: int = 1, extra: dict | None = None
    ) -> None:
        """Central celebration funnel for notable moments.

        Always fires a single ``taskmate_celebration`` event carrying a ``tier``
        (1=small, 2=medium, 3=epic) so one automation can scale its reaction
        (lights, sound, TTS) to the size of the moment. Also fires the opt-in
        ``celebration`` notification when enabled and the moment meets the
        configured minimum tier.
        """
        payload = {
            "child_id": child.id,
            "child_name": child.name,
            "kind": kind,
            "tier": int(tier),
            "message": message,
            "timestamp": dt_util.now().isoformat(),
        }
        if extra:
            payload.update(extra)
        self.hass.bus.async_fire("taskmate_celebration", payload)

        if not getattr(self, "notifications", None):
            return
        enabled = self.storage.get_setting("celebration_notify", False)
        if not (enabled is True or str(enabled).lower() == "true"):
            return
        try:
            min_tier = int(self.storage.get_setting("celebration_notify_min_tier", "2"))
        except (ValueError, TypeError):
            min_tier = 2
        if int(tier) < min_tier:
            return
        await self.notifications.fire(
            "celebration",
            {
                "child_name": child.name,
                "child_id": child.id,
                "kind": kind,
                "tier": int(tier),
                "message": message,
            },
        )

    async def _maybe_level_up(self, child) -> None:
        """Sync child.level to its XP; fire level-up events on an increase.

        Does not save — the caller persists ``child`` afterwards.
        """
        new = self.level_for_xp(getattr(child, "total_points_earned", 0))
        old = getattr(child, "level", 1) or 1
        if new == old:
            return
        child.level = new
        if new < old:
            return  # earned total dropped (e.g. undo); resync quietly
        for lvl in range(old + 1, new + 1):
            self.hass.bus.async_fire("taskmate_level_up", {
                "child_id": child.id, "child_name": child.name,
                "level": lvl, "timestamp": dt_util.now().isoformat(),
            })
            if getattr(self, "notifications", None):
                await self.notifications.fire("level_up", {
                    "child_name": child.name, "child_id": child.id, "level": lvl,
                })
            await self._celebrate(
                child, "level_up", f"{child.name} reached level {lvl}!",
                tier=3 if lvl % 5 == 0 else 2, extra={"level": lvl},
            )

    async def async_gift_points(self, from_child_id: str, to_child_id: str, points: int) -> None:
        """Transfer spendable points from one child to another (parent-controlled).

        Moves spendable balance only — neither child's career score / earned
        total changes (the recipient didn't earn it). Logged on both sides.
        """
        points = int(points)
        if points <= 0:
            raise ValueError("Gift amount must be positive")
        if from_child_id == to_child_id:
            raise ValueError("Cannot gift to the same child")
        sender = self.get_child(from_child_id)
        recipient = self.get_child(to_child_id)
        if not sender or not recipient:
            raise ValueError("Sender or recipient not found")
        if (sender.points or 0) < points:
            raise ValueError(
                f"Not enough points: {sender.name} has {sender.points}, gift {points}"
            )
        now = dt_util.now()
        sender.points -= points
        recipient.points += points
        self.storage.update_child(sender)
        self.storage.update_child(recipient)
        # Shared link_id so undo can reverse both legs together.
        gift_link = generate_id()
        self.storage.add_points_transaction(PointsTransaction(
            child_id=sender.id, points=-points,
            reason=f"Gift to {recipient.name}", created_at=now, link_id=gift_link,
        ))
        self.storage.add_points_transaction(PointsTransaction(
            child_id=recipient.id, points=points,
            reason=f"Gift from {sender.name}", created_at=now, link_id=gift_link,
        ))
        self.hass.bus.async_fire("taskmate_points_gifted", {
            "from_child_id": sender.id, "from_child_name": sender.name,
            "to_child_id": recipient.id, "to_child_name": recipient.name,
            "points": points, "timestamp": now.isoformat(),
        })
        await self.storage.async_save()
        await self.async_refresh()

    async def _async_decay_points(self) -> None:
        """Periodically decay each child's spendable points (anti-hoarding).

        Opt-in via ``points_decay_enabled``. On the period boundary
        (weekly=Mon, monthly=1st) reduces each child's ``points`` by
        ``points_decay_percent`` and logs it. Does not touch career score —
        decay is a spendable-balance reduction, not a penalty.
        """
        enabled = self.storage.get_setting("points_decay_enabled", False)
        if not (enabled is True or str(enabled).lower() == "true"):
            return
        try:
            pct = float(self.storage.get_setting("points_decay_percent", "10"))
        except (ValueError, TypeError):
            pct = 10.0
        if pct <= 0:
            return
        period = self.storage.get_setting("points_decay_period", "monthly")
        today = dt_util.now().date()
        due = (
            (period == "weekly" and today.weekday() == 0)
            or (period == "monthly" and today.day == 1)
        )
        if not due:
            return
        if self.storage.get_setting("points_decay_last", "") == today.isoformat():
            return
        now = dt_util.now()
        changed = False
        for child in self.storage.get_children():
            if (child.points or 0) <= 0:
                continue
            loss = round(child.points * pct / 100.0)
            if loss <= 0:
                continue
            child.points = max(0, child.points - loss)
            self.storage.update_child(child)
            self.storage.add_points_transaction(PointsTransaction(
                child_id=child.id, points=-loss,
                reason=f"Points decay (-{pct:.0f}%)", created_at=now,
            ))
            self.hass.bus.async_fire("taskmate_points_decay", {
                "child_id": child.id, "child_name": child.name,
                "points": loss, "timestamp": now.isoformat(),
            })
            changed = True
        self.storage.set_setting("points_decay_last", today.isoformat())
        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    async def _async_apply_interest(self) -> None:
        """Pay periodic interest on each child's spendable balance (savings reward).

        Opt-in via ``interest_enabled``. On the period boundary (weekly=Mon,
        monthly=1st) credits ``interest_percent`` of the current balance via the
        normal points path (counts as earned, so it also feeds XP).
        """
        enabled = self.storage.get_setting("interest_enabled", False)
        if not (enabled is True or str(enabled).lower() == "true"):
            return
        try:
            pct = float(self.storage.get_setting("interest_percent", "5"))
        except (ValueError, TypeError):
            pct = 5.0
        if pct <= 0:
            return
        period = self.storage.get_setting("interest_period", "weekly")
        today = dt_util.now().date()
        due = (
            (period == "weekly" and today.weekday() == 0)
            or (period == "monthly" and today.day == 1)
        )
        if not due:
            return
        if self.storage.get_setting("interest_last", "") == today.isoformat():
            return
        for child in self.storage.get_children():
            bal = child.points or 0
            if bal <= 0:
                continue
            interest = round(bal * pct / 100.0)
            if interest <= 0:
                continue
            await self.async_add_points(child.id, interest, reason=f"Savings interest (+{pct:.0f}%)")
            self.hass.bus.async_fire("taskmate_interest_paid", {
                "child_id": child.id, "child_name": child.name,
                "points": interest, "timestamp": dt_util.now().isoformat(),
            })
        self.storage.set_setting("interest_last", today.isoformat())
        await self.storage.async_save()

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

    def _setting_enabled(self, key: str, default: str = "false") -> bool:
        """Read a boolean setting that may be stored as a real bool or a
        "true"/"false" string (the panel sends bools; defaults are strings)."""
        v = self.storage.get_setting(key, default)
        return v is True or str(v).lower() == "true"

    def _due_chore_ids_for_child(self, child_id: str, day: date, *, include_rotation: bool) -> set[str]:
        """Chore IDs *due* for ``child_id`` on ``day`` (#563).

        A chore is due when it is enabled, assigned to the child (empty
        ``assigned_to`` = everyone), not disabled for them, and scheduled for
        that date. Rotation-mode chores only count when it's the child's turn —
        and only when ``include_rotation`` is True (past days can't reconstruct
        who was active, so the perfect-week path passes False).
        """
        out: set[str] = set()
        for chore in self.storage.get_chores():
            if not getattr(chore, "enabled", True):
                continue
            assigned = chore.assigned_to or []
            if assigned and child_id not in assigned:
                continue
            if child_id in getattr(chore, "disabled_for", []):
                continue
            mode = getattr(chore, "assignment_mode", "everyone")
            if mode not in ("", "everyone"):
                if not include_rotation:
                    continue
                if child_id not in self._compute_active_children(chore, day):
                    continue
            if not self._is_chore_scheduled_for_date(chore, day):
                continue
            out.add(chore.id)
        return out

    def _completed_chore_ids_for_child(self, child_id: str, day: date) -> set[str]:
        """Chore IDs the child has a (non-bonus) completion for on ``day`` —
        approved or pending, so slow parent approval doesn't break the day."""
        out: set[str] = set()
        for c in self.storage.get_completions():
            if c.child_id != child_id or getattr(c, "bonus_subtask_id", ""):
                continue
            try:
                if dt_util.as_local(c.completed_at).date() == day:
                    out.add(c.chore_id)
            except (ValueError, TypeError, AttributeError):
                continue
        return out

    def _all_due_chores_done(
        self, child_id: str, day: date, *, include_rotation: bool, extra_done: str | None = None
    ) -> bool:
        """True when every chore due for the child on ``day`` has a completion.

        A day with nothing due is satisfied. ``extra_done`` lets the streak path
        count an in-flight completion that hasn't been persisted yet.
        """
        due = self._due_chore_ids_for_child(child_id, day, include_rotation=include_rotation)
        if not due:
            return True
        done = self._completed_chore_ids_for_child(child_id, day)
        if extra_done:
            done = done | {extra_done}
        return due <= done

    async def _award_points(
        self,
        child: Child,
        points: int,
        completion_date: date | None = None,
        skip_streak: bool = False,
        chore_id: str | None = None,
    ) -> int:
        """Award points to a child, update streak, and apply bonus systems.

        Returns the total points awarded (base + weekend bonus), excluding
        milestone bonuses (which are logged as separate transactions).

        If skip_streak is True, streak tracking is skipped (used for bonus
        sub-task completions where the parent already counted).
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
        child.career_score = child.total_points_earned - child.total_penalties_received

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
        streak_reset_occurred = False
        advance_streak = not skip_streak
        # #563: when enabled, the streak only advances once EVERY chore due that
        # day is done. The in-flight completion (chore_id) is counted as done
        # since it may not be persisted yet at this point in the flow.
        if advance_streak and self._setting_enabled("streak_requires_all_chores"):
            if not self._all_due_chores_done(
                child.id, effective_date, include_rotation=True, extra_done=chore_id
            ):
                advance_streak = False
        if advance_streak:
            streak_mode = self.storage.get_setting("streak_reset_mode", "reset")
            streak_paused = getattr(child, "streak_paused", False)
            streak_before = child.current_streak or 0

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

            self.hass.bus.async_fire(
                "taskmate_streak_updated",
                {
                    "child_id": child.id,
                    "current_streak": child.current_streak,
                    "best_streak": child.best_streak,
                    "timestamp": dt_util.now().isoformat(),
                },
            )

        # ── Streak milestone bonus ──────────────────────────────────────────
        reached_milestones: list[tuple[int, int]] = []
        milestones_enabled = self.storage.get_setting("streak_milestones_enabled", "true") == "true"
        if advance_streak and milestones_enabled and child.current_streak > 0:
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
                    reached_milestones.append((days, bonus_pts))
                    _LOGGER.info(
                        "Streak milestone %d days reached for %s: +%d bonus",
                        days, child.name, bonus_pts,
                    )

            child.streak_milestones_achieved = sorted(achieved)

            if milestone_bonus > 0:
                child.points += milestone_bonus
                child.total_points_earned += milestone_bonus
                child.career_score = child.total_points_earned - child.total_penalties_received
                transaction = PointsTransaction(
                    child_id=child.id,
                    points=milestone_bonus,
                    reason=f"Streak milestone bonus ({child.current_streak} day streak!)",
                    created_at=now,
                )
                self.storage.add_points_transaction(transaction)

        self.storage.append_career_score_snapshot(
            child.id, effective_date.isoformat(), child.career_score
        )
        await self._maybe_level_up(child)
        self.storage.update_child(child)

        # Notify on each newly reached streak milestone (off by default; opt-in).
        if reached_milestones and getattr(self, "notifications", None):
            points_name = self.storage.get_points_name()
            for days, bonus_pts in reached_milestones:
                await self.notifications.fire(
                    "streak_milestone",
                    {
                        "child_name": child.name,
                        "child_id": child.id,
                        "days": days,
                        "streak": child.current_streak,
                        "points": bonus_pts,
                        "points_name": points_name,
                    },
                )
        # A big streak is a celebration moment too — epic at 30+ days.
        for days, _bonus_pts in reached_milestones:
            await self._celebrate(
                child, "streak_milestone",
                f"{child.name} hit a {days}-day streak!",
                tier=3 if days >= 30 else 2, extra={"days": days},
            )
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
            kept_ids = {c.id for c in to_keep}
            self.storage.replace_completions(to_keep)
            await self.storage.async_save()
            # Delete evidence photos belonging to the pruned completions so the
            # photos dir doesn't grow forever (best-effort; foreign/blank URLs
            # are ignored by async_delete_photo).
            for c in all_completions:
                if c.id not in kept_ids and getattr(c, "photo_url", ""):
                    await photos.async_delete_photo(self.hass, c.photo_url)
            await self.async_refresh()
            _LOGGER.info(
                "Pruned %d completions older than %d days",
                before - len(to_keep), days
            )

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
        self.hass.bus.async_fire("taskmate_penalty_applied", {
            "child_id": child.id, "child_name": child.name,
            "penalty_id": penalty.id, "penalty_name": penalty.name,
            "points": penalty.points,
            "timestamp": dt_util.now().isoformat(),
        })

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
        self.hass.bus.async_fire("taskmate_bonus_applied", {
            "child_id": child.id, "child_name": child.name,
            "bonus_id": bonus.id, "bonus_name": bonus.name,
            "points": bonus.points,
            "timestamp": dt_util.now().isoformat(),
        })

    async def _async_notify_pending_approval(
        self, child_name: str, chore_name: str, points: int,
        completion_id: str | None = None,
    ) -> None:
        await self.notifications.fire(
            "pending_chore_approval",
            {
                "entry_id": completion_id,
                "child_name": child_name,
                "chore_name": chore_name,
                "points": points,
                "points_name": self.storage.get_points_name(),
            },
        )

    async def _async_notify_pending_reward_claim(
        self, child_name: str, reward_name: str, cost: int,
        claim_id: str | None = None,
    ) -> None:
        await self.notifications.fire(
            "pending_reward_claim",
            {
                "entry_id": claim_id,
                "child_name": child_name,
                "reward_name": reward_name,
                "cost": cost,
                "points_name": self.storage.get_points_name(),
            },
        )
