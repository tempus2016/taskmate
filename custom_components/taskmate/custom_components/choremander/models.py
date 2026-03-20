"""Data models for Choremander integration."""
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
            "id": self.id,
        }


@dataclass
class Chore:
    """Represents a chore."""

    name: str
    points: int = 10
    description: str = ""
    due_days: list[str] = field(default_factory=list)
    assigned_to: list[str] = field(default_factory=list)  # List of child IDs
    requires_approval: bool = True
    time_category: str = "anytime"  # morning, afternoon, evening, night, anytime
    daily_limit: int = 1
    completion_sound: str = "coin"  # Sound to play on completion
    completion_percentage_per_month: int = 100  # Expected completion rate (100 = every day)
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chore:
        """Create a Chore from a dictionary."""
        return cls(
            name=data.get("name", ""),
            points=data.get("points", 10),
            description=data.get("description", ""),
            due_days=data.get("due_days", []),
            assigned_to=data.get("assigned_to", []),
            requires_approval=data.get("requires_approval", True),
            time_category=data.get("time_category", "anytime"),
            daily_limit=data.get("daily_limit", 1),
            completion_sound=data.get("completion_sound", "coin"),
            completion_percentage_per_month=data.get("completion_percentage_per_month", 100),
            id=data.get("id", generate_id()),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "points": self.points,
            "description": self.description,
            "due_days": self.due_days,
            "assigned_to": self.assigned_to,
            "requires_approval": self.requires_approval,
            "time_category": self.time_category,
            "daily_limit": self.daily_limit,
            "completion_sound": self.completion_sound,
            "completion_percentage_per_month": self.completion_percentage_per_month,
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
    override_point_value: bool = False  # If False (default), calculate cost dynamically; if True, use manual cost
    days_to_goal: int = 30  # Number of days to reach the reward goal
    id: str = field(default_factory=generate_id)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reward:
        """Create a Reward from a dictionary."""
        # Handle migration from old is_dynamic field
        override_point_value = data.get("override_point_value", None)
        if override_point_value is None:
            # Migrate from is_dynamic: if is_dynamic was True, override is False; if is_dynamic was False, override is True
            old_is_dynamic = data.get("is_dynamic", False)
            override_point_value = not old_is_dynamic
        return cls(
            name=data.get("name", ""),
            cost=data.get("cost", 50),
            description=data.get("description", ""),
            icon=data.get("icon", "mdi:gift"),
            assigned_to=data.get("assigned_to", []),
            is_jackpot=data.get("is_jackpot", False),
            override_point_value=override_point_value,
            days_to_goal=data.get("days_to_goal", 30),
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
            "override_point_value": self.override_point_value,
            "days_to_goal": self.days_to_goal,
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
