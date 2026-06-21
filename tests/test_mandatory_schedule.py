"""Tests for mandatory period-end scheduling (#532)."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord():
    c = object.__new__(TaskMateCoordinator)
    c.get_time_periods = MagicMock(return_value=[
        {"id": "morning", "start": "06:00", "end": "12:00"},
        {"id": "afternoon", "start": "12:00", "end": "17:00"},
        {"id": "evening", "start": "17:00", "end": "21:00"},
    ])
    return c


def test_period_end_times():
    c = _coord()
    ends = c._mandatory_period_end_times()
    assert (12, 0, "morning") in ends
    assert (17, 0, "afternoon") in ends
    assert (21, 0, "evening") in ends


def test_anytime_detection_targets_yesterday_and_clears_overrides():
    c = _coord()
    c.mandatory_postpone = {"c1:k1:2026-06-20": "afternoon"}
    c.async_detect_mandatory_misses = AsyncMock(return_value=0)
    now = dt.datetime(2026, 6, 21, 0, 0, 5)
    with patch("homeassistant.util.dt.now", return_value=now):
        run(c.async_detect_anytime_mandatory_misses())
    c.async_detect_mandatory_misses.assert_awaited_once()
    args = c.async_detect_mandatory_misses.await_args.args
    assert args[0] == "anytime"
    assert args[1] == dt.date(2026, 6, 20)
    assert c.mandatory_postpone == {}


def test_catchup_runs_for_passed_periods_only():
    c = _coord()
    c.async_detect_mandatory_misses = AsyncMock(return_value=0)
    now = dt.datetime(2026, 6, 21, 13, 0)  # 13:00 — morning(12:00) passed; afternoon(17:00)/evening(21:00) ahead
    with patch("homeassistant.util.dt.now", return_value=now):
        run(c.async_catchup_mandatory_misses())
    called_periods = [call.args[0] for call in c.async_detect_mandatory_misses.await_args_list]
    assert called_periods == ["morning"]
