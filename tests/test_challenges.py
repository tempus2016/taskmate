"""Tests for daily / weekly challenges."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Challenge, Child, ChoreCompletion

UTC = dt.timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(challenges, child, completions):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    progress: dict = {}
    storage = MagicMock()
    storage.get_challenges = MagicMock(return_value=challenges)
    storage.get_challenge = MagicMock(side_effect=lambda cid: next((c for c in challenges if c.id == cid), None))
    storage.get_completions = MagicMock(return_value=completions)
    storage.get_challenge_child_progress = MagicMock(
        side_effect=lambda cid, kid: progress.get(cid, {}).get(kid, {})
    )
    storage.set_challenge_child_progress = MagicMock(
        side_effect=lambda cid, kid, p: progress.setdefault(cid, {}).__setitem__(kid, p)
    )
    storage.update_child = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._progress = progress
    coord.get_child = MagicMock(return_value=child)
    coord.async_refresh = AsyncMock()
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    coord._maybe_level_up = AsyncMock()
    return coord


def _comp(child_id, when, approved=True, pts=10, bonus=""):
    return ChoreCompletion(chore_id="x", child_id=child_id, completed_at=when,
                           approved=approved, points_awarded=pts, bonus_subtask_id=bonus)


NOW = dt.datetime(2026, 6, 17, 10, tzinfo=UTC)  # a Wednesday


def _patched(fn):
    with patch("homeassistant.util.dt.now", return_value=NOW), \
         patch("homeassistant.util.dt.as_local", side_effect=lambda d: d):
        return fn()


def test_daily_chores_target_awards_bonus():
    ch = Challenge(name="3 today", scope="daily", metric="chores", target=3, bonus_points=15, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    comps = [_comp("kid", NOW), _comp("kid", NOW), _comp("kid", NOW)]
    coord = _coord([ch], child, comps)
    _patched(lambda: run(coord._async_evaluate_challenges("kid")))
    assert child.points == 15
    assert coord._progress["c1"]["kid"]["awarded"] is True
    fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
    assert "taskmate_challenge_completed" in fired


def test_not_awarded_below_target():
    ch = Challenge(name="3 today", scope="daily", metric="chores", target=3, bonus_points=15, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    coord = _coord([ch], child, [_comp("kid", NOW), _comp("kid", NOW)])
    _patched(lambda: run(coord._async_evaluate_challenges("kid")))
    assert child.points == 0
    assert coord._progress["c1"]["kid"]["awarded"] is False


def test_awarded_once_per_period():
    ch = Challenge(name="3 today", scope="daily", metric="chores", target=3, bonus_points=15, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    comps = [_comp("kid", NOW), _comp("kid", NOW), _comp("kid", NOW), _comp("kid", NOW)]
    coord = _coord([ch], child, comps)
    _patched(lambda: run(coord._async_evaluate_challenges("kid")))
    _patched(lambda: run(coord._async_evaluate_challenges("kid")))
    assert child.points == 15  # not doubled


def test_points_metric_weekly():
    ch = Challenge(name="50 this week", scope="weekly", metric="points", target=50, bonus_points=20, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    # Monday of NOW's week is 2026-06-15
    monday = dt.datetime(2026, 6, 15, 9, tzinfo=UTC)
    last_week = dt.datetime(2026, 6, 8, 9, tzinfo=UTC)
    comps = [_comp("kid", monday, pts=30), _comp("kid", NOW, pts=25),
             _comp("kid", last_week, pts=999)]  # last week excluded
    coord = _coord([ch], child, comps)
    _patched(lambda: run(coord._async_evaluate_challenges("kid")))
    assert child.points == 20  # 30+25=55 >= 50


def test_bonus_completions_excluded():
    ch = Challenge(name="3 today", scope="daily", metric="chores", target=3, bonus_points=15, id="c1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    comps = [_comp("kid", NOW), _comp("kid", NOW), _comp("kid", NOW, bonus="sub")]
    coord = _coord([ch], child, comps)
    _patched(lambda: run(coord._async_evaluate_challenges("kid")))
    assert child.points == 0  # only 2 count


def test_assignment_scoping():
    ch = Challenge(name="x", scope="daily", metric="chores", target=1, assigned_to=["other"], id="c1")
    child = Child(name="Mia", id="kid")
    coord = _coord([ch], child, [_comp("kid", NOW)])
    _patched(lambda: run(coord._async_evaluate_challenges("kid")))
    assert "c1" not in coord._progress


def test_create_validates_target():
    coord = _coord([], Child(name="Mia", id="kid"), [])
    coord.storage.add_challenge = MagicMock()
    with pytest.raises(ValueError):
        run(coord.async_create_challenge(name="bad", target=0))
