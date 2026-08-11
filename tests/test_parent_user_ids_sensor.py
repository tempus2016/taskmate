"""Overview sensor publishes parent_user_ids so cards can unlock controls (#661)."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate.sensor import TaskMateOverallStatsSensor

from .test_sensor_attributes import _stress_coordinator


def test_overview_exposes_parent_user_ids_default_empty():
    coord = _stress_coordinator()
    coord.storage.get_parent_user_ids = MagicMock(return_value=[])
    attrs = TaskMateOverallStatsSensor(coord, MagicMock())._build_attributes()
    assert attrs["parent_user_ids"] == []


def test_overview_reflects_stored_parent_user_ids():
    coord = _stress_coordinator()
    coord.storage.get_parent_user_ids = MagicMock(return_value=["mum-uid", "gran-uid"])
    attrs = TaskMateOverallStatsSensor(coord, MagicMock())._build_attributes()
    assert attrs["parent_user_ids"] == ["mum-uid", "gran-uid"]
