"""Non-admin parents can handle chore swaps outside the admin panel (#1275).

Approving or turning down a swap is a day-to-day parent action, like approving
a chore, so it is a ``_parent`` service rather than an admin-only WebSocket
command. A parent may also ask for a swap on a linked child's behalf, the same
way they can complete a chore for one. A child still can't ask in a sibling's
name.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import custom_components.taskmate as tm


class _Services:
    def __init__(self):
        self.handlers = {}

    def async_register(self, domain, name, handler, schema=None):
        self.handlers[name] = handler


async def _handlers(user, parent_ids, monkeypatch, linked_user_id="uid-kid"):
    """Register the real services against a fake hass and coordinator.

    The requesting child is linked to ``linked_user_id``, as in the report:
    every child has their own HA login.
    """
    coordinator = MagicMock()
    coordinator.storage.get_parent_user_ids = MagicMock(return_value=list(parent_ids))
    coordinator.storage.get_children = MagicMock(return_value=[])
    coordinator.storage.get_require_linked_child = MagicMock(return_value=False)
    coordinator.get_child = MagicMock(return_value=MagicMock(linked_user_id=linked_user_id))
    coordinator.async_record_audit = AsyncMock()
    for method in ("async_approve_swap", "async_reject_swap", "async_request_swap"):
        setattr(coordinator, method, AsyncMock())
    monkeypatch.setattr(tm, "_get_coordinator", lambda hass: coordinator)

    services = _Services()
    hass = MagicMock()
    hass.services = services
    hass.auth.async_get_user = AsyncMock(return_value=user)
    await tm._async_register_services(hass)
    return services.handlers, coordinator


def _call(user_id, data):
    call = MagicMock()
    call.context.user_id = user_id
    call.data = data
    return call


SETTLE = [
    (tm.SERVICE_APPROVE_SWAP, "async_approve_swap"),
    (tm.SERVICE_REJECT_SWAP, "async_reject_swap"),
]


@pytest.mark.parametrize(("service", "method"), SETTLE)
@pytest.mark.asyncio
async def test_listed_parent_may_settle_a_swap(service, method, monkeypatch):
    dad = MagicMock(is_admin=False)
    handlers, coordinator = await _handlers(dad, ["uid-dad"], monkeypatch)

    await handlers[service](_call("uid-dad", {"request_id": "r1"}))

    getattr(coordinator, method).assert_awaited_once_with("r1")


@pytest.mark.parametrize(("service", "method"), SETTLE)
@pytest.mark.asyncio
async def test_admin_may_settle_a_swap(service, method, monkeypatch):
    admin = MagicMock(is_admin=True)
    handlers, coordinator = await _handlers(admin, [], monkeypatch)

    await handlers[service](_call("uid-admin", {"request_id": "r1"}))

    getattr(coordinator, method).assert_awaited_once_with("r1")


@pytest.mark.parametrize(("service", "method"), SETTLE)
@pytest.mark.asyncio
async def test_child_may_not_settle_a_swap(service, method, monkeypatch):
    """The child who asked (or a sibling) can't approve their own swap."""
    kid = MagicMock(is_admin=False)
    handlers, coordinator = await _handlers(kid, ["uid-dad"], monkeypatch)

    with pytest.raises(tm.Unauthorized):
        await handlers[service](_call("uid-kid", {"request_id": "r1"}))

    getattr(coordinator, method).assert_not_awaited()


@pytest.mark.asyncio
async def test_listed_parent_may_request_for_a_linked_child(monkeypatch):
    """The reported failure: a non-admin parent got Unauthorized here."""
    dad = MagicMock(is_admin=False)
    handlers, coordinator = await _handlers(dad, ["uid-dad"], monkeypatch)

    await handlers[tm.SERVICE_REQUEST_SWAP](_call("uid-dad", {"chore_id": "ch1", "requester_id": "kid1"}))

    coordinator.async_request_swap.assert_awaited_once_with("ch1", "kid1")


@pytest.mark.asyncio
async def test_linked_child_may_still_request_for_themselves(monkeypatch):
    kid = MagicMock(is_admin=False)
    handlers, coordinator = await _handlers(kid, ["uid-dad"], monkeypatch)

    await handlers[tm.SERVICE_REQUEST_SWAP](_call("uid-kid", {"chore_id": "ch1", "requester_id": "kid1"}))

    coordinator.async_request_swap.assert_awaited_once_with("ch1", "kid1")


@pytest.mark.asyncio
async def test_sibling_may_not_request_in_another_childs_name(monkeypatch):
    sibling = MagicMock(is_admin=False)
    handlers, coordinator = await _handlers(sibling, ["uid-dad"], monkeypatch)

    with pytest.raises(tm.Unauthorized):
        await handlers[tm.SERVICE_REQUEST_SWAP](_call("uid-sibling", {"chore_id": "ch1", "requester_id": "kid1"}))

    coordinator.async_request_swap.assert_not_awaited()


def test_swap_services_are_registered_and_unloaded():
    """New services must also be removed on unload, or a reload double-registers."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "__init__.py").read_text(
        encoding="utf-8"
    )
    unload = src[src.rindex("SERVICE_REQUEST_SWAP,") :]
    assert "SERVICE_APPROVE_SWAP," in unload
    assert "SERVICE_REJECT_SWAP," in unload
