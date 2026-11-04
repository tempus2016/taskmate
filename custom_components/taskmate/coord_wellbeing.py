"""Help requests ("I'm stuck") and the end-of-day mood check-in.

Help: a child tapping "I'm stuck" on a chore sends the parents a push without
completing or skipping anything. A request stays open until a parent marks it
answered, or for two hours, so the card can say "help is on its way". A second
tap on the same chore inside ten minutes is refused rather than buzzing the
parent again, and so is any further tap inside a minute while one is still
open: the button is for the child's own chores today, one at a time.

Mood: once a day a child can say how the day went with one of five faces.
Parents see the trend in the admin panel; a sad or upset day can also send a
(gentle, opt-in) push.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN, NOTIF_TYPE_HELP_REQUESTED, NOTIF_TYPE_MOOD_LOW
from .coord_set_times import chore_has_times
from .models import generate_id

MOODS = ("great", "good", "ok", "sad", "upset")
LOW_MOODS = ("sad", "upset")
MOOD_EMOJI = {"great": "😄", "good": "🙂", "ok": "😐", "sad": "😢", "upset": "😠"}
MOOD_KEEP_DAYS = 90

HELP_OPEN_HOURS = 2
HELP_REPEAT_MINUTES = 10
HELP_COOLDOWN_SECONDS = 60
HELP_KEEP = 100
HELP_MESSAGE_MAX = 120


class WellbeingMixin:
    """Help requests and mood check-ins."""

    # ── Help ─────────────────────────────────────────────────────────────

    def _help_requests(self) -> list[dict[str, Any]]:
        return self.storage.get_section("help_requests", list)

    def open_help_requests(self, child_id: str | None = None) -> list[dict[str, Any]]:
        """Unanswered requests from the last two hours, newest first."""
        cutoff = dt_util.now() - timedelta(hours=HELP_OPEN_HOURS)
        out = []
        for req in self._help_requests():
            if req.get("answered") or (child_id and req.get("child_id") != child_id):
                continue
            try:
                at = datetime.fromisoformat(req.get("at", ""))
            except (TypeError, ValueError):
                continue
            if at >= cutoff:
                out.append(req)
        return sorted(out, key=lambda r: r.get("at", ""), reverse=True)

    async def async_request_help(self, child_id: str, chore_id: str, message: str = "") -> dict[str, Any]:
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        chore = self.get_chore(chore_id)
        if chore is None:
            raise ValueError(f"Chore {chore_id} not found")
        # Only a chore that is the child's to do today. The card only offers
        # those, but the service takes any chore id, and a sibling's chore
        # name in a parent's push is not this child's to send.
        if not self._is_chore_completable_by_child(chore, child_id):
            # Theirs, but not available right now — a recurring chore still in
            # its window, a spent one-off, a vacation or rota day off (#771):
            # say so, rather than "not one of your chores".
            assigned = getattr(chore, "assigned_to", []) or []
            if (not assigned or child_id in assigned) and not self.is_chore_available_for_child(chore, child_id):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="help_chore_not_available",
                    translation_placeholders={"chore": chore.name},
                )
            raise ValueError(f"{chore.name} is not one of {child.name}'s chores today.")
        now = dt_util.now()
        # Not one the child can do right now (#771): a recurring chore still
        # in its window, a spent one-off, a set time that isn't open, or a
        # chore for a part of the day that hasn't started or is over. The card
        # doesn't offer "I'm stuck" on those rows, and a parent's push about a
        # chore that can't be done yet would only confuse.
        reason = self._help_unavailable_reason(chore, child_id, now)
        if reason:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=reason,
                translation_placeholders={"chore": chore.name},
            )
        repeat_cutoff = now - timedelta(minutes=HELP_REPEAT_MINUTES)
        cooldown_cutoff = now - timedelta(seconds=HELP_COOLDOWN_SECONDS)
        for req in self._help_requests():
            if req.get("child_id") != child_id or req.get("answered"):
                continue
            try:
                at = datetime.fromisoformat(req.get("at", ""))
            except (TypeError, ValueError):
                continue
            if req.get("chore_id") == chore_id and at >= repeat_cutoff:
                raise ValueError("Help is already on its way.")
            # One open request a minute across every chore: each one is a push
            # to every parent, and a different chore each tap is still a burst.
            if at >= cooldown_cutoff:
                raise ValueError("Give it a minute before asking for help again.")
        record = {
            "id": generate_id(),
            "child_id": child_id,
            "chore_id": chore_id,
            "chore_name": chore.name,
            "message": (message or "").strip()[:HELP_MESSAGE_MAX],
            "at": now.isoformat(),
            "answered": False,
        }
        requests = self._help_requests()
        requests.append(record)
        del requests[:-HELP_KEEP]
        await self.storage.async_save()
        await self.notifications.fire(
            NOTIF_TYPE_HELP_REQUESTED,
            {
                "child_id": child_id,
                "child_name": child.name,
                "chore_id": chore_id,
                "chore_name": chore.name,
                "message": record["message"],
                "message_text": f" — “{record['message']}”" if record["message"] else "",
                "request_id": record["id"],
            },
        )
        await self.async_refresh()
        return record

    def _help_unavailable_reason(self, chore, child_id: str, now: datetime) -> str:
        """Why a help request for ``chore`` can't be taken now, or "" when it can.

        On top of _is_chore_completable_by_child (checked first): an open set
        time, as the completion path requires, and the child card's time-of-day rule
        (_isChorePreviewLocked / _isTimePeriodElapsed): a chore whose period
        comes after the current one hasn't started; one whose period is over,
        past any claim allowance, has passed. "anytime" chores are always open.
        """
        if chore_has_times(chore):
            if self.resolve_set_time(chore, child_id, "", now, as_parent=False) is None:
                return "help_chore_not_available"
            return ""
        cat = getattr(chore, "time_category", "") or "anytime"
        if cat == "anytime":
            return ""
        periods = self.get_time_periods()
        ids = [p["id"] for p in periods]
        if cat not in ids:
            return ""

        def minutes(value: str) -> int:
            h, m = (int(x) for x in value.split(":"))
            return h * 60 + m

        local = dt_util.as_local(now)
        now_min = local.hour * 60 + local.minute
        # Before the first period starts, it's still the first one (as on the card).
        current = 0
        for i, p in enumerate(periods):
            if now_min >= minutes(p["start"]):
                current = i
        own = ids.index(cat)
        if own > current:
            return "help_chore_not_open_yet"
        if own < current:
            allowance = max(0, int(getattr(chore, "claim_allowance_minutes", 0) or 0))
            start, end = minutes(periods[own]["start"]), minutes(periods[own]["end"])
            if not (start <= now_min < min(1440, end + allowance)):
                return "help_chore_time_passed"
        return ""

    async def async_answer_help(self, request_id: str) -> bool:
        """A parent saw it: close the request so the card stops saying "on its way"."""
        for req in self._help_requests():
            if req.get("id") == request_id and not req.get("answered"):
                req["answered"] = True
                req["answered_at"] = dt_util.now().isoformat()
                await self.storage.async_save()
                await self.async_refresh()
                return True
        return False

    # ── Mood ─────────────────────────────────────────────────────────────

    def _moods(self) -> dict[str, dict[str, str]]:
        return self.storage.get_section("moods", dict)

    def mood_on(self, child_id: str, day: date | None = None) -> str:
        day = day or dt_util.as_local(dt_util.now()).date()
        return (self._moods().get(child_id) or {}).get(day.isoformat(), "")

    async def async_log_mood(self, child_id: str, mood: str) -> None:
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        if mood not in MOODS:
            raise ValueError(f"Unknown mood {mood!r}")
        today = dt_util.as_local(dt_util.now()).date()
        per_child = self._moods().setdefault(child_id, {})
        per_child[today.isoformat()] = mood
        floor = (today - timedelta(days=MOOD_KEEP_DAYS)).isoformat()
        for day in [d for d in per_child if d < floor]:
            del per_child[day]
        await self.storage.async_save()
        payload = {"child_id": child_id, "child_name": child.name, "mood": mood, "emoji": MOOD_EMOJI[mood]}
        self.hass.bus.async_fire("taskmate_mood_logged", {**payload, "timestamp": dt_util.now().isoformat()})
        if mood in LOW_MOODS:
            await self.notifications.fire(NOTIF_TYPE_MOOD_LOW, payload)
        await self.async_refresh()

    def mood_report(self, days: int = 14) -> dict[str, Any]:
        """Each child's moods for the last ``days`` days, oldest first, with counts."""
        days = max(1, min(int(days or 14), MOOD_KEEP_DAYS))
        today = dt_util.as_local(dt_util.now()).date()
        span = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
        rows = []
        for child in self.storage.get_children():
            per_child = self._moods().get(child.id) or {}
            series = [{"date": d, "mood": per_child.get(d, "")} for d in span]
            counts = {m: sum(1 for s in series if s["mood"] == m) for m in MOODS}
            rows.append(
                {
                    "id": child.id,
                    "name": child.name,
                    "series": series,
                    "counts": counts,
                    "logged": sum(counts.values()),
                    "low_days": counts["sad"] + counts["upset"],
                }
            )
        return {"days": days, "start": span[0], "end": span[-1], "moods": list(MOODS), "children": rows}
