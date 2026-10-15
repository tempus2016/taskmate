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

    def week_points_earned(self, child_id: str) -> int:
        """Approved chore points since Monday — the same figure the cards show."""
        today = dt_util.as_local(dt_util.now()).date()
        week_start = today - timedelta(days=today.weekday())
        total = 0
        for comp in self.storage.get_completions():
            if comp.child_id != child_id or not comp.approved or comp.bonus_subtask_id:
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

    async def async_set_weekly_goal(self, child_id: str, target: int) -> None:
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        if not self.weekly_goals_enabled():
            raise ValueError("Weekly goals are switched off.")
        target = int(target)
        if not 0 <= target <= WEEKLY_GOAL_MAX:
            raise ValueError(f"Pick a goal from 0 to {WEEKLY_GOAL_MAX}.")
        goals = self._weekly_goals()
        goal = goals.setdefault(child_id, {})
        goal["target"] = target
        goal["set_at"] = dt_util.now().isoformat()
        if not target:
            goals.pop(child_id, None)
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
