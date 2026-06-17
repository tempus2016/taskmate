"""Tests that reaching a streak milestone fires the streak_milestone notification."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child

UTC = dt.timezone.utc


def _coord(settings):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": settings.get(k, d))
    storage.get_points_name = MagicMock(return_value="Stars")
    storage.add_points_transaction = MagicMock()
    storage.append_career_score_snapshot = MagicMock()
    storage.update_child = MagicMock()
    coord.storage = storage
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    return coord


def _run_award(coord, child, now_dt):
    import custom_components.taskmate.coordinator as _mod
    with patch.object(_mod.dt_util, "now", return_value=now_dt):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(coord._award_points(child, 10))
        finally:
            loop.close()


SETTINGS = {
    "streak_reset_mode": "reset",
    "weekend_multiplier": "1.0",
    "streak_milestones_enabled": "true",
    "streak_milestones": "3:5, 7:10",
}


def test_milestone_reached_fires_notification():
    coord = _coord(SETTINGS)
    child = Child(name="Mia", current_streak=2, last_completion_date="2024-03-19")
    _run_award(coord, child, dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC))  # streak -> 3
    coord.notifications.fire.assert_awaited_once()
    type_id, ctx = coord.notifications.fire.await_args[0]
    assert type_id == "streak_milestone"
    assert ctx["days"] == 3
    assert ctx["points"] == 5
    assert ctx["child_name"] == "Mia"


def test_no_milestone_no_notification():
    coord = _coord(SETTINGS)
    child = Child(name="Mia", current_streak=0, last_completion_date="2024-03-19")
    _run_award(coord, child, dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC))  # streak -> 1, no milestone
    coord.notifications.fire.assert_not_awaited()


def test_milestones_disabled_no_notification():
    coord = _coord({**SETTINGS, "streak_milestones_enabled": "false"})
    child = Child(name="Mia", current_streak=2, last_completion_date="2024-03-19")
    _run_award(coord, child, dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC))
    coord.notifications.fire.assert_not_awaited()
