"""Reactive ad-hoc chores with a deadline and speed bonus (#674).

An automation raises a short-lived chore — "the washing machine finished, empty
it within 30 minutes". It disappears when the deadline passes, and beating the
deadline pays a speed bonus.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.taskmate.models import Chore

from .test_coordinator_logic import _make_coord


def _now():
    return dt_util.as_local(dt_util.now())


def _in(minutes):
    return (_now() + timedelta(minutes=minutes)).isoformat()


def _coord():
    coord = _make_coord()
    coord.storage.get_last_completed = MagicMock(return_value={})
    coord.storage.get_chores = MagicMock(return_value=[])
    coord.storage.update_chore = MagicMock()
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord.hass.bus.async_fire = MagicMock()
    return coord


class TestDeadlineParsing:
    def test_unset_deadline_is_none(self):
        assert _coord().chore_deadline(Chore(name="Chore")) is None

    def test_blank_deadline_is_none(self):
        assert _coord().chore_deadline(Chore(name="Chore", deadline_at="   ")) is None

    def test_garbage_deadline_is_ignored(self):
        """Hand-edited storage shouldn't be able to make a chore vanish."""
        coord = _coord()
        chore = Chore(name="Chore", deadline_at="not-a-date")
        assert coord.chore_deadline(chore) is None
        assert coord.chore_deadline_passed(chore) is False

    def test_naive_deadline_is_treated_as_local(self):
        coord = _coord()
        naive = (datetime.now() + timedelta(minutes=30)).replace(microsecond=0).isoformat()
        parsed = coord.chore_deadline(Chore(name="Chore", deadline_at=naive))
        assert parsed is not None
        assert parsed.tzinfo is not None

    def test_aware_deadline_round_trips(self):
        coord = _coord()
        target = _now() + timedelta(minutes=15)
        parsed = coord.chore_deadline(Chore(name="Chore", deadline_at=target.isoformat()))
        assert abs((parsed - target).total_seconds()) < 1


class TestDeadlinePassed:
    def test_future_deadline_has_not_passed(self):
        assert _coord().chore_deadline_passed(Chore(name="C", deadline_at=_in(10))) is False

    def test_past_deadline_has_passed(self):
        assert _coord().chore_deadline_passed(Chore(name="C", deadline_at=_in(-1))) is True

    def test_no_deadline_never_passes(self):
        assert _coord().chore_deadline_passed(Chore(name="C")) is False


class TestAvailabilityGate:
    def _available(self, coord, chore):
        coord.storage.get_chore = MagicMock(return_value=chore)
        return coord.is_chore_available_for_child(chore, "kid1")

    def test_chore_within_deadline_is_available(self):
        coord = _coord()
        chore = Chore(name="Empty the washer", schedule_mode="one_shot",
                      created_date=_now().date().isoformat(), deadline_at=_in(20))
        assert self._available(coord, chore) is True

    def test_chore_past_deadline_is_unavailable(self):
        coord = _coord()
        chore = Chore(name="Empty the washer", schedule_mode="one_shot",
                      created_date=_now().date().isoformat(), deadline_at=_in(-5))
        assert self._available(coord, chore) is False

    def test_chore_without_deadline_is_unaffected(self):
        coord = _coord()
        chore = Chore(name="Wash up", schedule_mode="specific_days")
        assert self._available(coord, chore) is True


class TestSpeedBonus:
    def test_bonus_applied_when_deadline_beaten(self):
        coord = _coord()
        chore = Chore(name="C", deadline_at=_in(10), speed_bonus_points=5)
        assert coord._apply_speed_bonus(chore, 10, dt_util.now()) == 15

    def test_no_bonus_after_the_deadline(self):
        coord = _coord()
        chore = Chore(name="C", deadline_at=_in(-10), speed_bonus_points=5)
        assert coord._apply_speed_bonus(chore, 10, dt_util.now()) == 10

    def test_no_bonus_without_a_deadline(self):
        """A speed bonus with no deadline to beat is meaningless, not free points."""
        coord = _coord()
        chore = Chore(name="C", speed_bonus_points=5)
        assert coord._apply_speed_bonus(chore, 10, dt_util.now()) == 10

    def test_zero_bonus_is_a_no_op(self):
        coord = _coord()
        chore = Chore(name="C", deadline_at=_in(10), speed_bonus_points=0)
        assert coord._apply_speed_bonus(chore, 10, dt_util.now()) == 10

    def test_bonus_stacks_on_top_of_the_time_adjustment(self):
        """Both incentives can apply to one completion."""
        coord = _coord()
        chore = Chore(name="C", deadline_at=_in(10), speed_bonus_points=5,
                      due_time="23:59", early_bonus=3)
        adjusted = coord._apply_time_adjustment(chore, 10, dt_util.now())
        assert coord._apply_speed_bonus(chore, adjusted, dt_util.now()) == 18


class TestExpirySweep:
    @pytest.mark.asyncio
    async def test_expired_chore_is_disabled(self):
        coord = _coord()
        expired = Chore(name="Empty the washer", deadline_at=_in(-1))
        coord.storage.get_chores = MagicMock(return_value=[expired])
        await coord._async_expire_deadline_chores()
        assert expired.enabled is False
        coord.storage.async_save.assert_awaited()

    @pytest.mark.asyncio
    async def test_live_chore_is_left_alone(self):
        coord = _coord()
        live = Chore(name="Empty the washer", deadline_at=_in(30))
        coord.storage.get_chores = MagicMock(return_value=[live])
        await coord._async_expire_deadline_chores()
        assert live.enabled is True
        coord.storage.async_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_already_disabled_chore_is_skipped(self):
        coord = _coord()
        done = Chore(name="Empty the washer", deadline_at=_in(-1), enabled=False)
        coord.storage.get_chores = MagicMock(return_value=[done])
        await coord._async_expire_deadline_chores()
        coord.storage.update_chore.assert_not_called()

    @pytest.mark.asyncio
    async def test_expiry_fires_an_event(self):
        """So an automation can nag, re-raise, or log the miss."""
        coord = _coord()
        expired = Chore(name="Empty the washer", deadline_at=_in(-1))
        coord.storage.get_chores = MagicMock(return_value=[expired])
        await coord._async_expire_deadline_chores()
        coord.hass.bus.async_fire.assert_called_once()
        event, payload = coord.hass.bus.async_fire.call_args[0]
        assert event == "taskmate_chore_expired"
        assert payload["chore_id"] == expired.id
        assert payload["chore_name"] == "Empty the washer"

    @pytest.mark.asyncio
    async def test_sweep_refreshes_by_default(self):
        coord = _coord()
        coord.storage.get_chores = MagicMock(return_value=[Chore(name="C", deadline_at=_in(-1))])
        await coord._async_expire_deadline_chores()
        coord.async_refresh.assert_awaited()

    @pytest.mark.asyncio
    async def test_sweep_does_not_refresh_when_told_not_to(self):
        """Refreshing from inside _async_update_data re-enters the coordinator
        and deadlocks it — the whole integration wedges."""
        coord = _coord()
        coord.storage.get_chores = MagicMock(return_value=[Chore(name="C", deadline_at=_in(-1))])
        await coord._async_expire_deadline_chores(refresh=False)
        coord.storage.async_save.assert_awaited()
        coord.async_refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_update_data_sweeps_without_refreshing(self):
        """Guards the wiring itself, not just the helper's flag."""
        coord = _coord()
        coord.storage.data_version = 1
        coord._data_snapshot_cache = None
        coord._async_auto_stop_capped_sessions = AsyncMock()
        coord._async_check_family_goal = AsyncMock()
        coord._refresh_tracked_availability_entities = MagicMock()
        coord._build_data_snapshot = MagicMock(return_value={})
        expired = Chore(name="C", deadline_at=_in(-1))
        coord.storage.get_chores = MagicMock(return_value=[expired])
        await coord._async_update_data()
        assert expired.enabled is False
        coord.async_refresh.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_chores_without_deadlines_are_never_swept(self):
        coord = _coord()
        plain = Chore(name="Wash up")
        coord.storage.get_chores = MagicMock(return_value=[plain])
        await coord._async_expire_deadline_chores()
        assert plain.enabled is True


class TestRoundTrip:
    def test_fields_survive_to_dict_from_dict(self):
        chore = Chore(name="C", deadline_at=_in(30), speed_bonus_points=7)
        restored = Chore.from_dict(chore.to_dict())
        assert restored.deadline_at == chore.deadline_at
        assert restored.speed_bonus_points == 7

    def test_legacy_chore_without_the_fields(self):
        restored = Chore.from_dict({"name": "Old chore"})
        assert restored.deadline_at == ""
        assert restored.speed_bonus_points == 0
