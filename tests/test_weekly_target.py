"""Weekly target chores: "do this N times this week, on whichever days" (#883).

A chore with ``weekly_target`` set stays available every day it is scheduled
until the child has completed it N times in the current Monday-anchored week.
The quota sits alongside ``daily_limit`` — it caps the week the same way the
daily limit caps the day — and counts pending completions as well as approved
ones, so a slow parent approval never hands a child a spare go.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

UTC = timezone.utc
# Wednesday 22 April 2026; the week it belongs to starts Monday the 20th.
NOW = dt.datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
MONDAY = dt.datetime(2026, 4, 20, 9, 0, 0, tzinfo=UTC)
LAST_SUNDAY = dt.datetime(2026, 4, 19, 9, 0, 0, tzinfo=UTC)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chores, completions=None, available=True):
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_chores = MagicMock(return_value=chores)
    coord.storage.get_completions = MagicMock(return_value=completions or [])
    coord.is_chore_available_for_child = MagicMock(return_value=available)
    return coord


def _count(coord, chore_id="a", child_id="ch1"):
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        return coord.weekly_completion_count(chore_id, child_id)


def _due(coord, child_id="ch1"):
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        return [c.name for c in coord.get_due_chores_for_child(child_id)]


# ── the field ────────────────────────────────────────────────────────────────


def test_weekly_target_defaults_to_zero():
    assert Chore(name="Cello", id="a").weekly_target == 0


def test_weekly_target_round_trips_through_storage():
    chore = Chore(name="Cello", id="a", weekly_target=3)
    assert Chore.from_dict(chore.to_dict()).weekly_target == 3


# ── counting the week ────────────────────────────────────────────────────────


def test_counts_completions_since_monday():
    comps = [
        ChoreCompletion(chore_id="a", child_id="ch1", completed_at=MONDAY),
        ChoreCompletion(chore_id="a", child_id="ch1", completed_at=NOW),
    ]
    assert _count(_coord([], comps)) == 2


def test_ignores_completions_from_last_week():
    comps = [ChoreCompletion(chore_id="a", child_id="ch1", completed_at=LAST_SUNDAY)]
    assert _count(_coord([], comps)) == 0


def test_ignores_another_childs_completions():
    comps = [ChoreCompletion(chore_id="a", child_id="ch2", completed_at=NOW)]
    assert _count(_coord([], comps)) == 0


def test_ignores_another_chores_completions():
    comps = [ChoreCompletion(chore_id="b", child_id="ch1", completed_at=NOW)]
    assert _count(_coord([], comps)) == 0


def test_ignores_bonus_subtask_completions():
    comps = [ChoreCompletion(chore_id="a", child_id="ch1", completed_at=NOW, bonus_subtask_id="bs1")]
    assert _count(_coord([], comps)) == 0


def test_counts_pending_completions_as_well_as_approved():
    comps = [
        ChoreCompletion(chore_id="a", child_id="ch1", completed_at=MONDAY, approved=True),
        ChoreCompletion(chore_id="a", child_id="ch1", completed_at=NOW, approved=False),
    ]
    assert _count(_coord([], comps)) == 2


# ── what the child still owes ────────────────────────────────────────────────


def test_still_due_below_the_target():
    chores = [Chore(name="Cello", id="a", weekly_target=3)]
    comps = [ChoreCompletion(chore_id="a", child_id="ch1", completed_at=MONDAY)]
    assert _due(_coord(chores, comps)) == ["Cello"]


def test_not_due_once_the_target_is_met():
    chores = [Chore(name="Cello", id="a", weekly_target=2)]
    comps = [
        ChoreCompletion(chore_id="a", child_id="ch1", completed_at=MONDAY),
        ChoreCompletion(chore_id="a", child_id="ch1", completed_at=dt.datetime(2026, 4, 21, 9, tzinfo=UTC)),
    ]
    assert _due(_coord(chores, comps)) == []


def test_target_of_zero_leaves_the_chore_uncapped():
    chores = [Chore(name="Dishes", id="a", weekly_target=0, daily_limit=5)]
    comps = [ChoreCompletion(chore_id="a", child_id="ch1", completed_at=MONDAY) for _ in range(9)]
    assert _due(_coord(chores, comps)) == ["Dishes"]


def test_daily_limit_still_applies_under_the_weekly_target():
    """3x a week, but never twice in one day."""
    chores = [Chore(name="Cello", id="a", weekly_target=3, daily_limit=1)]
    comps = [ChoreCompletion(chore_id="a", child_id="ch1", completed_at=NOW)]
    assert _due(_coord(chores, comps)) == []


# ── completing ───────────────────────────────────────────────────────────────


def _complete_coord(chore, completions):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.data = {}
    storage = MagicMock()
    storage.get_chore = MagicMock(return_value=chore)
    storage.get_chores = MagicMock(return_value=[chore])
    storage.get_completions = MagicMock(return_value=completions)
    storage.add_completion = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.get_child = MagicMock(return_value=Child(name="Mia", id="c1"))
    coord.get_chore = MagicMock(return_value=chore)
    coord._is_chore_completable_by_child = MagicMock(return_value=True)
    coord.is_chore_available_for_child = MagicMock(return_value=True)
    coord._compute_active_children = MagicMock(return_value=["c1"])
    coord._is_rotation_done_today = MagicMock(return_value=False)
    coord.effective_chore_points = MagicMock(return_value=10)
    coord._apply_time_adjustment = MagicMock(side_effect=lambda c, b, t: b)
    coord._award_points = AsyncMock(return_value=10)
    coord.async_refresh = AsyncMock()
    coord.badges = None
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    return coord


def test_completing_is_refused_once_the_weekly_target_is_met():
    chore = Chore(name="Cello", id="a", weekly_target=2, daily_limit=5, requires_approval=False)
    comps = [
        ChoreCompletion(chore_id="a", child_id="c1", completed_at=MONDAY),
        ChoreCompletion(chore_id="a", child_id="c1", completed_at=MONDAY),
    ]
    coord = _complete_coord(chore, comps)
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        result = run(coord.async_complete_chore("a", "c1"))
    assert result is None
    coord.storage.add_completion.assert_not_called()


def test_completing_is_allowed_below_the_weekly_target():
    chore = Chore(name="Cello", id="a", weekly_target=3, daily_limit=5, requires_approval=False)
    comps = [ChoreCompletion(chore_id="a", child_id="c1", completed_at=MONDAY)]
    coord = _complete_coord(chore, comps)
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        result = run(coord.async_complete_chore("a", "c1"))
    assert result is not None
    coord.storage.add_completion.assert_called_once()
