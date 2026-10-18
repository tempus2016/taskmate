"""Reward fulfilment tracker (#1098): an approved reward stays owed until it is
handed over."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.models import Reward, RewardClaim

from .test_completion_eligibility import _make_system, _now, run

FUL = "custom_components.taskmate.coord_fulfilment.dt_util"


def _system(enabled=True, days=3):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.hass.bus = MagicMock()
    coord.badges = None
    coord.async_start_unlock = AsyncMock()
    if enabled:
        storage.set_setting("reward_fulfilment_enabled", True)
    storage.set_setting("reward_fulfilment_reminder_days", days)
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        reward = run(coord.async_add_reward("Movie night", cost=10))
    kid.points = 100
    storage.update_child(kid)
    return coord, storage, mod, kid, reward


def _claim_and_approve(coord, storage, mod, kid, reward, when=None):
    when = when or _now()
    with (
        patch.object(mod.dt_util, "now", return_value=when),
        patch("custom_components.taskmate.coord_rewards.dt_util.now", return_value=when),
        patch(f"{FUL}.now", return_value=when),
    ):
        claim = run(coord.async_claim_reward(reward.id, kid.id))
        run(coord.async_approve_reward(claim.id))
    return next(c for c in storage.get_reward_claims() if c.id == claim.id)


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


class TestOwed:
    def test_approving_while_on_puts_the_reward_in_the_owed_list(self):
        coord, storage, mod, kid, reward = _system()
        claim = _claim_and_approve(coord, storage, mod, kid, reward)
        assert claim.needs_delivery is True and claim.delivered_at is None
        with patch(f"{FUL}.now", return_value=_now()):
            owed = coord.owed_rewards()
        assert [o["claim_id"] for o in owed] == [claim.id]
        assert owed[0]["reward_name"] == "Movie night" and owed[0]["child_id"] == kid.id
        assert owed[0]["days_owed"] == 0
        with patch(f"{FUL}.now", return_value=_now()):
            assert [o["claim_id"] for o in coord.owed_rewards(kid.id)] == [claim.id]
            assert coord.owed_rewards("someone-else") == []

    def test_switched_off_means_nothing_is_tracked_or_shown(self):
        coord, storage, mod, kid, reward = _system(enabled=False)
        claim = _claim_and_approve(coord, storage, mod, kid, reward)
        assert claim.needs_delivery is False
        assert coord.owed_rewards() == []
        # Turning it on later does not back-fill old purchases.
        storage.set_setting("reward_fulfilment_enabled", True)
        assert coord.owed_rewards() == []

    def test_rewards_the_system_hands_over_itself_are_not_tracked(self):
        coord, storage, mod, kid, reward = _system()
        reward.streak_freeze = True
        storage.update_reward(reward)
        claim = _claim_and_approve(coord, storage, mod, kid, reward)
        assert claim.needs_delivery is False
        unlock = Reward(name="TV", cost=5, unlock_entity="switch.tv")
        storage.add_reward(unlock)
        claim = _claim_and_approve(coord, storage, mod, kid, unlock)
        assert claim.needs_delivery is False

    def test_marking_delivered_clears_it_and_fires_an_event(self):
        coord, storage, mod, kid, reward = _system()
        claim = _claim_and_approve(coord, storage, mod, kid, reward)
        later = _now() + dt.timedelta(days=1)
        with patch(f"{FUL}.now", return_value=later):
            run(coord.async_mark_reward_delivered(claim.id))
            assert coord.owed_rewards() == []
        stored = next(c for c in storage.get_reward_claims() if c.id == claim.id)
        assert stored.delivered_at == later and stored.delivered_by == "parent"
        (evt,) = _fired(coord, "taskmate_reward_delivered")
        assert evt["claim_id"] == claim.id and evt["child_id"] == kid.id and evt["reward_name"] == "Movie night"
        assert evt["delivered_by"] == "parent"

    def test_child_can_confirm_their_own_reward_only(self):
        coord, storage, mod, kid, reward = _system()
        claim = _claim_and_approve(coord, storage, mod, kid, reward)
        with pytest.raises(ValueError, match="not .*Vaiha|someone else|belong"):
            run(coord.async_mark_reward_delivered(claim.id, by="child", child_id="other"))
        with patch(f"{FUL}.now", return_value=_now()):
            run(coord.async_mark_reward_delivered(claim.id, by="child", child_id=kid.id))
        stored = next(c for c in storage.get_reward_claims() if c.id == claim.id)
        assert stored.delivered_by == "child"

    def test_marking_twice_or_an_unknown_claim_is_refused(self):
        coord, storage, mod, kid, reward = _system()
        claim = _claim_and_approve(coord, storage, mod, kid, reward)
        with patch(f"{FUL}.now", return_value=_now()):
            run(coord.async_mark_reward_delivered(claim.id))
            with pytest.raises(ValueError):
                run(coord.async_mark_reward_delivered(claim.id))
            with pytest.raises(ValueError):
                run(coord.async_mark_reward_delivered("nope"))

    def test_old_claims_load_with_safe_defaults_and_shape_is_unchanged(self):
        old = RewardClaim.from_dict({"reward_id": "r", "child_id": "c", "claimed_at": _now().isoformat()})
        assert old.needs_delivery is False and old.delivered_at is None and old.delivered_by == ""
        assert "needs_delivery" not in old.to_dict() and "delivered_at" not in old.to_dict()
        old.needs_delivery = True
        old.delivered_at = _now()
        old.delivered_by = "child"
        again = RewardClaim.from_dict(old.to_dict())
        assert again.needs_delivery is True and again.delivered_at == _now() and again.delivered_by == "child"


class TestReminder:
    def test_parents_are_nagged_after_n_days_and_then_every_n_days(self):
        coord, storage, mod, kid, reward = _system(days=3)
        claim = _claim_and_approve(coord, storage, mod, kid, reward)
        coord.notifications.fire.reset_mock()
        with patch(f"{FUL}.now", return_value=_now() + dt.timedelta(days=2, hours=23)):
            assert run(coord.async_check_owed_rewards()) == 0
        coord.notifications.fire.assert_not_called()
        with patch(f"{FUL}.now", return_value=_now() + dt.timedelta(days=3, minutes=1)):
            assert run(coord.async_check_owed_rewards()) == 1
            # Same minute again: nothing.
            assert run(coord.async_check_owed_rewards()) == 0
        type_id, ctx = coord.notifications.fire.call_args.args
        assert type_id == "reward_owed"
        assert ctx["child_name"] == "Vaiha" and ctx["reward_name"] == "Movie night" and ctx["days"] == 3
        assert ctx["claim_id"] == claim.id
        with patch(f"{FUL}.now", return_value=_now() + dt.timedelta(days=5)):
            assert run(coord.async_check_owed_rewards()) == 0
        with patch(f"{FUL}.now", return_value=_now() + dt.timedelta(days=6, minutes=1)):
            assert run(coord.async_check_owed_rewards()) == 1
        assert coord.notifications.fire.call_args.args[1]["days"] == 6

    def test_zero_days_or_feature_off_sends_nothing(self):
        coord, storage, mod, kid, reward = _system(days=0)
        _claim_and_approve(coord, storage, mod, kid, reward)
        coord.notifications.fire.reset_mock()
        with patch(f"{FUL}.now", return_value=_now() + dt.timedelta(days=30)):
            assert run(coord.async_check_owed_rewards()) == 0
        storage.set_setting("reward_fulfilment_reminder_days", 1)
        storage.set_setting("reward_fulfilment_enabled", False)
        with patch(f"{FUL}.now", return_value=_now() + dt.timedelta(days=30)):
            assert run(coord.async_check_owed_rewards()) == 0
        coord.notifications.fire.assert_not_called()

    def test_delivered_rewards_are_never_nagged(self):
        coord, storage, mod, kid, reward = _system(days=1)
        claim = _claim_and_approve(coord, storage, mod, kid, reward)
        with patch(f"{FUL}.now", return_value=_now()):
            run(coord.async_mark_reward_delivered(claim.id))
        coord.notifications.fire.reset_mock()
        with patch(f"{FUL}.now", return_value=_now() + dt.timedelta(days=9)):
            assert run(coord.async_check_owed_rewards()) == 0
        coord.notifications.fire.assert_not_called()


class TestSettings:
    def test_reminder_days_are_clamped_and_default_to_three(self):
        coord, storage, _mod, _kid, _reward = _system()
        assert coord.reward_fulfilment_reminder_days() == 3
        storage.set_setting("reward_fulfilment_reminder_days", "bogus")
        assert coord.reward_fulfilment_reminder_days() == 0
        storage.set_setting("reward_fulfilment_reminder_days", -4)
        assert coord.reward_fulfilment_reminder_days() == 0
        storage.set_setting("reward_fulfilment_enabled", "true")
        assert coord.reward_fulfilment_enabled() is True
