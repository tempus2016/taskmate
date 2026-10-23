"""Drag-to-reorder rewards: a stored order the sensor and rewards card follow."""

from __future__ import annotations

from unittest.mock import patch

from custom_components.taskmate import sensor as sensor_module

from .test_completion_eligibility import _make_system, _now, run
from .test_sensor_attributes import _MockEntry, _wired_stress_coordinator


def _system(*names):
    coord, storage, _mod = _make_system()
    with patch("custom_components.taskmate.coord_rewards.dt_util.now", return_value=_now()):
        rewards = [run(coord.async_add_reward(n, cost=10 * (i + 1))) for i, n in enumerate(names)]
    return coord, storage, rewards


def test_saved_order_is_the_stored_order():
    coord, storage, (cinema, xbox, dinner) = _system("Cinema trip", "30 min Xbox", "Pick Friday dinner")
    assert storage.has_reward_order() is False
    run(coord.async_set_reward_order([dinner.id, cinema.id, xbox.id]))
    assert [r.id for r in storage.get_rewards()] == [dinner.id, cinema.id, xbox.id]
    assert storage.has_reward_order() is True


def test_rewards_missing_from_the_order_go_last_in_their_existing_order():
    coord, storage, (a, b, c, d) = _system("A", "B", "C", "D")
    run(coord.async_set_reward_order([c.id, "gone", c.id]))
    assert [r.id for r in storage.get_rewards()] == [c.id, a.id, b.id, d.id]


def test_a_new_reward_goes_last():
    coord, storage, (a, b) = _system("A", "B")
    run(coord.async_set_reward_order([b.id, a.id]))
    with patch("custom_components.taskmate.coord_rewards.dt_util.now", return_value=_now()):
        new = run(coord.async_add_reward("New", cost=5))
    assert [r.id for r in storage.get_rewards()] == [b.id, a.id, new.id]


def test_rewards_sensor_flags_a_custom_order_only_once_set():
    coord = _wired_stress_coordinator()
    sensor = sensor_module.TaskMateRewardsSensor(coord, _MockEntry())
    coord.storage.has_reward_order = lambda: False
    assert "rewards_ordered" not in sensor._build_attributes()
    coord.storage.has_reward_order = lambda: True
    attrs = sensor._build_attributes()
    assert attrs["rewards_ordered"] is True
    # The list keeps the coordinator's (stored) order.
    assert [r["id"] for r in attrs["rewards"]] == [r.id for r in coord.data["rewards"]]
