"""Suggestions for the setup wizard (#980).

Chores suggested by age group and a handful of starter rewards. Only ids,
points, schedules and icons live here: every name is a translation key in the
panel's locale files (``wizard.chore.<id>`` / ``wizard.reward.<id>``), so a
chore the wizard creates takes the family's language at creation time.
``tests/test_setup_wizard.py`` checks every id has a name in every locale.

Rewards have fixed costs, like every other reward.
"""

from __future__ import annotations

from typing import Any

from .const import AGE_GROUPS

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

# Each age group: its youngest and oldest age (None = no upper limit), plus the
# colour and icon the wizard draws its heading with.
AGE_GROUP_INFO: dict[str, dict[str, Any]] = {
    "3_5": {"min_age": 3, "max_age": 5, "color": "#1abc9c", "icon": "mdi:toy-brick-outline"},
    "6_8": {"min_age": 6, "max_age": 8, "color": "#3498db", "icon": "mdi:bed-outline"},
    "9_12": {"min_age": 9, "max_age": 12, "color": "#ff6b9d", "icon": "mdi:dishwasher"},
    "13_plus": {"min_age": 13, "max_age": None, "color": "#9b59b6", "icon": "mdi:pot-steam-outline"},
}

# How often a suggestion comes round, as chore schedule fields, and roughly how
# many times a week that is (the wizard's "per week" estimate).
FREQUENCIES: dict[str, dict[str, Any]] = {
    "daily": {"schedule_mode": "specific_days", "per_week": 7},
    "weekdays": {"schedule_mode": "specific_days", "per_week": 5},
    "days": {"schedule_mode": "specific_days", "per_week": None},  # per_week = number of days
    "weekly": {"schedule_mode": "recurring", "recurrence": "weekly", "per_week": 1},
    "every_2_weeks": {"schedule_mode": "recurring", "recurrence": "every_2_weeks", "per_week": 0.5},
    "monthly": {"schedule_mode": "recurring", "recurrence": "monthly", "per_week": 0.25},
}


def _s(sid: str, age_group: str, points: int, freq: str, time: str, icon: str, days: list[str] | None = None) -> dict:
    return {
        "id": sid,
        "age_group": age_group,
        "points": points,
        "frequency": freq,
        "days": list(days or []),
        "time_category": time,
        "icon": icon,
    }


# About eight per age group; the wizard ticks the first five for each group a
# child is in. Points rise with age and with the size of the job.
SUGGESTED_CHORES: list[dict] = [
    # 3–5: one-step jobs
    _s("toys_away", "3_5", 1, "daily", "evening", "mdi:toy-brick-outline"),
    _s("clothes_basket", "3_5", 1, "daily", "evening", "mdi:basket-outline"),
    _s("brush_teeth_help", "3_5", 1, "daily", "morning", "mdi:toothbrush"),
    _s("shoes_coat", "3_5", 1, "daily", "afternoon", "mdi:shoe-sneaker"),
    _s("help_feed_pet", "3_5", 1, "daily", "morning", "mdi:paw"),
    _s("match_socks", "3_5", 1, "days", "anytime", "mdi:shoe-print", ["saturday"]),
    _s("napkins", "3_5", 1, "daily", "evening", "mdi:silverware-fork-knife"),
    _s("water_plant", "3_5", 1, "days", "anytime", "mdi:sprout-outline", ["wednesday", "saturday"]),
    # 6–8: routines they tick off themselves
    _s("make_bed", "6_8", 2, "daily", "morning", "mdi:bed-outline"),
    _s("get_dressed", "6_8", 1, "daily", "morning", "mdi:tshirt-crew-outline"),
    _s("pack_school_bag", "6_8", 2, "weekdays", "morning", "mdi:bag-personal-outline"),
    _s("set_clear_table", "6_8", 2, "daily", "evening", "mdi:silverware-variant"),
    _s("tidy_bedroom", "6_8", 3, "days", "anytime", "mdi:broom", ["saturday"]),
    _s("feed_pet", "6_8", 2, "daily", "morning", "mdi:paw"),
    _s("put_away_laundry", "6_8", 2, "days", "anytime", "mdi:tshirt-crew", ["tuesday", "friday"]),
    _s("read_15", "6_8", 2, "daily", "anytime", "mdi:book-open-variant"),
    # 9–12: real household jobs
    _s("dishwasher", "9_12", 3, "daily", "evening", "mdi:dishwasher"),
    _s("bins_out", "9_12", 3, "days", "anytime", "mdi:delete-outline", ["tuesday"]),
    _s("hoover_room", "9_12", 4, "days", "anytime", "mdi:vacuum-outline", ["saturday"]),
    _s("walk_dog", "9_12", 3, "daily", "afternoon", "mdi:dog-side"),
    _s("help_cook", "9_12", 4, "days", "evening", "mdi:pot-steam-outline", ["wednesday", "sunday"]),
    _s("clean_sink", "9_12", 3, "days", "anytime", "mdi:faucet", ["sunday"]),
    _s("homework_no_reminders", "9_12", 3, "weekdays", "afternoon", "mdi:pencil-outline"),
    _s("change_sheets", "9_12", 4, "every_2_weeks", "anytime", "mdi:bed-king-outline", ["sunday"]),
    # 13+: life skills
    _s("cook_meal", "13_plus", 8, "days", "evening", "mdi:chef-hat", ["friday"]),
    _s("own_laundry", "13_plus", 5, "weekly", "anytime", "mdi:washing-machine"),
    _s("mow_lawn", "13_plus", 8, "every_2_weeks", "anytime", "mdi:mower", ["saturday"]),
    _s("clean_bathroom", "13_plus", 6, "days", "anytime", "mdi:shower-head", ["sunday"]),
    _s("wash_car", "13_plus", 6, "monthly", "anytime", "mdi:car-wash"),
    _s("babysit", "13_plus", 8, "weekly", "anytime", "mdi:baby-face-outline"),
    _s("food_shop", "13_plus", 5, "days", "anytime", "mdi:cart-outline", ["saturday"]),
    _s("recycling", "13_plus", 3, "days", "anytime", "mdi:recycle", ["tuesday"]),
]

# Starter rewards in three tiers. ``picked`` ones are ticked when the wizard opens.
REWARD_TIERS: tuple[str, ...] = ("small", "saving", "big")
STARTER_REWARDS: list[dict] = [
    {"id": "screen_time", "tier": "small", "cost": 15, "icon": "mdi:television-play", "picked": True},
    {"id": "pick_pudding", "tier": "small", "cost": 10, "icon": "mdi:cupcake", "picked": False},
    {"id": "car_music", "tier": "small", "cost": 10, "icon": "mdi:music", "picked": False},
    {"id": "choose_dinner", "tier": "saving", "cost": 40, "icon": "mdi:pizza", "picked": True},
    {"id": "stay_up_late", "tier": "saving", "cost": 40, "icon": "mdi:weather-night", "picked": True},
    {"id": "family_film", "tier": "saving", "cost": 30, "icon": "mdi:movie-open-outline", "picked": True},
    {"id": "ice_cream_trip", "tier": "big", "cost": 100, "icon": "mdi:ice-cream", "picked": True},
    {"id": "spending_money", "tier": "big", "cost": 150, "icon": "mdi:cash", "picked": False},
    {"id": "sleepover", "tier": "big", "cost": 250, "icon": "mdi:sleep", "picked": True},
]


def suggestion_schedule(suggestion: dict) -> dict[str, Any]:
    """The chore schedule fields for a suggestion, plus its times-per-week."""
    freq = FREQUENCIES[suggestion["frequency"]]
    days = list(suggestion.get("days") or [])
    schedule: dict[str, Any] = {"schedule_mode": freq["schedule_mode"], "due_days": []}
    if suggestion["frequency"] == "weekdays":
        schedule["due_days"] = list(_WEEKDAYS)
    elif suggestion["frequency"] == "days":
        schedule["due_days"] = days
    if freq["schedule_mode"] == "recurring":
        schedule["recurrence"] = freq["recurrence"]
        # A weekly or fortnightly job pinned to a day only opens on that day.
        schedule["recurrence_day"] = days[0] if days and freq["recurrence"] != "monthly" else ""
    per_week = freq["per_week"] if freq["per_week"] is not None else len(days)
    return {"schedule": schedule, "per_week": per_week}


def setup_catalogue() -> dict[str, Any]:
    """Everything the wizard offers, in the shape the panel uses."""
    return {
        "age_groups": [{"id": gid, **AGE_GROUP_INFO[gid]} for gid in AGE_GROUPS],
        "chores": [{**s, **suggestion_schedule(s)} for s in SUGGESTED_CHORES],
        "reward_tiers": list(REWARD_TIERS),
        "rewards": [dict(r) for r in STARTER_REWARDS],
    }
