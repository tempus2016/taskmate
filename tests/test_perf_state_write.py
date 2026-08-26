"""#823: entity state writes must not rebuild the whole dataset per read.

Home Assistant logs ``Updating state for <entity> took N seconds`` when a
state write blocks the event loop. Three separate O(n^2)-ish paths caused it:

  * ``TaskMateCalendar.event`` re-projected the whole horizon on every read,
    and HA reads it twice per write (state + state_attributes);
  * ``TaskMateChoreAvailabilitySensor.native_value`` rebuilt the availability
    matrix that ``extra_state_attributes`` had just built;
  * ``_is_rotation_done_today`` rescanned every completion, per chore;
  * every ``from_dict`` burned a uuid4 on a default it then discarded.

These tests pin the work down to a bounded number of passes rather than a
wall-clock budget, so they stay stable on slow CI runners.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from custom_components.taskmate import calendar as calendar_module
from custom_components.taskmate import models as models_module
from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

UTC = timezone.utc
NOW = datetime(2026, 6, 22, 9, 0, tzinfo=UTC)  # a Monday


def _coord(children, chores, completions=None, settings=None):
    """A real coordinator over mocked storage, as in test_calendar_platform."""
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.states.get.return_value = None
    _settings = settings or {}
    by_id = {c.id: c for c in children}
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": _settings.get(k, d))
    storage.get_children = MagicMock(return_value=children)
    storage.get_child = MagicMock(side_effect=lambda cid: by_id.get(cid))
    storage.get_chores = MagicMock(return_value=chores)
    storage.get_completions = MagicMock(return_value=completions or [])
    storage.get_last_completed = MagicMock(return_value={})
    storage.get_season_points = MagicMock(return_value={})
    coord.storage = storage
    coord.external_state_version = 0
    coord.data = {
        "children": children,
        "chores": chores,
        "rewards": [],
        "completions": completions or [],
        "pending_completions": [],
        "pending_reward_claims": [],
        "pool_allocations": [],
    }
    return coord


def _cal(coord, child):
    cal = object.__new__(calendar_module.TaskMateCalendar)
    cal.coordinator = coord
    cal._child_id = child.id
    cal._entry = MagicMock()
    cal._events_cache = None
    cal._events_key = None
    return cal


def _patched_now():
    return patch.multiple(
        "homeassistant.util.dt",
        now=MagicMock(return_value=NOW),
    )


class TestFromDictIdGeneration:
    """A stored id must not cost a uuid4 that is immediately thrown away."""

    def test_rebuilding_stored_records_generates_no_ids(self):
        rows = [
            Chore(name="c", id="chore-1").to_dict(),
            Child(name="k", id="child-1").to_dict(),
            ChoreCompletion(child_id="child-1", chore_id="chore-1", completed_at=NOW, id="comp-1").to_dict(),
        ]
        types = [Chore, Child, ChoreCompletion]
        with patch.object(models_module, "generate_id", wraps=models_module.generate_id) as gen:
            rebuilt = [t.from_dict(r) for t, r in zip(types, rows, strict=True)]
        assert [o.id for o in rebuilt] == ["chore-1", "child-1", "comp-1"]
        assert gen.call_count == 0

    def test_missing_id_still_gets_one(self):
        chore = Chore.from_dict({"name": "no id"})
        assert chore.id


class TestCalendarEventCaching:
    """``event`` is read twice per state write — the projection runs once."""

    def _fixture(self):
        kids = [Child(name=f"K{i}", id=f"child-{i}") for i in range(3)]
        chores = [
            Chore(
                name=f"C{i}",
                assigned_to=[k.id for k in kids],
                assignment_mode="balanced" if i % 2 else "alternating",
                schedule_mode="specific_days",
                due_days=[],
                created_date="2026-01-01",
                id=f"chore-{i:02d}",
            )
            for i in range(12)
        ]
        return kids, chores

    def test_repeated_reads_reuse_one_projection(self):
        kids, chores = self._fixture()
        coord = _coord(kids, chores)
        cal = _cal(coord, kids[0])
        with _patched_now():
            assert cal.event is not None
            coord.storage.get_chores.reset_mock()
            assert cal.event is not None
            assert cal.event is not None
        assert coord.storage.get_chores.call_count == 0

    def test_new_coordinator_data_invalidates_the_projection(self):
        kids, chores = self._fixture()
        coord = _coord(kids, chores)
        cal = _cal(coord, kids[0])
        with _patched_now():
            first = cal.event
            coord.data = dict(coord.data)  # a fresh snapshot == real refresh
            coord.storage.get_chores.reset_mock()
            second = cal.event
        assert coord.storage.get_chores.call_count >= 1
        assert (first is None) == (second is None)

    def test_projection_rebuilds_no_dataclasses_per_chore_day(self):
        """Rotation modes resolve their pool from the scope cache, not storage."""
        kids, chores = self._fixture()
        coord = _coord(kids, chores)
        cal = _cal(coord, kids[0])
        with _patched_now():
            assert cal.event is not None
        # One projection = one chores read and one children read, not one per
        # (chore, day) via _chore_assignment_pool / balanced-mode grouping.
        assert coord.storage.get_chores.call_count <= 2
        assert coord.storage.get_child.call_count <= len(kids) * 2


class TestAvailabilitySensorSingleBuild:
    """state + attributes are written together; build the matrix once."""

    def test_native_value_reuses_the_attribute_matrix(self):
        kids = [Child(name=f"K{i}", id=f"child-{i}") for i in range(3)]
        chores = [Chore(name=f"C{i}", assigned_to=[], id=f"chore-{i}") for i in range(10)]
        coord = _coord(kids, chores)
        entry = MagicMock()
        entry.entry_id = "e"
        sensor = sensor_module.TaskMateChoreAvailabilitySensor(coord, entry)

        with patch.object(
            sensor_module, "_build_chore_availability", wraps=sensor_module._build_chore_availability
        ) as build:
            attrs = sensor.extra_state_attributes
            value = sensor.native_value
        assert build.call_count == 1
        assert value == sum(sum(1 for v in per.values() if v) for per in attrs["chore_availability"].values())


class TestRotationDoneScan:
    """``_is_rotation_done_today`` must not walk every completion per chore."""

    def test_completion_scan_is_shared_across_chores(self):
        kids = [Child(name=f"K{i}", id=f"child-{i}") for i in range(2)]
        chores = [
            Chore(
                name=f"C{i}",
                assigned_to=[k.id for k in kids],
                assignment_mode="alternating",
                due_days=[],
                id=f"chore-{i:02d}",
            )
            for i in range(20)
        ]
        completions = [
            ChoreCompletion(
                child_id=f"child-{i % 2}",
                chore_id=f"chore-{i % 20:02d}",
                completed_at=NOW - timedelta(days=i),
                approved=True,
                id=f"comp-{i}",
            )
            for i in range(400)
        ]
        coord = _coord(kids, chores, completions)

        scanned = 0
        real_cached = coord._cached_completions

        def counting():
            nonlocal scanned
            out = real_cached()
            scanned += len(out)
            return out

        coord._cached_completions = counting
        with _patched_now():
            with coord.availability_build_scope():
                for chore in chores:
                    coord._is_rotation_done_today(chore)
        # One shared pass, not one full walk per chore.
        assert scanned <= len(completions) * 2, f"walked {scanned} completions for {len(chores)} chores"
