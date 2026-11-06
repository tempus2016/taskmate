"""Week planner (admin panel): who gets which rotation chore, and saving a planned week.

The panel works out which chore falls on which day itself (it has to, to show
unsaved changes as they are made), with the same rules as the calendar
projection. Two things it can't know are asked of the backend:

* **Rotation picks** — whose turn an alternating/random/balanced chore is on a
  given day, and who won a day's occurrence at auction. Read with the same
  computation the projection report and the daily assignment use.
* **Saving** — every change the parent planned, applied in one batch through
  ``async_update_chore`` with ``refresh=False`` and then one save and one
  refresh (#794). Each chore's change stands alone: one that is refused (a
  past day, a day it is already on, a rotation chore given to one child) is
  reported and the rest still apply.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .errors import error_translation

_LOGGER = logging.getLogger(__name__)

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
PLANNER_MAX_CHANGES = 200
# Modes where a chore can simply be handed to one child. Rotation modes pick
# from a pool every day, and "unassigned" waits for someone to take it.
REASSIGNABLE_MODES = ("everyone", "first_come", "")

# Calendar refusals (#977) that the planner reports with its own wording.
_CALENDAR_CODES = {
    "calendar_past_date": "past_date",
    "calendar_already_scheduled": "already_scheduled",
}


class PlanError(ValueError):
    """A planned change that can't be made, with a code the panel translates."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class PlannerMixin:
    """The admin panel's week planner."""

    def week_plan(self, anchor: date | None = None) -> dict[str, Any]:
        """Rotation picks for the Monday-to-Sunday week containing ``anchor``."""
        today = dt_util.as_local(dt_util.now()).date()
        anchor = anchor or today
        start = anchor - timedelta(days=anchor.weekday())
        chores = [c for c in self.storage.get_chores() if getattr(c, "enabled", True)]
        days = []
        for offset in range(7):
            day = start + timedelta(days=offset)
            picks = {
                chore_id: child_id for chore_id, child_id in self._compute_daily_assignments(day).items() if child_id
            }
            # Won at auction (#982): that day's occurrence is the winner's.
            for chore in chores:
                winner = self.auction_winner(chore, day)
                if winner:
                    picks[chore.id] = winner
            days.append({"date": day.isoformat(), "picks": picks})
        return {"start": start.isoformat(), "today": today.isoformat(), "days": days}

    async def async_apply_week_plan(self, changes: list[dict]) -> dict[str, Any]:
        """Apply each chore's planned change; one save and refresh at the end."""
        today = dt_util.as_local(dt_util.now()).date()
        results = []
        applied = 0
        for change in changes:
            chore_id = change.get("chore_id", "")
            try:
                await self._apply_planned_change(change, today)
            except PlanError as err:
                results.append({"chore_id": chore_id, "ok": False, "code": err.code, "error": str(err)})
                continue
            except ServiceValidationError as err:
                key = getattr(err, "translation_key", "") or ""
                results.append(
                    {
                        "chore_id": chore_id,
                        "ok": False,
                        "code": _CALENDAR_CODES.get(key, "invalid"),
                        "error": str(err) or key,
                        **error_translation(err),
                    }
                )
                continue
            except ValueError as err:
                results.append(
                    {"chore_id": chore_id, "ok": False, "code": "invalid", "error": str(err), **error_translation(err)}
                )
                continue
            applied += 1
            results.append({"chore_id": chore_id, "ok": True})
        if applied:
            await self.storage.async_save()
            await self.async_refresh()
        return {"applied": applied, "results": results}

    async def _apply_planned_change(self, change: dict, today: date) -> None:
        """Check one chore's change in full, then save it — or touch nothing."""
        chore = self.storage.get_chore(change.get("chore_id", ""))
        if chore is None:
            raise PlanError("not_found", f"Chore {change.get('chore_id')} not found")
        mode = getattr(chore, "schedule_mode", "specific_days")

        if "due_days" in change:
            if mode != "specific_days":
                raise PlanError("wrong_schedule", "Only a chore on set weekdays has days to change")
            days = [d for d in WEEKDAYS if d in set(change["due_days"])]
            # An empty list means "every day": never let a move turn into that.
            if not days:
                raise PlanError("empty_days", "A chore needs at least one day")
            chore.due_days = days

        if "created_date" in change:
            if mode != "one_shot":
                raise PlanError("wrong_schedule", "Only a one-off chore has a date")
            new_day = date.fromisoformat(change["created_date"])
            if new_day < today:
                raise PlanError("past_date", "A one-off chore can't be moved into the past")
            # A one-off moved to another day gets a fresh run, as in the chore
            # editor: switched back on, with nobody's earlier finish holding it off.
            if new_day.isoformat() != (chore.created_date or ""):
                chore.enabled = True
                chore.disabled_for = []
            chore.created_date = new_day.isoformat()

        if "recurrence_day" in change or "recurrence_start" in change:
            if mode != "recurring":
                raise PlanError("wrong_schedule", "Only a repeating chore has a series to move")
            if "recurrence_day" in change:
                chore.recurrence_day = change["recurrence_day"] or ""
            if "recurrence_start" in change:
                chore.recurrence_start = change["recurrence_start"] or ""

        if "assigned_to" in change:
            if getattr(chore, "assignment_mode", "everyone") not in REASSIGNABLE_MODES:
                raise PlanError("rotation", "A rotation chore keeps its rotation")
            known = {c.id for c in self.storage.get_children()}
            who = list(dict.fromkeys(change["assigned_to"]))
            if not who or any(child_id not in known for child_id in who):
                raise PlanError("unknown_child", "Unknown child")
            chore.assigned_to = who

        moves = change.get("moves") or []
        if moves and mode == "one_shot":
            raise PlanError("wrong_schedule", "A one-off chore moves by its date")
        for move in moves:
            self._move_series_occurrence(
                chore, date.fromisoformat(move["origin"]), date.fromisoformat(move["date"]), today
            )

        await self.async_update_chore(chore, refresh=False)
