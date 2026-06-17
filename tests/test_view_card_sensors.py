"""Tests for the sensor fields that back the read-only view cards."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate import sensor as s
from custom_components.taskmate.models import CustomNotification


def test_custom_reminders_sorted_by_time():
    coord = MagicMock()
    coord.storage.get_custom_notifications = MagicMock(return_value=[
        CustomNotification(name="Evening", message_template="", time="19:00", day_mask=0b1111111, id="n2"),
        CustomNotification(name="Morning", message_template="", time="07:30", day_mask=0b0011111, id="n1"),
    ])
    out = s._build_custom_reminders(coord)
    assert [r["name"] for r in out] == ["Morning", "Evening"]
    assert out[0]["time"] == "07:30"
    assert out[0]["day_mask"] == 0b0011111
    assert out[0]["enabled"] is True


def test_custom_reminders_empty():
    coord = MagicMock()
    coord.storage.get_custom_notifications = MagicMock(return_value=[])
    assert s._build_custom_reminders(coord) == []
