"""Tests for mandatory-miss resolution actions (#532)."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import MandatoryMiss


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


PERIODS = [
    {"id": "morning", "start": "06:00", "end": "12:00"},
    {"id": "afternoon", "start": "12:00", "end": "17:00"},
    {"id": "evening", "start": "17:00", "end": "21:00"},
]


def _coord(miss):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_mandatory_misses = MagicMock(return_value=[miss])
    s.remove_mandatory_miss = MagicMock()
    s.get_chores = MagicMock(return_value=[MagicMock(id="c1", name="Homework")])
    s.async_save = AsyncMock()
    c.storage = s
    c.hass = MagicMock()
    c.hass.bus.async_fire = MagicMock()
    c.async_refresh = AsyncMock()
    c.async_remove_points = AsyncMock()
    c.mandatory_postpone = {}
    c.get_time_periods = MagicMock(return_value=PERIODS)
    return c


def _miss(period="morning", penalty=5):
    return MandatoryMiss(chore_id="c1", child_id="k1", due_date="2026-06-21",
                         period_id=period, penalty_points=penalty, id="m1")


def test_apply_penalty_deducts_and_removes():
    coord = _coord(_miss())
    run(coord.async_apply_mandatory_penalty("m1"))
    coord.async_remove_points.assert_awaited_once()
    args = coord.async_remove_points.await_args
    assert args.args[0] == "k1" and args.args[1] == 5
    assert args.kwargs["reason"].startswith("Penalty: ")
    coord.storage.remove_mandatory_miss.assert_called_once_with("m1")


def test_apply_penalty_zero_is_noop_deduction():
    coord = _coord(_miss(penalty=0))
    run(coord.async_apply_mandatory_penalty("m1"))
    coord.async_remove_points.assert_not_awaited()
    coord.storage.remove_mandatory_miss.assert_called_once_with("m1")


def test_postpone_sets_next_period_override():
    coord = _coord(_miss(period="morning"))
    now = dt.datetime(2026, 6, 21, 12, 0)  # afternoon still ahead
    with patch("homeassistant.util.dt.now", return_value=now):
        run(coord.async_postpone_mandatory_chore("m1"))
    assert coord.mandatory_postpone["c1:k1:2026-06-21"] == "afternoon"
    coord.storage.remove_mandatory_miss.assert_called_once_with("m1")


def test_postpone_after_last_period_rolls_tomorrow():
    coord = _coord(_miss(period="evening"))
    now = dt.datetime(2026, 6, 21, 21, 0)  # nothing later today
    with patch("homeassistant.util.dt.now", return_value=now):
        run(coord.async_postpone_mandatory_chore("m1"))
    assert "c1:k1:2026-06-21" not in coord.mandatory_postpone
    coord.storage.remove_mandatory_miss.assert_called_once_with("m1")


def test_dismiss_removes_no_points():
    coord = _coord(_miss())
    run(coord.async_dismiss_mandatory_chore("m1"))
    coord.async_remove_points.assert_not_awaited()
    coord.storage.remove_mandatory_miss.assert_called_once_with("m1")
