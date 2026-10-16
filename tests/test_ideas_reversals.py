"""The weekly goal bonus and a make-it-right refund follow the completion that
earned them, and count towards what a child's undo must still have in hand."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from custom_components.taskmate.models import Penalty

from .test_completion_eligibility import _now, run
from .test_family_care import _at, _family

GOALS = "custom_components.taskmate.coord_goals.dt_util"
RED = "custom_components.taskmate.coord_redemptions.dt_util"


def _goal_clock(mod):
    return (
        _at(mod),
        patch(f"{GOALS}.now", return_value=_now()),
        patch(f"{GOALS}.as_local", side_effect=lambda d: d),
    )


def _with(*patches):
    import contextlib

    stack = contextlib.ExitStack()
    for p in patches:
        stack.enter_context(p)
    return stack


class TestWeeklyGoalReversal:
    def _on(self, storage, bonus=15):
        storage.set_setting("weekly_goal_enabled", True)
        storage.set_setting("weekly_goal_bonus", bonus)
        storage.set_setting("chore_undo_seconds", 600)

    def test_undoing_the_chore_that_reached_the_goal_takes_the_bonus_back(self):
        coord, storage, mod, kid, chore = _family(requires_approval=False)
        self._on(storage)
        with _with(*_goal_clock(mod)):
            run(coord.async_set_weekly_goal(kid.id, 5))
            comp = run(coord.async_complete_chore(chore.id, kid.id))
            assert run(coord.async_check_weekly_goals()) == 1
            assert storage.get_child(kid.id).points == 5 + 15
            run(coord.async_undo_chore(comp.id))
            assert storage.get_child(kid.id).points == 0
            assert coord.weekly_goal_state(kid.id)["reached"] is False
            # It can be earned again this week.
            run(coord.async_complete_chore(chore.id, kid.id))
            assert run(coord.async_check_weekly_goals()) == 1
        assert storage.get_child(kid.id).points == 5 + 15
        assert storage.get_season_points(_now().strftime("%Y-%m")).get(kid.id, 0) == 15

    def test_rejecting_takes_it_back_too(self):
        coord, storage, mod, kid, chore = _family(requires_approval=True)
        self._on(storage)
        with _with(*_goal_clock(mod)):
            run(coord.async_set_weekly_goal(kid.id, 5))
            comp = run(coord.async_complete_chore(chore.id, kid.id))
            run(coord.async_approve_chore(comp.id))
            assert run(coord.async_check_weekly_goals()) == 1
            run(coord.async_reject_chore(comp.id))
        assert storage.get_child(kid.id).points == 0

    def test_undo_is_refused_once_the_goal_bonus_is_spent(self):
        coord, storage, mod, kid, chore = _family(requires_approval=False)
        self._on(storage)
        with _with(*_goal_clock(mod)):
            run(coord.async_set_weekly_goal(kid.id, 5))
            comp = run(coord.async_complete_chore(chore.id, kid.id))
            run(coord.async_check_weekly_goals())
            wish = run(coord.async_add_wish(kid.id, "Lego", target=100))
            run(coord.async_approve_wish(wish.id))
            run(coord.async_move_points_to_wish(wish.id, kid.id, 12))
            # 8 left, 5 + 15 owed.
            with pytest.raises(ValueError, match="already been spent"):
                run(coord.async_undo_chore(comp.id))
        assert storage.get_child(kid.id).points == 8

    def test_bonus_stays_while_other_completions_still_reach_the_goal(self):
        coord, storage, mod, kid, chore = _family(requires_approval=False, daily_limit=3)
        self._on(storage)
        with _with(*_goal_clock(mod)):
            run(coord.async_set_weekly_goal(kid.id, 5))
            run(coord.async_complete_chore(chore.id, kid.id))
            second = run(coord.async_complete_chore(chore.id, kid.id))
            run(coord.async_check_weekly_goals())
            run(coord.async_undo_chore(second.id))
        assert storage.get_child(kid.id).points == 5 + 15


class TestMakeItRightOwed:
    def test_undo_is_refused_once_the_refund_is_spent(self):
        coord, storage, mod, kid, chore = _family(requires_approval=False)
        storage.set_setting("chore_undo_seconds", 600)
        storage.update_child(type(kid)(**{**kid.__dict__, "points": 40}))
        penalty = Penalty(name="Slammed the door", points=10, redemption_chore_id=chore.id, redemption_percent=100)
        storage.add_penalty(penalty)
        with _at(mod), patch(f"{RED}.now", return_value=_now()), patch(f"{RED}.as_local", side_effect=lambda d: d):
            run(coord.async_apply_penalty(penalty.id, kid.id))
            assert storage.get_child(kid.id).points == 30
            comp = run(coord.async_complete_chore(chore.id, kid.id))
            assert storage.get_child(kid.id).points == 30 + 5 + 10
            assert coord._penalty_redemption_owed(comp) == 10
            wish = run(coord.async_add_wish(kid.id, "Lego", target=100))
            run(coord.async_approve_wish(wish.id))
            run(coord.async_move_points_to_wish(wish.id, kid.id, 35))
            # 10 left, 5 + 10 owed.
            with pytest.raises(ValueError, match="already been spent"):
                run(coord.async_undo_chore(comp.id))
            run(coord.async_take_points_from_wish(wish.id, kid.id, 35))
            run(coord.async_undo_chore(comp.id))
            # The offer is open again (checked against the same patched day).
            assert len(coord.open_redemptions(kid.id)) == 1
        assert storage.get_child(kid.id).points == 30
