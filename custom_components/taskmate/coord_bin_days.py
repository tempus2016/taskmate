"""Bin-day chores: a "put the bins out" chore raised from the council's calendar.

The parent picks one or more calendars that carry collection days (Waste
Collection Schedule, a council iCal, a hand-made local calendar). The
evening before a collection, at the put-out time, TaskMate looks at
tomorrow's events and raises one chore per bin: "♻️ Put the Recycling out".

The chore is a reactive one-off: it lives until the end of that evening and
then goes. Either the first child to do it gets the points, or the job
rotates round the chosen children one collection at a time.

Optionally a second chore, "Bring the Recycling in", appears on collection
day itself at the bring-in time.

Each event is only ever turned into a chore once, however often the
calendar is read.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from . import notify_strings

_LOGGER = logging.getLogger(__name__)

BIN_DAY_MODES = ("first_come", "rotate")
BIN_DAY_MAX_CALENDARS = 5
BIN_DAY_MAX_POINTS = 1000
DEFAULT_PUT_OUT_TIME = "18:00"
DEFAULT_BRING_IN_TIME = "16:00"
# Re-read tomorrow's events this often after the put-out time, so a
# collection added late in the evening still gets its chore.
_REQUERY_EVERY = timedelta(minutes=15)
_SEEN_KEEP_DAYS = 14
_SUMMARY_MAX = 60
# A calendar anyone can write to can raise chores, so it is bounded the same
# way as the shopping list: this many bin chores on the board at once, this
# many new ones per read. Skipped events are picked up on the next read.
BIN_DAY_MAX_OPEN = 10
BIN_DAY_MAX_PER_POLL = 5
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

# First match wins; the summary is checked in lower case.
_BIN_EMOJI = (
    (("recycl", "blue", "paper", "card", "plastic", "tin"), "♻️"),
    (("garden", "green", "brown", "compost", "food", "organic"), "🌿"),
    (("glass", "bottle"), "🍾"),
)
_DEFAULT_EMOJI = "🗑️"


def bin_emoji(summary: str) -> str:
    text = (summary or "").lower()
    for words, emoji in _BIN_EMOJI:
        if any(w in text for w in words):
            return emoji
    return _DEFAULT_EMOJI


def _parse_time(value: Any, default: str) -> time:
    m = _TIME_RE.match(str(value or "")) or _TIME_RE.match(default)
    return time(int(m.group(1)), int(m.group(2)))


def _event_day(event: dict[str, Any]) -> date | None:
    """The local date an event starts on (all-day or timed)."""
    start = event.get("start")
    if isinstance(start, dict):
        start = start.get("date") or start.get("dateTime")
    if isinstance(start, datetime):
        return dt_util.as_local(start).date()
    if isinstance(start, date):
        return start
    if not isinstance(start, str) or not start:
        return None
    try:
        if len(start) == 10:
            return date.fromisoformat(start)
        parsed = datetime.fromisoformat(start)
        return dt_util.as_local(parsed).date() if parsed.tzinfo else parsed.date()
    except ValueError:
        return None


class BinDaysMixin:
    """Collection-day chores from calendar entities."""

    # ── settings ─────────────────────────────────────────────────────────

    def bin_day_enabled(self) -> bool:
        return bool(self.storage.get_setting("bin_day_enabled", False))

    def bin_day_calendars(self) -> list[str]:
        raw = self.storage.get_setting("bin_day_calendars", [])
        if not isinstance(raw, list):
            return []
        return [c for c in raw if isinstance(c, str) and c.startswith("calendar.")][:BIN_DAY_MAX_CALENDARS]

    def bin_day_mode(self) -> str:
        mode = str(self.storage.get_setting("bin_day_mode", "first_come") or "first_come")
        return mode if mode in BIN_DAY_MODES else "first_come"

    def bin_day_points(self) -> int:
        try:
            return max(0, min(BIN_DAY_MAX_POINTS, int(self.storage.get_setting("bin_day_points", 5))))
        except (TypeError, ValueError):
            return 5

    def bin_day_children(self) -> list[str]:
        """Who can be given the job: the chosen children, else every child who isn't an adult."""
        children = self.storage.get_children()
        chosen = self.storage.get_setting("bin_day_children", [])
        known = {c.id for c in children}
        if isinstance(chosen, list):
            picked = [cid for cid in chosen if cid in known]
            if picked:
                return picked
        return [c.id for c in children if not getattr(c, "is_adult", False)]

    # ── calendar ─────────────────────────────────────────────────────────

    async def _async_bin_events(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Every event on the chosen calendars between ``start`` and ``end``."""
        out: list[dict[str, Any]] = []
        for entity_id in self.bin_day_calendars():
            try:
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {"entity_id": entity_id, "start_date_time": start, "end_date_time": end},
                    blocking=True,
                    return_response=True,
                )
            except Exception as err:  # noqa: BLE001 - one broken calendar must not stop the rest
                _LOGGER.debug("TaskMate: could not read bin days from %s: %s", entity_id, err)
                continue
            events: Any = []
            if isinstance(response, dict):
                bucket = response.get(entity_id, response)
                events = bucket.get("events", []) if isinstance(bucket, dict) else bucket
            for event in events or []:
                if not isinstance(event, dict):
                    continue
                summary = str(event.get("summary") or "").strip()[:_SUMMARY_MAX]
                day = _event_day(event)
                if summary and day:
                    out.append({"calendar": entity_id, "summary": summary, "date": day.isoformat()})
        return out

    async def async_bin_day_preview(self, days: int = 14) -> list[dict[str, Any]]:
        """The next collections, for the Settings page to show the setup works."""
        now = dt_util.now()
        start = dt_util.start_of_local_day(now)
        events = await self._async_bin_events(start, start + timedelta(days=max(1, min(days, 31))))
        seen: set[tuple[str, str]] = set()
        out = []
        for e in sorted(events, key=lambda e: (e["date"], e["summary"])):
            key = (e["date"], e["summary"].lower())
            if key in seen:
                continue
            seen.add(key)
            out.append({**e, "emoji": bin_emoji(e["summary"])})
        return out

    # ── the tick ─────────────────────────────────────────────────────────

    def _bin_state(self) -> dict[str, Any]:
        state = self.storage.get_section("bin_days", dict)
        if not isinstance(state.get("seen"), dict):
            state["seen"] = {}
        return state

    async def async_check_bin_days(self) -> int:
        """Raise put-out (and bring-in) chores when their time comes. Returns how many."""
        if not self.bin_day_enabled() or not self.bin_day_calendars():
            return 0
        now = dt_util.now()
        local = dt_util.as_local(now)
        today = local.date()
        state = self._bin_state()
        created = 0
        dirty = False
        open_jobs = self._open_bin_jobs(state)

        def _room() -> bool:
            return created < BIN_DAY_MAX_PER_POLL and open_jobs + created < BIN_DAY_MAX_OPEN

        if local.time() >= _parse_time(self.storage.get_setting("bin_day_put_out_time"), DEFAULT_PUT_OUT_TIME):
            try:
                last = datetime.fromisoformat(str(state.get("last_query") or ""))
            except ValueError:
                last = None
            if last is None or now - last >= _REQUERY_EVERY:
                state["last_query"] = now.isoformat()
                dirty = True
                tomorrow = dt_util.start_of_local_day(now) + timedelta(days=1)
                for event in await self._async_bin_events(tomorrow, tomorrow + timedelta(days=1)):
                    if event["date"] != (today + timedelta(days=1)).isoformat():
                        continue
                    key = f"{event['date']}|{event['summary'].lower()}"
                    if key in state["seen"]:
                        continue
                    if not _room():
                        _LOGGER.debug("TaskMate: bin chore for %s waits for the next read", key)
                        continue
                    chore = await self._async_raise_bin_chore("bin_day_put_out", event["summary"], local)
                    state["seen"][key] = {
                        "date": event["date"],
                        "summary": event["summary"],
                        "put_out_chore": chore.id if chore else "",
                        "bring_in": False,
                    }
                    created += 1 if chore else 0

        if self.storage.get_setting("bin_day_bring_in", False) and local.time() >= _parse_time(
            self.storage.get_setting("bin_day_bring_in_time"), DEFAULT_BRING_IN_TIME
        ):
            for record in state["seen"].values():
                if record.get("date") != today.isoformat() or record.get("bring_in"):
                    continue
                if not _room():
                    continue
                record["bring_in"] = True
                dirty = True
                chore = await self._async_raise_bin_chore("bin_day_bring_in", record["summary"], local)
                record["bring_in_chore"] = chore.id if chore else ""
                created += 1 if chore else 0

        cutoff = (today - timedelta(days=_SEEN_KEEP_DAYS)).isoformat()
        for key in [k for k, r in state["seen"].items() if str(r.get("date", "")) < cutoff]:
            del state["seen"][key]
            dirty = True
        if dirty or created:
            await self.storage.async_save()
        if created:
            await self.async_refresh()
        return created

    def _open_bin_jobs(self, state: dict[str, Any]) -> int:
        """Bin chores still on the board: raised, and neither done nor gone."""
        count = 0
        for record in state["seen"].values():
            for key in ("put_out_chore", "bring_in_chore"):
                chore = self.storage.get_chore(str(record.get(key) or ""))
                if chore is not None and getattr(chore, "enabled", True):
                    count += 1
        return count

    async def _async_raise_bin_chore(self, text_key: str, summary: str, local: datetime):
        """One-off chore for tonight; the deadline is the end of the day.

        Keeps the default ``requires_approval``: a calendar event is nobody's
        judgement of the work, so a parent ticks it off, never the auto-approve
        timer or a sibling. The caller saves once per tick.
        """
        pool = self.bin_day_children()
        if not pool:
            return None
        state = self._bin_state()
        mode = self.bin_day_mode()
        if mode == "rotate":
            turn = int(state.get("rotation", 0) or 0)
            assigned = [pool[turn % len(pool)]]
            state["rotation"] = turn + 1
            assignment_mode = "everyone"
        else:
            assigned = pool
            assignment_mode = "first_come" if len(pool) > 1 else "everyone"
        await notify_strings.async_load(self.hass)
        name = f"{bin_emoji(summary)} {notify_strings.render(self.hass, text_key, {'bin': summary})}"
        deadline = local.replace(hour=23, minute=59, second=0, microsecond=0)
        chore = await self.async_add_chore(
            name=name[:100],
            points=self.bin_day_points(),
            assigned_to=assigned,
            schedule_mode="one_shot",
            # "anytime": the parent picks the hour, and a time-of-day period would
            # lock the chore until it began (a 16:00 put-out vs an 18:00 evening).
            time_category="anytime",
            assignment_mode=assignment_mode,
            deadline_at=deadline.isoformat(),
            refresh=False,
        )
        self.hass.bus.async_fire(
            "taskmate_bin_day",
            {
                "chore_id": chore.id,
                "chore_name": chore.name,
                "bin": summary,
                "kind": "put_out" if text_key == "bin_day_put_out" else "bring_in",
                "child_ids": assigned,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        return chore
