"""Birthday mode (#924).

Each child may carry an optional ``birthday`` ("YYYY-MM-DD", or "MM-DD" when
the family would rather not show an age). On that day TaskMate celebrates it:

* chore points are multiplied by ``birthday_points_multiplier`` (default 2×),
  on top of the weekend multiplier in ``_award_points``;
* with ``birthday_chores_off`` on, non-mandatory chores are hidden for the day
  and the day can't break the streak;
* the built-in "Birthday" badge is awarded and a ``birthday`` celebration fires
  once per child per day (guarded, so a restart mid-birthday doesn't repeat it).

A 29 February birthday is celebrated on 28 February in non-leap years.
"""

from __future__ import annotations

import calendar
import logging
import re
from datetime import date

from homeassistant.util import dt as dt_util

from . import notify_strings

_LOGGER = logging.getLogger(__name__)

DEFAULT_BIRTHDAY_MULTIPLIER = 2.0

_BIRTHDAY_RE = re.compile(r"^(?:(\d{4})-|--)?(\d{2})-(\d{2})$")


def parse_birthday(value: str) -> tuple[int | None, int, int]:
    """Parse a stored birthday into ``(year | None, month, day)``.

    Accepts "YYYY-MM-DD", "MM-DD" and the ISO 8601 year-less "--MM-DD".
    Raises ValueError for anything else, including impossible dates
    (29 February is valid without a year, and in a leap year).
    """
    m = _BIRTHDAY_RE.match((value or "").strip())
    if not m:
        raise ValueError(f"Birthday must be YYYY-MM-DD or MM-DD, got {value!r}")
    year = int(m.group(1)) if m.group(1) else None
    month, day = int(m.group(2)), int(m.group(3))
    # 2000 is a leap year, so a year-less 02-29 validates.
    date(year or 2000, month, day)
    return year, month, day


def normalize_birthday(value: str) -> str:
    """Canonical stored form: "YYYY-MM-DD" or "MM-DD"; "" clears it."""
    value = (value or "").strip()
    if not value:
        return ""
    year, month, day = parse_birthday(value)
    if year is not None:
        if date(year, month, day) > dt_util.as_local(dt_util.now()).date():
            raise ValueError("Birthday can't be in the future")
        return f"{year:04d}-{month:02d}-{day:02d}"
    return f"{month:02d}-{day:02d}"


def birthday_in_year(value: str, year: int) -> date | None:
    """The date the birthday is celebrated in ``year`` (None if unset/invalid).

    29 February falls back to 28 February in non-leap years.
    """
    try:
        _year, month, day = parse_birthday(value)
    except ValueError:
        return None
    if month == 2 and day == 29 and not calendar.isleap(year):
        day = 28
    return date(year, month, day)


def is_birthday_on(value: str, on: date) -> bool:
    """True when a birthday string is celebrated on ``on``."""
    if not value or not isinstance(value, str):
        return False
    return birthday_in_year(value, on.year) == on


class BirthdaysMixin:
    """Mixin providing birthday detection, the multiplier and the day off."""

    def _birthday_today(self) -> date:
        return dt_util.as_local(dt_util.now()).date()

    def is_birthday(self, child, on: date | None = None) -> bool:
        if child is None:
            return False
        return is_birthday_on(getattr(child, "birthday", "") or "", on or self._birthday_today())

    def birthday_age(self, child, on: date | None = None) -> int | None:
        """Age the child turns on ``on`` — None when no birth year was given."""
        try:
            year, _m, _d = parse_birthday(str(getattr(child, "birthday", "") or ""))
        except ValueError:
            return None
        if year is None:
            return None
        return (on or self._birthday_today()).year - year

    def birthday_multiplier(self) -> float:
        try:
            value = float(self.storage.get_setting("birthday_points_multiplier", DEFAULT_BIRTHDAY_MULTIPLIER))
        except (ValueError, TypeError):
            return DEFAULT_BIRTHDAY_MULTIPLIER
        # Below 1 would make a birthday cost the child points.
        return max(1.0, value)

    def birthday_chores_off(self) -> bool:
        v = self.storage.get_setting("birthday_chores_off", False)
        return v is True or str(v).lower() == "true"

    def is_birthday_day_off(self, child, on: date | None = None) -> bool:
        """True when ``child`` has the day off: chores-off is on and it's their birthday."""
        return self.birthday_chores_off() and self.is_birthday(child, on)

    def birthday_summary(self, child) -> dict | None:
        """Compact sensor payload for a child whose birthday is today, else None."""
        if not self.is_birthday(child):
            return None
        out: dict = {"multiplier": self.birthday_multiplier()}
        age = self.birthday_age(child)
        if age is not None:
            out["age"] = age
        if self.birthday_chores_off():
            out["chores_off"] = True
        return out

    async def async_check_birthdays(self, refresh: bool = True) -> list[str]:
        """Celebrate today's birthdays once each. Returns the child ids celebrated.

        Runs at midnight, at startup (HA may have been off at midnight) and when
        a parent edits a child, so setting a birthday on the day still counts.
        """
        today = self._birthday_today()
        today_str = today.isoformat()
        done = self.storage.get_setting("birthday_celebrated", {})
        done = dict(done) if isinstance(done, dict) else {}
        celebrated: list[str] = []
        for child in self.storage.get_children():
            if not self.is_birthday(child, today) or done.get(child.id) == today_str:
                continue
            done[child.id] = today_str
            celebrated.append(child.id)
            # Persist the guard before the side-effects, so a failure below
            # can't make the next run celebrate twice.
            self.storage.set_setting("birthday_celebrated", done)
            age = self.birthday_age(child, today)
            if getattr(self, "badges", None):
                await self.badges.evaluate_for_child(child.id, "birthday")
            await self._celebrate(
                child,
                "birthday",
                notify_strings.render(self.hass, "celebrate_birthday", {"child_name": child.name}),
                tier=3,
                extra={"multiplier": self.birthday_multiplier(), **({"age": age} if age is not None else {})},
            )
            _LOGGER.info("Birthday celebrated for %s", child.name)
        # Drop guards for children who no longer exist.
        known = {c.id for c in self.storage.get_children()}
        stale = [cid for cid in done if cid not in known]
        for cid in stale:
            done.pop(cid)
        if stale:
            self.storage.set_setting("birthday_celebrated", done)
        if celebrated or stale:
            await self.storage.async_save()
            if refresh:
                await self.async_refresh()
        return celebrated
