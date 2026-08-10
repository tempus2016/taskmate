"""Tests for the celebration funnel (bigger celebration moments)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(settings=None):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    settings = settings or {}
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d=None: settings.get(k, d))
    coord.storage = storage
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    return coord


def _fired_event(coord):
    calls = [c for c in coord.hass.bus.async_fire.call_args_list if c[0][0] == "taskmate_celebration"]
    return calls


def test_event_always_fires_even_when_notify_off():
    coord = _coord({"celebration_notify": False})
    child = Child(name="Mia", id="a")
    run(coord._celebrate(child, "level_up", "Mia reached level 2!", tier=2))
    evs = _fired_event(coord)
    assert len(evs) == 1
    payload = evs[0][0][1]
    assert payload["kind"] == "level_up"
    assert payload["tier"] == 2
    assert payload["child_id"] == "a"
    coord.notifications.fire.assert_not_awaited()


def test_notify_fires_when_enabled_and_tier_meets_min():
    coord = _coord({"celebration_notify": "true", "celebration_notify_min_tier": "2"})
    child = Child(name="Mia", id="a")
    run(coord._celebrate(child, "perfect_week", "Perfect week!", tier=3))
    coord.notifications.fire.assert_awaited_once()
    assert coord.notifications.fire.await_args[0][0] == "celebration"


def test_notify_suppressed_below_min_tier():
    coord = _coord({"celebration_notify": True, "celebration_notify_min_tier": "3"})
    child = Child(name="Mia", id="a")
    run(coord._celebrate(child, "all_chores_done", "All done!", tier=1))
    # event still fires...
    assert len(_fired_event(coord)) == 1
    # ...but no notification (tier 1 < min 3)
    coord.notifications.fire.assert_not_awaited()


def test_extra_payload_merged():
    coord = _coord()
    child = Child(name="Bo", id="b")
    run(coord._celebrate(child, "level_up", "msg", tier=3, extra={"level": 5}))
    payload = _fired_event(coord)[0][0][1]
    assert payload["level"] == 5
