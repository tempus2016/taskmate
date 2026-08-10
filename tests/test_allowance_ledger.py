"""Tests for the allowance payout ledger (FEAT-3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child


def _coord(*, enabled=True, rate=10, currency="£", child=None):
    if child is None:
        child = Child(name="Alex", id="k1")
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    settings = {"allowance_enabled": enabled, "allowance_rate": rate, "allowance_currency": currency}
    s.get_setting = MagicMock(side_effect=lambda k, d=None: settings.get(k, d))
    s.get_child = MagicMock(return_value=child)
    s.add_allowance_payout = MagicMock()
    s.async_save = AsyncMock()
    c.storage = s
    c.hass = MagicMock()
    c.get_child = MagicMock(return_value=child)
    c.async_remove_points = AsyncMock()
    c.async_refresh = AsyncMock()
    # _setting_enabled reads via get_setting; reuse the real mixin method.
    return c


@pytest.mark.asyncio
async def test_payout_deducts_points_and_logs_amount():
    c = _coord(rate=10, currency="£")
    entry = await c.async_record_allowance_payout("k1", 50)
    c.async_remove_points.assert_awaited_once()
    args = c.async_remove_points.await_args
    assert args.args[0] == "k1" and args.args[1] == 50
    assert entry["amount"] == 5.0 and entry["currency"] == "£" and entry["points"] == 50
    c.storage.add_allowance_payout.assert_called_once()
    c.hass.bus.async_fire.assert_called_once()


@pytest.mark.asyncio
async def test_payout_rounds_to_cents():
    c = _coord(rate=3)
    entry = await c.async_record_allowance_payout("k1", 10)
    assert entry["amount"] == round(10 / 3, 2)


@pytest.mark.asyncio
async def test_payout_rejects_when_disabled():
    c = _coord(enabled=False)
    with pytest.raises(ValueError):
        await c.async_record_allowance_payout("k1", 10)
    c.async_remove_points.assert_not_awaited()


@pytest.mark.asyncio
async def test_payout_rejects_bad_points():
    c = _coord()
    with pytest.raises(ValueError):
        await c.async_record_allowance_payout("k1", 0)


@pytest.mark.asyncio
async def test_payout_rejects_unknown_child():
    c = _coord()
    c.get_child = MagicMock(return_value=None)
    with pytest.raises(ValueError):
        await c.async_record_allowance_payout("ghost", 10)
