"""Tests for quests (chore chains)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Quest


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(quests, child):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    progress: dict = {}
    storage = MagicMock()
    storage.get_quests = MagicMock(return_value=quests)
    storage.get_quest = MagicMock(side_effect=lambda qid: next((q for q in quests if q.id == qid), None))
    storage.get_quest_child_progress = MagicMock(side_effect=lambda qid, cid: progress.get(qid, {}).get(cid, {}))

    def _set(qid, cid, p):
        progress.setdefault(qid, {})[cid] = p

    storage.set_quest_child_progress = MagicMock(side_effect=_set)
    storage.update_child = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._progress = progress
    coord.get_child = MagicMock(return_value=child)
    coord.async_refresh = AsyncMock()
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    # Stub level-up so _complete_quest's optional hook is a no-op
    coord._maybe_level_up = AsyncMock()
    return coord


def test_advance_only_on_current_step():
    q = Quest(name="Morning", steps=["a", "b", "c"], bonus_points=30, id="q1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    coord = _coord([q], child)
    # Completing the second step out of order does nothing
    run(coord._async_advance_quests("kid", "b"))
    assert coord._progress.get("q1", {}).get("kid", {}).get("step", 0) == 0
    # Completing the first step advances to 1
    run(coord._async_advance_quests("kid", "a"))
    assert coord._progress["q1"]["kid"]["step"] == 1


def test_full_chain_awards_bonus_and_fires_event():
    q = Quest(name="Morning", steps=["a", "b"], bonus_points=30, id="q1")
    child = Child(name="Mia", id="kid", points=5, total_points_earned=5)
    coord = _coord([q], child)
    run(coord._async_advance_quests("kid", "a"))
    run(coord._async_advance_quests("kid", "b"))
    assert child.points == 35
    assert child.total_points_earned == 35
    prog = coord._progress["q1"]["kid"]
    assert prog["step"] == 2  # non-repeatable: stays complete
    assert prog["completed_count"] == 1
    fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
    assert "taskmate_quest_completed" in fired


def test_repeatable_resets_to_zero():
    q = Quest(name="Loop", steps=["a"], bonus_points=10, repeatable=True, id="q1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    coord = _coord([q], child)
    run(coord._async_advance_quests("kid", "a"))
    prog = coord._progress["q1"]["kid"]
    assert prog["step"] == 0  # reset
    assert prog["completed_count"] == 1
    assert child.points == 10


def test_assignment_scoping():
    q = Quest(name="OnlyBo", steps=["a"], assigned_to=["other"], id="q1")
    child = Child(name="Mia", id="kid")
    coord = _coord([q], child)
    run(coord._async_advance_quests("kid", "a"))
    assert "q1" not in coord._progress  # not assigned to this child


def test_inactive_quest_ignored():
    q = Quest(name="Off", steps=["a"], active=False, id="q1")
    child = Child(name="Mia", id="kid")
    coord = _coord([q], child)
    run(coord._async_advance_quests("kid", "a"))
    assert "q1" not in coord._progress


def test_create_quest_validates():
    coord = _coord([], Child(name="Mia", id="kid"))
    coord.storage.add_quest = MagicMock()
    with pytest.raises(ValueError):
        run(coord.async_create_quest(name="No steps", steps=[]))
    with pytest.raises(ValueError):
        run(coord.async_create_quest(name="", steps=["a"]))


# ---------------------------------------------------------------------------
# reversing an approval must rewind the chain, not leave it advanced
# ---------------------------------------------------------------------------


class TestQuestRewind:
    def test_mid_chain_step_is_rewound(self):
        q = Quest(name="Morning", steps=["a", "b", "c"], bonus_points=30, id="q1")
        child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
        coord = _coord([q], child)
        run(coord._async_advance_quests("kid", "a"))
        assert coord._progress["q1"]["kid"]["step"] == 1

        run(coord._async_rewind_quests("kid", "a"))
        assert coord._progress["q1"]["kid"]["step"] == 0

    def test_rewind_ignores_a_chore_that_did_not_advance_it(self):
        q = Quest(name="Morning", steps=["a", "b", "c"], bonus_points=30, id="q1")
        child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
        coord = _coord([q], child)
        run(coord._async_advance_quests("kid", "a"))

        run(coord._async_rewind_quests("kid", "zzz"))
        assert coord._progress["q1"]["kid"]["step"] == 1

    def test_repeatable_quest_bonus_is_not_paid_twice(self):
        """undo → re-approve on the final step used to pay the bonus again."""
        q = Quest(name="Loop", steps=["a"], bonus_points=30, id="q1", repeatable=True)
        child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
        coord = _coord([q], child)

        run(coord._async_advance_quests("kid", "a"))
        assert child.points == 30
        assert coord._progress["q1"]["kid"]["completed_count"] == 1

        run(coord._async_rewind_quests("kid", "a"))
        assert child.points == 0, "the quest bonus was not taken back"
        assert coord._progress["q1"]["kid"]["completed_count"] == 0

        run(coord._async_advance_quests("kid", "a"))
        assert child.points == 30, "re-approving paid the quest bonus twice"

    def test_one_shot_quest_completion_is_reversible(self):
        q = Quest(name="Once", steps=["a", "b"], bonus_points=50, id="q1", repeatable=False)
        child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
        coord = _coord([q], child)
        run(coord._async_advance_quests("kid", "a"))
        run(coord._async_advance_quests("kid", "b"))
        assert child.points == 50
        assert coord._progress["q1"]["kid"]["step"] == 2

        run(coord._async_rewind_quests("kid", "b"))
        assert coord._progress["q1"]["kid"]["step"] == 1
        assert child.points == 0
        assert coord._progress["q1"]["kid"]["completed_count"] == 0

    def test_rewind_logs_the_reversal(self):
        q = Quest(name="Loop", steps=["a"], bonus_points=30, id="q1", repeatable=True)
        child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
        coord = _coord([q], child)
        run(coord._async_advance_quests("kid", "a"))
        coord.storage.add_points_transaction.reset_mock()

        run(coord._async_rewind_quests("kid", "a"))
        tx = coord.storage.add_points_transaction.call_args[0][0]
        assert tx.points == -30
        assert "reversed" in tx.reason.lower()
