"""Data coordinator for TaskMate integration."""
from __future__ import annotations

import logging
import random
from collections.abc import Callable
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from . import photos
from .const import DOMAIN
from .coord_assignments import AssignmentsMixin
from .coord_avatars import AvatarsMixin
from .coord_badges import BadgeCoordinator
from .coord_calendar import CalendarMixin
from .coord_challenges import ChallengesMixin
from .coord_chores import ChoresMixin
from .coord_mandatory import MandatoryMixin
from .coord_notifications import NotificationCoordinator
from .coord_points import PointsMixin
from .coord_quests import QuestsMixin
from .coord_rewards import RewardsMixin
from .coord_roulette import RouletteMixin
from .coord_scheduled import ScheduledChangesMixin
from .coord_templates import TemplatesMixin
from .coord_timed import TimedMixin
from .coord_unlocks import UnlocksMixin
from .models import Child
from .storage import TaskMateStorage

_LOGGER = logging.getLogger(__name__)


class TaskMateCoordinator(
    ChoresMixin,
    MandatoryMixin,
    AssignmentsMixin,
    RewardsMixin,
    PointsMixin,
    QuestsMixin,
    AvatarsMixin,
    ChallengesMixin,
    TimedMixin,
    CalendarMixin,
    TemplatesMixin,
    ScheduledChangesMixin,
    RouletteMixin,
    UnlocksMixin,
    DataUpdateCoordinator,
):
    """Coordinator to manage TaskMate data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.storage = TaskMateStorage(hass, entry_id)
        self.notifications = NotificationCoordinator(hass, self.storage)
        self.badges = BadgeCoordinator(hass, self.storage, self, self.notifications)
        self.entry_id = entry_id
        self._unsub_midnight: Callable[[], None] | None = None
        self._unsub_prune: Callable[[], None] | None = None
        self._unsub_availability: Callable[[], None] | None = None
        self._tracked_availability_entities: set[str] = set()
        self._tracked_visibility_entities: set[str] = set()
        # Bumped whenever a tracked external entity (child availability, chore
        # visibility, chore weather) changes state. The data snapshot is reused
        # while storage.data_version is unchanged, so sensors that derive
        # attributes from live entity state need this to invalidate their cache.
        self.external_state_version: int = 0
        self._unsub_surprise: Callable[[], None] | None = None
        self._unsub_weekly: Callable[[], None] | None = None
        self._unsub_mandatory: list[Callable[[], None]] = []
        # Per-build memo for the availability matrix (PERF-1). Non-None only
        # inside `availability_build_scope()`; see coord_chores/coord_assignments.
        self._avail_cache: dict | None = None
        # (data_version, snapshot) cache for _async_update_data (PERF-2).
        self._data_snapshot_cache: tuple[int, dict[str, Any]] | None = None
        # Scheduled reverts for timed unlock rewards (#678).
        self._unlock_timers: list = []

    def difficulty_multiplier(self, tier: str) -> float:
        """Return the points multiplier for a difficulty tier.

        Unknown tiers fall back to the neutral "medium" baseline (×1.0).
        Per-tier multipliers are configurable via the
        ``difficulty_multiplier_<tier>`` settings keys.
        """
        from .const import DEFAULT_DIFFICULTY, DEFAULT_DIFFICULTY_MULTIPLIERS

        resolved = tier if tier in DEFAULT_DIFFICULTY_MULTIPLIERS else DEFAULT_DIFFICULTY
        default = DEFAULT_DIFFICULTY_MULTIPLIERS[resolved]
        try:
            return float(
                self.storage.get_setting(
                    f"difficulty_multiplier_{resolved}", str(default)
                )
            )
        except (ValueError, TypeError):
            return default

    def effective_chore_points(self, chore) -> int:
        """Base chore points scaled by its difficulty multiplier (never negative)."""
        from .const import DEFAULT_DIFFICULTY

        base = int(getattr(chore, "points", 0) or 0)
        tier = getattr(chore, "difficulty", DEFAULT_DIFFICULTY) or DEFAULT_DIFFICULTY
        return max(0, round(base * self.difficulty_multiplier(tier)))

    # ── Vacation / pause mode ────────────────────────────────────────────
    # A vacation period is a date range during which chores are hidden/paused
    # and streaks are frozen (missed days inside a vacation never break a
    # streak). Stored as the "vacation_periods" setting: a list of
    # {"id", "name", "start", "end"} with inclusive ISO "YYYY-MM-DD" bounds.

    def get_vacation_periods(self) -> list[dict]:
        """Return the configured vacation periods (validated, sorted by start)."""
        raw = self.storage.get_setting("vacation_periods", None)
        if not isinstance(raw, list):
            return []
        periods = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                start = date.fromisoformat(str(entry.get("start")))
                end = date.fromisoformat(str(entry.get("end")))
            except (TypeError, ValueError):
                continue
            if end < start:
                start, end = end, start
            periods.append({
                "id": str(entry.get("id") or "").strip() or start.isoformat(),
                "name": str(entry.get("name") or "").strip(),
                "start": start.isoformat(),
                "end": end.isoformat(),
            })
        return sorted(periods, key=lambda p: p["start"])

    def active_vacation(self, on: date | None = None) -> dict | None:
        """Return the vacation period covering ``on`` (default today), or None."""
        day = on or dt_util.now().date()
        for p in self.get_vacation_periods():
            try:
                if date.fromisoformat(p["start"]) <= day <= date.fromisoformat(p["end"]):
                    return p
            except (TypeError, ValueError):
                continue
        return None

    def is_vacation_day(self, on: date | None = None) -> bool:
        """True if ``on`` (default today) falls within any vacation period."""
        return self.active_vacation(on) is not None

    def _vacation_calendar_active(self) -> bool:
        """True if the global family vacation calendar entity currently has an
        active event. The ``vacation_calendar`` setting holds a ``calendar.*``
        (or any on/off) entity id; empty = disabled. Fail-open: a missing or
        broken entity does not freeze anyone.
        """
        entity_id = (self.storage.get_setting("vacation_calendar", "") or "").strip()
        if not entity_id:
            return False
        return self._read_entity_active(entity_id) is True

    @contextmanager
    def availability_build_scope(self):
        """Memoize chore-only computations for one availability build (PERF-1).

        The availability matrix calls ``is_chore_available_for_child`` for every
        chore × child. Several inner computations depend only on the chore (the
        rotation active-set, the rotation-done check) or are re-fetched from
        storage repeatedly (the completions list, which ``get_completions``
        rebuilds from dicts on each call). Inside this scope those are computed
        once and cached. The build is fully synchronous (no awaits), so storage
        cannot mutate while the cache is live. Re-entrant scopes reuse the cache.
        """
        if getattr(self, "_avail_cache", None) is not None:
            yield  # already inside a scope — reuse the existing cache
            return
        self._avail_cache = {
            "completions": self.storage.get_completions(),
            "active": {},
            "rotation_done": {},
        }
        try:
            yield
        finally:
            self._avail_cache = None

    def _cached_completions(self) -> list:
        """Completions list, served from the availability cache when in scope."""
        cache = getattr(self, "_avail_cache", None)
        if cache is not None:
            return cache["completions"]
        return self.storage.get_completions()

    def _is_child_on_vacation(self, child, on: date | None = None) -> bool:
        """True when ``child`` should be treated as away (streak frozen, chores
        hidden) on ``on`` (default today). Three stacking sources, OR'd:

          1. a global static ``vacation_periods`` range covers the day;
          2. the global ``vacation_calendar`` entity has an active event now;
          3. this child opted in (``pause_streak_when_unavailable``) and their
             own availability/unavailability sensor — which may be a
             ``calendar.*`` entity — currently reports them away.

        Sources 2 and 3 are evaluated live (current entity state); source 1 is
        historical date math. ``child`` may be ``None`` (callers that only have
        a global context), in which case only sources 1 and 2 apply.
        """
        if self.is_vacation_day(on):
            return True
        if self._vacation_calendar_active():
            return True
        if child is not None and getattr(child, "pause_streak_when_unavailable", False):
            if not self._is_child_available(child.id):
                return True
        return False

    # ── Backup / restore ─────────────────────────────────────────────────
    EXPORT_VERSION = 1

    def export_config(self) -> dict:
        """Return a portable backup of all TaskMate data."""
        return {
            "taskmate_export_version": self.EXPORT_VERSION,
            "data": self.storage.export_data(),
        }

    async def async_import_config(self, payload: dict) -> None:
        """Restore TaskMate data from an export payload (full replace)."""
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise ValueError("Invalid TaskMate export payload")
        self.storage.import_data(payload["data"])
        await self.storage.async_save()
        await self.async_refresh()

    # ── Admin audit log ──────────────────────────────────────────────────
    async def async_record_audit(
        self, user_id: str, user_name: str, action: str, target: str = ""
    ) -> None:
        """Record an admin config action in the audit log and persist it."""
        from .models import generate_id

        self.storage.add_audit_entry({
            "id": generate_id(),
            "ts": dt_util.now().isoformat(),
            "user_id": user_id or "",
            "user_name": user_name or "",
            "action": action,
            "target": target or "",
        })
        await self.storage.async_save()

    async def async_initialize(self) -> None:
        """Initialize the coordinator."""
        await self.storage.async_load()
        self.notifications.coordinator = self
        # Wire existing parent recipients to default-on parent-audience types
        # that have no routes yet (e.g. a parent added after the one-time seed),
        # so pending-approval notifications actually reach a parent.
        if self.notifications.ensure_parent_default_routes():
            await self.storage.async_save()
        # Achievement badges: silent retroactive backfill on first install
        if self.storage.is_badges_backfill_pending():
            await self.badges.rebuild_all()
            self.storage.clear_badges_backfill_pending()
            await self.storage.async_save()
        await self._async_backfill_career_history()
        await self._async_stop_stale_timed_sessions()
        # Catch up on scheduled changes (#675) that came due while HA was off —
        # the parent still expects "from 1 September" to have happened.
        await self.async_apply_due_scheduled_changes(refresh=False)
        # A restart mid-unlock must never strand the TV on (#678).
        await self.async_resume_unlocks()
        await self.async_refresh()
        # Schedule midnight streak check at 00:00:05
        self._unsub_midnight = async_track_time_change(
            self.hass, self._async_midnight_streak_check, hour=0, minute=0, second=5
        )
        # Schedule daily history pruning at 00:01:00
        self._unsub_prune = async_track_time_change(
            self.hass, self._async_scheduled_prune, hour=0, minute=1, second=0
        )
        # Re-evaluate availability-aware chore assignments when any HA entity
        # state changes. The callback filters cheaply on entity id so only
        # relevant flips trigger a recompute.
        self._refresh_tracked_availability_entities()
        self._unsub_availability = self.hass.bus.async_listen(
            "state_changed", self._availability_state_changed
        )
        # Surprise-bonus daily roll at 16:00 (opt-in; no-op unless enabled)
        self._unsub_surprise = async_track_time_change(
            self.hass, self._async_surprise_bonus_check, hour=16, minute=0, second=0
        )
        # Weekly digest — fired Sundays at 18:00 (opt-in)
        self._unsub_weekly = async_track_time_change(
            self.hass, self._async_weekly_digest_check, hour=18, minute=0, second=0
        )
        await self.notifications.async_setup_schedules()
        # Mandatory-chore period-end detection (#532)
        self.arm_mandatory_schedules()
        await self.async_catchup_mandatory_misses()

    @callback
    def _async_weekly_digest_check(self, now: datetime) -> None:
        """Daily 18:00 callback; fires the weekly digest on Sundays and the
        monthly report on the 1st of the month (FEAT-14)."""
        if now.weekday() == 6:  # Sunday
            self.hass.async_create_task(self._async_send_weekly_digest())
        if now.day == 1:
            self.hass.async_create_task(self._async_send_monthly_report())
            self.hass.async_create_task(self._async_finalize_season())

    async def _async_send_weekly_digest(self) -> None:
        """Build and send the weekly digest to parents (opt-in)."""
        summary = self._build_weekly_digest()
        if not summary:
            return
        await self.notifications.fire("weekly_digest", {"summary": summary})

    def _build_weekly_digest(self) -> str:
        """One line per child: chores done + points earned this week."""
        today = dt_util.now().date()
        week_start = today - timedelta(days=today.weekday())
        children = self.storage.get_children()
        if not children:
            return ""
        done: dict[str, int] = {}
        earned: dict[str, int] = {}
        for comp in self.storage.get_completions():
            if not comp.approved or comp.bonus_subtask_id:
                continue
            if dt_util.as_local(comp.completed_at).date() < week_start:
                continue
            done[comp.child_id] = done.get(comp.child_id, 0) + 1
            earned[comp.child_id] = earned.get(comp.child_id, 0) + (comp.points_awarded or 0)
        pts = self.storage.get_points_name()
        lines = [
            f"• {c.name}: {done.get(c.id, 0)} chores, {earned.get(c.id, 0)} {pts} earned"
            for c in children
        ]
        return "\n".join(lines)

    async def _async_send_monthly_report(self) -> None:
        """Build and send the previous calendar month's per-child recap (FEAT-14)."""
        today = dt_util.now().date()
        month_end = today.replace(day=1) - timedelta(days=1)
        month_start = month_end.replace(day=1)
        summary = self._build_monthly_report(month_start, month_end)
        if not summary:
            return
        await self.notifications.fire("monthly_report", {
            "summary": summary,
            "month": month_start.strftime("%B %Y"),
        })

    def _build_monthly_report(self, month_start: date, month_end: date) -> str:
        """Per-child recap for [month_start, month_end]: chores, points, level, best streak."""
        children = self.storage.get_children()
        if not children:
            return ""
        done: dict[str, int] = {}
        earned: dict[str, int] = {}
        for comp in self.storage.get_completions():
            if not comp.approved or comp.bonus_subtask_id:
                continue
            d = dt_util.as_local(comp.completed_at).date()
            if not (month_start <= d <= month_end):
                continue
            done[comp.child_id] = done.get(comp.child_id, 0) + 1
            earned[comp.child_id] = earned.get(comp.child_id, 0) + (comp.points_awarded or 0)
        pts = self.storage.get_points_name()
        lines = [
            f"• {c.name}: {done.get(c.id, 0)} chores, {earned.get(c.id, 0)} {pts}, "
            f"level {getattr(c, 'level', 1)}, best streak {getattr(c, 'best_streak', 0)}"
            for c in children
        ]
        return "\n".join(lines)

    # ── Leaderboard seasons (FEAT-2) ─────────────────────────────────────
    def get_season_standings(self, ym: str | None = None) -> list[dict]:
        """Per-child points earned in calendar month ``ym`` (default current),
        ranked high→low (ties broken by name)."""
        if ym is None:
            ym = dt_util.now().strftime("%Y-%m")
        pts = self.storage.get_season_points(ym)
        rows = [
            {"child_id": c.id, "name": c.name, "points": int(pts.get(c.id, 0))}
            for c in self.storage.get_children()
        ]
        rows.sort(key=lambda r: (-r["points"], r["name"].lower()))
        for i, r in enumerate(rows):
            r["rank"] = i + 1
        return rows

    # ── Family co-op goal (FEAT-4) ───────────────────────────────────────
    def family_goal_progress(self) -> int:
        """Combined current points across all children (the shared goal metric)."""
        return sum(c.points for c in self.storage.get_children())

    async def _async_check_family_goal(self) -> None:
        """Fire the family-goal notification once the combined points reach the
        target. Idempotent via the family_goal_achieved flag (reset when the
        target/enabled setting changes)."""
        if not self._setting_enabled("family_goal_enabled"):
            return
        if self.storage.get_setting("family_goal_achieved", False) in (True, "true"):
            return
        try:
            target = int(self.storage.get_setting("family_goal_target", 0))
        except (TypeError, ValueError):
            target = 0
        if target < 1 or self.family_goal_progress() < target:
            return
        self.storage.set_setting("family_goal_achieved", True)
        await self.storage.async_save()
        name = str(self.storage.get_setting("family_goal_name", "") or "Family goal")
        reward = str(self.storage.get_setting("family_goal_reward", "") or "a treat")
        self.hass.bus.async_fire("taskmate_family_goal_reached", {
            "goal_name": name, "goal_reward": reward, "target": target,
            "timestamp": dt_util.now().isoformat(),
        })
        await self.notifications.fire("family_goal_reached", {
            "goal_name": name, "goal_reward": reward,
        })

    # ── Allowance payout ledger (FEAT-3) ─────────────────────────────────
    async def async_record_allowance_payout(self, child_id: str, points: int) -> dict:
        """Record a parent-confirmed allowance payout: deduct ``points`` and log
        the cash equivalent (fixed conversion rate — no dynamic pricing).

        Returns the ledger entry. Raises ValueError on a bad child/points or when
        allowance is disabled.
        """
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        points = int(points)
        if points < 1:
            raise ValueError("points must be >= 1")
        if not self._setting_enabled("allowance_enabled"):
            raise ValueError("Allowance is not enabled")
        try:
            rate = int(self.storage.get_setting("allowance_rate", 10))
        except (TypeError, ValueError):
            rate = 10
        rate = max(1, rate)
        currency = str(self.storage.get_setting("allowance_currency", "") or "")
        amount = round(points / rate, 2)

        await self.async_remove_points(child_id, points, reason="Allowance payout")

        from .models import generate_id
        entry = {
            "id": generate_id(),
            "child_id": child_id,
            "child_name": child.name,
            "points": points,
            "amount": amount,
            "currency": currency,
            "date": dt_util.now().isoformat(),
        }
        self.storage.add_allowance_payout(entry)
        await self.storage.async_save()
        self.hass.bus.async_fire("taskmate_allowance_paid", {**entry, "timestamp": entry["date"]})
        await self.async_refresh()
        return entry

    # ── ICS calendar feed token (FEAT-10) ────────────────────────────────
    async def async_get_or_create_ics_token(self) -> str:
        """Return the ICS feed token, generating + persisting one on first use."""
        token = self.storage.get_setting("ics_token", "")
        if not token:
            import secrets
            token = secrets.token_urlsafe(24)
            self.storage.set_setting("ics_token", token)
            await self.storage.async_save()
        return token

    async def async_regenerate_ics_token(self) -> str:
        """Rotate the ICS feed token (invalidates existing subscriptions)."""
        import secrets
        token = secrets.token_urlsafe(24)
        self.storage.set_setting("ics_token", token)
        await self.storage.async_save()
        return token

    async def _async_finalize_season(self) -> None:
        """At month start, record the previous month's champion (top earner)."""
        now = dt_util.now()
        prev_end = now.date().replace(day=1) - timedelta(days=1)
        ym = prev_end.strftime("%Y-%m")
        if any(c.get("month") == ym for c in self.storage.get_season_champions()):
            return  # already finalised
        winners = [r for r in self.get_season_standings(ym) if r["points"] > 0]
        if not winners:
            return
        top = winners[0]
        self.storage.add_season_champion({
            "month": ym,
            "child_id": top["child_id"],
            "child_name": top["name"],
            "points": top["points"],
        })
        await self.storage.async_save()
        self.hass.bus.async_fire("taskmate_season_champion", {
            "month": ym, "child_id": top["child_id"], "child_name": top["name"],
            "points": top["points"], "timestamp": now.isoformat(),
        })
        await self.notifications.fire("season_champion", {
            "child_name": top["name"], "points": top["points"],
            "month": prev_end.strftime("%B %Y"),
            "points_name": self.storage.get_points_name(),
        })

    @callback
    def _async_surprise_bonus_check(self, now: datetime) -> None:
        """Scheduled callback — roll the daily surprise bonus."""
        self.hass.async_create_task(self._async_run_surprise_bonus())

    async def _async_run_surprise_bonus(self) -> None:
        """Each enabled day, give each child a random chance at a surprise bonus.

        Opt-in via the ``surprise_bonus_enabled`` setting. Per child, rolls
        ``surprise_bonus_chance`` percent; on a hit awards a random amount in
        [min, max], logged as a normal points transaction, and fires a
        ``taskmate_surprise_bonus`` event for automations.
        """
        enabled = self.storage.get_setting("surprise_bonus_enabled", False)
        if not (enabled is True or str(enabled).lower() == "true"):
            return
        try:
            chance = float(self.storage.get_setting("surprise_bonus_chance", "15"))
        except (ValueError, TypeError):
            chance = 15.0
        try:
            lo = int(float(self.storage.get_setting("surprise_bonus_min", "5")))
            hi = int(float(self.storage.get_setting("surprise_bonus_max", "20")))
        except (ValueError, TypeError):
            lo, hi = 5, 20
        if hi < lo:
            lo, hi = hi, lo
        for child in self.storage.get_children():
            if random.random() * 100.0 >= chance:
                continue
            pts = random.randint(lo, hi)
            if pts <= 0:
                continue
            await self.async_add_points(child.id, pts, reason="Surprise bonus 🎉")
            self.hass.bus.async_fire("taskmate_surprise_bonus", {
                "child_id": child.id, "child_name": child.name,
                "points": pts, "timestamp": dt_util.now().isoformat(),
            })

    async def _async_backfill_career_history(self) -> None:
        """Backfill career_score_history from completions and transactions.

        Runs once on startup for children whose history is sparse (fewer than
        7 entries). Uses all stored completions and transactions — not the
        capped sensor attributes — so coverage matches the 90-day retention.
        """
        children = self.storage.get_children()
        if not children:
            return

        needs_save = False
        completions = self.storage.get_completions()
        transactions = self.storage.get_points_transactions()
        chore_lookup = {ch.id: ch for ch in self.storage.get_chores()}

        for child in children:
            existing = self.storage.get_career_score_history(child.id)
            if len(existing) >= 7:
                continue

            daily_net: dict[str, int] = {}
            for comp in completions:
                if comp.child_id != child.id or not comp.approved:
                    continue
                day = comp.completed_at.date().isoformat()
                pts = comp.points_awarded
                if not pts:
                    chore = chore_lookup.get(comp.chore_id)
                    pts = chore.points if chore else 0
                daily_net[day] = daily_net.get(day, 0) + pts

            for txn in transactions:
                if txn.child_id != child.id:
                    continue
                day = txn.created_at.date().isoformat()
                daily_net[day] = daily_net.get(day, 0) + txn.points

            if not daily_net:
                continue

            sorted_days = sorted(daily_net.keys())
            total_net = sum(daily_net.values())
            start_score = (child.career_score or 0) - total_net

            running = start_score
            for day in sorted_days:
                running += daily_net[day]
                self.storage.append_career_score_snapshot(
                    child.id, day, running
                )
            needs_save = True
            _LOGGER.info(
                "Backfilled %d career history entries for %s",
                len(sorted_days), child.name,
            )

        if needs_save:
            await self.storage.async_save()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and clean up listeners."""
        self.cancel_unlock_timers()
        if self._unsub_midnight:
            self._unsub_midnight()
            self._unsub_midnight = None
        if self._unsub_prune:
            self._unsub_prune()
            self._unsub_prune = None
        if self._unsub_availability:
            self._unsub_availability()
            self._unsub_availability = None
        if self._unsub_surprise:
            self._unsub_surprise()
            self._unsub_surprise = None
        if self._unsub_weekly:
            self._unsub_weekly()
            self._unsub_weekly = None
        self.disarm_mandatory_schedules()
        # Flush any pending debounced save so an entry unload/reload can't drop
        # the last mutation (PERF-3).
        await self.storage.async_save_now()

    @callback
    def _async_midnight_streak_check(self, now: datetime) -> None:
        """Scheduled callback at midnight to run all daily maintenance."""
        self.hass.async_create_task(self._async_run_midnight_maintenance(now))

    async def _async_run_midnight_maintenance(self, now: datetime) -> None:
        """Run the midnight maintenance steps sequentially.

        A single task (rather than one task per step) so the read-modify-write
        steps on shared storage can't interleave and overwrite each other's
        saves. One step failing must not stop the rest.
        """
        steps = [
            self.async_apply_due_scheduled_changes,
            self.async_prune_roulette_state,
            self._async_check_streaks,
            self._async_expire_one_shot_chores,
            self._async_expire_dated_chores,
            self._async_expire_deadline_chores,
            self._async_restock_rewards,
            self._async_expire_rewards,
            self._async_decay_points,
            self._async_apply_interest,
            self._async_stop_stale_timed_sessions,
            # Rotate assignment_current_child_id and publish today's events
            # to every configured calendar
            self._async_refresh_assignments_and_publish,
            # Mandatory 'anytime' chores + postpone-map reset (#532)
            self.async_detect_anytime_mandatory_misses,
            self.async_prune_orphan_misses,
            self._async_sweep_orphan_photos,
        ]
        # Check for perfect week bonus every Monday at midnight
        if now.weekday() == 0:
            steps.append(self._async_check_perfect_week)
        for step in steps:
            try:
                await step()
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Midnight maintenance step %s failed", step.__name__)
        # Prune all-chores-done daily flags older than today
        self.storage.prune_all_done_flags(dt_util.now().date().isoformat())
        await self.storage.async_save()

    async def _async_sweep_orphan_photos(self) -> None:
        """Delete evidence photos not referenced by any completion (SEC-2)."""
        referenced = [
            getattr(c, "photo_url", "")
            for c in self.storage.get_completions()
            if getattr(c, "photo_url", "")
        ]
        removed = await photos.async_sweep_orphan_photos(self.hass, referenced)
        if removed:
            _LOGGER.info("Swept %d orphan evidence photo(s)", removed)

    @callback
    def _async_scheduled_prune(self, now: datetime) -> None:
        """Scheduled callback to prune old completion history."""
        days = int(self.storage.get_setting("history_days", "90"))
        self.hass.async_create_task(self.async_prune_history(days))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from storage.

        PERF-2: rebuilding every child/chore/completion from its stored dict on
        each 30 s poll is wasteful when nothing changed. Cache the built dict
        keyed by ``storage.data_version`` (bumped on every save) and reuse it
        until the next mutation. Availability is recomputed in the sensor layer
        from live entity state, not from this dict, so a stale-version reuse
        never staleness-bugs availability — listeners still re-read each tick.
        """
        # May stop sessions (mutates + saves -> bumps the version), so run first.
        await self._async_auto_stop_capped_sessions()
        await self._async_check_family_goal()
        # Reactive-chore deadlines are minutes long, so they can't wait for
        # midnight maintenance like the date-based expiries do. refresh=False:
        # we are already inside the refresh, and the snapshot below picks the
        # change up in this same tick.
        await self._async_expire_deadline_chores(refresh=False)
        self._refresh_tracked_availability_entities()
        version = self.storage.data_version
        cached = getattr(self, "_data_snapshot_cache", None)
        if cached is not None and cached[0] == version:
            return cached[1]
        snapshot = self._build_data_snapshot()
        self._data_snapshot_cache = (version, snapshot)
        return snapshot

    def _build_data_snapshot(self) -> dict[str, Any]:
        return {
            "children": self.storage.get_children(),
            "chores": self.storage.get_chores(),
            "rewards": self.storage.get_rewards(),
            "completions": self.storage.get_completions(),
            "pending_completions": self.storage.get_pending_completions(),
            "reward_claims": self.storage.get_reward_claims(),
            "pending_reward_claims": self.storage.get_pending_reward_claims(),
            "points_transactions": self.storage.get_points_transactions(),
            "points_name": self.storage.get_points_name(),
            "points_icon": self.storage.get_points_icon(),
            "settings": self.storage.get_settings(),
            "penalties": self.storage.get_penalties(),
            "bonuses": self.storage.get_bonuses(),
            "pool_allocations": self.storage.get_pool_allocations(),
            "timed_sessions": self.storage.get_timed_sessions(),
        }

    # Child operations
    async def async_add_child(
        self,
        name: str,
        avatar: str = "mdi:account-circle",
        availability_entity: str = "",
        availability_inverted: bool = False,
        unavailability_entity: str = "",
        pause_streak_when_unavailable: bool = False,
        linked_user_id: str = "",
    ) -> Child:
        """Add a new child."""
        child = Child(
            name=name,
            avatar=avatar,
            availability_entity=availability_entity,
            availability_inverted=availability_inverted,
            unavailability_entity=unavailability_entity,
            pause_streak_when_unavailable=pause_streak_when_unavailable,
            linked_user_id=linked_user_id,
        )
        self.storage.add_child(child)
        await self.storage.async_save()
        await self.async_refresh()
        return child

    async def async_update_child(self, child: Child) -> None:
        """Update a child."""
        self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_child(self, child_id: str) -> None:
        """Remove a child and all associated data."""
        self.storage.remove_child(child_id)
        self.storage.remove_completions_for_child(child_id)
        self.storage.remove_reward_claims_for_child(child_id)
        self.storage.remove_transactions_for_child(child_id)
        self.storage.remove_last_completed_for_child(child_id)
        self.storage.remove_pool_allocations_for_child(child_id)
        self.storage.remove_career_score_history_for_child(child_id)
        self.storage.remove_quest_progress_for_child(child_id)
        self.storage.remove_challenge_progress_for_child(child_id)
        # Remove child from chore assigned_to lists
        for chore in self.storage.get_chores():
            if child_id in chore.assigned_to:
                chore.assigned_to.remove(child_id)
                self.storage.update_chore(chore)
        await self.storage.async_save()
        await self.async_refresh()

    def get_child(self, child_id: str) -> Child | None:
        """Get a child by ID."""
        return self.storage.get_child(child_id)

    async def async_set_setting(self, key: str, value: str) -> None:
        """Update a generic setting."""
        self.storage.set_setting(key, value)
        await self.storage.async_save()
        await self.async_refresh()

    # Settings
    async def async_set_points_settings(self, name: str, icon: str) -> None:
        """Update points settings."""
        self.storage.set_points_name(name)
        self.storage.set_points_icon(icon)
        await self.storage.async_save()
        await self.async_refresh()
