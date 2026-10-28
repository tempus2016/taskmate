"""Set times: a chore that comes up at set times of day ("several times a day").

A chore with ``times`` is ticked off once per time instead of up to
``daily_limit`` times whenever. Each time is open from its start to its end
(plus the chore's claim allowance), can be missed, and earns its own points.
For the day as a whole (streaks, the weekly target, "all done today") the
chore counts once, and only when every time is done.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from homeassistant.util import dt as dt_util

from .models import MandatoryMiss, PointsTransaction, _hhmm_minutes

_LOGGER = logging.getLogger(__name__)

# Storage key: {"<chore_id>:<child_id>:<ISO day>": bonus paid}.
_BONUS_KEY = "set_times_bonus_paid"
_BONUS_KEEP_DAYS = 14

# The period_id a set-time mandatory miss is filed under.
SET_TIME_PERIOD = "set_time"

# Assignment modes where every assigned child owes the chore (same as
# coord_mandatory's).
_SHARED_MODES = {"everyone", "first_come", "unassigned"}


def chore_has_times(chore) -> bool:
    times = getattr(chore, "times", None)
    return isinstance(times, list) and bool(times)


def set_time_label(chore, time_id: str) -> str:
    """ "Wash hands (Lunch)" for a set-time completion; the bare name otherwise."""
    name = getattr(chore, "name", "") or ""
    times = getattr(chore, "times", None)
    if not time_id or not isinstance(times, list):
        return name
    t = next((t for t in times if t.id == time_id), None)
    if t is None:
        return name
    return f"{name} ({t.name or t.start})"


def set_time_of(chore, time_id: str):
    """The chore's ChoreTime with ``time_id``, or None."""
    times = getattr(chore, "times", None)
    if not time_id or not isinstance(times, list):
        return None
    return next((t for t in times if t.id == time_id), None)


class SetTimesMixin:
    """Per-time windows, completion bookkeeping, bonus and misses."""

    # ── windows ──────────────────────────────────────────────────────────

    def set_time_window(self, chore, t, day: date) -> tuple[datetime, datetime]:
        """Local (opens, closes) for set time ``t`` on ``day``.

        ``closes`` includes the chore's claim allowance, capped at midnight
        like night chores.
        """
        tz = dt_util.get_default_time_zone() if hasattr(dt_util, "get_default_time_zone") else dt_util.DEFAULT_TIME_ZONE
        midnight = datetime(day.year, day.month, day.day, tzinfo=tz)
        start = _hhmm_minutes(t.start) or 0
        end = _hhmm_minutes(t.end) or 0
        grace = max(0, int(getattr(chore, "claim_allowance_minutes", 0) or 0))
        close = min(end + grace, 24 * 60)
        return midnight + timedelta(minutes=start), midnight + timedelta(minutes=close)

    def set_time_is_open(self, chore, t, now: datetime) -> bool:
        local = dt_util.as_local(now)
        opens, closes = self.set_time_window(chore, t, local.date())
        return opens <= local < closes

    def set_time_has_closed(self, chore, t, now: datetime) -> bool:
        local = dt_util.as_local(now)
        _opens, closes = self.set_time_window(chore, t, local.date())
        return local >= closes

    # ── what has been done ───────────────────────────────────────────────

    def set_time_completions(self, chore, child_id: str, day: date, *, approved_only: bool = False) -> dict:
        """{time_id: completion} for ``child_id``'s set-time ticks of ``chore`` on ``day``.

        A parent completion for the whole pool (or for this child) counts the
        same way it does for the daily limit. Completions an inspection sent
        back to redo don't count.
        """
        redo = self.inspection_redo_completion_ids() if hasattr(self, "inspection_redo_completion_ids") else set()
        out: dict = {}
        for comp in self.storage.get_completions():
            if comp.chore_id != chore.id or comp.id in redo:
                continue
            time_id = getattr(comp, "time_id", "")
            # A parent's "done for today" (no time) covers every time.
            if not time_id and comp.child_id != "__parent__":
                continue
            if getattr(comp, "bonus_subtask_id", ""):
                continue
            if not self._counts_toward_child_quota(chore, comp.child_id, child_id, getattr(comp, "for_child_id", "")):
                continue
            if approved_only and not comp.approved:
                continue
            try:
                if dt_util.as_local(comp.completed_at).date() != day:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if time_id:
                out.setdefault(time_id, comp)
            else:
                for t in chore.times:
                    out.setdefault(t.id, comp)
        return out

    def set_times_full_day(
        self, chore, child_id: str, day: date, *, approved_only: bool = False, exclude_id: str = ""
    ) -> bool:
        """True when every one of the chore's set times is done on ``day``."""
        ids = {t.id for t in chore.times}
        if not ids:
            return False
        done = self.set_time_completions(chore, child_id, day, approved_only=approved_only)
        done = {tid for tid, comp in done.items() if comp.id != exclude_id}
        return ids <= done

    def set_times_full_days(
        self, chore, child_id: str, days, *, approved_only: bool = False, exclude_id: str = ""
    ) -> int:
        """How many of ``days`` had every set time done (the weekly target counts these)."""
        return sum(
            1
            for d in days
            if self.set_times_full_day(chore, child_id, d, approved_only=approved_only, exclude_id=exclude_id)
        )

    def set_time_states(self, chore, child_id: str, now: datetime | None = None) -> dict[str, str]:
        """{time_id: state} for today: done / pending / now / later / missed."""
        now = now or dt_util.now()
        today = dt_util.as_local(now).date()
        done = self.set_time_completions(chore, child_id, today)
        out: dict[str, str] = {}
        for t in chore.times:
            comp = done.get(t.id)
            if comp is not None:
                out[t.id] = "done" if comp.approved else "pending"
            elif self.set_time_is_open(chore, t, now):
                out[t.id] = "now"
            elif self.set_time_has_closed(chore, t, now):
                out[t.id] = "missed"
            else:
                out[t.id] = "later"
        return out

    def set_times_outstanding(self, chore, child_id: str, now: datetime | None = None) -> bool:
        """Whether anything is still owed today: a time not done that hasn't closed."""
        return any(s in ("now", "later") for s in self.set_time_states(chore, child_id, now).values())

    def resolve_set_time(self, chore, child_id: str, time_id: str, now: datetime, *, as_parent: bool):
        """The set time a completion right now would tick off, or None.

        ``time_id`` names one; otherwise it's the time open now. A child can
        only tick a time while it's open. A parent may tick any time that
        isn't done yet, so with nothing open they get the latest one that has
        started, or failing that the first. A time already done today gives None.
        Raises ValueError for a ``time_id`` the chore doesn't have.
        """
        today = dt_util.as_local(now).date()
        done = self.set_time_completions(chore, child_id, today)
        if time_id:
            t = next((t for t in chore.times if t.id == time_id), None)
            if t is None:
                raise ValueError("That time isn't one of this chore's set times.")
            if t.id in done:
                return None
            if not as_parent and not self.set_time_is_open(chore, t, now):
                return None
            return t
        todo = [t for t in chore.times if t.id not in done]
        open_now = [t for t in todo if self.set_time_is_open(chore, t, now)]
        if open_now:
            return open_now[0]
        if not as_parent or not todo:
            return None
        local = dt_util.as_local(now)
        started = [t for t in todo if self.set_time_window(chore, t, today)[0] <= local]
        return started[-1] if started else todo[0]

    # ── the all-times bonus ──────────────────────────────────────────────

    def _set_times_bonus_store(self) -> dict:
        return self.storage._data.setdefault(_BONUS_KEY, {})

    async def _async_pay_set_times_bonus(self, chore, child, completion) -> None:
        """Pay ``times_bonus`` once every set time of the day is approved."""
        bonus = int(getattr(chore, "times_bonus", 0) or 0)
        if bonus <= 0 or not getattr(completion, "time_id", "") or not chore_has_times(chore):
            return
        day = dt_util.as_local(completion.completed_at).date()
        key = f"{chore.id}:{child.id}:{day.isoformat()}"
        paid = self._set_times_bonus_store()
        if key in paid:
            return
        # Every time done by the child, approved; a parent's "done for today"
        # closes the chore but earns no bonus.
        done = self.set_time_completions(chore, child.id, day, approved_only=True)
        if any(not getattr(done.get(t.id), "time_id", "") for t in chore.times):
            return
        # Claim the day before anything below can suspend.
        paid[key] = bonus
        cutoff = (day - timedelta(days=_BONUS_KEEP_DAYS)).isoformat()
        for old in [k for k in paid if k.rsplit(":", 1)[-1] < cutoff]:
            paid.pop(old, None)
        child.points += bonus
        child.total_points_earned += bonus
        child.career_score = child.total_points_earned - child.total_penalties_received
        self.storage.add_points_transaction(
            PointsTransaction(
                child_id=child.id,
                points=bonus,
                reason=f"All times done: {chore.name}",
                created_at=dt_util.now(),
            )
        )
        if hasattr(self, "_maybe_level_up"):
            await self._maybe_level_up(child)
        self.storage.update_child(child)
        self.hass.bus.async_fire(
            "taskmate_set_times_completed",
            {
                "child_id": child.id,
                "child_name": child.name,
                "chore_id": chore.id,
                "chore_name": chore.name,
                "bonus": bonus,
                "timestamp": dt_util.now().isoformat(),
            },
        )

    def _set_times_bonus_refund_owed(self, completion, child) -> int:
        """What reversing ``completion`` would take back of a paid all-times bonus."""
        if not child or not getattr(completion, "time_id", "") or not completion.approved:
            return 0
        chore = self.get_chore(completion.chore_id)
        if chore is None:
            return 0
        day = dt_util.as_local(completion.completed_at).date()
        key = f"{completion.chore_id}:{child.id}:{day.isoformat()}"
        paid = self._set_times_bonus_store().get(key)
        if not paid:
            return 0
        if self.set_times_full_day(chore, child.id, day, approved_only=True, exclude_id=completion.id):
            return 0
        return max(0, int(paid))

    def _reverse_set_times_bonus(self, completion, child) -> None:
        """Take back the all-times bonus when ``completion`` stops counting."""
        refund = self._set_times_bonus_refund_owed(completion, child)
        if refund <= 0:
            return
        day = dt_util.as_local(completion.completed_at).date()
        self._set_times_bonus_store().pop(f"{completion.chore_id}:{child.id}:{day.isoformat()}", None)
        chore = self.get_chore(completion.chore_id)
        child.points = max(0, child.points - refund)
        child.total_points_earned = max(0, child.total_points_earned - refund)
        self.storage.add_points_transaction(
            PointsTransaction(
                child_id=child.id,
                points=-refund,
                reason=f"All times done reversed: {getattr(chore, 'name', '')}".rstrip(": "),
                created_at=dt_util.now(),
            ),
            reverses_season=True,
        )

    # ── streaks ──────────────────────────────────────────────────────────

    def set_time_skips_streak(self, chore, completion, *, approved_only: bool = True) -> bool:
        """A set-time completion moves the streak only when it finishes the day."""
        if not getattr(completion, "time_id", "") or not chore_has_times(chore):
            return False
        day = dt_util.as_local(completion.completed_at).date()
        return not self.set_times_full_day(chore, completion.child_id, day, approved_only=approved_only)

    # ── mandatory misses, one per time ───────────────────────────────────

    def _set_time_owers(self, chore, day: date) -> list[str]:
        if hasattr(self, "_mandatory_owers"):
            return self._mandatory_owers(chore, day)
        assigned = list(getattr(chore, "assigned_to", []) or [])
        return assigned or [c.id for c in self.storage.get_children()]

    async def async_detect_set_time_misses(self, now: datetime | None = None, day: date | None = None) -> int:
        """Raise a mandatory miss for each set time that closed undone.

        Runs on the mandatory escalation tick, at startup and after a
        rejection, so it is idempotent: one miss per (chore, child, day, time).
        ``day`` before today checks every time of that day.
        """
        if getattr(self, "storage", None) is None:
            return 0
        now = now or dt_util.now()
        today = dt_util.as_local(now).date()
        day = day or today
        existing = {
            (m.chore_id, m.child_id, m.due_date, getattr(m, "time_id", "")) for m in self.storage.get_mandatory_misses()
        }
        created = 0
        for chore in self.storage.get_chores():
            if not chore_has_times(chore) or not getattr(chore, "mandatory", False):
                continue
            if not getattr(chore, "enabled", True):
                continue
            if hasattr(self, "_is_chore_scheduled_for_date") and not self._is_chore_scheduled_for_date(chore, day):
                continue
            if self._chore_hidden_by_gate(chore):
                continue
            for child_id in self._set_time_owers(chore, day):
                if child_id in (getattr(chore, "disabled_for", []) or []):
                    continue
                if hasattr(self, "is_sick_day") and self.is_sick_day(child_id, day):
                    continue
                if self.weekly_target_met(chore, child_id, day):
                    continue
                done = self.set_time_completions(chore, child_id, day)
                for t in chore.times:
                    if t.id in done:
                        continue
                    if day == today and not self.set_time_has_closed(chore, t, now):
                        continue
                    if (chore.id, child_id, day.isoformat(), t.id) in existing:
                        continue
                    miss = MandatoryMiss(
                        chore_id=chore.id,
                        child_id=child_id,
                        due_date=day.isoformat(),
                        period_id=SET_TIME_PERIOD,
                        penalty_points=int(getattr(chore, "mandatory_penalty_points", 0) or 0),
                        time_id=t.id,
                    )
                    self.storage.add_mandatory_miss(miss)
                    existing.add((chore.id, child_id, day.isoformat(), t.id))
                    created += 1
                    self.hass.bus.async_fire(
                        "taskmate_mandatory_missed",
                        {
                            "miss_id": miss.id,
                            "chore_id": chore.id,
                            "child_id": child_id,
                            "period_id": SET_TIME_PERIOD,
                            "time_id": t.id,
                            "penalty_points": miss.penalty_points,
                            "timestamp": dt_util.now().isoformat(),
                        },
                    )
        if created:
            await self.storage.async_save()
            await self.async_refresh()
        return created

    def set_time_miss_done(self, miss, day: date) -> bool:
        """Whether a set-time miss's time has since been ticked off."""
        chore = self.get_chore(miss.chore_id)
        if chore is None:
            return False
        return miss.time_id in self.set_time_completions(chore, miss.child_id, day)

    # ── the card view ────────────────────────────────────────────────────

    def set_times_state_for(self, chore, child_ids, now: datetime | None = None) -> dict[str, dict[str, str]]:
        """{child_id: {time_id: state}} for the sensor, only for children it applies to."""
        now = now or dt_util.now()
        return {cid: self.set_time_states(chore, cid, now) for cid in child_ids}
