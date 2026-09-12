"""Tests for mandatory-miss detection (#532)."""

from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chores, children, completions):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_chores = MagicMock(return_value=chores)
    s.get_children = MagicMock(return_value=children)
    s.get_completions = MagicMock(return_value=completions)
    s.get_mandatory_misses = MagicMock(return_value=[])
    s._added = []
    s.add_mandatory_miss = MagicMock(side_effect=lambda m: s._added.append(m))
    s.async_save = AsyncMock()
    c.storage = s
    c.hass = MagicMock()
    c.hass.bus.async_fire = MagicMock()
    c.async_refresh = AsyncMock()
    c.mandatory_postpone = {}
    c._is_chore_scheduled_for_date = MagicMock(return_value=True)
    return c


DAY = dt.date(2026, 6, 21)


def test_miss_created_for_incomplete_mandatory():
    chore = Chore(
        name="Homework",
        mandatory=True,
        mandatory_penalty_points=5,
        time_category="afternoon",
        assigned_to=["k1"],
        id="c1",
    )
    coord = _coord([chore], [Child(name="Kid", id="k1")], [])
    n = run(coord.async_detect_mandatory_misses("afternoon", DAY))
    assert n == 1
    assert coord.storage._added[0].chore_id == "c1"
    assert coord.storage._added[0].child_id == "k1"
    assert coord.storage._added[0].penalty_points == 5


def test_no_miss_when_completed_today():
    chore = Chore(name="Homework", mandatory=True, time_category="afternoon", assigned_to=["k1"], id="c1")
    comp = ChoreCompletion(chore_id="c1", child_id="k1", completed_at=dt.datetime(2026, 6, 21, 13, 0))
    coord = _coord([chore], [Child(name="Kid", id="k1")], [comp])
    assert run(coord.async_detect_mandatory_misses("afternoon", DAY)) == 0


def test_no_miss_for_non_mandatory():
    chore = Chore(name="Extra", mandatory=False, time_category="afternoon", assigned_to=["k1"], id="c1")
    coord = _coord([chore], [Child(name="Kid", id="k1")], [])
    assert run(coord.async_detect_mandatory_misses("afternoon", DAY)) == 0


def test_wrong_period_skipped():
    chore = Chore(name="Homework", mandatory=True, time_category="morning", assigned_to=["k1"], id="c1")
    coord = _coord([chore], [Child(name="Kid", id="k1")], [])
    assert run(coord.async_detect_mandatory_misses("afternoon", DAY)) == 0


def test_per_child_and_idempotent():
    chore = Chore(name="Homework", mandatory=True, time_category="afternoon", assigned_to=["k1", "k2"], id="c1")
    coord = _coord([chore], [Child(name="A", id="k1"), Child(name="B", id="k2")], [])
    assert run(coord.async_detect_mandatory_misses("afternoon", DAY)) == 2
    existing = list(coord.storage._added)
    coord.storage.get_mandatory_misses = MagicMock(return_value=existing)
    assert run(coord.async_detect_mandatory_misses("afternoon", DAY)) == 0


def test_disabled_for_child_skipped():
    chore = Chore(
        name="Homework", mandatory=True, time_category="afternoon", assigned_to=["k1"], disabled_for=["k1"], id="c1"
    )
    coord = _coord([chore], [Child(name="Kid", id="k1")], [])
    assert run(coord.async_detect_mandatory_misses("afternoon", DAY)) == 0


# ---------------------------------------------------------------------------
# rejection re-opens the miss question (#detection only ran at period end)
# ---------------------------------------------------------------------------


def _recheck_coord(chore, completions, now):
    coord = _coord([chore], [Child(name="Kid", id="k1")], completions)
    coord.get_chore = MagicMock(return_value=chore)
    coord.get_time_periods = MagicMock(
        return_value=[
            {"id": "morning", "start": "06:00", "end": "12:00"},
            {"id": "afternoon", "start": "12:00", "end": "18:00"},
            {"id": "evening", "start": "18:00", "end": "21:00"},
        ]
    )
    coord._dt_now = now
    return coord


def _mandatory_chore(category="evening"):
    return Chore(
        name="Bins out",
        mandatory=True,
        mandatory_penalty_points=20,
        time_category=category,
        assigned_to=["k1"],
        id="c1",
    )


def test_recheck_creates_the_miss_once_the_period_has_closed():
    """Submit before the deadline, get rejected after it: the miss is now owed."""
    import custom_components.taskmate.coord_mandatory as _mod
    from unittest.mock import patch

    chore = _mandatory_chore("evening")
    now = dt.datetime(2026, 6, 21, 21, 30, tzinfo=dt.timezone.utc)
    coord = _recheck_coord(chore, [], now)

    with patch.object(_mod.dt_util, "now", return_value=now):
        created = run(coord.async_recheck_mandatory_miss("c1", "k1", DAY))

    assert created == 1
    assert coord.storage._added[0].chore_id == "c1"
    assert coord.storage._added[0].penalty_points == 20


def test_recheck_is_a_no_op_while_the_period_is_still_open():
    """Rejecting early in the period must not penalise a child who can still act."""
    import custom_components.taskmate.coord_mandatory as _mod
    from unittest.mock import patch

    chore = _mandatory_chore("evening")
    now = dt.datetime(2026, 6, 21, 19, 0, tzinfo=dt.timezone.utc)
    coord = _recheck_coord(chore, [], now)

    with patch.object(_mod.dt_util, "now", return_value=now):
        assert run(coord.async_recheck_mandatory_miss("c1", "k1", DAY)) == 0
    assert coord.storage._added == []


def test_recheck_ignores_non_mandatory_chores():
    import custom_components.taskmate.coord_mandatory as _mod
    from unittest.mock import patch

    chore = Chore(name="Extra", mandatory=False, time_category="evening", assigned_to=["k1"], id="c1")
    now = dt.datetime(2026, 6, 21, 23, 0, tzinfo=dt.timezone.utc)
    coord = _recheck_coord(chore, [], now)

    with patch.object(_mod.dt_util, "now", return_value=now):
        assert run(coord.async_recheck_mandatory_miss("c1", "k1", DAY)) == 0


def test_recheck_does_not_double_up_an_existing_miss():
    import custom_components.taskmate.coord_mandatory as _mod
    from custom_components.taskmate.models import MandatoryMiss
    from unittest.mock import patch

    chore = _mandatory_chore("evening")
    now = dt.datetime(2026, 6, 21, 22, 0, tzinfo=dt.timezone.utc)
    coord = _recheck_coord(chore, [], now)
    coord.storage.get_mandatory_misses = MagicMock(
        return_value=[MandatoryMiss(chore_id="c1", child_id="k1", due_date=DAY.isoformat(), period_id="evening")]
    )

    with patch.object(_mod.dt_util, "now", return_value=now):
        assert run(coord.async_recheck_mandatory_miss("c1", "k1", DAY)) == 0


def test_recheck_on_a_past_day_always_counts_as_closed():
    import custom_components.taskmate.coord_mandatory as _mod
    from unittest.mock import patch

    chore = _mandatory_chore("evening")
    now = dt.datetime(2026, 6, 23, 9, 0, tzinfo=dt.timezone.utc)
    coord = _recheck_coord(chore, [], now)

    with patch.object(_mod.dt_util, "now", return_value=now):
        assert run(coord.async_recheck_mandatory_miss("c1", "k1", DAY)) == 1
