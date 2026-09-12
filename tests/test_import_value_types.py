"""A restored backup or shared pack must not smuggle wrong value *types*.

The key whitelists on import and on template packs decide which fields survive,
not what they hold. Anything the rest of the app treats as a number has to
actually be a finite number by the time it lands in storage — otherwise it
flows into points arithmetic, the sensor attribute build, and the admin panel's
number inputs, none of which expect a string, a dict, inf or NaN.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage

XSS = '<img src=x onerror="alert(1)">'


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── backup import ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_coerces_chore_numbers(hass):
    storage = TaskMateStorage(hass, "imp1")
    await storage.async_load()
    storage.import_data(
        {
            "chores": [
                {
                    "id": "c1",
                    "name": "Tidy room",
                    "points": XSS,
                    "daily_limit": {"nested": 1},
                    "timed_rate_minutes": "5",
                    "bonus_subtasks": [{"id": "b1", "name": "Hoover", "points": XSS}],
                }
            ]
        }
    )
    chore = storage._data["chores"][0]
    assert chore["points"] == 0
    assert chore["daily_limit"] == 0
    assert chore["timed_rate_minutes"] == 5  # a numeric string is fine, coerced
    assert chore["bonus_subtasks"][0]["points"] == 0
    # The escape hatch is gone: nothing numeric is a string any more.
    assert not isinstance(chore["points"], str)


@pytest.mark.asyncio
async def test_import_coerces_child_reward_and_badge_numbers(hass):
    storage = TaskMateStorage(hass, "imp2")
    await storage.async_load()
    storage.import_data(
        {
            "children": [{"id": "k1", "name": "Alice", "points": XSS, "current_streak": "abc"}],
            "rewards": [{"id": "r1", "name": "Movie", "cost": XSS, "quantity": "many"}],
            "badges": [{"id": "b1", "name": "Star", "criteria": [{"metric": "points", "value": XSS}]}],
            "points_transactions": [{"id": "t1", "child_id": "k1", "points": XSS}],
        }
    )
    assert storage._data["children"][0]["points"] == 0
    assert storage._data["children"][0]["current_streak"] == 0
    assert storage._data["rewards"][0]["cost"] == 0
    assert storage._data["rewards"][0]["quantity"] == 0
    assert storage._data["badges"][0]["criteria"][0]["value"] == 0
    assert storage._data["points_transactions"][0]["points"] == 0


@pytest.mark.asyncio
async def test_import_keeps_unlimited_reward_quantity_as_none(hass):
    storage = TaskMateStorage(hass, "imp3")
    await storage.async_load()
    storage.import_data({"rewards": [{"id": "r1", "name": "Movie", "cost": 5, "quantity": None}]})
    assert storage._data["rewards"][0]["quantity"] is None


@pytest.mark.asyncio
async def test_import_drops_unparseable_timestamps(hass):
    storage = TaskMateStorage(hass, "imp4")
    await storage.async_load()
    storage.import_data(
        {
            "completions": [
                {"id": "x1", "chore_id": "c1", "child_id": "k1", "completed_at": XSS, "approved_at": XSS}
            ]
        }
    )
    comp = storage._data["completions"][0]
    assert comp["completed_at"] == ""
    assert comp["approved_at"] == ""


@pytest.mark.asyncio
async def test_import_keeps_valid_timestamps(hass):
    storage = TaskMateStorage(hass, "imp5")
    await storage.async_load()
    stamp = "2026-06-21T13:00:00+00:00"
    storage.import_data(
        {"completions": [{"id": "x1", "chore_id": "c1", "child_id": "k1", "completed_at": stamp}]}
    )
    assert storage._data["completions"][0]["completed_at"] == stamp


@pytest.mark.asyncio
async def test_import_rejects_non_finite_settings(hass):
    storage = TaskMateStorage(hass, "imp6")
    await storage.async_load()
    storage.import_data({"settings": {"weekend_multiplier": "inf", "level_xp_step": "nan"}})
    settings = storage._data["settings"]
    assert "weekend_multiplier" not in settings
    assert "level_xp_step" not in settings


@pytest.mark.asyncio
async def test_import_leaves_good_data_alone(hass):
    storage = TaskMateStorage(hass, "imp7")
    await storage.async_load()
    storage.import_data(
        {
            "children": [{"id": "k1", "name": "Alice", "points": 120}],
            "chores": [{"id": "c1", "name": "Dishes", "points": 10, "daily_limit": 2}],
            "settings": {"weekend_multiplier": 1.5},
        }
    )
    assert storage._data["children"][0]["points"] == 120
    assert storage._data["chores"][0]["points"] == 10
    assert storage._data["chores"][0]["daily_limit"] == 2
    assert storage._data["settings"]["weekend_multiplier"] == 1.5


# ── template packs ──────────────────────────────────────────────────────────


def _templates_coord():
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    return coord


def _pack(chore):
    return {
        "format": "taskmate.template-pack",
        "version": 1,
        "templates": [{"name": "Morning", "icon": "mdi:x", "chores": [chore]}],
    }


def test_template_pack_coerces_numeric_fields():
    coord = _templates_coord()
    clean = coord._validate_pack(
        _pack({"name": "Make bed", "points": XSS, "daily_limit": "3", "timed_rate_minutes": {"a": 1}})
    )
    chore = clean[0]["chores"][0]
    assert chore["points"] == 10  # falls back to the field default
    assert chore["daily_limit"] == 3
    assert chore["timed_rate_minutes"] == 15


def test_template_pack_rejects_non_finite_numbers():
    coord = _templates_coord()
    clean = coord._validate_pack(_pack({"name": "Make bed", "points": "inf", "daily_limit": "nan"}))
    chore = clean[0]["chores"][0]
    assert chore["points"] == 10
    assert chore["daily_limit"] == 1


def test_template_pack_keeps_optional_numbers_unset():
    coord = _templates_coord()
    clean = coord._validate_pack(_pack({"name": "Wash car", "weather_temp_min": None}))
    assert clean[0]["chores"][0]["weather_temp_min"] is None


def test_template_pack_coerces_optional_numbers():
    coord = _templates_coord()
    clean = coord._validate_pack(_pack({"name": "Wash car", "weather_temp_min": XSS}))
    assert clean[0]["chores"][0]["weather_temp_min"] is None


def test_template_pack_preserves_valid_values():
    coord = _templates_coord()
    clean = coord._validate_pack(
        _pack({"name": "Make bed", "points": 25, "daily_limit": 2, "weather_temp_min": 4.5})
    )
    chore = clean[0]["chores"][0]
    assert chore["points"] == 25
    assert chore["daily_limit"] == 2
    assert chore["weather_temp_min"] == 4.5
