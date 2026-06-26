"""Mandatory-chore detection, scheduling, and resolution (#532)."""
from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta
import logging

from homeassistant.core import callback
from homeassistant.helpers.event import (
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    NOTIF_TYPE_MANDATORY_PARENT_ALERT,
    NOTIF_TYPE_MANDATORY_REMINDER,
)
from .models import MandatoryMiss, parse_datetime

# How often the escalation ladder is re-evaluated (FEAT-6).
_ESCALATION_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)

# Assignment modes where every assigned child owes the chore. Rotation modes
# point to a single current child via assignment_current_child_id.
_SHARED_MODES = {"everyone", "first_come", "unassigned"}


class MandatoryMixin:
    """Detection + scheduling + resolution for mandatory chores."""

    def _ensure_mandatory_state(self) -> None:
        if not hasattr(self, "mandatory_postpone"):
            self.mandatory_postpone = {}

    def _effective_period_for(self, chore, child_id: str, day: date) -> str:
        """The chore's period for this child/day, honoring any postpone override."""
        self._ensure_mandatory_state()
        key = f"{chore.id}:{child_id}:{day.isoformat()}"
        return self.mandatory_postpone.get(key) or (chore.time_category or "anytime")

    def _mandatory_owers(self, chore) -> list[str]:
        """Child IDs responsible for this chore right now."""
        mode = getattr(chore, "assignment_mode", "everyone")
        assigned = list(getattr(chore, "assigned_to", []) or [])
        if mode in _SHARED_MODES:
            if assigned:
                return assigned
            return [c.id for c in self.storage.get_children()]
        cur = getattr(chore, "assignment_current_child_id", "") or ""
        return [cur] if cur else []

    def _child_completed_today(self, chore_id: str, child_id: str, day: date) -> bool:
        for comp in self.storage.get_completions():
            if comp.chore_id != chore_id or comp.child_id != child_id:
                continue
            if comp.bonus_subtask_id:
                continue
            if dt_util.as_local(comp.completed_at).date() == day:
                return True
        return False

    async def async_detect_mandatory_misses(self, period_id: str, day: date) -> int:
        """Create misses for due+incomplete mandatory chores in `period_id`."""
        existing = {
            (m.chore_id, m.child_id, m.due_date)
            for m in self.storage.get_mandatory_misses()
        }
        created = 0
        for chore in self.storage.get_chores():
            if not getattr(chore, "mandatory", False):
                continue
            if not getattr(chore, "enabled", True):
                continue
            if not self._is_chore_scheduled_for_date(chore, day):
                continue
            for child_id in self._mandatory_owers(chore):
                if self._effective_period_for(chore, child_id, day) != period_id:
                    continue
                if child_id in (getattr(chore, "disabled_for", []) or []):
                    continue
                if self._child_completed_today(chore.id, child_id, day):
                    continue
                if (chore.id, child_id, day.isoformat()) in existing:
                    continue
                miss = MandatoryMiss(
                    chore_id=chore.id,
                    child_id=child_id,
                    due_date=day.isoformat(),
                    period_id=period_id,
                    penalty_points=int(getattr(chore, "mandatory_penalty_points", 0) or 0),
                )
                self.storage.add_mandatory_miss(miss)
                created += 1
                self.hass.bus.async_fire("taskmate_mandatory_missed", {
                    "miss_id": miss.id, "chore_id": chore.id, "child_id": child_id,
                    "period_id": period_id, "penalty_points": miss.penalty_points,
                    "timestamp": dt_util.now().isoformat(),
                })
        if created:
            await self.storage.async_save()
            await self.async_refresh()
        return created

    # ---- resolution actions ------------------------------------------------

    def _get_miss(self, miss_id: str) -> MandatoryMiss | None:
        for m in self.storage.get_mandatory_misses():
            if m.id == miss_id:
                return m
        return None

    def _next_period_after(self, period_id: str, now: datetime) -> str | None:
        """Next period whose end is still in the future today, by start order."""
        cur_now = now.time()
        for p in self.get_time_periods():
            try:
                eh, em = [int(x) for x in p["end"].split(":")]
            except (ValueError, KeyError):
                continue
            if dt_time(eh, em) > cur_now and p["id"] != period_id:
                return p["id"]
        return None

    async def async_apply_mandatory_penalty(self, miss_id: str) -> None:
        miss = self._get_miss(miss_id)
        if miss is None:
            return
        chore = next((c for c in self.storage.get_chores() if c.id == miss.chore_id), None)
        name = getattr(chore, "name", "chore")
        if miss.penalty_points > 0:
            await self.async_remove_points(
                miss.child_id, miss.penalty_points,
                reason=f"Penalty: {name} (missed mandatory)",
            )
        self.storage.remove_mandatory_miss(miss_id)
        await self.storage.async_save()
        self.hass.bus.async_fire("taskmate_mandatory_penalty_applied", {
            "miss_id": miss_id, "chore_id": miss.chore_id, "child_id": miss.child_id,
            "points": miss.penalty_points, "timestamp": dt_util.now().isoformat(),
        })
        await self.async_refresh()

    async def async_postpone_mandatory_chore(self, miss_id: str) -> None:
        miss = self._get_miss(miss_id)
        if miss is None:
            return
        self._ensure_mandatory_state()
        now = dt_util.now()
        nxt = self._next_period_after(miss.period_id, now)
        if nxt:
            key = f"{miss.chore_id}:{miss.child_id}:{miss.due_date}"
            self.mandatory_postpone[key] = nxt
        # else: no window left today -> let normal scheduling resurface tomorrow
        self.storage.remove_mandatory_miss(miss_id)
        await self.storage.async_save()
        self.hass.bus.async_fire("taskmate_mandatory_postponed", {
            "miss_id": miss_id, "chore_id": miss.chore_id, "child_id": miss.child_id,
            "next_period": nxt or "", "timestamp": dt_util.now().isoformat(),
        })
        await self.async_refresh()

    async def async_dismiss_mandatory_chore(self, miss_id: str) -> None:
        miss = self._get_miss(miss_id)
        if miss is None:
            return
        self.storage.remove_mandatory_miss(miss_id)
        await self.storage.async_save()
        self.hass.bus.async_fire("taskmate_mandatory_dismissed", {
            "miss_id": miss_id, "chore_id": miss.chore_id, "child_id": miss.child_id,
            "timestamp": dt_util.now().isoformat(),
        })
        await self.async_refresh()

    # ---- escalation (FEAT-6) ----------------------------------------------

    async def async_escalate_mandatory_misses(self, now: datetime | None = None) -> int:
        """Walk today's open mandatory misses and advance each escalation stage.

        Ladder driven by minutes elapsed since the miss was created:
          stage 1 (nudge)        immediately -> mandatory_reminder (child)
          stage 2 (reminder)     after reminder_minutes -> mandatory_reminder
          stage 3 (parent alert) after parent_minutes  -> mandatory_parent_alert

        A miss whose chore has since been completed by that child is skipped (it
        will be resolved by the parent / next-day prune). Each notification is
        still gated by its own master switch + routes inside ``fire()``; stages
        advance regardless so a disabled type is not retro-fired when re-enabled.
        Returns the number of misses whose stage advanced.
        """
        now = now or dt_util.now()
        today_iso = now.date().isoformat()
        reminder_minutes = self.storage.get_escalation_reminder_minutes()
        parent_minutes = self.storage.get_escalation_parent_minutes()
        chores = {c.id: c for c in self.storage.get_chores()}
        children = {c.id: c for c in self.storage.get_children()}
        advanced = 0

        for miss in self.storage.get_mandatory_misses():
            if miss.due_date != today_iso:
                continue  # only escalate same-day misses (skips midnight backfill)
            if self._child_completed_today(miss.chore_id, miss.child_id, now.date()):
                continue
            created = parse_datetime(miss.created_at)
            if created is None:
                continue
            elapsed_min = (now - created).total_seconds() / 60.0
            target = 1
            if elapsed_min >= reminder_minutes:
                target = 2
            if elapsed_min >= parent_minutes:
                target = 3
            if target <= miss.escalation_stage:
                continue

            chore = chores.get(miss.chore_id)
            child = children.get(miss.child_id)
            ctx = {
                "child_id": miss.child_id,
                "child_name": getattr(child, "name", ""),
                "chore_name": getattr(chore, "name", "chore"),
            }
            for stage in range(miss.escalation_stage + 1, target + 1):
                if stage in (1, 2):
                    await self.notifications.fire(
                        NOTIF_TYPE_MANDATORY_REMINDER, ctx,
                        only_recipients={f"child:{miss.child_id}"},
                    )
                elif stage == 3:
                    await self.notifications.fire(
                        NOTIF_TYPE_MANDATORY_PARENT_ALERT, ctx,
                    )
            miss.escalation_stage = target
            self.storage.update_mandatory_miss(miss)
            advanced += 1

        if advanced:
            await self.storage.async_save()
        return advanced

    # ---- scheduling --------------------------------------------------------

    def _mandatory_period_end_times(self) -> list[tuple[int, int, str]]:
        """Distinct (hour, minute, period_id) from each period's end time."""
        out: list[tuple[int, int, str]] = []
        for p in self.get_time_periods():
            try:
                h, m = [int(x) for x in p["end"].split(":")]
            except (ValueError, KeyError):
                continue
            out.append((h, m, p["id"]))
        return out

    def arm_mandatory_schedules(self) -> None:
        """Register a callback at each period's end time + the escalation tick."""
        self._ensure_mandatory_state()
        self._unsub_mandatory = getattr(self, "_unsub_mandatory", [])
        for hour, minute, period_id in self._mandatory_period_end_times():
            unsub = async_track_time_change(
                self.hass,
                self._make_mandatory_period_cb(period_id),
                hour=hour, minute=minute, second=10,
            )
            self._unsub_mandatory.append(unsub)
        # Reminder escalation ladder (FEAT-6) — re-evaluate open misses on a tick.
        self._unsub_mandatory.append(
            async_track_time_interval(
                self.hass, self._escalation_tick, _ESCALATION_INTERVAL,
            )
        )

    @callback
    def _escalation_tick(self, now: datetime) -> None:
        self.hass.async_create_task(self.async_escalate_mandatory_misses(now))

    def _make_mandatory_period_cb(self, period_id: str):
        @callback
        def _cb(now: datetime) -> None:
            self.hass.async_create_task(
                self.async_detect_mandatory_misses(period_id, dt_util.now().date())
            )
        return _cb

    def disarm_mandatory_schedules(self) -> None:
        for unsub in getattr(self, "_unsub_mandatory", []):
            unsub()
        self._unsub_mandatory = []

    async def async_rearm_mandatory_schedules(self) -> None:
        """Re-arm after the time_periods setting changes."""
        self.disarm_mandatory_schedules()
        self.arm_mandatory_schedules()

    async def async_catchup_mandatory_misses(self) -> None:
        """On startup, detect misses for any period that already ended today.

        The period-end callbacks only fire going forward, so a restart after a
        boundary would otherwise miss that period for the rest of the day. The
        detector's existing-item guard keeps this idempotent.
        """
        now = dt_util.now()
        today = now.date()
        cur = now.time()
        for hour, minute, period_id in self._mandatory_period_end_times():
            if dt_time(hour, minute) <= cur:
                await self.async_detect_mandatory_misses(period_id, today)

    async def async_detect_anytime_mandatory_misses(self) -> None:
        """Midnight: raise misses for incomplete mandatory 'anytime' chores for the
        day that just ended, then prune the postpone override map (new day starts clean)."""
        self._ensure_mandatory_state()
        yesterday = (dt_util.now() - timedelta(days=1)).date()
        await self.async_detect_mandatory_misses("anytime", yesterday)
        self.mandatory_postpone = {}

    # ---- maintenance -------------------------------------------------------

    async def async_prune_orphan_misses(self) -> int:
        """Drop misses whose chore is gone, disabled, or no longer mandatory."""
        chores = {c.id: c for c in self.storage.get_chores()}
        removed = 0
        for m in self.storage.get_mandatory_misses():
            chore = chores.get(m.chore_id)
            if chore is None or not getattr(chore, "mandatory", False) or not getattr(chore, "enabled", True):
                self.storage.remove_mandatory_miss(m.id)
                removed += 1
        if removed:
            await self.storage.async_save()
            await self.async_refresh()
        return removed

    def mandatory_misses_state(self) -> list[dict]:
        """Misses enriched with chore/child display names for the UI."""
        chores = {c.id: c for c in self.storage.get_chores()}
        children = {c.id: c for c in self.storage.get_children()}
        out = []
        for m in self.storage.get_mandatory_misses():
            d = m.to_dict()
            d["chore_name"] = getattr(chores.get(m.chore_id), "name", "")
            d["child_name"] = getattr(children.get(m.child_id), "name", "")
            out.append(d)
        return out
