"""Surprise inspections on the Parent Dashboard Card (#1285).

The pending-approvals sensor publishes what the card needs to run an
inspection without the admin panel: the start defaults (only while the
feature is on), open inspections with whether a fail can send the chore back,
and the approved chores that can still be flagged, newest first and capped.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pytest

from custom_components.taskmate import sensor as sensor_module

from .conftest import dt_util_mock
from .test_inspections import NOW, _approved, _system, run

UTC = dt.timezone.utc


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = NOW
    yield
    dt_util_mock._now = saved


def _attrs(coord) -> dict:
    sensor = sensor_module.PendingApprovalsSensor(coord, MagicMock(entry_id="e1"))
    return sensor.extra_state_attributes


def test_nothing_while_inspections_are_off():
    async def go():
        coord = await _system({"inspections_enabled": False})
        await _approved(coord)
        return _attrs(coord)

    attrs = run(go())
    for key in ("inspection_settings", "open_inspections", "inspectable_completions"):
        assert key not in attrs


def test_settings_ride_along_and_empty_lists_stay_out():
    async def go():
        coord = await _system(
            {
                "inspection_bonus": 25,
                "inspection_window": "bed",
                "inspection_fail_mode": "ask",
                "inspection_tell_child": False,
                "inspection_bedtime": "19:30",
            }
        )
        return _attrs(coord)

    attrs = run(go())
    assert attrs["inspection_settings"] == {
        "bonus": 25,
        "window": "bed",
        "fail_mode": "ask",
        "tell_child": False,
        "bedtime": "19:30",
        "bed_rule": {"min_minutes": 30, "fallback_hours": 1},
    }
    assert "open_inspections" not in attrs
    assert "inspectable_completions" not in attrs


def test_approved_chore_is_offered_then_moves_to_open():
    async def go():
        coord = await _system()
        child, _chore, completion = await _approved(coord, points=7)
        before = _attrs(coord)
        record = await coord.async_start_inspection(completion.id, bonus=12, window="1h", tell_child=False)
        return child, completion, record, before, _attrs(coord)

    child, completion, record, before, after = run(go())
    (row,) = before["inspectable_completions"]
    assert row == {
        "completion_id": completion.id,
        "child_id": child.id,
        "child_name": "Vaiha",
        "chore_name": "Tidy bedroom",
        "points": 7,
        "approved_at": (completion.approved_at or completion.completed_at).isoformat(),
    }
    assert "open_inspections" not in before

    # Once flagged it can't be flagged again; it waits for a decision instead.
    assert "inspectable_completions" not in after
    (open_row,) = after["open_inspections"]
    assert open_row["id"] == record["id"]
    assert open_row["completion_id"] == completion.id
    assert open_row["child_name"] == "Vaiha"
    assert open_row["chore_name"] == "Tidy bedroom"
    assert open_row["bonus"] == 12
    assert open_row["points"] == 7
    assert open_row["until"] == record["until"]
    assert open_row["tell_child"] is False
    assert open_row["source"] == "parent"
    # A plain chore done today can be sent back to redo.
    assert open_row["can_redo"] is True


def test_decided_inspection_leaves_the_open_list():
    async def go():
        coord = await _system()
        _child, _chore, completion = await _approved(coord)
        record = await coord.async_start_inspection(completion.id)
        await coord.async_pass_inspection(record["id"], bonus=5)
        return _attrs(coord)

    attrs = run(go())
    assert "open_inspections" not in attrs
    assert "inspectable_completions" not in attrs


def test_inspectable_list_is_newest_first_and_capped(monkeypatch):
    monkeypatch.setattr(sensor_module, "INSPECTABLE_CARD_MAX", 3)

    async def go():
        coord = await _system()
        child = await coord.async_add_child("Vaiha")
        base = dt.datetime(2024, 3, 20, 6, 0, tzinfo=UTC)
        for i in range(5):
            chore = await coord.async_add_chore(
                f"Chore {i}", points=1, requires_approval=False, schedule_mode="specific_days", assigned_to=[child.id]
            )
            # Done (and auto-approved) an hour apart, oldest first.
            dt_util_mock._now = base + dt.timedelta(hours=i)
            await coord.async_complete_chore(chore.id, child.id)
        dt_util_mock._now = base + dt.timedelta(hours=6)
        return _attrs(coord)

    rows = run(go())["inspectable_completions"]
    assert [r["chore_name"] for r in rows] == ["Chore 4", "Chore 3", "Chore 2"]


def test_stand_in_coordinator_publishes_nothing():
    # Other sensor tests drive this sensor with a MagicMock coordinator, whose
    # inspections_enabled() answers with a mock rather than a bool.
    coord = MagicMock()
    coord.data = {"pending_completions": [], "pending_reward_claims": []}
    coord.storage.get_swap_requests.return_value = []
    coord.mandatory_misses_state.return_value = []
    coord.miss_review_location.return_value = "card"
    coord.owed_rewards.return_value = []
    coord.quality_rating_enabled.return_value = False
    attrs = _attrs(coord)
    assert "inspection_settings" not in attrs
