"""Tests for the levels / XP system."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(step="100"):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": {"level_xp_step": step}.get(k, d))
    coord.storage = storage
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    return coord


def test_level_for_xp_curve():
    coord = _coord("100")
    assert coord.level_for_xp(0) == 1
    assert coord.level_for_xp(99) == 1
    assert coord.level_for_xp(100) == 2
    assert coord.level_for_xp(250) == 3


def test_level_info():
    coord = _coord("100")
    info = coord.level_info(Child(name="A", total_points_earned=250))
    assert info == {"level": 3, "progress": 50, "target": 100}


def test_custom_step():
    coord = _coord("50")
    assert coord.level_for_xp(120) == 3  # 120 // 50 + 1


def test_level_up_fires_event_and_notification():
    coord = _coord("100")
    child = Child(name="Mia", total_points_earned=205, level=1)
    run(coord._maybe_level_up(child))
    assert child.level == 3
    # event fired for each level crossed (2 and 3)
    levels = [c[0][1]["level"] for c in coord.hass.bus.async_fire.call_args_list if c[0][0] == "taskmate_level_up"]
    assert levels == [2, 3]
    assert coord.notifications.fire.await_count == 2


def test_no_levelup_when_unchanged():
    coord = _coord("100")
    child = Child(name="Mia", total_points_earned=150, level=2)
    run(coord._maybe_level_up(child))
    assert child.level == 2
    coord.notifications.fire.assert_not_awaited()


def test_level_resyncs_down_quietly_on_drop():
    coord = _coord("100")
    child = Child(name="Mia", total_points_earned=50, level=3)  # earned dropped (e.g. undo)
    run(coord._maybe_level_up(child))
    assert child.level == 1
    coord.notifications.fire.assert_not_awaited()


def test_level_round_trips_serialization():
    assert Child.from_dict(Child(name="A", level=4).to_dict()).level == 4
