"""Family co-op goal progress (FEAT-4, #1282).

The goal counts points the children have earned since it started, not their
current balances: spending or redeeming personal points never moves it back,
and a new goal starts at 0. Each child's ``total_points_earned`` at the start
is kept in the ``family_goal_baseline`` setting ({child_id: earned}). A child
missing from it (added after the goal started) counts from 0. Penalties don't
lower ``total_points_earned``, so they don't lower the goal either. Adult
profiles (#1061) are left out unless ``family_goal_include_adults`` is on.
The baseline records every profile, adults too, so switching adults in
mid-goal counts what they've earned since the goal started; an adult with no
entry (a goal started before this option) counts from the moment it's
switched on (``include_adults_switched_on``).

Installs from before #1282 get a baseline of ``earned - balance`` per child on
first load (``seed_family_goal_baseline``), so an existing goal shows the same
number it showed before the upgrade and only counts new earnings from then on.
Until a baseline exists (e.g. straight after restoring an older backup) the
goal falls back to the combined balances, as it always did.
"""

from __future__ import annotations

from typing import Any

BASELINE_KEY = "family_goal_baseline"
INCLUDE_ADULTS_KEY = "family_goal_include_adults"


def includes_adults(storage) -> bool:
    return storage.get_setting(INCLUDE_ADULTS_KEY, False) in (True, "true")


def _goal_children(storage) -> list[Any]:
    """The profiles whose points count towards the goal."""
    if includes_adults(storage):
        return list(storage.get_children())
    return [c for c in storage.get_children() if not getattr(c, "is_adult", False)]


def _earned(child) -> int:
    try:
        return int(getattr(child, "total_points_earned", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _balance(child) -> int:
    try:
        return int(getattr(child, "points", 0) or 0)
    except (TypeError, ValueError):
        return 0


def family_goal_progress(storage) -> int:
    """Points earned towards the current family goal (children, plus adults if included)."""
    kids = _goal_children(storage)
    baseline = storage.get_setting(BASELINE_KEY, None)
    if not isinstance(baseline, dict):
        return max(0, sum(_balance(c) for c in kids))
    total = 0
    for child in kids:
        try:
            start = int(baseline.get(child.id, 0) or 0)
        except (TypeError, ValueError):
            start = 0
        # Undoing an approval from before the start can take a child below it.
        total += max(0, _earned(child) - start)
    return total


def start_family_goal(storage) -> None:
    """Start the goal again at 0: every child counts from what they've earned now.

    Balances aren't touched. Re-arms the celebration. The caller saves.
    """
    storage.set_setting(BASELINE_KEY, {c.id: _earned(c) for c in storage.get_children()})
    storage.set_setting("family_goal_achieved", False)


def include_adults_switched_on(storage) -> None:
    """Adults just joined the goal: any adult the baseline doesn't know counts from now.

    Without this, an adult missing from the baseline would bring every point
    they've ever earned. The caller saves.
    """
    baseline = storage.get_setting(BASELINE_KEY, None)
    if not isinstance(baseline, dict):
        return
    updated = dict(baseline)
    for child in storage.get_children():
        if getattr(child, "is_adult", False) and child.id not in updated:
            updated[child.id] = _earned(child)
    storage.set_setting(BASELINE_KEY, updated)


def seed_family_goal_baseline(storage) -> bool:
    """One-time upgrade step: keep each existing goal's number. Returns True if it seeded."""
    if isinstance(storage.get_setting(BASELINE_KEY, None), dict):
        return False
    storage.set_setting(BASELINE_KEY, {c.id: _earned(c) - _balance(c) for c in storage.get_children()})
    return True
