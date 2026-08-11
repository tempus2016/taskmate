"""Timed unlock rewards (#678).

Spend points to unlock the TV for half an hour. Two hard limits keep this from
becoming "a reward can do anything to your house": a reward can only turn one
entity on and back off, and that entity must be on the parent's allowlist —
checked at save time AND again when it actually fires.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.taskmate.models import Child, Reward

from .test_coordinator_logic import _make_coord


def _coord(allowlist=None, unlocks=None):
    settings = {}
    if allowlist is not None:
        settings["unlock_allowlist"] = allowlist
    if unlocks is not None:
        settings["active_unlocks"] = unlocks
    coord = _make_coord(settings=settings)

    def _set(key, value):
        settings[key] = value

    coord.storage.set_setting = MagicMock(side_effect=_set)
    coord.storage.get_setting = MagicMock(side_effect=lambda k, d="": settings.get(k, d))
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord.hass.services.async_call = AsyncMock()
    coord.hass.bus.async_fire = MagicMock()
    coord._unlock_timers = []
    coord._settings = settings
    return coord


def _reward(**kwargs):
    return Reward(name="TV time", cost=50, **kwargs)


class TestAllowlist:
    def test_empty_allowlist_permits_nothing(self):
        """Fail closed: this gates household devices."""
        assert _coord([]).is_unlock_allowed("switch.tv") is False

    def test_unset_allowlist_permits_nothing(self):
        assert _coord().is_unlock_allowed("switch.tv") is False

    def test_exact_entity_is_permitted(self):
        assert _coord(["switch.tv"]).is_unlock_allowed("switch.tv") is True

    def test_bare_domain_permits_the_whole_domain(self):
        coord = _coord(["switch"])
        assert coord.is_unlock_allowed("switch.tv") is True
        assert coord.is_unlock_allowed("switch.anything") is True

    def test_domain_entry_does_not_leak_to_other_domains(self):
        assert _coord(["switch"]).is_unlock_allowed("light.bedroom") is False

    def test_other_entities_are_refused(self):
        assert _coord(["switch.tv"]).is_unlock_allowed("switch.boiler") is False

    def test_matching_is_case_insensitive(self):
        assert _coord(["Switch.TV"]).is_unlock_allowed("switch.tv") is True

    @pytest.mark.parametrize("value", ["", "   ", "notanentity", "switch"])
    def test_malformed_entity_ids_are_refused(self, value):
        assert _coord(["switch", "switch.tv"]).is_unlock_allowed(value) is False


class TestValidation:
    def test_blank_entity_is_allowed_and_means_no_unlock(self):
        assert _coord(["switch.tv"]).validate_unlock("", 0) == ("", 0)

    def test_disallowed_entity_is_rejected(self):
        with pytest.raises(ValueError, match="not on the unlock allowlist"):
            _coord(["switch.tv"]).validate_unlock("switch.boiler", 30)

    def test_allowed_entity_passes(self):
        assert _coord(["switch.tv"]).validate_unlock("switch.tv", 30) == ("switch.tv", 30)

    def test_minutes_must_be_a_number(self):
        with pytest.raises(ValueError, match="whole number"):
            _coord(["switch.tv"]).validate_unlock("switch.tv", "ages")

    def test_negative_minutes_rejected(self):
        with pytest.raises(ValueError, match="negative"):
            _coord(["switch.tv"]).validate_unlock("switch.tv", -1)

    def test_absurd_duration_rejected(self):
        with pytest.raises(ValueError, match="cannot exceed"):
            _coord(["switch.tv"]).validate_unlock("switch.tv", 10000)


class TestStartingAnUnlock:
    @pytest.mark.asyncio
    async def test_unlock_turns_the_entity_on(self):
        coord = _coord(["switch.tv"])
        record = await coord.async_start_unlock(
            _reward(unlock_entity="switch.tv", unlock_minutes=30), Child(name="Kid", id="k1")
        )
        assert record["entity_id"] == "switch.tv"
        coord.hass.services.async_call.assert_awaited_with(
            "homeassistant", "turn_on", {"entity_id": "switch.tv"}, blocking=False
        )

    @pytest.mark.asyncio
    async def test_reward_without_unlock_does_nothing(self):
        coord = _coord(["switch.tv"])
        assert await coord.async_start_unlock(_reward(), Child(name="Kid", id="k1")) is None
        coord.hass.services.async_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_entity_removed_from_allowlist_is_refused_at_fire_time(self):
        """The allowlist can change after a reward was created — re-check."""
        coord = _coord(["switch.something_else"])
        result = await coord.async_start_unlock(
            _reward(unlock_entity="switch.tv", unlock_minutes=30), Child(name="Kid", id="k1")
        )
        assert result is None
        coord.hass.services.async_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unlock_is_persisted_so_a_restart_can_revert_it(self):
        coord = _coord(["switch.tv"])
        await coord.async_start_unlock(
            _reward(unlock_entity="switch.tv", unlock_minutes=30), Child(name="Kid", id="k1")
        )
        assert len(coord.active_unlocks()) == 1
        coord.storage.async_save.assert_awaited()

    @pytest.mark.asyncio
    async def test_zero_minutes_does_not_schedule_a_revert(self):
        coord = _coord(["switch.tv"])
        record = await coord.async_start_unlock(
            _reward(unlock_entity="switch.tv", unlock_minutes=0), Child(name="Kid", id="k1")
        )
        assert record["revert_at"] == ""
        assert coord.active_unlocks() == []

    @pytest.mark.asyncio
    async def test_starting_fires_an_event(self):
        coord = _coord(["switch.tv"])
        await coord.async_start_unlock(
            _reward(unlock_entity="switch.tv", unlock_minutes=30), Child(name="Kid", id="k1")
        )
        event, payload = coord.hass.bus.async_fire.call_args[0]
        assert event == "taskmate_unlock_started"
        assert payload["child_name"] == "Kid"


class TestReverting:
    @pytest.mark.asyncio
    async def test_revert_turns_the_entity_off_and_clears_the_record(self):
        coord = _coord(["switch.tv"])
        record = await coord.async_start_unlock(
            _reward(unlock_entity="switch.tv", unlock_minutes=30), Child(name="Kid", id="k1")
        )
        await coord.async_revert_unlock(record)
        coord.hass.services.async_call.assert_awaited_with(
            "homeassistant", "turn_off", {"entity_id": "switch.tv"}, blocking=False
        )
        assert coord.active_unlocks() == []

    @pytest.mark.asyncio
    async def test_revert_fires_an_event(self):
        coord = _coord(["switch.tv"])
        record = await coord.async_start_unlock(
            _reward(unlock_entity="switch.tv", unlock_minutes=30), Child(name="Kid", id="k1")
        )
        coord.hass.bus.async_fire.reset_mock()
        await coord.async_revert_unlock(record)
        assert coord.hass.bus.async_fire.call_args[0][0] == "taskmate_unlock_ended"


class TestSurvivingARestart:
    """The one genuinely bad failure mode: a restart leaving the TV on forever."""

    @pytest.mark.asyncio
    async def test_expired_unlock_is_reverted_on_startup(self):
        past = (dt_util.now() - timedelta(minutes=5)).isoformat()
        coord = _coord(["switch.tv"], [{"entity_id": "switch.tv", "revert_at": past}])
        assert await coord.async_resume_unlocks() == 1
        coord.hass.services.async_call.assert_awaited_with(
            "homeassistant", "turn_off", {"entity_id": "switch.tv"}, blocking=False
        )
        assert coord.active_unlocks() == []

    @pytest.mark.asyncio
    async def test_still_running_unlock_is_kept_and_rearmed(self):
        future = (dt_util.now() + timedelta(minutes=25)).isoformat()
        coord = _coord(["switch.tv"], [{"entity_id": "switch.tv", "revert_at": future}])
        assert await coord.async_resume_unlocks() == 0
        assert len(coord.active_unlocks()) == 1
        assert len(coord._unlock_timers) == 1
        coord.hass.services.async_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unparseable_revert_time_is_turned_off_not_left_on(self):
        coord = _coord(["switch.tv"], [{"entity_id": "switch.tv", "revert_at": "whenever"}])
        assert await coord.async_resume_unlocks() == 1
        coord.hass.services.async_call.assert_awaited_with(
            "homeassistant", "turn_off", {"entity_id": "switch.tv"}, blocking=False
        )

    @pytest.mark.asyncio
    async def test_resume_reverts_even_if_no_longer_allowlisted(self):
        """Turning something OFF is always safe — never gate the revert."""
        past = (dt_util.now() - timedelta(minutes=5)).isoformat()
        coord = _coord([], [{"entity_id": "switch.tv", "revert_at": past}])
        assert await coord.async_resume_unlocks() == 1
        coord.hass.services.async_call.assert_awaited_with(
            "homeassistant", "turn_off", {"entity_id": "switch.tv"}, blocking=False
        )

    @pytest.mark.asyncio
    async def test_nothing_active_is_a_no_op(self):
        coord = _coord(["switch.tv"], [])
        assert await coord.async_resume_unlocks() == 0
        coord.hass.services.async_call.assert_not_awaited()

    def test_cancelling_timers_is_safe_when_one_raises(self):
        coord = _coord(["switch.tv"])
        bad = MagicMock(side_effect=RuntimeError("already gone"))
        good = MagicMock()
        coord._unlock_timers = [bad, good]
        coord.cancel_unlock_timers()  # must not raise during teardown
        good.assert_called_once()
        assert coord._unlock_timers == []


class TestModel:
    def test_unlock_fields_round_trip(self):
        reward = _reward(unlock_entity="switch.tv", unlock_minutes=45)
        restored = Reward.from_dict(reward.to_dict())
        assert restored.unlock_entity == "switch.tv"
        assert restored.unlock_minutes == 45

    def test_legacy_reward_without_unlock_fields(self):
        restored = Reward.from_dict({"name": "Old reward", "cost": 10})
        assert restored.unlock_entity == ""
        assert restored.unlock_minutes == 0
