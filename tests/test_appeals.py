"""Appeals: a child can ask for a second look at a rejection or a penalty."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.taskmate.models import Penalty

from .test_completion_eligibility import _now, run
from .test_family_care import _at, _family, _fired

APPEALS = "custom_components.taskmate.coord_appeals.dt_util"


def _clock(mod, when=None):
    import contextlib

    when = when or _now()
    stack = contextlib.ExitStack()
    for target in (
        f"{APPEALS}.now",
        "custom_components.taskmate.coord_rejections.dt_util.now",
        "custom_components.taskmate.coord_chores.dt_util.now",
        "custom_components.taskmate.coord_points.dt_util.now",
        "custom_components.taskmate.coord_rewards.dt_util.now",
    ):
        stack.enter_context(patch(target, return_value=when))
    stack.enter_context(_at(mod, when))
    return stack


def _setup(enabled=True):
    coord, storage, mod, kid, chore = _family(requires_approval=True, daily_limit=5)
    coord._celebrate = AsyncMock()
    coord.badges = None
    coord.async_start_unlock = AsyncMock()
    if enabled:
        storage.set_setting("appeals_enabled", True)
    return coord, storage, mod, kid, chore


def _reject_chore(coord, mod, kid, chore, reason=""):
    with _clock(mod):
        comp = run(coord.async_complete_chore(chore.id, kid.id))
        run(coord.async_reject_chore(comp.id, reason=reason))
    return comp


class TestAppealable:
    def test_a_rejected_chore_is_appealable_even_without_a_reason(self):
        coord, storage, mod, kid, chore = _setup()
        _reject_chore(coord, mod, kid, chore)
        with _clock(mod):
            (item,) = coord.appealable_for_child(kid.id)
        assert item["kind"] == "chore" and item["name"] == "Tidy room" and item["points"] == 5

    def test_nothing_is_appealable_while_switched_off(self):
        coord, storage, mod, kid, chore = _setup(enabled=False)
        _reject_chore(coord, mod, kid, chore, "Not done")
        with _clock(mod):
            assert coord.appealable_for_child(kid.id) == []
        # And a rejection without a reason still leaves no trace, as before.
        coord2, storage2, mod2, kid2, chore2 = _setup(enabled=False)
        _reject_chore(coord2, mod2, kid2, chore2)
        assert storage2.get_rejections() == []

    def test_the_activity_feed_still_only_shows_reasoned_rejections(self):
        coord, storage, mod, kid, chore = _setup()
        _reject_chore(coord, mod, kid, chore)
        with _clock(mod):
            assert coord.recent_rejections() == []
            assert coord.rejections_for_child(kid.id) == []

    def test_a_penalty_is_appealable_and_the_window_closes_after_48_hours(self):
        coord, storage, mod, kid, chore = _setup()
        kid.points = 20
        storage.update_child(kid)
        storage.add_penalty(Penalty(name="Slammed the door", points=5, id="pen1"))
        with _clock(mod):
            run(coord.async_apply_penalty("pen1", kid.id))
            (item,) = coord.appealable_for_child(kid.id)
        assert item["kind"] == "penalty" and item["name"] == "Slammed the door" and item["points"] == 5
        with _clock(mod, _now() + dt.timedelta(hours=49)):
            assert coord.appealable_for_child(kid.id) == []


class TestAppeal:
    def test_appealing_notifies_parents_and_takes_the_item_off_the_list(self):
        coord, storage, mod, kid, chore = _setup()
        _reject_chore(coord, mod, kid, chore)
        with _clock(mod):
            (item,) = coord.appealable_for_child(kid.id)
            appeal = run(coord.async_appeal(kid.id, item["kind"], item["target_id"], "I did do it!"))
            assert coord.appealable_for_child(kid.id) == []
            with pytest.raises(ValueError, match="already"):
                run(coord.async_appeal(kid.id, item["kind"], item["target_id"]))
        assert appeal["status"] == "open" and appeal["message"] == "I did do it!"
        type_id, ctx = coord.notifications.fire.call_args.args
        assert type_id == "appeal_submitted" and ctx["child_name"] == "Vaiha" and ctx["item_name"] == "Tidy room"
        (evt,) = _fired(coord, "taskmate_appeal_submitted")
        assert evt["appeal_id"] == appeal["id"]

    def test_a_child_cannot_appeal_someone_elses_item_or_something_made_up(self):
        coord, storage, mod, kid, chore = _setup()
        _reject_chore(coord, mod, kid, chore)
        with _clock(mod):
            other = run(coord.async_add_child("Leo"))
            (item,) = coord.appealable_for_child(kid.id)
            with pytest.raises(ValueError):
                run(coord.async_appeal(other.id, item["kind"], item["target_id"]))
            with pytest.raises(ValueError):
                run(coord.async_appeal(kid.id, "chore", "nope"))

    def test_refused_while_switched_off(self):
        coord, storage, mod, kid, chore = _setup()
        _reject_chore(coord, mod, kid, chore)
        storage.set_setting("appeals_enabled", False)
        with _clock(mod), pytest.raises(ValueError, match="switched off"):
            run(coord.async_appeal(kid.id, "chore", "anything"))


class TestDecide:
    def _appeal(self, coord, storage, mod, kid, chore):
        _reject_chore(coord, mod, kid, chore)
        with _clock(mod):
            (item,) = coord.appealable_for_child(kid.id)
            return run(coord.async_appeal(kid.id, item["kind"], item["target_id"]))

    def test_overturning_a_chore_rejection_pays_the_points(self):
        coord, storage, mod, kid, chore = _setup()
        appeal = self._appeal(coord, storage, mod, kid, chore)
        with _clock(mod):
            run(coord.async_decide_appeal(appeal["id"], overturn=True, note="Sorry, you're right"))
            decided = coord.appeals_for_child(kid.id)
        assert storage.get_child(kid.id).points == 5
        assert decided[0]["status"] == "overturned" and decided[0]["note"] == "Sorry, you're right"
        (evt,) = _fired(coord, "taskmate_appeal_decided")
        assert evt["overturned"] is True
        assert coord.notifications.fire.call_args.args[0] == "appeal_decided"
        with _clock(mod), pytest.raises(ValueError, match="already"):
            run(coord.async_decide_appeal(appeal["id"], overturn=False))

    def test_upholding_changes_nothing_but_the_status(self):
        coord, storage, mod, kid, chore = _setup()
        appeal = self._appeal(coord, storage, mod, kid, chore)
        with _clock(mod):
            run(coord.async_decide_appeal(appeal["id"], overturn=False, note="Bed still unmade"))
            assert coord.appeals_for_child(kid.id)[0]["status"] == "upheld"
            assert coord.open_appeals() == []
        assert storage.get_child(kid.id).points == 0

    def test_overturning_a_reward_rejection_approves_it_now(self):
        coord, storage, mod, kid, chore = _setup()
        kid.points = 30
        storage.update_child(kid)
        with _clock(mod):
            reward = run(coord.async_add_reward("Movie night", cost=10))
            claim = run(coord.async_claim_reward(reward.id, kid.id))
            run(coord.async_reject_reward(claim.id))
            (item,) = coord.appealable_for_child(kid.id)
            assert item["kind"] == "reward" and item["points"] == 10
            appeal = run(coord.async_appeal(kid.id, "reward", item["target_id"]))
            run(coord.async_decide_appeal(appeal["id"], overturn=True))
        assert storage.get_child(kid.id).points == 20
        assert any(c.approved and c.reward_id == reward.id for c in storage.get_reward_claims())

    def test_overturning_a_penalty_undoes_it_and_closes_its_make_it_right_offer(self):
        coord, storage, mod, kid, chore = _setup()
        kid.points = 20
        storage.update_child(kid)
        storage.add_penalty(Penalty(name="Slammed the door", points=5, id="pen1", redemption_chore_id=chore.id))
        with _clock(mod):
            run(coord.async_apply_penalty("pen1", kid.id))
            assert len(coord.open_redemptions(kid.id)) == 1
            (item,) = coord.appealable_for_child(kid.id)
            appeal = run(coord.async_appeal(kid.id, "penalty", item["target_id"]))
            run(coord.async_decide_appeal(appeal["id"], overturn=True))
            assert coord.open_redemptions(kid.id) == []
        child = storage.get_child(kid.id)
        assert child.points == 20 and child.total_penalties_received == 0

    def test_a_penalty_already_earned_back_is_not_appealable(self):
        coord, storage, mod, kid, chore = _setup()
        chore.requires_approval = False
        storage.update_chore(chore)
        kid.points = 20
        storage.update_child(kid)
        storage.add_penalty(Penalty(name="Slammed the door", points=5, id="pen1", redemption_chore_id=chore.id))
        with _clock(mod):
            run(coord.async_apply_penalty("pen1", kid.id))
            run(coord.async_complete_chore(chore.id, kid.id))
            assert [i["kind"] for i in coord.appealable_for_child(kid.id)] == []
