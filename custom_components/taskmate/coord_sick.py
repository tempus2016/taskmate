"""Sick days: one tap gives a child the day off.

A sick day works like a one-child, one-day vacation without needing an
availability entity: the child's chores are hidden, their streak is frozen
over the day (it never counts as missed), and no mandatory-chore miss is
raised for them. A parent sets it for today (or another day) and can take
it back.
"""

from __future__ import annotations

from datetime import date, timedelta

from homeassistant.util import dt as dt_util

SICK_KEEP_DAYS = 120


class SickDaysMixin:
    """Per-child sick days."""

    def _sick_days(self) -> dict[str, list[str]]:
        return self.storage.get_section("sick_days", dict)

    def is_sick_day(self, child_id: str | None, on: date | None = None) -> bool:
        if not child_id:
            return False
        day = (on or dt_util.as_local(dt_util.now()).date()).isoformat()
        return day in (self._sick_days().get(child_id) or [])

    def sick_days_for(self, child_id: str) -> list[str]:
        return sorted(self._sick_days().get(child_id) or [])

    async def async_set_sick_day(self, child_id: str, day: date | None = None, sick: bool = True) -> bool:
        """Mark (or unmark) ``day`` (default today) as a sick day. Returns the new state."""
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        today = dt_util.as_local(dt_util.now()).date()
        day = day or today
        if day < today - timedelta(days=7) or day > today + timedelta(days=30):
            raise ValueError("Pick a day from a week ago to a month ahead.")
        days = set(self._sick_days().get(child_id) or [])
        key = day.isoformat()
        if sick:
            days.add(key)
        else:
            days.discard(key)
        floor = (today - timedelta(days=SICK_KEEP_DAYS)).isoformat()
        kept = sorted(d for d in days if d >= floor)
        if kept:
            self._sick_days()[child_id] = kept
        else:
            self._sick_days().pop(child_id, None)
        await self.storage.async_save()
        self.hass.bus.async_fire(
            "taskmate_sick_day",
            {
                "child_id": child_id,
                "child_name": child.name,
                "date": key,
                "sick": bool(sick),
                "timestamp": dt_util.now().isoformat(),
            },
        )
        await self.async_refresh()
        return bool(sick)
