"""Tests for the pending-approvals binary sensor."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate.binary_sensor import HasPendingApprovalsBinarySensor


def _make_sensor(pending_completions=None, pending_reward_claims=None):
    """Build a HasPendingApprovalsBinarySensor with a stubbed coordinator/entry."""
    coordinator = MagicMock()
    coordinator.data = {
        "pending_completions": pending_completions or [],
        "pending_reward_claims": pending_reward_claims or [],
    }
    entry = MagicMock()
    entry.entry_id = "test-entry"
    return HasPendingApprovalsBinarySensor(coordinator, entry)


def test_is_off_when_no_pending_items():
    sensor = _make_sensor()
    assert sensor.is_on is False
    assert sensor.icon == "mdi:bell-check"


def test_is_on_when_pending_chore_completion():
    sensor = _make_sensor(pending_completions=[{"id": "c1"}])
    assert sensor.is_on is True
    assert sensor.icon == "mdi:bell-alert"


def test_is_on_when_pending_reward_claim():
    sensor = _make_sensor(pending_reward_claims=[{"id": "r1"}])
    assert sensor.is_on is True


def test_extra_state_attributes_reports_counts():
    sensor = _make_sensor(
        pending_completions=[{"id": "c1"}, {"id": "c2"}],
        pending_reward_claims=[{"id": "r1"}],
    )
    attrs = sensor.extra_state_attributes
    assert attrs["pending_chore_completions"] == 2
    assert attrs["pending_reward_claims"] == 1
    assert attrs["total_pending"] == 3


def test_unique_id_includes_entry_id():
    sensor = _make_sensor()
    assert sensor._attr_unique_id == "test-entry_has_pending_approvals"
