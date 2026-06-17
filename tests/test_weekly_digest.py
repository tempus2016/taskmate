"""Tests for the weekly digest."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, ChoreCompletion

UTC = dt.timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(children, completions):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_children = MagicMock(return_value=children)
    storage.get_completions = MagicMock(return_value=completions)
    storage.get_points_name = MagicMock(return_value="Stars")
    coord.storage = storage
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    return coord


def _comp(child, when, approved=True, pts=10, bonus=""):
    return ChoreCompletion(chore_id="x", child_id=child, completed_at=when,
                           approved=approved, points_awarded=pts, bonus_subtask_id=bonus)


def test_digest_counts_this_week_only():
    # week of Mon 2026-06-15..Sun 21
    this_week = dt.datetime(2026, 6, 17, 9, tzinfo=UTC)
    last_week = dt.datetime(2026, 6, 8, 9, tzinfo=UTC)
    coord = _coord(
        [Child(name="Mia", id="a"), Child(name="Bo", id="b")],
        [_comp("a", this_week, pts=10), _comp("a", this_week, pts=5),
         _comp("a", last_week, pts=99), _comp("b", this_week, pts=7)],
    )
    with patch("homeassistant.util.dt.now", return_value=dt.datetime(2026, 6, 21, 18, tzinfo=UTC)), \
         patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        s = coord._build_weekly_digest()
    assert "Mia: 2 chores, 15 Stars" in s
    assert "Bo: 1 chores, 7 Stars" in s
    assert "99" not in s  # last week excluded


def test_digest_excludes_pending_and_bonus():
    now = dt.datetime(2026, 6, 17, 9, tzinfo=UTC)
    coord = _coord([Child(name="Mia", id="a")],
                   [_comp("a", now, approved=False, pts=10), _comp("a", now, bonus="sub", pts=5),
                    _comp("a", now, pts=8)])
    with patch("homeassistant.util.dt.now", return_value=dt.datetime(2026, 6, 21, 18, tzinfo=UTC)), \
         patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        s = coord._build_weekly_digest()
    assert "Mia: 1 chores, 8 Stars" in s


def test_no_children_empty():
    coord = _coord([], [])
    with patch("homeassistant.util.dt.now", return_value=dt.datetime(2026, 6, 21, 18, tzinfo=UTC)):
        assert coord._build_weekly_digest() == ""


def test_check_only_fires_on_sunday():
    coord = _coord([Child(name="A", id="a")], [])
    coord._async_send_weekly_digest = AsyncMock()
    coord.hass = MagicMock()
    # Wednesday -> no task created
    coord._async_weekly_digest_check(dt.datetime(2026, 6, 17, 18))
    coord.hass.async_create_task.assert_not_called()
    # Sunday -> task created
    coord._async_weekly_digest_check(dt.datetime(2026, 6, 21, 18))
    coord.hass.async_create_task.assert_called_once()
