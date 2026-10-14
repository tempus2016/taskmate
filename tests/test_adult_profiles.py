"""Adult profiles (#1061).

Parents who log their own chores were added as children and then had to
approve each other's work. A profile marked as an adult skips the approval
queue for its own completions; children's completions are unchanged.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

from custom_components.taskmate.models import BonusSubTask, Child

from .test_completion_eligibility import _make_system, _now, run


def _family(coord):
    kid = run(coord.async_add_child("Alice"))
    mum = run(coord.async_add_child("Mum", is_adult=True))
    return kid, mum


def _chore(coord, **over):
    return run(
        coord.async_add_chore(
            "Wash the car",
            points=20,
            requires_approval=True,
            schedule_mode="specific_days",
            **over,
        )
    )


class TestModel:
    def test_round_trips(self):
        child = Child.from_dict(Child(name="Dad", is_adult=True).to_dict())
        assert child.is_adult is True

    def test_existing_profiles_are_children(self):
        assert Child.from_dict({"name": "Old"}).is_adult is False


class TestCompletion:
    def test_adult_completion_is_approved_straight_away(self):
        coord, storage, _mod = _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            _kid, mum = _family(coord)
            chore = _chore(coord)
            completion = run(coord.async_complete_chore(chore.id, mum.id))

        assert completion.approved is True
        assert storage.get_child(mum.id).points == 20
        coord._async_notify_pending_approval.assert_not_called()

    def test_child_completion_still_waits_for_approval(self):
        coord, storage, _mod = _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            kid, _mum = _family(coord)
            chore = _chore(coord)
            completion = run(coord.async_complete_chore(chore.id, kid.id))

        assert completion.approved is False
        assert storage.get_child(kid.id).points == 0

    def test_adult_bonus_subtask_is_approved_straight_away(self):
        coord, storage, _mod = _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            _kid, mum = _family(coord)
            chore = _chore(coord)
            chore.bonus_subtasks = [BonusSubTask(id="b1", name="Polish too", points=5)]
            storage.update_chore(chore)
            run(coord.async_complete_chore(chore.id, mum.id))
            completion = run(coord.async_complete_bonus_subtask(chore.id, "b1", mum.id))

        assert completion.approved is True
        assert storage.get_child(mum.id).points == 25

    def test_adult_timed_session_is_approved_straight_away(self):
        coord, storage, _mod = _make_system()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            _kid, mum = _family(coord)
            chore = _chore(coord, assigned_to=[mum.id])
            chore.task_type = "timed"
            chore.timed_rate_points = 5
            chore.timed_rate_minutes = 10
            storage.update_chore(chore)
            run(coord.async_start_timed_task(chore.id, mum.id))
        with patch.object(_mod.dt_util, "now", return_value=_now() + dt.timedelta(minutes=30)):
            run(coord.async_stop_timed_task(chore.id, mum.id))

        completion = next(c for c in storage.get_completions() if c.chore_id == chore.id)
        assert completion.approved is True
        assert storage.get_child(mum.id).points == 15
