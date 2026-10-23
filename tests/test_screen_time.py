"""Screen-time bank: rewards buy minutes, the child's devices spend them."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.taskmate.models import Reward

from .test_completion_eligibility import _make_system, _now, run

ST = "custom_components.taskmate.coord_screen_time.dt_util"


def _system(devices=("switch.tv",), warn=10, stop=False):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.hass.bus = MagicMock()
    coord.hass.services = MagicMock()
    coord.hass.services.async_call = AsyncMock()
    coord.badges = None
    coord.async_start_unlock = AsyncMock()
    states: dict[str, str] = {}
    coord.hass.states = MagicMock()
    coord.hass.states.get = lambda eid: SimpleNamespace(state=states[eid]) if eid in states else None
    storage.set_setting("screen_time_enabled", True)
    storage.set_setting("screen_time_warn_minutes", warn)
    storage.set_setting("screen_time_stop_at_zero", stop)
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        other = run(coord.async_add_child("Leo"))
    storage.set_setting("screen_time_devices", {kid.id: list(devices)})
    kid.points = 100
    storage.update_child(kid)
    return coord, storage, mod, kid, other, states


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


def _tick(coord, n=1):
    with patch(f"{ST}.now", return_value=_now()):
        for _ in range(n):
            run(coord.async_check_screen_time())


def _set(coord, kid, minutes):
    with patch(f"{ST}.now", return_value=_now()):
        run(coord.async_adjust_screen_time(kid.id, minutes))


class TestReward:
    def test_approving_a_screen_time_reward_adds_the_minutes(self):
        coord, storage, mod, kid, _other, _states = _system()
        reward = Reward(name="30 min Xbox", cost=10, screen_minutes=30)
        storage.add_reward(reward)
        with (
            patch.object(mod.dt_util, "now", return_value=_now()),
            patch("custom_components.taskmate.coord_rewards.dt_util.now", return_value=_now()),
            patch(f"{ST}.now", return_value=_now()),
        ):
            claim = run(coord.async_claim_reward(reward.id, kid.id))
            run(coord.async_approve_reward(claim.id))
        assert coord.screen_time_balance(kid.id) == 30
        assert storage.get_child(kid.id).points == 90
        (evt,) = _fired(coord, "taskmate_screen_time_changed")
        assert evt["delta"] == 30 and evt["minutes"] == 30 and evt["reward_id"] == reward.id

    def test_screen_time_rewards_are_never_owed_or_jackpots(self):
        coord, *_ = _system()
        reward = Reward(name="TV", cost=10, screen_minutes=20, is_jackpot=True)
        assert reward.is_jackpot is False
        assert coord.reward_needs_delivery(reward) is False
        assert Reward.from_dict(reward.to_dict()).screen_minutes == 20

    def test_the_rewards_sensor_flags_only_screen_time_rewards(self):
        reward = Reward(name="TV", cost=10, screen_minutes=20)
        assert reward.to_dict()["screen_minutes"] == 20
        assert Reward.from_dict({"name": "Old"}).screen_minutes == 0


class TestBurn:
    def test_a_minute_is_spent_only_while_a_device_is_on(self):
        coord, _storage, _mod, kid, _other, states = _system()
        _set(coord, kid, 30)
        states["switch.tv"] = "off"
        _tick(coord)
        assert coord.screen_time_balance(kid.id) == 30
        states["switch.tv"] = "on"
        _tick(coord, 3)
        assert coord.screen_time_balance(kid.id) == 27

    def test_two_devices_on_still_cost_one_minute(self):
        coord, _storage, _mod, kid, _other, states = _system(devices=("switch.tv", "media_player.xbox"))
        _set(coord, kid, 10)
        states.update({"switch.tv": "on", "media_player.xbox": "playing"})
        _tick(coord)
        assert coord.screen_time_balance(kid.id) == 9

    def test_low_warning_fires_once_and_rearms_after_a_top_up(self):
        coord, _storage, _mod, kid, _other, states = _system(warn=10)
        _set(coord, kid, 12)
        states["switch.tv"] = "on"
        _tick(coord, 4)
        assert len(_fired(coord, "taskmate_screen_time_low")) == 1
        types = [c.args[0] for c in coord.notifications.fire.call_args_list]
        assert types.count("screen_time_low") == 1
        _set(coord, kid, 20)
        _tick(coord, 20)
        assert len(_fired(coord, "taskmate_screen_time_low")) == 2

    def test_reaching_zero_fires_out_once_and_only_targets_that_child(self):
        coord, _storage, _mod, kid, other, states = _system()
        _set(coord, kid, 2)
        states["switch.tv"] = "on"
        _tick(coord, 5)
        assert coord.screen_time_balance(kid.id) == 0
        assert len(_fired(coord, "taskmate_screen_time_out")) == 1
        call = next(c for c in coord.notifications.fire.call_args_list if c.args[0] == "screen_time_out")
        assert f"child:{kid.id}" in call.kwargs["only_recipients"]
        assert f"child:{other.id}" not in call.kwargs["only_recipients"]

    def test_stop_at_zero_turns_the_devices_off_and_keeps_them_off(self):
        coord, _storage, _mod, kid, _other, states = _system(devices=("switch.tv", "binary_sensor.console"), stop=True)
        _set(coord, kid, 1)
        states.update({"switch.tv": "on", "binary_sensor.console": "on"})
        _tick(coord, 3)
        calls = [
            c for c in coord.hass.services.async_call.call_args_list if c.args[:2] == ("homeassistant", "turn_off")
        ]
        assert calls and all(c.args[2] == {"entity_id": "switch.tv"} for c in calls)
        assert len(calls) == 3

    def test_without_stop_at_zero_nothing_is_switched(self):
        coord, _storage, _mod, kid, _other, states = _system(stop=False)
        states["switch.tv"] = "on"
        _tick(coord, 2)
        coord.hass.services.async_call.assert_not_called()

    def test_disabled_feature_spends_nothing_and_hides_the_summary(self):
        coord, storage, _mod, kid, _other, states = _system()
        _set(coord, kid, 10)
        storage.set_setting("screen_time_enabled", False)
        states["switch.tv"] = "on"
        _tick(coord)
        assert coord.screen_time_balance(kid.id) == 10
        assert coord.screen_time_summary(kid.id) is None


class TestAdjust:
    def test_balance_never_goes_negative_and_unknown_child_is_refused(self):
        coord, _storage, _mod, kid, _other, _states = _system()
        _set(coord, kid, 5)
        _set(coord, kid, -50)
        assert coord.screen_time_balance(kid.id) == 0
        with pytest.raises(ValueError, match="not found"):
            _set(coord, SimpleNamespace(id="nope"), 5)

    def test_summary_and_state_for_the_card_and_panel(self):
        coord, _storage, _mod, kid, other, states = _system(warn=10)
        _set(coord, kid, 8)
        states["switch.tv"] = "on"
        assert coord.screen_time_summary(kid.id) == {"minutes": 8, "active": True, "low": True}
        assert coord.screen_time_summary(other.id) == {"minutes": 0, "active": False, "low": False}
        state = coord.screen_time_state()
        assert state[kid.id]["devices"] == ["switch.tv"]
        assert state[kid.id]["log"][-1]["delta"] == 8


class TestSettingsValidation:
    def test_devices_must_come_from_known_domains(self):
        from custom_components.taskmate.websocket import _validate_screen_time_devices

        assert _validate_screen_time_devices({"a": ["switch.tv", "switch.tv"]}) == {"a": ["switch.tv"]}
        with pytest.raises(vol.Invalid):
            _validate_screen_time_devices({"a": ["lock.front_door"]})
        with pytest.raises(vol.Invalid):
            _validate_screen_time_devices({"a": [f"switch.d{i}" for i in range(11)]})


def test_removing_a_child_forgets_their_balance_and_devices():
    coord, storage, _mod, kid, _other, _states = _system()
    _set(coord, kid, 30)
    storage.remove_child_from_sections(kid.id)
    assert coord.screen_time_balance(kid.id) == 0
    assert coord.screen_time_devices(kid.id) == []


def test_a_screen_going_off_refreshes_the_card_once():
    coord, _storage, _mod, kid, _other, states = _system()
    coord.async_refresh = AsyncMock()
    states["switch.tv"] = "on"
    _tick(coord)
    assert coord.async_refresh.await_count == 1
    states["switch.tv"] = "off"
    _tick(coord)
    assert coord.async_refresh.await_count == 2
    _tick(coord)
    assert coord.async_refresh.await_count == 2
