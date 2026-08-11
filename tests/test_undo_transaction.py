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


def _txn(points, reason, tid="t1", child_id="c1", link_id=""):
    return PointsTransaction(
        child_id=child_id,
        points=points,
        reason=reason,
        created_at=dt.datetime(2024, 1, 1, tzinfo=UTC),
        id=tid,
        link_id=link_id,
    )


def _coord_multi(children, txns):
    """Coordinator whose get_child resolves against a {id: Child} map (gift undo)."""
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_points_transactions = MagicMock(return_value=txns)
    storage.update_child = MagicMock()
    storage.append_career_score_snapshot = MagicMock()
    storage.remove_points_transaction = MagicMock(return_value=True)
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.get_child = MagicMock(side_effect=lambda cid: children.get(cid))
    coord.async_refresh = AsyncMock()
    return coord


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
    child = Child(name="Mia", points=40, total_points_earned=100, total_penalties_received=10)
    coord = _coord(child, [_txn(-10, "Penalty: Messy room")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 50  # 40 + 10 back
    assert child.total_penalties_received == 0  # 10 - 10
    assert child.career_score == 100  # earned - penalties
    coord.storage.remove_points_transaction.assert_called_once_with("t1")


def test_undo_bonus_removes_points_and_earned():
    child = Child(name="Mia", points=50, total_points_earned=120, total_penalties_received=0)
    coord = _coord(child, [_txn(20, "Bonus: Helped out")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 30  # 50 - 20
    assert child.total_points_earned == 100  # 120 - 20


def test_undo_bonus_points_floor_at_zero():
    child = Child(name="Mia", points=5, total_points_earned=5)
    coord = _coord(child, [_txn(20, "Bonus: Big")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 0  # clamped, not negative


def test_undo_missing_transaction_raises():
    child = Child(name="Mia")
    coord = _coord(child, [])
    with pytest.raises(ValueError, match="not found"):
        run(coord.async_undo_transaction("nope"))


# ── manual adjustments (now reversible) ──────────────────────────────────────
def test_undo_manual_add_removes_points_and_earned():
    # async_add_points raised both points and total_points_earned.
    child = Child(name="Mia", points=50, total_points_earned=120)
    coord = _coord(child, [_txn(20, "Pocket money top-up")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 30  # 50 - 20
    assert child.total_points_earned == 100  # 120 - 20
    coord.storage.remove_points_transaction.assert_called_once_with("t1")


def test_undo_manual_remove_restores_points_only():
    # A plain (non-penalty) remove only reduced spendable points; undo must not
    # touch totals.
    child = Child(name="Mia", points=30, total_points_earned=100, total_penalties_received=0)
    coord = _coord(child, [_txn(-10, "Confiscated tablet")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 40  # 30 + 10 back
    assert child.total_points_earned == 100  # unchanged
    assert child.total_penalties_received == 0  # unchanged


def test_undo_manual_add_with_empty_reason():
    child = Child(name="Mia", points=15, total_points_earned=15)
    coord = _coord(child, [_txn(5, "")])
    run(coord.async_undo_transaction("t1"))
    assert child.points == 10
    assert child.total_points_earned == 10


# ── gifts (two-leg reversal via link_id) ─────────────────────────────────────
def test_undo_gift_reverses_both_legs():
    sender = Child(name="Mia", id="c1", points=30)
    recipient = Child(name="Sam", id="c2", points=70)
    legs = [
        _txn(-20, "Gift to Sam", tid="g_send", child_id="c1", link_id="L1"),
        _txn(20, "Gift from Mia", tid="g_recv", child_id="c2", link_id="L1"),
    ]
    coord = _coord_multi({"c1": sender, "c2": recipient}, legs)
    run(coord.async_undo_transaction("g_send"))  # undo from either leg
    assert sender.points == 50  # 30 + 20 back to sender
    assert recipient.points == 50  # 70 - 20 removed from recipient
    removed = {c.args[0] for c in coord.storage.remove_points_transaction.call_args_list}
    assert removed == {"g_send", "g_recv"}  # both legs gone


def test_undo_legacy_gift_without_link_id_refused():
    sender = Child(name="Mia", id="c1", points=30)
    coord = _coord_multi(
        {"c1": sender},
        [_txn(-20, "Gift to Sam", tid="g_old", child_id="c1", link_id="")],
    )
    with pytest.raises(ValueError, match="predates"):
        run(coord.async_undo_transaction("g_old"))
    coord.storage.remove_points_transaction.assert_not_called()


# ── derived transactions stay refused (deny-list) ────────────────────────────
@pytest.mark.parametrize(
    "reason",
    [
        "Weekend bonus (×2)",
        "Streak milestone bonus (7 day streak!)",
        "Perfect week bonus! (01 Jan – 07 Jan)",
        "Allocated to pool: Bike",
        "Pool refund (reward expired)",
        "Points decay (-10%)",
        "Savings interest (+5%)",
        "Badge: Tidy Titan",
    ],
)
def test_undo_refuses_derived(reason):
    child = Child(name="Mia", points=50, id="c1")
    coord = _coord(child, [_txn(-10, reason)])
    with pytest.raises(ValueError, match="can't be undone"):
        run(coord.async_undo_transaction("t1"))
    coord.storage.remove_points_transaction.assert_not_called()
