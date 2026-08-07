"""Backend parent gate for day-to-day service calls (issue #661).

Day-to-day parent actions (approve/reject, gift/adjust points, confirm
rewards/allowance, award badges, complete-as-parent) accept HA admins,
context-less calls, *and* non-admin users listed in ``parent_user_ids``.
Structural config stays on ``_async_require_admin``.
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


def _coord_with_parents(parent_ids, monkeypatch):
    coordinator = MagicMock()
    coordinator.storage.get_parent_user_ids = MagicMock(return_value=list(parent_ids))
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)
    return coordinator


@pytest.mark.asyncio
async def test_passes_without_user_context(monkeypatch):
    """Automations/scripts (no user_id) pass through untouched."""
    _coord_with_parents([], monkeypatch)
    hass = _hass(None)
    await tm._async_require_parent(hass, _call(None))
    hass.auth.async_get_user.assert_not_called()


@pytest.mark.asyncio
async def test_allows_admin_user(monkeypatch):
    _coord_with_parents([], monkeypatch)
    admin = MagicMock(is_admin=True)
    await tm._async_require_parent(_hass(admin), _call("uid-admin"))


@pytest.mark.asyncio
async def test_allows_listed_parent(monkeypatch):
    _coord_with_parents(["uid-mum"], monkeypatch)
    mum = MagicMock(is_admin=False)
    await tm._async_require_parent(_hass(mum), _call("uid-mum"))


@pytest.mark.asyncio
async def test_rejects_non_admin_non_parent(monkeypatch):
    _coord_with_parents(["uid-mum"], monkeypatch)
    other = MagicMock(is_admin=False)
    with pytest.raises(tm.Unauthorized):
        await tm._async_require_parent(_hass(other), _call("uid-child"))


@pytest.mark.asyncio
async def test_rejects_unknown_user(monkeypatch):
    """A user_id that no longer resolves to a user is rejected, not allowed."""
    _coord_with_parents(["uid-mum"], monkeypatch)
    with pytest.raises(tm.Unauthorized):
        await tm._async_require_parent(_hass(None), _call("uid-ghost"))


# ---------------------------------------------------------------------------
# Which gate each service is actually wired to (#749)
#
# The gate function above was correct all along; three day-to-day actions were
# just never moved onto it, so a TaskMate parent tapping Apply on a bonus got
# "Failed to perform the action taskmate/apply_bonus. Unauthorized" while the
# quick +points buttons on the same card worked.
# ---------------------------------------------------------------------------


class _Services:
    """Capture the registered handler for each service name."""

    def __init__(self):
        self.handlers = {}

    def async_register(self, domain, name, handler, schema=None):
        self.handlers[name] = handler


async def _handlers(user, parent_ids, monkeypatch):
    """Register the real services against a fake hass and a fake coordinator."""
    coordinator = MagicMock()
    coordinator.storage.get_parent_user_ids = MagicMock(return_value=list(parent_ids))
    coordinator.async_record_audit = AsyncMock()
    for method in (
        "async_apply_bonus", "async_apply_penalty", "async_remove_points",
        "async_add_bonus", "async_update_bonus", "async_remove_bonus",
    ):
        setattr(coordinator, method, AsyncMock())
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)

    services = _Services()
    hass = MagicMock()
    hass.services = services
    hass.auth.async_get_user = AsyncMock(return_value=user)
    await tm._async_register_services(hass)
    return services.handlers, coordinator


def _service_call(user_id, data):
    call = MagicMock()
    call.context.user_id = user_id
    call.data = data
    return call


PARENT_ACTIONS = [
    (tm.SERVICE_APPLY_BONUS, {"bonus_id": "b1", "child_id": "c1"}, "async_apply_bonus"),
    (tm.SERVICE_APPLY_PENALTY, {"penalty_id": "p1", "child_id": "c1"}, "async_apply_penalty"),
    (tm.SERVICE_REMOVE_POINTS, {"child_id": "c1", "points": 5, "reason": ""}, "async_remove_points"),
]


@pytest.mark.parametrize(("service", "data", "method"), PARENT_ACTIONS)
@pytest.mark.asyncio
async def test_parent_may_apply_incentives(service, data, method, monkeypatch):
    """A non-admin TaskMate parent can apply a bonus/penalty and deduct points."""
    mum = MagicMock(is_admin=False)
    handlers, coordinator = await _handlers(mum, ["uid-mum"], monkeypatch)

    await handlers[service](_service_call("uid-mum", data))

    getattr(coordinator, method).assert_awaited()


@pytest.mark.parametrize(("service", "data", "method"), PARENT_ACTIONS)
@pytest.mark.asyncio
async def test_non_parent_may_not_apply_incentives(service, data, method, monkeypatch):
    """A child (non-admin, not a listed parent) is still rejected."""
    kid = MagicMock(is_admin=False)
    handlers, coordinator = await _handlers(kid, ["uid-mum"], monkeypatch)

    with pytest.raises(tm.Unauthorized):
        await handlers[service](_service_call("uid-child", data))

    getattr(coordinator, method).assert_not_awaited()


@pytest.mark.parametrize("service", ["add_bonus", "update_bonus", "remove_bonus"])
@pytest.mark.asyncio
async def test_defining_incentives_stays_admin_only(service, monkeypatch):
    """Creating/editing/deleting a bonus is structural config: admin only."""
    mum = MagicMock(is_admin=False)
    handlers, _ = await _handlers(mum, ["uid-mum"], monkeypatch)

    with pytest.raises(tm.Unauthorized):
        await handlers[service](_service_call("uid-mum", {"bonus_id": "b1", "name": "x", "points": 5}))
