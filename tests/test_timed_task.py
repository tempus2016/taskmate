"""Tests for the timed-task lifecycle (TEST-2): start / pause / stop.

coord_timed.py had no direct test. We drive the coordinator methods with a
stubbed storage layer (no real Home Assistant), covering the validation
guards and the running/paused state transitions.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, TimedSession

UTC = timezone.utc
NOW = dt.datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chore=None, child=None, active=None, dated=None):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_chore = MagicMock(return_value=chore)
    storage.get_child = MagicMock(return_value=child)
    storage.get_active_timed_session = MagicMock(return_value=active)
    storage.get_timed_session = MagicMock(return_value=dated)
    storage.save_timed_session = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def _timed_chore(max_daily=0):
    return Chore(name="Practice piano", task_type="timed", timed_max_daily_minutes=max_daily, id="cho1")


def _patch_now():
    return patch("custom_components.taskmate.coord_timed.dt_util.now", return_value=NOW)


# ── start validation ─────────────────────────────────────────────────────────

def test_start_unknown_chore_raises():
    coord = _coord(chore=None)
    with pytest.raises(ValueError):
        run(coord.async_start_timed_task("nope", "ch1"))


def test_start_non_timed_chore_raises():
    coord = _coord(chore=Chore(name="Dishes", task_type="standard", id="cho1"), child=Child(name="A", id="ch1"))
    with pytest.raises(ValueError):
        run(coord.async_start_timed_task("cho1", "ch1"))


def test_start_unknown_child_raises():
    coord = _coord(chore=_timed_chore(), child=None)
    with pytest.raises(ValueError):
        run(coord.async_start_timed_task("cho1", "ch1"))


def test_start_already_running_raises():
    running = TimedSession(chore_id="cho1", child_id="ch1", state="running")
    coord = _coord(chore=_timed_chore(), child=Child(name="A", id="ch1"), active=running)
    with pytest.raises(ValueError):
        run(coord.async_start_timed_task("cho1", "ch1"))


def test_start_fresh_creates_running_session():
    coord = _coord(chore=_timed_chore(), child=Child(name="A", id="ch1"), active=None)
    with _patch_now():
        run(coord.async_start_timed_task("cho1", "ch1"))
    saved = coord.storage.save_timed_session.call_args.args[0]
    assert saved.state == "running"
    assert saved.chore_id == "cho1" and saved.child_id == "ch1"
    assert saved.segments and saved.segments[-1]["end"] is None
    coord.async_refresh.assert_awaited_once()


def test_resume_paused_appends_segment():
    paused = TimedSession(chore_id="cho1", child_id="ch1", state="paused",
                          segments=[{"start": NOW.isoformat(), "end": NOW.isoformat()}],
                          total_seconds_today=60)
    coord = _coord(chore=_timed_chore(), child=Child(name="A", id="ch1"), active=paused)
    with _patch_now():
        run(coord.async_start_timed_task("cho1", "ch1"))
    assert paused.state == "running"
    assert paused.segments[-1]["end"] is None  # a new open segment was appended


def test_resume_blocked_by_daily_cap():
    paused = TimedSession(chore_id="cho1", child_id="ch1", state="paused",
                          segments=[], total_seconds_today=3600)
    coord = _coord(chore=_timed_chore(max_daily=30), child=Child(name="A", id="ch1"), active=paused)
    with pytest.raises(ValueError):
        run(coord.async_start_timed_task("cho1", "ch1"))


# ── pause ────────────────────────────────────────────────────────────────────

def test_pause_without_running_raises():
    coord = _coord(active=None)
    with pytest.raises(ValueError):
        run(coord.async_pause_timed_task("cho1", "ch1"))


def test_pause_running_sets_paused_and_closes_segment():
    start = (NOW - dt.timedelta(minutes=5)).isoformat()
    running = TimedSession(chore_id="cho1", child_id="ch1", state="running",
                           segments=[{"start": start, "end": None}])
    coord = _coord(active=running)
    with _patch_now():
        run(coord.async_pause_timed_task("cho1", "ch1"))
    assert running.state == "paused"
    assert running.segments[-1]["end"] is not None
    assert running.total_seconds_today >= 5 * 60 - 1


# ── stop ─────────────────────────────────────────────────────────────────────

def test_stop_without_active_raises():
    coord = _coord(active=None)
    with pytest.raises(ValueError):
        run(coord.async_stop_timed_task("cho1", "ch1"))
