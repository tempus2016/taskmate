"""Scheduled chore config changes (#675).

"From 1 September this chore is worth 20 points." A change is queued against a
chore with a date; at midnight (and at startup, to catch up after downtime)
every due change is applied and stamped.

Applied changes are kept rather than deleted so the panel can show what changed
and when — a config change that happens silently is worse than one that doesn't
happen at all.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.util import dt as dt_util

from .models import SCHEDULED_CHANGE_FIELDS, ScheduledChange

_LOGGER = logging.getLogger(__name__)


def coerce_scheduled_value(field: str, value: Any) -> Any:
    """Coerce a queued value to the field's type, or raise ValueError.

    Values arrive from the websocket as JSON, so an int field can turn up as a
    string. Validating at queue time means a bad value fails in front of the
    parent rather than silently at midnight weeks later.
    """
    expected = SCHEDULED_CHANGE_FIELDS.get(field)
    if expected is None:
        raise ValueError(f"'{field}' cannot be changed on a schedule")

    if expected is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ValueError(f"'{field}' expects true or false")

    if expected is int:
        try:
            coerced = int(value)
        except (TypeError, ValueError) as err:
            raise ValueError(f"'{field}' expects a whole number") from err
        if coerced < 0:
            raise ValueError(f"'{field}' cannot be negative")
        return coerced

    if expected is list:
        if not isinstance(value, list):
            raise ValueError(f"'{field}' expects a list")
        return [str(v) for v in value]

    if value is None:
        raise ValueError(f"'{field}' expects text")
    return str(value)


class ScheduledChangesMixin:
    """Mixin providing scheduled-change CRUD and the apply pass."""

    def get_scheduled_changes(self, chore_id: str = "") -> list[ScheduledChange]:
        """Scheduled changes, optionally filtered to one chore, soonest first."""
        changes = self.storage.get_scheduled_changes()
        if chore_id:
            changes = [c for c in changes if c.chore_id == chore_id]
        return sorted(changes, key=lambda c: (c.apply_on, c.created_at))

    async def async_add_scheduled_change(
        self,
        chore_id: str,
        apply_on: str,
        changes: dict[str, Any],
        note: str = "",
    ) -> ScheduledChange:
        """Queue a change. Validates the chore, the date and every field now."""
        if not self.storage.get_chore(chore_id):
            raise ValueError(f"Chore {chore_id} not found")

        try:
            target = date.fromisoformat(apply_on)
        except (TypeError, ValueError) as err:
            raise ValueError("apply_on must be an ISO date, e.g. 2026-09-01") from err
        if target <= dt_util.as_local(dt_util.now()).date():
            raise ValueError("apply_on must be a future date")

        if not changes:
            raise ValueError("A scheduled change must change at least one field")
        coerced = {f: coerce_scheduled_value(f, v) for f, v in changes.items()}

        change = ScheduledChange(
            chore_id=chore_id,
            apply_on=apply_on,
            changes=coerced,
            note=note,
        )
        self.storage.add_scheduled_change(change)
        await self.storage.async_save()
        await self.async_refresh()
        return change

    async def async_remove_scheduled_change(self, change_id: str) -> None:
        if not self.storage.get_scheduled_change(change_id):
            raise ValueError(f"Scheduled change {change_id} not found")
        self.storage.remove_scheduled_change(change_id)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_apply_due_scheduled_changes(self, refresh: bool = True) -> int:
        """Apply every pending change dated today or earlier. Returns the count.

        "Or earlier" matters: Home Assistant may have been off on the day a
        change was due, and the parent still expects it to have happened.
        """
        today = dt_util.as_local(dt_util.now()).date()
        applied = 0

        for change in self.storage.get_scheduled_changes():
            if change.applied:
                continue
            try:
                if date.fromisoformat(change.apply_on) > today:
                    continue
            except (TypeError, ValueError):
                _LOGGER.warning(
                    "Scheduled change %s has an unparseable date %r — skipping",
                    change.id,
                    change.apply_on,
                )
                continue

            chore = self.storage.get_chore(change.chore_id)
            if not chore:
                # The chore was deleted after the change was queued. Mark it
                # applied so it stops being retried every single midnight.
                change.applied = True
                change.applied_at = dt_util.now().isoformat()
                change.note = (change.note + " [chore deleted]").strip()
                self.storage.update_scheduled_change(change)
                applied += 1
                continue

            for field_name, value in change.changes.items():
                if field_name not in SCHEDULED_CHANGE_FIELDS:
                    _LOGGER.warning(
                        "Scheduled change %s targets unknown field '%s' — skipping it",
                        change.id,
                        field_name,
                    )
                    continue
                setattr(chore, field_name, value)
            self.storage.update_chore(chore)

            change.applied = True
            change.applied_at = dt_util.now().isoformat()
            self.storage.update_scheduled_change(change)
            applied += 1

            _LOGGER.info(
                "Applied scheduled change to '%s': %s",
                chore.name,
                ", ".join(f"{k}={v}" for k, v in change.changes.items()),
            )
            self.hass.bus.async_fire(
                "taskmate_scheduled_change_applied",
                {
                    "change_id": change.id,
                    "chore_id": change.chore_id,
                    "chore_name": chore.name,
                    "changes": change.changes,
                    "timestamp": dt_util.now().isoformat(),
                },
            )

        if applied:
            await self.storage.async_save()
            if refresh:
                await self.async_refresh()
        return applied
