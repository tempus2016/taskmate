"""Family style preset (#1260): Game, Team or Custom.

A style is a named set of on/off switches applied in one go. It never deletes
anything: points, history, penalties and raffles stay where they are, and
every switch stays editable afterwards.

- ``family_style``: "game", "team" or "custom". Missing means the install
  predates the feature and behaves exactly as before (read as "game").
- ``style_hide_scope``: "cards" (default) hides a switched-off feature on the
  cards only; "both" also takes its tabs out of the admin panel.
- ``family_style_snapshot``: the switches as they were just before Team was
  applied, so Game can put them back. Without one, Game uses the defaults.

Changing a covered switch by hand afterwards makes the style "custom".
"""

from __future__ import annotations

from typing import Any, Final

from .family_goal import start_family_goal

FAMILY_STYLE_KEY: Final = "family_style"
STYLE_HIDE_SCOPE_KEY: Final = "style_hide_scope"
STYLE_SNAPSHOT_KEY: Final = "family_style_snapshot"

FAMILY_STYLES: Final = ("game", "team", "custom")
STYLE_HIDE_SCOPES: Final = ("cards", "both")

# Every switch a style covers: key -> (default when unset, value under Team).
# The defaults are the ones each feature already reads, so an install that
# has never stored a key keeps behaving the same.
STYLE_SWITCHES: Final[dict[str, tuple[bool, bool]]] = {
    "leaderboard_enabled": (True, False),
    "penalties_enabled": (True, False),
    "points_decay_enabled": (False, False),
    "raffles_enabled": (True, False),
    "roulette_enabled": (False, False),
    "inspections_enabled": (True, False),
    "family_goal_enabled": (False, True),
}

# The new switches the cards read off the overview sensor (only when off).
CARD_FEATURE_SWITCHES: Final[dict[str, str]] = {
    "leaderboard": "leaderboard_enabled",
    "penalties": "penalties_enabled",
    "raffles": "raffles_enabled",
}


def _as_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def switch_value(settings: dict, key: str) -> bool:
    """A covered switch as a bool, its default when it was never stored."""
    return _as_bool((settings or {}).get(key), STYLE_SWITCHES[key][0])


def switch_values(settings: dict) -> dict[str, bool]:
    return {key: switch_value(settings, key) for key in STYLE_SWITCHES}


def current_style(settings: dict) -> str:
    """The stored style; a missing or unknown one reads as "game"."""
    value = (settings or {}).get(FAMILY_STYLE_KEY)
    return value if value in FAMILY_STYLES else "game"


def hide_scope(settings: dict) -> str:
    value = (settings or {}).get(STYLE_HIDE_SCOPE_KEY)
    return value if value in STYLE_HIDE_SCOPES else "cards"


def features_off(settings: dict) -> list[str]:
    """The card features switched off, e.g. ["leaderboard", "raffles"]."""
    return [name for name, key in CARD_FEATURE_SWITCHES.items() if not switch_value(settings, key)]


def _target_values(settings: dict, style: str) -> dict[str, bool]:
    now = switch_values(settings)
    if style == "team":
        return {key: team for key, (_default, team) in STYLE_SWITCHES.items()}
    if style == "game":
        snapshot = (settings or {}).get(STYLE_SNAPSHOT_KEY)
        if isinstance(snapshot, dict):
            return {key: _as_bool(snapshot.get(key), STYLE_SWITCHES[key][0]) for key in STYLE_SWITCHES}
        return {key: default for key, (default, _team) in STYLE_SWITCHES.items()}
    return now


def plan_family_style(settings: dict, style: str) -> list[dict[str, Any]]:
    """What applying ``style`` would change: [{key, old, new}], in switch order."""
    if style not in FAMILY_STYLES:
        raise ValueError(f"unknown family style: {style}")
    now = switch_values(settings)
    target = _target_values(settings, style)
    return [{"key": key, "old": now[key], "new": target[key]} for key in STYLE_SWITCHES if now[key] != target[key]]


def apply_family_style(storage, style: str) -> dict[str, Any]:
    """Apply a style to the stored settings (the caller saves and refreshes).

    Returns {style, previous, changes}. Team keeps a snapshot of the switches
    as they were (only the first time, so Team → Custom → Team still returns
    to the original values); Game restores it and drops it.
    """
    settings = storage.get_settings()
    previous = settings.get(FAMILY_STYLE_KEY)
    changes = plan_family_style(settings, style)
    if style == "team" and not isinstance(settings.get(STYLE_SNAPSHOT_KEY), dict):
        storage.set_setting(STYLE_SNAPSHOT_KEY, switch_values(settings))
    for change in changes:
        storage.set_setting(change["key"], change["new"])
    if style == "game" and STYLE_SNAPSHOT_KEY in settings:
        storage.get_settings().pop(STYLE_SNAPSHOT_KEY, None)
    # A family goal switched on (or off) starts again, as in update_settings;
    # switched on, it counts from 0 (#1282).
    if any(c["key"] == "family_goal_enabled" for c in changes):
        storage.set_setting("family_goal_achieved", False)
    if any(c["key"] == "family_goal_enabled" and c["new"] for c in changes):
        start_family_goal(storage)
    storage.set_setting(FAMILY_STYLE_KEY, style)
    return {"style": style, "previous": previous if previous in FAMILY_STYLES else None, "changes": changes}


def note_manual_change(storage, before: dict[str, bool]) -> bool:
    """Flip a Game or Team family to "custom" when a covered switch changed by hand.

    ``before`` is ``switch_values`` taken before the edit. A family that never
    picked a style is left alone. Returns True when the style changed.
    """
    settings = storage.get_settings()
    if settings.get(FAMILY_STYLE_KEY) not in ("game", "team"):
        return False
    if switch_values(settings) == before:
        return False
    storage.set_setting(FAMILY_STYLE_KEY, "custom")
    return True
