"""Points operations mixin for TaskMateCoordinator."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from .models import Bonus, Child, Penalty, PointsTransaction

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

                if getattr(self, "badges", None):
                    await self.badges.evaluate_for_child(child.id, "perfect_week")
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

    async def async_add_points(self, child_id: str, points: int, reason: str = "") -> None:
        """Add points to a child (bonus)."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        child.points += points
        child.total_points_earned += points
        child.career_score = child.total_points_earned - child.total_penalties_received
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
        skip_streak: bool = False,
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
        if not skip_streak:
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

        # ── Streak milestone bonus ──────────────────────────────────────────
        milestones_enabled = self.storage.get_setting("streak_milestones_enabled", "true") == "true"
        if not skip_streak and milestones_enabled and child.current_streak > 0:
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
