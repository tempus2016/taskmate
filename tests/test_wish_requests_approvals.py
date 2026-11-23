"""New wishes on the pending-approvals sensors (#1284).

The parent dashboard reads `wish_requests` off sensor.taskmate_pending_approvals
to approve or decline a child's new wish without the admin panel; the wish
also counts as something waiting for a parent on both approval sensors.
"""

from __future__ import annotations

import datetime as dt
from datetime import timezone
from unittest.mock import MagicMock

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.binary_sensor import HasPendingApprovalsBinarySensor
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Wish

T0 = dt.datetime(2026, 11, 20, 8, 0, tzinfo=timezone.utc)
MIA = Child(name="Mia", id="k1")


def _coord(wishes, children=(MIA,)):
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_wishes.return_value = list(wishes)
    coord.storage.get_swap_requests.return_value = []
    by_id = {c.id: c for c in children}
    coord.storage.get_child.side_effect = by_id.get
    coord.data = {"pending_completions": [], "pending_reward_claims": []}
    coord.mandatory_misses_state = MagicMock(return_value=[])
    coord.quality_rating_enabled = MagicMock(return_value=False)
    return coord


def _sensor(coord):
    return sensor_module.PendingApprovalsSensor(coord, MagicMock(entry_id="e1"))


def test_a_pending_wish_is_listed_compactly_and_counted():
    wishes = [
        Wish(child_id="k1", name="Bike", target=500, id="w2", created_at=T0 + dt.timedelta(hours=1)),
        Wish(
            child_id="k1",
            name="Lego",
            target=250,
            id="w1",
            created_at=T0,
            link="https://example.com/lego",
            image_url="/api/taskmate/image/a.jpg",
        ),
        Wish(child_id="k1", name="Saving", target=50, id="w3", status="active"),
        Wish(child_id="k1", name="No", target=50, id="w4", status="declined"),
    ]
    sensor = _sensor(_coord(wishes))
    attrs = sensor.extra_state_attributes
    assert attrs["pending_wish_requests"] == 2
    # Oldest first, and only the fields that are set.
    assert attrs["wish_requests"] == [
        {
            "wish_id": "w1",
            "type": "wish",
            "child_id": "k1",
            "child_name": "Mia",
            "wish_name": "Lego",
            "target": 250,
            "requested_at": T0.isoformat(),
            "link": "https://example.com/lego",
            "image_url": "/api/taskmate/image/a.jpg",
        },
        {
            "wish_id": "w2",
            "type": "wish",
            "child_id": "k1",
            "child_name": "Mia",
            "wish_name": "Bike",
            "target": 500,
            "requested_at": (T0 + dt.timedelta(hours=1)).isoformat(),
        },
    ]
    assert sensor.native_value == 2


def test_no_pending_wish_leaves_the_attributes_out():
    attrs = _sensor(_coord([Wish(child_id="k1", name="Bike", target=5, status="active")])).extra_state_attributes
    assert "wish_requests" not in attrs
    assert "pending_wish_requests" not in attrs


def test_a_wish_whose_child_has_gone_is_left_out():
    sensor = _sensor(_coord([Wish(child_id="gone", name="Bike", target=5)]))
    assert "wish_requests" not in sensor.extra_state_attributes
    assert sensor.native_value == 0


def test_the_wish_list_is_kept_out_of_the_recorder():
    assert "wish_requests" in sensor_module.PendingApprovalsSensor._unrecorded_attributes


def test_binary_sensor_turns_on_for_a_pending_wish():
    coordinator = MagicMock()
    coordinator.data = {"pending_completions": [], "pending_reward_claims": []}
    coordinator.storage.get_swap_requests.return_value = []
    coordinator.storage.get_wishes.return_value = [
        Wish(child_id="k1", name="Bike", target=5),
        Wish(child_id="k1", name="Old", target=5, status="active"),
    ]
    sensor = HasPendingApprovalsBinarySensor(coordinator, MagicMock(entry_id="e1"))
    assert sensor.is_on is True
    attrs = sensor.extra_state_attributes
    assert attrs["pending_wish_requests"] == 1
    assert attrs["total_pending"] == 1
