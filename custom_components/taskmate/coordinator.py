"""Data coordinator for TaskMate integration."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta
import logging
import random
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coord_assignments import AssignmentsMixin
from .coord_badges import BadgeCoordinator
from .coord_notifications import NotificationCoordinator
from .coord_calendar import CalendarMixin
from .coord_chores import ChoresMixin
from .coord_points import PointsMixin
from .coord_rewards import RewardsMixin
from .coord_templates import TemplatesMixin
from .coord_timed import TimedMixin
from .models import Child
from .storage import TaskMateStorage

_LOGGER = logging.getLogger(__name__)


class TaskMateCoordinator(
    ChoresMixin,
    AssignmentsMixin,
    RewardsMixin,
    PointsMixin,
    TimedMixin,
    CalendarMixin,
    TemplatesMixin,
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
        self._unsub_surprise: Callable[[], None] | None = None

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
        # Achievement badges: silent retroactive backfill on first install
        if self.storage._data.get("badges_backfill_pending"):
            await self.badges.rebuild_all()
            self.storage._data.pop("badges_backfill_pending", None)
            await self.storage.async_save()
        await self._async_backfill_career_history()
        await self._async_stop_stale_timed_sessions()
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
        self._unsub_availability = self.hass.bus.async_listen(
            "state_changed", self._availability_state_changed
        )
        # Surprise-bonus daily roll at 16:00 (opt-in; no-op unless enabled)
        self._unsub_surprise = async_track_time_change(
            self.hass, self._async_surprise_bonus_check, hour=16, minute=0, second=0
        )
        await self.notifications.async_setup_schedules()

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
            self._async_check_streaks,
            self._async_expire_one_shot_chores,
            self._async_restock_rewards,
            self._async_expire_rewards,
            self._async_stop_stale_timed_sessions,
            # Rotate assignment_current_child_id and publish today's events
            # to every configured calendar
            self._async_refresh_assignments_and_publish,
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

    @callback
    def _async_scheduled_prune(self, now: datetime) -> None:
        """Scheduled callback to prune old completion history."""
        days = int(self.storage.get_setting("history_days", "90"))
        self.hass.async_create_task(self.async_prune_history(days))

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from storage."""
        await self._async_auto_stop_capped_sessions()
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
            "settings": self.storage._data.get("settings", {}),
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
        linked_user_id: str = "",
    ) -> Child:
        """Add a new child."""
        child = Child(
            name=name,
            avatar=avatar,
            availability_entity=availability_entity,
            availability_inverted=availability_inverted,
            unavailability_entity=unavailability_entity,
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
