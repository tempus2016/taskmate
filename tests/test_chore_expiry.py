"""Tests for dated chore expiry (expires_on)."""

from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(chores):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.get_chores = MagicMock(return_value=chores)
    storage.update_chore = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def _run_on(coord, date_obj):
    ndt = dt.datetime(date_obj.year, date_obj.month, date_obj.day, 0, 5)
    with (
        patch("homeassistant.util.dt.now", return_value=ndt),
        patch("homeassistant.util.dt.as_local", side_effect=lambda d: d),
    ):
        run(coord._async_expire_dated_chores())


def test_expires_after_date():
    c = Chore(name="Summer job", expires_on="2026-06-16", enabled=True, id="c1")
    coord = _coord([c])
    _run_on(coord, dt.date(2026, 6, 17))  # day after expiry
    assert c.enabled is False
    coord.storage.update_chore.assert_called_once()


def test_still_enabled_on_expiry_day():
    c = Chore(name="Lasts today", expires_on="2026-06-17", enabled=True, id="c1")
    coord = _coord([c])
    _run_on(coord, dt.date(2026, 6, 17))  # inclusive — still valid
    assert c.enabled is True
    coord.storage.update_chore.assert_not_called()


def test_no_expiry_date_ignored():
    c = Chore(name="Forever", expires_on="", enabled=True, id="c1")
    coord = _coord([c])
    _run_on(coord, dt.date(2026, 6, 17))
    assert c.enabled is True


def test_already_disabled_skipped():
    c = Chore(name="Done", expires_on="2020-01-01", enabled=False, id="c1")
    coord = _coord([c])
    _run_on(coord, dt.date(2026, 6, 17))
    coord.storage.update_chore.assert_not_called()


def test_bad_date_ignored():
    c = Chore(name="Oops", expires_on="not-a-date", enabled=True, id="c1")
    coord = _coord([c])
    _run_on(coord, dt.date(2026, 6, 17))
    assert c.enabled is True


def test_expires_on_round_trips():
    c = Chore(name="X", expires_on="2026-12-31")
    assert Chore.from_dict(c.to_dict()).expires_on == "2026-12-31"
