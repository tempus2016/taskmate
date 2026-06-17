"""Tests for periodic points decay."""
from __future__ import annotations

import asyncio
import datetime as dt
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
    store = dict(settings)
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": store.get(k, d))
    storage.set_setting = MagicMock(side_effect=lambda k, v: store.__setitem__(k, v))
    storage.get_children = MagicMock(return_value=children)
    storage.update_child = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._store = store
    coord.async_refresh = AsyncMock()
    return coord


def _run_on(coord, date_obj):
    ndt = dt.datetime(date_obj.year, date_obj.month, date_obj.day, 0, 5)
    with patch("homeassistant.util.dt.now", return_value=ndt):
        run(coord._async_decay_points())


def test_disabled_noop():
    c = Child(name="A", points=100, id="c1")
    coord = _coord({"points_decay_enabled": False}, [c])
    _run_on(coord, dt.date(2026, 7, 1))
    assert c.points == 100


def test_monthly_decay_on_first():
    c = Child(name="A", points=100, id="c1")
    coord = _coord({"points_decay_enabled": True, "points_decay_period": "monthly",
                    "points_decay_percent": "10"}, [c])
    _run_on(coord, dt.date(2026, 7, 1))   # 1st -> decay 10%
    assert c.points == 90
    coord.storage.add_points_transaction.assert_called_once()
    assert any(x[0][0] == "taskmate_points_decay" for x in coord.hass.bus.async_fire.call_args_list)


def test_monthly_skips_non_first():
    c = Child(name="A", points=100, id="c1")
    coord = _coord({"points_decay_enabled": True, "points_decay_period": "monthly",
                    "points_decay_percent": "10"}, [c])
    _run_on(coord, dt.date(2026, 7, 15))
    assert c.points == 100


def test_weekly_on_monday_only():
    c = Child(name="A", points=200, id="c1")
    coord = _coord({"points_decay_enabled": True, "points_decay_period": "weekly",
                    "points_decay_percent": "25"}, [c])
    _run_on(coord, dt.date(2026, 6, 17))  # Wed
    assert c.points == 200
    _run_on(coord, dt.date(2026, 6, 15))  # Mon -> 25% off
    assert c.points == 150


def test_no_double_decay_same_day():
    c = Child(name="A", points=100, id="c1")
    coord = _coord({"points_decay_enabled": True, "points_decay_period": "monthly",
                    "points_decay_percent": "10"}, [c])
    _run_on(coord, dt.date(2026, 7, 1))
    assert c.points == 90
    _run_on(coord, dt.date(2026, 7, 1))   # guarded by points_decay_last
    assert c.points == 90


def test_zero_balance_skipped():
    c = Child(name="A", points=0, id="c1")
    coord = _coord({"points_decay_enabled": True, "points_decay_period": "monthly",
                    "points_decay_percent": "10"}, [c])
    _run_on(coord, dt.date(2026, 7, 1))
    assert c.points == 0
    coord.storage.add_points_transaction.assert_not_called()
