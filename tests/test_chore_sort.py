"""Family-wide chore order (#1231): presets, the published order, sort-once.

Drives the real coordinator against real storage (the test_watch harness).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate.chore_sort import (
    CHORE_SORT_MODES,
    chore_sort_mode,
    effective_chore_order,
    sorted_chore_ids,
)
from custom_components.taskmate.models import Chore, ChoreTime
from custom_components.taskmate.sensor import ChildStatsSensor, TaskMateOverallStatsSensor
from custom_components.taskmate.watch import next_chore_for_child
from custom_components.taskmate.websocket import (
    _SUBKEY_SETTINGS,
    _UPDATE_SETTINGS_SCHEMA,
    WS_SORT_CHORE_ORDERS,
    WS_UPDATE_SETTINGS,
    _build_state_snapshot,
)

from .test_watch import _make_system

PERIODS = [
    {"id": "morning", "start": "06:00"},
    {"id": "afternoon", "start": "12:00"},
    {"id": "evening", "start": "17:00"},
]


def _c(cid, name, cat="anytime", times=None):
    return Chore(id=cid, name=name, time_category=cat, times=times or [])


CHORES = [
    _c("e", "Wash up", "evening"),
    _c("m", "brush teeth", "morning"),
    _c("a", "Read", "anytime"),
    _c("n", "Apples", "afternoon"),
]


# ── pure sort ────────────────────────────────────────────────────────────


def test_added_keeps_storage_order():
    assert sorted_chore_ids("added", CHORES, ["n", "a"]) == ["e", "m", "a", "n"]


def test_name_is_case_insensitive():
    assert sorted_chore_ids("name", CHORES) == ["n", "m", "a", "e"]


def test_time_puts_anytime_first_then_periods_by_start():
    assert sorted_chore_ids("time", CHORES, [], PERIODS) == ["a", "m", "n", "e"]


def test_time_ties_keep_the_manual_order():
    chores = [_c("m1", "One", "morning"), _c("m2", "Two", "morning"), _c("e", "Eve", "evening")]
    assert sorted_chore_ids("time", chores, ["e", "m2", "m1"], PERIODS) == ["m2", "m1", "e"]


def test_time_uses_the_earliest_set_time():
    chores = [
        _c("n", "Lunch box", "afternoon"),
        _c("hands", "Wash hands", "anytime", [ChoreTime(start="12:30"), ChoreTime(start="07:15")]),
        _c("m", "Bed", "morning"),
    ]
    # Set times sort by their first time (07:15), between morning and afternoon.
    assert sorted_chore_ids("time", chores, [], PERIODS) == ["m", "hands", "n"]


def test_time_unknown_period_sorts_last():
    chores = [_c("x", "Gone", "brunch"), _c("e", "Eve", "evening")]
    assert sorted_chore_ids("time", chores, [], PERIODS) == ["e", "x"]


def test_manual_returns_the_stored_list():
    assert sorted_chore_ids("manual", CHORES, ["n", "e"]) == ["n", "e"]


def test_unknown_stored_mode_reads_as_manual():
    storage = MagicMock()
    storage.get_setting = MagicMock(return_value="sideways")
    assert chore_sort_mode(storage) == "manual"


# ── settings plumbing ────────────────────────────────────────────────────


def test_setting_is_accepted_and_routed():
    schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA)
    for mode in CHORE_SORT_MODES:
        assert schema({"type": WS_UPDATE_SETTINGS, "chore_sort": mode})["chore_sort"] == mode
    with pytest.raises(vol.Invalid):
        schema({"type": WS_UPDATE_SETTINGS, "chore_sort": "random"})
    assert "chore_sort" in _SUBKEY_SETTINGS


def test_ws_sort_command_registered():
    from custom_components.taskmate import websocket as ws

    assert WS_SORT_CHORE_ORDERS == "taskmate/sort_chore_orders"
    assert ws._ws_sort_chore_orders in ws._COMMANDS


# ── real coordinator ─────────────────────────────────────────────────────


async def _family():
    coord, storage = await _make_system()
    a = await coord.async_add_child("Ann")
    b = await coord.async_add_child("Ben")
    eve = await coord.async_add_chore("Wash up", points=1, time_category="evening")
    mor = await coord.async_add_chore("Brush teeth", points=1, time_category="morning")
    any_ = await coord.async_add_chore("Read", points=1, time_category="anytime")
    return coord, storage, a, b, eve, mor, any_


async def test_manual_mode_publishes_the_childs_own_order():
    coord, storage, a, _b, eve, mor, any_ = await _family()
    await coord.async_set_chore_order(a.id, [any_.id, eve.id])
    assert effective_chore_order(coord, coord.get_child(a.id)) == [any_.id, eve.id]


async def test_time_mode_publishes_sorted_order_and_keeps_manual_underneath():
    coord, storage, a, _b, eve, mor, any_ = await _family()
    await coord.async_set_chore_order(a.id, [eve.id, mor.id])
    storage.set_setting("chore_sort", "time")
    assert effective_chore_order(coord, coord.get_child(a.id)) == [any_.id, mor.id, eve.id]
    # The child's manual order is untouched, for when the setting goes back.
    assert coord.get_child(a.id).chore_order == [eve.id, mor.id]
    # A chore added later lands in its place without anyone reordering it.
    aft = await coord.async_add_chore("Lunch box", points=1, time_category="afternoon")
    assert effective_chore_order(coord, coord.get_child(a.id)) == [any_.id, mor.id, aft.id, eve.id]


async def test_sensors_publish_the_effective_order():
    coord, storage, a, _b, eve, mor, any_ = await _family()
    storage.set_setting("chore_sort", "name")
    coord.data = {"children": storage.get_children(), "chores": storage.get_chores(), "settings": {}}
    attrs = ChildStatsSensor(coord, MagicMock(), coord.get_child(a.id)).extra_state_attributes
    assert attrs["chore_order"] == [mor.id, any_.id, eve.id]


async def test_overview_reports_the_mode():
    from .test_sensor_attributes import _stress_coordinator

    coord = _stress_coordinator()
    attrs = TaskMateOverallStatsSensor(coord, MagicMock())._build_attributes()
    assert attrs["chore_sort"] == "manual"


async def test_snapshot_defaults_to_manual():
    coord, storage, *_ = await _family()
    assert _build_state_snapshot(coord)["settings"]["chore_sort"] == "manual"
    storage.set_setting("chore_sort", "time")
    assert _build_state_snapshot(coord)["settings"]["chore_sort"] == "time"


async def test_sort_once_writes_every_child_and_saves_once():
    coord, storage, a, b, eve, mor, any_ = await _family()
    coord.async_refresh.reset_mock()
    count = await coord.async_sort_chore_orders("time")
    assert count == 2
    for child in (a, b):
        assert coord.get_child(child.id).chore_order == [any_.id, mor.id, eve.id]
    # One refresh for the whole batch, never one per child.
    assert coord.async_refresh.await_count == 1
    # The setting stays manual, so the reorder card can fine-tune.
    assert chore_sort_mode(storage) == "manual"


async def test_sort_once_can_target_some_children():
    coord, storage, a, b, eve, mor, any_ = await _family()
    await coord.async_set_chore_order(b.id, [eve.id])
    assert await coord.async_sort_chore_orders("name", [a.id]) == 1
    assert coord.get_child(a.id).chore_order == [mor.id, any_.id, eve.id]
    assert coord.get_child(b.id).chore_order == [eve.id]


async def test_sort_once_rejects_manual():
    coord, *_ = await _family()
    with pytest.raises(ValueError):
        await coord.async_sort_chore_orders("manual")


async def test_watch_next_chore_follows_the_family_sort():
    coord, storage, a, _b, eve, mor, any_ = await _family()
    storage.set_setting("chore_sort", "name")
    due = [eve, any_]
    coord.get_due_chores_for_child = lambda _cid: list(due)
    assert next_chore_for_child(coord, a.id).id == any_.id
    storage.set_setting("chore_sort", "added")
    assert next_chore_for_child(coord, a.id).id == eve.id
