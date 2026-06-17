"""Backend admin gate for parent-privileged service calls (issue #410).

The `complete_chore` service's `as_parent` path must enforce admin on the
backend, not just hide the control in the UI. These cover the shared
`_async_require_admin` helper that both the `_admin` wrapper and the
as_parent branch use.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

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
