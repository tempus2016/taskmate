"""Built-in chore template packs for TaskMate."""

from __future__ import annotations

TEMPLATE_CHORE_FIELDS = (
    "name",
    "points",
    "description",
    "requires_approval",
    "time_category",
    "daily_limit",
    "completion_sound",
    "schedule_mode",
    "due_days",
    "recurrence",
    "recurrence_day",
    "recurrence_start",
    "first_occurrence_mode",
    "assignment_mode",
    "require_availability",
    "visibility_entity",
    "visibility_state",
    "visibility_operator",
    "weather_entity",
    "weather_block_conditions",
    "weather_temp_min",
    "weather_temp_max",
    "weather_wind_max",
    "task_type",
    "timed_rate_points",
    "timed_rate_minutes",
    "timed_max_daily_minutes",
)

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
_WEEKENDS = ["saturday", "sunday"]


def _chore(name: str, points: int, time_category: str, due_days: list[str] = _WEEKDAYS) -> dict:
    """One built-in template chore; all built-ins share the same fixed defaults."""
    return {
        "name": name,
        "points": points,
        "time_category": time_category,
        "schedule_mode": "specific_days",
        "due_days": list(due_days),
        "requires_approval": False,
        "assignment_mode": "everyone",
        "daily_limit": 1,
        "completion_sound": "coin",
    }


BUILT_IN_TEMPLATES: list[dict] = [
    {
        "id": "morning_routine",
        "name": "Morning routine",
        "icon": "mdi:weather-sunny",
        "builtin": True,
        "chores": [
            _chore("Make bed", 2, "morning"),
            _chore("Brush teeth", 1, "morning"),
            _chore("Get dressed", 1, "morning"),
            _chore("Pack school bag", 2, "morning"),
        ],
    },
    {
        "id": "evening_routine",
        "name": "Evening routine",
        "icon": "mdi:weather-night",
        "builtin": True,
        "chores": [
            _chore("Brush teeth", 1, "evening"),
            _chore("Put on pyjamas", 1, "evening"),
            _chore("Tidy room", 2, "evening"),
            _chore("Set out clothes for tomorrow", 1, "evening"),
        ],
    },
    {
        "id": "kitchen_helper",
        "name": "Kitchen helper",
        "icon": "mdi:silverware-fork-knife",
        "builtin": True,
        "chores": [
            _chore("Set table", 2, "evening"),
            _chore("Clear plates", 2, "evening"),
            _chore("Load dishwasher", 3, "evening"),
            _chore("Wipe counters", 2, "evening"),
        ],
    },
    {
        "id": "weekend_helper",
        "name": "Weekend helper",
        "icon": "mdi:broom",
        "builtin": True,
        "chores": [
            _chore("Tidy bedroom", 3, "anytime", _WEEKENDS),
            _chore("Hoover", 4, "anytime", _WEEKENDS),
            _chore("Help with laundry", 3, "anytime", _WEEKENDS),
            _chore("Take bins out", 2, "anytime", _WEEKENDS),
        ],
    },
    {
        "id": "pet_care",
        "name": "Pet care",
        "icon": "mdi:paw",
        "builtin": True,
        "chores": [
            _chore("Feed pet", 2, "morning"),
            _chore("Fill water bowl", 1, "morning"),
            _chore("Walk dog", 3, "afternoon"),
            _chore("Clean litter tray", 3, "anytime"),
        ],
    },
    {
        "id": "homework_reading",
        "name": "Homework & reading",
        "icon": "mdi:book-open-variant",
        "builtin": True,
        "chores": [
            _chore("Do homework", 3, "afternoon"),
            _chore("Read for 20 minutes", 2, "anytime"),
            _chore("Practice instrument", 2, "anytime"),
        ],
    },
]

BUILT_IN_IDS = frozenset(t["id"] for t in BUILT_IN_TEMPLATES)
