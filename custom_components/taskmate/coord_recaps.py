"""Recaps (#929): a "Wrapped"-style summary of a child's period.

A parent picks how often each child gets one — any combination of weekly,
monthly, every 3/6/9 months and yearly, as a family default with a per-child
override. Periods align to calendar boundaries (weekly follows the country's
first weekday; every 9 months is anchored to 1 January 2026). Just after a
period ends a recap is built and stored as a small JSON snapshot, so a later
undo, points edit or deleted chore never rewrites an old recap.

Completion history is pruned after ``history_days`` and points transactions are
capped at 200, so neither can answer "what did Malia do all year" on 1 January.
A compact per-child daily ledger is rolled up from them every midnight (and at
startup) instead, and recaps are aggregated from the ledger. The last few days
are re-rolled on every pass so a late approval or an undo still lands.

Recaps are built at midnight and announced later, at the configured send time,
so nobody is woken up. Turning a frequency on never back-fills: the first recap
covers the period the frequency was switched on in.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from . import notify_strings
from .models import generate_id
from .timewindow import parse_hhmm

_LOGGER = logging.getLogger(__name__)

RECAP_FREQUENCIES = (
    "weekly",
    "monthly",
    "every_3_months",
    "every_6_months",
    "every_9_months",
    "yearly",
)
# Longest first: when several recaps land on the same day the longest period
# is shown (and announced) first.
_FREQ_RANK = {
    "yearly": 0,
    "every_9_months": 1,
    "every_6_months": 2,
    "every_3_months": 3,
    "monthly": 4,
    "weekly": 5,
}
_FREQ_MONTHS = {"monthly": 1, "every_3_months": 3, "every_6_months": 6, "every_9_months": 9, "yearly": 12}
# Nine doesn't divide a year, so the blocks need an anchor. John picked
# 1 January 2026: Jan-Sep 2026, Oct 2026-Jun 2027, and so on.
NINE_MONTH_ANCHOR = date(2026, 1, 1)

# Off until a parent ticks a frequency (#944): an upgrade must not start
# building recaps and pushing "recap ready" to families who never asked.
DEFAULT_RECAP_FREQUENCIES: tuple[str, ...] = ()
DEFAULT_RECAP_SEND_TIME = "08:00"
RECAP_RETENTION_DAYS = {"1y": 366, "2y": 731, "forever": None}
DEFAULT_RECAP_RETENTION = "forever"

# Re-roll this many recent days on every pass: a chore done on Sunday and
# approved on Monday belongs to Sunday.
_LEDGER_REFRESH_DAYS = 7
# Two years and a bit, so a yearly recap can still compare against the year
# before even when the stored recap for it has been retired.
_LEDGER_KEEP_DAYS = 740
# Catch-up after downtime builds at most this many missed periods per frequency.
_MAX_CATCHUP_PERIODS = 12
# A pending announcement older than this is dropped rather than sent late.
_NOTIFY_MAX_AGE_DAYS = 7
PREVIEW_DAYS = 30
# A preview covers a rolling 30 days, not a calendar period.
PREVIEW_FREQUENCY = "preview"
_PREVIEW_TTL = timedelta(hours=24)
_MAX_LIST_ITEMS = 6

# CLDR first-day-of-week by country. Everything not listed starts on Monday.
_SUNDAY_FIRST = frozenset(
    "AG AS BD BR BS BT BW BZ CA CN CO DM DO ET GT GU HK HN ID IL IN JM JP KE KH KR LA MH MM MO MT MX MZ "
    "NI NP PA PE PH PK PR PT PY SA SG SV TH TT TW UM US VE VI WS YE ZA ZW".split()
)
_SATURDAY_FIRST = frozenset("AE AF BH DJ DZ EG IQ IR JO KW LY OM QA SD SY".split())


def _add_months(day: date, months: int) -> date:
    """The first of the month ``months`` after ``day``'s month (may be negative)."""
    years, month0 = divmod(day.month - 1 + months, 12)
    return date(day.year + years, month0 + 1, 1)


def week_start_for_country(country: str | None) -> int:
    """First weekday (0=Monday ... 6=Sunday) for an ISO country code."""
    code = (country or "").upper()
    if code in _SUNDAY_FIRST:
        return 6
    if code in _SATURDAY_FIRST:
        return 5
    return 0


def period_for(freq: str, day: date, week_start: int = 0) -> tuple[date, date]:
    """The calendar period of ``freq`` containing ``day``, as inclusive dates."""
    if freq == "weekly":
        start = day - timedelta(days=(day.weekday() - week_start) % 7)
        return start, start + timedelta(days=6)
    months = _FREQ_MONTHS[freq]
    if freq == "every_9_months":
        offset = (day.year - NINE_MONTH_ANCHOR.year) * 12 + day.month - 1
        start = _add_months(NINE_MONTH_ANCHOR, (offset // 9) * 9)
    else:
        start = date(day.year, ((day.month - 1) // months) * months + 1, 1)
    return start, _add_months(start, months) - timedelta(days=1)


def completed_periods(freq: str, today: date, week_start: int = 0, limit: int = _MAX_CATCHUP_PERIODS):
    """Finished periods of ``freq`` before ``today``, newest first."""
    current_start, _ = period_for(freq, today, week_start)
    day = current_start - timedelta(days=1)
    for _ in range(limit):
        start, end = period_for(freq, day, week_start)
        yield start, end
        day = start - timedelta(days=1)


def period_label(freq: str, start: date, end: date, hass: Any = None) -> str:
    """Short label for a period, used in notification text (HA's language)."""
    if freq == "weekly":
        return notify_strings.text(hass, "period_weekly")
    if freq == "monthly":
        return notify_strings.month_name(hass, start.month)
    if freq == "yearly":
        return str(start.year)
    return notify_strings.render(
        hass,
        "period_range",
        {
            "start": notify_strings.text(hass, f"month_short_{start.month}"),
            "end": notify_strings.text(hass, f"month_short_{end.month}"),
        },
    )


def _valid_frequencies(raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    wanted = {str(f) for f in raw}
    return [f for f in RECAP_FREQUENCIES if f in wanted]


def _as_bool(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value is True or str(value).lower() == "true"


def _rank(recap: dict) -> int:
    return _FREQ_RANK.get(recap.get("frequency"), 9)


class RecapsMixin:
    """Mixin: the recap ledger, generation, retention and announcements."""

    # ── settings ─────────────────────────────────────────────────────────

    def recap_family_frequencies(self) -> list[str]:
        raw = self.storage.get_setting("recap_frequencies", None)
        if raw is None:
            return list(DEFAULT_RECAP_FREQUENCIES)
        return _valid_frequencies(raw)

    def recap_child_overrides(self) -> dict[str, list[str]]:
        raw = self.storage.get_setting("recap_child_frequencies", {})
        if not isinstance(raw, dict):
            return {}
        return {str(cid): _valid_frequencies(v) for cid, v in raw.items()}

    def recap_frequencies_for(self, child_id: str) -> list[str]:
        """The child's own list when set to Custom, else the family default."""
        overrides = self.recap_child_overrides()
        if child_id in overrides:
            return overrides[child_id]
        return self.recap_family_frequencies()

    def recaps_enabled_anywhere(self) -> bool:
        """True when the family default or any child's Custom list has a frequency."""
        if self.recap_family_frequencies():
            return True
        return any(self.recap_child_overrides().values())

    def recap_week_start(self) -> int:
        return week_start_for_country(getattr(getattr(self.hass, "config", None), "country", None))

    def recap_compare_enabled(self) -> bool:
        return _as_bool(self.storage.get_setting("recap_compare", True), True)

    def recap_send_time(self) -> str:
        value = str(self.storage.get_setting("recap_send_time", DEFAULT_RECAP_SEND_TIME) or "")
        try:
            parse_hhmm(value)
        except (ValueError, TypeError, AttributeError):
            return DEFAULT_RECAP_SEND_TIME
        return value

    def _recap_today(self) -> date:
        return dt_util.as_local(dt_util.now()).date()

    # ── storage ──────────────────────────────────────────────────────────

    def _recap_store(self) -> list[dict]:
        data = self.storage.data
        if not isinstance(data.get("recaps"), list):
            data["recaps"] = []
        return data["recaps"]

    def _recap_ledger(self) -> dict:
        data = self.storage.data
        ledger = data.get("recap_ledger")
        if not isinstance(ledger, dict):
            ledger = data["recap_ledger"] = {}
        if not isinstance(ledger.get("days"), dict):
            ledger["days"] = {}
        if not isinstance(ledger.get("chores"), dict):
            ledger["chores"] = {}
        return ledger

    def _recap_state(self) -> dict:
        data = self.storage.data
        if not isinstance(data.get("recap_state"), dict):
            data["recap_state"] = {}
        return data["recap_state"]

    # ── the daily ledger ─────────────────────────────────────────────────

    def _recap_day_rows(self, days: set[str]) -> dict[str, dict[str, dict]]:
        """Aggregate completions + bonus transactions for the given ISO days.

        Returns ``{child_id: {day: {"c", "p", "b", "t"}}}``. ``c`` counts chores
        (bonus sub-tasks are extra credit on a chore already counted), ``p`` is
        chore points including sub-tasks, ``b`` is bonus points and ``t`` is
        per-chore counts for the top-chore slide.
        """
        rows: dict[str, dict[str, dict]] = {}

        def row(child_id: str, day: str) -> dict:
            return rows.setdefault(child_id, {}).setdefault(day, {"c": 0, "p": 0, "b": 0, "t": {}})

        for comp in self.storage.get_completions():
            if not getattr(comp, "approved", False):
                continue
            try:
                day = dt_util.as_local(comp.completed_at).date().isoformat()
            except (AttributeError, TypeError, ValueError):
                continue
            if day not in days:
                continue
            entry = row(comp.child_id, day)
            entry["p"] += int(getattr(comp, "points_awarded", 0) or 0)
            if getattr(comp, "bonus_subtask_id", ""):
                continue
            entry["c"] += 1
            entry["t"][comp.chore_id] = entry["t"].get(comp.chore_id, 0) + 1

        for txn in self.storage.get_points_transactions():
            points = int(getattr(txn, "points", 0) or 0)
            reason = str(getattr(txn, "reason", "") or "")
            # Gifts and refunds move points around; they weren't earned.
            if points <= 0 or reason.startswith("Gift from") or "refund" in reason.lower():
                continue
            try:
                day = dt_util.as_local(txn.created_at).date().isoformat()
            except (AttributeError, TypeError, ValueError):
                continue
            if day in days:
                row(txn.child_id, day)["b"] += points
        return rows

    def _recap_rollup(self, today: date) -> None:
        """Roll finished days into the ledger (idempotent)."""
        ledger = self._recap_ledger()
        yesterday = today - timedelta(days=1)
        rolled_raw = ledger.get("rolled")
        try:
            rolled = date.fromisoformat(rolled_raw) if rolled_raw else None
        except (TypeError, ValueError):
            rolled = None

        if rolled is None:
            # First run: back-fill everything the completion history still has.
            earliest = yesterday
            for comp in self.storage.get_completions():
                if not getattr(comp, "approved", False):
                    continue
                try:
                    earliest = min(earliest, dt_util.as_local(comp.completed_at).date())
                except (AttributeError, TypeError, ValueError):
                    continue
            start = earliest
            ledger.setdefault("since", min(earliest, today).isoformat())
        else:
            start = min(rolled + timedelta(days=1), today - timedelta(days=_LEDGER_REFRESH_DAYS))

        if start <= yesterday:
            span = [(start + timedelta(days=i)).isoformat() for i in range((yesterday - start).days + 1)]
            fresh = self._recap_day_rows(set(span))
            # Bonus points come from transactions, which are capped at 200: only
            # trust a recount for a day the retained transactions fully cover.
            covered_from = None
            for txn in self.storage.get_points_transactions():
                try:
                    stamp = dt_util.as_local(txn.created_at).date()
                except (AttributeError, TypeError, ValueError):
                    continue
                covered_from = stamp if covered_from is None else min(covered_from, stamp)
            days_map = ledger["days"]
            children = {c.id for c in self.storage.get_children()}
            for child_id in children | set(days_map) | set(fresh):
                per_child = days_map.setdefault(child_id, {})
                for day in span:
                    new = fresh.get(child_id, {}).get(day)
                    old = per_child.get(day)
                    if old and (covered_from is None or date.fromisoformat(day) <= covered_from):
                        # Keep the bonus we saw while its transactions still existed.
                        new = dict(new or {"c": 0, "p": 0, "b": 0, "t": {}})
                        new["b"] = max(new["b"], int(old.get("b", 0) or 0))
                    if new and (new["c"] or new["p"] or new["b"]):
                        per_child[day] = {k: v for k, v in new.items() if v}
                    else:
                        per_child.pop(day, None)
                if not per_child:
                    days_map.pop(child_id, None)
            # Remember chore names/icons so a recap can still name a chore that
            # has since been deleted.
            names = ledger["chores"]
            for chore in self.storage.get_chores():
                names[chore.id] = [chore.name, getattr(chore, "icon", "") or ""]
            ledger["rolled"] = yesterday.isoformat()

        # Retire old days, orphaned children and names nothing refers to.
        cutoff = (today - timedelta(days=_LEDGER_KEEP_DAYS)).isoformat()
        known = {c.id for c in self.storage.get_children()}
        for child_id in list(ledger["days"]):
            if child_id not in known:
                del ledger["days"][child_id]
                continue
            per_child = ledger["days"][child_id]
            for day in [d for d in per_child if d < cutoff]:
                del per_child[day]
        referenced = {
            cid for per_child in ledger["days"].values() for row in per_child.values() for cid in row.get("t", {})
        }
        live = {c.id for c in self.storage.get_chores()}
        for chore_id in [cid for cid in ledger["chores"] if cid not in referenced and cid not in live]:
            del ledger["chores"][chore_id]

    # ── building a recap ─────────────────────────────────────────────────

    def _recap_totals(self, days: dict[str, dict], start: date, end: date) -> dict[str, Any]:
        """Headline figures for one child's days in [start, end]."""
        chores = chore_points = bonus = active = 0
        run = best_run = 0
        run_start = best_start = best_end = None
        best_day = None
        per_chore: dict[str, int] = {}
        dow = [0] * 7
        span = (end - start).days + 1
        for i in range(span):
            day = start + timedelta(days=i)
            row = days.get(day.isoformat()) or {}
            c = int(row.get("c", 0) or 0)
            p = int(row.get("p", 0) or 0) + int(row.get("b", 0) or 0)
            chores += c
            chore_points += int(row.get("p", 0) or 0)
            bonus += int(row.get("b", 0) or 0)
            dow[day.weekday()] += c
            for chore_id, n in (row.get("t") or {}).items():
                per_chore[chore_id] = per_chore.get(chore_id, 0) + int(n or 0)
            if c:
                active += 1
                run += 1
                run_start = run_start if run > 1 else day
                # >= so a tie goes to the later run: the one they remember.
                if run >= best_run:
                    best_run, best_start, best_end = run, run_start, day
                if best_day is None or (c, p) > (best_day[1], best_day[2]):
                    best_day = (day, c, p)
            else:
                run = 0
        return {
            "chores": chores,
            "points": chore_points + bonus,
            "chore_points": chore_points,
            "bonus_points": bonus,
            "days_active": active,
            "days": span,
            "dow": dow,
            "per_chore": per_chore,
            "streak": {"days": best_run, "start": best_start.isoformat(), "end": best_end.isoformat()}
            if best_run
            else None,
            "best_day": {"date": best_day[0].isoformat(), "chores": best_day[1], "points": best_day[2]}
            if best_day
            else None,
        }

    @staticmethod
    def _recap_buckets(freq: str, days: dict[str, dict], start: date, end: date) -> list[list]:
        """Chore counts per sub-period: days of a week, weeks of a month, else months."""
        buckets: list[list] = []
        if freq == "weekly":
            step = 1
        elif freq in ("monthly", PREVIEW_FREQUENCY):
            step = 7
        else:
            step = 0
        cursor = start
        while cursor <= end:
            nxt = cursor + timedelta(days=step) if step else _add_months(cursor, 1)
            last = min(end, nxt - timedelta(days=1))
            total = 0
            for i in range((last - cursor).days + 1):
                total += int((days.get((cursor + timedelta(days=i)).isoformat()) or {}).get("c", 0) or 0)
            buckets.append([cursor.isoformat(), total])
            cursor = nxt
        return buckets

    def _recap_highlights(self, child_id: str, start: date, end: date) -> tuple[list[dict], list[dict]]:
        """Badges earned and rewards redeemed inside the period."""
        badges_by_id = {b.id: b for b in self.storage.get_badges()}
        badges: list[dict] = []
        for award in sorted(self.storage.get_awarded_badges(), key=lambda a: a.earned_at):
            if award.child_id != child_id or getattr(award, "silent", False):
                continue
            badge = badges_by_id.get(award.badge_id)
            if badge is None:
                continue
            try:
                when = dt_util.as_local(award.earned_at).date()
            except (AttributeError, TypeError, ValueError):
                continue
            if start <= when <= end:
                badges.append({"name": badge.name, "icon": getattr(badge, "icon", "") or "mdi:trophy"})

        rewards_by_id = {r.id: r for r in self.storage.get_rewards()}
        rewards: list[dict] = []
        for claim in self.storage.get_reward_claims():
            if claim.child_id != child_id or not getattr(claim, "approved", False):
                continue
            reward = rewards_by_id.get(claim.reward_id)
            if reward is None:
                continue
            try:
                when = dt_util.as_local(claim.approved_at or claim.claimed_at).date()
            except (AttributeError, TypeError, ValueError):
                continue
            if start <= when <= end:
                cost = claim.approved_cost if claim.approved_cost is not None else getattr(reward, "cost", 0)
                rewards.append(
                    {"name": reward.name, "cost": int(cost or 0), "icon": getattr(reward, "icon", "") or "mdi:gift"}
                )
        return badges[-_MAX_LIST_ITEMS:], rewards[-_MAX_LIST_ITEMS:]

    def _recap_previous(self, child_id: str, freq: str, start: date, week_start: int) -> dict | None:
        """Figures for the period before, from its stored recap or the ledger."""
        prev_start, prev_end = period_for(freq, start - timedelta(days=1), week_start)
        for recap in self._recap_store():
            if (
                recap.get("child_id") == child_id
                and recap.get("frequency") == freq
                and recap.get("start") == prev_start.isoformat()
                and not recap.get("preview")
            ):
                streak = recap.get("streak") or {}
                return {
                    "start": recap["start"],
                    "end": recap.get("end", prev_end.isoformat()),
                    "chores": recap.get("chores", 0),
                    "points": recap.get("points", 0),
                    "streak": streak.get("days", 0),
                    "days_active": recap.get("days_active", 0),
                }
        ledger = self._recap_ledger()
        try:
            since = date.fromisoformat(ledger.get("since", ""))
        except (TypeError, ValueError):
            return None
        if prev_start < since:
            # The ledger doesn't reach back that far: no comparison beats a
            # comparison against zeros.
            return None
        totals = self._recap_totals(ledger["days"].get(child_id, {}), prev_start, prev_end)
        return {
            "start": prev_start.isoformat(),
            "end": prev_end.isoformat(),
            "chores": totals["chores"],
            "points": totals["points"],
            "streak": (totals["streak"] or {}).get("days", 0),
            "days_active": totals["days_active"],
        }

    def _recap_build(
        self,
        child_id: str,
        freq: str,
        start: date,
        end: date,
        *,
        days: dict[str, dict] | None = None,
        preview: bool = False,
    ) -> dict[str, Any]:
        """Snapshot one child's period. ``days`` overrides the ledger (preview)."""
        ledger = self._recap_ledger()
        if days is None:
            days = ledger["days"].get(child_id, {})
        week_start = self.recap_week_start()
        totals = self._recap_totals(days, start, end)
        top = None
        if totals["per_chore"]:
            chore_id, count = max(totals["per_chore"].items(), key=lambda kv: (kv[1], kv[0]))
            name, icon = (ledger["chores"].get(chore_id) or ["", ""])[:2]
            chore = self.storage.get_chore(chore_id)
            if chore is not None:
                name, icon = chore.name, getattr(chore, "icon", "") or icon
            if name:
                top = {"name": name, "icon": icon or "", "count": count}
        badges, rewards = self._recap_highlights(child_id, start, end)
        recap: dict[str, Any] = {
            "id": generate_id(),
            "child_id": child_id,
            "frequency": freq,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "created_at": dt_util.now().isoformat(),
            "week_start": week_start,
            "chores": totals["chores"],
            "points": totals["points"],
            "chore_points": totals["chore_points"],
            "bonus_points": totals["bonus_points"],
            "days_active": totals["days_active"],
            "days": totals["days"],
            "bars": self._recap_buckets(freq, days, start, end),
            "dow": totals["dow"],
            "top_chore": top,
            "streak": totals["streak"],
            "best_day": totals["best_day"],
            "badges": badges,
            "rewards": rewards,
            "previous": None if preview else self._recap_previous(child_id, freq, start, week_start),
            "notified": preview,
        }
        if preview:
            recap["preview"] = True
        return recap

    # ── the scheduled pass ───────────────────────────────────────────────

    def _recap_sync_state(self, today: date) -> None:
        """Track when each child's frequency was switched on (no back-fill)."""
        state = self._recap_state()
        known = set()
        for child in self.storage.get_children():
            known.add(child.id)
            wanted = set(self.recap_frequencies_for(child.id))
            per_child = state.get(child.id)
            if not isinstance(per_child, dict):
                per_child = state[child.id] = {}
            for freq in wanted - set(per_child):
                per_child[freq] = {"since": today.isoformat()}
            for freq in set(per_child) - wanted:
                del per_child[freq]
        for child_id in [cid for cid in state if cid not in known]:
            del state[child_id]

    def _recap_prune(self, today: date) -> bool:
        """Apply retention, drop expired previews and deleted children's recaps."""
        store = self._recap_store()
        keep_days = RECAP_RETENTION_DAYS.get(
            str(self.storage.get_setting("recap_retention", DEFAULT_RECAP_RETENTION)), None
        )
        cutoff = (today - timedelta(days=keep_days)).isoformat() if keep_days else None
        known = {c.id for c in self.storage.get_children()}
        now = dt_util.now()
        kept = []
        for recap in store:
            if recap.get("child_id") not in known:
                continue
            if recap.get("preview"):
                try:
                    created = datetime.fromisoformat(recap.get("created_at", ""))
                except (TypeError, ValueError):
                    continue
                if now - created > _PREVIEW_TTL:
                    continue
            elif cutoff and recap.get("end", "") < cutoff:
                continue
            kept.append(recap)
        changed = len(kept) != len(store)
        store[:] = kept
        return changed

    async def async_run_recaps(self, today: date | None = None) -> list[dict]:
        """Roll the ledger and build every recap whose period has finished.

        Runs just after midnight and at startup, so a boundary missed while
        Home Assistant was off is still built. Returns the new recaps.
        """
        today = today or self._recap_today()
        self._recap_rollup(today)
        self._recap_sync_state(today)
        week_start = self.recap_week_start()
        store = self._recap_store()
        state = self._recap_state()
        built: list[dict] = []
        for child in self.storage.get_children():
            for freq, marker in (state.get(child.id) or {}).items():
                try:
                    since = date.fromisoformat(marker.get("since", ""))
                except (TypeError, ValueError, AttributeError):
                    continue
                last = marker.get("last") or ""
                due = [
                    (start, end)
                    for start, end in completed_periods(freq, today, week_start)
                    if end >= since and end.isoformat() > last
                ]
                for start, end in reversed(due):
                    recap = self._recap_build(child.id, freq, start, end)
                    store.append(recap)
                    built.append(recap)
                    marker["last"] = end.isoformat()
        self._recap_prune(today)
        await self.storage.async_save()
        if built:
            _LOGGER.info("Built %d recap(s)", len(built))
        return built

    async def async_build_recap_preview(self, child_id: str) -> dict[str, Any]:
        """A throw-away recap of the last 30 days (including today) for a parent.

        Replaces the child's previous preview and expires after a day. Never
        announced, never used as a comparison baseline.
        """
        if self.storage.get_child(child_id) is None:
            raise ValueError(f"Child {child_id} not found")
        today = self._recap_today()
        self._recap_rollup(today)
        days = dict(self._recap_ledger()["days"].get(child_id, {}))
        live = self._recap_day_rows({today.isoformat()}).get(child_id, {}).get(today.isoformat())
        if live:
            days[today.isoformat()] = live
        start = today - timedelta(days=PREVIEW_DAYS - 1)
        recap = self._recap_build(child_id, PREVIEW_FREQUENCY, start, today, days=days, preview=True)
        store = self._recap_store()
        store[:] = [r for r in store if not (r.get("preview") and r.get("child_id") == child_id)]
        store.append(recap)
        await self.storage.async_save()
        return recap

    # ── reading ──────────────────────────────────────────────────────────

    def recaps_for_child(self, child_id: str) -> list[dict]:
        """A child's recaps, newest period first, longest first on a tie."""
        self._recap_prune(self._recap_today())
        mine = [r for r in self._recap_store() if r.get("child_id") == child_id]
        mine.sort(key=lambda r: (r.get("preview", False), r.get("end", ""), -_rank(r)), reverse=True)
        return mine

    def recap_summary(self, recap: dict) -> dict[str, Any]:
        out = {k: recap.get(k) for k in ("id", "frequency", "start", "end", "created_at", "chores", "points")}
        if recap.get("preview"):
            out["preview"] = True
        return out

    def recap_upcoming(self, child_id: str, today: date | None = None) -> list[dict]:
        """The next recap per active frequency, soonest first."""
        today = today or self._recap_today()
        week_start = self.recap_week_start()
        out = []
        for freq in self.recap_frequencies_for(child_id):
            start, end = period_for(freq, today, week_start)
            out.append(
                {
                    "frequency": freq,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "ready_on": (end + timedelta(days=1)).isoformat(),
                }
            )
        out.sort(key=lambda u: (u["ready_on"], _FREQ_RANK.get(u["frequency"], 9)))
        return out

    def recap_schedule(self, today: date | None = None) -> dict[str, Any]:
        """When each frequency's next recap lands (for the settings screen)."""
        today = today or self._recap_today()
        week_start = self.recap_week_start()
        return {
            "week_start": week_start,
            "next": {
                freq: (period_for(freq, today, week_start)[1] + timedelta(days=1)).isoformat()
                for freq in RECAP_FREQUENCIES
            },
        }

    # ── announcements ────────────────────────────────────────────────────

    async def async_send_recap_notifications(self) -> int:
        """Announce recaps built since the last send. Returns the children told.

        Every pending recap is marked announced first, so a failure half-way
        can never double-send. One ``taskmate_recap_ready`` event per child
        fires whether or not notifications are switched on.
        """
        store = self._recap_store()
        pending = [r for r in store if not r.get("notified") and not r.get("preview")]
        if not pending:
            return 0
        for recap in pending:
            recap["notified"] = True
        # Children and parents added since the last send get the default route.
        self.ensure_recap_routes()
        await self.storage.async_save()

        oldest = dt_util.now() - timedelta(days=_NOTIFY_MAX_AGE_DAYS)
        fresh = []
        for recap in pending:
            try:
                created = datetime.fromisoformat(recap.get("created_at", ""))
            except (TypeError, ValueError):
                continue
            if created >= oldest:
                fresh.append(recap)

        by_child: dict[str, list[dict]] = {}
        for recap in sorted(fresh, key=_rank):
            by_child.setdefault(recap["child_id"], []).append(recap)

        per_child: list[dict] = []
        for child_id, recaps in by_child.items():
            child = self.storage.get_child(child_id)
            if child is None:
                continue
            first = recaps[0]
            label = period_label(
                first["frequency"], date.fromisoformat(first["start"]), date.fromisoformat(first["end"]), self.hass
            )
            if len(recaps) == 1:
                message = notify_strings.render(self.hass, "recap_ready", {"period": label, "child_name": child.name})
            else:
                message = notify_strings.render(
                    self.hass, "recap_ready_many", {"count": len(recaps), "child_name": child.name}
                )
            per_child.append(
                {
                    "child_id": child_id,
                    "child_name": child.name,
                    "message": message,
                    "label": label,
                    "recaps": [
                        {"id": r["id"], "frequency": r["frequency"], "start": r["start"], "end": r["end"]}
                        for r in recaps
                    ],
                }
            )
        if not per_child:
            return 0

        joined = notify_strings.join_names(self.hass, [c["child_name"] for c in per_child])
        labels = {c["label"] for c in per_child}
        if len(labels) == 1:
            parent_message = notify_strings.render(
                self.hass, "recap_parent_one", {"period": per_child[0]["label"], "names": joined}
            )
        else:
            parent_message = notify_strings.render(self.hass, "recap_parent_many", {"names": joined})

        await self.notifications.send_recap_ready(
            per_child,
            parent_message,
            to_children=_as_bool(self.storage.get_setting("recap_notify_children", True), True),
            to_parents=_as_bool(self.storage.get_setting("recap_notify_parents", True), True),
        )
        return len(per_child)

    # ── scheduling ───────────────────────────────────────────────────────

    def arm_recap_schedules(self) -> None:
        """Midnight build + the daily announcement at the configured time."""
        self.disarm_recap_schedules()
        hour, minute = parse_hhmm(self.recap_send_time())
        self._recap_unsubs = [
            async_track_time_change(self.hass, self._recap_midnight, hour=0, minute=0, second=30),
            async_track_time_change(self.hass, self._recap_send_due, hour=hour, minute=minute, second=0),
        ]

    def disarm_recap_schedules(self) -> None:
        for unsub in getattr(self, "_recap_unsubs", None) or []:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("recap schedule unsub failed", exc_info=True)
        self._recap_unsubs = []

    @callback
    def _recap_midnight(self, now: datetime) -> None:
        self.hass.async_create_task(self._async_recap_guarded(self.async_run_recaps))

    @callback
    def _recap_send_due(self, now: datetime) -> None:
        self.hass.async_create_task(self._async_recap_guarded(self.async_send_recap_notifications))

    async def _async_recap_guarded(self, step) -> None:
        try:
            await step()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Recap step %s failed", getattr(step, "__name__", step))

    async def async_start_recaps(self) -> None:
        """Startup: catch up on missed boundaries, then on a missed send time."""
        self.ensure_recap_routes()
        await self._async_recap_guarded(self.async_run_recaps)
        now = dt_util.as_local(dt_util.now())
        hour, minute = parse_hhmm(self.recap_send_time())
        if (now.hour, now.minute) >= (hour, minute):
            await self._async_recap_guarded(self.async_send_recap_notifications)
        self.arm_recap_schedules()

    async def async_recap_settings_changed(self) -> None:
        """A parent saved recap settings: record switch-on dates, re-arm the send time."""
        self._recap_sync_state(self._recap_today())
        self.ensure_recap_routes()
        await self.storage.async_save()
        self.arm_recap_schedules()

    def ensure_recap_routes(self) -> None:
        """Deliver "recap ready" to every child and parent once recaps are on.

        Recaps are opt-in (#944), so nothing happens until a parent ticks a
        frequency. The first pass after that switches the type on (the Recaps
        settings carry their own child/parent switches). After that only
        recipients with no route yet are added: a parent who unticks someone
        in the notification matrix stays unticked.
        """
        from .const import NOTIF_TYPE_RECAP_READY
        from .models import NotificationRoute

        if not self.recaps_enabled_anywhere():
            return
        if not self.storage.get_setting("recap_notify_seeded", False):
            self.storage.set_notification_master(NOTIF_TYPE_RECAP_READY, True)
            self.storage.set_setting("recap_notify_seeded", True)
        routes = self.storage.get_notification_config(NOTIF_TYPE_RECAP_READY).routes
        wanted = [f"child:{c.id}" for c in self.storage.get_children()]
        wanted += [p.id for p in self.storage.get_parent_recipients() if p.enabled]
        for rid in wanted:
            if rid not in routes:
                self.storage.set_notification_route(NOTIF_TYPE_RECAP_READY, rid, NotificationRoute(enabled=True))
