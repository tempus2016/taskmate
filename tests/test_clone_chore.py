"""Tests for cloning / duplicating a chore."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import BonusSubTask, Chore

UTC = dt.timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(source):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    added = []
    storage = MagicMock()
    storage.add_chore = MagicMock(side_effect=lambda c: added.append(c))
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._added = added
    coord.get_chore = MagicMock(return_value=source)
    coord._compute_active_children = MagicMock(return_value=[])
    coord._publish_chore_to_calendars = AsyncMock()
    coord.async_refresh = AsyncMock()
    return coord


def _source():
    return Chore(
        name="Tidy room",
        points=15,
        difficulty="hard",
        assigned_to=["c1", "c2"],
        time_category="evening",
        daily_limit=2,
        schedule_mode="recurring",
        recurrence="weekly",
        assignment_mode="alternating",
        assignment_current_child_id="c1",
        skip_date="2024-01-01",
        skip_count=3,
        disabled_for=["c2"],
        enabled=False,
        publish_calendar_published_dates=["2024-01-01"],
        bonus_subtasks=[BonusSubTask(name="Make bed", points=5)],
        id="src1",
    )


def test_clone_copies_config_with_new_identity():
    src = _source()
    coord = _coord(src)
    clone = run(coord.async_clone_chore("src1"))
    assert clone.id != "src1"
    assert clone.name == "Tidy room (copy)"
    # config copied
    assert clone.points == 15
    assert clone.difficulty == "hard"
    assert clone.assigned_to == ["c1", "c2"]
    assert clone.time_category == "evening"
    assert clone.daily_limit == 2
    assert clone.assignment_mode == "alternating"
    coord.storage.add_chore.assert_called_once()


def test_clone_resets_runtime_state():
    coord = _coord(_source())
    clone = run(coord.async_clone_chore("src1"))
    assert clone.enabled is True
    assert clone.disabled_for == []
    assert clone.skip_date == ""
    assert clone.skip_count == 0
    assert clone.assignment_current_child_id == ""
    assert clone.publish_calendar_published_dates == []


def test_clone_gives_subtasks_new_ids():
    src = _source()
    coord = _coord(src)
    clone = run(coord.async_clone_chore("src1"))
    assert len(clone.bonus_subtasks) == 1
    assert clone.bonus_subtasks[0].name == "Make bed"
    assert clone.bonus_subtasks[0].id != src.bonus_subtasks[0].id


def test_clone_does_not_mutate_source():
    src = _source()
    coord = _coord(src)
    run(coord.async_clone_chore("src1"))
    assert src.name == "Tidy room"
    assert src.enabled is False
    assert src.id == "src1"


def test_clone_missing_chore_raises():
    coord = _coord(None)
    coord.get_chore = MagicMock(return_value=None)
    try:
        run(coord.async_clone_chore("nope"))
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "not found" in str(e)


def test_clone_one_shot_gets_today_created_date():
    src = _source()
    src.schedule_mode = "one_shot"
    src.created_date = "2020-01-01"
    coord = _coord(src)
    clone = run(coord.async_clone_chore("src1"))
    assert clone.created_date != "2020-01-01"
