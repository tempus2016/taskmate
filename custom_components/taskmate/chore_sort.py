"""Family-wide chore order on the cards (#1231).

Every card that lists a child's chores (child, kiosk, routine, sticker chart)
and the watch's "next chore" follow the ``chore_order`` the sensors publish for
that child. This module decides what that list is:

* ``manual`` (the default) is each child's own order from the reorder card or
  the panel, exactly as before. Chores missing from it follow in the order
  they were added.
* ``time``, ``name`` and ``added`` sort automatically, so a chore added later
  lands in its place without anyone reordering it. The child's manual order is
  kept untouched underneath, ready for when the setting goes back to manual.

The same sort backs the panel's "sort everyone once" action, which writes the
result into every child's manual order and leaves the setting on manual.
"""

from __future__ import annotations

from typing import Any

CHORE_SORT_MODES: tuple[str, ...] = ("manual", "time", "name", "added")
CHORE_SORT_PRESETS: tuple[str, ...] = ("time", "name", "added")
CHORE_SORT_SETTING = "chore_sort"


def chore_sort_mode(storage: Any) -> str:
    """The stored mode, or ``manual`` when unset or unknown."""
    value = storage.get_setting(CHORE_SORT_SETTING, "manual")
    return value if value in CHORE_SORT_MODES else "manual"


def _minutes(hhmm: Any) -> int | None:
    try:
        h, m = (int(x) for x in str(hhmm).split(":"))
    except (TypeError, ValueError):
        return None
    return h * 60 + m


def _time_key(chore: Any, period_starts: dict[str, int]) -> int:
    """When in the day a chore comes up, in minutes; anytime sorts first."""
    starts = [
        m for t in (getattr(chore, "times", None) or []) if (m := _minutes(getattr(t, "start", None))) is not None
    ]
    if starts:
        return min(starts)
    category = getattr(chore, "time_category", "anytime") or "anytime"
    if category == "anytime":
        return -1
    # A period that no longer exists sorts after every real one.
    return period_starts.get(category, 24 * 60)


def sorted_chore_ids(
    mode: str,
    chores: list,
    manual_order: list[str] | None = None,
    periods: list[dict] | None = None,
) -> list[str]:
    """Chore ids in ``mode`` order. ``chores`` must be in the order they were added.

    Ties keep the child's manual order, then the order the chores were added,
    so sorting by time of day still respects a hand-made order within a period.
    """
    manual_rank: dict[str, int] = {}
    for index, chore_id in enumerate(manual_order or []):
        manual_rank.setdefault(chore_id, index)
    unranked = len(manual_rank)
    added = {c.id: i for i, c in enumerate(chores)}

    if mode == "added":
        return [c.id for c in chores]
    if mode == "name":
        return [c.id for c in sorted(chores, key=lambda c: ((getattr(c, "name", "") or "").casefold(), added[c.id]))]
    if mode == "time":
        starts = {p["id"]: m for p in (periods or []) if (m := _minutes(p.get("start"))) is not None}
        return [
            c.id
            for c in sorted(chores, key=lambda c: (_time_key(c, starts), manual_rank.get(c.id, unranked), added[c.id]))
        ]
    # manual: the stored list as-is (the cards append the rest in added order).
    return list(manual_order or [])


def effective_chore_order(coordinator: Any, child: Any, chores: list | None = None) -> list[str]:
    """The ``chore_order`` the cards should follow for ``child``."""
    manual = list(getattr(child, "chore_order", None) or [])
    mode = chore_sort_mode(coordinator.storage)
    if mode == "manual":
        return manual
    if chores is None:
        chores = coordinator.storage.get_chores()
    periods = coordinator.get_time_periods() if mode == "time" else None
    return sorted_chore_ids(mode, chores, manual, periods)
