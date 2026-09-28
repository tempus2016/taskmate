"""Removing a child or parent takes everything of theirs with them (#946).

Deleting a child used to leave their notification routes, missed-mandatory
records and registry entities behind; deleting a parent recipient left their
routes. Installs that deleted people before the fix are swept on load.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.taskmate.coordinator as coord_mod
from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import (
    Child,
    CustomNotification,
    MandatoryMiss,
    ParentRecipient,
    TimedSession,
)
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import FakeStore

ENTRY = "entry1"
GONE = "aaaaaaaaaaaaaaaa"
KEPT = "bbbbbbbbbbbbbbbb"


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _storage(data: dict) -> TaskMateStorage:
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = ENTRY
    storage._store = FakeStore(None, 1, "test")
    storage._data = data
    storage._data_version = 0
    return storage


class FakeRegistry:
    """Entity registry holding (entity_id, unique_id) pairs for one entry."""

    def __init__(self, unique_ids: list[str]):
        self.entries = {f"sensor.e{i}": uid for i, uid in enumerate(unique_ids)}

    def async_remove(self, entity_id: str) -> None:
        self.entries.pop(entity_id)

    def remaining(self) -> set[str]:
        return set(self.entries.values())


@pytest.fixture
def registry(monkeypatch):
    reg = FakeRegistry([])
    fake_er = SimpleNamespace(
        async_get=lambda hass: reg,
        async_entries_for_config_entry=lambda r, entry_id: [
            SimpleNamespace(entity_id=eid, unique_id=uid) for eid, uid in list(r.entries.items())
        ],
    )
    monkeypatch.setattr(coord_mod, "er", fake_er)
    return reg


def _coord(storage: TaskMateStorage) -> TaskMateCoordinator:
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.data = {}
    coord.entry_id = ENTRY
    coord.storage = storage
    coord.notifications = MagicMock()
    coord.notifications.async_setup_schedules = AsyncMock()
    coord.async_refresh = AsyncMock()
    return coord


def _family() -> dict:
    """Two children, two parents, each routed and owing something."""
    return {
        "children": [Child(name="Gone", id=GONE).to_dict(), Child(name="Kept", id=KEPT).to_dict()],
        "chores": [],
        "completions": [],
        "parent_recipients": [
            ParentRecipient(name="Mum", notify_service="notify.mum", id="parent:mum").to_dict(),
            ParentRecipient(name="Dad", notify_service="notify.dad", id="parent:dad").to_dict(),
        ],
        "notification_config": {
            "bedtime_reminder": {
                "type_id": "bedtime_reminder",
                "master_enabled": True,
                "routes": {
                    f"child:{GONE}": {"enabled": True, "time": "19:30"},
                    f"child:{KEPT}": {"enabled": True, "time": "20:00"},
                },
            },
            "pending_chore_approval": {
                "type_id": "pending_chore_approval",
                "master_enabled": True,
                "routes": {"parent:mum": {"enabled": True}, "parent:dad": {"enabled": True}},
            },
        },
        "custom_notifications": [
            CustomNotification(
                name="Teeth",
                message_template="Brush",
                time="19:00",
                recipient_ids=[f"child:{GONE}", f"child:{KEPT}", "parent:mum", "parent:dad"],
                id="c1",
            ).to_dict()
        ],
        "mandatory_misses": [
            MandatoryMiss(chore_id="ch1", child_id=GONE, due_date="2026-09-27", period_id="anytime").to_dict(),
            MandatoryMiss(chore_id="ch1", child_id=KEPT, due_date="2026-09-27", period_id="anytime").to_dict(),
        ],
        "timed_sessions": [
            TimedSession(chore_id="ch1", child_id=GONE, session_date="2026-09-28").to_dict(),
            TimedSession(chore_id="ch1", child_id=KEPT, session_date="2026-09-28").to_dict(),
        ],
        "settings": {
            "birthday_celebrated": {GONE: "2026-09-28", KEPT: "2026-03-01"},
            "recap_child_frequencies": {GONE: ["weekly"], KEPT: ["monthly"]},
        },
    }


def _route_ids(storage: TaskMateStorage) -> set[str]:
    return {rid for cfg in storage.get_all_notification_configs().values() for rid in cfg.routes}


def _per_child_uids(child_id: str) -> list[str]:
    return [
        f"{ENTRY}_{child_id}_points",
        f"{ENTRY}_{child_id}_stats",
        f"{ENTRY}_{child_id}_badges",
        f"{ENTRY}_{child_id}_wishlist",
        f"{ENTRY}_{child_id}_calendar",
        f"{ENTRY}_{child_id}_todo",
        f"{ENTRY}_{child_id}_cccccccccccccccc_complete",
        f"{ENTRY}_{child_id}_dddddddddddddddd_claim",
    ]


GLOBAL_UIDS = [
    f"{ENTRY}_overall_stats",
    f"{ENTRY}_chores",
    f"{ENTRY}_pending_approvals",
    f"{ENTRY}_setting_chore_undo_seconds",
    f"{ENTRY}_has_pending_approvals",
]


# ── removing a child ────────────────────────────────────────────────────────


def test_removing_child_drops_their_routes_everywhere(registry):
    storage = _storage(_family())
    run(_coord(storage).async_remove_child(GONE))

    assert _route_ids(storage) == {f"child:{KEPT}", "parent:mum", "parent:dad"}
    assert storage.get_custom_notifications()[0].recipient_ids == [f"child:{KEPT}", "parent:mum", "parent:dad"]


def test_removing_child_rearms_schedules_when_a_route_went(registry):
    storage = _storage(_family())
    coord = _coord(storage)
    run(coord.async_remove_child(GONE))
    coord.notifications.async_setup_schedules.assert_awaited_once()


def test_removing_unrouted_child_leaves_schedules_alone(registry):
    data = _family()
    data["notification_config"] = {}
    data["custom_notifications"] = []
    coord = _coord(_storage(data))
    run(coord.async_remove_child(GONE))
    coord.notifications.async_setup_schedules.assert_not_awaited()


def test_removing_child_drops_their_mandatory_misses(registry):
    storage = _storage(_family())
    run(_coord(storage).async_remove_child(GONE))
    assert [m.child_id for m in storage.get_mandatory_misses()] == [KEPT]


def test_removing_child_drops_their_timed_sessions(registry):
    storage = _storage(_family())
    run(_coord(storage).async_remove_child(GONE))
    assert [s.child_id for s in storage.get_timed_sessions()] == [KEPT]


def test_removing_child_drops_their_per_child_settings(registry):
    storage = _storage(_family())
    run(_coord(storage).async_remove_child(GONE))
    assert storage.get_setting("birthday_celebrated") == {KEPT: "2026-03-01"}
    assert storage.get_setting("recap_child_frequencies") == {KEPT: ["monthly"]}


def test_removing_child_drops_their_kiosk_pin(registry):
    storage = _storage(_family())
    storage.set_kiosk_pin_hash(GONE, "hash-gone")
    storage.set_kiosk_pin_hash(KEPT, "hash-kept")
    run(_coord(storage).async_remove_child(GONE))
    assert storage.get_kiosk_pin_child_ids() == [KEPT]


def test_removing_child_removes_only_their_entities(registry):
    registry.entries = {
        f"sensor.e{i}": uid for i, uid in enumerate(_per_child_uids(GONE) + _per_child_uids(KEPT) + GLOBAL_UIDS)
    }
    run(_coord(_storage(_family())).async_remove_child(GONE))
    assert registry.remaining() == set(_per_child_uids(KEPT) + GLOBAL_UIDS)


# ── removing a parent ───────────────────────────────────────────────────────


def test_deleting_parent_drops_their_routes(hass):
    storage = _storage(_family())
    notif = NotificationCoordinator(hass, storage)
    notif.async_setup_schedules = AsyncMock()

    run(notif.delete_parent("parent:mum"))

    assert [p.id for p in storage.get_parent_recipients()] == ["parent:dad"]
    assert _route_ids(storage) == {f"child:{GONE}", f"child:{KEPT}", "parent:dad"}
    assert "parent:mum" not in storage.get_custom_notifications()[0].recipient_ids


def test_remove_notification_recipient_reports_no_change_for_a_stranger():
    storage = _storage(_family())
    assert storage.remove_notification_recipient("child:nobody") is False
    assert storage.remove_notification_recipient("parent:dad") is True


# ── sweeping installs affected before the fix ────────────────────────────────


def _orphaned_install() -> dict:
    """Storage as a pre-fix install leaves it: GONE and parent:mum were deleted."""
    data = _family()
    data["children"] = [c for c in data["children"] if c["id"] != GONE]
    data["parent_recipients"] = [p for p in data["parent_recipients"] if p["id"] != "parent:mum"]
    data["notifications_migration_done"] = True
    return data


def test_load_prunes_routes_of_deleted_people(hass):
    storage = TaskMateStorage(hass, ENTRY)
    storage._store._data = _orphaned_install()
    run(storage.async_load())

    assert _route_ids(storage) == {f"child:{KEPT}", "parent:dad"}
    assert storage.get_custom_notifications()[0].recipient_ids == [f"child:{KEPT}", "parent:dad"]


def test_load_prunes_mandatory_misses_of_deleted_children(hass):
    storage = TaskMateStorage(hass, ENTRY)
    storage._store._data = _orphaned_install()
    run(storage.async_load())
    assert [m.child_id for m in storage.get_mandatory_misses()] == [KEPT]


def test_load_leaves_unprefixed_route_keys_alone(hass):
    data = _orphaned_install()
    data["notification_config"]["bedtime_reminder"]["routes"]["something_else"] = {"enabled": True}
    storage = TaskMateStorage(hass, ENTRY)
    storage._store._data = data
    run(storage.async_load())
    assert "something_else" in _route_ids(storage)


def test_setup_prunes_entities_of_already_deleted_children(registry):
    registry.entries = {
        f"sensor.e{i}": uid for i, uid in enumerate(_per_child_uids(GONE) + _per_child_uids(KEPT) + GLOBAL_UIDS)
    }
    coord = _coord(_storage(_orphaned_install()))
    assert coord.async_prune_orphan_child_entities() == len(_per_child_uids(GONE))
    assert registry.remaining() == set(_per_child_uids(KEPT) + GLOBAL_UIDS)


def test_orphan_entity_sweep_ignores_other_entries_and_non_id_segments(registry):
    """Only generated-id-shaped segments are judged; another entry is untouched."""
    others = [f"other_{GONE}_points", f"{ENTRY}_notanid_points", f"{ENTRY}_{GONE}"]
    registry.entries = {f"sensor.e{i}": uid for i, uid in enumerate(others + GLOBAL_UIDS)}
    coord = _coord(_storage(_orphaned_install()))
    assert coord.async_prune_orphan_child_entities() == 0
    assert registry.remaining() == set(others + GLOBAL_UIDS)
