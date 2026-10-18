"""Personal bests (#1099): a child's own records, and the moment they beat one.

Badges and streak milestones celebrate round numbers set by a parent. A
personal best is the child's own bar: the most points they have ever earned
in a day or a week, the most chores in a day, their biggest single award and
their longest streak. Each record keeps the value and the day it was set.

Records are checked after every approval. The first time a measure is seen
it is stored quietly as the baseline — a child's very first chore is not
"five records at once". From then on, going past a stored value fires
``taskmate_personal_best``, the opt-in ``personal_best`` notification and a
tier-2 celebration, and the record shows as new on the child's card for the
rest of the day.

When an approval is undone or rejected the affected day or week is
recomputed from the completions still on file; a record that no longer
holds falls back to the best the kept history can show. Records older than
the kept history are left as they are.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from . import notify_strings
from .const import NOTIF_TYPE_PERSONAL_BEST

_LOGGER = logging.getLogger(__name__)

RECORD_KEYS: tuple[str, ...] = (
    "longest_streak",
    "best_day_points",
    "best_day_chores",
    "best_week_points",
    "best_single_award",
)
_DAY_RECORDS = ("best_day_points", "best_day_chores")
_WEEK_RECORDS = ("best_week_points",)


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


class PersonalBestsMixin:
    """Per-child records with a new-record celebration."""

    def _personal_bests(self) -> dict[str, dict[str, Any]]:
        return self.storage.get_section("personal_bests", dict)

    def _child_completions(self, child_id: str) -> list:
        return [c for c in self.storage.get_completions() if c.child_id == child_id and c.approved]

    def _local_day(self, comp) -> date:
        return dt_util.as_local(comp.completed_at).date()

    def _measures_for(self, child, completions: list) -> dict[str, tuple[int, str]]:
        """Each record's current value with the day it belongs to."""
        today = dt_util.as_local(dt_util.now()).date()
        week_start = _week_start(today)
        day_points = day_chores = week_points = 0
        single = (0, "")
        for comp in completions:
            day = self._local_day(comp)
            pts = int(comp.points_awarded or 0)
            if day == today:
                day_points += pts
                if not comp.bonus_subtask_id:
                    day_chores += 1
            if day >= week_start:
                week_points += pts
            if pts > single[0]:
                single = (pts, day.isoformat())
        return {
            "longest_streak": (int(getattr(child, "current_streak", 0) or 0), today.isoformat()),
            "best_day_points": (day_points, today.isoformat()),
            "best_day_chores": (day_chores, today.isoformat()),
            "best_week_points": (week_points, week_start.isoformat()),
            "best_single_award": single,
        }

    def personal_bests_state(self, child) -> dict[str, Any]:
        """The records board for a card, or {} while there is nothing to show.

        ``new_today`` lists the records beaten today, so a card can make a
        fuss for the rest of the day.
        """
        section = self._personal_bests()
        records = (section.get(child.id) or {}) if isinstance(section, dict) else {}
        out: dict[str, Any] = {}
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        new_today = []
        for key in RECORD_KEYS:
            rec = records.get(key)
            if not rec:
                continue
            entry = {"value": int(rec.get("value", 0) or 0), "date": rec.get("date", "") or ""}
            if rec.get("previous") is not None and str(rec.get("set_at", ""))[:10] == today:
                entry["previous"] = int(rec["previous"])
                new_today.append(key)
            out[key] = entry
        if "longest_streak" not in out and int(getattr(child, "best_streak", 0) or 0) > 0:
            # Streaks were tracked long before records were: show the old best
            # so nobody starts from zero. It has no date of its own.
            out["longest_streak"] = {"value": int(child.best_streak), "date": ""}
        if new_today:
            out["new_today"] = new_today
        return out

    async def async_check_personal_bests(self, child_id: str, refresh: bool = True) -> list[str]:
        """Store any measure now past its record. Returns the records beaten (not baselines).

        Runs after the approval path's own refresh, so when something changed
        the cards need another push or the new record sits unseen until the
        next unrelated update. Batch callers (a filled team, Approve all) pass
        ``refresh=False`` and refresh once themselves (#794).
        """
        child = self.get_child(child_id)
        if child is None:
            return []
        section = self._personal_bests()
        if not isinstance(section, dict):
            return []
        records = section.setdefault(child.id, {})
        measures = self._measures_for(child, self._child_completions(child.id))
        now = dt_util.now()
        beaten: list[str] = []
        changed = False
        for key, (value, day) in measures.items():
            if value <= 0:
                continue
            rec = records.get(key)
            if rec is None:
                if key == "longest_streak" and int(getattr(child, "best_streak", 0) or 0) > value:
                    # The old best streak is the bar to beat, not today's run.
                    records[key] = {"value": int(child.best_streak), "date": "", "set_at": now.isoformat()}
                else:
                    records[key] = {"value": value, "date": day, "set_at": now.isoformat()}
                changed = True
                continue
            previous = int(rec.get("value", 0) or 0)
            if value <= previous:
                continue
            records[key] = {"value": value, "date": day, "set_at": now.isoformat(), "previous": previous}
            changed = True
            beaten.append(key)
        if not changed:
            return []
        await self.storage.async_save()
        points_name = self.storage.get_points_name()
        for key in beaten:
            rec = records[key]
            label = notify_strings.render(self.hass, f"record_{key}", {"points_name": points_name})
            payload = {
                "child_id": child.id,
                "child_name": child.name,
                "record": key,
                "value": rec["value"],
                "previous": rec["previous"],
                "date": rec["date"],
                "timestamp": now.isoformat(),
            }
            self.hass.bus.async_fire("taskmate_personal_best", payload)
            if getattr(self, "notifications", None):
                await self.notifications.fire(
                    NOTIF_TYPE_PERSONAL_BEST,
                    {**payload, "record_label": label, "points_name": points_name},
                )
            if hasattr(self, "_celebrate"):
                await self._celebrate(
                    child,
                    "personal_best",
                    notify_strings.render(
                        self.hass,
                        "celebrate_personal_best",
                        {"child_name": child.name, "record_label": label, "value": rec["value"]},
                    ),
                    tier=2,
                    extra={"record": key, "value": rec["value"], "previous": rec["previous"]},
                )
        if refresh:
            await self.async_refresh()
        return beaten

    async def async_recompute_personal_bests(self, child_id: str) -> None:
        """After a reversal: a record set on a day (or week) we still hold must still be true."""
        section = self._personal_bests()
        records = section.get(child_id) if isinstance(section, dict) else None
        if not records:
            return
        completions = self._child_completions(child_id)
        if completions:
            oldest = min(self._local_day(c) for c in completions)
        else:
            oldest = dt_util.as_local(dt_util.now()).date()
        days: dict[str, dict[str, int]] = {}
        single: dict[str, int] = {}
        for comp in completions:
            day = self._local_day(comp).isoformat()
            pts = int(comp.points_awarded or 0)
            bucket = days.setdefault(day, {"points": 0, "chores": 0})
            bucket["points"] += pts
            if not comp.bonus_subtask_id:
                bucket["chores"] += 1
            single[day] = max(single.get(day, 0), pts)
        weeks: dict[str, int] = {}
        for day, bucket in days.items():
            wk = _week_start(date.fromisoformat(day)).isoformat()
            weeks[wk] = weeks.get(wk, 0) + bucket["points"]

        def best(table: dict[str, int]) -> tuple[int, str]:
            if not table:
                return (0, "")
            day, value = max(table.items(), key=lambda kv: (kv[1], kv[0]))
            return (value, day)

        tables = {
            "best_day_points": {d: b["points"] for d, b in days.items()},
            "best_day_chores": {d: b["chores"] for d, b in days.items()},
            "best_week_points": weeks,
            "best_single_award": single,
        }
        changed = False
        for key, table in tables.items():
            rec = records.get(key)
            if not rec or not rec.get("date"):
                continue
            rec_day = date.fromisoformat(rec["date"])
            if key in _WEEK_RECORDS:
                in_history = rec_day + timedelta(days=6) >= oldest
            else:
                in_history = rec_day >= oldest
            if not in_history:
                continue
            still = table.get(rec["date"], 0)
            if still >= int(rec.get("value", 0) or 0):
                continue
            value, day = best(table)
            if value > 0:
                records[key] = {"value": value, "date": day, "set_at": ""}
            else:
                records.pop(key, None)
            changed = True
        if changed:
            await self.storage.async_save()
