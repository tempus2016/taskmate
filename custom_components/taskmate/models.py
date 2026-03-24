"""Data models for TaskMate integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())[:8]


def parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse a datetime value, ensuring timezone awareness.

    If the datetime is naive (no timezone info), assume it's in the local
    timezone of the HA instance. All stored datetimes should have timezone info.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        # If already a datetime, ensure it has timezone info
        if value.tzinfo is None:
            # Naive datetime - assume UTC for backward compatibility
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            # Naive datetime string - assume UTC for backward compatibility
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
    streak_milestones_achieved: list = None  # List of milestone day counts already awarded (None = use [])
    awarded_perfect_weeks: list = None  # List of Monday ISO dates for awarded perfect weeks (None = use [])
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
            pending_rewards=data.get("pending_rewards", []),
            chore_order=data.get("chore_order", []),
            last_completion_date=data.get("last_completion_date", None),
            streak_paused=data.get("streak_paused", False),
            streak_milestones_achieved=data.get("streak_milestones_achieved", []),
            awarded_perfect_weeks=data.get("awarded_perfect_weeks", []),
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
            "streak_milestones_achieved": self.streak_milestones_achieved or [],
            "awarded_perfect_weeks": self.awarded_perfect_weeks or [],
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
    daily_limit: int = 1
    completion_sound: str = "coin"  # Sound to play on completion
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
            assigned_to=data.get("assigned_to", []),
            requires_approval=data.get("requires_approval", True),
            time_category=data.get("time_category", "anytime"),
            daily_limit=data.get("daily_limit", 1),
            completion_sound=data.get("completion_sound", "coin"),
            schedule_mode=schedule_mode,
            due_days=data.get("due_days", []),
            recurrence=data.get("recurrence", "weekly"),
            recurrence_day=data.get("recurrence_day", ""),
            recurrence_start=data.get("recurrence_start", ""),
            first_occurrence_mode=data.get("first_occurrence_mode", "available_immediately"),
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
            "daily_limit": self.daily_limit,
            "completion_sound": self.completion_sound,
            "schedule_mode": self.schedule_mode,
            "due_days": self.due_days,
            "recurrence": self.recurrence,
            "recurrence_day": self.recurrence_day,
            "recurrence_start": self.recurrence_start,
            "first_occurrence_mode": self.first_occurrence_mode,
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
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reward:
        """Create a Reward from a dictionary."""
        return cls(
            name=data.get("name", ""),
            cost=data.get("cost", 50),
            description=data.get("description", ""),
            icon=data.get("icon", "mdi:gift"),
            assigned_to=data.get("assigned_to", []),
            is_jackpot=data.get("is_jackpot", False),
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
