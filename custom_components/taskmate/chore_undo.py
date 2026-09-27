"""Child undo policy for chore completions (#918).

One place decides whether a child may take back one of their own completions,
so the ``taskmate.undo_chore`` service and the sensor records the cards read
can never disagree. The rules:

* The global window (``chore_undo_seconds``) is 0 by default, which switches
  the feature off entirely — every completion stays parent-only, as before.
* Only completions a child submitted carry ``child_undo_allowed``. Records
  written before the feature existed load with it False, so they stay
  parent-only.
* A parent's review (approve, or undo-approval) clears the flag for good.
* A pending submission can be withdrawn for as long as it stays unreviewed.
* An auto-approved completion can be undone until ``completed_at`` plus the
  window.

This module grants nothing on its own: the caller must still apply the
linked-child authorisation rule for the completion's stored child.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util


def undo_window_seconds(storage: Any) -> int:
    """The configured window, as a plain int (0 when unset or unreadable)."""
    value = storage.get_chore_undo_seconds()
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _affected(completion: Any, completions: list) -> list:
    """The records an undo of ``completion`` would reverse.

    Undoing a main chore also removes that day's bonus sub-tasks (see
    ``_reverse_completion_awards``), so a child may only do it when every one
    of them is still theirs to undo.
    """
    affected = [completion]
    if not getattr(completion, "bonus_subtask_id", ""):
        day = dt_util.as_local(completion.completed_at).date()
        affected.extend(
            c
            for c in completions
            if c.id != completion.id
            and c.chore_id == completion.chore_id
            and c.child_id == completion.child_id
            and c.bonus_subtask_id
            and dt_util.as_local(c.completed_at).date() == day
        )
    return affected


def child_undo_metadata(completion: Any, completions: list, window_seconds: int) -> dict:
    """Return the child-undo fields to publish for ``completion``.

    ``{"child_undo_pending": True}`` for a withdrawable pending submission,
    ``{"child_undo_until": <iso>}`` for an auto-approved one still inside the
    window, and ``{}`` otherwise. Empty for the common case keeps the sensor
    attributes small.
    """
    if window_seconds <= 0:
        return {}
    if getattr(completion, "child_undo_allowed", False) is not True:
        return {}
    affected = _affected(completion, completions)
    if any(getattr(c, "child_undo_allowed", False) is not True for c in affected):
        return {}
    approved = [c for c in affected if c.approved]
    if not approved:
        return {"child_undo_pending": True}
    deadline = min(c.completed_at for c in approved) + timedelta(seconds=window_seconds)
    return {"child_undo_until": deadline.isoformat()}


def child_can_undo(completion: Any, completions: list, window_seconds: int, now: datetime | None = None) -> bool:
    """True if a child may undo ``completion`` right now."""
    meta = child_undo_metadata(completion, completions, window_seconds)
    if meta.get("child_undo_pending"):
        return True
    until = meta.get("child_undo_until")
    if not until:
        return False
    return (now or dt_util.now()) < datetime.fromisoformat(until)
