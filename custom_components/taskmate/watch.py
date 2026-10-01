"""Watch support (#978): a compact per-child summary and "complete next chore".

TaskMate can't ship watch code of its own — Apple Watch complications and
Wear OS complications/tiles are built in the Home Assistant companion apps
from entities and templates. This module supplies the two backend pieces
they need: the numbers behind the per-child watch sensor, and the rule for
which chore ``taskmate.complete_next_chore`` ticks off.
"""

from __future__ import annotations

from homeassistant.util import dt as dt_util

# Complication text has to stay short; long chore names are clipped.
NEXT_CHORE_NAME_MAX = 40

WATCH_STATUS_TO_DO = "to_do"
WATCH_STATUS_ALL_DONE = "all_done"
WATCH_STATUS_NO_CHORES = "no_chores"

# English fallback for the sensor state, used until (or if) the HA entity
# translations for the configured language can't be loaded. "#" stands for
# the count: hassfest rejects {placeholders} in entity state translations.
COUNT_TOKEN = "#"
DEFAULT_STATE_STRINGS = {
    "left": "# left",
    WATCH_STATUS_ALL_DONE: "All done",
    WATCH_STATUS_NO_CHORES: "No chores",
}

_BOARD_CACHE_ATTR = "_taskmate_watch_board_cache"


def chore_needs_input(coordinator, chore) -> bool:
    """True for a chore a single tap from a watch can't finish.

    A photo-proof chore needs a picture, an open-ended one needs a note, a
    timed one runs a clock, and a teamwork one only completes when the whole
    team has joined — none of those make sense from a wrist.
    """
    if getattr(chore, "require_photo", False) or getattr(chore, "open_ended", False):
        return True
    if (getattr(chore, "task_type", "standard") or "standard") == "timed":
        return True
    return bool(coordinator.teamwork_size(chore))


def next_chore_for_child(coordinator, child_id: str):
    """The chore ``complete_next_chore`` would complete for this child, or None.

    "Next" follows the child card: the child's custom ``chore_order`` first,
    then the remaining chores in their default order. Only chores the child
    still owes today (``get_due_chores_for_child``) that a single tap can
    finish are considered.
    """
    child = coordinator.get_child(child_id)
    if child is None:
        return None
    candidates = [c for c in coordinator.get_due_chores_for_child(child_id) if not chore_needs_input(coordinator, c)]
    if not candidates:
        return None
    # indexOf semantics, as on the card: a duplicated id keeps its first slot.
    rank: dict[str, int] = {}
    for index, chore_id in enumerate(getattr(child, "chore_order", None) or []):
        rank.setdefault(chore_id, index)
    unranked = len(rank)
    # sorted() is stable, so unranked chores keep their default order.
    return sorted(candidates, key=lambda c: rank.get(c.id, unranked))[0]


def today_board(coordinator) -> dict:
    """``get_today_board`` once per coordinator update, shared by every child's watch
    sensor and the chore board sensor (#1017)."""
    key = (
        id(coordinator.data),
        getattr(coordinator, "external_state_version", 0),
        dt_util.as_local(dt_util.now()).date().isoformat(),
    )
    cached = getattr(coordinator, _BOARD_CACHE_ATTR, None)
    if cached and cached[0] == key:
        return cached[1]
    board = coordinator.get_today_board()
    setattr(coordinator, _BOARD_CACHE_ATTR, (key, board))
    return board


def watch_summary(coordinator, child_id: str) -> dict | None:
    """Today's numbers for one child, sized for a watch complication.

    ``left`` counts every chore still owed today (including ones that need a
    photo or a timer); ``done`` counts the ones completed, whether approved or
    still waiting for a parent. ``progress`` is ``done / total`` in 0–1, the
    range a gauge/ring complication expects — 1.0 when nothing was due.
    """
    child = coordinator.get_child(child_id)
    if child is None:
        return None
    entry = next((e for e in today_board(coordinator)["children"] if e["child_id"] == child_id), None)
    items = entry["chores"] if entry else []
    total = len(items)
    left = sum(1 for i in items if i["status"] in ("todo", "missed"))
    done = sum(1 for i in items if i["status"] in ("done", "pending"))
    if total == 0:
        status = WATCH_STATUS_NO_CHORES
    elif left == 0:
        status = WATCH_STATUS_ALL_DONE
    else:
        status = WATCH_STATUS_TO_DO
    summary = {
        "child_id": child.id,
        "status": status,
        "left": left,
        "done": done,
        "total": total,
        "progress": round(done / total, 2) if total else 1.0,
        "points": child.points,
        "streak": getattr(child, "current_streak", 0) or 0,
    }
    if left:
        nxt = next_chore_for_child(coordinator, child_id)
        if nxt is not None:
            summary["next_chore"] = (nxt.name or "")[:NEXT_CHORE_NAME_MAX]
    return summary


def watch_state(summary: dict | None, strings: dict[str, str]) -> str | None:
    """The short sensor state: "3 left", "All done" or "No chores"."""
    if summary is None:
        return None
    status = summary["status"]
    if status == WATCH_STATUS_TO_DO:
        template = strings.get("left") or ""
        if COUNT_TOKEN not in template:
            template = DEFAULT_STATE_STRINGS["left"]
        return template.replace(COUNT_TOKEN, str(summary["left"]), 1)
    return strings.get(status) or DEFAULT_STATE_STRINGS[status]
