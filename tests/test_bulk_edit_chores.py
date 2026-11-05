"""Edit selected chores (#1174): change only the chosen settings on many chores.

Drives the real coordinator against real storage (the test_watch harness).
"""

from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.websocket import _BULK_EDIT_CHANGES_SCHEMA, WS_BULK_EDIT_CHORES

from .test_watch import _make_system


async def _family():
    coord, storage = await _make_system()
    a = await coord.async_add_child("Ann")
    b = await coord.async_add_child("Ben")
    one = await coord.async_add_chore(
        "Make bed", points=2, assigned_to=[a.id], requires_approval=True, time_category="morning"
    )
    two = await coord.async_add_chore(
        "Feed cat", points=5, assigned_to=[b.id], requires_approval=False, time_category="evening"
    )
    return coord, storage, a, b, one, two


async def test_only_the_chosen_fields_change():
    coord, storage, a, b, one, two = await _family()
    res = await coord.async_bulk_edit_chores([one.id, two.id], {"points": 7, "requires_approval": False})
    assert res == {"count": 2, "skipped": []}
    for cid, cat, who in ((one.id, "morning", [a.id]), (two.id, "evening", [b.id])):
        c = storage.get_chore(cid)
        assert c.points == 7
        assert c.requires_approval is False
        # Untouched: time of day, children, name.
        assert c.time_category == cat
        assert c.assigned_to == who


async def test_children_schedule_and_period():
    coord, storage, a, b, one, two = await _family()
    await coord.async_bulk_edit_chores(
        [one.id, two.id],
        {
            "assigned_to": [a.id, b.id],
            "schedule_mode": "specific_days",
            "due_days": ["monday", "friday"],
            "time_category": "afternoon",
        },
    )
    for cid in (one.id, two.id):
        c = storage.get_chore(cid)
        assert c.assigned_to == [a.id, b.id]
        assert c.due_days == ["monday", "friday"]
        assert c.time_category == "afternoon"
    await coord.async_bulk_edit_chores([one.id], {"schedule_mode": "recurring", "recurrence": "every_2_weeks"})
    c = storage.get_chore(one.id)
    assert (c.schedule_mode, c.recurrence) == ("recurring", "every_2_weeks")


async def test_one_save_and_one_refresh_for_the_batch():
    coord, storage, a, b, one, two = await _family()
    coord.async_refresh.reset_mock()
    await coord.async_bulk_edit_chores([one.id, two.id], {"points": 1})
    assert coord.async_refresh.await_count == 1


async def test_a_chore_that_refuses_is_skipped_and_named():
    coord, storage, a, b, one, two = await _family()
    real = coord.async_update_chore

    async def picky(chore, *, refresh=True):
        if chore.id == two.id:
            raise ValueError("no")
        return await real(chore, refresh=refresh)

    coord.async_update_chore = picky
    res = await coord.async_bulk_edit_chores([one.id, two.id], {"points": 9})
    assert res == {"count": 1, "skipped": ["Feed cat"]}
    assert storage.get_chore(one.id).points == 9
    assert storage.get_chore(two.id).points == 5


async def test_unknown_child_period_or_field_is_refused():
    coord, storage, a, b, one, two = await _family()
    with pytest.raises(ValueError):
        await coord.async_bulk_edit_chores([one.id], {"assigned_to": ["nobody"]})
    with pytest.raises(ValueError):
        await coord.async_bulk_edit_chores([one.id], {"time_category": "brunch"})
    with pytest.raises(ValueError):
        await coord.async_bulk_edit_chores([one.id], {"name": "x"})
    assert storage.get_chore(one.id).points == 2


async def test_no_changes_is_a_no_op():
    coord, storage, a, b, one, two = await _family()
    assert await coord.async_bulk_edit_chores([one.id], {}) == {"count": 0, "skipped": []}


def test_schema_limits_what_can_be_sent():
    assert _BULK_EDIT_CHANGES_SCHEMA({"points": 3, "due_days": ["monday"]}) == {"points": 3, "due_days": ["monday"]}
    for bad in ({"schedule_mode": "one_shot"}, {"due_days": ["someday"]}, {"points": -1}, {"name": "x"}):
        with pytest.raises(vol.Invalid):
            _BULK_EDIT_CHANGES_SCHEMA(bad)


def test_command_registered():
    assert WS_BULK_EDIT_CHORES == "taskmate/bulk_edit_chores"
    assert ws._ws_bulk_edit_chores in ws._COMMANDS
