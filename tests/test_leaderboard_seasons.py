"""Tests for leaderboard seasons (FEAT-2)."""
from __future__ import annotations

import datetime as dt
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, PointsTransaction
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc


@pytest.mark.asyncio
async def test_positive_transactions_accumulate_per_month(hass):
    s = TaskMateStorage(hass, "season")
    await s.async_load()
    when = dt.datetime(2026, 4, 10, 9, 0, tzinfo=UTC)
    s.add_points_transaction(PointsTransaction(child_id="k1", points=10, created_at=when))
    s.add_points_transaction(PointsTransaction(child_id="k1", points=5, created_at=when))
    s.add_points_transaction(PointsTransaction(child_id="k2", points=7, created_at=when))
    # Negative (penalty/spend) does not count toward earned-season points.
    s.add_points_transaction(PointsTransaction(child_id="k1", points=-3, created_at=when))
    # Different month is bucketed separately.
    s.add_points_transaction(PointsTransaction(
        child_id="k1", points=99, created_at=dt.datetime(2026, 5, 1, 9, 0, tzinfo=UTC)))

    assert s.get_season_points("2026-04") == {"k1": 15, "k2": 7}
    assert s.get_season_points("2026-05") == {"k1": 99}


def _coord(children, season_points, champions=None):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_children = MagicMock(return_value=children)
    s.get_season_points = MagicMock(side_effect=lambda ym: dict(season_points.get(ym, {})))
    s.get_season_champions = MagicMock(return_value=list(champions or []))
    s.get_points_name = MagicMock(return_value="Stars")
    c.storage = s
    return c


def test_standings_ranked_desc_with_rank():
    kids = [Child(name="Alex", id="k1"), Child(name="Sam", id="k2"), Child(name="Mo", id="k3")]
    c = _coord(kids, {"2026-04": {"k1": 5, "k2": 20}})
    rows = c.get_season_standings("2026-04")
    assert [(r["name"], r["points"], r["rank"]) for r in rows] == [
        ("Sam", 20, 1), ("Alex", 5, 2), ("Mo", 0, 3),
    ]


@pytest.mark.asyncio
async def test_finalize_records_champion_and_notifies(monkeypatch):
    from tests.conftest import dt_util_mock
    kids = [Child(name="Alex", id="k1"), Child(name="Sam", id="k2")]
    c = _coord(kids, {"2026-04": {"k1": 30, "k2": 12}})
    c.storage.add_season_champion = MagicMock()
    c.storage.async_save = AsyncMock()
    c.hass = MagicMock()
    c.notifications = MagicMock()
    c.notifications.fire = AsyncMock()
    monkeypatch.setattr(dt_util_mock, "_now", dt.datetime(2026, 5, 1, 18, 0, tzinfo=UTC))
    await c._async_finalize_season()
    entry = c.storage.add_season_champion.call_args[0][0]
    assert entry == {"month": "2026-04", "child_id": "k1", "child_name": "Alex", "points": 30}
    fired = c.notifications.fire.await_args[0]
    assert fired[0] == "season_champion"
    assert fired[1]["child_name"] == "Alex" and fired[1]["month"] == "April 2026"


@pytest.mark.asyncio
async def test_finalize_skips_when_no_points(monkeypatch):
    from tests.conftest import dt_util_mock
    c = _coord([Child(name="Alex", id="k1")], {"2026-04": {}})
    c.storage.add_season_champion = MagicMock()
    c.storage.async_save = AsyncMock()
    c.hass = MagicMock()
    c.notifications = MagicMock()
    c.notifications.fire = AsyncMock()
    monkeypatch.setattr(dt_util_mock, "_now", dt.datetime(2026, 5, 1, 18, 0, tzinfo=UTC))
    await c._async_finalize_season()
    c.storage.add_season_champion.assert_not_called()


@pytest.mark.asyncio
async def test_finalize_is_idempotent_for_month(monkeypatch):
    from tests.conftest import dt_util_mock
    c = _coord([Child(name="Alex", id="k1")], {"2026-04": {"k1": 5}},
               champions=[{"month": "2026-04", "child_id": "k1"}])
    c.storage.add_season_champion = MagicMock()
    c.storage.async_save = AsyncMock()
    c.hass = MagicMock()
    c.notifications = MagicMock()
    c.notifications.fire = AsyncMock()
    monkeypatch.setattr(dt_util_mock, "_now", dt.datetime(2026, 5, 1, 18, 0, tzinfo=UTC))
    await c._async_finalize_season()
    c.storage.add_season_champion.assert_not_called()
