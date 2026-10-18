"""Tests for parent_complete_chore coordinator method."""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, patch

import pytest

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

    return coord, storage, _mod


class TestParentCompleteChore:
    def test_parent_complete_creates_completion_with_zero_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Vacuum",
                    points=10,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[child.id],
                )
            )

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        completions = storage.get_completions()
        assert len(completions) == 1
        assert completions[0].child_id == "__parent__"
        assert completions[0].points_awarded == 0
        assert completions[0].approved is True

    def test_parent_complete_updates_last_completed_for_all_children(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(
                coord.async_add_chore(
                    "Dishes",
                    points=5,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[alice.id, bob.id],
                )
            )

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        alice_lc = storage.get_last_completed(chore.id, alice.id)
        bob_lc = storage.get_last_completed(chore.id, bob.id)
        assert alice_lc.get("current") == now.isoformat()
        assert bob_lc.get("current") == now.isoformat()

    def test_parent_complete_rejects_one_shot_chore(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Special task",
                    points=10,
                    requires_approval=False,
                    schedule_mode="one_shot",
                    assigned_to=[child.id],
                )
            )

        with patch.object(_mod.dt_util, "now", return_value=now):
            with pytest.raises(ValueError, match="one.shot"):
                run(coord.async_parent_complete_chore(chore.id))

    def test_parent_complete_rejects_nonexistent_chore(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            with pytest.raises(ValueError, match="not found"):
                run(coord.async_parent_complete_chore("fake_id"))

    def test_parent_complete_rejects_disabled_chore(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Mop",
                    points=5,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[child.id],
                )
            )
            chore.enabled = False
            storage.update_chore(chore)

        with patch.object(_mod.dt_util, "now", return_value=now):
            with pytest.raises(ValueError, match="disabled"):
                run(coord.async_parent_complete_chore(chore.id))

    def test_parent_complete_does_not_award_points(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Sweep",
                    points=15,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[child.id],
                )
            )

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        updated_child = storage.get_child(child.id)
        assert updated_child.points == 0
        assert updated_child.current_streak == 0

    def test_parent_complete_suppresses_availability_for_children(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Laundry",
                    points=5,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[child.id],
                )
            )

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        with patch.object(_mod.dt_util, "now", return_value=now):
            available = coord.is_chore_available_for_child(chore, child.id)
        assert available is False

    def test_parent_complete_everyone_mode_updates_all_children(self):
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(
                coord.async_add_chore(
                    "Tidy",
                    points=5,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[],  # empty = everyone
                )
            )

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        alice_lc = storage.get_last_completed(chore.id, alice.id)
        bob_lc = storage.get_last_completed(chore.id, bob.id)
        assert alice_lc.get("current") == now.isoformat()
        assert bob_lc.get("current") == now.isoformat()


class TestParentCompleteIntegration:
    """Full lifecycle: parent completes → chore becomes unavailable → next cycle it returns."""

    def test_chore_returns_after_recurrence_window(self):
        coord, storage, _mod = _make_system()
        now = _now(2024, 3, 20)  # Wednesday

        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Weekly clean",
                    points=10,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[child.id],
                )
            )

        # Parent completes it
        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        # Same day: not available
        with patch.object(_mod.dt_util, "now", return_value=now):
            assert coord.is_chore_available_for_child(chore, child.id) is False

        # 6 days later: still not available
        six_days = _now(2024, 3, 26)
        with patch.object(_mod.dt_util, "now", return_value=six_days):
            assert coord.is_chore_available_for_child(chore, child.id) is False

        # 7 days later: available again
        seven_days = _now(2024, 3, 27)
        with patch.object(_mod.dt_util, "now", return_value=seven_days):
            assert coord.is_chore_available_for_child(chore, child.id) is True

    def test_parent_complete_clears_rotation_pointer_today(self):
        """For rotation-mode chores, parent_complete should clear today's
        cached current assignee so the chore stops pointing at the original
        child. The next midnight refresh recomputes the pointer normally.
        """
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(
                coord.async_add_chore(
                    "Alternating chore",
                    points=5,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[alice.id, bob.id],
                    assignment_mode="alternating",
                )
            )
            chore.assignment_current_child_id = alice.id
            storage.update_chore(chore)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        updated_chore = storage.get_chore(chore.id)
        assert updated_chore.assignment_current_child_id == ""

    def test_parent_complete_preserves_everyone_mode_pointer(self):
        """Everyone-mode chores don't use the assignment_current_child_id
        cache. Make sure parent_complete leaves it untouched (still empty)
        and doesn't error.
        """
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Brush teeth",
                    points=2,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="daily",
                    assigned_to=[],  # everyone
                )
            )

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))

        updated_chore = storage.get_chore(chore.id)
        assert updated_chore.assignment_current_child_id == ""

    def test_parent_complete_counts_toward_rotation_done_today(self):
        """A `__parent__` completion fills today's quota for the rotation
        pool, so `_is_rotation_done_today` returns True afterwards.
        """
        coord, storage, _mod = _make_system()
        now = _now()

        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(
                coord.async_add_chore(
                    "Bins",
                    points=5,
                    requires_approval=False,
                    schedule_mode="recurring",
                    recurrence="weekly",
                    assigned_to=[alice.id, bob.id],
                    assignment_mode="alternating",
                )
            )

        with patch.object(_mod.dt_util, "now", return_value=now):
            assert coord._is_rotation_done_today(chore) is False
            run(coord.async_parent_complete_chore(chore.id))
            # Re-fetch since parent_complete may have mutated the chore.
            chore = storage.get_chore(chore.id)
            assert coord._is_rotation_done_today(chore) is True


class TestParentCompleteClosesChoreForChildren:
    """A parent completion closes the day for the pool on the service path too (#1082).

    The child card already treats a `__parent__` completion as the child's own
    for every mode except first_come; the backend has to agree, or an
    automation, NFC tag or `complete_next_chore` still credits the child.
    """

    def _weekday_chore(self, coord, _mod, now, daily_limit=1):
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        with patch.object(_mod.dt_util, "now", return_value=now):
            child = run(coord.async_add_child("Alice"))
            chore = run(
                coord.async_add_chore(
                    "Feed the cat",
                    points=5,
                    requires_approval=False,
                    schedule_mode="specific_days",
                    due_days=days,
                    daily_limit=daily_limit,
                    assigned_to=[child.id],
                )
            )
        return child, chore

    def test_child_cannot_complete_after_parent_complete(self):
        coord, storage, _mod = _make_system()
        now = _now()
        child, chore = self._weekday_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))
            result = run(coord.async_complete_chore(chore.id, child.id))

        assert result is None
        assert [c.child_id for c in storage.get_completions()] == ["__parent__"]
        assert storage.get_child(child.id).points == 0

    def test_parent_complete_counts_as_one_toward_a_higher_daily_limit(self):
        """Card parity: the card counts the parent completion as one of the
        child's, so with a limit of 2 one more completion is still allowed."""
        coord, storage, _mod = _make_system()
        now = _now()
        child, chore = self._weekday_chore(coord, _mod, now, daily_limit=2)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))
            assert run(coord.async_complete_chore(chore.id, child.id)) is not None
            assert run(coord.async_complete_chore(chore.id, child.id)) is None

    def test_parent_completed_chore_is_not_due_for_child(self):
        coord, storage, _mod = _make_system()
        now = _now()
        child, chore = self._weekday_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            assert [c.id for c in coord.get_due_chores_for_child(child.id)] == [chore.id]
            run(coord.async_parent_complete_chore(chore.id))
            assert coord.get_due_chores_for_child(child.id) == []

    def test_today_board_shows_parent_completed_chore_as_done(self):
        coord, storage, _mod = _make_system()
        now = _now()
        child, chore = self._weekday_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id))
            board = coord.get_today_board()

        items = board["children"][0]["chores"]
        assert items == [{"chore_id": chore.id, "status": "done", "count": 1, "limit": 1}]


class TestParentCompleteForOneChild:
    """ "Parent did it" for one child of a shared chore (#1096)."""

    def _shared_chore(self, coord, _mod, now, **kwargs):
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        opts = {"schedule_mode": "specific_days", "due_days": days}
        opts.update(kwargs)
        with patch.object(_mod.dt_util, "now", return_value=now):
            alice = run(coord.async_add_child("Alice"))
            bob = run(coord.async_add_child("Bob"))
            chore = run(
                coord.async_add_chore(
                    "Tidy room", points=5, requires_approval=False, assigned_to=[alice.id, bob.id], **opts
                )
            )
        return alice, bob, chore

    def test_records_a_parent_completion_for_that_child(self):
        coord, storage, _mod = _make_system()
        now = _now()
        alice, bob, chore = self._shared_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id, alice.id))

        [comp] = storage.get_completions()
        assert comp.child_id == "__parent__"
        assert comp.for_child_id == alice.id
        assert comp.points_awarded == 0
        assert storage.get_child(alice.id).points == 0

    def test_closes_the_chore_for_that_child_only(self):
        coord, storage, _mod = _make_system()
        now = _now()
        alice, bob, chore = self._shared_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id, alice.id))
            assert coord.get_due_chores_for_child(alice.id) == []
            assert [c.id for c in coord.get_due_chores_for_child(bob.id)] == [chore.id]
            assert run(coord.async_complete_chore(chore.id, alice.id)) is None
            assert run(coord.async_complete_chore(chore.id, bob.id)) is not None

        assert storage.get_child(bob.id).points == 5

    def test_today_board_marks_only_that_child_done(self):
        coord, storage, _mod = _make_system()
        now = _now()
        alice, bob, chore = self._shared_chore(coord, _mod, now)

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id, alice.id))
            board = coord.get_today_board()

        status = {c["child_id"]: c["chores"][0]["status"] for c in board["children"]}
        assert status == {alice.id: "done", bob.id: "todo"}

    def test_recurring_chore_advances_only_that_childs_window(self):
        coord, storage, _mod = _make_system()
        now = _now()
        alice, bob, chore = self._shared_chore(coord, _mod, now, schedule_mode="recurring", recurrence="weekly")

        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id, alice.id))
            assert coord.is_chore_available_for_child(chore, alice.id) is False
            assert coord.is_chore_available_for_child(chore, bob.id) is True

        assert storage.get_last_completed(chore.id, alice.id).get("current") == now.isoformat()
        assert not storage.get_last_completed(chore.id, bob.id).get("current")

    def test_rejects_a_child_the_chore_is_not_assigned_to(self):
        coord, storage, _mod = _make_system()
        now = _now()
        alice, bob, chore = self._shared_chore(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            carol = run(coord.async_add_child("Carol"))
            with pytest.raises(ValueError, match="not assigned"):
                run(coord.async_parent_complete_chore(chore.id, carol.id))
        assert storage.get_completions() == []

    @pytest.mark.parametrize("mode", ["alternating", "first_come"])
    def test_rejects_rotation_and_race_chores(self, mode):
        coord, storage, _mod = _make_system()
        now = _now()
        alice, bob, chore = self._shared_chore(coord, _mod, now, assignment_mode=mode)
        with patch.object(_mod.dt_util, "now", return_value=now):
            with pytest.raises(ValueError, match="rotation"):
                run(coord.async_parent_complete_chore(chore.id, alice.id))
        assert storage.get_completions() == []

    def test_round_trips_through_storage_and_the_sensor(self):
        from custom_components.taskmate.models import ChoreCompletion
        from custom_components.taskmate.sensor import _build_todays_completions

        coord, storage, _mod = _make_system()
        now = _now()
        alice, bob, chore = self._shared_chore(coord, _mod, now)
        with patch.object(_mod.dt_util, "now", return_value=now):
            run(coord.async_parent_complete_chore(chore.id, alice.id))
            run(coord.async_parent_complete_chore(chore.id))

        per_child, whole_pool = storage.get_completions()
        assert ChoreCompletion.from_dict(per_child.to_dict()).for_child_id == alice.id
        assert "for_child_id" not in whole_pool.to_dict()

        common = {
            "child_lookup": {c.id: c for c in storage.get_children()},
            "chore_lookup": {c.id: c for c in storage.get_chores()},
            "all_completions": storage.get_completions(),
        }
        with patch("custom_components.taskmate.sensor.dt_util.now", return_value=now):
            recs = {r["completion_id"]: r for r in _build_todays_completions(common)}
        assert recs[per_child.id]["for_child_id"] == alice.id
        assert "for_child_id" not in recs[whole_pool.id]
