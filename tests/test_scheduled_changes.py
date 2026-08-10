"""Scheduled chore config changes (#675).

"From 1 September this chore is worth 20 points." Queued against a chore with a
date, applied at midnight, and caught up at startup if Home Assistant was off
on the day it came due.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.util import dt as dt_util

from custom_components.taskmate.coord_scheduled import coerce_scheduled_value
from custom_components.taskmate.models import Chore, ScheduledChange

from .test_coordinator_logic import _make_coord


def _day(offset):
    return (dt_util.as_local(dt_util.now()).date() + timedelta(days=offset)).isoformat()


def _coord(chores=None, changes=None):
    coord = _make_coord()
    store = {c.id: c for c in (chores or [])}
    queued = list(changes or [])

    coord.storage.get_chore = MagicMock(side_effect=lambda cid: store.get(cid))
    coord.storage.get_chores = MagicMock(return_value=list(store.values()))
    coord.storage.update_chore = MagicMock(side_effect=lambda c: store.__setitem__(c.id, c))
    coord.storage.get_scheduled_changes = MagicMock(side_effect=lambda: list(queued))
    coord.storage.get_scheduled_change = MagicMock(
        side_effect=lambda cid: next((c for c in queued if c.id == cid), None)
    )
    coord.storage.add_scheduled_change = MagicMock(side_effect=queued.append)

    def _update(change):
        for i, c in enumerate(queued):
            if c.id == change.id:
                queued[i] = change
                return
        queued.append(change)

    coord.storage.update_scheduled_change = MagicMock(side_effect=_update)
    coord.storage.remove_scheduled_change = MagicMock(
        side_effect=lambda cid: queued.__setitem__(slice(None), [c for c in queued if c.id != cid])
    )

    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord.hass.bus.async_fire = MagicMock()
    coord._queued = queued
    coord._chores = store
    return coord


class TestCoerceValue:
    def test_unknown_field_is_rejected(self):
        """A queued change must not be able to rewrite runtime state."""
        with pytest.raises(ValueError, match="cannot be changed"):
            coerce_scheduled_value("assignment_current_child_id", "kid1")

    @pytest.mark.parametrize(("raw", "expected"), [(True, True), ("true", True), ("false", False)])
    def test_bool_coercion(self, raw, expected):
        assert coerce_scheduled_value("enabled", raw) is expected

    def test_bool_rejects_nonsense(self):
        with pytest.raises(ValueError, match="true or false"):
            coerce_scheduled_value("enabled", "maybe")

    def test_int_accepts_numeric_string(self):
        """Websocket JSON can deliver a number as a string."""
        assert coerce_scheduled_value("points", "20") == 20

    def test_int_rejects_text(self):
        with pytest.raises(ValueError, match="whole number"):
            coerce_scheduled_value("points", "lots")

    def test_int_rejects_negative(self):
        with pytest.raises(ValueError, match="negative"):
            coerce_scheduled_value("points", -5)

    def test_list_coerced_to_strings(self):
        assert coerce_scheduled_value("assigned_to", ["a", 2]) == ["a", "2"]

    def test_list_rejects_scalar(self):
        with pytest.raises(ValueError, match="expects a list"):
            coerce_scheduled_value("assigned_to", "kid1")

    def test_text_field(self):
        assert coerce_scheduled_value("description", "Do it well") == "Do it well"


class TestQueueing:
    @pytest.mark.asyncio
    async def test_queue_a_change(self):
        chore = Chore(name="Mow")
        coord = _coord([chore])
        change = await coord.async_add_scheduled_change(chore.id, _day(30), {"points": "20"})
        assert change.changes == {"points": 20}
        assert change.applied is False
        coord.storage.async_save.assert_awaited()

    @pytest.mark.asyncio
    async def test_unknown_chore_is_rejected(self):
        coord = _coord([])
        with pytest.raises(ValueError, match="not found"):
            await coord.async_add_scheduled_change("nope", _day(30), {"points": 20})

    @pytest.mark.asyncio
    async def test_past_date_is_rejected(self):
        chore = Chore(name="Mow")
        coord = _coord([chore])
        with pytest.raises(ValueError, match="future date"):
            await coord.async_add_scheduled_change(chore.id, _day(-1), {"points": 20})

    @pytest.mark.asyncio
    async def test_today_is_rejected(self):
        """Today would fire at the next midnight — a day later than it reads."""
        chore = Chore(name="Mow")
        coord = _coord([chore])
        with pytest.raises(ValueError, match="future date"):
            await coord.async_add_scheduled_change(chore.id, _day(0), {"points": 20})

    @pytest.mark.asyncio
    async def test_bad_date_is_rejected(self):
        chore = Chore(name="Mow")
        coord = _coord([chore])
        with pytest.raises(ValueError, match="ISO date"):
            await coord.async_add_scheduled_change(chore.id, "next tuesday", {"points": 20})

    @pytest.mark.asyncio
    async def test_empty_change_is_rejected(self):
        chore = Chore(name="Mow")
        coord = _coord([chore])
        with pytest.raises(ValueError, match="at least one field"):
            await coord.async_add_scheduled_change(chore.id, _day(30), {})

    @pytest.mark.asyncio
    async def test_bad_value_is_rejected_at_queue_time(self):
        """Fail in front of the parent, not silently at midnight weeks later."""
        chore = Chore(name="Mow")
        coord = _coord([chore])
        with pytest.raises(ValueError, match="whole number"):
            await coord.async_add_scheduled_change(chore.id, _day(30), {"points": "loads"})

    @pytest.mark.asyncio
    async def test_remove_a_change(self):
        chore = Chore(name="Mow")
        change = ScheduledChange(chore_id=chore.id, apply_on=_day(30), changes={"points": 20})
        coord = _coord([chore], [change])
        await coord.async_remove_scheduled_change(change.id)
        assert coord._queued == []

    @pytest.mark.asyncio
    async def test_remove_unknown_change(self):
        coord = _coord([])
        with pytest.raises(ValueError, match="not found"):
            await coord.async_remove_scheduled_change("nope")


class TestApplying:
    @pytest.mark.asyncio
    async def test_future_change_is_not_applied(self):
        chore = Chore(name="Mow", points=10)
        change = ScheduledChange(chore_id=chore.id, apply_on=_day(5), changes={"points": 20})
        coord = _coord([chore], [change])
        assert await coord.async_apply_due_scheduled_changes() == 0
        assert chore.points == 10

    @pytest.mark.asyncio
    async def test_due_change_is_applied(self):
        chore = Chore(name="Mow", points=10)
        change = ScheduledChange(chore_id=chore.id, apply_on=_day(0), changes={"points": 20})
        coord = _coord([chore], [change])
        assert await coord.async_apply_due_scheduled_changes() == 1
        assert chore.points == 20
        assert coord._queued[0].applied is True
        assert coord._queued[0].applied_at

    @pytest.mark.asyncio
    async def test_overdue_change_still_applies(self):
        """HA may have been off on the day — the parent still expects it."""
        chore = Chore(name="Mow", points=10)
        change = ScheduledChange(chore_id=chore.id, apply_on=_day(-9), changes={"points": 20})
        coord = _coord([chore], [change])
        assert await coord.async_apply_due_scheduled_changes() == 1
        assert chore.points == 20

    @pytest.mark.asyncio
    async def test_applied_change_is_not_reapplied(self):
        chore = Chore(name="Mow", points=99)
        change = ScheduledChange(chore_id=chore.id, apply_on=_day(-1), changes={"points": 20}, applied=True)
        coord = _coord([chore], [change])
        assert await coord.async_apply_due_scheduled_changes() == 0
        assert chore.points == 99

    @pytest.mark.asyncio
    async def test_multiple_fields_in_one_change(self):
        chore = Chore(name="Mow", points=10, enabled=True, assigned_to=["a"])
        change = ScheduledChange(
            chore_id=chore.id, apply_on=_day(0), changes={"points": 20, "enabled": False, "assigned_to": ["b"]}
        )
        coord = _coord([chore], [change])
        await coord.async_apply_due_scheduled_changes()
        assert (chore.points, chore.enabled, chore.assigned_to) == (20, False, ["b"])

    @pytest.mark.asyncio
    async def test_deleted_chore_change_is_retired_not_retried(self):
        """Otherwise it would be reconsidered at every midnight, forever."""
        change = ScheduledChange(chore_id="gone", apply_on=_day(0), changes={"points": 20})
        coord = _coord([], [change])
        assert await coord.async_apply_due_scheduled_changes() == 1
        assert coord._queued[0].applied is True
        assert "chore deleted" in coord._queued[0].note

    @pytest.mark.asyncio
    async def test_unparseable_date_is_skipped_not_fatal(self):
        chore = Chore(name="Mow", points=10)
        change = ScheduledChange(chore_id=chore.id, apply_on="whenever", changes={"points": 20})
        coord = _coord([chore], [change])
        assert await coord.async_apply_due_scheduled_changes() == 0
        assert chore.points == 10

    @pytest.mark.asyncio
    async def test_unknown_field_is_skipped_at_apply_time(self):
        """Defence in depth: storage could have been hand-edited since queueing."""
        chore = Chore(name="Mow", points=10)
        change = ScheduledChange(chore_id=chore.id, apply_on=_day(0), changes={"points": 20, "skip_date": "2026-01-01"})
        coord = _coord([chore], [change])
        await coord.async_apply_due_scheduled_changes()
        assert chore.points == 20
        assert chore.skip_date == ""

    @pytest.mark.asyncio
    async def test_applying_fires_an_event(self):
        chore = Chore(name="Mow", points=10)
        change = ScheduledChange(chore_id=chore.id, apply_on=_day(0), changes={"points": 20})
        coord = _coord([chore], [change])
        await coord.async_apply_due_scheduled_changes()
        event, payload = coord.hass.bus.async_fire.call_args[0]
        assert event == "taskmate_scheduled_change_applied"
        assert payload["chore_name"] == "Mow"
        assert payload["changes"] == {"points": 20}

    @pytest.mark.asyncio
    async def test_no_refresh_when_asked_not_to(self):
        """Startup catch-up runs before the first refresh."""
        chore = Chore(name="Mow", points=10)
        change = ScheduledChange(chore_id=chore.id, apply_on=_day(0), changes={"points": 20})
        coord = _coord([chore], [change])
        await coord.async_apply_due_scheduled_changes(refresh=False)
        coord.async_refresh.assert_not_awaited()
        coord.storage.async_save.assert_awaited()

    @pytest.mark.asyncio
    async def test_nothing_due_does_not_save(self):
        chore = Chore(name="Mow", points=10)
        coord = _coord([chore], [])
        await coord.async_apply_due_scheduled_changes()
        coord.storage.async_save.assert_not_awaited()


class TestListing:
    def test_sorted_soonest_first(self):
        chore = Chore(name="Mow")
        late = ScheduledChange(chore_id=chore.id, apply_on=_day(30), changes={"points": 30})
        soon = ScheduledChange(chore_id=chore.id, apply_on=_day(2), changes={"points": 20})
        coord = _coord([chore], [late, soon])
        assert [c.id for c in coord.get_scheduled_changes()] == [soon.id, late.id]

    def test_filtered_by_chore(self):
        a, b = Chore(name="A"), Chore(name="B")
        ca = ScheduledChange(chore_id=a.id, apply_on=_day(2), changes={"points": 1})
        cb = ScheduledChange(chore_id=b.id, apply_on=_day(3), changes={"points": 2})
        coord = _coord([a, b], [ca, cb])
        assert [c.id for c in coord.get_scheduled_changes(a.id)] == [ca.id]


class TestModel:
    def test_round_trip(self):
        change = ScheduledChange(chore_id="c1", apply_on="2026-09-01", changes={"points": 20}, note="new school year")
        restored = ScheduledChange.from_dict(change.to_dict())
        assert restored.chore_id == "c1"
        assert restored.apply_on == "2026-09-01"
        assert restored.changes == {"points": 20}
        assert restored.note == "new school year"
        assert restored.applied is False

    def test_from_sparse_dict(self):
        restored = ScheduledChange.from_dict({"chore_id": "c1", "apply_on": "2026-09-01"})
        assert restored.changes == {}
        assert restored.created_at  # always stamped
