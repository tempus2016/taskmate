"""``taskmate.*`` services for editing and deleting chores (#1156).

The panel edits chores over its WebSocket API, which some clients can't use
(an AI assistant's Home Assistant connector, Assist, a plain script). These
services give them the same reach: ``update_chore`` and ``delete_chore`` by
chore id, plus the scheduling and assignment fields ``add_chore`` was missing.

Both go through the caller's ``_admin`` wrapper, so they follow the same rule
as ``add_chore``: a signed-in user needs to be an administrator, an automation
or script with no user behind it runs, and every call lands in the audit log.

``assigned_to`` takes child names as well as ids, because a name is what a
person (or an assistant) actually has. A name that matches nobody, or more
than one child, is refused with the list of valid names rather than guessed.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import date

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import (
    ASSIGNMENT_MODES,
    DIFFICULTY_TIERS,
    DOMAIN,
    RECURRENCE_PERIOD_DAYS,
    SCHEDULE_MODES,
    TEAM_POINTS_MODES,
    TEAM_SIZE_MAX,
    TIME_CATEGORIES,
    recurrence_interval_days,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_UPDATE_CHORE = "update_chore"
SERVICE_DELETE_CHORE = "delete_chore"

CHORE_SERVICES: tuple[str, ...] = (SERVICE_UPDATE_CHORE, SERVICE_DELETE_CHORE)

WEEKDAYS: tuple[str, ...] = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

Handler = Callable[[ServiceCall], Awaitable[None]]
Wrapper = Callable[[Handler], Handler]


def _weekday(value) -> str:
    """A full weekday name, any case ("Monday" -> "monday")."""
    text = str(value).strip().lower()
    if text not in WEEKDAYS:
        raise vol.Invalid(f"Unknown weekday {value!r}; use one of {', '.join(WEEKDAYS)}")
    return text


def _recurrence(value) -> str:
    """weekly, every_2_weeks, monthly, every_3_months, every_6_months or every_<N>_days."""
    text = str(value).strip().lower()
    if text in RECURRENCE_PERIOD_DAYS or recurrence_interval_days(text) is not None:
        return text
    raise vol.Invalid(
        f"Unknown recurrence {value!r}; use {', '.join(RECURRENCE_PERIOD_DAYS)} or every_<N>_days (N from 2 to 365)"
    )


def _iso_date_or_empty(value) -> str:
    """'' (no start date) or a YYYY-MM-DD date."""
    if value in (None, ""):
        return ""
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError as err:
        raise vol.Invalid(f"Invalid date {value!r}; use YYYY-MM-DD") from err


def _hhmm_or_empty(value) -> str:
    """'' (no due time) or an HH:MM time, normalised to two digits each."""
    if value in (None, ""):
        return ""
    parts = str(value).strip().split(":")
    # A time selector sends HH:MM:SS; the seconds are dropped.
    if len(parts) == 3 and parts[2].isdigit():
        parts = parts[:2]
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
        raise vol.Invalid(f"Invalid time {value!r}; use HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise vol.Invalid(f"Invalid time {value!r}; use HH:MM")
    return f"{hour:02d}:{minute:02d}"


def _str_list(value) -> list[str]:
    """One string or a list of them, blanks dropped."""
    items = value if isinstance(value, list) else [value]
    return [str(v).strip() for v in items if v is not None and str(v).strip()]


_NON_NEGATIVE = vol.All(vol.Coerce(int), vol.Range(min=0))

# The scheduling and assignment fields the panel has and add_chore lacked.
# No defaults: add_chore falls back to the coordinator's own, and update_chore
# only touches the fields a call actually names.
SCHEDULE_FIELDS: dict = {
    vol.Optional("assignment_mode"): vol.In(ASSIGNMENT_MODES),
    vol.Optional("schedule_mode"): vol.In(SCHEDULE_MODES),
    vol.Optional("due_days"): vol.All(_str_list, [_weekday]),
    vol.Optional("recurrence"): _recurrence,
    vol.Optional("recurrence_day"): vol.Any("", None, _weekday),
    vol.Optional("recurrence_start"): _iso_date_or_empty,
    vol.Optional("due_time"): _hhmm_or_empty,
    vol.Optional("daily_limit"): vol.All(vol.Coerce(int), vol.Range(min=1)),
}

# Everything update_chore can change: the add_chore fields, minus the ones
# that only make sense at creation (one_shot / expires_in_minutes — use
# schedule_mode instead), plus enabled.
UPDATE_FIELDS: dict = {
    vol.Required("chore_id"): vol.All(str, vol.Length(min=1)),
    vol.Optional("name"): vol.All(str, vol.Strip, vol.Length(min=1, max=200)),
    vol.Optional("description"): str,
    vol.Optional("points"): _NON_NEGATIVE,
    vol.Optional("assigned_to"): _str_list,
    vol.Optional("time_category"): vol.In(TIME_CATEGORIES),
    vol.Optional("difficulty"): vol.In(DIFFICULTY_TIERS),
    vol.Optional("requires_approval"): vol.Boolean(),
    vol.Optional("enabled"): vol.Boolean(),
    vol.Optional("speed_bonus_points"): _NON_NEGATIVE,
    vol.Optional("team_size"): vol.All(vol.Coerce(int), vol.Range(min=0, max=TEAM_SIZE_MAX)),
    vol.Optional("team_points_mode"): vol.In(TEAM_POINTS_MODES),
    vol.Optional("team_bonus"): _NON_NEGATIVE,
    vol.Optional("times"): vol.All(lambda v: v if isinstance(v, list) else [v], [dict]),
    vol.Optional("times_bonus"): vol.All(vol.Coerce(int), vol.Range(min=0, max=1000)),
    **SCHEDULE_FIELDS,
}

DELETE_FIELDS: dict = {
    vol.Required("chore_id"): vol.All(str, vol.Length(min=1)),
    vol.Required("confirm"): vol.Boolean(),
}


def resolve_children(coordinator, refs) -> list[str]:
    """Turn child ids or names into ids, refusing anything unknown or ambiguous.

    An exact id wins over a name, so a child called the same as another's id
    can't hijack it. Names match case-insensitively, ignoring outer spaces.
    """
    children = list(coordinator.storage.get_children())
    by_id = {c.id: c for c in children}
    valid = ", ".join(sorted(c.name for c in children)) or "none"
    resolved: list[str] = []
    for ref in _str_list(refs or []):
        if ref in by_id:
            child_id = ref
        else:
            matches = [c for c in children if (c.name or "").strip().casefold() == ref.casefold()]
            if not matches:
                raise ServiceValidationError(f"Unknown child {ref!r}. Valid children: {valid}")
            if len(matches) > 1:
                ids = ", ".join(c.id for c in matches)
                raise ServiceValidationError(f"More than one child is called {ref!r}; use the child id instead ({ids})")
            child_id = matches[0].id
        if child_id not in resolved:
            resolved.append(child_id)
    return resolved


def _today() -> str:
    return dt_util.as_local(dt_util.now()).date().isoformat()


async def async_update_chore_from_call(coordinator, data: dict) -> None:
    """Apply an update_chore call to the stored chore."""
    changes = dict(data)
    chore_id = changes.pop("chore_id")
    # storage.get_chore builds a fresh Chore from the stored dict, so nothing
    # set on it below reaches storage unless async_update_chore accepts it.
    chore = coordinator.storage.get_chore(chore_id)
    if chore is None:
        raise ServiceValidationError(f"Chore {chore_id} not found")
    if not changes:
        raise ServiceValidationError("Nothing to update: name at least one field to change")
    if "assigned_to" in changes:
        changes["assigned_to"] = resolve_children(coordinator, changes["assigned_to"])
    if "recurrence_day" in changes:
        changes["recurrence_day"] = changes["recurrence_day"] or ""
    # Becoming a one-off works the way creating one does: it's for today, once.
    if changes.get("schedule_mode", chore.schedule_mode) == "one_shot":
        changes["daily_limit"] = 1
        if chore.schedule_mode != "one_shot":
            chore.created_date = _today()
    for field, value in changes.items():
        setattr(chore, field, list(value) if isinstance(value, list) else value)
    # Teamwork, set-time and every other cross-field rule is checked here,
    # before storage is written, so a refused edit changes nothing.
    await coordinator.async_update_chore(chore)


async def async_delete_chore_from_call(coordinator, data: dict) -> None:
    """Delete a chore the same way the panel does (it goes to Recently deleted)."""
    chore_id = data["chore_id"]
    if not data.get("confirm"):
        raise ServiceValidationError("Set confirm: true to delete the chore")
    if coordinator.storage.get_chore(chore_id) is None:
        raise ServiceValidationError(f"Chore {chore_id} not found")
    await coordinator.async_remove_chore(chore_id)


def async_register_chore_services(
    hass: HomeAssistant,
    *,
    admin_action: Wrapper,
    get_coordinator: Callable[[], object],
) -> None:
    """Register update_chore and delete_chore with the caller's admin wrapper."""

    def _coordinator():
        coordinator = get_coordinator()
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
        return coordinator

    async def handle_update_chore(call: ServiceCall) -> None:
        coordinator = _coordinator()
        if coordinator:
            await async_update_chore_from_call(coordinator, call.data)

    async def handle_delete_chore(call: ServiceCall) -> None:
        coordinator = _coordinator()
        if coordinator:
            await async_delete_chore_from_call(coordinator, call.data)

    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_CHORE, admin_action(handle_update_chore), schema=vol.Schema(UPDATE_FIELDS)
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_CHORE, admin_action(handle_delete_chore), schema=vol.Schema(DELETE_FIELDS)
    )
