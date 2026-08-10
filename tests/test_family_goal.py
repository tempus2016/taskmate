"""Tests for the family co-op goal (FEAT-4)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child


def _coord(children, settings):
    c = object.__new__(TaskMateCoordinator)
    s = MagicMock()
    s.get_children = MagicMock(return_value=children)
    s.get_setting = MagicMock(side_effect=lambda k, d=None: settings.get(k, d))
    s.set_setting = MagicMock(side_effect=lambda k, v: settings.__setitem__(k, v))
    s.async_save = AsyncMock()
    c.storage = s
    c.hass = MagicMock()
    c.notifications = MagicMock()
    c.notifications.fire = AsyncMock()
    return c


def _kids(*points):
    return [Child(name=f"k{i}", id=f"k{i}", points=p) for i, p in enumerate(points)]


def test_progress_is_combined_points():
    c = _coord(_kids(100, 250, 50), {})
    assert c.family_goal_progress() == 400


@pytest.mark.asyncio
async def test_goal_fires_when_reached():
    settings = {
        "family_goal_enabled": True,
        "family_goal_target": 300,
        "family_goal_name": "Movie",
        "family_goal_reward": "popcorn",
    }
    c = _coord(_kids(150, 200), settings)  # 350 >= 300
    await c._async_check_family_goal()
    assert settings.get("family_goal_achieved") is True
    c.notifications.fire.assert_awaited_once()
    args = c.notifications.fire.await_args[0]
    assert args[0] == "family_goal_reached"
    assert args[1]["goal_name"] == "Movie" and args[1]["goal_reward"] == "popcorn"
    c.hass.bus.async_fire.assert_called_once()


@pytest.mark.asyncio
async def test_goal_not_fired_below_target():
    settings = {"family_goal_enabled": True, "family_goal_target": 1000}
    c = _coord(_kids(100, 100), settings)
    await c._async_check_family_goal()
    assert settings.get("family_goal_achieved") is None
    c.notifications.fire.assert_not_awaited()


@pytest.mark.asyncio
async def test_goal_only_fires_once():
    settings = {"family_goal_enabled": True, "family_goal_target": 100, "family_goal_achieved": True}
    c = _coord(_kids(500), settings)
    await c._async_check_family_goal()
    c.notifications.fire.assert_not_awaited()


@pytest.mark.asyncio
async def test_goal_skipped_when_disabled():
    settings = {"family_goal_enabled": False, "family_goal_target": 10}
    c = _coord(_kids(500), settings)
    await c._async_check_family_goal()
    c.notifications.fire.assert_not_awaited()
