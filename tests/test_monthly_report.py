"""Tests for the monthly report (FEAT-14)."""
from __future__ import annotations

import datetime as dt
from datetime import date, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, ChoreCompletion

UTC = timezone.utc


def _coord(children, completions):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_children = MagicMock(return_value=children)
    s.get_completions = MagicMock(return_value=completions)
    s.get_points_name = MagicMock(return_value="Stars")
    c.storage = s
    return c


def _comp(child_id, when, approved=True, points=10, bonus=""):
    return ChoreCompletion(chore_id="x", child_id=child_id, completed_at=when,
                           approved=approved, points_awarded=points, bonus_subtask_id=bonus)


def test_monthly_report_counts_only_in_range_and_approved():
    kid = Child(name="Alex", id="k1", level=4, best_streak=9)
    comps = [
        _comp("k1", dt.datetime(2026, 4, 5, 9, 0, tzinfo=UTC)),    # in range
        _comp("k1", dt.datetime(2026, 4, 20, 9, 0, tzinfo=UTC)),   # in range
        _comp("k1", dt.datetime(2026, 3, 31, 9, 0, tzinfo=UTC)),   # before
        _comp("k1", dt.datetime(2026, 5, 1, 9, 0, tzinfo=UTC)),    # after
        _comp("k1", dt.datetime(2026, 4, 10, 9, 0, tzinfo=UTC), approved=False),  # pending
        _comp("k1", dt.datetime(2026, 4, 11, 9, 0, tzinfo=UTC), bonus="b1"),      # bonus
    ]
    c = _coord([kid], comps)
    out = c._build_monthly_report(date(2026, 4, 1), date(2026, 4, 30))
    assert out == "• Alex: 2 chores, 20 Stars, level 4, best streak 9"


def test_monthly_report_empty_without_children():
    c = _coord([], [])
    assert c._build_monthly_report(date(2026, 4, 1), date(2026, 4, 30)) == ""


@pytest.mark.asyncio
async def test_send_monthly_report_targets_previous_month(monkeypatch):
    from tests.conftest import dt_util_mock
    kid = Child(name="Alex", id="k1")
    comp = _comp("k1", dt.datetime(2026, 4, 15, 9, 0, tzinfo=UTC))
    c = _coord([kid], [comp])
    c.notifications = MagicMock()
    c.notifications.fire = AsyncMock()
    # "Today" is 1 May 2026 -> report covers April 2026.
    monkeypatch.setattr(dt_util_mock, "_now", dt.datetime(2026, 5, 1, 18, 0, tzinfo=UTC))
    await c._async_send_monthly_report()
    c.notifications.fire.assert_awaited_once()
    args = c.notifications.fire.await_args[0]
    assert args[0] == "monthly_report"
    assert args[1]["month"] == "April 2026"
    assert "Alex: 1 chores" in args[1]["summary"]


def test_evening_callback_fires_monthly_on_first():
    c = object.__new__(TaskMateCoordinator)
    c.hass = MagicMock()
    created = []
    c.hass.async_create_task = lambda coro: (created.append(coro), coro.close())
    # 1st of month, not Sunday -> monthly report + season finalize (FEAT-2).
    c._async_weekly_digest_check(dt.datetime(2026, 4, 1, 18, 0, tzinfo=UTC))
    assert len(created) == 2
