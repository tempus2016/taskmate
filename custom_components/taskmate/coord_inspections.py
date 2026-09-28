"""Surprise inspections (#981) mixin for TaskMateCoordinator.

A parent (or an optional random daily pick) flags a recently approved chore
for a spot check. The inspection stays open for a window; inside it the parent
passes it (a fixed bonus, paid as an ordinary points transaction, plus the
child's celebration) or fails it — either "just noted" (nothing changes) or
"sent back to redo": the chore goes back on the child's list as not done for
today, and finishing it again goes through the normal completion / approval
path but pays nothing, because the original points stand. An inspection left
undecided closes quietly when its window runs out, with a parent reminder
``INSPECTION_REMINDER_MINUTES`` before.

State lives under its own storage key (``inspections``): a list of small dicts
plus the random pick's bookkeeping. Window ends, reminders and the daily pick
run on timers, with a catch-up at startup for anything that came due while
Home Assistant was off.

Record shape: ``id, completion_id, child_id, chore_id, chore_name,
completed_on`` (local date of the inspected completion), ``points`` (what it
earned), ``status`` (open / passed / failed / redo / expired), ``bonus``,
``tell_child``, ``source`` (parent / random), ``started_at``, ``until``,
``reminded``, ``decided_at``, ``note``, ``bonus_txn_id`` and
``redo_completion_id``.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_time, async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    NOTIF_TYPE_INSPECTION_PASSED,
    NOTIF_TYPE_INSPECTION_REMINDER,
    NOTIF_TYPE_INSPECTION_STARTED,
)
from .models import clean_label, format_datetime, generate_id, parse_datetime
from .timewindow import parse_hhmm

_LOGGER = logging.getLogger(__name__)

# An approved chore can be inspected for this long after its approval, once.
INSPECTABLE_HOURS = 24
INSPECTION_REMINDER_MINUTES = 30
INSPECTION_BONUS_MAX = 10000
INSPECTION_NOTE_MAX = 200
# Finished inspections are kept this long for the activity feeds.
INSPECTION_KEEP_DAYS = 7
INSPECTION_KEEP_MAX = 100
# At most this many per child on the overview sensor (16 KB cap).
INSPECTION_CARD_MAX = 4
INSPECTION_WINDOWS = ("1h", "2h", "4h", "bed")
INSPECTION_FAIL_MODES = ("note", "redo", "ask")
_WINDOW_HOURS = {"1h": 1, "2h": 2, "4h": 4}
# "Until bedtime" asked for too close to bedtime gets an hour instead.
_BEDTIME_MIN_MINUTES = 30

DEFAULT_INSPECTION_BONUS = 10
DEFAULT_INSPECTION_WINDOW = "2h"
DEFAULT_INSPECTION_BEDTIME = "20:00"
DEFAULT_INSPECTION_PICK_TIME = "17:00"
DEFAULT_INSPECTION_PICK_CHANCE = 30

# Reason on the pass bonus's points transaction. The cards and the panel
# recognise the prefix (icon + translation); it stays undoable like a bonus.
PASS_REASON_PREFIX = "Inspection passed:"


def _at(value) -> datetime | None:
    try:
        return parse_datetime(value)
    except (TypeError, ValueError):
        return None


def _local_date(value) -> str:
    at = _at(value) if not isinstance(value, datetime) else value
    return dt_util.as_local(at).date().isoformat() if at else ""


class InspectionsMixin:
    """Spot-check a finished chore for a bonus."""

    # ── settings ─────────────────────────────────────────────────────────

    def _insp_flag(self, key: str, default: bool) -> bool:
        value = self.storage.get_setting(key, default)
        return value is True or str(value).lower() == "true"

    def _insp_int(self, key: str, default: int, low: int, high: int) -> int:
        try:
            value = int(float(self.storage.get_setting(key, default)))
        except (TypeError, ValueError):
            value = default
        return max(low, min(high, value))

    def inspections_enabled(self) -> bool:
        return self._insp_flag("inspections_enabled", True)

    def inspection_default_bonus(self) -> int:
        return self._insp_int("inspection_bonus", DEFAULT_INSPECTION_BONUS, 0, INSPECTION_BONUS_MAX)

    def inspection_default_window(self) -> str:
        value = self.storage.get_setting("inspection_window", DEFAULT_INSPECTION_WINDOW)
        return value if value in INSPECTION_WINDOWS else DEFAULT_INSPECTION_WINDOW

    def inspection_bedtime(self) -> tuple[int, int]:
        parsed = parse_hhmm(str(self.storage.get_setting("inspection_bedtime", DEFAULT_INSPECTION_BEDTIME) or ""))
        return parsed or parse_hhmm(DEFAULT_INSPECTION_BEDTIME)

    def inspection_fail_default(self) -> str:
        value = self.storage.get_setting("inspection_fail_mode", "note")
        return value if value in INSPECTION_FAIL_MODES else "note"

    def inspection_until(self, window: str, now: datetime) -> datetime:
        """When an inspection started at ``now`` with ``window`` closes."""
        if window == "bed":
            hour, minute = self.inspection_bedtime()
            local = dt_util.as_local(now)
            until = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if until - local >= timedelta(minutes=_BEDTIME_MIN_MINUTES):
                return until
            return now + timedelta(hours=1)
        return now + timedelta(hours=_WINDOW_HOURS.get(window, 2))

    # ── reads ────────────────────────────────────────────────────────────

    def _find_inspection(self, inspection_id: str) -> dict | None:
        return next((r for r in self.storage.get_inspections() if r.get("id") == inspection_id), None)

    def _require_open_inspection(self, inspection_id: str) -> dict:
        record = self._find_inspection(inspection_id)
        if record is None:
            raise ValueError("That inspection no longer exists. Refresh and try again.")
        if record.get("status") != "open":
            raise ValueError("That inspection has already been decided or has closed.")
        return record

    def _save_inspection(self, record: dict) -> None:
        rows = [r for r in self.storage.get_inspections() if r.get("id") != record.get("id")]
        rows.append(record)
        self.storage.set_inspections(rows)

    def _inspected_completion(self, completion_id: str):
        return next((c for c in self.storage.get_completions() if c.id == completion_id), None)

    def _inspection_item_name(self, completion) -> str:
        chore = self.get_chore(completion.chore_id)
        if chore is not None:
            return chore.name
        bounty = self.storage.get_bounty(getattr(completion, "bounty_id", "") or "")
        return getattr(bounty, "title", "") or ""

    def inspectable_error(self, completion, now: datetime | None = None) -> str:
        """Why ``completion`` can't be inspected right now ("" when it can)."""
        if completion is None:
            return "That chore no longer exists."
        if not completion.approved:
            return "Only approved chores can be inspected."
        if getattr(completion, "bonus_subtask_id", "") or completion.child_id == "__parent__":
            return "Only a child's own chore can be inspected."
        if self.get_child(completion.child_id) is None:
            return "That child no longer exists."
        now = now or dt_util.now()
        approved = completion.approved_at or completion.completed_at
        if approved is None or now - approved > timedelta(hours=INSPECTABLE_HOURS):
            return f"Only chores approved in the last {INSPECTABLE_HOURS} hours can be inspected."
        if any(r.get("completion_id") == completion.id for r in self.storage.get_inspections()):
            return "That chore has already been inspected."
        return ""

    def inspectable_completion_ids(self) -> list[str]:
        """Approved completions a parent may inspect now (the panel's magnifier)."""
        if not self.inspections_enabled():
            return []
        now = dt_util.now()
        cutoff = now - timedelta(hours=INSPECTABLE_HOURS)
        return [
            c.id
            for c in self.storage.get_completions()
            if c.approved and (c.approved_at or c.completed_at) >= cutoff and not self.inspectable_error(c, now)
        ]

    def inspection_can_redo(self, record: dict) -> bool:
        """Whether a fail may send this chore back: a plain chore, done today."""
        completion = self._inspected_completion(record.get("completion_id", ""))
        if completion is None or getattr(completion, "bounty_id", ""):
            return False
        chore = self.get_chore(completion.chore_id)
        if chore is None or getattr(chore, "task_type", "") == "timed" or self.teamwork_size(chore):
            return False
        return _local_date(completion.completed_at) == dt_util.as_local(dt_util.now()).date().isoformat()

    # ── parent actions ───────────────────────────────────────────────────

    async def async_start_inspection(
        self,
        completion_id: str,
        *,
        bonus: int | None = None,
        window: str | None = None,
        tell_child: bool | None = None,
        source: str = "parent",
    ) -> dict:
        """Flag an approved chore for a spot check."""
        if not self.inspections_enabled():
            raise ValueError("Surprise inspections are switched off in Settings.")
        completion = self._inspected_completion(completion_id)
        now = dt_util.now()
        error = self.inspectable_error(completion, now)
        if error:
            raise ValueError(error)
        window = window if window in INSPECTION_WINDOWS else self.inspection_default_window()
        bonus = self.inspection_default_bonus() if bonus is None else max(0, min(INSPECTION_BONUS_MAX, int(bonus)))
        tell = self._insp_flag("inspection_tell_child", True) if tell_child is None else bool(tell_child)
        record = {
            "id": generate_id(),
            "completion_id": completion.id,
            "child_id": completion.child_id,
            "chore_id": completion.chore_id,
            "chore_name": self._inspection_item_name(completion),
            "completed_on": _local_date(completion.completed_at),
            "points": int(completion.points_awarded or 0),
            "status": "open",
            "bonus": bonus,
            "tell_child": tell,
            "source": "random" if source == "random" else "parent",
            "started_at": format_datetime(now),
            "until": format_datetime(self.inspection_until(window, now)),
            "reminded": False,
            "decided_at": None,
            "note": "",
            "bonus_txn_id": "",
            "redo_completion_id": "",
        }
        self._prune_inspections(now)
        self._save_inspection(record)
        await self.storage.async_save()
        self._arm_inspection_timer()
        self._fire_inspection_event("taskmate_inspection_started", record)
        await self.async_refresh()
        child = self.get_child(record["child_id"])
        if tell and child is not None:
            await self.notifications.fire(
                NOTIF_TYPE_INSPECTION_STARTED,
                {
                    **self._inspection_notify_context(record, child),
                    "until": dt_util.as_local(_at(record["until"])).strftime("%H:%M"),
                },
                only_recipients={f"child:{child.id}"},
            )
        return record

    async def async_pass_inspection(self, inspection_id: str, *, bonus: int | None = None, note: str = "") -> dict:
        """It passed: pay the bonus (a normal transaction) and celebrate."""
        record = self._require_open_inspection(inspection_id)
        if bonus is not None:
            record["bonus"] = max(0, min(INSPECTION_BONUS_MAX, int(bonus)))
        record["status"] = "passed"
        record["decided_at"] = format_datetime(dt_util.now())
        record["note"] = clean_label(note, INSPECTION_NOTE_MAX)
        # Claim the decision before paying: the award awaits, and a second
        # pass landing meanwhile must find the inspection already decided.
        self._save_inspection(record)
        await self.storage.async_save()
        child = self.get_child(record["child_id"])
        if child is not None and record["bonus"] > 0:
            reason = f"{PASS_REASON_PREFIX} {record['chore_name']}".strip()
            await self.async_add_points(child.id, record["bonus"], reason=reason)
            txn = next(
                (
                    t
                    for t in reversed(self.storage.get_points_transactions())
                    if t.child_id == child.id and t.reason == reason and t.points == record["bonus"]
                ),
                None,
            )
            if txn is not None:
                record["bonus_txn_id"] = txn.id
                self._save_inspection(record)
                await self.storage.async_save()
        self._arm_inspection_timer()
        self._fire_inspection_event("taskmate_inspection_passed", record)
        await self.async_refresh()
        if child is not None:
            await self.notifications.fire(
                NOTIF_TYPE_INSPECTION_PASSED,
                {
                    **self._inspection_notify_context(record, child),
                    "note": record["note"],
                    "note_text": f": {record['note']}" if record["note"] else "",
                },
                only_recipients={f"child:{child.id}"},
            )
            await self._celebrate(
                child,
                "inspection_passed",
                f"{child.name}'s {record['chore_name']} passed inspection!",
                tier=1,
                extra={"inspection_id": record["id"], "bonus": record["bonus"]},
            )
        return record

    async def async_fail_inspection(self, inspection_id: str, *, redo: bool | None = None, note: str = "") -> dict:
        """It didn't pass. No points are taken either way.

        ``redo`` sends the chore back: the inspected completion stops counting
        as today's done (``inspection_redo_completion_ids``), a recurring
        chore's window and a one-shot's "done" flag are reopened for the child,
        and the next completion of it pays nothing (``_inspection_redo_for``).
        ``None`` follows the "If it fails" setting ("ask" means just note it).
        """
        record = self._require_open_inspection(inspection_id)
        if redo is None:
            redo = self.inspection_fail_default() == "redo"
        if redo and not self.inspection_can_redo(record):
            raise ValueError("Only a chore finished today can be sent back to redo.")
        record["status"] = "redo" if redo else "failed"
        record["decided_at"] = format_datetime(dt_util.now())
        record["note"] = clean_label(note, INSPECTION_NOTE_MAX)
        if redo:
            self._reopen_inspected_chore(record)
        self._save_inspection(record)
        await self.storage.async_save()
        self._arm_inspection_timer()
        self._fire_inspection_event("taskmate_inspection_failed", record, redo=redo)
        await self.async_refresh()
        return record

    async def async_cancel_inspection(self, inspection_id: str) -> None:
        """Call it off: as if it never started (the chore can be flagged again)."""
        record = self._require_open_inspection(inspection_id)
        self.storage.set_inspections([r for r in self.storage.get_inspections() if r.get("id") != record["id"]])
        await self.storage.async_save()
        self._arm_inspection_timer()
        self._fire_inspection_event("taskmate_inspection_cancelled", record)
        await self.async_refresh()

    def _reopen_inspected_chore(self, record: dict) -> None:
        """Let the child do the chore again today (the "send back" half of a fail)."""
        chore = self.get_chore(record["chore_id"])
        if chore is None:
            return
        mode = getattr(chore, "schedule_mode", "specific_days")
        if mode == "recurring":
            self.storage.undo_last_completed(chore.id, record["child_id"])
        elif mode == "one_shot" and record["child_id"] in chore.disabled_for:
            chore.disabled_for.remove(record["child_id"])
            chore.enabled = True
            self.storage.update_chore(chore)

    # ── hooks from the chore paths ───────────────────────────────────────

    def _inspection_redo_records(self) -> list[dict]:
        """Sent-back inspections still waiting for their redo today."""
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        return [
            r
            for r in self.storage.get_inspections()
            if r.get("status") == "redo" and not r.get("redo_completion_id") and r.get("completed_on") == today
        ]

    def inspection_redo_completion_ids(self) -> set[str]:
        """Completions sent back to redo: they no longer count as today's done."""
        return {r["completion_id"] for r in self._inspection_redo_records() if r.get("completion_id")}

    def _inspection_redo_for(self, chore_id: str, child_id: str) -> dict | None:
        return next(
            (
                r
                for r in self._inspection_redo_records()
                if r.get("chore_id") == chore_id and r.get("child_id") == child_id
            ),
            None,
        )

    def _inspection_on_redo_recorded(self, record: dict, completion_id: str) -> None:
        """The redo is in: link it, so the original counts as done again."""
        record["redo_completion_id"] = completion_id
        self._save_inspection(record)

    def _inspection_on_completion_removed(self, completion_id: str) -> None:
        """A completion was rejected or undone.

        The inspected completion itself: an open inspection of it is void
        (there's nothing left to inspect). A redo: the chore is owed again.
        """
        rows = self.storage.get_inspections()
        if not rows:
            return
        changed = False
        kept = []
        for r in rows:
            if r.get("completion_id") == completion_id and r.get("status") == "open":
                changed = True
                continue
            if r.get("redo_completion_id") == completion_id:
                r["redo_completion_id"] = ""
                changed = True
            kept.append(r)
        if changed:
            self.storage.set_inspections(kept)

    # ── housekeeping ─────────────────────────────────────────────────────

    def _prune_inspections(self, now: datetime) -> None:
        cutoff = now - timedelta(days=INSPECTION_KEEP_DAYS)
        rows = [
            r
            for r in self.storage.get_inspections()
            if r.get("status") == "open" or (_at(r.get("decided_at") or r.get("started_at")) or now) >= cutoff
        ]
        self.storage.set_inspections(rows[-INSPECTION_KEEP_MAX:])

    async def async_sweep_inspections(self, refresh: bool = True) -> bool:
        """Close inspections whose window ran out; remind parents of ones about to.

        Runs from the inspection timer and at startup. Returns whether
        anything changed.
        """
        rows = self.storage.get_inspections()
        now = dt_util.now()
        closed: list[dict] = []
        reminders: list[dict] = []
        changed = False
        for r in rows:
            if r.get("status") != "open":
                continue
            until = _at(r.get("until"))
            if until is None or until <= now:
                r["status"] = "expired"
                r["decided_at"] = format_datetime(until or now)
                closed.append(r)
                changed = True
            elif not r.get("reminded") and until - now <= timedelta(minutes=INSPECTION_REMINDER_MINUTES):
                r["reminded"] = True
                changed = True
                started = _at(r.get("started_at"))
                # A window no longer than the reminder lead would remind the
                # parent the moment it opened, which tells them nothing.
                if started is None or until - started > timedelta(minutes=INSPECTION_REMINDER_MINUTES):
                    reminders.append(r)
        if changed:
            self.storage.set_inspections(rows)
            await self.storage.async_save()
        self._arm_inspection_timer()
        for r in closed:
            self._fire_inspection_event("taskmate_inspection_expired", r)
        for r in reminders:
            child = self.get_child(r["child_id"])
            if child is None:
                continue
            until = _at(r["until"])
            await self.notifications.fire(
                NOTIF_TYPE_INSPECTION_REMINDER,
                {
                    **self._inspection_notify_context(r, child),
                    "minutes": max(1, round((until - now).total_seconds() / 60)),
                    "until": dt_util.as_local(until).strftime("%H:%M"),
                },
            )
        if changed and refresh:
            await self.async_refresh()
        return changed

    def _arm_inspection_timer(self) -> None:
        """One timer, at the next reminder or window end of any open inspection."""
        unsub = getattr(self, "_insp_timer_unsub", None)
        if unsub:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("inspection timer unsub failed", exc_info=True)
        self._insp_timer_unsub = None
        hass = getattr(self, "hass", None)
        if hass is None:
            return
        due: list[datetime] = []
        for r in self.storage.get_inspections():
            if r.get("status") != "open":
                continue
            until = _at(r.get("until"))
            if until is None:
                continue
            due.append(until)
            if not r.get("reminded"):
                due.append(until - timedelta(minutes=INSPECTION_REMINDER_MINUTES))
        if not due:
            return
        when = max(min(due), dt_util.now() + timedelta(seconds=1))
        self._insp_timer_unsub = async_track_point_in_time(hass, self._inspection_timer_fired, when)

    @callback
    def _inspection_timer_fired(self, _now: datetime) -> None:
        self._insp_timer_unsub = None
        self.hass.async_create_task(self._async_inspection_guarded(self.async_sweep_inspections))

    async def _async_inspection_guarded(self, step) -> None:
        try:
            await step()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Inspection step %s failed", getattr(step, "__name__", step))

    # ── random daily pick ────────────────────────────────────────────────

    def inspection_pick_time(self) -> tuple[int, int]:
        value = str(self.storage.get_setting("inspection_pick_time", DEFAULT_INSPECTION_PICK_TIME) or "")
        return parse_hhmm(value) or parse_hhmm(DEFAULT_INSPECTION_PICK_TIME)

    async def async_run_inspection_pick(self) -> dict | None:
        """Once a day: with the configured chance, flag one chore approved today.

        Never the child picked the day before. Rolls at most once per day, so
        the startup catch-up can't roll a second time.
        """
        if not (self.inspections_enabled() and self._insp_flag("inspection_pick_enabled", False)):
            return None
        now = dt_util.now()
        today = dt_util.as_local(now).date()
        if self.storage.get_inspection_meta("last_pick") == today.isoformat():
            return None
        self.storage.set_inspection_meta("last_pick", today.isoformat())
        await self.storage.async_save()
        chance = self._insp_int("inspection_pick_chance", DEFAULT_INSPECTION_PICK_CHANCE, 0, 100)
        if random.random() * 100.0 >= chance:
            return None
        allowed = self.storage.get_setting("inspection_pick_children", []) or []
        allowed = set(allowed) if isinstance(allowed, list) else set()
        yesterday_child = ""
        if self.storage.get_inspection_meta("last_pick_child_on") == (today - timedelta(days=1)).isoformat():
            yesterday_child = self.storage.get_inspection_meta("last_pick_child")
        candidates = [
            c
            for c in self.storage.get_completions()
            if c.approved
            and _local_date(c.approved_at or c.completed_at) == today.isoformat()
            and (not allowed or c.child_id in allowed)
            and c.child_id != yesterday_child
            and not self.inspectable_error(c, now)
        ]
        if not candidates:
            return None
        pick = random.choice(candidates)
        record = await self.async_start_inspection(pick.id, source="random")
        self.storage.set_inspection_meta("last_pick_child", pick.child_id)
        self.storage.set_inspection_meta("last_pick_child_on", today.isoformat())
        await self.storage.async_save()
        return record

    @callback
    def _inspection_pick_due(self, _now: datetime) -> None:
        self.hass.async_create_task(self._async_inspection_guarded(self.async_run_inspection_pick))

    def arm_inspection_schedules(self) -> None:
        """The daily pick at its configured time, plus the next-event timer."""
        self.disarm_inspection_schedules()
        hour, minute = self.inspection_pick_time()
        self._insp_pick_unsub = async_track_time_change(
            self.hass, self._inspection_pick_due, hour=hour, minute=minute, second=0
        )
        self._arm_inspection_timer()

    def disarm_inspection_schedules(self) -> None:
        for attr in ("_insp_pick_unsub", "_insp_timer_unsub"):
            unsub = getattr(self, attr, None)
            if unsub:
                try:
                    unsub()
                except Exception:  # noqa: BLE001
                    _LOGGER.debug("inspection schedule unsub failed", exc_info=True)
            setattr(self, attr, None)

    async def async_start_inspections(self) -> None:
        """Startup: close/remind whatever came due while HA was off, catch up
        on a missed daily pick, then arm the timers."""
        await self._async_inspection_guarded(lambda: self.async_sweep_inspections(refresh=False))
        now = dt_util.as_local(dt_util.now())
        if (now.hour, now.minute) >= self.inspection_pick_time():
            await self._async_inspection_guarded(self.async_run_inspection_pick)
        self.arm_inspection_schedules()

    async def async_inspection_settings_changed(self) -> None:
        """A parent saved inspection settings: move the daily pick."""
        self.arm_inspection_schedules()

    # ── views ────────────────────────────────────────────────────────────

    def inspections_for_child(self, child_id: str) -> list[dict]:
        """What the child's card shows today, newest first (compact).

        An open inspection only when the child was told; a decision made
        today; a redo only until it's been done again. An inspection that
        closed undecided shows nothing.
        """
        rows = [r for r in self.storage.get_inspections() if r.get("child_id") == child_id]
        if not rows:
            return []
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        out: list[dict] = []
        for r in reversed(rows):
            status = r.get("status")
            item = {"id": r.get("id"), "chore_id": r.get("chore_id"), "status": status}
            if status == "open":
                if not r.get("tell_child"):
                    continue
                item.update({"bonus": r.get("bonus", 0), "until": r.get("until")})
            elif status in ("passed", "failed", "redo") and _local_date(r.get("decided_at")) == today:
                if status == "passed":
                    item["bonus"] = r.get("bonus", 0)
                if status == "redo":
                    if r.get("redo_completion_id") or r.get("completed_on") != today:
                        continue
                    item["points"] = r.get("points", 0)
                if r.get("note"):
                    item["note"] = r["note"]
            else:
                continue
            item["name"] = r.get("chore_name", "")
            out.append(item)
            if len(out) >= INSPECTION_CARD_MAX:
                break
        return out

    def inspections_state(self) -> list[dict]:
        """Every kept inspection for the admin panel, with whether it can be sent back."""
        return [
            {**r, "can_redo": self.inspection_can_redo(r)} if r.get("status") == "open" else r
            for r in self.storage.get_inspections()
        ]

    def recent_inspection_events(self) -> list[dict]:
        """Inspection entries for the activity feed, oldest first.

        A pass with a bonus is already in the feed as its points transaction
        ("Inspection passed: …"), so only a no-bonus pass is listed here. A
        secret inspection appears once it's decided, not before.
        """
        events: list[dict] = []
        for r in self.storage.get_inspections():
            status = r.get("status")
            if r.get("tell_child") or status != "open":
                events.append(self._inspection_event(r, "inspection_started", r.get("started_at")))
            if status == "passed" and not r.get("bonus_txn_id"):
                events.append(self._inspection_event(r, "inspection_passed", r.get("decided_at")))
            elif status in ("failed", "redo"):
                events.append(self._inspection_event(r, f"inspection_{status}", r.get("decided_at")))
        return events

    @staticmethod
    def _inspection_event(r: dict, kind: str, at) -> dict:
        event = {
            "id": f"{r.get('id')}_{kind}",
            "type": kind,
            "child_id": r.get("child_id", ""),
            "chore_id": r.get("chore_id", ""),
            "chore_name": r.get("chore_name", ""),
            "created_at": str(at or ""),
        }
        if kind == "inspection_passed":
            event["points"] = r.get("bonus", 0)
        if kind in ("inspection_failed", "inspection_redo") and r.get("note"):
            event["note"] = r["note"]
        return event

    def _inspection_notify_context(self, record: dict, child) -> dict:
        return {
            "child_name": child.name,
            "child_id": child.id,
            "chore_name": record.get("chore_name", ""),
            "bonus": record.get("bonus", 0),
            "points_name": self.storage.get_points_name(),
        }

    def _fire_inspection_event(self, event: str, record: dict, **extra) -> None:
        child = self.get_child(record.get("child_id", ""))
        self.hass.bus.async_fire(
            event,
            {
                "inspection_id": record.get("id"),
                "completion_id": record.get("completion_id"),
                "child_id": record.get("child_id"),
                "child_name": getattr(child, "name", ""),
                "chore_id": record.get("chore_id"),
                "chore_name": record.get("chore_name"),
                "bonus": record.get("bonus", 0),
                "status": record.get("status"),
                "timestamp": dt_util.now().isoformat(),
                **extra,
            },
        )
