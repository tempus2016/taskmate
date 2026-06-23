"""Regression test for #558: a quest step on a chore that does NOT require
approval must advance the quest at completion time (auto-approve), not only
through the parent-approval path.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, Quest


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chore, quests, child):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()

    progress: dict = {}
    storage = MagicMock()
    storage.get_completions = MagicMock(return_value=[])
    storage.add_completion = MagicMock()
    storage.set_last_completed = MagicMock()
    storage.update_chore = MagicMock()
    storage.update_child = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.async_save = AsyncMock()
    # Quest plumbing (real QuestsMixin runs against these)
    storage.get_quests = MagicMock(return_value=quests)
    storage.get_quest_child_progress = MagicMock(
        side_effect=lambda qid, cid: progress.get(qid, {}).get(cid, {})
    )
    storage.set_quest_child_progress = MagicMock(
        side_effect=lambda qid, cid, p: progress.setdefault(qid, {}).__setitem__(cid, p)
    )

    coord.storage = storage
    coord._progress = progress
    coord.get_chore = MagicMock(return_value=chore)
    coord.get_child = MagicMock(return_value=child)
    coord.async_refresh = AsyncMock()
    coord._maybe_level_up = AsyncMock()
    # Skip badge / challenge side-effects we don't assert on here.
    coord.badges = None
    coord._async_evaluate_challenges = AsyncMock()
    # Points plumbing
    coord.effective_chore_points = MagicMock(return_value=chore.points)
    coord._apply_time_adjustment = MagicMock(side_effect=lambda c, base, when: base)
    coord._award_points = AsyncMock(return_value=chore.points)
    return coord


def test_no_approval_chore_advances_quest():
    """The final quest step is a no-approval chore: completing it must finish
    the quest (the exact #558 scenario)."""
    chore = Chore(name="Brush teeth", id="c2", points=5, requires_approval=False)
    quest = Quest(name="Bedtime", steps=["c1", "c2"], bonus_points=20, id="q1")
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    coord = _coord(chore, [quest], child)
    # Child is already on the final step (c1 done previously).
    coord.storage.set_quest_child_progress("q1", "kid", {"step": 1})

    comp = run(coord.async_complete_chore("c2", "kid"))

    assert comp is not None and comp.approved is True
    prog = coord._progress["q1"]["kid"]
    assert prog["step"] == 2, "quest should have advanced to completion"
    assert prog["completed_count"] == 1
    # _award_points is stubbed (doesn't mutate points), so only the quest bonus
    # — applied by the real _complete_quest — lands on the wallet here.
    assert child.points == 20
    fired = [c[0][0] for c in coord.hass.bus.async_fire.call_args_list]
    assert "taskmate_quest_completed" in fired


def test_no_approval_chore_evaluates_challenges():
    """Auto-approved completions must also run challenge evaluation (same gap)."""
    chore = Chore(name="Brush teeth", id="c2", points=5, requires_approval=False)
    child = Child(name="Mia", id="kid", points=0, total_points_earned=0)
    coord = _coord(chore, [], child)

    run(coord.async_complete_chore("c2", "kid"))

    coord._async_evaluate_challenges.assert_awaited_once_with("kid")
