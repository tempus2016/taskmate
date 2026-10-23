"""Per-chore streaks, the completion heatmap and the tomorrow preview.

All three are read-only views over data TaskMate already keeps:

* **Per-chore streaks** — for each child and chore, how many of the chore's
  due days in a row the child did it. Only days the chore is scheduled count,
  so a Monday/Wednesday/Friday chore isn't broken on Tuesday. Holidays, sick
  days and a birthday day off neither count nor break it, and today only
  counts once it's done. On a turn-taking chore a day a sibling did it is
  skipped rather than breaking the streak.
* **Completion heatmap** — chores done per child per day, for the last few
  weeks, for the Insights calendar and the heatmap card.
* **Tomorrow preview** — the chores due for a child tomorrow, worked out with
  the same scheduling rules as today's list, so the card never has to
  reimplement recurrence.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

# Streaks shorter than this aren't worth a tag (and stay off the sensor).
CHORE_STREAK_MIN = 2
# How far back a per-chore streak is followed.
CHORE_STREAK_LOOKBACK = 366
# The heatmap the sensor carries: six weeks, ending today.
HEATMAP_DAYS = 42
HEATMAP_MAX_DAYS = 120


def _local_day(when) -> date | None:
    try:
        return dt_util.as_local(when).date()
    except (TypeError, ValueError, AttributeError):
        return None


class ChoreInsightsMixin:
    """Per-chore streaks, the completion heatmap and tomorrow's chores."""

    # ── per-chore streaks ────────────────────────────────────────────────

    def chore_streaks(self, children, chores, completions, today: date | None = None) -> dict[str, dict[str, int]]:
        """``{child_id: {chore_id: days}}`` for every streak of at least two."""
        today = today or dt_util.as_local(dt_util.now()).date()
        floor = today - timedelta(days=CHORE_STREAK_LOOKBACK)
        mine: dict[tuple[str, str], set[date]] = {}
        anyone: dict[str, set[date]] = {}
        for comp in completions:
            if getattr(comp, "bonus_subtask_id", ""):
                continue
            day = _local_day(comp.completed_at)
            if day is None or not floor <= day <= today:
                continue
            anyone.setdefault(comp.chore_id, set()).add(day)
            mine.setdefault((comp.child_id, comp.chore_id), set()).add(day)
        out: dict[str, dict[str, int]] = {}
        for child in children:
            streaks = {}
            for chore in chores:
                days = mine.get((child.id, chore.id))
                if not days or len(days) < CHORE_STREAK_MIN:
                    continue
                n = self._chore_streak(child, chore, days, anyone.get(chore.id, set()), today, floor)
                if n >= CHORE_STREAK_MIN:
                    streaks[chore.id] = n
            if streaks:
                out[child.id] = streaks
        return out

    def _chore_streak(self, child, chore, days: set[date], anyone: set[date], today: date, floor: date) -> int:
        """Consecutive due days, newest first, on which ``child`` did ``chore``."""
        if not getattr(chore, "enabled", True) or child.id in (getattr(chore, "disabled_for", None) or []):
            return 0
        if int(getattr(chore, "weekly_target", 0) or 0) > 0:
            return 0  # owed by Sunday, not on any one day
        assigned = getattr(chore, "assigned_to", None) or []
        if assigned and child.id not in assigned:
            return 0
        rotating = getattr(chore, "assignment_mode", "everyone") not in ("", "everyone")
        mandatory = getattr(chore, "mandatory", False)
        streak = 0
        day = today
        while day >= floor:
            if self._is_chore_scheduled_for_date(chore, day):
                if day in days:
                    streak += 1
                elif day == today or (rotating and day in anyone):
                    pass  # still time today / a sibling's turn
                elif not self._chore_streak_excused(child, day, mandatory):
                    break
            day -= timedelta(days=1)
        return streak

    def _chore_streak_excused(self, child, day: date, mandatory: bool) -> bool:
        """A holiday, a sick day or a birthday day off never breaks a streak."""
        if self.is_vacation_day(day) or self.is_sick_day(child.id, day):
            return True
        return not mandatory and self.is_birthday_day_off(child, day)

    # ── completion heatmap ───────────────────────────────────────────────

    def completion_heatmap(
        self, completions, days: int = HEATMAP_DAYS, today: date | None = None
    ) -> dict[str, list[int]]:
        """``{child_id: [count, ...]}`` per day, oldest first, ending today.

        Counts every chore a child did (approved or waiting), not bonus
        sub-tasks. Children with nothing in the window are left out.
        """
        days = max(1, min(int(days or HEATMAP_DAYS), HEATMAP_MAX_DAYS))
        today = today or dt_util.as_local(dt_util.now()).date()
        start = today - timedelta(days=days - 1)
        out: dict[str, list[int]] = {}
        for comp in completions:
            if getattr(comp, "bonus_subtask_id", "") or comp.child_id == "__parent__":
                continue
            day = _local_day(comp.completed_at)
            if day is None or not start <= day <= today:
                continue
            out.setdefault(comp.child_id, [0] * days)[(day - start).days] += 1
        return out

    def heatmap_report(self, days: int = HEATMAP_DAYS) -> dict[str, Any]:
        """The Insights calendar: every child's daily counts, oldest first."""
        days = max(7, min(int(days or HEATMAP_DAYS), HEATMAP_MAX_DAYS))
        today = dt_util.as_local(dt_util.now()).date()
        counts = self.completion_heatmap(self.storage.get_completions(), days, today)
        rows = []
        for child in self.storage.get_children():
            series = counts.get(child.id) or [0] * days
            rows.append(
                {
                    "id": child.id,
                    "name": child.name,
                    "counts": series,
                    "total": sum(series),
                    "active_days": sum(1 for n in series if n),
                    "best": max(series),
                }
            )
        start = today - timedelta(days=days - 1)
        return {"days": days, "start": start.isoformat(), "end": today.isoformat(), "children": rows}

    # ── tomorrow preview ─────────────────────────────────────────────────

    def chores_due_on(self, child_id: str, day: date) -> list[str]:
        """Chore ids due for ``child_id`` on ``day``, in the chores' own order."""
        due = self._due_chore_ids_for_child(child_id, day, include_rotation=True)
        return [c.id for c in self.storage.get_chores() if c.id in due]

    def tomorrow_chore_ids(self, child_id: str) -> list[str]:
        """What's due for the child tomorrow (empty on a holiday or sick day)."""
        tomorrow = dt_util.as_local(dt_util.now()).date() + timedelta(days=1)
        if self.is_vacation_day(tomorrow) or self.is_sick_day(child_id, tomorrow):
            return []
        return self.chores_due_on(child_id, tomorrow)
