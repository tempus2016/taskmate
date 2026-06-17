"""Tests for undo/retract of applied penalties and bonuses."""
from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, PointsTransaction
from custom_components.taskmate.storage import TaskMateStorage

UTC = dt.timezone.utc


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(child, txns):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_points_transactions = MagicMock(return_value=txns)
    storage.update_child = MagicMock()
    storage.append_career_score_snapshot = MagicMock()
    storage.remove_points_transaction = MagicMock(return_value=True)
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.get_child = MagicMock(return_value=child)
    coord.async_refresh = AsyncMock()
    return coord


def _txn(points, reason, tid="t1"):
    return PointsTransaction(child_id="c1", points=points, reason=reason,
                             created_at=dt.datetime(2024, 1, 1, tzinfo=UTC), id=tid)


# ── storage ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_storage_remove_transaction(hass):
    storage = TaskMateStorage(hass, "undo")
    await storage.async_load()
    storage.add_points_transaction(_txn(-5, "Penalty: x", "tx1"))
    assert storage.remove_points_transaction("tx1") is True
    assert storage.remove_points_transaction("tx1") is False


# ── coordinator ──────────────────────────────────────────────────────────────
def test_undo_penalty_restores_points_and_counter():
    child = Child(name="Mia", points=40, total_points_earned=100,
                  total_penalties_received=10)
    coord = _coord(child, [_txn(-10, "Penalty: Messy room")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 50                       # 40 + 10 back
    assert child.total_penalties_received == 0      # 10 - 10
    assert child.career_score == 100                # earned - penalties
    coord.storage.remove_points_transaction.assert_called_once_with("t1")


def test_undo_bonus_removes_points_and_earned():
    child = Child(name="Mia", points=50, total_points_earned=120,
                  total_penalties_received=0)
    coord = _coord(child, [_txn(20, "Bonus: Helped out")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 30                        # 50 - 20
    assert child.total_points_earned == 100          # 120 - 20


def test_undo_bonus_points_floor_at_zero():
    child = Child(name="Mia", points=5, total_points_earned=5)
    coord = _coord(child, [_txn(20, "Bonus: Big")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 0                          # clamped, not negative


def test_undo_rejects_non_penalty_bonus():
    child = Child(name="Mia", points=50)
    coord = _coord(child, [_txn(-10, "Allocated to pool: Bike")])
    with pytest.raises(ValueError, match="penalties and bonuses"):
        run(coord.async_undo_transaction("t1"))
    coord.storage.remove_points_transaction.assert_not_called()


def test_undo_missing_transaction_raises():
    child = Child(name="Mia")
    coord = _coord(child, [])
    with pytest.raises(ValueError, match="not found"):
        run(coord.async_undo_transaction("nope"))
