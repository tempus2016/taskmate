"""PERF-4: service-description rebuild is gated by storage.data_version."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from custom_components.taskmate import (
    _async_update_service_descriptions,
)
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator


def _hass_with_coord(version):
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.data_version = version
    for getter in ("get_children", "get_chores", "get_rewards", "get_penalties", "get_bonuses", "get_task_groups"):
        setattr(storage, getter, MagicMock(return_value=[]))
    coord.storage = storage
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": coord}}
    return hass, coord


def test_skips_rebuild_when_version_unchanged():
    hass, coord = _hass_with_coord(version=5)
    with (
        patch("custom_components.taskmate.async_set_service_schema"),
        patch("custom_components.taskmate._load_base_descriptions", return_value={}),
    ):
        _async_update_service_descriptions(hass)  # first pass -> builds
        assert coord.storage.get_children.call_count == 1
        _async_update_service_descriptions(hass)  # same version -> short-circuit
        assert coord.storage.get_children.call_count == 1


def test_rebuilds_after_version_bump():
    hass, coord = _hass_with_coord(version=5)
    with (
        patch("custom_components.taskmate.async_set_service_schema"),
        patch("custom_components.taskmate._load_base_descriptions", return_value={}),
    ):
        _async_update_service_descriptions(hass)
        assert coord.storage.get_children.call_count == 1
        coord.storage.data_version = 6
        _async_update_service_descriptions(hass)  # version changed -> rebuild
        assert coord.storage.get_children.call_count == 2
