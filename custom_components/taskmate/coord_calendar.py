"""Calendar operations mixin for TaskMateCoordinator."""
from __future__ import annotations

import asyncio
import logging
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_CALENDAR_PROJECTION_DAYS,
    MAX_CALENDAR_PROJECTION_DAYS,
    MIN_CALENDAR_PROJECTION_DAYS,
)
from .models import Chore

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class CalendarMixin:
    """Mixin providing calendar projection and event publishing logic."""

    _DEFAULT_TIME_BOUNDARIES: dict[str, tuple[str, str]] = {
        "morning":   ("06:00", "12:00"),
        "afternoon": ("12:00", "17:00"),
        "evening":   ("17:00", "21:00"),
        "night":     ("21:00", "23:59"),
    }

    _SCHEDULE_DOW = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

    def _get_time_boundaries(self) -> dict[str, tuple[time, time] | None]:
        """Build time boundaries from storage settings with defaults."""
        result: dict[str, tuple[time, time] | None] = {"anytime": None}
        for cat, (def_start, def_end) in self._DEFAULT_TIME_BOUNDARIES.items():
            start_str = self.storage.get_setting(f"time_{cat}_start", def_start)
            end_str = self.storage.get_setting(f"time_{cat}_end", def_end)
            try:
                sh, sm = (int(x) for x in start_str.split(":"))
                eh, em = (int(x) for x in end_str.split(":"))
                result[cat] = (time(sh, sm), time(eh, em))
            except (ValueError, TypeError):
                sh, sm = (int(x) for x in def_start.split(":"))
                eh, em = (int(x) for x in def_end.split(":"))
                result[cat] = (time(sh, sm), time(eh, em))
        return result

    def _time_category_window(self, category: str, today: date) -> tuple[datetime, datetime] | None:
        """Return (start, end) datetimes for a time_category, or None for all-day."""
        boundaries = self._get_time_boundaries()
        window = boundaries.get(category or "anytime")
        if window is None:
            return None
        start_t, end_t = window
        return datetime.combine(today, start_t), datetime.combine(today, end_t)

    def _chore_event_marker(self, chore: Chore) -> str:
        """Marker stitched into the event description so we can find our own events."""
        return f"taskmate:chore:{chore.id}"

    def _calendar_projection_days(self) -> int:
        """Return the configured projection horizon, clamped to the allowed range."""
        try:
            raw = int(float(self.storage.get_setting(
                "calendar_projection_days", str(DEFAULT_CALENDAR_PROJECTION_DAYS)
            )))
        except (TypeError, ValueError):
            raw = DEFAULT_CALENDAR_PROJECTION_DAYS
        return max(MIN_CALENDAR_PROJECTION_DAYS, min(MAX_CALENDAR_PROJECTION_DAYS, raw))

    def _is_chore_scheduled_for_date(self, chore: Chore, day: date) -> bool:
        """Return True if the chore's schedule places it on `day`.

        Mirrors the client-side `_isChoreScheduledOn` in taskmate-calendar-card.js
        so the HA calendar projection matches what the card shows. Does not
        consult completion state — this is purely the recurrence/schedule math.
        """
        if not getattr(chore, "enabled", True):
            return False

        schedule_mode = getattr(chore, "schedule_mode", "specific_days")
        created_iso = getattr(chore, "created_date", "") or ""

        if schedule_mode == "one_shot":
            return bool(created_iso) and created_iso == day.isoformat()

        if created_iso:
            try:
                if day < date.fromisoformat(created_iso):
                    return False
            except ValueError:
                pass

        if schedule_mode == "specific_days":
            due_days = list(getattr(chore, "due_days", []) or [])
            if not due_days:
                return True
            return self._SCHEDULE_DOW[day.weekday()] in due_days

        if schedule_mode != "recurring":
            return False

        recurrence = getattr(chore, "recurrence", "weekly")
        recurrence_day = (getattr(chore, "recurrence_day", "") or "").lower()
        recurrence_start = getattr(chore, "recurrence_start", "") or ""
        day_dow = self._SCHEDULE_DOW[day.weekday()]

        if recurrence_day and recurrence in ("weekly", "every_2_weeks"):
            if recurrence_day != day_dow:
                return False
            if recurrence == "every_2_weeks" and recurrence_start:
                try:
                    anchor = date.fromisoformat(recurrence_start)
                    diff = (day - anchor).days
                    if diff < 0 or (diff // 7) % 2 != 0:
                        return False
                except ValueError:
                    pass
            return True

        if recurrence == "every_2_days" and recurrence_start:
            try:
                anchor = date.fromisoformat(recurrence_start)
                diff = (day - anchor).days
                return diff >= 0 and diff % 2 == 0
            except ValueError:
                return False

        month_steps = {"monthly": 1, "every_3_months": 3, "every_6_months": 6}.get(recurrence)
        if month_steps and recurrence_start:
            try:
                anchor = date.fromisoformat(recurrence_start)
                if day < anchor:
                    return False
                months_diff = (day.year - anchor.year) * 12 + (day.month - anchor.month)
                if months_diff % month_steps != 0:
                    return False
                # Clamp the anchor day for shorter months (e.g. 31st → Feb 28th)
                target_day = min(anchor.day, monthrange(day.year, day.month)[1])
                return day.day == target_day
            except ValueError:
                return False

        # Weekly/every_2_weeks without an explicit day: same weekday as today,
        # matching the card's fallback for loosely-scheduled recurrences.
        if recurrence in ("weekly", "every_2_weeks"):
            today = dt_util.as_local(dt_util.now()).date()
            return day.weekday() == today.weekday()

        return False

    def _build_event_payload(self, chore: Chore, day: date, summary: str) -> dict:
        """Build the calendar.create_event payload for one (chore, day)."""
        description = self._chore_event_marker(chore)
        window = self._time_category_window(
            getattr(chore, "time_category", "anytime"), day
        )
        if window is None:
            return {
                "summary": summary,
                "description": description,
                "start_date": day.isoformat(),
                "end_date": (day + timedelta(days=1)).isoformat(),
            }
        start_dt, end_dt = window
        return {
            "summary": summary,
            "description": description,
            "start_date_time": start_dt.isoformat(),
            "end_date_time": end_dt.isoformat(),
        }

    def _child_name_for_day(self, chore: Chore, day: date) -> str:
        """Return the display name for the chore's assignee on `day`."""
        active = self._compute_active_children(chore, day)
        if not active:
            return "Everyone"
        child = self.storage.get_child(active[0])
        return child.name if child else "Everyone"

    async def _publish_chore_to_calendars(self, chore: Chore, today: date | None = None) -> None:
        """Publish assignments for `chore` across the configured projection horizon.

        For every date in [today, today + horizon) that the schedule covers and
        hasn't already been published, computes that date's active child and
        writes an event to each configured calendar. Past entries are pruned
        from `publish_calendar_published_dates` so the list doesn't grow
        unbounded. Fan-out is via asyncio.gather so N entities x M missing
        days scale with the slowest single service call.
        """
        entities = list(getattr(chore, "publish_calendar_entities", []) or [])
        if not entities:
            return

        if today is None:
            today = dt_util.as_local(dt_util.now()).date()
        horizon = self._calendar_projection_days()

        published = set(getattr(chore, "publish_calendar_published_dates", []) or [])
        # Prune stale entries (strictly before today) so the list stays small.
        published = {iso for iso in published if iso >= today.isoformat()}

        pending: list[tuple[date, dict]] = []
        for offset in range(horizon):
            day = today + timedelta(days=offset)
            day_iso = day.isoformat()
            if day_iso in published:
                continue
            if not self._is_chore_scheduled_for_date(chore, day):
                continue
            summary = f"{chore.name} — {self._child_name_for_day(chore, day)}"
            pending.append((day, self._build_event_payload(chore, day, summary)))

        if not pending and not published.symmetric_difference(
            getattr(chore, "publish_calendar_published_dates", []) or []
        ):
            # Nothing to publish and nothing pruned — leave the chore untouched
            # so the caller doesn't write the record out for no reason.
            return

        async def _call(entity_id: str, payload: dict) -> None:
            try:
                await self.hass.services.async_call(
                    "calendar",
                    "create_event",
                    {"entity_id": entity_id, **payload},
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001 - HA service errors vary
                _LOGGER.warning(
                    "TaskMate: failed to publish chore %s to calendar %s: %s",
                    chore.name,
                    entity_id,
                    err,
                )

        tasks = [_call(e, payload) for day, payload in pending for e in entities]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            for day, _ in pending:
                published.add(day.isoformat())

        chore.publish_calendar_published_dates = sorted(published)

    async def _cleanup_chore_from_calendars(
        self,
        chore: Chore,
        entities: list[str] | None = None,
        today: date | None = None,
        summary_prefixes: list[str] | None = None,
    ) -> None:
        """Best-effort delete of the chore's own events from each configured calendar.

        Uses a description marker (`taskmate:chore:<id>`) stitched in at create
        time to re-identify events. Covers today through today+horizon+7 so the
        full projection range is cleaned up on edit/delete. Failure modes
        (unavailable calendar, integration without delete_event support,
        response service disabled) are caught and logged; cleanup never blocks
        the caller.
        """
        ents = list(entities if entities is not None else getattr(chore, "publish_calendar_entities", []) or [])
        if not ents:
            return

        if today is None:
            today = dt_util.as_local(dt_util.now()).date()
        window_days = max(30, self._calendar_projection_days() + 7)
        window_start = datetime.combine(today, time(0, 0)).isoformat()
        window_end = datetime.combine(today + timedelta(days=window_days), time(0, 0)).isoformat()
        marker = self._chore_event_marker(chore)
        # Fallback summary prefixes: covers integrations whose get_events
        # response omits or strips the description field. Default to the
        # current chore's name so deletes still work for unedited chores.
        prefixes = list(summary_prefixes or [f"{chore.name} — "])

        def _matches(event: dict) -> bool:
            if marker in (event.get("description") or ""):
                return True
            summary = event.get("summary") or ""
            return any(summary.startswith(p) for p in prefixes if p)

        async def _purge(entity_id: str) -> None:
            try:
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        "entity_id": entity_id,
                        "start_date_time": window_start,
                        "end_date_time": window_end,
                    },
                    blocking=True,
                    return_response=True,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "TaskMate: could not list events on %s for cleanup: %s",
                    entity_id,
                    err,
                )
                return

            events = []
            if isinstance(response, dict):
                bucket = response.get(entity_id, response)
                if isinstance(bucket, dict):
                    events = bucket.get("events", []) or []
                elif isinstance(bucket, list):
                    events = bucket

            for event in events:
                if not _matches(event):
                    continue
                uid = event.get("uid") or event.get("recurrence_id") or event.get("id")
                if not uid:
                    continue
                try:
                    await self.hass.services.async_call(
                        "calendar",
                        "delete_event",
                        {"entity_id": entity_id, "uid": uid},
                        blocking=True,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning(
                        "TaskMate: failed to delete event %s from %s: %s",
                        uid,
                        entity_id,
                        err,
                    )

        await asyncio.gather(*(_purge(e) for e in ents), return_exceptions=True)
        chore.publish_calendar_published_dates = []
