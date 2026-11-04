"""Deleting a chore clears its timed sessions straight away.

A running or paused timer on a deleted chore used to stay in storage until the
midnight stale-session sweep, and a bulk delete left the chore's completions
and other per-chore records behind as well — so restoring it from Recently
deleted then added its completions a second time. Every delete path now goes
through async_remove_chore, and a restore never brings a timer back.
"""

from __future__ import annotations

from custom_components.taskmate.models import ChoreCompletion, TimedSession

from .test_completion_eligibility import _now, run
from .test_recently_deleted import _at, _chore, _system


def _timed(coord, name="Reading"):
    chore = _chore(coord, name)
    chore.task_type = "timed"
    chore.timed_rate_minutes = 5
    chore.timed_rate_points = 2
    coord.storage.update_chore(chore)
    return chore


def _session(storage, chore, child, state="paused"):
    storage.save_timed_session(
        TimedSession(
            chore_id=chore.id,
            child_id=child.id,
            state=state,
            segments=[{"start": _now().isoformat(), "end": None if state == "running" else _now().isoformat()}],
            session_date=_now().date().isoformat(),
        )
    )


def _sessions_for(storage, chore_id):
    return [s for s in storage.get_timed_sessions() if s.chore_id == chore_id]


class TestDeleteClearsSessions:
    def test_remove_chore_drops_its_running_and_paused_sessions(self):
        coord, storage, kid, other = _system()
        chore = _timed(coord)
        _session(storage, chore, kid, "running")
        _session(storage, chore, other, "paused")
        with _at(_now()):
            run(coord.async_remove_chore(chore.id))
        assert _sessions_for(storage, chore.id) == []

    def test_other_chores_sessions_are_left_alone(self):
        coord, storage, kid, _other = _system()
        gone, kept = _timed(coord, "Reading"), _timed(coord, "Piano")
        _session(storage, gone, kid)
        _session(storage, kept, kid, "running")
        with _at(_now()):
            run(coord.async_remove_chore(gone.id))
        assert [s.chore_id for s in storage.get_timed_sessions()] == [kept.id]

    def test_delete_service_path_drops_sessions(self):
        from custom_components.taskmate.chore_services import async_delete_chore_from_call

        coord, storage, kid, _other = _system()
        chore = _timed(coord)
        _session(storage, chore, kid)
        with _at(_now()):
            run(async_delete_chore_from_call(coord, {"chore_id": chore.id, "confirm": True}))
        assert _sessions_for(storage, chore.id) == []

    def test_bulk_delete_drops_sessions(self):
        coord, storage, kid, _other = _system()
        a, b = _timed(coord, "A"), _timed(coord, "B")
        _session(storage, a, kid)
        _session(storage, b, kid, "running")
        with _at(_now()):
            run(coord.async_bulk_chore_action("delete", [a.id, b.id]))
        assert storage.get_timed_sessions() == []

    def test_shopping_job_retire_path_drops_sessions(self):
        """keep_deleted=False (chores TaskMate retires itself) clears them too."""
        coord, storage, kid, _other = _system()
        chore = _timed(coord)
        _session(storage, chore, kid)
        with _at(_now()):
            run(coord.async_remove_chore(chore.id, keep_deleted=False))
        assert _sessions_for(storage, chore.id) == []
        assert coord.recently_deleted() == []


class TestRestore:
    def test_restore_does_not_bring_a_timer_back(self):
        coord, storage, kid, _other = _system()
        chore = _timed(coord)
        _session(storage, chore, kid, "running")
        with _at(_now()):
            run(coord.async_remove_chore(chore.id))
            run(coord.async_restore_deleted("chore", chore.id))
        assert storage.get_chore(chore.id) is not None
        assert _sessions_for(storage, chore.id) == []

    def test_restore_drops_an_orphan_timer_left_by_an_older_delete(self):
        """Before the fix a delete left the session behind; a restore must not
        pick it back up as a timer that has been "running" ever since."""
        coord, storage, kid, _other = _system()
        chore = _timed(coord)
        with _at(_now()):
            run(coord.async_remove_chore(chore.id))
        _session(storage, chore, kid, "running")  # the orphan an older delete left
        with _at(_now()):
            run(coord.async_restore_deleted("chore", chore.id))
        assert _sessions_for(storage, chore.id) == []

    def test_restore_after_bulk_delete_does_not_double_completions(self):
        coord, storage, kid, _other = _system()
        chore = _chore(coord)
        storage.add_completion(
            ChoreCompletion(chore_id=chore.id, child_id=kid.id, completed_at=_now(), approved=True, points_awarded=5)
        )
        with _at(_now()):
            run(coord.async_bulk_chore_action("delete", [chore.id]))
        assert [c for c in storage.get_completions() if c.chore_id == chore.id] == []
        with _at(_now()):
            run(coord.async_restore_deleted("chore", chore.id))
        assert len([c for c in storage.get_completions() if c.chore_id == chore.id]) == 1

    def test_bulk_delete_cleans_what_a_single_delete_cleans(self):
        coord, storage, kid, _other = _system()
        first, chore = _chore(coord, "Make bed"), _chore(coord)
        storage.set_last_completed(chore.id, kid.id, _now().isoformat())
        storage.data["task_groups"] = [
            {"id": "g1", "name": "Morning", "policy": "sticky", "chore_ids": [first.id, chore.id]}
        ]
        with _at(_now()):
            run(coord.async_set_chore_order(kid.id, [chore.id, first.id]))
            run(coord.async_bulk_chore_action("delete", [chore.id]))
        assert not storage.get_last_completed(chore.id, kid.id)
        assert storage.get_task_groups()[0].chore_ids == [first.id]
        assert storage.get_child(kid.id).chore_order == [first.id]
        assert [e["id"] for e in coord.recently_deleted()] == [chore.id]
