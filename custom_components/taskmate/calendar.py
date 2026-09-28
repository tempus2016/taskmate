"""Calendar platform for TaskMate.

Exposes one read-only ``calendar.taskmate_<child>`` entity per child. Events are
derived live from existing TaskMate data — there is no second store and nothing
to keep in sync:

  * chore occurrences come from the recurrence/assignment engine
    (``_is_chore_scheduled_for_date`` + ``_compute_active_children``), rendered
    as timed events inside the configured time-of-day window or as all-day
    events when the chore is "anytime";
  * away / unavailable blocks come from ``_is_child_on_vacation`` (#525),
    coalesced into multi-day all-day events. On an away day the child's chores
    are hidden, mirroring the rest of the integration.

Two-way (#977): a parent or admin can edit the calendar from Home Assistant.
Creating an event adds a one-off chore for the child; moving an occurrence
moves that one day (a one-off chore just changes date); deleting one removes
that day only. Each chore occurrence carries a uid of
``taskmate-chore:<chore id>:<scheduled date>`` so an edit can find it again —
the scheduled date stays the identity even after the occurrence is moved.
Moving or removing a whole repeating series is refused: edit the chore.
Completing a chore from the calendar is intentionally not supported.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEntityFeature, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import authz
from .const import DOMAIN
from .coordinator import TaskMateCoordinator
from .entity import taskmate_device_info
from .models import Child, Chore

try:  # The websocket connection a calendar-panel edit arrived on (see _acting_user_ids).
    from homeassistant.components.websocket_api.connection import current_connection
except ImportError:  # pragma: no cover - present on every supported HA version
    current_connection = None

_LOGGER = logging.getLogger(__name__)

# Prefix of every chore occurrence's event uid: taskmate-chore:<chore id>:<date>.
_UID_PREFIX = "taskmate-chore"
# The description marker TaskMate stamps on events it publishes to other
# calendars. A create_event carrying it is TaskMate talking to itself (a chore
# published to a TaskMate calendar) and must not spawn a new chore.
_PUBLISHED_MARKER = "taskmate:chore:"

# How far ahead the `event` (next-up) property scans for the soonest event.
_NEXT_EVENT_HORIZON_DAYS = 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one calendar entity per child, adding more as children are created."""
    coordinator: TaskMateCoordinator = hass.data[DOMAIN][entry.entry_id]
    tracked: set[str] = set()

    def _new_entities() -> list[TaskMateCalendar]:
        out: list[TaskMateCalendar] = []
        for child in coordinator.data.get("children", []):
            if child.id in tracked:
                continue
            tracked.add(child.id)
            out.append(TaskMateCalendar(coordinator, entry, child))
        return out

    async_add_entities(_new_entities())

    @callback
    def _async_add_new() -> None:
        new = _new_entities()
        if new:
            async_add_entities(new)

    coordinator.async_add_listener(_async_add_new)


def _chore_applies_to_child(coordinator: TaskMateCoordinator, chore: Chore, child_id: str, day: date) -> bool:
    """True if ``chore`` is scheduled for ``child_id`` on ``day``.

    Combines the recurrence schedule with the assignment engine so the calendar
    matches who would actually see the chore — without consulting completion
    state (the calendar projects the schedule, not today's done/not-done).
    """
    if not getattr(chore, "enabled", True):
        return False
    if getattr(chore, "assignment_mode", "everyone") == "unassigned":
        return False
    if not coordinator._is_chore_scheduled_for_date(chore, day):
        return False
    active = coordinator._compute_active_children(chore, day)
    if active:
        return child_id in active
    # Empty active set means an unrestricted "everyone" chore (no assigned_to).
    return not chore.assigned_to


def _chore_description(chore: Chore) -> str:
    """Compact one-line description for a chore event."""
    parts = ["TaskMate chore"]
    pts = getattr(chore, "points", 0) or 0
    parts.append(f"{pts} pts")
    cat = getattr(chore, "time_category", "anytime") or "anytime"
    if cat != "anytime":
        parts.append(cat)
    return " · ".join(parts)


def _occurrence_uid(chore_id: str, origin: date) -> str:
    """The stable uid for the occurrence of ``chore_id`` scheduled on ``origin``."""
    return f"{_UID_PREFIX}:{chore_id}:{origin.isoformat()}"


def _parse_day(value: str) -> date | None:
    """Parse an occurrence date: ISO (2026-06-22) or RFC 5545 (20260622[T...])."""
    digits = str(value or "").replace("-", "")[:8]
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def _parse_occurrence_uid(uid: str, recurrence_id: str | None) -> tuple[str, date] | None:
    """Split an event uid into (chore id, scheduled date), or None if not ours.

    Accepts the full per-occurrence uid, or the bare ``taskmate-chore:<id>``
    series uid plus a ``recurrence_id`` naming the occurrence.
    """
    parts = str(uid or "").split(":")
    if len(parts) < 2 or parts[0] != _UID_PREFIX or not parts[1]:
        return None
    raw = parts[2] if len(parts) >= 3 else recurrence_id
    day = _parse_day(raw) if raw else None
    return (parts[1], day) if day else None


def _local_date_time(value: date | datetime) -> tuple[date, time | None]:
    """Split an event start into its local date and time (None = all-day)."""
    if isinstance(value, datetime):
        local = dt_util.as_local(value) if value.tzinfo else value
        return local.date(), local.time().replace(second=0, microsecond=0)
    return value, None


def _as_local_dt(value: date | datetime) -> datetime:
    """Normalise a CalendarEvent start/end to an aware local datetime for sorting."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return value
    return datetime(value.year, value.month, value.day, tzinfo=dt_util.DEFAULT_TIME_ZONE)


class TaskMateCalendar(CoordinatorEntity, CalendarEntity):
    """A calendar of one child's chores and away periods, editable by parents."""

    _attr_icon = "mdi:calendar-account"
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT | CalendarEntityFeature.UPDATE_EVENT | CalendarEntityFeature.DELETE_EVENT
    )
    # Context handed over by a calendar.* service call (see async_set_context).
    _edit_context: Any = None

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
        child: Child,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._child_id = child.id
        self._attr_unique_id = f"{entry.entry_id}_{child.id}_calendar"
        self._attr_name = f"TaskMate {child.name}"
        self._events_cache: list[CalendarEvent] | None = None
        self._events_key: tuple | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return taskmate_device_info(self._entry.entry_id)

    @property
    def _child(self) -> Child | None:
        return self.coordinator.storage.get_child(self._child_id)

    @property
    def available(self) -> bool:
        return self._child is not None and super().available

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next upcoming event (HA shows this as the entity state).

        Home Assistant reads this twice per state write (once for the state,
        once for the state attributes), and writes on every coordinator
        refresh — so the horizon projection is memoized against the same key
        the sensors use: the data snapshot plus the external-entity version
        that covers availability/visibility flips (#823). Only the cheap
        "which one is next" filter re-runs.
        """
        child = self._child
        if not child:
            return None
        now = dt_util.now()
        today = now.date()
        events = self._cached_horizon(child, today)
        upcoming = [e for e in events if _as_local_dt(e.end) > now]
        upcoming.sort(key=lambda e: _as_local_dt(e.start))
        return upcoming[0] if upcoming else None

    def _cached_horizon(self, child: Child, today: date) -> list[CalendarEvent]:
        """The next-up horizon for ``today``, rebuilt only when inputs change."""
        key = (
            today,
            id(self.coordinator.data),
            getattr(self.coordinator, "external_state_version", 0),
        )
        cached = getattr(self, "_events_cache", None)
        if cached is not None and getattr(self, "_events_key", None) == key:
            return cached
        events = self._build_events(child, today, today + timedelta(days=_NEXT_EVENT_HORIZON_DAYS))
        self._events_cache = events
        self._events_key = key
        return events

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all events overlapping the requested range."""
        # A calendar.get_events service call hands us a context too; drop it
        # so it can never vouch for a later edit (see async_set_context).
        self._edit_context = None
        child = self._child
        if not child:
            return []
        return self._build_events(child, start_date.date(), end_date.date())

    # ── Two-way editing (#977) ─────────────────────────────────────────────

    @callback
    def async_set_context(self, context: Any) -> None:
        """Remember the context of a calendar.* service call for the edit it precedes.

        Home Assistant sets the context immediately before invoking the entity
        method, with no await in between, and the edit consumes it at once.
        """
        parent = getattr(super(), "async_set_context", None)
        if parent is not None:
            parent(context)
        self._edit_context = context

    def _acting_user_ids(self) -> set[str]:
        """Every HA user behind the current edit.

        The calendar panel edits over the calendar/event/* websocket commands,
        which call the entity directly without setting a context — so the
        user there comes from the websocket connection itself. A calendar.*
        service call sets a context. Both are checked when both are present;
        neither (an automation or script) is a trusted caller, as elsewhere.
        """
        ids: set[str] = set()
        conn = current_connection.get() if current_connection is not None else None
        user = getattr(conn, "user", None) if conn is not None else None
        if user is not None and getattr(user, "id", None):
            ids.add(user.id)
        ctx, self._edit_context = self._edit_context, None
        if ctx is not None and getattr(ctx, "user_id", None):
            ids.add(ctx.user_id)
        return ids

    async def _async_require_parent(self) -> str:
        """Refuse the edit unless every acting user is a parent or an admin.

        Returns the acting user id for the audit log ("" when trusted).
        """
        ids = self._acting_user_ids()
        for user_id in ids:
            if not await authz.async_user_is_parent(self.hass, self.coordinator, user_id):
                raise Unauthorized(user_id=user_id)
        return sorted(ids)[0] if ids else ""

    async def _async_audit(self, user_id: str, action: str, target: str) -> None:
        """Record the edit in TaskMate's audit log. Never blocks the edit."""
        user_name = ""
        if user_id:
            try:
                user = await self.hass.auth.async_get_user(user_id)
                user_name = user.name if user else ""
            except Exception:  # noqa: BLE001 - audit must never break the action
                user_name = ""
        child = self._child
        who = child.name if child else self._child_id
        try:
            await self.coordinator.async_record_audit(user_id, user_name, action, f"{who}: {target}")
        except Exception:  # noqa: BLE001 - audit must never break the action
            _LOGGER.debug("Failed to record calendar audit for %s", action, exc_info=True)

    def _resolve_occurrence(self, uid: str, recurrence_id: str | None) -> tuple[Chore, date]:
        """The chore and scheduled date behind ``uid`` — on *this* child's calendar."""
        parsed = _parse_occurrence_uid(uid, recurrence_id)
        chore = self.coordinator.storage.get_chore(parsed[0]) if parsed else None
        if chore is None:
            raise self.coordinator._calendar_error("calendar_unknown_event")
        origin = parsed[1]
        current = self.coordinator._occurrence_day(chore, origin)
        with self.coordinator.availability_build_scope():
            applies = _chore_applies_to_child(self.coordinator, chore, self._child_id, current)
        if not applies:
            raise self.coordinator._calendar_error("calendar_unknown_event")
        return chore, origin

    @staticmethod
    def _refuse_series(recurrence_range: str | None, rrule: str | None = None) -> None:
        if (recurrence_range or "").upper() == "THISANDFUTURE" or rrule:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="calendar_series_not_supported")

    async def async_create_event(self, **kwargs: Any) -> None:
        """Add a one-off chore for this child on the event's date."""
        user_id = await self._async_require_parent()
        description = str(kwargs.get("description") or "")
        if _PUBLISHED_MARKER in description:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="calendar_own_event")
        if kwargs.get("rrule"):
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="calendar_repeating_create")
        day, start_time = _local_date_time(kwargs["dtstart"])
        chore = await self.coordinator.async_calendar_add_chore(
            self._child_id,
            str(kwargs.get("summary") or ""),
            day,
            description=description,
            start_time=start_time,
        )
        await self._async_audit(user_id, "calendar.create_event", f"{chore.name} ({day.isoformat()})")

    async def async_update_event(
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Move one occurrence (or a one-off chore) to the event's new date."""
        user_id = await self._async_require_parent()
        self._refuse_series(recurrence_range, event.get("rrule"))
        chore, origin = self._resolve_occurrence(uid, recurrence_id)
        new_day, start_time = _local_date_time(event["dtstart"])
        await self.coordinator.async_move_chore_occurrence(
            chore.id,
            origin,
            new_day,
            start_time=start_time,
            all_day=start_time is None,
            summary=event.get("summary"),
        )
        await self._async_audit(
            user_id, "calendar.move_event", f"{chore.name} ({origin.isoformat()} → {new_day.isoformat()})"
        )

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        """Remove one occurrence — that day only."""
        user_id = await self._async_require_parent()
        self._refuse_series(recurrence_range)
        chore, origin = self._resolve_occurrence(uid, recurrence_id)
        await self.coordinator.async_remove_chore_occurrence(chore.id, origin)
        await self._async_audit(user_id, "calendar.delete_event", f"{chore.name} ({origin.isoformat()})")

    def _build_events(self, child: Child, start_day: date, end_day: date) -> list[CalendarEvent]:
        with self.coordinator.availability_build_scope():
            return self._build_events_locked(child, start_day, end_day)

    def _build_events_locked(self, child: Child, start_day: date, end_day: date) -> list[CalendarEvent]:
        """Project the range. Must run inside ``availability_build_scope`` so the
        rotation pool and balanced-mode grouping resolve from the scope cache
        instead of rebuilding every stored chore/child per (chore, day) (#823).
        """
        coord = self.coordinator
        events: list[CalendarEvent] = []

        # ---- away blocks: coalesce consecutive away days into one all-day event ----
        run_start: date | None = None
        run_label: str | None = None
        day = start_day
        while day <= end_day:
            if coord._is_child_on_vacation(child, day):
                if run_start is None:
                    period = coord.active_vacation(day)
                    run_label = (period or {}).get("name") or ""
                    run_start = day
            elif run_start is not None:
                events.append(_away_event(run_start, day, run_label))
                run_start = None
            day += timedelta(days=1)
        if run_start is not None:
            events.append(_away_event(run_start, end_day + timedelta(days=1), run_label))

        # ---- chore occurrences (skipped on away days) ----
        chores = coord._cached_chores()
        tz = dt_util.DEFAULT_TIME_ZONE
        day = start_day
        while day <= end_day:
            if not coord._is_child_on_vacation(child, day):
                for chore in chores:
                    if not _chore_applies_to_child(coord, chore, child.id, day):
                        continue
                    window = coord._time_category_window(getattr(chore, "time_category", "anytime"), day)
                    desc = _chore_description(chore)
                    # The uid names the scheduled date, so an edit finds the
                    # occurrence again even after it has been moved (#977).
                    ident = _occurrence_ident(coord, chore, day)
                    if window is None:
                        events.append(
                            CalendarEvent(
                                start=day,
                                end=day + timedelta(days=1),
                                summary=chore.name,
                                description=desc,
                                **ident,
                            )
                        )
                    else:
                        start_dt, end_dt = window
                        events.append(
                            CalendarEvent(
                                start=start_dt.replace(tzinfo=tz),
                                end=end_dt.replace(tzinfo=tz),
                                summary=chore.name,
                                description=desc,
                                **ident,
                            )
                        )
            day += timedelta(days=1)

        return events


def _occurrence_ident(coord: TaskMateCoordinator, chore: Chore, day: date) -> dict[str, str]:
    """uid (+ recurrence_id for a repeating chore) of the occurrence shown on ``day``."""
    if getattr(chore, "schedule_mode", "specific_days") == "one_shot":
        return {"uid": _occurrence_uid(chore.id, day)}
    origin = coord.occurrence_origin(chore, day)
    return {"uid": _occurrence_uid(chore.id, origin), "recurrence_id": origin.isoformat()}


def _away_event(start_day: date, end_day_exclusive: date, label: str | None) -> CalendarEvent:
    """Build a coalesced all-day 'away' event over [start, end)."""
    summary = f"Away — {label}" if label else "Away"
    return CalendarEvent(
        start=start_day,
        end=end_day_exclusive,
        summary=summary,
        description="Unavailable — streak paused and chores hidden.",
    )
