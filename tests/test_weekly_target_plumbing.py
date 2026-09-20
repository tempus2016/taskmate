"""Weekly target: the surfaces around the coordinator (#883).

The cap itself is covered in test_weekly_target.py. What breaks silently is
everything either side of it — a field the WebSocket schema drops never
reaches the chore, a field missing from the sensor slice is invisible to every
card, and the two day-shaped systems (mandatory misses, perfect week) will
happily demand a weekly chore daily unless they're told not to.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

UTC = timezone.utc
NOW = dt.datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)  # Wednesday
MONDAY = dt.datetime(2026, 4, 20, 9, 0, 0, tzinfo=UTC)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── WebSocket surface ────────────────────────────────────────────────────────


def test_weekly_target_is_editable_over_the_websocket():
    # _CHORE_EDITABLE_FIELDS gates what actually reaches the Chore in both add
    # and update; a field that passes the schema but is missing here is
    # silently dropped.
    from custom_components.taskmate.websocket import _CHORE_EDITABLE_FIELDS

    assert "weekly_target" in _CHORE_EDITABLE_FIELDS


def test_weekly_target_accepts_a_positive_count():
    from custom_components.taskmate.websocket import _chore_payload_schema

    # A default (PREVENT_EXTRA) schema: an undeclared key is rejected, so this
    # only passes once the field is actually declared.
    schema = vol.Schema(_chore_payload_schema(require_name=False))
    assert schema({"weekly_target": 3})["weekly_target"] == 3


def test_weekly_target_accepts_zero_to_turn_it_off():
    from custom_components.taskmate.websocket import _chore_payload_schema

    schema = vol.Schema(_chore_payload_schema(require_name=False))
    assert schema({"weekly_target": 0})["weekly_target"] == 0


def test_weekly_target_rejects_a_negative_count():
    from custom_components.taskmate.websocket import _chore_payload_schema

    schema = vol.Schema(_chore_payload_schema(require_name=False))
    with pytest.raises(vol.Invalid):
        schema({"weekly_target": -1})


# ── sensor slices ────────────────────────────────────────────────────────────


def _sensor_coord(chores, children, completions):
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_completions = MagicMock(return_value=completions)
    coord.effective_chore_points = MagicMock(side_effect=lambda c: c.points)
    return coord


def test_chores_slice_emits_the_weekly_target_when_set():
    # Cards read chores from _build_chores_list; a field absent there is
    # invisible to every card no matter how good the rendering is.
    chore = Chore(name="Cello", id="a", weekly_target=3)
    coord = _sensor_coord([chore], [], [])
    record = sensor_module._build_chores_list(coord, {"chores": [chore]})[0]
    assert record["weekly_target"] == 3


def test_chores_slice_omits_the_weekly_target_when_unset():
    # Optional fields stay out of the record unless used — the slice has a
    # 16 KB ceiling and most chores will never have a weekly target.
    chore = Chore(name="Dishes", id="a")
    coord = _sensor_coord([chore], [], [])
    record = sensor_module._build_chores_list(coord, {"chores": [chore]})[0]
    assert "weekly_target" not in record


def _summary_coord(chores, children, completions):
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_completions = MagicMock(return_value=completions)
    coord.level_info = MagicMock(return_value={"level": 1, "progress": 0, "target": 100})
    coord.roulette_enabled = MagicMock(return_value=False)
    coord.quest_progress_for_child = MagicMock(return_value=[])
    coord.challenge_progress_for_child = MagicMock(return_value=[])
    coord.avatar_options_for_child = MagicMock(return_value=[])
    coord._is_child_on_vacation = MagicMock(return_value=False)
    common = {
        "children": children,
        "chores": chores,
        "pending_points_by_child": {},
        "committed_points_by_child": {},
        "total_allocated_by_child": {},
        "season_points": {},
    }
    return coord, common


def test_child_summary_carries_weekly_progress():
    chore = Chore(name="Cello", id="a", weekly_target=3)
    child = Child(name="Mia", id="c1")
    comps = [
        ChoreCompletion(chore_id="a", child_id="c1", completed_at=MONDAY),
        ChoreCompletion(chore_id="a", child_id="c1", completed_at=NOW),
    ]
    coord, common = _summary_coord([chore], [child], comps)
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        summary = sensor_module._build_children_summary(coord, common)
    assert summary[0]["weekly_chore_progress"] == {"a": 2}


def test_child_summary_omits_weekly_progress_when_no_chore_uses_it():
    chore = Chore(name="Dishes", id="a")
    child = Child(name="Mia", id="c1")
    coord, common = _summary_coord([chore], [child], [])
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        summary = sensor_module._build_children_summary(coord, common)
    assert "weekly_chore_progress" not in summary[0]


# ── mandatory misses ─────────────────────────────────────────────────────────


def _mandatory_coord(chores, children, completions):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_chores = MagicMock(return_value=chores)
    s.get_children = MagicMock(return_value=children)
    s.get_completions = MagicMock(return_value=completions)
    s.get_mandatory_misses = MagicMock(return_value=[])
    s._added = []
    s.add_mandatory_miss = MagicMock(side_effect=lambda m: s._added.append(m))
    s.async_save = AsyncMock()
    c.storage = s
    c.hass = MagicMock()
    c.hass.bus.async_fire = MagicMock()
    c.async_refresh = AsyncMock()
    c.mandatory_postpone = {}
    c._is_chore_scheduled_for_date = MagicMock(return_value=True)
    return c


def test_no_mandatory_miss_once_the_weekly_target_is_met():
    """3x a week, done 3x by Wednesday — Thursday evening owes nothing."""
    chore = Chore(
        name="Cello",
        mandatory=True,
        weekly_target=2,
        time_category="afternoon",
        assigned_to=["k1"],
        id="c1",
    )
    comps = [
        ChoreCompletion(chore_id="c1", child_id="k1", completed_at=MONDAY),
        ChoreCompletion(chore_id="c1", child_id="k1", completed_at=dt.datetime(2026, 4, 21, 9, tzinfo=UTC)),
    ]
    coord = _mandatory_coord([chore], [Child(name="Kid", id="k1")], comps)
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        assert run(coord.async_detect_mandatory_misses("afternoon", NOW.date())) == 0


def test_mandatory_miss_still_raised_below_the_weekly_target():
    chore = Chore(
        name="Cello",
        mandatory=True,
        weekly_target=3,
        time_category="afternoon",
        assigned_to=["k1"],
        id="c1",
    )
    comps = [ChoreCompletion(chore_id="c1", child_id="k1", completed_at=MONDAY)]
    coord = _mandatory_coord([chore], [Child(name="Kid", id="k1")], comps)
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        assert run(coord.async_detect_mandatory_misses("afternoon", NOW.date())) == 1


# ── perfect week ─────────────────────────────────────────────────────────────


def test_weekly_target_chores_are_not_due_on_any_particular_day():
    """perfect_week_requires_all_chores must not demand a weekly chore daily."""
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_chores = MagicMock(
        return_value=[
            Chore(name="Cello", id="a", weekly_target=3),
            Chore(name="Dishes", id="b"),
        ]
    )
    coord._is_chore_scheduled_for_date = MagicMock(return_value=True)
    due = coord._due_chore_ids_for_child("c1", NOW.date(), include_rotation=False)
    assert due == {"b"}
