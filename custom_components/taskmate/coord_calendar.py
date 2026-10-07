"""Calendar operations mixin for TaskMateCoordinator."""

from __future__ import annotations

import asyncio
import logging
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import (
    DEFAULT_CALENDAR_PROJECTION_DAYS,
    DEFAULT_TIME_PERIODS,
    DOMAIN,
    MAX_CALENDAR_PROJECTION_DAYS,
    MIN_CALENDAR_PROJECTION_DAYS,
    TIME_CATEGORY_ICONS,
    recurrence_interval_days,
)
from .models import Chore

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class CalendarMixin:
    """Mixin providing calendar projection and event publishing logic."""

    _SCHEDULE_DOW = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

    @staticmethod
    def _parse_hhmm(value: str) -> time | None:
        """Parse an HH:MM string, returning None when invalid."""
        try:
            h, m = (int(x) for x in str(value).split(":"))
            return time(h, m)
        except (ValueError, TypeError):
            return None

    def get_time_periods(self) -> list[dict]:
        """Resolve the user-defined time-of-day periods, ordered by start.

        Fallback chain: `time_periods` setting → legacy `time_<cat>_start/end`
        keys → DEFAULT_TIME_PERIODS. "anytime" is implicit and never listed.
        """
        raw = self.storage.get_setting("time_periods", None)
        if isinstance(raw, list) and raw:
            periods = []
            for entry in raw:
                if not isinstance(entry, dict):
                    continue
                start = self._parse_hhmm(entry.get("start"))
                end = self._parse_hhmm(entry.get("end"))
                pid = str(entry.get("id") or "").strip()
                if not pid or pid == "anytime" or start is None or end is None:
                    continue
                periods.append(
                    {
                        "id": pid,
                        "label": str(entry.get("label") or "").strip(),
                        "start": start.strftime("%H:%M"),
                        "end": end.strftime("%H:%M"),
                        "icon": str(entry.get("icon") or "") or TIME_CATEGORY_ICONS.get(pid, "mdi:clock-outline"),
                    }
                )
            if periods:
                return sorted(periods, key=lambda p: p["start"])

        # Legacy flat keys (pre-time_periods installs); these already default
        # to the built-in boundaries, so this also covers fresh installs.
        periods = []
        for default in DEFAULT_TIME_PERIODS:
            pid = default["id"]
            start_str = self.storage.get_setting(f"time_{pid}_start", default["start"])
            end_str = self.storage.get_setting(f"time_{pid}_end", default["end"])
            start = self._parse_hhmm(start_str) or self._parse_hhmm(default["start"])
            end = self._parse_hhmm(end_str) or self._parse_hhmm(default["end"])
            periods.append(
                {
                    "id": pid,
                    "label": "",
                    "start": start.strftime("%H:%M"),
                    "end": end.strftime("%H:%M"),
                    "icon": default["icon"],
                }
            )
        return sorted(periods, key=lambda p: p["start"])

    def _get_time_boundaries(self) -> dict[str, tuple[time, time] | None]:
        """Build time boundaries from the resolved periods."""
        result: dict[str, tuple[time, time] | None] = {"anytime": None}
        for period in self.get_time_periods():
            result[period["id"]] = (
                self._parse_hhmm(period["start"]),
                self._parse_hhmm(period["end"]),
            )
        return result

    def _time_category_window(self, category: str, today: date) -> tuple[datetime, datetime] | None:
        """Return (start, end) datetimes for a time_category, or None for all-day."""
        boundaries = self._get_time_boundaries()
        window = boundaries.get(category or "anytime")
        if window is None:
            return None
        start_t, end_t = window
        return datetime.combine(today, start_t), datetime.combine(today, end_t)

    # A chore with a due_time shows as a short event starting then (#993).
    _DUE_TIME_EVENT_MINUTES = 30

    def _chore_event_window(self, chore: Chore, day: date) -> tuple[datetime, datetime] | None:
        """Return the (start, end) a chore's event covers on ``day``, or None for all-day.

        A valid due_time wins: the event starts at it and lasts
        ``_DUE_TIME_EVENT_MINUTES`` (possibly past midnight). Without one, the
        event spans the chore's time-of-day period, or the whole day for anytime.
        """
        due = self._parse_hhmm(getattr(chore, "due_time", "") or "")
        if due is not None:
            start = datetime.combine(day, due)
            return start, start + timedelta(minutes=self._DUE_TIME_EVENT_MINUTES)
        return self._time_category_window(getattr(chore, "time_category", "anytime"), day)

    def _chore_event_marker(self, chore: Chore) -> str:
        """Marker stitched into the event description so we can find our own events."""
        return f"taskmate:chore:{chore.id}"

    def _calendar_projection_days(self) -> int:
        """Return the configured projection horizon, clamped to the allowed range."""
        try:
            raw = int(
                float(self.storage.get_setting("calendar_projection_days", str(DEFAULT_CALENDAR_PROJECTION_DAYS)))
            )
        except (TypeError, ValueError):
            raw = DEFAULT_CALENDAR_PROJECTION_DAYS
        return max(MIN_CALENDAR_PROJECTION_DAYS, min(MAX_CALENDAR_PROJECTION_DAYS, raw))

    @staticmethod
    def occurrence_override(chore: Chore, day: date) -> bool | None:
        """How a calendar move/removal (#977) changes ``day`` for ``chore``.

        True: an occurrence was moved onto ``day``. False: the occurrence that
        belonged to ``day`` was moved away or removed. None: nothing was
        changed on ``day`` and the regular schedule decides.
        """
        moved = getattr(chore, "moved_occurrences", None) or {}
        if not moved:
            return None
        iso = day.isoformat()
        if iso in moved.values():
            return True
        if iso in moved:
            return False
        return None

    @staticmethod
    def occurrence_origin(chore: Chore, day: date) -> date:
        """The scheduled date the occurrence held on ``day`` belongs to.

        A moved occurrence keeps the identity of the day it was moved from, so
        a recurrence window measures from the original date and the calendar
        event keeps the same uid wherever it is moved to.
        """
        moved = getattr(chore, "moved_occurrences", None) or {}
        iso = day.isoformat()
        for src, dst in moved.items():
            if dst == iso:
                try:
                    return date.fromisoformat(src)
                except ValueError:
                    break
        return day

    def _is_chore_scheduled_for_date(self, chore: Chore, day: date) -> bool:
        """Return True if the chore is due on `day`, calendar moves included.

        Every caller that asks "is this chore on this day" — the calendar
        entity, the ICS feed, calendar publishing, streaks, perfect weeks and
        mandatory misses — goes through here, so a moved or removed occurrence
        (#977) is honoured everywhere at once.
        """
        if not getattr(chore, "enabled", True):
            return False
        override = self.occurrence_override(chore, day)
        if override is not None:
            return override
        return self._is_chore_base_scheduled_for_date(chore, day)

    def _is_chore_base_scheduled_for_date(self, chore: Chore, day: date) -> bool:
        """Return True if the chore's regular schedule places it on `day`.

        Mirrors the client-side `_isChoreScheduledOn` in taskmate-calendar-card.js
        so the HA calendar projection matches what the card shows. Does not
        consult completion state or calendar moves — this is purely the
        recurrence/schedule math.
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
        # For interval recurrences, fall back to created_date as the cadence
        # anchor when no explicit recurrence_start is set — otherwise these
        # chores never project onto the calendar at all (ERR-2).
        anchor_iso = recurrence_start or created_iso
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

        interval_days = recurrence_interval_days(recurrence)
        if interval_days and anchor_iso:
            try:
                anchor = date.fromisoformat(anchor_iso)
                diff = (day - anchor).days
                return diff >= 0 and diff % interval_days == 0
            except ValueError:
                return False

        month_steps = {"monthly": 1, "every_3_months": 3, "every_6_months": 6}.get(recurrence)
        if month_steps and anchor_iso:
            try:
                anchor = date.fromisoformat(anchor_iso)
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
        window = self._chore_event_window(chore, day)
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

    # ── Two-way calendar edits (#977) ─────────────────────────────────────
    # How long a spent move/removal is kept. Long enough that a recurrence
    # window after a moved occurrence still measures from its original date,
    # short enough that the map can't grow without bound.
    _MOVED_OCCURRENCE_RETENTION_DAYS = 62

    @staticmethod
    def _calendar_error(key: str, **placeholders: str) -> ServiceValidationError:
        """A translated, user-facing refusal for a calendar edit."""
        return ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=key,
            translation_placeholders=placeholders or None,
        )

    def _period_for_time(self, value: time) -> str:
        """The time-of-day period containing ``value``, or "anytime"."""
        for period in self.get_time_periods():
            start = self._parse_hhmm(period["start"])
            end = self._parse_hhmm(period["end"])
            if start is not None and end is not None and start <= value < end:
                return period["id"]
        return "anytime"

    def _occurrence_start_time(self, chore: Chore, day: date) -> time | None:
        """The start time the calendar shows for ``chore`` on ``day`` (None = all-day)."""
        window = self._chore_event_window(chore, day)
        return window[0].time() if window else None

    def _prune_moved_occurrences(self, moved: dict[str, str], today: date) -> dict[str, str]:
        """Drop moves/removals that lie entirely in the distant past."""
        cutoff = (today - timedelta(days=self._MOVED_OCCURRENCE_RETENTION_DAYS)).isoformat()
        return {src: dst for src, dst in moved.items() if src >= cutoff or (dst and dst >= cutoff)}

    async def async_calendar_add_chore(
        self,
        child_id: str,
        name: str,
        day: date,
        *,
        description: str = "",
        start_time: time | None = None,
    ) -> Chore:
        """Create a one-off chore for ``child_id`` on ``day`` from a calendar event.

        Goes through ``async_add_chore`` like the ``add_chore`` service, with
        its default points. A timed event sets the chore's due time and files
        it under the time-of-day period that contains it.
        """
        name = (name or "").strip()
        if not name:
            raise self._calendar_error("calendar_empty_title")
        today = dt_util.as_local(dt_util.now()).date()
        if day < today:
            raise self._calendar_error("calendar_past_date")
        if not self.storage.get_child(child_id):
            raise ValueError(f"Unknown child: {child_id}")
        return await self.async_add_chore(
            name=name,
            description=(description or "").strip(),
            assigned_to=[child_id],
            schedule_mode="one_shot",
            created_date=day.isoformat(),
            time_category=self._period_for_time(start_time) if start_time else "anytime",
            due_time=start_time.strftime("%H:%M") if start_time else "",
        )

    async def async_move_chore_occurrence(
        self,
        chore_id: str,
        origin: date,
        new_day: date,
        *,
        start_time: time | None = None,
        all_day: bool | None = None,
        summary: str | None = None,
    ) -> Chore:
        """Move one occurrence of a chore to ``new_day``.

        ``origin`` is the occurrence's scheduled date (its identity, which a
        move never changes). A one-off chore simply takes the new date — and a
        new title or time if the event changed them. A repeating chore moves
        only this occurrence; its title and time of day belong to the whole
        series, so changing those here is refused.
        """
        chore = self.storage.get_chore(chore_id)
        if not chore:
            raise self._calendar_error("calendar_unknown_event")
        today = dt_util.as_local(dt_util.now()).date()
        current = self._occurrence_day(chore, origin)
        if new_day < today or current < today:
            raise self._calendar_error("calendar_past_date")

        old_start = self._occurrence_start_time(chore, current)
        time_changed = all_day is not None and (
            (all_day and old_start is not None) or (not all_day and start_time != old_start)
        )
        title = (summary or "").strip()

        if getattr(chore, "schedule_mode", "specific_days") == "one_shot":
            if title:
                chore.name = title
            chore.created_date = new_day.isoformat()
            if time_changed:
                chore.time_category = self._period_for_time(start_time) if start_time else "anytime"
                chore.due_time = start_time.strftime("%H:%M") if start_time else ""
            await self.async_update_chore(chore)
            return chore

        if title and title != chore.name:
            raise self._calendar_error("calendar_rename_series")
        if time_changed:
            raise self._calendar_error("calendar_time_follows_chore")
        if new_day == current:
            return chore
        if self._is_chore_scheduled_for_date(chore, new_day):
            raise self._calendar_error("calendar_already_scheduled", chore=chore.name, date=new_day.isoformat())

        moved = dict(getattr(chore, "moved_occurrences", None) or {})
        if new_day == origin:
            moved.pop(origin.isoformat(), None)
        else:
            moved[origin.isoformat()] = new_day.isoformat()
        chore.moved_occurrences = self._prune_moved_occurrences(moved, today)
        await self.async_update_chore(chore)
        return chore

    async def async_remove_chore_occurrence(self, chore_id: str, origin: date) -> Chore:
        """Remove one occurrence of a chore — that day only.

        A repeating chore records the removal and carries on as normal on every
        other day. A one-off chore has only the one occurrence, so it is
        switched off, exactly as if it had expired.
        """
        chore = self.storage.get_chore(chore_id)
        if not chore:
            raise self._calendar_error("calendar_unknown_event")
        today = dt_util.as_local(dt_util.now()).date()
        if self._occurrence_day(chore, origin) < today:
            raise self._calendar_error("calendar_past_date")

        if getattr(chore, "schedule_mode", "specific_days") == "one_shot":
            chore.enabled = False
        else:
            moved = dict(getattr(chore, "moved_occurrences", None) or {})
            moved[origin.isoformat()] = ""
            chore.moved_occurrences = self._prune_moved_occurrences(moved, today)
        await self.async_update_chore(chore)
        return chore

    @staticmethod
    def _occurrence_day(chore: Chore, origin: date) -> date:
        """Where the occurrence scheduled for ``origin`` currently sits."""
        if getattr(chore, "schedule_mode", "specific_days") == "one_shot":
            try:
                return date.fromisoformat(getattr(chore, "created_date", "") or "")
            except ValueError:
                return origin
        dst = (getattr(chore, "moved_occurrences", None) or {}).get(origin.isoformat())
        if dst:
            try:
                return date.fromisoformat(dst)
            except ValueError:
                pass
        return origin
