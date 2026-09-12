"""Tests for the admin audit log."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.storage import TaskMateStorage


# ── storage ──────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_storage_append_order_and_cap(hass):
    storage = TaskMateStorage(hass, "audit")
    await storage.async_load()
    for i in range(550):
        storage.add_audit_entry({"id": str(i), "action": "x", "target": str(i)})
    log = storage.get_audit_log()
    assert len(log) == 500  # capped
    assert log[0]["id"] == "549"  # newest first
    assert log[-1]["id"] == "50"  # oldest 50 dropped


@pytest.mark.asyncio
async def test_storage_clear(hass):
    storage = TaskMateStorage(hass, "audit2")
    await storage.async_load()
    storage.add_audit_entry({"id": "1", "action": "x"})
    storage.clear_audit_log()
    assert storage.get_audit_log() == []


# ── coordinator.async_record_audit ────────────────────────────────────────
@pytest.mark.asyncio
async def test_record_audit_builds_entry_and_saves():
    coord = object.__new__(TaskMateCoordinator)
    storage = MagicMock()
    storage.add_audit_entry = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    await coord.async_record_audit("u1", "John", "add_chore", "Tidy room")
    storage.add_audit_entry.assert_called_once()
    entry = storage.add_audit_entry.call_args[0][0]
    assert entry["user_id"] == "u1"
    assert entry["user_name"] == "John"
    assert entry["action"] == "add_chore"
    assert entry["target"] == "Tidy room"
    assert entry["id"] and entry["ts"]
    storage.async_save.assert_awaited_once()


# ── _audit_target ─────────────────────────────────────────────────────────
def _named(name):
    m = MagicMock()
    m.name = name
    return m


def _coord_with_lookups():
    coord = MagicMock()
    coord.get_chore = MagicMock(return_value=_named("Tidy"))
    coord.get_child = MagicMock(return_value=_named("Mia"))
    coord.get_reward = MagicMock(return_value=None)
    return coord


def test_audit_target_prefers_name():
    assert ws._audit_target(_coord_with_lookups(), {"name": "  New Chore "}) == "New Chore"


def test_audit_target_resolves_chore_name():
    assert ws._audit_target(_coord_with_lookups(), {"chore_id": "c1"}) == "Tidy"


def test_audit_target_resolves_child_name():
    assert ws._audit_target(_coord_with_lookups(), {"child_id": "c1"}) == "Mia"


def test_audit_target_falls_back_to_id_when_unresolved():
    assert ws._audit_target(_coord_with_lookups(), {"reward_id": "r9"}) == "r9"


def test_audit_target_other_id_fields():
    assert ws._audit_target(_coord_with_lookups(), {"badge_id": "b3"}) == "b3"


def test_audit_target_empty_when_nothing():
    assert ws._audit_target(_coord_with_lookups(), {"foo": "bar"}) == ""


# ── _admin_only wrapper records mutations, skips read-only ─────────────────
def _conn():
    c = MagicMock()
    c.user.is_admin = True
    c.user.id = "admin1"
    c.user.name = "Admin"
    return c


def _hass_with(coord):
    h = MagicMock()
    h.data = {DOMAIN: {"entry": coord}}
    return h


@pytest.mark.asyncio
async def test_wrapper_audits_mutation():
    coord = object.__new__(TaskMateCoordinator)
    coord.async_record_audit = AsyncMock()
    coord.get_chore = MagicMock(return_value=None)
    coord.get_child = MagicMock(return_value=None)
    coord.get_reward = MagicMock(return_value=None)

    @ws._admin_only
    async def handler(hass, connection, msg, coordinator):
        connection.send_result(msg["id"], {"ok": True})

    await handler(_hass_with(coord), _conn(), {"id": 1, "type": "taskmate/add_chore", "name": "Bin"})
    coord.async_record_audit.assert_awaited_once()
    args = coord.async_record_audit.await_args[0]
    assert args[0] == "admin1" and args[2] == "add_chore" and args[3] == "Bin"


@pytest.mark.asyncio
async def test_wrapper_skips_readonly():
    coord = object.__new__(TaskMateCoordinator)
    coord.async_record_audit = AsyncMock()

    @ws._admin_only
    async def handler(hass, connection, msg, coordinator):
        connection.send_result(msg["id"], {"ok": True})

    await handler(_hass_with(coord), _conn(), {"id": 1, "type": "taskmate/get_state"})
    coord.async_record_audit.assert_not_awaited()


@pytest.mark.asyncio
async def test_wrapper_does_not_audit_on_handler_error():
    coord = object.__new__(TaskMateCoordinator)
    coord.async_record_audit = AsyncMock()

    @ws._admin_only
    async def handler(hass, connection, msg, coordinator):
        raise ValueError("boom")

    await handler(_hass_with(coord), _conn(), {"id": 1, "type": "taskmate/add_chore", "name": "x"})
    coord.async_record_audit.assert_not_awaited()


# ---------------------------------------------------------------------------
# child-facing mutations are audited too, and truncation is visible
# ---------------------------------------------------------------------------


def test_child_facing_services_are_audited():
    """The actions a child can drive are exactly the ones worth reviewing."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "__init__.py").read_text(
        encoding="utf-8"
    )

    for handler in (
        "handle_complete_chore",
        "handle_complete_bonus_subtask",
        "handle_claim_reward",
        "handle_allocate_points_to_pool",
        "handle_spin_roulette",
        "handle_choose_avatar",
        "handle_request_swap",
        "handle_start_timed_task",
        "handle_stop_timed_task",
    ):
        assert f"_audited({handler})" in src, f"{handler} is not audited"

    # …and the wrapper really does record.
    block = src[src.index("def _audited(handler):") : src.index("def _parent(handler):")]
    assert "_async_record_service_audit(hass, call)" in block


def test_dropped_audit_entries_are_counted():
    from custom_components.taskmate.storage import TaskMateStorage

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage._data = {}
    for i in range(520):
        storage.add_audit_entry({"id": str(i), "action": "service.test"})

    assert len(storage._data["audit_log"]) == 500
    assert storage.get_audit_dropped_count() == 20
    # The oldest really are gone — the count is what makes that visible.
    assert storage._data["audit_log"][0]["id"] == "20"


def test_clearing_the_log_resets_the_dropped_counter():
    from custom_components.taskmate.storage import TaskMateStorage

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage._data = {}
    for i in range(505):
        storage.add_audit_entry({"id": str(i), "action": "service.test"})
    assert storage.get_audit_dropped_count() == 5

    storage.clear_audit_log()
    assert storage.get_audit_dropped_count() == 0
