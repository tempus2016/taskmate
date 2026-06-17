"""Data models for TaskMate integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

_LOGGER = logging.getLogger(__name__)


def generate_id() -> str:
    """Generate a unique ID.

    Returns the first 16 hex chars of a UUID4 (64 bits). Short enough to
    use in dotted HA keys and service-call payloads without being unwieldy;
    still provides ~1.8e19 values, far more than the entities a household
    will ever create.
    """
    return str(uuid.uuid4()).replace("-", "")[:16]


def parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse a datetime value, ensuring timezone awareness.

    If the datetime is naive (no timezone info), assume UTC for backward
    compatibility. All newly stored datetimes include timezone info via
    format_datetime(), so naive values only appear in legacy data.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except (ValueError, TypeError):
            _LOGGER.warning("Could not parse stored datetime %r", value)
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    return None


def format_datetime(dt: datetime | None) -> str | None:
    """Format a datetime as ISO string with timezone info.

    Converts to UTC before formatting to ensure consistency.
    """
    if dt is None:
        return None
    # Ensure we have timezone info
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Convert to UTC and format with 'Z' suffix for clarity
    utc_dt = dt.astimezone(timezone.utc)
    # Use isoformat but replace +00:00 with Z for cleaner output
    return utc_dt.isoformat().replace("+00:00", "Z")


@dataclass
class TimedSession:
    """Tracks an active or paused timed-task session."""

    chore_id: str
    child_id: str
    state: str = "stopped"  # "running" | "paused" | "stopped"
    segments: list[dict[str, Any]] = field(default_factory=list)
    total_seconds_today: int = 0
    session_date: str = ""  # ISO date this session belongs to
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimedSession":
        return cls(
            chore_id=data.get("chore_id", ""),
            child_id=data.get("child_id", ""),
            state=data.get("state", "stopped"),
            segments=list(data.get("segments", [])),
            total_seconds_today=data.get("total_seconds_today", 0),
            session_date=data.get("session_date", ""),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "chore_id": self.chore_id,
            "child_id": self.child_id,
            "state": self.state,
            "segments": self.segments,
            "total_seconds_today": self.total_seconds_today,
            "session_date": self.session_date,
            "id": self.id,
        }


@dataclass
class BonusSubTask:
    """An optional bonus sub-task embedded within a parent chore."""

    name: str
    points: int = 5
    description: str = ""
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BonusSubTask:
        return cls(
            name=data.get("name", ""),
            points=data.get("points", 5),
            description=data.get("description", ""),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "points": self.points,
            "description": self.description,
            "id": self.id,
        }


@dataclass
class Child:
    """Represents a child."""

    name: str
    avatar: str = "mdi:account-circle"
    points: int = 0
    total_points_earned: int = 0
    total_chores_completed: int = 0
    current_streak: int = 0
    best_streak: int = 0
    pending_rewards: list[str] = field(default_factory=list)
    chore_order: list[str] = field(default_factory=list)  # Custom chore ordering for this child
    last_completion_date: str | None = None  # ISO date string of last chore completion (for streak tracking)
    streak_paused: bool = False  # True if streak is paused due to missed day (pause mode)
    streak_milestones_achieved: list[int] = field(default_factory=list)
    awarded_perfect_weeks: list[str] = field(default_factory=list)
    availability_entity: str = ""  # HA entity id; empty = always available
    availability_inverted: bool = False  # When True, _AVAILABLE_STATES means UNAVAILABLE
    unavailability_entity: str = ""  # Second HA entity; _AVAILABLE_STATES = child is busy
    career_score: int = 0
    total_penalties_received: int = 0
    notify_service: str | None = None
    linked_user_id: str = ""  # HA user id; when set, only that user (or an admin) may self-serve as this child
    level: int = 1  # cached XP level (derived from total_points_earned)
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Child:
        """Create a Child from a dictionary."""
        return cls(
            name=data.get("name", ""),
            avatar=data.get("avatar", "mdi:account-circle"),
            points=data.get("points", 0),
            total_points_earned=data.get("total_points_earned", 0),
            total_chores_completed=data.get("total_chores_completed", 0),
            current_streak=data.get("current_streak", 0),
            best_streak=data.get("best_streak", 0),
            pending_rewards=list(data.get("pending_rewards", [])),
            chore_order=list(data.get("chore_order", [])),
            last_completion_date=data.get("last_completion_date", None),
            streak_paused=data.get("streak_paused", False),
            streak_milestones_achieved=list(data.get("streak_milestones_achieved", [])),
            awarded_perfect_weeks=list(data.get("awarded_perfect_weeks", [])),
            availability_entity=data.get("availability_entity", ""),
            availability_inverted=data.get("availability_inverted", False),
            unavailability_entity=data.get("unavailability_entity", ""),
            career_score=data.get("career_score", 0),
            total_penalties_received=data.get("total_penalties_received", 0),
            notify_service=data.get("notify_service", None),
            linked_user_id=data.get("linked_user_id", ""),
            level=int(data.get("level", 1) or 1),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "avatar": self.avatar,
            "points": self.points,
            "total_points_earned": self.total_points_earned,
            "total_chores_completed": self.total_chores_completed,
            "current_streak": self.current_streak,
            "best_streak": self.best_streak,
            "pending_rewards": self.pending_rewards,
            "chore_order": self.chore_order,
            "last_completion_date": self.last_completion_date,
            "streak_paused": self.streak_paused,
            "streak_milestones_achieved": self.streak_milestones_achieved,
            "awarded_perfect_weeks": self.awarded_perfect_weeks,
            "availability_entity": self.availability_entity,
            "availability_inverted": self.availability_inverted,
            "unavailability_entity": self.unavailability_entity,
            "career_score": self.career_score,
            "total_penalties_received": self.total_penalties_received,
            "notify_service": self.notify_service,
            "linked_user_id": self.linked_user_id,
            "level": self.level,
            "id": self.id,
        }


@dataclass
class Chore:
    """Represents a chore."""

    name: str
    points: int = 10
    description: str = ""
    assigned_to: list[str] = field(default_factory=list)  # List of child IDs
    requires_approval: bool = True
    time_category: str = "anytime"  # morning, afternoon, evening, night, anytime
    claim_allowance_minutes: int = 0  # Grace minutes past period end during which the chore stays claimable; 0 = no grace. Night chores still cap at midnight.
    daily_limit: int = 1
    completion_sound: str = "coin"  # Sound to play on completion
    difficulty: str = "medium"  # easy | medium | hard — scales awarded points by the tier multiplier (medium = ×1.0 baseline)
    # Scheduling
    # schedule_mode: "specific_days" = show on selected days of week (Mode A)
    #                "recurring"     = rolling window recurrence (Mode B)
    schedule_mode: str = "specific_days"
    due_days: list[str] = field(default_factory=list)  # Mode A: days to show chore
    # Mode B fields
    recurrence: str = "weekly"  # every_2_days | weekly | every_2_weeks | monthly | every_3_months | every_6_months
    recurrence_day: str = ""    # optional: which day of week for weekly/every_2_weeks
    recurrence_start: str = ""  # optional: ISO date anchor for every_2_days
    first_occurrence_mode: str = "available_immediately"  # available_immediately | wait_for_first_occurrence
    # Dynamic visibility
    visibility_entity: str = ""  # optional: entity_id to check for visibility
    visibility_state: str = "on"  # state/value that makes chore visible (e.g. "on", "true", "123")
    visibility_operator: str = "equals"  # equals, gte, lte, gt, lt, not_equals
    # One-shot chore fields
    enabled: bool = True  # False = soft-disabled (completed or expired)
    disabled_for: list[str] = field(default_factory=list)  # Child IDs this chore is disabled for
    created_date: str = ""  # ISO date for one-shot expiry, e.g. "2026-04-16"
    expires_on: str = ""  # optional ISO end date; chore auto-disables the day after
    # Time-of-day incentive: when due_time (HH:MM) is set, a completion at/before
    # it earns +early_bonus, after it loses late_penalty (applied to the award).
    due_time: str = ""
    early_bonus: int = 0
    late_penalty: int = 0
    require_photo: bool = False  # require an evidence photo; forces parent approval
    # Dynamic assignment (sibling rotation)
    assignment_mode: str = "everyone"  # everyone | alternating | random
    assignment_rotation_anchor: str = ""  # ISO date; day-0 of the rotation for alternating
    assignment_current_child_id: str = ""  # cached active child ID for today (computed at midnight and on create/update)
    require_availability: bool = False  # When True, skip children whose availability entity says they're unavailable
    # Skip state (ephemeral: cleared at midnight when skip_date != today)
    skip_date: str = ""  # ISO date the skip applies to ("" = no active skip)
    skip_count: int = 0  # number of times skipped today; added to rotation index
    # Calendar publish: list of HA calendar entity ids to mirror the chore to. Any number supported.
    publish_calendar_entities: list[str] = field(default_factory=list)
    # ISO dates already written to the configured calendars. Used for both
    # idempotence (don't re-publish the same day) and projection cleanup
    # (entries < today are pruned before each publish pass).
    publish_calendar_published_dates: list[str] = field(default_factory=list)
    # Bonus sub-tasks: optional extra-credit tasks that unlock after the parent chore is completed
    bonus_subtasks: list[BonusSubTask] = field(default_factory=list)
    # Timed task fields
    task_type: str = "standard"  # "standard" | "timed"
    timed_rate_points: int = 10  # points awarded per rate window
    timed_rate_minutes: int = 5  # rate window size in minutes
    timed_max_daily_minutes: int = 0  # 0 = unlimited; caps total daily duration
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chore:
        """Create a Chore from a dictionary."""
        # Migration: if old data has due_days set but no schedule_mode,
        # treat as specific_days. Otherwise default to specific_days.
        schedule_mode = data.get("schedule_mode", "specific_days")
        # If old data has due_days but schedule_mode wasn't stored, preserve as specific_days
        if "schedule_mode" not in data and data.get("due_days"):
            schedule_mode = "specific_days"

        return cls(
            name=data.get("name", ""),
            points=data.get("points", 10),
            description=data.get("description", ""),
            assigned_to=list(data.get("assigned_to", [])),
            requires_approval=data.get("requires_approval", True),
            time_category=data.get("time_category", "anytime"),
            claim_allowance_minutes=max(0, int(data.get("claim_allowance_minutes", 0) or 0)),
            daily_limit=data.get("daily_limit", 1),
            completion_sound=data.get("completion_sound", "coin"),
            difficulty=data.get("difficulty", "medium"),
            schedule_mode=schedule_mode,
            due_days=list(data.get("due_days", [])),
            recurrence=data.get("recurrence", "weekly"),
            recurrence_day=data.get("recurrence_day", ""),
            recurrence_start=data.get("recurrence_start", ""),
            first_occurrence_mode=data.get("first_occurrence_mode", "available_immediately"),
            visibility_entity=data.get("visibility_entity", ""),
            visibility_state=data.get("visibility_state", "on"),
            visibility_operator=data.get("visibility_operator", "equals"),
            enabled=data.get("enabled", True),
            disabled_for=list(data.get("disabled_for", [])),
            created_date=data.get("created_date", ""),
            expires_on=data.get("expires_on", ""),
            due_time=data.get("due_time", ""),
            early_bonus=int(data.get("early_bonus", 0) or 0),
            late_penalty=int(data.get("late_penalty", 0) or 0),
            require_photo=data.get("require_photo", False),
            assignment_mode=data.get("assignment_mode", "everyone"),
            assignment_rotation_anchor=data.get("assignment_rotation_anchor", ""),
            assignment_current_child_id=data.get("assignment_current_child_id", ""),
            require_availability=data.get("require_availability", False),
            skip_date=data.get("skip_date", ""),
            skip_count=int(data.get("skip_count", 0) or 0),
            publish_calendar_entities=list(data.get("publish_calendar_entities", [])),
            # Back-compat: old records stored a single ISO date in
            # `publish_calendar_last_date`. Seed the new list with it so we
            # don't immediately republish today on the next tick after upgrade.
            publish_calendar_published_dates=(
                list(data.get("publish_calendar_published_dates", []))
                or ([data["publish_calendar_last_date"]] if data.get("publish_calendar_last_date") else [])
            ),
            bonus_subtasks=[BonusSubTask.from_dict(b) for b in data.get("bonus_subtasks", [])],
            task_type=data.get("task_type", "standard"),
            timed_rate_points=data.get("timed_rate_points", 10),
            timed_rate_minutes=max(1, int(data.get("timed_rate_minutes", 5) or 5)),
            timed_max_daily_minutes=max(0, int(data.get("timed_max_daily_minutes", 0) or 0)),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "points": self.points,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "requires_approval": self.requires_approval,
            "time_category": self.time_category,
            "claim_allowance_minutes": self.claim_allowance_minutes,
            "daily_limit": self.daily_limit,
            "completion_sound": self.completion_sound,
            "difficulty": self.difficulty,
            "schedule_mode": self.schedule_mode,
            "due_days": self.due_days,
            "recurrence": self.recurrence,
            "recurrence_day": self.recurrence_day,
            "recurrence_start": self.recurrence_start,
            "first_occurrence_mode": self.first_occurrence_mode,
            "visibility_entity": self.visibility_entity,
            "visibility_state": self.visibility_state,
            "visibility_operator": self.visibility_operator,
            "enabled": self.enabled,
            "disabled_for": self.disabled_for,
            "created_date": self.created_date,
            "expires_on": self.expires_on,
            "due_time": self.due_time,
            "early_bonus": self.early_bonus,
            "late_penalty": self.late_penalty,
            "require_photo": self.require_photo,
            "assignment_mode": self.assignment_mode,
            "assignment_rotation_anchor": self.assignment_rotation_anchor,
            "assignment_current_child_id": self.assignment_current_child_id,
            "require_availability": self.require_availability,
            "skip_date": self.skip_date,
            "skip_count": self.skip_count,
            "publish_calendar_entities": self.publish_calendar_entities,
            "publish_calendar_published_dates": self.publish_calendar_published_dates,
            "bonus_subtasks": [b.to_dict() for b in self.bonus_subtasks],
            "task_type": self.task_type,
            "timed_rate_points": self.timed_rate_points,
            "timed_rate_minutes": self.timed_rate_minutes,
            "timed_max_daily_minutes": self.timed_max_daily_minutes,
            "id": self.id,
        }


@dataclass
class Reward:
    """Represents a reward."""

    name: str
    cost: int = 50
    description: str = ""
    icon: str = "mdi:gift"
    assigned_to: list[str] = field(default_factory=list)  # List of child IDs, empty means all children
    is_jackpot: bool = False  # If True, pool stars from all assigned children together
    pool_enabled: bool = False  # If True, this reward uses pool-mode (savings jar) semantics
    quantity: int | None = None  # Remaining stock; None means unlimited
    expires_at: str | None = None  # ISO "YYYY-MM-DD"; None means no deadline
    # Auto-restock: periodically reset `quantity` back to restock_amount.
    restock_enabled: bool = False
    restock_amount: int = 0
    restock_period: str = "weekly"  # daily | weekly (Mon) | monthly (1st)
    restock_last: str = ""  # ISO date this reward was last restocked
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reward:
        """Create a Reward from a dictionary."""
        raw_quantity = data.get("quantity")
        quantity = int(raw_quantity) if raw_quantity is not None else None
        raw_expires = data.get("expires_at")
        expires_at = str(raw_expires) if raw_expires else None
        return cls(
            name=data.get("name", ""),
            cost=data.get("cost", 50),
            description=data.get("description", ""),
            icon=data.get("icon", "mdi:gift"),
            assigned_to=list(data.get("assigned_to", [])),
            is_jackpot=data.get("is_jackpot", False),
            pool_enabled=data.get("pool_enabled", False),
            quantity=quantity,
            expires_at=expires_at,
            restock_enabled=data.get("restock_enabled", False),
            restock_amount=int(data.get("restock_amount", 0) or 0),
            restock_period=data.get("restock_period", "weekly"),
            restock_last=data.get("restock_last", ""),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "cost": self.cost,
            "description": self.description,
            "icon": self.icon,
            "assigned_to": self.assigned_to,
            "is_jackpot": self.is_jackpot,
            "pool_enabled": self.pool_enabled,
            "quantity": self.quantity,
            "expires_at": self.expires_at,
            "restock_enabled": self.restock_enabled,
            "restock_amount": self.restock_amount,
            "restock_period": self.restock_period,
            "restock_last": self.restock_last,
            "id": self.id,
        }


@dataclass
class Quest:
    """A chore chain: an ordered sequence of chores that awards a bonus.

    A child advances one step each time they complete (and have approved) the
    chore at their current step. Finishing the final step awards
    ``bonus_points``. If ``repeatable`` the child's progress resets so they can
    run the chain again; otherwise it stays complete.
    """

    name: str
    description: str = ""
    icon: str = "mdi:map-marker-path"
    steps: list[str] = field(default_factory=list)   # ordered chore IDs
    bonus_points: int = 25
    assigned_to: list[str] = field(default_factory=list)  # child IDs; empty = all
    repeatable: bool = False
    active: bool = True
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Quest:
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            icon=data.get("icon", "mdi:map-marker-path"),
            steps=[str(s) for s in data.get("steps", [])],
            bonus_points=int(data.get("bonus_points", 25) or 0),
            assigned_to=list(data.get("assigned_to", [])),
            repeatable=bool(data.get("repeatable", False)),
            active=bool(data.get("active", True)),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "steps": self.steps,
            "bonus_points": self.bonus_points,
            "assigned_to": self.assigned_to,
            "repeatable": self.repeatable,
            "active": self.active,
            "id": self.id,
        }


@dataclass
class ChoreCompletion:
    """Represents a chore completion record."""

    chore_id: str
    child_id: str
    completed_at: datetime
    approved: bool = False
    approved_at: datetime | None = None
    points_awarded: int = 0
    bonus_subtask_id: str = ""  # Non-empty = this completion is for a bonus sub-task
    timed_duration_seconds: int = 0
    photo_url: str = ""  # optional evidence photo (URL/path) attached at completion
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChoreCompletion:
        """Create a ChoreCompletion from a dictionary."""
        completed_at = parse_datetime(data.get("completed_at"))
        approved_at = parse_datetime(data.get("approved_at"))

        return cls(
            chore_id=data.get("chore_id", ""),
            child_id=data.get("child_id", ""),
            completed_at=completed_at or datetime.now(timezone.utc),
            approved=data.get("approved", False),
            approved_at=approved_at,
            points_awarded=data.get("points_awarded", 0),
            bonus_subtask_id=data.get("bonus_subtask_id", ""),
            timed_duration_seconds=data.get("timed_duration_seconds", 0),
            photo_url=data.get("photo_url", ""),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chore_id": self.chore_id,
            "child_id": self.child_id,
            "completed_at": format_datetime(self.completed_at),
            "approved": self.approved,
            "approved_at": format_datetime(self.approved_at),
            "points_awarded": self.points_awarded,
            "bonus_subtask_id": self.bonus_subtask_id,
            "timed_duration_seconds": self.timed_duration_seconds,
            "photo_url": self.photo_url,
            "id": self.id,
        }


@dataclass
class RewardClaim:
    """Represents a reward claim."""

    reward_id: str
    child_id: str
    claimed_at: datetime
    approved: bool = False
    approved_at: datetime | None = None
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RewardClaim:
        """Create a RewardClaim from a dictionary."""
        claimed_at = parse_datetime(data.get("claimed_at"))
        approved_at = parse_datetime(data.get("approved_at"))

        return cls(
            reward_id=data.get("reward_id", ""),
            child_id=data.get("child_id", ""),
            claimed_at=claimed_at or datetime.now(timezone.utc),
            approved=data.get("approved", False),
            approved_at=approved_at,
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "reward_id": self.reward_id,
            "child_id": self.child_id,
            "claimed_at": format_datetime(self.claimed_at),
            "approved": self.approved,
            "approved_at": format_datetime(self.approved_at),
            "id": self.id,
        }


@dataclass
class PoolAllocation:
    """Represents points a child has deposited into a specific reward's pool."""

    child_id: str
    reward_id: str
    allocated_points: int = 0
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PoolAllocation":
        """Create a PoolAllocation from a dictionary."""
        return cls(
            child_id=data.get("child_id", ""),
            reward_id=data.get("reward_id", ""),
            allocated_points=data.get("allocated_points", 0),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "child_id": self.child_id,
            "reward_id": self.reward_id,
            "allocated_points": self.allocated_points,
            "id": self.id,
        }


@dataclass
class Penalty:
    """Represents a penalty that deducts points from a child."""

    name: str
    points: int  # Points to deduct (always positive; deduction is applied on use)
    description: str = ""
    icon: str = "mdi:alert-circle-outline"
    assigned_to: list[str] = field(default_factory=list)  # Child IDs who can receive this penalty (empty = all)
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Penalty":
        """Create a Penalty from a dictionary."""
        return cls(
            id=data.get("id", generate_id()),
            name=data.get("name", ""),
            # Always positive — a negative value would *grant* points on use
            points=max(0, int(data.get("points", 0) or 0)),
            description=data.get("description", ""),
            icon=data.get("icon", "mdi:alert-circle-outline"),
            assigned_to=list(data.get("assigned_to", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "points": self.points,
            "description": self.description,
            "icon": self.icon,
            "assigned_to": self.assigned_to,
        }


@dataclass
class Bonus:
    """Represents a bonus that awards points to a child."""

    name: str
    points: int  # Points to award (always positive)
    description: str = ""
    icon: str = "mdi:star-circle-outline"
    assigned_to: list[str] = field(default_factory=list)  # Child IDs who can receive this bonus (empty = all)
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Bonus":
        """Create a Bonus from a dictionary."""
        return cls(
            id=data.get("id", generate_id()),
            name=data.get("name", ""),
            # Always positive — a negative value would *deduct* points on use
            points=max(0, int(data.get("points", 0) or 0)),
            description=data.get("description", ""),
            icon=data.get("icon", "mdi:star-circle-outline"),
            assigned_to=list(data.get("assigned_to", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "points": self.points,
            "description": self.description,
            "icon": self.icon,
            "assigned_to": self.assigned_to,
        }


@dataclass
class BadgeCriterion:
    """A single threshold rule used by Badge evaluation."""

    metric: str
    operator: str = ">="
    value: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BadgeCriterion":
        return cls(
            metric=data.get("metric", ""),
            operator=data.get("operator", ">="),
            value=int(data.get("value", 0) or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"metric": self.metric, "operator": self.operator, "value": self.value}


@dataclass
class PointsTransaction:
    """Represents a manual points adjustment (add or remove)."""

    child_id: str
    points: int  # positive = added, negative = removed
    reason: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PointsTransaction:
        """Create a PointsTransaction from a dictionary."""
        created_at = parse_datetime(data.get("created_at"))
        return cls(
            child_id=data.get("child_id", ""),
            points=data.get("points", 0),
            reason=data.get("reason", ""),
            created_at=created_at or datetime.now(timezone.utc),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "child_id": self.child_id,
            "points": self.points,
            "reason": self.reason,
            "created_at": format_datetime(self.created_at),
            "id": self.id,
        }


@dataclass
class Badge:
    """An achievement badge definition (built-in or custom)."""

    name: str
    description: str = ""
    icon: str = "mdi:trophy"
    tier: str = "bronze"  # "bronze" | "silver" | "gold" | "platinum"
    point_bonus: int = 0
    criteria: list[BadgeCriterion] = field(default_factory=list)
    combinator: str = "AND"  # reserved; v1 always AND
    assigned_to: list[str] = field(default_factory=list)  # empty = all kids
    builtin: bool = False
    enabled: bool = True
    notify_on_earn: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Badge":
        created_at = parse_datetime(data.get("created_at"))
        return cls(
            id=data.get("id", generate_id()),
            name=data.get("name", ""),
            description=data.get("description", ""),
            icon=data.get("icon", "mdi:trophy"),
            tier=data.get("tier", "bronze"),
            point_bonus=int(data.get("point_bonus", 0) or 0),
            criteria=[BadgeCriterion.from_dict(c) for c in data.get("criteria", [])],
            combinator=data.get("combinator", "AND"),
            assigned_to=list(data.get("assigned_to", [])),
            builtin=bool(data.get("builtin", False)),
            enabled=bool(data.get("enabled", True)),
            notify_on_earn=bool(data.get("notify_on_earn", True)),
            created_at=created_at or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "tier": self.tier,
            "point_bonus": self.point_bonus,
            "criteria": [c.to_dict() for c in self.criteria],
            "combinator": self.combinator,
            "assigned_to": self.assigned_to,
            "builtin": self.builtin,
            "enabled": self.enabled,
            "notify_on_earn": self.notify_on_earn,
            "created_at": format_datetime(self.created_at),
        }


@dataclass
class AwardedBadge:
    """A badge earn record for a specific child."""

    child_id: str
    badge_id: str
    earned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    manually_awarded: bool = False
    silent: bool = False  # True = retroactive backfill; suppresses notify + bonus
    bonus_credited: int = 0  # actual point_bonus credited at earn time
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AwardedBadge":
        earned_at = parse_datetime(data.get("earned_at"))
        return cls(
            id=data.get("id", generate_id()),
            child_id=data.get("child_id", ""),
            badge_id=data.get("badge_id", ""),
            earned_at=earned_at or datetime.now(timezone.utc),
            manually_awarded=bool(data.get("manually_awarded", False)),
            silent=bool(data.get("silent", False)),
            bonus_credited=int(data.get("bonus_credited", 0) or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "child_id": self.child_id,
            "badge_id": self.badge_id,
            "earned_at": format_datetime(self.earned_at),
            "manually_awarded": self.manually_awarded,
            "silent": self.silent,
            "bonus_credited": self.bonus_credited,
        }


@dataclass
class TaskGroup:
    """Groups chores so assignments stay coordinated across them.

    Policies:
    - sticky: followers are forced onto the leader chore's assignee today.
    - spread: group members are assigned distinct children today (wraps when
      there are more chores than children).

    `chore_ids` order is meaningful: index 0 is the leader for sticky; for
    spread it's the iteration order when walking the "already used" set.
    """

    name: str
    policy: str = "sticky"  # sticky | spread
    chore_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskGroup":
        return cls(
            name=data.get("name", ""),
            policy=data.get("policy", "sticky"),
            chore_ids=list(data.get("chore_ids", [])),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "policy": self.policy,
            "chore_ids": self.chore_ids,
            "id": self.id,
        }


@dataclass
class ParentRecipient:
    """A configured parent notification target."""

    name: str
    notify_service: str
    enabled: bool = True
    id: str = field(default_factory=lambda: f"parent:{generate_id()}")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ParentRecipient:
        rid = data.get("id") or f"parent:{generate_id()}"
        return cls(
            name=data.get("name", ""),
            notify_service=data.get("notify_service", ""),
            enabled=bool(data.get("enabled", True)),
            id=rid,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "notify_service": self.notify_service,
            "enabled": self.enabled,
        }


@dataclass
class NotificationRoute:
    """Per-recipient notification settings inside a NotificationConfig."""

    enabled: bool = False
    time: str | None = None  # "HH:MM" — only meaningful for per-recipient-time types

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationRoute:
        return cls(
            enabled=bool(data.get("enabled", False)),
            time=data.get("time"),
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"enabled": self.enabled}
        if self.time is not None:
            d["time"] = self.time
        return d


@dataclass
class NotificationConfig:
    """Stored configuration for one notification type."""

    type_id: str
    master_enabled: bool = False
    routes: dict[str, NotificationRoute] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationConfig:
        raw_routes = data.get("routes", {}) or {}
        return cls(
            type_id=data.get("type_id", ""),
            master_enabled=bool(data.get("master_enabled", False)),
            routes={
                rid: NotificationRoute.from_dict(rdata)
                for rid, rdata in raw_routes.items()
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type_id": self.type_id,
            "master_enabled": self.master_enabled,
            "routes": {rid: r.to_dict() for rid, r in self.routes.items()},
        }


@dataclass
class CustomNotification:
    """Parent-defined scheduled reminder."""

    name: str
    message_template: str
    time: str                         # "HH:MM"
    day_mask: int = 0b1111111         # bit0=Mon … bit6=Sun
    recipient_ids: list[str] = field(default_factory=list)
    enabled: bool = True
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CustomNotification:
        return cls(
            name=data.get("name", ""),
            message_template=data.get("message_template", ""),
            time=data.get("time", "20:00"),
            day_mask=int(data.get("day_mask", 0b1111111)),
            recipient_ids=list(data.get("recipient_ids", [])),
            enabled=bool(data.get("enabled", True)),
            id=data.get("id") or generate_id(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "message_template": self.message_template,
            "time": self.time,
            "day_mask": self.day_mask,
            "recipient_ids": list(self.recipient_ids),
            "enabled": self.enabled,
        }
