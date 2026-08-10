"""PERF-1: availability_build_scope memoizes per-chore work and completions."""

from __future__ import annotations

import datetime as dt
from datetime import timezone
from unittest.mock import MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore

UTC = timezone.utc
NOW = dt.datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)  # Monday


def _coord(chores, completions=None):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.storage = MagicMock()
    coord.storage.get_chores = MagicMock(return_value=chores)
    coord.storage.get_completions = MagicMock(return_value=completions or [])
    coord.storage.get_children = MagicMock(return_value=[])
    coord.storage.get_child = MagicMock(return_value=None)
    # Isolate the rotation/completions logic from the unrelated gates.
    coord._is_child_on_vacation = MagicMock(return_value=False)
    coord._is_visibility_entity_active = MagicMock(return_value=True)
    return coord


def test_scope_fetches_completions_once_across_many_lookups():
    # depends_on forces is_chore_available_for_child to read completions.
    chores = [Chore(name=f"c{i}", assigned_to=["k1"], depends_on=["dep"], id=f"id{i}") for i in range(5)]
    coord = _coord(chores)

    with (
        patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW),
        patch("custom_components.taskmate.coord_assignments.dt_util.now", return_value=NOW),
    ):
        with coord.availability_build_scope():
            for c in chores:
                for kid in ("k1", "k2", "k3"):
                    coord.is_chore_available_for_child(c, kid)

    # get_completions: once at scope entry. Never again inside the scope.
    assert coord.storage.get_completions.call_count == 1


def test_rotation_done_memoized_per_chore():
    chore = Chore(name="rot", assignment_mode="alternating", assigned_to=["k1", "k2"], id="r1")
    coord = _coord([chore])
    coord._is_rotation_done_today_uncached = MagicMock(return_value=False)
    coord._compute_active_children_uncached = MagicMock(return_value=["k1", "k2"])

    with (
        patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW),
        patch("custom_components.taskmate.coord_assignments.dt_util.now", return_value=NOW),
    ):
        with coord.availability_build_scope():
            for kid in ("k1", "k2"):
                coord.is_chore_available_for_child(chore, kid)

    # Despite two children, the chore-only computations run once each.
    assert coord._is_rotation_done_today_uncached.call_count == 1
    assert coord._compute_active_children_uncached.call_count == 1


def test_no_scope_means_no_cache_state_leaks():
    chore = Chore(name="x", assigned_to=["k1"], depends_on=["dep"], id="x1")
    coord = _coord([chore])
    with (
        patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW),
        patch("custom_components.taskmate.coord_assignments.dt_util.now", return_value=NOW),
    ):
        coord.is_chore_available_for_child(chore, "k1")
    # Outside a scope the cache is never created; storage is queried directly.
    assert getattr(coord, "_avail_cache", None) is None
    assert coord.storage.get_completions.call_count == 1


def test_scope_clears_cache_on_exit():
    coord = _coord([])
    with coord.availability_build_scope():
        assert coord._avail_cache is not None
    assert coord._avail_cache is None


def test_nested_scope_reuses_outer_cache():
    coord = _coord([])
    with coord.availability_build_scope():
        outer = coord._avail_cache
        with coord.availability_build_scope():
            assert coord._avail_cache is outer  # inner reuses, doesn't replace
        # Inner exit must NOT clear the outer scope's cache.
        assert coord._avail_cache is outer
    assert coord._avail_cache is None
