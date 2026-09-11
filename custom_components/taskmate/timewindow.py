"""Shared "HH:MM" time-of-day window helpers.

Used by per-child quiet hours (notifications) and by time-locked rewards
(#857). Both need the same semantics, including windows that wrap midnight.
"""

from __future__ import annotations

from datetime import datetime


def parse_hhmm(value: str) -> tuple[int, int] | None:
    """Parse "HH:MM" into (hour, minute); None if blank/malformed."""
    if not value:
        return None
    try:
        hour, minute = map(int, value.split(":", 1))
    except (ValueError, AttributeError):
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def is_within_window(start: str, end: str, now: datetime) -> bool:
    """True if ``now`` falls inside the [start, end) HH:MM window.

    Both bounds must be set, else the window is disabled and this returns
    False. A start later than the end denotes an overnight window (e.g.
    20:00-07:00). The end bound is exclusive so equal bounds (07:00-07:00)
    are treated as disabled rather than as a full 24 hours.
    """
    s = parse_hhmm(start)
    e = parse_hhmm(end)
    if s is None or e is None or s == e:
        return False
    cur = now.hour * 60 + now.minute
    start_m = s[0] * 60 + s[1]
    end_m = e[0] * 60 + e[1]
    if start_m < end_m:
        return start_m <= cur < end_m
    # Overnight window: active from start through midnight to end.
    return cur >= start_m or cur < end_m


def has_window(start: str, end: str) -> bool:
    """True if start/end describe a usable window (both parse and differ)."""
    s = parse_hhmm(start)
    e = parse_hhmm(end)
    return s is not None and e is not None and s != e
