"""Backend admin gate for parent-privileged service calls (issue #410).

The `complete_chore` service's `as_parent` path must enforce admin on the
backend, not just hide the control in the UI. These cover the shared
`_async_require_admin` helper that both the `_admin` wrapper and the
as_parent branch use.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.taskmate as tm


def _call(user_id):
    call = MagicMock()
    call.context.user_id = user_id
    return call


def _hass(user):
    hass = MagicMock()
    hass.auth.async_get_user = AsyncMock(return_value=user)
    return hass


@pytest.mark.asyncio
async def test_passes_without_user_context():
    """Automations/scripts/schedules (no user_id) pass through untouched."""
    hass = _hass(None)
    await tm._async_require_admin(hass, _call(None))
    hass.auth.async_get_user.assert_not_called()


@pytest.mark.asyncio
async def test_allows_admin_user():
    admin = MagicMock(is_admin=True)
    await tm._async_require_admin(_hass(admin), _call("uid-admin"))


@pytest.mark.asyncio
async def test_rejects_non_admin_user():
    non_admin = MagicMock(is_admin=False)
    with pytest.raises(tm.Unauthorized):
        await tm._async_require_admin(_hass(non_admin), _call("uid-child"))


@pytest.mark.asyncio
async def test_rejects_unknown_user():
    """A user_id that no longer resolves to a user is rejected, not allowed."""
    with pytest.raises(tm.Unauthorized):
        await tm._async_require_admin(_hass(None), _call("uid-ghost"))


# ---------------------------------------------------------------------------
# SEC-3: mutating service calls are recorded in the admin audit log
# ---------------------------------------------------------------------------


def _audit_call(user_id, service, data):
    call = MagicMock()
    call.context.user_id = user_id
    call.service = service
    call.data = data
    return call


@pytest.mark.asyncio
async def test_service_audit_records_with_child_name(monkeypatch):
    coordinator = MagicMock()
    coordinator.get_child = MagicMock(return_value=MagicMock(name="x"))
    coordinator.get_child.return_value.name = "Malia"
    coordinator.async_record_audit = AsyncMock()
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)
    hass = _hass(MagicMock(name="Parent"))
    hass.auth.async_get_user.return_value.name = "Parent"
    await tm._async_record_service_audit(hass, _audit_call("uid-admin", "add_points", {"child_id": "c1", "points": 5}))
    coordinator.async_record_audit.assert_awaited_once()
    args = coordinator.async_record_audit.await_args.args
    assert args[0] == "uid-admin"
    assert args[2] == "service.add_points"
    assert args[3] == "Malia"


@pytest.mark.asyncio
async def test_service_audit_falls_back_to_id_target(monkeypatch):
    coordinator = MagicMock()
    coordinator.async_record_audit = AsyncMock()
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)
    hass = _hass(None)
    await tm._async_record_service_audit(hass, _audit_call(None, "add_chore", {"chore_id": "ch9"}))
    args = coordinator.async_record_audit.await_args.args
    assert args[2] == "service.add_chore"
    assert args[3] == "chore_id=ch9"


@pytest.mark.asyncio
async def test_service_audit_noop_without_coordinator(monkeypatch):
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: None)
    # must not raise
    await tm._async_record_service_audit(_hass(None), _audit_call("u", "add_points", {}))
