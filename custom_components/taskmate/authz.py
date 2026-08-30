"""Shared authorization checks for TaskMate.

The panel's WebSocket commands are admin-gated and the ``taskmate.*`` services
carry admin / parent / linked-child checks. The auto-generated entity platforms
(number/select/button/todo) and the mobile-action event handler reach the same
coordinator mutations through a different door, so they must apply the *same*
checks. These helpers work off a plain Home Assistant ``Context`` (its
``user_id``) so every caller — service, entity, or event — shares one
implementation and the rules can't drift between doors.

Context-less callers (automations, scripts, schedules, internal refreshes) are
trusted and pass every check, matching the long-standing service behaviour.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant


def _context_user_id(context: Any) -> str:
    """Return the acting user id, or "" for a trusted/context-less caller."""
    return getattr(context, "user_id", "") or "" if context is not None else ""


async def async_user_is_admin(hass: HomeAssistant, user_id: str) -> bool:
    """True if ``user_id`` resolves to an admin HA user."""
    if not user_id:
        return False
    user = await hass.auth.async_get_user(user_id)
    return bool(user and user.is_admin)


async def async_context_is_admin(hass: HomeAssistant, context: Any) -> bool:
    """True if the context is trusted (no user) or belongs to an admin."""
    user_id = _context_user_id(context)
    if not user_id:
        return True
    return await async_user_is_admin(hass, user_id)


async def async_context_is_parent(hass: HomeAssistant, coordinator: Any, context: Any) -> bool:
    """True if the context is trusted, an admin, or a configured TaskMate parent."""
    user_id = _context_user_id(context)
    if not user_id:
        return True
    if await async_user_is_admin(hass, user_id):
        return True
    parent_ids = coordinator.storage.get_parent_user_ids() if coordinator else []
    return user_id in parent_ids


async def async_context_allows_child(
    hass: HomeAssistant, coordinator: Any, context: Any, child_id: str
) -> bool:
    """True if the context user may act *as* ``child_id`` (linked-child rule).

    Mirrors the service-layer ``_async_require_linked_child`` gate: a child that
    has ``linked_user_id`` set may only be driven by that HA user (or an admin);
    an unlinked child keeps the open/kiosk behaviour, except a user who is
    themselves linked to a *different* child may never act through an unlinked
    child.
    """
    user_id = _context_user_id(context)
    if not user_id:
        return True
    child = coordinator.get_child(child_id) if coordinator else None
    linked = getattr(child, "linked_user_id", "") if child else ""
    if linked == user_id:
        return True
    if await async_user_is_admin(hass, user_id):
        return True
    if linked:
        return False
    others = coordinator.storage.get_children() or []
    if any(getattr(c, "linked_user_id", "") == user_id for c in others):
        return False
    return True
