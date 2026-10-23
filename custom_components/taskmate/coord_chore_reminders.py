"""Child-chosen reminder times: "remind me about homework at 17:30".

A child picks a time on their card for any of their chores, within the
earliest/latest bounds a parent sets (``chore_reminders_enabled``,
``chore_reminders_earliest``, ``chore_reminders_latest``). The choice is kept
per child per chore (``chore_reminders`` in storage).

The minutely tick sends that child — and only that child — a push at the
chosen time on days the chore is due and not done yet. It's an opt-in
notification type like every one added after release.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.util import dt as dt_util

from .const import NOTIF_TYPE_CHORE_SELF_REMINDER
from .timewindow import parse_hhmm

_LOGGER = logging.getLogger(__name__)

DEFAULT_REMINDER_EARLIEST = "15:00"
DEFAULT_REMINDER_LATEST = "20:00"
# A tick that runs a little late still sends, but never twice in a day.
_REMINDER_GRACE_MINUTES = 5


def _minutes(value: str) -> int | None:
    parsed = parse_hhmm(value)
    return parsed[0] * 60 + parsed[1] if parsed else None


class ChoreRemindersMixin:
    """Per-child, per-chore reminder times and the push that goes with them."""

    def chore_reminders_enabled(self) -> bool:
        return bool(self.storage.get_setting("chore_reminders_enabled", False))

    def chore_reminder_bounds(self) -> tuple[str, str]:
        """The earliest and latest time a child may pick, as "HH:MM"."""
        earliest = str(self.storage.get_setting("chore_reminders_earliest", "") or DEFAULT_REMINDER_EARLIEST)
        latest = str(self.storage.get_setting("chore_reminders_latest", "") or DEFAULT_REMINDER_LATEST)
        if _minutes(earliest) is None:
            earliest = DEFAULT_REMINDER_EARLIEST
        if _minutes(latest) is None:
            latest = DEFAULT_REMINDER_LATEST
        if _minutes(latest) < _minutes(earliest):
            earliest, latest = latest, earliest
        return earliest, latest

    def chore_reminders_for_child(self, child_id: str) -> dict[str, str]:
        """``{chore_id: "HH:MM"}`` while the feature is on."""
        if not self.chore_reminders_enabled():
            return {}
        mine = self.storage.get_section("chore_reminders", dict).get(child_id)
        if not isinstance(mine, dict):
            return {}
        chores = {c.id for c in self.storage.get_chores()}
        return {cid: t for cid, t in mine.items() if cid in chores and _minutes(t) is not None}

    async def async_set_chore_reminder(self, child_id: str, chore_id: str, time: str = "") -> None:
        """Set (or, with no time, clear) a child's reminder for one chore."""
        if not self.chore_reminders_enabled():
            raise ValueError("Reminders are turned off")
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        chore = self.get_chore(chore_id)
        if chore is None:
            raise ValueError(f"Chore {chore_id} not found")
        assigned = chore.assigned_to or []
        if assigned and child_id not in assigned:
            raise ValueError(f"{chore.name} isn't one of {child.name}'s chores")
        section = self.storage.get_section("chore_reminders", dict)
        mine = section.setdefault(child_id, {})
        time = (time or "").strip()
        if time:
            at = _minutes(time)
            if at is None:
                raise ValueError("Pick a time like 17:30")
            earliest, latest = self.chore_reminder_bounds()
            if not _minutes(earliest) <= at <= _minutes(latest):
                raise ValueError(f"Pick a time between {earliest} and {latest}")
            mine[chore_id] = f"{at // 60:02d}:{at % 60:02d}"
        else:
            mine.pop(chore_id, None)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_check_chore_reminders(self) -> None:
        """Minutely: push each reminder that's due, once a day."""
        if not self.chore_reminders_enabled():
            return
        now = dt_util.as_local(dt_util.now())
        today = now.date()
        now_m = now.hour * 60 + now.minute
        sent: set[tuple[str, str, str]] = {
            k for k in (getattr(self, "_chore_reminders_sent", None) or set()) if k[2] == today.isoformat()
        }
        self._chore_reminders_sent = sent
        section = self.storage.get_section("chore_reminders", dict)
        for child_id, mine in list(section.items()):
            if not isinstance(mine, dict) or not mine:
                continue
            child = self.get_child(child_id)
            if child is None:
                continue
            done = None
            for chore_id, at in mine.items():
                at_m = _minutes(at)
                if at_m is None or not 0 <= now_m - at_m < _REMINDER_GRACE_MINUTES:
                    continue
                key = (child_id, chore_id, today.isoformat())
                if key in sent:
                    continue
                chore = self.get_chore(chore_id)
                if chore is None or not self._is_chore_scheduled_for_date(chore, today):
                    continue
                if not self.is_chore_available_for_child(chore, child_id):
                    continue
                if done is None:
                    done = self._completed_chore_ids_for_child(child_id, today)
                if chore_id in done:
                    continue
                sent.add(key)
                await self.notifications.fire(
                    NOTIF_TYPE_CHORE_SELF_REMINDER,
                    {"child_name": child.name, "child_id": child_id, "chore_name": chore.name, "time": at},
                    only_recipients={f"child:{child_id}"},
                )

    def chore_reminder_settings(self) -> dict[str, Any] | None:
        """What the card needs to offer the picker, while the feature is on."""
        if not self.chore_reminders_enabled():
            return None
        earliest, latest = self.chore_reminder_bounds()
        return {"earliest": earliest, "latest": latest}
