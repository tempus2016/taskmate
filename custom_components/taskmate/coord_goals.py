"""Personal weekly goals: a child picks their own target for the week.

"I want to earn 120 this week." The child (or a parent) sets a points target;
once the points the child has earned since Monday reach it, they get the
family's goal bonus — once per week. The target carries over from week to
week until it is changed, so a child who likes their goal doesn't have to set
it every Monday.

Turned on with the ``weekly_goal_enabled`` setting; ``weekly_goal_bonus`` is
the fixed bonus (0 = just the satisfaction of hitting it).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import NOTIF_TYPE_WEEKLY_GOAL_REACHED
from .models import PointsTransaction

WEEKLY_GOAL_MAX = 100000


def _week_key(day) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


class WeeklyGoalsMixin:
    """Child-set weekly points targets with a once-a-week bonus."""

    def weekly_goals_enabled(self) -> bool:
        v = self.storage.get_setting("weekly_goal_enabled", False)
        return v is True or str(v).lower() == "true"

    def weekly_goal_bonus(self) -> int:
        try:
            return max(0, int(self.storage.get_setting("weekly_goal_bonus", 10) or 0))
        except (TypeError, ValueError):
            return 0

    def _weekly_goals(self) -> dict[str, dict[str, Any]]:
        return self.storage.get_section("weekly_goals", dict)

    def week_points_earned(self, child_id: str, exclude_ids: set | None = None) -> int:
        """Approved chore points since Monday — the same figure the cards show.

        ``exclude_ids`` leaves out completions about to be reversed.
        """
        today = dt_util.as_local(dt_util.now()).date()
        week_start = today - timedelta(days=today.weekday())
        total = 0
        for comp in self.storage.get_completions():
            if comp.child_id != child_id or not comp.approved or comp.bonus_subtask_id:
                continue
            if exclude_ids and comp.id in exclude_ids:
                continue
            if dt_util.as_local(comp.completed_at).date() >= week_start:
                total += comp.points_awarded or 0
        return total

    def weekly_goal_state(self, child_id: str) -> dict[str, Any] | None:
        """What a card needs to draw the goal, or None when there's nothing to show."""
        if not self.weekly_goals_enabled():
            return None
        goal = self._weekly_goals().get(child_id) or {}
        target = int(goal.get("target", 0) or 0)
        today = dt_util.as_local(dt_util.now()).date()
        state: dict[str, Any] = {"target": target, "bonus": self.weekly_goal_bonus()}
        if target:
            state["earned"] = self.week_points_earned(child_id)
            state["reached"] = goal.get("reached_week") == _week_key(today)
        return state

    async def async_set_weekly_goal(self, child_id: str, target: int, *, as_parent: bool = False) -> None:
        """Set (or clear, with 0) a child's weekly target.

        ``as_parent`` is a grown-up setting it on the child's behalf. A child
        setting their own goal is held to two rules a parent isn't: the
        target is at least the bonus it pays, so a goal of 1 can't farm a
        10-point bonus every week; and it can't move once this week's bonus
        has been paid, because lowering it would keep a bonus the week no
        longer earns when a completion is reversed.
        """
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        if not self.weekly_goals_enabled():
            raise ValueError("Weekly goals are switched off.")
        target = int(target)
        if not 0 <= target <= WEEKLY_GOAL_MAX:
            raise ValueError(f"Pick a goal from 0 to {WEEKLY_GOAL_MAX}.")
        # The record outlives a cleared goal: it keeps ``reached_week``, so
        # clearing and re-setting a goal can't pay the same week's bonus twice.
        goal = self._weekly_goals().setdefault(child_id, {})
        if not as_parent:
            bonus = self.weekly_goal_bonus()
            if target and bonus and target < bonus:
                raise ValueError(f"A goal has to be at least {bonus}, the bonus it pays.")
            week = _week_key(dt_util.as_local(dt_util.now()).date())
            if goal.get("reached_week") == week and target != int(goal.get("target", 0) or 0):
                raise ValueError("This week's goal has already been reached and paid, so it can't change until Monday.")
        goal["target"] = target
        goal["set_at"] = dt_util.now().isoformat()
        await self.storage.async_save()
        # Setting a goal you've already passed counts straight away.
        await self.async_check_weekly_goals(refresh=False)
        await self.async_refresh()

    async def async_check_weekly_goals(self, refresh: bool = True) -> int:
        """Pay the bonus to every child who reached their goal this week. Idempotent."""
        if not self.weekly_goals_enabled():
            return 0
        today = dt_util.as_local(dt_util.now()).date()
        week = _week_key(today)
        bonus = self.weekly_goal_bonus()
        paid = 0
        for child_id, goal in list(self._weekly_goals().items()):
            target = int(goal.get("target", 0) or 0)
            if not target or goal.get("reached_week") == week:
                continue
            child = self.get_child(child_id)
            if child is None:
                continue
            earned = self.week_points_earned(child_id)
            if earned < target:
                continue
            goal["reached_week"] = week
            goal["bonus_paid"] = bonus
            # The target the bonus was judged against: a reversal later this
            # week is judged against this, not whatever the target is by then.
            goal["paid_target"] = target
            await self.storage.async_save()
            if bonus:
                await self.async_add_points(child_id, bonus, reason=f"Weekly goal reached 🎯 ({target})")
            paid += 1
            await self.notifications.fire(
                NOTIF_TYPE_WEEKLY_GOAL_REACHED,
                {
                    "child_id": child_id,
                    "child_name": child.name,
                    "target": target,
                    "earned": earned,
                    "bonus": bonus,
                    "points_name": self.storage.get_points_name(),
                },
            )
        if paid and refresh:
            await self.async_refresh()
        return paid

    @staticmethod
    def _paid_target(goal: dict[str, Any]) -> int:
        """The target this week's bonus was paid for (the current one on older records)."""
        return int(goal.get("paid_target") or goal.get("target", 0) or 0)

    def _weekly_goal_refund_owed(self, child_id: str, exclude_ids: set | None = None) -> int:
        """The goal bonus a reversal of ``exclude_ids`` would take back, without doing it."""
        if not self.weekly_goals_enabled():
            return 0
        goal = self._weekly_goals().get(child_id) or {}
        target = self._paid_target(goal)
        week = _week_key(dt_util.as_local(dt_util.now()).date())
        if not target or goal.get("reached_week") != week:
            return 0
        if self.week_points_earned(child_id, exclude_ids) >= target:
            return 0
        return max(0, int(goal.get("bonus_paid", self.weekly_goal_bonus()) or 0))

    async def async_reverse_weekly_goals(self, child_id: str) -> None:
        """Take the goal bonus back when this week's points no longer reach the target.

        Called after a completion has been reversed and left the week's
        total. The goal can be reached, and paid, again later in the week.
        """
        if not self.weekly_goals_enabled():
            return
        goal = self._weekly_goals().get(child_id) or {}
        target = self._paid_target(goal)
        week = _week_key(dt_util.as_local(dt_util.now()).date())
        if not target or goal.get("reached_week") != week:
            return
        if self.week_points_earned(child_id) >= target:
            return
        child = self.get_child(child_id)
        if child is None:
            return
        bonus = max(0, int(goal.pop("bonus_paid", self.weekly_goal_bonus()) or 0))
        goal.pop("reached_week", None)
        goal.pop("paid_target", None)
        if bonus:
            child.points = max(0, child.points - bonus)
            child.total_points_earned = max(0, child.total_points_earned - bonus)
            child.career_score = child.total_points_earned - child.total_penalties_received
            self.storage.update_child(child)
            self.storage.add_points_transaction(
                PointsTransaction(
                    child_id=child.id,
                    points=-bonus,
                    reason=f"Weekly goal reversed ({target})",
                    created_at=dt_util.now(),
                ),
                reverses_season=True,
            )
        await self.storage.async_save()
        await self.async_refresh()
