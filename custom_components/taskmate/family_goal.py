"""Family co-op goal progress (FEAT-4, #1282).

The goal counts points the children have earned since it started, not their
current balances: spending or redeeming personal points never moves it back,
and a new goal starts at 0. Each child's ``total_points_earned`` at the start
is kept in the ``family_goal_baseline`` setting ({child_id: earned}). A child
missing from it (added after the goal started) counts from 0. Penalties don't
lower ``total_points_earned``, so they don't lower the goal either. Adult
profiles are left out (#1061).

Installs from before #1282 get a baseline of ``earned - balance`` per child on
first load (``seed_family_goal_baseline``), so an existing goal shows the same
number it showed before the upgrade and only counts new earnings from then on.
Until a baseline exists (e.g. straight after restoring an older backup) the
goal falls back to the combined balances, as it always did.
"""

from __future__ import annotations

from typing import Any

BASELINE_KEY = "family_goal_baseline"


def _goal_children(storage) -> list[Any]:
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
    """Points the children have earned towards the current family goal."""
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
    storage.set_setting(BASELINE_KEY, {c.id: _earned(c) for c in _goal_children(storage)})
    storage.set_setting("family_goal_achieved", False)


def seed_family_goal_baseline(storage) -> bool:
    """One-time upgrade step: keep each existing goal's number. Returns True if it seeded."""
    if isinstance(storage.get_setting(BASELINE_KEY, None), dict):
        return False
    storage.set_setting(BASELINE_KEY, {c.id: _earned(c) - _balance(c) for c in _goal_children(storage)})
    return True
