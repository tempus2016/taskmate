"""first_come shares its daily_limit across the pool (#1159).

A first_come chore with daily_limit N is open to the whole pool until it has
been done N times today in total, whoever did it — the same child may do it
more than once. Each completion pays the child who made it. Once the shared
limit is filled it closes for everyone. A limit of 1 is the classic
single-winner race, and existing first_come chores are reset to 1 on upgrade
so a limit the old editor hid doesn't quietly start applying.
"""

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


def _now():
    return dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)


def _make_system(initial=None):
    from tests.conftest import FakeHass, FakeStore

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._store._data = initial
    storage._data = {}
    run(storage.async_load())

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None
    coord.async_refresh = AsyncMock()

    import custom_components.taskmate.coordinator as _mod

    return coord, storage, _mod


def _dishwasher(coord, _mod, now, daily_limit=2):
    with patch.object(_mod.dt_util, "now", return_value=now):
        a = run(coord.async_add_child("Ava"))
        b = run(coord.async_add_child("Ben"))
        chore = run(
            coord.async_add_chore(
                "Empty the dishwasher",
                points=3,
                requires_approval=False,
                assignment_mode="first_come",
                assigned_to=[a.id, b.id],
                daily_limit=daily_limit,
            )
        )
    return chore, a, b


def _complete(coord, _mod, now, chore, child_id, **kw):
    with patch.object(_mod.dt_util, "now", return_value=now):
        return run(coord.async_complete_chore(chore.id, child_id, **kw))


def _done_by(storage, chore):
    return [c.child_id for c in storage.get_completions() if c.chore_id == chore.id and not c.bonus_subtask_id]


def _points(storage, child_id):
    return storage.get_child(child_id).points


class TestSharedLimit:
    def test_same_child_twice_then_closed_for_everyone(self):
        """Scenario 1: Ava does it twice, gets 6; Ben is then refused."""
        coord, storage, _mod = _make_system()
        now = _now()
        chore, a, b = _dishwasher(coord, _mod, now)

        _complete(coord, _mod, now, chore, a.id)
        with patch.object(_mod.dt_util, "now", return_value=now):
            assert coord._is_rotation_done_today(chore) is False
        _complete(coord, _mod, now, chore, a.id)
        assert _complete(coord, _mod, now, chore, b.id) is None

        assert _done_by(storage, chore) == [a.id, a.id]
        assert _points(storage, a.id) == 6
        assert _points(storage, b.id) == 0

    def test_one_each(self):
        """Scenario 2: one each, 3 points each, then closed."""
        coord, storage, _mod = _make_system()
        now = _now()
        chore, a, b = _dishwasher(coord, _mod, now)

        _complete(coord, _mod, now, chore, a.id)
        _complete(coord, _mod, now, chore, b.id)
        assert _complete(coord, _mod, now, chore, a.id) is None
        assert _complete(coord, _mod, now, chore, b.id) is None

        assert sorted(_done_by(storage, chore)) == sorted([a.id, b.id])
        assert _points(storage, a.id) == 3
        assert _points(storage, b.id) == 3

    def test_closes_for_whole_pool_once_filled(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, a, b = _dishwasher(coord, _mod, now)

        _complete(coord, _mod, now, chore, b.id)
        _complete(coord, _mod, now, chore, b.id)
        with patch.object(_mod.dt_util, "now", return_value=now):
            assert coord._is_rotation_done_today(chore) is True
            assert coord.is_chore_available_for_child(chore, a.id) is False
            assert coord.is_chore_available_for_child(chore, b.id) is False
        assert _points(storage, b.id) == 6

    def test_limit_one_is_still_a_single_winner_race(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, a, b = _dishwasher(coord, _mod, now, daily_limit=1)

        _complete(coord, _mod, now, chore, a.id)
        assert _complete(coord, _mod, now, chore, b.id) is None
        assert _complete(coord, _mod, now, chore, a.id) is None
        assert _done_by(storage, chore) == [a.id]

    def test_pool_wide_parent_completion_uses_a_slot(self):
        coord, storage, _mod = _make_system()
        now = _now()
        chore, a, b = _dishwasher(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))
        _complete(coord, _mod, now, chore, a.id)
        assert _complete(coord, _mod, now, chore, b.id) is None
        assert _points(storage, a.id) == 3


class TestUpgradeReset:
    def _initial(self):
        return {
            "children": [],
            "chores": [
                {"id": "fc", "name": "Race", "assignment_mode": "first_come", "daily_limit": 3},
                {"id": "fc1", "name": "Race one", "assignment_mode": "first_come", "daily_limit": 1},
                {"id": "ev", "name": "Everyone", "assignment_mode": "everyone", "daily_limit": 3},
            ],
        }

    def test_stale_first_come_limit_is_reset_once(self):
        _coord, storage, _mod = _make_system(self._initial())
        limits = {c.id: c.daily_limit for c in storage.get_chores()}
        assert limits == {"fc": 1, "fc1": 1, "ev": 3}
        assert storage._data["_first_come_limit_reset"] is True

    def test_limit_set_after_upgrade_is_kept(self):
        _coord, storage, _mod = _make_system(self._initial())
        storage._data["chores"][0]["daily_limit"] = 2
        run(storage.async_load())
        assert {c.id: c.daily_limit for c in storage.get_chores()}["fc"] == 2
