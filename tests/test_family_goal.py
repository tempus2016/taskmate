"""Tests for the family co-op goal (FEAT-4)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import family_services, websocket
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.family_goal import (
    BASELINE_KEY,
    family_goal_progress,
    seed_family_goal_baseline,
    start_family_goal,
)
from custom_components.taskmate.family_style import apply_family_style
from custom_components.taskmate.models import Child
from custom_components.taskmate.storage import TaskMateStorage


def _coord(children, settings):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_children = MagicMock(return_value=children)
    s.get_setting = MagicMock(side_effect=lambda k, d=None: settings.get(k, d))
    s.set_setting = MagicMock(side_effect=lambda k, v: settings.__setitem__(k, v))
    s.async_save = AsyncMock()
    c.storage = s
    c.hass = MagicMock()
    c.notifications = MagicMock()
    c.notifications.fire = AsyncMock()
    return c


def _kids(*points):
    return [Child(name=f"k{i}", id=f"k{i}", points=p) for i, p in enumerate(points)]


def test_progress_is_combined_points():
    c = _coord(_kids(100, 250, 50), {})
    assert c.family_goal_progress() == 400


@pytest.mark.asyncio
async def test_goal_fires_when_reached():
    settings = {
        "family_goal_enabled": True,
        "family_goal_target": 300,
        "family_goal_name": "Movie",
        "family_goal_reward": "popcorn",
    }
    c = _coord(_kids(150, 200), settings)  # 350 >= 300
    await c._async_check_family_goal()
    assert settings.get("family_goal_achieved") is True
    c.notifications.fire.assert_awaited_once()
    args = c.notifications.fire.await_args[0]
    assert args[0] == "family_goal_reached"
    assert args[1]["goal_name"] == "Movie" and args[1]["goal_reward"] == "popcorn"
    c.hass.bus.async_fire.assert_called_once()


@pytest.mark.asyncio
async def test_goal_not_fired_below_target():
    settings = {"family_goal_enabled": True, "family_goal_target": 1000}
    c = _coord(_kids(100, 100), settings)
    await c._async_check_family_goal()
    assert settings.get("family_goal_achieved") is None
    c.notifications.fire.assert_not_awaited()


@pytest.mark.asyncio
async def test_goal_only_fires_once():
    settings = {"family_goal_enabled": True, "family_goal_target": 100, "family_goal_achieved": True}
    c = _coord(_kids(500), settings)
    await c._async_check_family_goal()
    c.notifications.fire.assert_not_awaited()


@pytest.mark.asyncio
async def test_goal_skipped_when_disabled():
    settings = {"family_goal_enabled": False, "family_goal_target": 10}
    c = _coord(_kids(500), settings)
    await c._async_check_family_goal()
    c.notifications.fire.assert_not_awaited()


# ── Points earned since the goal started (#1282) ─────────────────────────────


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _storage(children=None, settings=None):
    """A real storage loaded from a saved file holding these children/settings."""
    stored = None
    if children is not None or settings is not None:
        stored = {"children": children or [], "settings": dict(settings or {})}
    storage = TaskMateStorage(MagicMock(), "test_entry")
    storage._store = MagicMock()
    storage._store.async_load = AsyncMock(return_value=stored)
    storage._store.async_save = AsyncMock()
    storage._store.async_delay_save = MagicMock()
    _run(storage.async_load())
    return storage


def _child(cid, points, earned, adult=False):
    return {"id": cid, "name": cid, "points": points, "total_points_earned": earned, "is_adult": adult}


def _set(storage, cid, **fields):
    for c in storage._data["children"]:
        if c["id"] == cid:
            c.update(fields)


def test_upgrade_keeps_the_number_an_existing_goal_showed():
    # Before #1282 the goal showed combined balances: 300 + 200.
    s = _storage([_child("a", 300, 900), _child("b", 200, 250)], {"family_goal_enabled": True})
    assert s.get_setting(BASELINE_KEY) == {"a": 600, "b": 50}
    assert family_goal_progress(s) == 500


def test_upgrade_seeds_only_once():
    s = _storage([_child("a", 10, 10)])
    s.set_setting(BASELINE_KEY, {"a": 3})
    assert seed_family_goal_baseline(s) is False
    assert s.get_setting(BASELINE_KEY) == {"a": 3}


def test_the_requested_example():
    s = _storage([_child("a", 300, 300), _child("b", 200, 200)])
    start_family_goal(s)
    assert family_goal_progress(s) == 0
    _set(s, "a", points=320, total_points_earned=320)
    assert family_goal_progress(s) == 20
    _set(s, "b", points=230, total_points_earned=230)
    assert family_goal_progress(s) == 50
    _set(s, "a", points=220)  # A spends 100 personal points
    assert family_goal_progress(s) == 50
    _set(s, "a", points=240, total_points_earned=340)
    assert family_goal_progress(s) == 70


def test_reset_leaves_balances_alone_and_rearms_the_celebration():
    s = _storage([_child("a", 300, 400)], {"family_goal_achieved": True})
    start_family_goal(s)
    assert s.get_children()[0].points == 300
    assert s.get_setting("family_goal_achieved") is False
    assert family_goal_progress(s) == 0


def test_adults_are_left_out():
    s = _storage([_child("a", 0, 0), _child("mum", 0, 0, adult=True)])
    start_family_goal(s)
    assert "mum" not in s.get_setting(BASELINE_KEY)
    _set(s, "mum", total_points_earned=500)
    _set(s, "a", total_points_earned=40)
    assert family_goal_progress(s) == 40


def test_a_child_added_after_the_start_counts_from_zero():
    s = _storage([_child("a", 0, 0)])
    start_family_goal(s)
    s._data["children"].append(_child("new", 15, 15))
    assert family_goal_progress(s) == 15


def test_undoing_an_old_approval_never_goes_below_zero():
    s = _storage([_child("a", 100, 100), _child("b", 0, 0)])
    start_family_goal(s)
    _set(s, "a", total_points_earned=80)
    _set(s, "b", total_points_earned=30)
    assert family_goal_progress(s) == 30


def test_without_a_baseline_it_falls_back_to_balances():
    s = _storage([_child("a", 120, 900), _child("mum", 50, 50, adult=True)])
    s.get_settings().pop(BASELINE_KEY)
    assert family_goal_progress(s) == 120


def _coordinator(storage):
    c = object.__new__(TaskMateCoordinator)
    c.storage = storage
    c.async_refresh = AsyncMock()
    c.async_check_birthdays = AsyncMock(return_value=[])
    c.async_record_audit = AsyncMock()
    return c


def _update_settings(coord, **fields):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coord}}
    conn = MagicMock()
    conn.user = SimpleNamespace(is_admin=True, id="u1", name="Parent")
    _run(websocket._ws_update_settings(hass, conn, {"id": 1, "type": websocket.WS_UPDATE_SETTINGS, **fields}))


def test_switching_the_goal_on_starts_it_at_zero():
    s = _storage([_child("a", 300, 300)])
    _update_settings(_coordinator(s), family_goal_enabled=True, family_goal_target=500)
    assert family_goal_progress(s) == 0


def test_a_new_target_keeps_the_progress():
    s = _storage([_child("a", 300, 300)], {"family_goal_enabled": True})
    start_family_goal(s)
    _set(s, "a", total_points_earned=360)
    _update_settings(_coordinator(s), family_goal_enabled=True, family_goal_target=800)
    assert family_goal_progress(s) == 60


def test_the_team_style_switching_the_goal_on_starts_it_at_zero():
    s = _storage([_child("a", 300, 300)])
    apply_family_style(s, "team")
    assert family_goal_progress(s) == 0


def test_coordinator_reset_saves_and_refreshes():
    s = _storage([_child("a", 300, 300)])
    c = _coordinator(s)
    s.async_save = AsyncMock()
    _run(c.async_reset_family_goal())
    assert c.family_goal_progress() == 0
    s.async_save.assert_awaited_once()
    c.async_refresh.assert_awaited_once()


def test_reset_service_is_registered_as_a_parent_action():
    hass = MagicMock()
    registered = {}
    hass.services.async_register = lambda domain, name, handler, schema=None: registered.__setitem__(name, handler)
    parent_wrapped = []

    def parent_action(handler):
        parent_wrapped.append(handler)
        return handler

    family_services.async_register_family_services(
        hass,
        child_action=lambda h: h,
        parent_action=parent_action,
        get_coordinator=lambda: None,
        require_linked_child=AsyncMock(),
    )
    assert "reset_family_goal" in registered
    assert registered["reset_family_goal"] in parent_wrapped
    assert "reset_family_goal" in family_services.FAMILY_SERVICES
