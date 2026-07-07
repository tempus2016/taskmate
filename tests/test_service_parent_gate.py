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
