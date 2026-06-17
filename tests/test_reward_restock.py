"""Tests for reward auto-restock."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Reward


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(rewards):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_rewards = MagicMock(return_value=rewards)
    storage.update_reward = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def _run_on(coord, date_obj):
    fake = MagicMock()
    fake.now.return_value = dt.datetime(date_obj.year, date_obj.month, date_obj.day, 0, 5)
    with patch.dict("sys.modules"):
        with patch("homeassistant.util.dt.now", return_value=fake.now.return_value):
            run(coord._async_restock_rewards())


def test_daily_restocks_every_day():
    r = Reward(name="Snack", quantity=0, restock_enabled=True, restock_amount=3,
               restock_period="daily", restock_last="", id="r1")
    coord = _coord([r])
    _run_on(coord, dt.date(2026, 6, 17))  # any day
    assert r.quantity == 3 and r.restock_last == "2026-06-17"


def test_weekly_only_on_monday():
    r = Reward(name="Movie", quantity=0, restock_enabled=True, restock_amount=1,
               restock_period="weekly", restock_last="", id="r1")
    coord = _coord([r])
    _run_on(coord, dt.date(2026, 6, 17))  # Wednesday -> no restock
    assert r.quantity == 0
    _run_on(coord, dt.date(2026, 6, 15))  # Monday -> restock
    assert r.quantity == 1


def test_monthly_only_on_first():
    r = Reward(name="Outing", quantity=0, restock_enabled=True, restock_amount=2,
               restock_period="monthly", restock_last="", id="r1")
    coord = _coord([r])
    _run_on(coord, dt.date(2026, 6, 17))  # not the 1st
    assert r.quantity == 0
    _run_on(coord, dt.date(2026, 7, 1))   # 1st -> restock
    assert r.quantity == 2


def test_no_double_restock_same_day():
    r = Reward(name="Snack", quantity=5, restock_enabled=True, restock_amount=3,
               restock_period="daily", restock_last="2026-06-17", id="r1")
    coord = _coord([r])
    _run_on(coord, dt.date(2026, 6, 17))  # already restocked today
    assert r.quantity == 5  # untouched
    coord.storage.update_reward.assert_not_called()


def test_disabled_or_zero_amount_skipped():
    r1 = Reward(name="Off", quantity=0, restock_enabled=False, restock_amount=3,
                restock_period="daily", id="r1")
    r2 = Reward(name="ZeroAmt", quantity=0, restock_enabled=True, restock_amount=0,
                restock_period="daily", id="r2")
    coord = _coord([r1, r2])
    _run_on(coord, dt.date(2026, 6, 17))
    assert r1.quantity == 0 and r2.quantity == 0
    coord.storage.update_reward.assert_not_called()


def test_restock_round_trips_serialization():
    r = Reward(name="X", restock_enabled=True, restock_amount=4, restock_period="monthly",
               restock_last="2026-06-01")
    r2 = Reward.from_dict(r.to_dict())
    assert r2.restock_enabled and r2.restock_amount == 4
    assert r2.restock_period == "monthly" and r2.restock_last == "2026-06-01"
