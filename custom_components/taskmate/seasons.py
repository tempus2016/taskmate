"""Seasonal themes for the child and kiosk cards.

A parent switches each season on in Settings. While one is on and today falls
in its window, the overview sensor names it, so every card dresses itself the
same way without each working out the dates on its own.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .const import SEASONS


def active_season(settings: dict[str, Any], today: date) -> str:
    """The season to show today, or "" when none is on and in its window."""
    for season, (key, start, end) in SEASONS.items():
        if settings.get(key) not in (True, "true"):
            continue
        if start <= (today.month, today.day) <= end:
            return season
    return ""
