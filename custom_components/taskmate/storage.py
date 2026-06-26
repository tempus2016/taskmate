"""Storage management for TaskMate integration."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .models import (
    AwardedBadge,
    Badge,
    Bonus,
    Challenge,
    Child,
    Chore,
    ChoreCompletion,
    CustomNotification,
    MandatoryMiss,
    NotificationConfig,
    NotificationRoute,
    ParentRecipient,
    Penalty,
    PointsTransaction,
    PoolAllocation,
    Quest,
    Reward,
    RewardClaim,
    TaskGroup,
    TimedSession,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"

# Debounce window for coalescing the 2-4 saves a single operation can trigger
# into one disk write (PERF-3). Small enough that a crash loses at most this
# much; HA flushes pending delayed saves on shutdown.
_SAVE_DEBOUNCE_SECONDS = 1.0


class TaskMateStorage:
    """Manage TaskMate data storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        self._data: dict[str, Any] = {}
        # Monotonic counter bumped on every persisted mutation (PERF-2). Lets the
        # coordinator skip rebuilding its data snapshot when nothing has changed.
        self._data_version = 0

    async def async_load(self) -> dict[str, Any]:
        """Load data from storage."""
        data = await self._store.async_load()
        is_fresh = data is None
        if is_fresh:
            data = {
                "children": [],
                "chores": [],
                "rewards": [],
                "completions": [],
                "mandatory_misses": [],
                "reward_claims": [],
                "points_transactions": [],
                "pool_allocations": [],
                "task_groups": [],
                "badges": [],
                "awarded_badges": [],
                "points_name": "Stars",
                "points_icon": "mdi:star",
                "last_completed": {},
            }
        self._data = data

        # Ensure last_completed store exists (migration for existing installs)
        if "last_completed" not in self._data:
            self._data["last_completed"] = {}

        # Ensure pool_allocations store exists (migration for v3.0 pool mode)
        if "pool_allocations" not in self._data:
            self._data["pool_allocations"] = []

        # Ensure task_groups store exists (migration for existing installs)
        if "task_groups" not in self._data:
            self._data["task_groups"] = []

        # Ensure timed_sessions store exists (migration for timed tasks feature)
        if "timed_sessions" not in self._data:
            self._data["timed_sessions"] = []

        # Ensure career_score_history store exists
        if "career_score_history" not in self._data:
            self._data["career_score_history"] = {}

        # Ensure templates store exists
        if "templates" not in self._data:
            self._data["templates"] = []

        # Ensure badges store exists (migration for achievement badges feature)
        if "badges" not in self._data:
            self._data["badges"] = []

        # Ensure awarded_badges store exists (migration for achievement badges feature)
        if "awarded_badges" not in self._data:
            self._data["awarded_badges"] = []

        # Ensure chore_display_order store exists (global admin ordering)
        if "chore_display_order" not in self._data:
            self._data["chore_display_order"] = []

        # Notifications overhaul (v3.9.0)
        if "parent_recipients" not in self._data:
            self._data["parent_recipients"] = []
        if "notification_config" not in self._data:
            self._data["notification_config"] = {}
        if "custom_notifications" not in self._data:
            self._data["custom_notifications"] = []
        if "notifications_migration_done" not in self._data:
            self._run_notifications_migration()
            self._data["notifications_migration_done"] = True

        # Badge migration / seeding
        self._seed_builtin_badges(is_fresh=is_fresh)

        # Run data migrations
        await self._migrate_assigned_to_child_ids()
        await self._migrate_pool_allocations_v2()
        await self._migrate_career_score()

        return data

    async def _migrate_pool_allocations_v2(self) -> None:
        """Migrate beta1 pool allocations to beta2 semantics.

        In v3.0.0-beta1, pool allocations did NOT deduct from child.points (the points
        stayed in the gross balance until redeem). From beta2 onward, allocations deduct
        immediately so the visible balance reflects commitment.

        For existing installs: subtract each allocation's allocated_points from the
        corresponding child's points, once. Guarded by a version flag so it runs only
        on the first beta2 load.
        """
        if self._data.get("_pool_semantics_version", 1) >= 2:
            return

        allocations = self._data.get("pool_allocations", [])
        children = self._data.get("children", [])
        if not allocations or not children:
            # Mark as migrated even if nothing to do
            self._data["_pool_semantics_version"] = 2
            await self.async_save()
            return

        # Build child lookup keyed by id
        children_by_id = {c.get("id"): c for c in children}
        adjusted = 0
        for alloc in allocations:
            child_data = children_by_id.get(alloc.get("child_id"))
            if not child_data:
                continue
            allocated = int(alloc.get("allocated_points", 0) or 0)
            if allocated <= 0:
                continue
            current_points = int(child_data.get("points", 0) or 0)
            child_data["points"] = max(0, current_points - allocated)
            adjusted += 1

        self._data["_pool_semantics_version"] = 2
        if adjusted:
            _LOGGER.info(
                "TaskMate: migrated %d pool allocation(s) to beta2 semantics "
                "(points now deducted at allocation time)", adjusted
            )
        await self.async_save()

    async def _migrate_assigned_to_child_ids(self) -> None:
        """Migrate chore assigned_to from child names to child IDs if needed.

        This handles legacy data where assigned_to might contain child names
        instead of child IDs.
        """
        children = self._data.get("children", [])
        chores = self._data.get("chores", [])

        if not children or not chores:
            return

        # Build a map of child name -> child ID for migration
        name_to_id = {}
        valid_ids = set()
        for child in children:
            child_id = child.get("id", "")
            child_name = child.get("name", "")
            if child_id:
                valid_ids.add(child_id)
            if child_name and child_id:
                name_to_id[child_name] = child_id

        # Check and migrate each chore's assigned_to
        data_modified = False
        for chore in chores:
            assigned_to = chore.get("assigned_to", [])
            if not assigned_to:
                continue

            new_assigned_to = []
            chore_modified = False

            for assignment in assigned_to:
                if assignment in valid_ids:
                    # Already a valid child ID
                    new_assigned_to.append(assignment)
                elif assignment in name_to_id:
                    # This is a child name, convert to ID
                    new_assigned_to.append(name_to_id[assignment])
                    chore_modified = True
                    _LOGGER.warning(
                        "Migrating chore '%s' assigned_to: '%s' -> '%s' (name to ID)",
                        chore.get("name", "unknown"),
                        assignment,
                        name_to_id[assignment]
                    )
                else:
                    # Unknown value, keep it but log a warning
                    new_assigned_to.append(assignment)
                    _LOGGER.warning(
                        "Chore '%s' has unknown assigned_to value: '%s'",
                        chore.get("name", "unknown"),
                        assignment
                    )

            if chore_modified:
                chore["assigned_to"] = new_assigned_to
                data_modified = True

        if data_modified:
            _LOGGER.info("Data migration completed: converted child names to IDs in assigned_to")
            await self.async_save()

    async def _migrate_career_score(self) -> None:
        """Initialize career_score for existing installations.

        Sets career_score = total_points_earned for each child (we cannot
        retroactively determine penalty totals from the pruned transaction
        buffer).  Runs once, guarded by _career_score_initialized flag.
        """
        if self._data.get("_career_score_initialized"):
            return

        children = self._data.get("children", [])
        for child_data in children:
            earned = int(child_data.get("total_points_earned", 0) or 0)
            child_data.setdefault("career_score", earned)
            child_data.setdefault("total_penalties_received", 0)

        self._data["_career_score_initialized"] = True
        if children:
            _LOGGER.info(
                "TaskMate: initialized career_score for %d child(ren) "
                "from total_points_earned", len(children)
            )
        await self.async_save()

    async def async_save(self) -> None:
        """Persist data, debounced (PERF-3).

        A single TaskMate operation often calls this 2-4× (e.g. mutate a record,
        award points, refresh). ``Store.async_delay_save`` coalesces all of them
        into one disk write after a short delay, instead of serialising the whole
        ``_data`` blob each time. HA flushes any pending delayed write on
        shutdown; ``async_shutdown`` also forces a flush via ``async_save_now``.
        Use ``async_save_now`` when an immediate on-disk write is required.
        """
        # Bump synchronously, before any await: a mutation method calls this with
        # no interleaving await after touching _data, so the new version is
        # visible the instant anything else (e.g. the 30 s poll) can run.
        self._data_version = getattr(self, "_data_version", 0) + 1
        self._store.async_delay_save(lambda: self._data, _SAVE_DEBOUNCE_SECONDS)

    async def async_save_now(self) -> None:
        """Persist data immediately, bypassing the debounce (shutdown/flush)."""
        self._data_version = getattr(self, "_data_version", 0) + 1
        await self._store.async_save(self._data)

    @property
    def data_version(self) -> int:
        """Monotonic version of the in-memory data; bumped on each save."""
        return getattr(self, "_data_version", 0)

    @property
    def data(self) -> dict[str, Any]:
        """Return current data."""
        return self._data

    # Children management
    def get_children(self) -> list[Child]:
        """Get all children."""
        return [Child.from_dict(c) for c in self._data.get("children", [])]

    def get_child(self, child_id: str) -> Child | None:
        """Get a child by ID."""
        for child_data in self._data.get("children", []):
            if child_data.get("id") == child_id:
                return Child.from_dict(child_data)
        return None

    def add_child(self, child: Child) -> None:
        """Add a child."""
        if "children" not in self._data:
            self._data["children"] = []
        self._data["children"].append(child.to_dict())

    def update_child(self, child: Child) -> None:
        """Update a child."""
        children = self._data.get("children", [])
        for i, c in enumerate(children):
            if c.get("id") == child.id:
                children[i] = child.to_dict()
                return
        # If not found, add it
        self.add_child(child)

    def remove_child(self, child_id: str) -> None:
        """Remove a child and cascade-delete their awarded badges."""
        self._data["children"] = [
            c for c in self._data.get("children", []) if c.get("id") != child_id
        ]
        self.remove_awards_for_child(child_id)

    # Chores management
    def get_chores(self) -> list[Chore]:
        """Get all chores."""
        return [Chore.from_dict(c) for c in self._data.get("chores", [])]

    def get_chore(self, chore_id: str) -> Chore | None:
        """Get a chore by ID."""
        for chore_data in self._data.get("chores", []):
            if chore_data.get("id") == chore_id:
                return Chore.from_dict(chore_data)
        return None

    def add_chore(self, chore: Chore) -> None:
        """Add a chore."""
        if "chores" not in self._data:
            self._data["chores"] = []
        self._data["chores"].append(chore.to_dict())

    def update_chore(self, chore: Chore) -> None:
        """Update a chore."""
        chores = self._data.get("chores", [])
        for i, c in enumerate(chores):
            if c.get("id") == chore.id:
                chores[i] = chore.to_dict()
                return
        self.add_chore(chore)

    def remove_chore(self, chore_id: str) -> None:
        """Remove a chore."""
        self._data["chores"] = [
            c for c in self._data.get("chores", []) if c.get("id") != chore_id
        ]
        order = self._data.get("chore_display_order", [])
        if chore_id in order:
            order.remove(chore_id)

    def get_chore_display_order(self) -> list[str]:
        """Get the global chore display order."""
        return list(self._data.get("chore_display_order", []))

    def set_chore_display_order(self, order: list[str]) -> None:
        """Set the global chore display order."""
        self._data["chore_display_order"] = list(order)

    # Rewards management
    def get_rewards(self) -> list[Reward]:
        """Get all rewards."""
        return [Reward.from_dict(r) for r in self._data.get("rewards", [])]

    def get_reward(self, reward_id: str) -> Reward | None:
        """Get a reward by ID."""
        for reward_data in self._data.get("rewards", []):
            if reward_data.get("id") == reward_id:
                return Reward.from_dict(reward_data)
        return None

    def add_reward(self, reward: Reward) -> None:
        """Add a reward."""
        if "rewards" not in self._data:
            self._data["rewards"] = []
        self._data["rewards"].append(reward.to_dict())

    def update_reward(self, reward: Reward) -> None:
        """Update a reward."""
        rewards = self._data.get("rewards", [])
        for i, r in enumerate(rewards):
            if r.get("id") == reward.id:
                rewards[i] = reward.to_dict()
                return
        self.add_reward(reward)

    def remove_reward(self, reward_id: str) -> None:
        """Remove a reward."""
        self._data["rewards"] = [
            r for r in self._data.get("rewards", []) if r.get("id") != reward_id
        ]

    # Completions management
    def get_completions(self) -> list[ChoreCompletion]:
        """Get all chore completions."""
        return [ChoreCompletion.from_dict(c) for c in self._data.get("completions", [])]

    def get_pending_completions(self) -> list[ChoreCompletion]:
        """Get pending (unapproved) completions."""
        return [c for c in self.get_completions() if not c.approved]

    def add_completion(self, completion: ChoreCompletion) -> None:
        """Add a completion record."""
        if "completions" not in self._data:
            self._data["completions"] = []
        self._data["completions"].append(completion.to_dict())

    def update_completion(self, completion: ChoreCompletion) -> None:
        """Update a completion record."""
        completions = self._data.get("completions", [])
        for i, c in enumerate(completions):
            if c.get("id") == completion.id:
                completions[i] = completion.to_dict()
                return
        _LOGGER.warning(
            "update_completion: completion %s not found (possibly pruned mid-update)",
            completion.id,
        )

    def remove_completion(self, completion_id: str) -> None:
        """Remove a completion record."""
        self._data["completions"] = [
            c for c in self._data.get("completions", []) if c.get("id") != completion_id
        ]

    # Mandatory-miss management (#532)
    def get_mandatory_misses(self) -> list[MandatoryMiss]:
        """Get all pending mandatory-miss review items."""
        return [MandatoryMiss.from_dict(m) for m in self._data.get("mandatory_misses", [])]

    def add_mandatory_miss(self, miss: MandatoryMiss) -> None:
        """Add a mandatory-miss item."""
        self._data.setdefault("mandatory_misses", []).append(miss.to_dict())

    def update_mandatory_miss(self, miss: MandatoryMiss) -> None:
        """Replace a mandatory-miss item by id."""
        items = self._data.get("mandatory_misses", [])
        for i, m in enumerate(items):
            if m.get("id") == miss.id:
                items[i] = miss.to_dict()
                return

    def remove_mandatory_miss(self, miss_id: str) -> None:
        """Remove a mandatory-miss item by id."""
        self._data["mandatory_misses"] = [
            m for m in self._data.get("mandatory_misses", []) if m.get("id") != miss_id
        ]

    def replace_mandatory_misses(self, misses: list[MandatoryMiss]) -> None:
        """Replace the whole mandatory-miss collection."""
        self._data["mandatory_misses"] = [m.to_dict() for m in misses]

    # Reward claims management
    def get_reward_claims(self) -> list[RewardClaim]:
        """Get all reward claims."""
        return [RewardClaim.from_dict(r) for r in self._data.get("reward_claims", [])]

    def get_pending_reward_claims(self) -> list[RewardClaim]:
        """Get pending (unapproved) reward claims."""
        return [c for c in self.get_reward_claims() if not c.approved]

    def add_reward_claim(self, claim: RewardClaim) -> None:
        """Add a reward claim."""
        if "reward_claims" not in self._data:
            self._data["reward_claims"] = []
        self._data["reward_claims"].append(claim.to_dict())

    def update_reward_claim(self, claim: RewardClaim) -> None:
        """Update a reward claim."""
        claims = self._data.get("reward_claims", [])
        for i, c in enumerate(claims):
            if c.get("id") == claim.id:
                claims[i] = claim.to_dict()
                return
        _LOGGER.warning(
            "update_reward_claim: claim %s not found (possibly removed mid-update)",
            claim.id,
        )

    def remove_reward_claim(self, claim_id: str) -> None:
        """Remove a reward claim."""
        self._data["reward_claims"] = [
            c for c in self._data.get("reward_claims", []) if c.get("id") != claim_id
        ]

    # Penalties management
    def get_penalties(self) -> list[Penalty]:
        """Get all penalties."""
        return [Penalty.from_dict(p) for p in self._data.get("penalties", [])]

    def get_penalty(self, penalty_id: str) -> Penalty | None:
        """Get a penalty by ID."""
        for p in self._data.get("penalties", []):
            if p.get("id") == penalty_id:
                return Penalty.from_dict(p)
        return None

    def add_penalty(self, penalty) -> None:
        """Add a new penalty."""
        self._data.setdefault("penalties", []).append(penalty.to_dict())

    def update_penalty(self, penalty) -> None:
        """Update an existing penalty."""
        penalties = self._data.get("penalties", [])
        for i, p in enumerate(penalties):
            if p.get("id") == penalty.id:
                penalties[i] = penalty.to_dict()
                return
        penalties.append(penalty.to_dict())

    def remove_penalty(self, penalty_id: str) -> None:
        """Remove a penalty."""
        self._data["penalties"] = [
            p for p in self._data.get("penalties", []) if p.get("id") != penalty_id
        ]

    # Bonuses management
    def get_bonuses(self) -> list[Bonus]:
        """Get all bonuses."""
        return [Bonus.from_dict(b) for b in self._data.get("bonuses", [])]

    def get_bonus(self, bonus_id: str) -> Bonus | None:
        """Get a bonus by ID."""
        for b in self._data.get("bonuses", []):
            if b.get("id") == bonus_id:
                return Bonus.from_dict(b)
        return None

    def add_bonus(self, bonus) -> None:
        """Add a new bonus."""
        self._data.setdefault("bonuses", []).append(bonus.to_dict())

    def update_bonus(self, bonus) -> None:
        """Update an existing bonus."""
        bonuses = self._data.get("bonuses", [])
        for i, b in enumerate(bonuses):
            if b.get("id") == bonus.id:
                bonuses[i] = bonus.to_dict()
                return
        bonuses.append(bonus.to_dict())

    def remove_bonus(self, bonus_id: str) -> None:
        """Remove a bonus."""
        self._data["bonuses"] = [
            b for b in self._data.get("bonuses", []) if b.get("id") != bonus_id
        ]

    # Badges management
    def get_badges(self) -> list[Badge]:
        """Get all badges."""
        return [Badge.from_dict(b) for b in self._data.get("badges", [])]

    def get_badge(self, badge_id: str) -> Badge | None:
        """Get a badge by ID."""
        for b in self._data.get("badges", []):
            if b.get("id") == badge_id:
                return Badge.from_dict(b)
        return None

    def add_badge(self, badge: Badge) -> None:
        """Add a new badge."""
        self._data.setdefault("badges", []).append(badge.to_dict())

    def update_badge(self, badge: Badge) -> None:
        """Update an existing badge."""
        badges = self._data.get("badges", [])
        for i, b in enumerate(badges):
            if b.get("id") == badge.id:
                badges[i] = badge.to_dict()
                return
        badges.append(badge.to_dict())

    def remove_badge(self, badge_id: str) -> None:
        """Remove a badge and cascade-delete its awards."""
        self._data["badges"] = [
            b for b in self._data.get("badges", []) if b.get("id") != badge_id
        ]
        self.remove_awards_for_badge(badge_id)

    # Awarded badges management
    def get_awarded_badges(self) -> list[AwardedBadge]:
        """Get all awarded badges."""
        return [AwardedBadge.from_dict(a) for a in self._data.get("awarded_badges", [])]

    def get_awarded_badges_for_child(self, child_id: str) -> list[AwardedBadge]:
        """Get awarded badges for a specific child."""
        return [a for a in self.get_awarded_badges() if a.child_id == child_id]

    def add_awarded_badge(self, awarded: AwardedBadge) -> None:
        """Add an awarded-badge record."""
        self._data.setdefault("awarded_badges", []).append(awarded.to_dict())

    def remove_awarded_badge(self, awarded_id: str) -> None:
        """Remove an awarded-badge record by id."""
        self._data["awarded_badges"] = [
            a for a in self._data.get("awarded_badges", []) if a.get("id") != awarded_id
        ]

    def remove_awards_for_badge(self, badge_id: str) -> None:
        """Cascade-delete all awards referencing a badge id."""
        self._data["awarded_badges"] = [
            a for a in self._data.get("awarded_badges", []) if a.get("badge_id") != badge_id
        ]

    def remove_awards_for_child(self, child_id: str) -> None:
        """Cascade-delete all awards for a child id."""
        self._data["awarded_badges"] = [
            a for a in self._data.get("awarded_badges", []) if a.get("child_id") != child_id
        ]

    def has_awarded(self, child_id: str, badge_id: str) -> bool:
        """Check whether the child has already earned this badge."""
        for a in self._data.get("awarded_badges", []):
            if a.get("child_id") == child_id and a.get("badge_id") == badge_id:
                return True
        return False

    def _seed_builtin_badges(self, *, is_fresh: bool) -> None:
        """Seed the built-in badge catalogue.

        On fresh install (is_fresh=True): add all built-ins and set the
        backfill_pending flag so existing kid state can be retro-awarded silently.
        On existing install (is_fresh=False): add only built-ins missing from
        storage; preserve parent customisations; do not set backfill flag.
        Idempotent.
        """
        from .coord_badges import BUILTIN_CATALOGUE

        existing = self._data.get("badges", [])
        existing_ids = {b.get("id") for b in existing}

        for builtin in BUILTIN_CATALOGUE:
            if builtin.id not in existing_ids:
                existing.append(builtin.to_dict())

        self._data["badges"] = existing

        if is_fresh:
            self._data["badges_backfill_pending"] = True

    def _run_notifications_migration(self) -> None:
        """Seed parent_recipients + notification_config from legacy notify_service.

        Idempotent: a guard flag is written by the caller in async_load.
        """
        legacy = (self._data.get("settings", {}) or {}).get("notify_service", "")
        parents: list[dict] = []
        existing_parents = self._data.setdefault("parent_recipients", [])
        existing_services = {r.get("notify_service") for r in existing_parents}
        if legacy and legacy not in existing_services:
            seeded = ParentRecipient(name="Parent", notify_service=legacy)
            parents.append(seeded.to_dict())
        existing_parents.extend(parents)

        # Defaults: previously-active types ON (preserves existing behaviour);
        # new types OFF (no surprise pings on upgrade).
        defaults_on = {"pending_chore_approval", "pending_reward_claim", "badge_earned"}
        defaults_off = {"bedtime_reminder", "streak_at_risk", "all_chores_done"}
        nc = self._data.setdefault("notification_config", {})
        seeded_parent_id = parents[0]["id"] if parents else None

        for tid in defaults_on:
            cfg = NotificationConfig(
                type_id=tid,
                master_enabled=True,
                routes={
                    seeded_parent_id: NotificationRoute(enabled=True)
                } if seeded_parent_id else {},
            )
            nc[tid] = cfg.to_dict()

        for tid in defaults_off:
            nc[tid] = NotificationConfig(type_id=tid, master_enabled=False).to_dict()

    # --- parent recipients ---
    def get_parent_recipients(self) -> list[ParentRecipient]:
        return [ParentRecipient.from_dict(d) for d in self._data.get("parent_recipients", [])]

    def upsert_parent_recipient(self, p: ParentRecipient) -> None:
        rows = self._data.setdefault("parent_recipients", [])
        for i, row in enumerate(rows):
            if row.get("id") == p.id:
                rows[i] = p.to_dict()
                return
        rows.append(p.to_dict())

    def delete_parent_recipient(self, parent_id: str) -> None:
        self._data["parent_recipients"] = [
            r for r in self._data.get("parent_recipients", [])
            if r.get("id") != parent_id
        ]

    # --- notification config ---
    def get_notification_config(self, type_id: str) -> NotificationConfig:
        raw = (self._data.get("notification_config", {}) or {}).get(type_id)
        if not raw:
            return NotificationConfig(type_id=type_id)
        return NotificationConfig.from_dict(raw)

    def set_notification_master(self, type_id: str, enabled: bool) -> None:
        cfg = self.get_notification_config(type_id)
        cfg.master_enabled = enabled
        self._data.setdefault("notification_config", {})[type_id] = cfg.to_dict()

    def set_notification_route(
        self, type_id: str, recipient_id: str, route: NotificationRoute
    ) -> None:
        cfg = self.get_notification_config(type_id)
        cfg.routes[recipient_id] = route
        self._data.setdefault("notification_config", {})[type_id] = cfg.to_dict()

    def get_all_notification_configs(self) -> dict[str, NotificationConfig]:
        return {
            tid: NotificationConfig.from_dict(raw)
            for tid, raw in (self._data.get("notification_config", {}) or {}).items()
        }

    # --- custom notifications ---
    def get_custom_notifications(self) -> list[CustomNotification]:
        return [
            CustomNotification.from_dict(d)
            for d in self._data.get("custom_notifications", [])
        ]

    def upsert_custom_notification(self, n: CustomNotification) -> None:
        rows = self._data.setdefault("custom_notifications", [])
        for i, row in enumerate(rows):
            if row.get("id") == n.id:
                rows[i] = n.to_dict()
                return
        rows.append(n.to_dict())

    def delete_custom_notification(self, custom_id: str) -> None:
        self._data["custom_notifications"] = [
            r for r in self._data.get("custom_notifications", [])
            if r.get("id") != custom_id
        ]

    # --- streak-at-risk cutoff ---
    def get_streak_at_risk_cutoff(self) -> str:
        return (self._data.get("settings", {}) or {}).get(
            "streak_at_risk_cutoff_time", "20:00"
        )

    def set_streak_at_risk_cutoff(self, hhmm: str) -> None:
        self._data.setdefault("settings", {})["streak_at_risk_cutoff_time"] = hhmm

    # --- mandatory reminder escalation (FEAT-6) ---
    def get_escalation_reminder_minutes(self) -> int:
        """Minutes after a mandatory miss before the child reminder escalates."""
        try:
            return max(1, int((self._data.get("settings", {}) or {}).get(
                "mandatory_escalation_reminder_minutes", 30)))
        except (TypeError, ValueError):
            return 30

    def get_escalation_parent_minutes(self) -> int:
        """Minutes after a mandatory miss before the parent alert escalates."""
        try:
            return max(1, int((self._data.get("settings", {}) or {}).get(
                "mandatory_escalation_parent_minutes", 120)))
        except (TypeError, ValueError):
            return 120

    def set_escalation_minutes(self, reminder_minutes: int, parent_minutes: int) -> None:
        s = self._data.setdefault("settings", {})
        s["mandatory_escalation_reminder_minutes"] = max(1, int(reminder_minutes))
        s["mandatory_escalation_parent_minutes"] = max(1, int(parent_minutes))

    # Task groups management
    def get_task_groups(self) -> list[TaskGroup]:
        """Get all task groups."""
        return [TaskGroup.from_dict(g) for g in self._data.get("task_groups", [])]

    def get_task_group(self, group_id: str) -> TaskGroup | None:
        """Get a task group by ID."""
        for g in self._data.get("task_groups", []):
            if g.get("id") == group_id:
                return TaskGroup.from_dict(g)
        return None

    def get_task_group_for_chore(self, chore_id: str) -> TaskGroup | None:
        """Return the group that contains this chore, or None."""
        for g in self._data.get("task_groups", []):
            if chore_id in g.get("chore_ids", []):
                return TaskGroup.from_dict(g)
        return None

    def add_task_group(self, group: TaskGroup) -> None:
        """Add a task group."""
        self._data.setdefault("task_groups", []).append(group.to_dict())

    def update_task_group(self, group: TaskGroup) -> None:
        """Update an existing task group."""
        groups = self._data.get("task_groups", [])
        for i, g in enumerate(groups):
            if g.get("id") == group.id:
                groups[i] = group.to_dict()
                return
        groups.append(group.to_dict())

    def remove_task_group(self, group_id: str) -> None:
        """Remove a task group."""
        self._data["task_groups"] = [
            g for g in self._data.get("task_groups", []) if g.get("id") != group_id
        ]

    def remove_chore_from_task_groups(self, chore_id: str) -> None:
        """Strip a chore ID from every group (used on chore delete)."""
        for g in self._data.get("task_groups", []):
            if chore_id in g.get("chore_ids", []):
                g["chore_ids"] = [c for c in g["chore_ids"] if c != chore_id]

    # Points transactions management
    def get_points_transactions(self) -> list[PointsTransaction]:
        """Get all points transactions."""
        return [PointsTransaction.from_dict(t) for t in self._data.get("points_transactions", [])]

    def add_points_transaction(self, transaction: PointsTransaction) -> None:
        """Add a points transaction record."""
        if "points_transactions" not in self._data:
            self._data["points_transactions"] = []
        self._data["points_transactions"].append(transaction.to_dict())

        # Keep only the last 200 transactions to avoid unbounded storage growth
        if len(self._data["points_transactions"]) > 200:
            self._data["points_transactions"] = self._data["points_transactions"][-200:]

    def remove_points_transaction(self, transaction_id: str) -> bool:
        """Remove a points transaction by id. Returns True if one was removed."""
        txns = self._data.get("points_transactions", [])
        for i, t in enumerate(txns):
            if t.get("id") == transaction_id:
                del txns[i]
                return True
        return False

    # ── Admin audit log ──────────────────────────────────────────────────
    def get_audit_log(self) -> list[dict]:
        """Return admin audit entries, newest first."""
        return list(reversed(self._data.get("audit_log", [])))

    def add_audit_entry(self, entry: dict) -> None:
        """Append an admin audit entry, capping the log at 500 (oldest dropped)."""
        log = self._data.setdefault("audit_log", [])
        log.append(entry)
        if len(log) > 500:
            del log[:-500]

    def clear_audit_log(self) -> None:
        """Remove all audit entries."""
        self._data["audit_log"] = []

    # ── Chore swap requests ──────────────────────────────────────────────
    def get_swap_requests(self) -> list[dict]:
        return list(self._data.get("swap_requests", []))

    def add_swap_request(self, req: dict) -> None:
        self._data.setdefault("swap_requests", []).append(req)

    def update_swap_request(self, req_id: str, **changes) -> bool:
        for r in self._data.get("swap_requests", []):
            if r.get("id") == req_id:
                r.update(changes)
                return True
        return False

    def remove_swap_request(self, req_id: str) -> bool:
        reqs = self._data.get("swap_requests", [])
        for i, r in enumerate(reqs):
            if r.get("id") == req_id:
                del reqs[i]
                return True
        return False

    # ── Quests (chore chains) ────────────────────────────────────────────
    def get_quests(self) -> list[Quest]:
        return [Quest.from_dict(q) for q in self._data.get("quests", [])]

    def get_quest(self, quest_id: str) -> Quest | None:
        for q in self._data.get("quests", []):
            if q.get("id") == quest_id:
                return Quest.from_dict(q)
        return None

    def add_quest(self, quest: Quest) -> None:
        self._data.setdefault("quests", []).append(quest.to_dict())

    def update_quest(self, quest: Quest) -> None:
        quests = self._data.get("quests", [])
        for i, q in enumerate(quests):
            if q.get("id") == quest.id:
                quests[i] = quest.to_dict()
                return
        self.add_quest(quest)

    def remove_quest(self, quest_id: str) -> None:
        self._data["quests"] = [
            q for q in self._data.get("quests", []) if q.get("id") != quest_id
        ]
        # Drop any progress tracked for this quest
        prog = self._data.get("quest_progress", {})
        prog.pop(quest_id, None)

    def get_quest_progress(self) -> dict:
        """All quest progress: {quest_id: {child_id: {step, completed_count, last_completed}}}."""
        return self._data.setdefault("quest_progress", {})

    def get_quest_child_progress(self, quest_id: str, child_id: str) -> dict:
        return self.get_quest_progress().setdefault(quest_id, {}).get(child_id, {})

    def set_quest_child_progress(self, quest_id: str, child_id: str, progress: dict) -> None:
        self.get_quest_progress().setdefault(quest_id, {})[child_id] = progress

    def remove_quest_progress_for_child(self, child_id: str) -> None:
        for child_map in self.get_quest_progress().values():
            child_map.pop(child_id, None)

    # ── Challenges (daily / weekly) ──────────────────────────────────────
    def get_challenges(self) -> list[Challenge]:
        return [Challenge.from_dict(c) for c in self._data.get("challenges", [])]

    def get_challenge(self, challenge_id: str) -> Challenge | None:
        for c in self._data.get("challenges", []):
            if c.get("id") == challenge_id:
                return Challenge.from_dict(c)
        return None

    def add_challenge(self, challenge: Challenge) -> None:
        self._data.setdefault("challenges", []).append(challenge.to_dict())

    def update_challenge(self, challenge: Challenge) -> None:
        items = self._data.get("challenges", [])
        for i, c in enumerate(items):
            if c.get("id") == challenge.id:
                items[i] = challenge.to_dict()
                return
        self.add_challenge(challenge)

    def remove_challenge(self, challenge_id: str) -> None:
        self._data["challenges"] = [
            c for c in self._data.get("challenges", []) if c.get("id") != challenge_id
        ]
        self._data.get("challenge_progress", {}).pop(challenge_id, None)

    def get_challenge_progress(self) -> dict:
        """All challenge progress: {challenge_id: {child_id: {period, awarded}}}."""
        return self._data.setdefault("challenge_progress", {})

    def get_challenge_child_progress(self, challenge_id: str, child_id: str) -> dict:
        return self.get_challenge_progress().setdefault(challenge_id, {}).get(child_id, {})

    def set_challenge_child_progress(self, challenge_id: str, child_id: str, progress: dict) -> None:
        self.get_challenge_progress().setdefault(challenge_id, {})[child_id] = progress

    def remove_challenge_progress_for_child(self, child_id: str) -> None:
        for child_map in self.get_challenge_progress().values():
            child_map.pop(child_id, None)

    # ── Backup / restore ─────────────────────────────────────────────────
    def export_data(self) -> dict:
        """Return a deep copy of the full stored data (for backup/export)."""
        import copy
        return copy.deepcopy(self._data)

    def import_data(self, data: dict) -> None:
        """Replace all stored data with ``data`` (restore from a backup).

        Core collection keys are ensured so downstream readers never KeyError on
        a partial import.
        """
        import copy
        if not isinstance(data, dict):
            raise ValueError("import data must be an object")
        self._data = copy.deepcopy(data)
        list_keys = (
            "children", "chores", "rewards", "penalties", "bonuses",
            "task_groups", "completions", "mandatory_misses", "reward_claims", "points_transactions",
            "pool_allocations", "badges", "awarded_badges", "parent_recipients",
            "audit_log", "timed_sessions", "quests", "challenges",
        )
        for k in list_keys:
            if not isinstance(self._data.get(k), list):
                self._data[k] = []
        if not isinstance(self._data.get("settings"), dict):
            self._data["settings"] = {}
        if not isinstance(self._data.get("quest_progress"), dict):
            self._data["quest_progress"] = {}
        if not isinstance(self._data.get("challenge_progress"), dict):
            self._data["challenge_progress"] = {}
        self._sanitize_imported_records()

    def _sanitize_imported_records(self) -> None:
        """Re-validate untrusted inner records after a full-replace import (SEC-5).

        ``import_data`` deep-copies the payload in with only top-level coercion,
        so a crafted backup could smuggle a ``photo_url`` that bypasses the
        ``is_taskmate_photo_url`` gate enforced at the ``complete_chore``
        boundary. Strip any completion ``photo_url`` that isn't one of our own
        well-formed photo URLs so the panel never renders a foreign/dangerous one.
        """
        from .photos import is_taskmate_photo_url
        for comp in self._data.get("completions", []):
            if not isinstance(comp, dict):
                continue
            url = comp.get("photo_url")
            if url and not is_taskmate_photo_url(url):
                _LOGGER.warning(
                    "Import: dropped non-TaskMate photo_url on completion %s",
                    comp.get("id", "?"),
                )
                comp["photo_url"] = ""

    def replace_completions(self, completions: list[ChoreCompletion]) -> None:
        """Replace all completions with the given list."""
        self._data["completions"] = [c.to_dict() for c in completions]

    def remove_completions_for_child(self, child_id: str) -> None:
        """Remove all completions for a given child."""
        self._data["completions"] = [
            c for c in self._data.get("completions", []) if c.get("child_id") != child_id
        ]

    def remove_completions_for_chore(self, chore_id: str) -> None:
        """Remove all completions for a given chore."""
        self._data["completions"] = [
            c for c in self._data.get("completions", []) if c.get("chore_id") != chore_id
        ]

    def remove_reward_claims_for_child(self, child_id: str) -> None:
        """Remove all reward claims for a given child."""
        self._data["reward_claims"] = [
            c for c in self._data.get("reward_claims", []) if c.get("child_id") != child_id
        ]

    def remove_reward_claims_for_reward(self, reward_id: str) -> None:
        """Remove all reward claims for a given reward."""
        self._data["reward_claims"] = [
            c for c in self._data.get("reward_claims", []) if c.get("reward_id") != reward_id
        ]

    # Pool allocations management (v3.0 pool mode)
    def get_pool_allocations(self) -> list[PoolAllocation]:
        """Get all pool allocations."""
        return [PoolAllocation.from_dict(a) for a in self._data.get("pool_allocations", [])]

    def get_pool_allocation(self, child_id: str, reward_id: str) -> PoolAllocation | None:
        """Get a pool allocation for a specific (child, reward) pair."""
        for a in self._data.get("pool_allocations", []):
            if a.get("child_id") == child_id and a.get("reward_id") == reward_id:
                return PoolAllocation.from_dict(a)
        return None

    def upsert_pool_allocation(self, allocation: PoolAllocation) -> None:
        """Insert or update a pool allocation (keyed by child_id + reward_id)."""
        allocations = self._data.setdefault("pool_allocations", [])
        for i, a in enumerate(allocations):
            if a.get("child_id") == allocation.child_id and a.get("reward_id") == allocation.reward_id:
                allocations[i] = allocation.to_dict()
                return
        allocations.append(allocation.to_dict())

    def remove_pool_allocation(self, child_id: str, reward_id: str) -> None:
        """Remove a pool allocation for a specific (child, reward) pair."""
        self._data["pool_allocations"] = [
            a for a in self._data.get("pool_allocations", [])
            if not (a.get("child_id") == child_id and a.get("reward_id") == reward_id)
        ]

    def remove_pool_allocations_for_child(self, child_id: str) -> None:
        """Remove all pool allocations for a given child."""
        self._data["pool_allocations"] = [
            a for a in self._data.get("pool_allocations", []) if a.get("child_id") != child_id
        ]

    def remove_pool_allocations_for_reward(self, reward_id: str) -> None:
        """Remove all pool allocations for a given reward."""
        self._data["pool_allocations"] = [
            a for a in self._data.get("pool_allocations", []) if a.get("reward_id") != reward_id
        ]

    def get_total_allocated_for_child(self, child_id: str) -> int:
        """Return the sum of this child's allocations across all rewards."""
        return sum(
            a.get("allocated_points", 0)
            for a in self._data.get("pool_allocations", [])
            if a.get("child_id") == child_id
        )

    def get_total_allocated_for_reward(self, reward_id: str) -> int:
        """Return the sum of all children's allocations for a specific reward (used for jackpots)."""
        return sum(
            a.get("allocated_points", 0)
            for a in self._data.get("pool_allocations", [])
            if a.get("reward_id") == reward_id
        )

    def remove_transactions_for_child(self, child_id: str) -> None:
        """Remove all points transactions for a given child."""
        self._data["points_transactions"] = [
            t for t in self._data.get("points_transactions", []) if t.get("child_id") != child_id
        ]

    def remove_last_completed_for_child(self, child_id: str) -> None:
        """Remove all last_completed records for a given child."""
        lc = self._data.get("last_completed", {})
        for chore_id in list(lc.keys()):
            lc[chore_id].pop(child_id, None)
            if not lc[chore_id]:
                del lc[chore_id]

    def remove_last_completed_for_chore(self, chore_id: str) -> None:
        """Remove last_completed records for a given chore."""
        self._data.get("last_completed", {}).pop(chore_id, None)

    # Last completed store — used for recurrence window checks
    def get_last_completed(self, chore_id: str, child_id: str) -> dict:
        """Get last_completed record for a chore/child pair.

        Returns dict with 'current' and 'previous' ISO datetime strings,
        or empty dict if never completed.
        """
        return self._data.get("last_completed", {}).get(chore_id, {}).get(child_id, {})

    def set_last_completed(self, chore_id: str, child_id: str, completed_at_iso: str) -> None:
        """Record a new completion — shifts current to previous."""
        if "last_completed" not in self._data:
            self._data["last_completed"] = {}
        if chore_id not in self._data["last_completed"]:
            self._data["last_completed"][chore_id] = {}

        existing = self._data["last_completed"][chore_id].get(child_id, {})
        current = existing.get("current")

        self._data["last_completed"][chore_id][child_id] = {
            "current": completed_at_iso,
            "previous": current,  # may be None
        }

    def undo_last_completed(self, chore_id: str, child_id: str) -> None:
        """Undo the most recent completion — restores previous as current."""
        record = self._data.get("last_completed", {}).get(chore_id, {}).get(child_id)
        if not record:
            return

        previous = record.get("previous")
        if previous:
            self._data["last_completed"][chore_id][child_id] = {
                "current": previous,
                "previous": None,
            }
        else:
            # No previous — remove the record entirely
            del self._data["last_completed"][chore_id][child_id]
            if not self._data["last_completed"][chore_id]:
                del self._data["last_completed"][chore_id]

    # Timed sessions management
    def get_timed_sessions(self) -> list[TimedSession]:
        """Get all timed sessions."""
        return [TimedSession.from_dict(s) for s in self._data.get("timed_sessions", [])]

    def get_timed_session(self, chore_id: str, child_id: str, session_date: str) -> TimedSession | None:
        """Get a timed session for a specific chore/child/date."""
        for s in self._data.get("timed_sessions", []):
            if (s.get("chore_id") == chore_id
                    and s.get("child_id") == child_id
                    and s.get("session_date") == session_date):
                return TimedSession.from_dict(s)
        return None

    def get_active_timed_session(self, chore_id: str, child_id: str) -> TimedSession | None:
        """Get a running or paused session for a chore/child pair."""
        for s in self._data.get("timed_sessions", []):
            if (s.get("chore_id") == chore_id
                    and s.get("child_id") == child_id
                    and s.get("state") in ("running", "paused")):
                return TimedSession.from_dict(s)
        return None

    def save_timed_session(self, session: TimedSession) -> None:
        """Insert or update a timed session."""
        sessions = self._data.setdefault("timed_sessions", [])
        for i, s in enumerate(sessions):
            if s.get("id") == session.id:
                sessions[i] = session.to_dict()
                return
        sessions.append(session.to_dict())

    def remove_timed_session(self, session_id: str) -> None:
        """Remove a timed session."""
        self._data["timed_sessions"] = [
            s for s in self._data.get("timed_sessions", [])
            if s.get("id") != session_id
        ]

    # Generic settings
    def get_setting(self, key: str, default: Any = "") -> Any:
        """Get a generic setting value (may be a bool/number/list, not just str)."""
        return self._data.get("settings", {}).get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Set a generic setting value."""
        if "settings" not in self._data:
            self._data["settings"] = {}
        self._data["settings"][key] = value

    def get_settings(self) -> dict[str, Any]:
        """The whole settings dict (live reference; callers must not assume a copy)."""
        return self._data.get("settings", {}) or {}

    # ── Typed top-level flags (ARCH-1) ────────────────────────────────────
    # These live at the root of _data (not under "settings"). Accessors keep the
    # key names + defaults in one place so setup/migration logic can't drift.
    def is_initial_setup_done(self) -> bool:
        return bool(self._data.get("_initial_setup_done"))

    def mark_initial_setup_done(self) -> None:
        self._data["_initial_setup_done"] = True

    def is_badges_backfill_pending(self) -> bool:
        return bool(self._data.get("badges_backfill_pending"))

    def clear_badges_backfill_pending(self) -> None:
        self._data.pop("badges_backfill_pending", None)

    # Settings
    def get_points_name(self) -> str:
        """Get the points currency name."""
        return self._data.get("points_name", "Stars")

    def set_points_name(self, name: str) -> None:
        """Set the points currency name."""
        self._data["points_name"] = name

    def get_points_icon(self) -> str:
        """Get the points icon."""
        return self._data.get("points_icon", "mdi:star")

    def set_points_icon(self, icon: str) -> None:
        """Set the points icon."""
        self._data["points_icon"] = icon

    # Career score history management
    def get_career_score_history(self, child_id: str) -> list[dict]:
        """Get career score history for a child."""
        return list(self._data.get("career_score_history", {}).get(child_id, []))

    def append_career_score_snapshot(self, child_id: str, date_str: str, score: int) -> None:
        """Upsert a daily career score snapshot for a child.

        If an entry for the given date already exists, its score is updated
        (last-write-wins).  Entries older than 90 days are pruned.
        """
        history = self._data.setdefault("career_score_history", {})
        entries = history.setdefault(child_id, [])

        # Upsert: update existing date or append
        for entry in entries:
            if entry.get("date") == date_str:
                entry["score"] = score
                break
        else:
            entries.append({"date": date_str, "score": score})

        # Prune entries older than 90 days
        cutoff = (date.today() - timedelta(days=90)).isoformat()
        history[child_id] = [e for e in entries if e.get("date", "") >= cutoff]

    def remove_career_score_history_for_child(self, child_id: str) -> None:
        """Remove all career score history for a child."""
        history = self._data.get("career_score_history", {})
        history.pop(child_id, None)

    def prune_all_done_flags(self, keep_date: str) -> None:
        """Drop all-chores-done flags for dates other than keep_date.

        Keys are "all_done_<child_id>_<isodate>".
        """
        flags = self._data.get("all_done_flags", {})
        for key in list(flags):
            if not key.endswith(keep_date):
                flags.pop(key, None)

    # Template management
    def get_custom_templates(self) -> list[dict]:
        """Get all custom (user-created) templates."""
        return list(self._data.get("templates", []))

    def get_custom_template(self, template_id: str) -> dict | None:
        """Get a single custom template by ID."""
        for tpl in self._data.get("templates", []):
            if tpl.get("id") == template_id:
                return dict(tpl)
        return None

    def add_custom_template(self, template: dict) -> None:
        """Add a custom template."""
        if "templates" not in self._data:
            self._data["templates"] = []
        self._data["templates"].append(template)

    def update_custom_template(self, template_id: str, updates: dict) -> None:
        """Update a custom template's fields."""
        templates = self._data.get("templates", [])
        for tpl in templates:
            if tpl.get("id") == template_id:
                tpl.update(updates)
                return
        raise ValueError(f"Template {template_id} not found")

    def remove_custom_template(self, template_id: str) -> None:
        """Remove a custom template."""
        templates = self._data.get("templates", [])
        original_len = len(templates)
        self._data["templates"] = [t for t in templates if t.get("id") != template_id]
        if len(self._data["templates"]) == original_len:
            raise ValueError(f"Template {template_id} not found")
