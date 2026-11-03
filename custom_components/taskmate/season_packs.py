"""Season event packs: the content each season brings, shipped as data.

A pack is a handful of ordinary TaskMate items — chores, a quest, a reward, a
badge, a challenge — that install themselves when the season's window starts
and are hidden again when it ends (coord_season_packs.py does that).

Only ids, points, schedules and icons live here. Every name is a translation
key in the panel's locale files (``season_pack.<season>.<key>``), read in Home
Assistant's language when the pack installs, the way the library and the
setup wizard name what they create. ``tests/test_season_packs.py`` checks every
key has a name in every locale.

Points and costs are fixed numbers, like every other TaskMate item.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).parent / "www" / "locales"
STRING_PREFIX = "season_pack."

_EVERY_DAY = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_SCHOOL_NIGHTS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
_SCHOOL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

ADVENT_DOORS = 24
EASTER_EGGS = 7


def _days(points: int, icon: str, time: str, days: list[str], **extra: Any) -> dict:
    """A chore shown on the given weekdays."""
    return {
        "points": points,
        "icon": icon,
        "time_category": time,
        "schedule_mode": "specific_days",
        "due_days": list(days),
        **extra,
    }


def _every(points: int, icon: str, time: str, recurrence: str, **extra: Any) -> dict:
    """A chore that comes back a while after it is done (once per short season
    when the gap is longer than the window)."""
    return {
        "points": points,
        "icon": icon,
        "time_category": time,
        "schedule_mode": "recurring",
        "recurrence": recurrence,
        **extra,
    }


# One dict per season. ``chores`` are keyed by their string key; a chore with
# ``day`` is a one-off on that day of the window (0 = the first day), which is
# how the advent doors and the Easter eggs open one a day. ``badge.goal`` is how
# many of the pack's jobs (approved, inside the window) earn it; ``badge.counts``
# narrows that to some of the chores.
PACKS: dict[str, dict[str, Any]] = {
    "halloween": {
        "emoji": "🎃",
        "chores": {
            "carve_pumpkin": _every(10, "mdi:halloween", "afternoon", "every_14_days"),
            "sweep_leaves": _every(5, "mdi:leaf", "afternoon", "every_3_days"),
            "sort_sweets": _every(5, "mdi:candy", "anytime", "every_14_days"),
            "hang_decorations": _every(5, "mdi:spider-web", "anytime", "every_14_days", quest_only=True),
            "trick_or_treat_tidy": _every(5, "mdi:broom", "evening", "every_14_days", quest_only=True),
        },
        "quest": {
            "key": "pumpkin_patrol",
            "icon": "mdi:map-marker-path",
            "bonus": 25,
            "steps": ["carve_pumpkin", "sweep_leaves", "sort_sweets", "hang_decorations", "trick_or_treat_tidy"],
        },
        "reward": {"key": "pick_the_movie", "icon": "mdi:movie-open", "cost": 40},
        "badge": {"key": "ghostbuster", "icon": "mdi:ghost", "tier": "silver", "bonus": 10, "goal": 5},
    },
    "christmas": {
        "emoji": "🎄",
        "advent": True,
        "chores": {
            **{
                f"advent_{n}": {
                    "points": 5,
                    "icon": "mdi:gift-outline",
                    "time_category": "anytime",
                    "schedule_mode": "one_shot",
                    "day": n - 1,
                    "door": n,
                    "requires_approval": True,
                }
                for n in range(1, ADVENT_DOORS + 1)
            },
            "write_cards": _every(10, "mdi:email-heart-outline", "anytime", "every_30_days"),
            "wrap_gift": _every(5, "mdi:gift", "anytime", "weekly"),
            "tidy_tree": _every(3, "mdi:pine-tree", "anytime", "every_3_days"),
            "set_table": _days(3, "mdi:silverware-fork-knife", "evening", _EVERY_DAY),
            "paper_chain": _every(5, "mdi:link-variant", "anytime", "every_30_days", quest_only=True),
            "bake_biscuits": _every(5, "mdi:cookie", "afternoon", "every_30_days", quest_only=True),
        },
        "quest": {
            "key": "elf_helper",
            "icon": "mdi:map-marker-path",
            "bonus": 30,
            "steps": ["write_cards", "wrap_gift", "tidy_tree", "set_table", "paper_chain", "bake_biscuits"],
        },
        "reward": {"key": "christmas_eve_film", "icon": "mdi:television-classic", "cost": 60},
        "badge": {
            "key": "little_elf",
            "icon": "mdi:pine-tree",
            "tier": "gold",
            "bonus": 20,
            "goal": 20,
            "counts": "advent",
        },
    },
    "easter": {
        "emoji": "🐣",
        "chores": {
            f"egg_{n}": {
                "points": 5,
                "icon": "mdi:egg-easter",
                "time_category": "anytime",
                "schedule_mode": "one_shot",
                "day": n - 1,
                "egg": n,
                "requires_approval": True,
            }
            for n in range(1, EASTER_EGGS + 1)
        },
        "badge": {"key": "egg_hunter", "icon": "mdi:egg-easter", "tier": "silver", "bonus": 10, "goal": 5},
    },
    "summer": {
        "emoji": "☀️",
        "chores": {
            "read_20": _days(3, "mdi:book-open-variant", "anytime", _EVERY_DAY, challenge=True),
            "water_garden": _days(3, "mdi:watering-can", "evening", ["monday", "wednesday", "friday"]),
            "paddling_pool": _every(5, "mdi:pool", "afternoon", "weekly"),
            "beach_bag": _every(3, "mdi:bag-personal", "morning", "weekly"),
        },
        # The reading challenge: read (a chore of its own) and get five jobs
        # done in a week, with the existing weekly challenge.
        "challenge": {
            "key": "reading_challenge",
            "icon": "mdi:book-open-page-variant",
            "scope": "weekly",
            "metric": "chores",
            "target": 5,
            "bonus": 25,
        },
        "badge": {"key": "sun_seeker", "icon": "mdi:white-balance-sunny", "tier": "gold", "bonus": 20, "goal": 20},
    },
    "back_to_school": {
        "emoji": "🎒",
        "chores": {
            "pack_bag": _days(3, "mdi:bag-personal-outline", "evening", _SCHOOL_NIGHTS),
            "lay_out_uniform": _days(2, "mdi:tshirt-crew-outline", "evening", _SCHOOL_NIGHTS),
            "lunchbox_back": _days(2, "mdi:food-takeout-box-outline", "afternoon", _SCHOOL_DAYS),
            "label_things": _every(5, "mdi:label-outline", "anytime", "every_30_days", quest_only=True),
        },
        "quest": {
            "key": "ready_for_school",
            "icon": "mdi:map-marker-path",
            "bonus": 20,
            "steps": ["pack_bag", "lay_out_uniform", "lunchbox_back", "label_things"],
        },
    },
}


def pack_string_keys() -> list[str]:
    """Every locale key the packs name things with (for the locale test)."""
    keys = [f"{STRING_PREFIX}door", f"{STRING_PREFIX}easter.egg"]
    for season, pack in PACKS.items():
        for key, chore in pack["chores"].items():
            if "egg" in chore:
                continue
            keys.append(f"{STRING_PREFIX}{season}.{key}")
        for kind in ("quest", "reward", "challenge"):
            if kind in pack:
                keys.append(f"{STRING_PREFIX}{season}.{pack[kind]['key']}")
        if "challenge" in pack:
            keys.append(f"{STRING_PREFIX}{season}.{pack['challenge']['key']}_desc")
        if "badge" in pack:
            keys.append(f"{STRING_PREFIX}{season}.{pack['badge']['key']}")
            keys.append(f"{STRING_PREFIX}{season}.{pack['badge']['key']}_desc")
    return keys


def pack_contents(season: str) -> list[dict]:
    """What a pack holds, for the panel's chips and Preview: kind, key and the
    fixed numbers. Names are looked up by the panel from the same keys."""
    pack = PACKS.get(season)
    if not pack:
        return []
    out: list[dict] = []
    chores = pack["chores"]
    doors = [k for k, c in chores.items() if "door" in c]
    eggs = [k for k, c in chores.items() if "egg" in c]
    if doors:
        out.append({"kind": "advent", "count": len(doors), "points": chores[doors[0]]["points"]})
    if eggs:
        out.append({"kind": "hunt", "count": len(eggs), "points": chores[eggs[0]]["points"]})
    if "quest" in pack:
        quest = pack["quest"]
        out.append(
            {
                "kind": "quest",
                "key": quest["key"],
                "steps": len(quest["steps"]),
                "items": list(quest["steps"]),
                "points": quest["bonus"],
            }
        )
    if "challenge" in pack:
        ch = pack["challenge"]
        out.append({"kind": "challenge", "key": ch["key"], "target": ch["target"], "points": ch["bonus"]})
    plain = [
        {"key": k, "points": c["points"]}
        for k, c in chores.items()
        if not any(f in c for f in ("door", "egg", "quest_only", "challenge"))
    ]
    if plain:
        out.append({"kind": "chores", "items": plain})
    if "reward" in pack:
        out.append({"kind": "reward", "key": pack["reward"]["key"], "points": pack["reward"]["cost"]})
    if "badge" in pack:
        badge = pack["badge"]
        out.append({"kind": "badge", "key": badge["key"], "goal": badge["goal"], "points": badge["bonus"]})
    return out


# ── Names in the family's language ─────────────────────────────────────────

_cache: dict[str, dict[str, str]] = {}


def _read(code: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{code}.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _LOGGER.warning("Could not read TaskMate locale %s for season packs", path.name)
        return {}
    return {k: v for k, v in data.items() if k.startswith(STRING_PREFIX) and isinstance(v, str) and v.strip()}


def read_strings(lang: str) -> dict[str, str]:
    """English, overlaid with the base language (pt for pt-BR), then the exact one."""
    strings = _read("en")
    candidates = [lang.split("-", 1)[0], lang] if "-" in lang else [lang]
    for code in candidates:
        if code != "en":
            strings.update(_read(code))
    return strings


async def async_load_strings(hass: Any, lang: str) -> dict[str, str]:
    """The pack names for ``lang``, read once off the event loop and cached."""
    if lang not in _cache:
        _cache[lang] = await hass.async_add_executor_job(read_strings, lang)
    return _cache[lang]


def name_of(strings: dict[str, str], key: str, **params: Any) -> str:
    """A pack string with its ``{n}`` / ``{job}`` filled in; the key if missing."""
    from .notify_strings import safe_format

    text = strings.get(STRING_PREFIX + key) or key
    try:
        return safe_format(text, params) if params else text
    except (KeyError, IndexError, ValueError):
        return text
