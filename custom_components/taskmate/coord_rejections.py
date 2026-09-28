"""Reject reasons (#976) mixin for TaskMateCoordinator.

A parent can say why a chore submission or a reward claim was rejected.
Rejecting deletes the completion / claim, so the reason can't live on the
record itself: it goes into a small family-wide log in storage instead
(``rejections``), kept for ``REJECTION_KEEP_DAYS`` days and capped at
``REJECTION_KEEP_MAX`` rows. Only rejections that carry a reason are logged —
a rejection without one behaves exactly as it always has.

The log feeds two things: the child's card (``rejections_for_child``, via
the overview sensor's child summary) and the activity feed
(``recent_rejections``, via the activity sensor's transactions).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from .const import NOTIF_TYPE_ITEM_REJECTED
from .models import REJECT_REASON_MAX, clean_label, format_datetime, generate_id, parse_datetime

_LOGGER = logging.getLogger(__name__)

REJECTION_KEEP_DAYS = 7
REJECTION_KEEP_MAX = 50
# How long a reason stays on the child's card. A newer attempt at the same
# chore (or a new claim of the same reward) retires it sooner.
REJECTION_CARD_HOURS = 24
# At most this many reasons per child on the overview sensor (16 KB cap).
REJECTION_CARD_MAX = 5


def clean_reject_reason(value) -> str:
    """Single-line, trimmed, capped reason text ("" when none)."""
    return clean_label(value, REJECT_REASON_MAX)


class RejectionsMixin:
    """Record why something was rejected, and tell the child."""

    def _record_rejection(self, kind: str, child_id: str, item_id: str, item_name: str, reason: str) -> None:
        """Log a reasoned rejection. ``kind`` is "chore" or "reward"; no-op without a reason."""
        if not reason or not child_id:
            return
        now = dt_util.now()
        cutoff = now - timedelta(days=REJECTION_KEEP_DAYS)
        rows = [r for r in self.storage.get_rejections() if (_at(r) or now) >= cutoff]
        rows.append(
            {
                "id": generate_id(),
                "kind": kind,
                "child_id": child_id,
                "item_id": item_id,
                "item_name": item_name,
                "reason": reason,
                # UTC, like every stored timestamp: the activity feed sorts
                # these ISO strings against transaction times.
                "rejected_at": format_datetime(now),
            }
        )
        self.storage.set_rejections(rows[-REJECTION_KEEP_MAX:])

    async def _async_notify_rejected(self, kind: str, child, item_name: str, reason: str) -> None:
        """Tell the child their chore / claim was sent back (opt-in notification type)."""
        if child is None or not getattr(self, "notifications", None):
            return
        await self.notifications.fire(
            NOTIF_TYPE_ITEM_REJECTED,
            {
                "child_name": child.name,
                "child_id": child.id,
                "kind": kind,
                "item_name": item_name,
                "reason": reason,
                "reason_text": f": {reason}" if reason else "",
            },
            only_recipients={f"child:{child.id}"},
        )

    def recent_rejections(self) -> list[dict]:
        """Every logged rejection still inside the keep window, oldest first."""
        cutoff = dt_util.now() - timedelta(days=REJECTION_KEEP_DAYS)
        return [r for r in self.storage.get_rejections() if (_at(r) or cutoff) > cutoff]

    def rejections_for_child(self, child_id: str) -> list[dict]:
        """The reasons still worth showing on this child's card, newest first.

        One per chore / reward (the latest), from the last
        ``REJECTION_CARD_HOURS`` hours, and only while the child hasn't had
        another go at it since — once they redo the chore or claim the reward
        again, the old reason no longer describes anything on the card.
        """
        rows = [r for r in self.storage.get_rejections() if r.get("child_id") == child_id]
        if not rows:
            return []
        cutoff = dt_util.now() - timedelta(hours=REJECTION_CARD_HOURS)
        latest_try: dict[tuple[str, str], datetime] = {}
        for c in self.storage.get_completions():
            if c.child_id == child_id and c.completed_at:
                key = ("chore", c.chore_id)
                latest_try[key] = max(latest_try.get(key, c.completed_at), c.completed_at)
        for c in self.storage.get_reward_claims():
            if c.child_id == child_id and c.claimed_at:
                key = ("reward", c.reward_id)
                latest_try[key] = max(latest_try.get(key, c.claimed_at), c.claimed_at)
        out: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for r in reversed(rows):
            key = (str(r.get("kind", "")), str(r.get("item_id", "")))
            at = _at(r)
            if key in seen or at is None or at < cutoff:
                continue
            seen.add(key)
            tried = latest_try.get(key)
            if tried is not None and tried > at:
                continue
            out.append({"kind": key[0], "id": key[1], "reason": r.get("reason", ""), "at": r.get("rejected_at")})
            if len(out) >= REJECTION_CARD_MAX:
                break
        return out


def _at(row: dict) -> datetime | None:
    try:
        return parse_datetime(row.get("rejected_at"))
    except (TypeError, ValueError):
        return None
