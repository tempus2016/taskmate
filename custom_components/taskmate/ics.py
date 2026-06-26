"""ICS (iCalendar) feed generation for TaskMate chores (FEAT-10).

Pure-ish helpers that turn the chore calendar projection into an RFC 5545 feed a
calendar app (Google/Apple/Outlook) can subscribe to. Token auth + the HTTP view
live in ``http_calendar.py``; this module only builds text.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

PRODID = "-//TaskMate//Chores//EN"


def _escape(text: str) -> str:
    """Escape a value per RFC 5545 (backslash, comma, semicolon, newline)."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold(line: str) -> str:
    """Fold a content line to <=75 octets with CRLF + space continuation."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    out = []
    while len(raw) > 75:
        # Don't split a multibyte char: back off to a UTF-8 boundary.
        cut = 75
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n ".join(out)


def _dt_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _date(d: date) -> str:
    return d.strftime("%Y%m%d")


def make_uid(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"{digest}@taskmate"


def build_calendar(events: list[dict], now: datetime, name: str = "TaskMate Chores") -> str:
    """Render ``events`` (dicts: uid, summary, description, start, end, all_day)
    into an ICS document. ``start``/``end`` are dates (all-day) or aware datetimes."""
    stamp = _dt_utc(now)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
    ]
    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev['uid']}")
        lines.append(f"DTSTAMP:{stamp}")
        if ev["all_day"]:
            lines.append(f"DTSTART;VALUE=DATE:{_date(ev['start'])}")
            lines.append(f"DTEND;VALUE=DATE:{_date(ev['end'])}")
        else:
            lines.append(f"DTSTART:{_dt_utc(ev['start'])}")
            lines.append(f"DTEND:{_dt_utc(ev['end'])}")
        lines.append(_fold(f"SUMMARY:{_escape(ev['summary'])}"))
        if ev.get("description"):
            lines.append(_fold(f"DESCRIPTION:{_escape(ev['description'])}"))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def build_chore_events(coordinator, start_day: date, end_day: date) -> list[dict]:
    """Project each child's scheduled chores over [start_day, end_day] into event dicts."""
    from .calendar import _chore_applies_to_child, _chore_description

    events: list[dict] = []
    children = coordinator.storage.get_children()
    chores = coordinator.storage.get_chores()
    for child in children:
        day = start_day
        while day <= end_day:
            if not coordinator._is_child_on_vacation(child, day):
                for chore in chores:
                    if not _chore_applies_to_child(coordinator, chore, child.id, day):
                        continue
                    window = coordinator._time_category_window(
                        getattr(chore, "time_category", "anytime"), day
                    )
                    summary = f"{chore.name} — {child.name}"
                    desc = _chore_description(chore)
                    if window is None:
                        events.append({
                            "uid": make_uid(chore.id, child.id, day.isoformat(), "allday"),
                            "summary": summary, "description": desc,
                            "start": day, "end": day + timedelta(days=1), "all_day": True,
                        })
                    else:
                        start_dt, end_dt = window
                        events.append({
                            "uid": make_uid(chore.id, child.id, day.isoformat(), "timed"),
                            "summary": summary, "description": desc,
                            "start": _ensure_aware(start_dt),
                            "end": _ensure_aware(end_dt), "all_day": False,
                        })
            day += timedelta(days=1)
    return events


def _ensure_aware(dt: datetime) -> datetime:
    from homeassistant.util import dt as dt_util
    if dt.tzinfo is None:
        return dt.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return dt
