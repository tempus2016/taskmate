"""Tests for inter-child points gifting."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(children):
    by_id = {c.id: c for c in children}
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    storage = MagicMock()
    storage.update_child = MagicMock()
    txns = []
    storage.add_points_transaction = MagicMock(side_effect=lambda t: txns.append(t))
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._txns = txns
    coord.get_child = MagicMock(side_effect=lambda cid: by_id.get(cid))
    coord.async_refresh = AsyncMock()
    return coord


def test_gift_transfers_spendable_only():
    a = Child(name="A", points=50, total_points_earned=200, id="a")
    b = Child(name="B", points=10, total_points_earned=30, id="b")
    coord = _coord([a, b])
    run(coord.async_gift_points("a", "b", 20))
    assert a.points == 30 and b.points == 30
    # earned totals (career) untouched
    assert a.total_points_earned == 200 and b.total_points_earned == 30
    # two transactions logged with opposite signs
    signs = sorted(t.points for t in coord._txns)
    assert signs == [-20, 20]
    assert any(c[0][0] == "taskmate_points_gifted" for c in coord.hass.bus.async_fire.call_args_list)


def test_insufficient_balance_raises():
    a = Child(name="A", points=5, id="a")
    b = Child(name="B", points=0, id="b")
    coord = _coord([a, b])
    with pytest.raises(ValueError, match="Not enough"):
        run(coord.async_gift_points("a", "b", 20))
    assert a.points == 5 and b.points == 0


def test_self_gift_rejected():
    a = Child(name="A", points=50, id="a")
    coord = _coord([a])
    with pytest.raises(ValueError, match="same child"):
        run(coord.async_gift_points("a", "a", 10))


def test_nonpositive_rejected():
    a = Child(name="A", points=50, id="a")
    b = Child(name="B", points=0, id="b")
    coord = _coord([a, b])
    with pytest.raises(ValueError, match="positive"):
        run(coord.async_gift_points("a", "b", 0))


def test_missing_child_raises():
    a = Child(name="A", points=50, id="a")
    coord = _coord([a])
    with pytest.raises(ValueError, match="not found"):
        run(coord.async_gift_points("a", "ghost", 10))
