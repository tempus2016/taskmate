"""NFC / QR tag completion (#923).

A chore can be linked to one or more Home Assistant tags — an NFC sticker on
the dishwasher, a QR code on the bedroom door. Scanning the tag in the HA
companion app fires ``tag_scanned``; this mixin turns that into a normal chore
completion for whoever scanned it.

Every completion goes through ``async_complete_chore`` so approval, schedule,
availability, dependency, rotation, daily-limit and weekly-target rules all
still apply — a tag is just another button, never a bypass. The only rules
added here are the ones a tag needs on top:

* the child is resolved from the scanning HA user (``linked_user_id``); an
  unresolved scan only credits a chore assigned to exactly one child, and only
  if the scanning user may act as that child;
* a chore that needs a photo or a typed note can't be completed by a tag alone,
  because a tap carries neither;
* a repeat scan moments after a completion is ignored (phones often read one
  NFC tap twice).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from . import authz
from .const import EVENT_TAG_COMPLETION, TAG_SCAN_DEBOUNCE_SECONDS
from .models import parse_datetime

_LOGGER = logging.getLogger(__name__)


class TagsMixin:
    """Mixin completing chores from HA ``tag_scanned`` events."""

    @callback
    def _tag_scanned(self, event) -> None:
        """Bus listener: hand the scan to the async handler."""
        data = event.data or {}
        self.hass.async_create_task(
            self.async_handle_tag_scan(
                str(data.get("tag_id") or ""),
                device_id=str(data.get("device_id") or ""),
                context=getattr(event, "context", None),
            )
        )

    def chores_for_tag(self, tag_id: str) -> list:
        """Chores linked to ``tag_id`` (exact match, as HA reports it)."""
        tag_id = (tag_id or "").strip()
        if not tag_id:
            return []
        return [c for c in self.storage.get_chores() if tag_id in (getattr(c, "tag_ids", None) or [])]

    def _child_for_tag_user(self, user_id: str):
        """The child whose ``linked_user_id`` is the scanning HA user, if any."""
        if not user_id:
            return None
        for child in self.storage.get_children():
            if getattr(child, "linked_user_id", "") == user_id:
                return child
        return None

    def _recent_tag_completion(self, chore_id: str, child_id: str) -> bool:
        """True if this child completed this chore inside the debounce window."""
        cutoff = dt_util.now() - timedelta(seconds=TAG_SCAN_DEBOUNCE_SECONDS)
        for comp in self.storage.get_completions():
            if comp.chore_id != chore_id or comp.child_id != child_id or comp.bonus_subtask_id:
                continue
            done_at = parse_datetime(comp.completed_at)
            if done_at is not None and done_at >= cutoff:
                return True
        return False

    async def async_handle_tag_scan(self, tag_id: str, device_id: str = "", context: Any = None) -> list:
        """Complete every chore linked to ``tag_id`` for the scanning child.

        Returns the completions created (empty when the scan did nothing). Never
        raises: this runs from an event listener, where an exception would only
        land in the HA log as an unhandled task error.
        """
        chores = self.chores_for_tag(tag_id)
        if not chores:
            return []

        user_id = authz._context_user_id(context)
        scanner = self._child_for_tag_user(user_id)
        completions = []

        for chore in chores:
            child = scanner
            if child is None:
                # No linked child for this user (or a user-less scan from a
                # fixed reader): only a chore with a single assignee has an
                # unambiguous owner. A user linked to a different child is
                # refused by the same linked-child rule the services apply.
                assigned = list(getattr(chore, "assigned_to", []) or [])
                if len(assigned) != 1:
                    _LOGGER.info(
                        "Tag %s scanned for '%s' but the child can't be determined "
                        "(scanning user isn't linked to a child and the chore has %d assignees)",
                        tag_id,
                        chore.name,
                        len(assigned),
                    )
                    continue
                child = self.get_child(assigned[0])
                if child is None:
                    continue
                if not await authz.async_context_allows_child(self.hass, self, context, child.id):
                    _LOGGER.info(
                        "Tag %s scanned for '%s': this user may not complete chores as %s",
                        tag_id,
                        chore.name,
                        child.name,
                    )
                    continue

            if getattr(chore, "task_type", "standard") == "timed":
                _LOGGER.info("Tag %s: '%s' is a timed chore — start it from the card instead", tag_id, chore.name)
                continue
            if getattr(chore, "require_photo", False) or getattr(chore, "open_ended", False):
                _LOGGER.info(
                    "Tag %s: '%s' needs a photo or a note, which a tag scan can't provide",
                    tag_id,
                    chore.name,
                )
                continue
            if self._recent_tag_completion(chore.id, child.id):
                _LOGGER.debug("Tag %s: ignoring repeat scan of '%s' for %s", tag_id, chore.name, child.name)
                continue

            try:
                completion = await self.async_complete_chore(chore.id, child.id)
            except ValueError as err:
                _LOGGER.info("Tag %s could not complete '%s' for %s: %s", tag_id, chore.name, child.name, err)
                continue
            if completion is None:
                # Soft no-op (already done, not today, not their turn, ...) —
                # async_complete_chore has logged the reason.
                continue

            completions.append(completion)
            self.hass.bus.async_fire(
                EVENT_TAG_COMPLETION,
                {
                    "tag_id": tag_id,
                    "device_id": device_id,
                    "child_id": child.id,
                    "child_name": child.name,
                    "chore_id": chore.id,
                    "chore_name": chore.name,
                    "completion_id": completion.id,
                    "pending_approval": not completion.approved,
                },
            )
            await self._async_record_tag_audit(user_id, child.name)

        return completions

    async def _async_record_tag_audit(self, user_id: str, target: str) -> None:
        """Leave the same trail a service-driven completion does (best-effort)."""
        user_name = ""
        if user_id:
            try:
                user = await self.hass.auth.async_get_user(user_id)
                user_name = user.name if user else ""
            except Exception:  # noqa: BLE001 - audit must never break the action
                user_name = ""
        try:
            await self.async_record_audit(user_id, user_name, "tag.complete_chore", target)
        except Exception:  # noqa: BLE001 - audit must never break the action
            _LOGGER.debug("Failed to record tag completion audit", exc_info=True)
