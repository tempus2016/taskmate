"""Guest child profiles (#690).

A visiting cousin gets a temporary child that expires on its own and stays out
of the family leaderboard, so a week's visit doesn't permanently distort the
season standings or leave a stale profile behind.

"Archived" rather than deleted: the visit's completions stay in history, and
next summer the same guest can be reactivated instead of rebuilt.
"""
from __future__ import annotations

import logging
from datetime import date

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class GuestsMixin:
    """Mixin providing guest-profile lifecycle."""

    def is_guest_child(self, child) -> bool:
        return bool(getattr(child, "is_guest", False))

    def guest_has_expired(self, child, on: date | None = None) -> bool:
        """True when a guest's stay has ended.

        A guest with no end date never expires — a parent may not know how long
        the visit will be, and silently archiving them mid-stay would be worse
        than leaving the profile up.
        """
        if not self.is_guest_child(child):
            return False
        raw = (getattr(child, "guest_expires_on", "") or "").strip()
        if not raw:
            return False
        try:
            ends = date.fromisoformat(raw)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "Guest %s has an unparseable expiry %r — treating as open-ended",
                getattr(child, "name", ""), raw,
            )
            return False
        return (on or dt_util.as_local(dt_util.now()).date()) > ends

    def leaderboard_children(self) -> list:
        """Children who count towards the family leaderboard.

        Guests are excluded: a cousin here for a week shouldn't win the month,
        and their absence shouldn't look like a loss when they leave.
        """
        return [c for c in self.storage.get_children() if not self.is_guest_child(c)]

    async def async_archive_expired_guests(self, refresh: bool = True) -> list[str]:
        """Archive guests whose stay has ended. Returns the names archived.

        Archiving disables the profile rather than deleting it, so the visit's
        history survives and the same guest can be reactivated next time.
        """
        today = dt_util.as_local(dt_util.now()).date()
        archived: list[str] = []

        for child in self.storage.get_children():
            if not self.guest_has_expired(child, today):
                continue
            if getattr(child, "availability_entity", "") == "__guest_archived__":
                continue  # already archived

            # Mark unavailable via the existing availability plumbing, so every
            # chore/streak path treats them as away without new special cases.
            child.availability_entity = "__guest_archived__"
            child.pause_streak_when_unavailable = True
            self.storage.update_child(child)
            archived.append(child.name)
            _LOGGER.info("Archived guest profile '%s' (stay ended %s)",
                         child.name, child.guest_expires_on)
            self.hass.bus.async_fire(
                "taskmate_guest_archived",
                {
                    "child_id": child.id,
                    "child_name": child.name,
                    "expired_on": child.guest_expires_on,
                    "timestamp": dt_util.now().isoformat(),
                },
            )

        if archived:
            await self.storage.async_save()
            if refresh:
                await self.async_refresh()
        return archived

    async def async_set_guest(
        self, child_id: str, is_guest: bool, expires_on: str = "",
    ) -> None:
        """Mark a child as a guest (or back to a family member)."""
        child = self.storage.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        if expires_on:
            try:
                date.fromisoformat(expires_on)
            except (TypeError, ValueError) as err:
                raise ValueError("expires_on must be an ISO date, e.g. 2026-08-31") from err

        child.is_guest = bool(is_guest)
        child.guest_expires_on = expires_on if is_guest else ""
        if not is_guest and child.availability_entity == "__guest_archived__":
            # Promoting an archived guest to a family member un-archives them.
            child.availability_entity = ""
        self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()
