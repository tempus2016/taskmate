"""Seasonal themes and the windows season event packs install in.

A parent switches each season's theme on in Settings. While one is on and
today falls in its window, the overview sensor names it, so every card dresses
itself the same way without each working out the dates on its own.

Halloween, Christmas and Summer have fixed dates. Easter is the week up to
Easter Sunday, worked out for each year; Back to school is the 14 days from a
first school day the parent sets, so it has no window until one is set.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .const import SEASON_ORDER, SEASON_SCHOOL_DAYS, SEASON_SCHOOL_START_KEY, SEASON_THEME_KEYS, SEASONS


def easter_sunday(year: int) -> date:
    """Western (Gregorian) Easter Sunday: the anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return date(year, month, day + 1)


def school_start(settings: dict[str, Any]) -> date | None:
    """The first school day the parent set, or None."""
    raw = settings.get(SEASON_SCHOOL_START_KEY)
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def season_window(season: str, year: int, settings: dict[str, Any]) -> tuple[date, date] | None:
    """The season's window that starts in ``year`` (both ends inclusive), or None."""
    if season in SEASONS:
        _key, (sm, sd), (em, ed) = SEASONS[season]
        return date(year, sm, sd), date(year, em, ed)
    if season == "easter":
        sunday = easter_sunday(year)
        return sunday - timedelta(days=6), sunday
    if season == "back_to_school":
        start = school_start(settings)
        if start is None or start.year != year:
            return None
        return start, start + timedelta(days=SEASON_SCHOOL_DAYS - 1)
    return None


def current_window(season: str, today: date, settings: dict[str, Any]) -> tuple[date, date] | None:
    """The window ``today`` falls in. A window that started last year counts
    (Back to school can run over New Year)."""
    for year in (today.year, today.year - 1):
        window = season_window(season, year, settings)
        if window and window[0] <= today <= window[1]:
            return window
    return None


def next_window(season: str, today: date, settings: dict[str, Any]) -> tuple[date, date] | None:
    """Today's window, else the next one to come (None when there is none)."""
    window = current_window(season, today, settings)
    if window:
        return window
    for year in (today.year, today.year + 1):
        window = season_window(season, year, settings)
        if window and window[0] > today:
            return window
    return None


def _on(value: Any) -> bool:
    return value in (True, "true")


def active_season(settings: dict[str, Any], today: date) -> str:
    """The season to show today, or "" when none is on and in its window."""
    for season in SEASON_ORDER:
        if not _on(settings.get(SEASON_THEME_KEYS[season])):
            continue
        if current_window(season, today, settings):
            return season
    return ""
