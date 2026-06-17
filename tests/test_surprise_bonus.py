"""Tests for the daily surprise / random bonus roll."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(settings, children):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": settings.get(k, d))
    storage.get_children = MagicMock(return_value=children)
    storage.get_points_name = MagicMock(return_value="Stars")
    coord.storage = storage
    coord.async_add_points = AsyncMock()
    return coord


def test_disabled_does_nothing():
    coord = _coord({"surprise_bonus_enabled": False}, [Child(name="A", id="c1")])
    run(coord._async_run_surprise_bonus())
    coord.async_add_points.assert_not_awaited()


def test_enabled_awards_when_roll_hits():
    coord = _coord(
        {"surprise_bonus_enabled": True, "surprise_bonus_chance": "100",
         "surprise_bonus_min": "5", "surprise_bonus_max": "5"},
        [Child(name="Mia", id="c1")],
    )
    import custom_components.taskmate.coordinator as mod
    with patch.object(mod.random, "random", return_value=0.0), \
         patch.object(mod.random, "randint", return_value=5):
        run(coord._async_run_surprise_bonus())
    coord.async_add_points.assert_awaited_once()
    args = coord.async_add_points.await_args
    assert args[0][0] == "c1" and args[0][1] == 5
    assert "Surprise" in args.kwargs["reason"]
    # event fired
    assert any(c[0][0] == "taskmate_surprise_bonus" for c in coord.hass.bus.async_fire.call_args_list)


def test_roll_miss_skips_child():
    coord = _coord(
        {"surprise_bonus_enabled": True, "surprise_bonus_chance": "10"},
        [Child(name="Mia", id="c1")],
    )
    import custom_components.taskmate.coordinator as mod
    # random()*100 = 50 >= chance 10 -> miss
    with patch.object(mod.random, "random", return_value=0.5):
        run(coord._async_run_surprise_bonus())
    coord.async_add_points.assert_not_awaited()


def test_enabled_accepts_string_true():
    coord = _coord(
        {"surprise_bonus_enabled": "true", "surprise_bonus_chance": "100",
         "surprise_bonus_min": "8", "surprise_bonus_max": "8"},
        [Child(name="Mia", id="c1")],
    )
    import custom_components.taskmate.coordinator as mod
    with patch.object(mod.random, "random", return_value=0.0), \
         patch.object(mod.random, "randint", return_value=8):
        run(coord._async_run_surprise_bonus())
    coord.async_add_points.assert_awaited_once()


def test_reversed_min_max_swapped():
    coord = _coord(
        {"surprise_bonus_enabled": True, "surprise_bonus_chance": "100",
         "surprise_bonus_min": "20", "surprise_bonus_max": "5"},
        [Child(name="Mia", id="c1")],
    )
    import custom_components.taskmate.coordinator as mod
    captured = {}
    def _randint(a, b):
        captured["lo"], captured["hi"] = a, b
        return a
    with patch.object(mod.random, "random", return_value=0.0), \
         patch.object(mod.random, "randint", side_effect=_randint):
        run(coord._async_run_surprise_bonus())
    assert captured["lo"] == 5 and captured["hi"] == 20  # swapped
