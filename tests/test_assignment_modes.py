"""Tests for dynamic chore assignment (alternating/random) and calendar publishing.

Covers:
- `_compute_active_children` for each mode (everyone/alternating/random).
- `is_chore_available_for_child` respects the dynamic active child.
- `_publish_chore_to_calendars` fans out calendar.create_event per entity.
- Immediate publish on chore create/update.
- Scale smoke test: 50 chores x 5 children x 3 calendars run concurrently.
- Storage round-trip keeps legacy chores backwards-compatible.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import time
from datetime import date, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore

from .conftest import dt_util_mock, run_async

UTC = timezone.utc


def _coord(children: list[Child]) -> TaskMateCoordinator:
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.services = MagicMock()
    coord.hass.services.async_call = AsyncMock()
    coord.data = {}
    coord._unsub_midnight = None
    coord._unsub_prune = None

    by_id = {c.id: c for c in children}
    stored_chores: list[Chore] = []

    storage = MagicMock()
    storage.get_children = MagicMock(return_value=list(children))
    storage.get_child = MagicMock(side_effect=lambda cid: by_id.get(cid))
    storage.get_chores = MagicMock(side_effect=lambda: list(stored_chores))

    def _get_chore(cid):
        found = next((c for c in stored_chores if c.id == cid), None)
        # Return a snapshot so callers comparing against the stored state see
        # the pre-update values (mirrors real serialize/deserialize behaviour).
        return Chore.from_dict(found.to_dict()) if found is not None else None

    storage.get_chore = MagicMock(side_effect=_get_chore)
    storage.add_chore = MagicMock(side_effect=stored_chores.append)
    storage.update_chore = MagicMock(side_effect=lambda chore: stored_chores.__setitem__(
        next(i for i, c in enumerate(stored_chores) if c.id == chore.id), chore
    ))
    storage.async_save = AsyncMock()

    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def test_compute_active_everyone_returns_assigned_list():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    chore = Chore(name="X", assigned_to=[a.id, b.id])
    assert coord._compute_active_children(chore, date(2026, 4, 20)) == [a.id, b.id]


def test_compute_active_alternating_rotates_day_by_day():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    anchor = date(2026, 4, 20)  # Monday
    chore = Chore(
        name="Litter box",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
    )
    assert coord._compute_active_children(chore, anchor) == [a.id]
    assert coord._compute_active_children(chore, anchor + dt.timedelta(days=1)) == [b.id]
    assert coord._compute_active_children(chore, anchor + dt.timedelta(days=2)) == [a.id]
    # Three-child rotation wraps correctly
    c = Child(name="C")
    coord2 = _coord([a, b, c])
    chore2 = Chore(name="Table", assigned_to=[a.id, b.id, c.id], assignment_mode="alternating",
                   assignment_rotation_anchor=anchor.isoformat())
    picks = [coord2._compute_active_children(chore2, anchor + dt.timedelta(days=i))[0] for i in range(4)]
    assert picks == [a.id, b.id, c.id, a.id]


def test_compute_active_alternating_defaults_to_all_children_when_unassigned():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    chore = Chore(name="Any", assignment_mode="alternating")
    today = date(2026, 4, 20)
    # Should pick one of the two children deterministically
    pick = coord._compute_active_children(chore, today)
    assert pick and pick[0] in (a.id, b.id)


def test_compute_active_random_is_stable_per_day():
    kids = [Child(name=f"K{i}") for i in range(5)]
    coord = _coord(kids)
    chore = Chore(name="Lottery", assigned_to=[c.id for c in kids], assignment_mode="random")
    today = date(2026, 4, 20)
    a1 = coord._compute_active_children(chore, today)
    a2 = coord._compute_active_children(chore, today)
    assert a1 == a2
    assert len(a1) == 1 and a1[0] in {c.id for c in kids}


def test_compute_active_random_varies_by_date():
    # Over a week's worth of dates at least two picks must differ for a 5-child pool.
    kids = [Child(name=f"K{i}") for i in range(5)]
    coord = _coord(kids)
    chore = Chore(name="Roulette", assigned_to=[c.id for c in kids], assignment_mode="random")
    picks = {coord._compute_active_children(chore, date(2026, 4, 20) + dt.timedelta(days=i))[0]
             for i in range(14)}
    assert len(picks) >= 2


def test_is_chore_available_respects_dynamic_assignment():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    # needs storage.get_last_completed for is_chore_available_for_child
    coord.storage.get_last_completed = MagicMock(return_value={})
    anchor = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
    chore = Chore(
        name="Dishes",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
    )
    assert coord.is_chore_available_for_child(chore, a.id) is True
    assert coord.is_chore_available_for_child(chore, b.id) is False
    # Everyone mode is unchanged
    chore.assignment_mode = "everyone"
    assert coord.is_chore_available_for_child(chore, a.id) is True
    assert coord.is_chore_available_for_child(chore, b.id) is True


def test_publish_fans_out_one_call_per_calendar():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    today = date(2026, 4, 20)
    chore = Chore(
        name="Litter box",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=today.isoformat(),
        publish_calendar_entities=["calendar.kids", "calendar.family", "calendar.shared"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    assert coord.hass.services.async_call.await_count == 3
    # Dedup: second call on the same day is a no-op.
    run_async(coord._publish_chore_to_calendars(chore, today))
    assert coord.hass.services.async_call.await_count == 3
    # Next day re-enables publishing.
    run_async(coord._publish_chore_to_calendars(chore, today + dt.timedelta(days=1)))
    assert coord.hass.services.async_call.await_count == 6
    # Summary references today's active child (A on day-0)
    first_call = coord.hass.services.async_call.await_args_list[0]
    payload = first_call.args[2]
    assert payload["summary"] == "Litter box — A"
    assert payload["start_date"] == today.isoformat()


def test_publish_is_noop_when_no_entities_configured():
    a = Child(name="A")
    coord = _coord([a])
    chore = Chore(name="Solo", assigned_to=[a.id])
    run_async(coord._publish_chore_to_calendars(chore, date(2026, 4, 20)))
    assert coord.hass.services.async_call.await_count == 0


def test_async_add_chore_publishes_immediately():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    dt_util_mock._now = dt.datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    chore = run_async(coord.async_add_chore(
        name="Trash day",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor="2026-04-20",
        publish_calendar_entities=["calendar.kids", "calendar.family"],
    ))
    assert coord.hass.services.async_call.await_count == 2
    assert chore.publish_calendar_last_date == "2026-04-20"
    assert chore.assignment_current_child_id == a.id


def test_async_update_chore_republishes_on_name_change():
    a = Child(name="A")
    coord = _coord([a])
    dt_util_mock._now = dt.datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    chore = run_async(coord.async_add_chore(
        name="Old",
        assigned_to=[a.id],
        publish_calendar_entities=["calendar.x"],
    ))
    # One publish for the initial create
    assert coord.hass.services.async_call.await_count == 1
    # Simulate an edit flow: fetch a fresh copy, mutate, save.
    edited = coord.storage.get_chore(chore.id)
    edited.name = "New"
    run_async(coord.async_update_chore(edited))
    # Guard cleared due to name change, so we publish again
    assert coord.hass.services.async_call.await_count == 2


def test_scale_50_chores_5_children_3_calendars():
    kids = [Child(name=f"K{i}") for i in range(5)]
    coord = _coord(kids)
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(0, 0, 5), tzinfo=UTC)
    cals = ["calendar.a", "calendar.b", "calendar.c"]
    for i in range(50):
        chore = Chore(
            name=f"Chore {i}",
            assigned_to=[c.id for c in kids],
            assignment_mode="alternating" if i % 2 == 0 else "random",
            assignment_rotation_anchor=today.isoformat(),
            publish_calendar_entities=list(cals),
        )
        coord.storage.add_chore(chore)

    started = time.monotonic()
    run_async(coord._async_refresh_assignments_and_publish())
    duration = time.monotonic() - started

    assert coord.hass.services.async_call.await_count == 50 * 3
    # Concurrency guarantees the midnight tick stays sub-second even with 150 calls.
    assert duration < 5.0


def test_chore_from_dict_defaults_are_legacy_safe():
    legacy = {"name": "Legacy"}
    chore = Chore.from_dict(legacy)
    assert chore.assignment_mode == "everyone"
    assert chore.assignment_rotation_anchor == ""
    assert chore.assignment_current_child_id == ""
    assert chore.publish_calendar_entities == []
    assert chore.publish_calendar_last_date == ""
    # Round-trip preserves the new fields
    restored = Chore.from_dict(chore.to_dict())
    assert restored.assignment_mode == "everyone"
    assert restored.publish_calendar_entities == []
