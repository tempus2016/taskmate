"""Tests for periodic savings interest."""

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
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_add_points = AsyncMock()
    return coord


def _run_on(coord, date_obj):
    with patch(
        "homeassistant.util.dt.now", return_value=dt.datetime(date_obj.year, date_obj.month, date_obj.day, 0, 5)
    ):
        run(coord._async_apply_interest())


def test_disabled_noop():
    coord = _coord({"interest_enabled": False}, [Child(name="A", points=100, id="c1")])
    _run_on(coord, dt.date(2026, 6, 15))
    coord.async_add_points.assert_not_awaited()


def test_weekly_interest_on_monday():
    coord = _coord(
        {"interest_enabled": True, "interest_period": "weekly", "interest_percent": "10"},
        [Child(name="A", points=100, id="c1")],
    )
    _run_on(coord, dt.date(2026, 6, 17))  # Wed -> none
    coord.async_add_points.assert_not_awaited()
    _run_on(coord, dt.date(2026, 6, 15))  # Mon -> 10
    coord.async_add_points.assert_awaited_once()
    assert coord.async_add_points.await_args[0][1] == 10


def test_monthly_first_only():
    coord = _coord(
        {"interest_enabled": True, "interest_period": "monthly", "interest_percent": "5"},
        [Child(name="A", points=200, id="c1")],
    )
    _run_on(coord, dt.date(2026, 7, 2))
    coord.async_add_points.assert_not_awaited()
    _run_on(coord, dt.date(2026, 7, 1))
    assert coord.async_add_points.await_args[0][1] == 10  # 5% of 200


def test_zero_balance_skipped():
    coord = _coord(
        {"interest_enabled": True, "interest_period": "monthly", "interest_percent": "5"},
        [Child(name="A", points=0, id="c1")],
    )
    _run_on(coord, dt.date(2026, 7, 1))
    coord.async_add_points.assert_not_awaited()


def test_no_double_same_day():
    coord = _coord(
        {"interest_enabled": True, "interest_period": "monthly", "interest_percent": "5"},
        [Child(name="A", points=100, id="c1")],
    )
    _run_on(coord, dt.date(2026, 7, 1))
    _run_on(coord, dt.date(2026, 7, 1))
    assert coord.async_add_points.await_count == 1
