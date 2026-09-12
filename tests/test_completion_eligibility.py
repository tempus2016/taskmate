"""Server-side completion eligibility must hold for every schedule mode.

The child card filters chores it offers, but a direct service / entity / Dev
Tools call bypasses the card entirely. The coordinator is the authority, so the
same ``assigned_to`` / schedule / availability rules have to be enforced there
for ``specific_days``, ``recurring`` AND ``one_shot`` chores alike.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import BonusSubTask
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now(year=2024, month=3, day=20, hour=12):
    # 2024-03-20 is a Wednesday.
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
    coord._async_notify_pending_approval = AsyncMock()

    return coord, storage, _mod


def _two_children(coord):
    alice = run(coord.async_add_child("Alice"))
    bob = run(coord.async_add_child("Bob"))
    return alice, bob


class TestAssignedToEnforcedForEveryScheduleMode:
    @pytest.mark.parametrize("schedule_mode", ["specific_days", "recurring", "one_shot"])
    def test_unassigned_child_cannot_complete(self, schedule_mode):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            alice, bob = _two_children(coord)
            chore = run(
                coord.async_add_chore(
                    "Mow the lawn",
                    points=50,
                    requires_approval=False,
                    schedule_mode=schedule_mode,
                    recurrence="weekly",
                    assigned_to=[alice.id],
                )
            )
            result = run(coord.async_complete_chore(chore.id, bob.id))

        assert result is None, f"{schedule_mode}: unassigned child completed the chore"
        assert storage.get_completions() == []
        assert storage.get_child(bob.id).points == 0

    @pytest.mark.parametrize("schedule_mode", ["specific_days", "recurring", "one_shot"])
    def test_assigned_child_can_still_complete(self, schedule_mode):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            alice, _bob = _two_children(coord)
            chore = run(
                coord.async_add_chore(
                    "Mow the lawn",
                    points=50,
                    requires_approval=False,
                    schedule_mode=schedule_mode,
                    recurrence="weekly",
                    assigned_to=[alice.id],
                )
            )
            result = run(coord.async_complete_chore(chore.id, alice.id))

        assert result is not None, f"{schedule_mode}: assigned child was wrongly blocked"
        assert storage.get_child(alice.id).points == 50

    @pytest.mark.parametrize("schedule_mode", ["specific_days", "recurring", "one_shot"])
    def test_empty_assigned_to_still_means_everyone(self, schedule_mode):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            _alice, bob = _two_children(coord)
            chore = run(
                coord.async_add_chore(
                    "Family tidy-up",
                    points=5,
                    requires_approval=False,
                    schedule_mode=schedule_mode,
                    recurrence="weekly",
                    assigned_to=[],
                )
            )
            result = run(coord.async_complete_chore(chore.id, bob.id))

        assert result is not None, f"{schedule_mode}: everyone-mode chore blocked the child"
        assert storage.get_child(bob.id).points == 5

    @pytest.mark.parametrize("schedule_mode", ["specific_days", "recurring", "one_shot"])
    def test_parent_may_still_complete_on_behalf(self, schedule_mode):
        """as_parent is the authority and stays exempt from the assignment filter."""
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            alice, bob = _two_children(coord)
            chore = run(
                coord.async_add_chore(
                    "Mow the lawn",
                    points=50,
                    requires_approval=True,
                    schedule_mode=schedule_mode,
                    recurrence="weekly",
                    assigned_to=[alice.id],
                )
            )
            result = run(coord.async_complete_chore(chore.id, bob.id, as_parent=True))

        assert result is not None, f"{schedule_mode}: parent blocked from completing on behalf"
        assert storage.get_child(bob.id).points == 50

    def test_unassigned_child_cannot_disable_a_one_shot_chore(self):
        """The one_shot path appends to disabled_for — that must not be reachable."""
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            alice, bob = _two_children(coord)
            chore = run(
                coord.async_add_chore(
                    "Paint the fence",
                    points=20,
                    requires_approval=False,
                    schedule_mode="one_shot",
                    assigned_to=[alice.id],
                )
            )
            run(coord.async_complete_chore(chore.id, bob.id))

        assert bob.id not in (storage.get_chore(chore.id).disabled_for or [])

    def test_day_filter_still_applies_to_specific_days(self):
        coord, storage, _mod = _make_system()
        now = _now()  # Wednesday
        with patch.object(_mod.dt_util, "now", return_value=now):
            alice, _bob = _two_children(coord)
            chore = run(
                coord.async_add_chore(
                    "Bins out",
                    points=10,
                    requires_approval=False,
                    schedule_mode="specific_days",
                    due_days=["monday"],
                    assigned_to=[alice.id],
                )
            )
            result = run(coord.async_complete_chore(chore.id, alice.id))

        assert result is None
        assert storage.get_child(alice.id).points == 0


class TestBonusSubtaskAssignment:
    def test_unassigned_child_cannot_complete_a_bonus_subtask(self):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            alice, bob = _two_children(coord)
            chore = run(
                coord.async_add_chore(
                    "Tidy room",
                    points=10,
                    requires_approval=False,
                    schedule_mode="specific_days",
                    assigned_to=[alice.id],
                )
            )
            chore.bonus_subtasks = [BonusSubTask(id="b1", name="Hoover too", points=25)]
            storage.update_chore(chore)
            # Parent completes the base chore for Bob, opening the bonus gate.
            run(coord.async_complete_chore(chore.id, bob.id, as_parent=True))

            with pytest.raises(ValueError, match="not assigned"):
                run(coord.async_complete_bonus_subtask(chore.id, "b1", bob.id))

        assert storage.get_child(bob.id).points == 10  # base only, no bonus

    def test_assigned_child_completes_bonus_subtask_normally(self):
        coord, storage, _mod = _make_system()
        now = _now()
        with patch.object(_mod.dt_util, "now", return_value=now):
            alice, _bob = _two_children(coord)
            chore = run(
                coord.async_add_chore(
                    "Tidy room",
                    points=10,
                    requires_approval=False,
                    schedule_mode="specific_days",
                    assigned_to=[alice.id],
                )
            )
            chore.bonus_subtasks = [BonusSubTask(id="b1", name="Hoover too", points=25)]
            storage.update_chore(chore)
            run(coord.async_complete_chore(chore.id, alice.id))
            run(coord.async_complete_bonus_subtask(chore.id, "b1", alice.id))

        assert storage.get_child(alice.id).points == 35
