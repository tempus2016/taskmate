"""Opt-in linked-user gate for child-facing service calls (security finding #2).

The open child services (complete_chore without as_parent, claim_reward,
allocate_points_to_pool, timed tasks, bonus subtasks) accept an arbitrary
``child_id``. When a child is linked to an HA user via ``linked_user_id``,
``_async_require_linked_child`` restricts that child's self-service calls to the
linked user (admins and context-less calls always pass). Children with no link
keep the default open/kiosk behaviour.
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


def _coordinator(linked_user_id, others=None):
    coord = MagicMock()
    if linked_user_id is None:
        coord.get_child.return_value = None
    else:
        coord.get_child.return_value = MagicMock(linked_user_id=linked_user_id)
    coord.get_children.return_value = others or []
    return coord


@pytest.mark.asyncio
async def test_passes_without_user_context():
    """Automations/scripts (no user_id) pass through untouched."""
    hass = _hass(None)
    coord = _coordinator("uid-malia")
    await tm._async_require_linked_child(hass, _call(None), coord, "child-1")
    coord.get_child.assert_not_called()


@pytest.mark.asyncio
async def test_unlinked_child_is_open_to_any_user():
    """Default kiosk behaviour: a child with no link accepts any user."""
    await tm._async_require_linked_child(
        _hass(MagicMock(is_admin=False)), _call("uid-anyone"), _coordinator(""), "child-1"
    )


@pytest.mark.asyncio
async def test_unknown_child_is_open():
    """A child_id that doesn't resolve has no link, so it stays open."""
    await tm._async_require_linked_child(
        _hass(MagicMock(is_admin=False)), _call("uid-anyone"), _coordinator(None), "child-x"
    )


@pytest.mark.asyncio
async def test_linked_user_allowed():
    """The linked user may act as their own child."""
    hass = _hass(MagicMock(is_admin=False))
    await tm._async_require_linked_child(hass, _call("uid-malia"), _coordinator("uid-malia"), "child-1")
    hass.auth.async_get_user.assert_not_called()


@pytest.mark.asyncio
async def test_admin_overrides_link():
    """An admin (parent) may act on behalf of any linked child."""
    await tm._async_require_linked_child(
        _hass(MagicMock(is_admin=True)), _call("uid-parent"), _coordinator("uid-malia"), "child-1"
    )


@pytest.mark.asyncio
async def test_other_non_admin_rejected():
    """A different non-admin user (e.g. a sibling) is blocked."""
    with pytest.raises(tm.Unauthorized):
        await tm._async_require_linked_child(
            _hass(MagicMock(is_admin=False)), _call("uid-sibling"), _coordinator("uid-malia"), "child-1"
        )


@pytest.mark.asyncio
async def test_unlinked_child_blocks_known_other_child():
    """SEC-4: a user linked to a different child can't act via an unlinked child."""
    coord = _coordinator("", others=[MagicMock(linked_user_id="uid-sibling")])
    with pytest.raises(tm.Unauthorized):
        await tm._async_require_linked_child(
            _hass(MagicMock(is_admin=False)), _call("uid-sibling"), coord, "child-1"
        )


@pytest.mark.asyncio
async def test_unlinked_child_admin_still_allowed_with_other_links():
    """An admin is allowed through an unlinked child even when other links exist."""
    coord = _coordinator("", others=[MagicMock(linked_user_id="uid-sibling")])
    await tm._async_require_linked_child(
        _hass(MagicMock(is_admin=True)), _call("uid-parent"), coord, "child-1"
    )
