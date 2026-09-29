"""Notification bus events must not reuse a feature event's name (#1014).

A feature that fires ``taskmate_<x>`` itself and also sends notification
type ``x`` used to put two ``taskmate_<x>`` events on the bus, so an
automation on it ran twice.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coord_notifications import (
    _OWN_EVENT_TYPES,
    NOTIFICATION_TYPES_BY_ID,
    NotificationCoordinator,
    notification_event_name,
)
from custom_components.taskmate.storage import TaskMateStorage

PKG = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"


def _feature_event_names() -> set[str]:
    """Every literal ``"taskmate_<x>"`` string in the integration's Python."""
    names: set[str] = set()
    for path in PKG.glob("*.py"):
        names |= set(re.findall(r'"taskmate_(\w+)"', path.read_text(encoding="utf-8")))
    return names


def test_own_event_types_match_the_features_that_fire_them():
    clashing = set(NOTIFICATION_TYPES_BY_ID) & _feature_event_names()
    assert clashing == set(_OWN_EVENT_TYPES)


def test_no_notification_event_reuses_a_feature_event_name():
    features = {f"taskmate_{n}" for n in _feature_event_names()}
    for type_id in NOTIFICATION_TYPES_BY_ID:
        assert notification_event_name(type_id) not in features, type_id


def test_older_types_keep_their_event_name():
    assert notification_event_name("pending_chore_approval") == "taskmate_pending_chore_approval"
    assert notification_event_name("weekly_digest") == "taskmate_weekly_digest"


@pytest.mark.asyncio
@pytest.mark.parametrize("type_id", sorted(_OWN_EVENT_TYPES))
async def test_clashing_type_fires_renamed_event(hass, type_id):
    storage = TaskMateStorage(hass, "test")
    await storage.async_load()
    coord = NotificationCoordinator(hass, storage)
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = MagicMock()
    storage.set_notification_master(type_id, False)

    await coord.fire(type_id, {"child_name": "M"})

    hass.bus.async_fire.assert_called_once()
    name, payload = hass.bus.async_fire.call_args[0]
    assert name == f"taskmate_{type_id}_notification"
    assert payload["recipients"] == []
