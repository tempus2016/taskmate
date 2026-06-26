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

Read-only for now: completing a chore from the calendar is intentionally not
supported.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import TaskMateCoordinator
from .models import Child, Chore

_LOGGER = logging.getLogger(__name__)

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


def _chore_applies_to_child(
    coordinator: TaskMateCoordinator, chore: Chore, child_id: str, day: date
) -> bool:
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


def _as_local_dt(value: date | datetime) -> datetime:
    """Normalise a CalendarEvent start/end to an aware local datetime for sorting."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        return value
    return datetime(value.year, value.month, value.day, tzinfo=dt_util.DEFAULT_TIME_ZONE)


class TaskMateCalendar(CoordinatorEntity, CalendarEntity):
    """A read-only calendar of one child's chores and away periods."""

    _attr_icon = "mdi:calendar-account"

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

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="TaskMate",
            manufacturer="TaskMate",
            model="Family Chore Manager",
        )

    @property
    def _child(self) -> Child | None:
        return self.coordinator.storage.get_child(self._child_id)

    @property
    def available(self) -> bool:
        return self._child is not None and super().available

    @property
    def event(self) -> CalendarEvent | None:
        """The current or next upcoming event (HA shows this as the entity state)."""
        child = self._child
        if not child:
            return None
        now = dt_util.now()
        today = now.date()
        events = self._build_events(child, today, today + timedelta(days=_NEXT_EVENT_HORIZON_DAYS))
        upcoming = [e for e in events if _as_local_dt(e.end) > now]
        upcoming.sort(key=lambda e: _as_local_dt(e.start))
        return upcoming[0] if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all events overlapping the requested range."""
        child = self._child
        if not child:
            return []
        return self._build_events(child, start_date.date(), end_date.date())

    def _build_events(
        self, child: Child, start_day: date, end_day: date
    ) -> list[CalendarEvent]:
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
        chores = coord.storage.get_chores()
        tz = dt_util.DEFAULT_TIME_ZONE
        day = start_day
        while day <= end_day:
            if not coord._is_child_on_vacation(child, day):
                for chore in chores:
                    if not _chore_applies_to_child(coord, chore, child.id, day):
                        continue
                    window = coord._time_category_window(
                        getattr(chore, "time_category", "anytime"), day
                    )
                    desc = _chore_description(chore)
                    if window is None:
                        events.append(CalendarEvent(
                            start=day,
                            end=day + timedelta(days=1),
                            summary=chore.name,
                            description=desc,
                        ))
                    else:
                        start_dt, end_dt = window
                        events.append(CalendarEvent(
                            start=start_dt.replace(tzinfo=tz),
                            end=end_dt.replace(tzinfo=tz),
                            summary=chore.name,
                            description=desc,
                        ))
            day += timedelta(days=1)

        return events


def _away_event(start_day: date, end_day_exclusive: date, label: str | None) -> CalendarEvent:
    """Build a coalesced all-day 'away' event over [start, end)."""
    summary = f"Away — {label}" if label else "Away"
    return CalendarEvent(
        start=start_day,
        end=end_day_exclusive,
        summary=summary,
        description="Unavailable — streak paused and chores hidden.",
    )
