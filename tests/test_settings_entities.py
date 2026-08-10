"""Tests for the number/select config-setting entities (FEAT-9)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.number import TaskMateSettingNumber
from custom_components.taskmate.select import TaskMateSettingSelect


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(settings=None):
    s = settings or {}
    coord = MagicMock()
    coord.storage.get_setting = MagicMock(side_effect=lambda k, d=None: s.get(k, d))
    coord.storage.set_setting = MagicMock(side_effect=lambda k, v: s.__setitem__(k, v))
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    return coord, s


def _entry():
    e = MagicMock()
    e.entry_id = "e1"
    return e


def test_number_reads_default_and_value():
    coord, _ = _coord({"weekend_multiplier": "2.0"})
    num = TaskMateSettingNumber(
        coord, _entry(), "weekend_multiplier", "weekend_multiplier", 1.0, 5.0, 0.5, 1.0, "mdi:x"
    )
    assert num._attr_unique_id == "e1_setting_weekend_multiplier"
    assert num.native_value == 2.0
    # missing setting -> default
    coord2, _ = _coord({})
    num2 = TaskMateSettingNumber(
        coord2, _entry(), "weekend_multiplier", "weekend_multiplier", 1.0, 5.0, 0.5, 1.0, "mdi:x"
    )
    assert num2.native_value == 1.0


def test_number_set_persists_int_when_integer():
    coord, store = _coord({})
    num = TaskMateSettingNumber(coord, _entry(), "perfect_week_bonus", "perfect_week_bonus", 0, 1000, 1, 0, "mdi:x")
    run(num.async_set_native_value(25.0))
    assert store["perfect_week_bonus"] == 25
    assert isinstance(store["perfect_week_bonus"], int)
    coord.async_refresh.assert_awaited_once()


def test_number_set_keeps_float_step():
    coord, store = _coord({})
    num = TaskMateSettingNumber(
        coord, _entry(), "weekend_multiplier", "weekend_multiplier", 1.0, 5.0, 0.5, 1.0, "mdi:x"
    )
    run(num.async_set_native_value(1.5))
    assert store["weekend_multiplier"] == 1.5


def test_select_current_option_falls_back_for_invalid():
    coord, _ = _coord({"streak_reset_mode": "bogus"})
    sel = TaskMateSettingSelect(
        coord, _entry(), "streak_reset_mode", "streak_reset_mode", ["reset", "pause"], "reset", "mdi:x"
    )
    assert sel.current_option == "reset"
    coord2, _ = _coord({"streak_reset_mode": "pause"})
    sel2 = TaskMateSettingSelect(
        coord2, _entry(), "streak_reset_mode", "streak_reset_mode", ["reset", "pause"], "reset", "mdi:x"
    )
    assert sel2.current_option == "pause"


def test_select_set_persists_and_rejects_invalid():
    coord, store = _coord({})
    sel = TaskMateSettingSelect(
        coord, _entry(), "card_design", "card_design", ["classic", "playroom"], "classic", "mdi:x"
    )
    run(sel.async_select_option("playroom"))
    assert store["card_design"] == "playroom"
    run(sel.async_select_option("hacker"))  # invalid -> ignored
    assert store["card_design"] == "playroom"
