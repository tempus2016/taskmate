"""Tests for time-locked rewards (#857).

A reward can be restricted to certain weekdays and/or a time-of-day window.
Outside that window the reward is still visible but cannot be claimed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Reward

from .conftest import dt_util_mock

UTC = timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_coord(*, children=None, rewards=None):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.data = {}
    _children = {c.id: c for c in (children or [])}
    _rewards = {r.id: r for r in (rewards or [])}

    storage = MagicMock()
    storage.get_child = MagicMock(side_effect=lambda cid: _children.get(cid))
    storage.get_reward = MagicMock(side_effect=lambda rid: _rewards.get(rid))
    storage.get_reward_claims = MagicMock(return_value=[])
    storage.get_pending_reward_claims = MagicMock(return_value=[])
    storage.get_pool_allocation = MagicMock(return_value=None)
    storage.get_pool_allocations = MagicMock(return_value=[])
    storage.get_total_allocated_for_child = MagicMock(return_value=0)
    storage.get_total_allocated_for_reward = MagicMock(return_value=0)
    storage.upsert_pool_allocation = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.add_reward_claim = MagicMock()
    storage.update_child = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    notifications = MagicMock()
    notifications.fire = AsyncMock()
    coord.notifications = notifications
    return coord


def _locked_reward(**kw):
    base = {"name": "Candy bucket", "cost": 10, "id": "reward1", "time_lock_enabled": True}
    base.update(kw)
    return Reward(**base)


def _at(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


# 2024-03-20 is a Wednesday (weekday() == 2); 2024-03-22 is a Friday.
WED_NOON = _at(2024, 3, 20, 12)
FRI_NOON = _at(2024, 3, 22, 12)
FRI_2000 = _at(2024, 3, 22, 20)


# ---------------------------------------------------------------------------
# Pure predicate
# ---------------------------------------------------------------------------


class TestRewardIsTimeLocked:
    def test_disabled_is_never_locked(self):
        r = Reward(
            name="x",
            cost=10,
            time_lock_enabled=False,
            available_days=[4, 5],
            available_from="20:00",
            available_until="21:00",
        )
        assert TaskMateCoordinator._reward_is_time_locked(r, WED_NOON) is False

    def test_enabled_with_nothing_configured_is_not_locked(self):
        assert TaskMateCoordinator._reward_is_time_locked(_locked_reward(), WED_NOON) is False

    def test_day_not_allowed_is_locked(self):
        r = _locked_reward(available_days=[4, 5])  # Fri, Sat
        assert TaskMateCoordinator._reward_is_time_locked(r, WED_NOON) is True

    def test_day_allowed_is_not_locked(self):
        r = _locked_reward(available_days=[4, 5])
        assert TaskMateCoordinator._reward_is_time_locked(r, FRI_NOON) is False

    def test_all_days_selected_behaves_like_no_day_restriction(self):
        r = _locked_reward(available_days=[0, 1, 2, 3, 4, 5, 6])
        assert TaskMateCoordinator._reward_is_time_locked(r, WED_NOON) is False

    def test_inside_time_window_is_not_locked(self):
        r = _locked_reward(available_from="07:00", available_until="19:00")
        assert TaskMateCoordinator._reward_is_time_locked(r, WED_NOON) is False

    def test_after_window_end_is_locked(self):
        r = _locked_reward(available_from="07:00", available_until="19:00")
        assert TaskMateCoordinator._reward_is_time_locked(r, _at(2024, 3, 20, 19, 0)) is True

    def test_before_window_start_is_locked(self):
        r = _locked_reward(available_from="07:00", available_until="19:00")
        assert TaskMateCoordinator._reward_is_time_locked(r, _at(2024, 3, 20, 6, 59)) is True

    def test_overnight_window_spans_midnight(self):
        r = _locked_reward(available_from="20:00", available_until="07:00")
        assert TaskMateCoordinator._reward_is_time_locked(r, _at(2024, 3, 20, 22)) is False
        assert TaskMateCoordinator._reward_is_time_locked(r, _at(2024, 3, 20, 3)) is False
        assert TaskMateCoordinator._reward_is_time_locked(r, WED_NOON) is True

    def test_equal_bounds_means_no_time_restriction(self):
        r = _locked_reward(available_from="07:00", available_until="07:00")
        assert TaskMateCoordinator._reward_is_time_locked(r, WED_NOON) is False

    def test_malformed_times_are_ignored(self):
        r = _locked_reward(available_from="nonsense", available_until="19:00")
        assert TaskMateCoordinator._reward_is_time_locked(r, WED_NOON) is False

    def test_day_and_time_must_both_pass(self):
        r = _locked_reward(available_days=[4], available_from="18:00", available_until="21:00")
        assert TaskMateCoordinator._reward_is_time_locked(r, FRI_2000) is False  # right day, right time
        assert TaskMateCoordinator._reward_is_time_locked(r, FRI_NOON) is True  # right day, wrong time
        assert TaskMateCoordinator._reward_is_time_locked(r, _at(2024, 3, 20, 20)) is True  # wrong day


# ---------------------------------------------------------------------------
# Claim / allocation gating
# ---------------------------------------------------------------------------


class TestTimeLockGating:
    def test_claim_blocked_outside_window(self):
        child = Child(name="Alice", points=100, id="kid1")
        reward = _locked_reward(available_days=[4, 5])
        coord = _make_coord(children=[child], rewards=[reward])
        dt_util_mock._now = WED_NOON
        try:
            with pytest.raises(ValueError, match="not available"):
                run(coord.async_claim_reward("reward1", "kid1"))
        finally:
            dt_util_mock._now = WED_NOON

    def test_claim_allowed_inside_window(self):
        child = Child(name="Alice", points=100, id="kid1")
        reward = _locked_reward(available_days=[4, 5])
        coord = _make_coord(children=[child], rewards=[reward])
        dt_util_mock._now = FRI_NOON
        try:
            claim = run(coord.async_claim_reward("reward1", "kid1"))
            assert claim.reward_id == "reward1"
        finally:
            dt_util_mock._now = WED_NOON

    def test_pool_allocation_still_allowed_outside_window(self):
        """Saving up is not spending — a time lock must not block allocations."""
        child = Child(name="Alice", points=100, id="kid1")
        reward = _locked_reward(cost=50, pool_enabled=True, available_days=[4, 5])
        coord = _make_coord(children=[child], rewards=[reward])
        dt_util_mock._now = WED_NOON
        run(coord.async_allocate_points_to_pool("kid1", "reward1", 10))
        coord.storage.upsert_pool_allocation.assert_called()

    def test_time_lock_does_not_make_reward_unavailable_for_refunds(self):
        """`_reward_is_unavailable` drives pool refunds — a temporary lock must stay out of it."""
        reward = _locked_reward(available_days=[4, 5])
        dt_util_mock._now = WED_NOON
        assert TaskMateCoordinator._reward_is_unavailable(reward) is False


# ---------------------------------------------------------------------------
# Model round-trip
# ---------------------------------------------------------------------------


class TestRewardModel:
    def test_defaults_are_unlocked(self):
        r = Reward(name="x", cost=10)
        assert r.time_lock_enabled is False
        assert r.available_days == []
        assert r.available_from == ""
        assert r.available_until == ""

    def test_round_trip(self):
        r = _locked_reward(available_days=[4, 5], available_from="18:00", available_until="21:00")
        r2 = Reward.from_dict(r.to_dict())
        assert r2.time_lock_enabled is True
        assert r2.available_days == [4, 5]
        assert r2.available_from == "18:00"
        assert r2.available_until == "21:00"

    def test_legacy_dict_without_fields(self):
        r = Reward.from_dict({"name": "Old", "cost": 20, "id": "r9"})
        assert r.time_lock_enabled is False
        assert r.available_days == []

    def test_out_of_range_days_are_dropped(self):
        r = Reward.from_dict({"name": "x", "cost": 10, "available_days": [0, 7, -1, "3", "x"]})
        assert r.available_days == [0, 3]


# ---------------------------------------------------------------------------
# Sensor payload
# ---------------------------------------------------------------------------


class TestSensorPayload:
    @staticmethod
    def _build(reward, now):
        from custom_components.taskmate import sensor as sensor_module

        dt_util_mock._now = now
        try:
            return sensor_module._build_rewards_list(
                {
                    "rewards": [reward],
                    "children": [Child(name="Alice", points=100, id="kid1")],
                    "pool_by_child_reward": {},
                    "pool_total_by_reward": {},
                }
            )[0]
        finally:
            dt_util_mock._now = WED_NOON

    def test_unlocked_reward_carries_no_time_lock_payload(self):
        row = self._build(Reward(name="Plain", cost=10, id="reward1"), WED_NOON)
        assert "time_lock" not in row
        assert "is_time_locked" not in row
        assert row["is_available"] is True

    def test_locked_reward_exposes_window_and_flag(self):
        reward = _locked_reward(available_days=[4, 5], available_from="18:00", available_until="21:00")
        row = self._build(reward, WED_NOON)
        assert row["time_lock"] == {"days": [4, 5], "from": "18:00", "until": "21:00"}
        assert row["is_time_locked"] is True
        assert row["is_available"] is False

    def test_inside_window_is_available_and_flag_omitted(self):
        reward = _locked_reward(available_days=[4, 5], available_from="18:00", available_until="21:00")
        row = self._build(reward, FRI_2000)
        assert row["time_lock"]["days"] == [4, 5]
        assert "is_time_locked" not in row
        assert row["is_available"] is True


# ---------------------------------------------------------------------------
# Websocket contract
# ---------------------------------------------------------------------------


def _reward_schema():
    """The add_reward websocket schema, wrapped for direct validation."""
    import voluptuous as vol

    from custom_components.taskmate.websocket import _reward_payload_schema

    return vol.Schema(_reward_payload_schema(require_name=True), extra=vol.ALLOW_EXTRA)


class TestWebsocketSchema:
    def test_accepts_time_lock_fields(self):
        schema = _reward_schema()
        schema(
            {
                "name": "Candy",
                "cost": 10,
                "time_lock_enabled": True,
                "available_days": [4, 5],
                "available_from": "18:00",
                "available_until": "21:00",
            }
        )

    def test_blank_times_mean_no_restriction(self):
        schema = _reward_schema()
        out = schema({"name": "Candy", "cost": 10, "available_from": "", "available_until": ""})
        assert out["available_from"] == ""

    def test_rejects_bad_time(self):
        import voluptuous as vol

        schema = _reward_schema()
        with pytest.raises(vol.Invalid):
            schema({"name": "Candy", "cost": 10, "available_from": "25:00"})

    def test_rejects_out_of_range_day(self):
        import voluptuous as vol

        schema = _reward_schema()
        with pytest.raises(vol.Invalid):
            schema({"name": "Candy", "cost": 10, "available_days": [7]})

    def test_editable_field_list_covers_the_lock(self):
        from custom_components.taskmate.websocket import _REWARD_FIELDS

        assert {"time_lock_enabled", "available_days", "available_from", "available_until"} <= _REWARD_FIELDS
