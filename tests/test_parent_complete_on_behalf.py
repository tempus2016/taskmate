"""Tests for completing a chore on behalf of a child (as_parent flag)."""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now(year=2024, month=3, day=20, hour=12):
    return dt.datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def _make_system(now=None):
    from tests.conftest import FakeHass, FakeStore

    if now is None:
        now = _now()

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    run(storage.async_load())

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None

    import custom_components.taskmate.coordinator as _mod

    coord._dt_now = now
    coord.async_refresh = AsyncMock()
    # Isolate the completion logic from the notification subsystem.
    coord._async_notify_pending_approval = AsyncMock()

    return coord, storage, _mod


class TestCompleteOnBehalf:
    def test_as_parent_awards_immediately_when_approval_required(self):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Dishes",
                    points=10,
                    requires_approval=True,
                    schedule_mode="specific_days",
                    assigned_to=[child.id],
                )
            )
            run(coord.async_complete_chore(chore.id, child.id, as_parent=True))

        comps = storage.get_completions()
        assert len(comps) == 1
        assert comps[0].approved is True
        assert comps[0].points_awarded == 10
        assert storage.get_child(child.id).points == 10

    def test_as_parent_false_still_creates_pending_when_approval_required(self):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Dishes",
                    points=10,
                    requires_approval=True,
                    schedule_mode="specific_days",
                    assigned_to=[child.id],
                )
            )
            run(coord.async_complete_chore(chore.id, child.id, as_parent=False))

        comps = storage.get_completions()
        assert len(comps) == 1
        assert comps[0].approved is False
        assert comps[0].points_awarded == 0
        assert storage.get_child(child.id).points == 0

    def test_as_parent_respects_daily_limit(self):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Dishes",
                    points=10,
                    requires_approval=True,
                    schedule_mode="specific_days",
                    assigned_to=[child.id],
                )
            )
            run(coord.async_complete_chore(chore.id, child.id, as_parent=True))
            # Daily limit reached is a soft rejection even via as_parent: no-op.
            result = run(coord.async_complete_chore(chore.id, child.id, as_parent=True))
            assert result is None
            assert len(storage.get_completions()) == 1

    def test_as_parent_one_shot_auto_disables_child(self):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Paint fence",
                    points=20,
                    requires_approval=True,
                    schedule_mode="one_shot",
                    assigned_to=[child.id],
                )
            )
            run(coord.async_complete_chore(chore.id, child.id, as_parent=True))

        updated = storage.get_chore(chore.id)
        assert child.id in updated.disabled_for
