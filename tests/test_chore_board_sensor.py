"""The chore board sensor behind the chore board card (#1017).

Drives the real coordinator against real storage, the same harness as the
watch sensor tests: the board must be exactly what the panel's Today page
draws, and roll over at midnight even when nothing else changed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.sensor import TaskMateChoreBoardSensor
from tests.test_watch import _bump, _chore, _make_system


def _sensor(coord):
    return TaskMateChoreBoardSensor(coord, MagicMock(entry_id="e1"))


def test_identity_and_unrecorded_board():
    async def scenario():
        coord, _ = await _make_system()
        sensor = _sensor(coord)
        assert sensor._attr_unique_id == "e1_chore_board"
        # "TaskMate Chore Board" -> sensor.taskmate_chore_board, the id the
        # attribute resolver merges.
        assert sensor._attr_name == "TaskMate Chore Board"
        assert "chore_board" in sensor._unrecorded_attributes

    asyncio.run(scenario())


def test_state_counts_what_is_still_to_do_across_children():
    async def scenario():
        coord, _ = await _make_system()
        a = await coord.async_add_child("A")
        b = await coord.async_add_child("B")
        dishes = await _chore(coord, a, "Dishes")
        await _chore(coord, a, "Bins")
        await _chore(coord, b, "Bed", approval=True)
        sensor = _sensor(coord)
        assert sensor.native_value == 3

        await coord.async_complete_chore(dishes.id, a.id)
        _bump(coord)
        assert sensor.native_value == 2

    asyncio.run(scenario())


def test_attribute_is_the_panels_today_state():
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        bed = await _chore(coord, kid, "Bed", approval=True)
        await _chore(coord, kid, "Teeth")
        await coord.async_complete_chore(bed.id, kid.id)
        _bump(coord)

        board = _sensor(coord).extra_state_attributes["chore_board"]
        assert board == coord.daily_progress_state()
        statuses = {c["chore_id"]: c["status"] for c in board["board"]["children"][0]["chores"]}
        assert statuses[bed.id] == "pending"
        assert len(board["history"][kid.id]) == 7
        assert board["history"][kid.id][-1] == {"date": board["board"]["date"], "due": 2, "done": 1}

    asyncio.run(scenario())


def test_same_snapshot_is_cached_and_a_new_day_rebuilds(monkeypatch):
    async def scenario():
        coord, _ = await _make_system()
        kid = await coord.async_add_child("Kid")
        await _chore(coord, kid, "Teeth")
        sensor = _sensor(coord)

        calls = []
        real = coord.get_today_board

        def counting():
            calls.append(1)
            return real()

        coord.get_today_board = counting
        first = sensor.extra_state_attributes["chore_board"]
        assert sensor.extra_state_attributes["chore_board"] is first
        assert sensor.native_value == 1
        built = len(calls)
        # The board is built once and shared with the history, not twice.
        assert built == 1

        tomorrow = datetime.now().astimezone() + timedelta(days=1)
        monkeypatch.setattr(sensor_module.dt_util, "now", lambda *a, **k: tomorrow)
        sensor.extra_state_attributes  # noqa: B018 - property read rebuilds
        assert len(calls) > built

    asyncio.run(scenario())


def test_daily_progress_state_uses_a_board_it_is_given():
    async def scenario():
        coord, _ = await _make_system()
        await coord.async_add_child("Kid")
        board = coord.get_today_board()
        coord.get_today_board = MagicMock(side_effect=AssertionError("rebuilt"))
        assert coord.daily_progress_state(board=board)["board"] is board

    asyncio.run(scenario())
