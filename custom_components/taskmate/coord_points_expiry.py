"""Points expiry (optional): unspent points fade away after a set number of days.

Each child's balance is tracked as dated lots — ``[{"d": ISO date, "n": points}]``,
oldest first — in the ``points_expiry`` section. Rather than hook every place
a balance changes, the lots are reconciled against ``child.points`` on every
refresh and every minute:

* the balance went **up** → the difference is a new lot dated today. That
  covers chores, bonuses and adjustments, and also refunds: a refunded or
  returned point starts its clock again, never earlier than the day it came
  back;
* the balance went **down** → the difference is taken from the oldest lots
  first (FIFO). Spending, penalties, removals, savings-jar deposits and
  gifts to a sibling all use up the points closest to expiring.

Points saved into a reward's savings jar have left the balance, so they
never expire while they sit there. Points a child moves into a wish (#932)
are different: they are still the child's to take back, so the lots they
came out of travel with the wish (``take_lots`` / ``restore_lots``) and keep
their dates — moving points in and out is not a way to restart the clock.

On the minutely tick any lot older than ``points_expiry_days`` is taken off
the balance with a "Points expired" transaction and a
``taskmate_points_expired`` event. Inside the warning window the card shows
"N points expire on <day>" and the opt-in ``points_expiring`` notification
goes to the child once per expiry date.

Switching the feature on starts every existing balance as one lot dated that
day, so nothing expires by surprise; switching it off forgets the lots.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import NOTIF_TYPE_POINTS_EXPIRING
from .models import PointsTransaction

_LOGGER = logging.getLogger(__name__)

POINTS_EXPIRY_DEFAULT_DAYS = 90
POINTS_EXPIRY_MAX_DAYS = 730
POINTS_EXPIRY_DEFAULT_WARN = 7
POINTS_EXPIRY_MAX_WARN = 60
POINTS_EXPIRED_REASON = "Points expired"
_SECTION = "points_expiry"


def _int_setting(raw: Any, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(raw)))
    except (TypeError, ValueError):
        return default


class PointsExpiryMixin:
    """Dated points lots, spent oldest first, expired on the tick."""

    def points_expiry_enabled(self) -> bool:
        v = self.storage.get_setting("points_expiry_enabled", False)
        return v is True or str(v).lower() == "true"

    def points_expiry_days(self) -> int:
        raw = self.storage.get_setting("points_expiry_days", POINTS_EXPIRY_DEFAULT_DAYS)
        return _int_setting(raw, POINTS_EXPIRY_DEFAULT_DAYS, 1, POINTS_EXPIRY_MAX_DAYS)

    def points_expiry_warn_days(self) -> int:
        raw = self.storage.get_setting("points_expiry_warn_days", POINTS_EXPIRY_DEFAULT_WARN)
        return _int_setting(raw, POINTS_EXPIRY_DEFAULT_WARN, 0, POINTS_EXPIRY_MAX_WARN)

    # ── lots ─────────────────────────────────────────────────────────────

    def _expiry_record(self, child_id: str) -> dict[str, Any]:
        section = self.storage.get_section(_SECTION, dict)
        record = section.get(child_id)
        if not isinstance(record, dict) or not isinstance(record.get("lots"), list):
            record = {"lots": []}
            section[child_id] = record
        return record

    @staticmethod
    def _lot_total(lots: list) -> int:
        return sum(int(lot.get("n", 0) or 0) for lot in lots if isinstance(lot, dict))

    def _reconcile_lots(self, child) -> list[dict[str, Any]]:
        """Bring a child's lots in line with their balance (see the module docstring)."""
        record = self._expiry_record(child.id)
        lots = [lot for lot in record["lots"] if isinstance(lot, dict) and int(lot.get("n", 0) or 0) > 0]
        balance = max(0, int(child.points or 0))
        diff = balance - self._lot_total(lots)
        if diff > 0:
            today = dt_util.as_local(dt_util.now()).date().isoformat()
            if lots and lots[-1].get("d") == today:
                lots[-1]["n"] = int(lots[-1]["n"]) + diff
            else:
                lots.append({"d": today, "n": diff})
        elif diff < 0:
            owed = -diff
            while owed > 0 and lots:
                take = min(owed, int(lots[0]["n"]))
                lots[0]["n"] = int(lots[0]["n"]) - take
                owed -= take
                if lots[0]["n"] <= 0:
                    lots.pop(0)
        record["lots"] = lots
        return lots

    def take_lots(self, child, amount: int) -> list[dict[str, Any]]:
        """Take ``amount`` points off ``child``'s oldest lots and return them.

        For points leaving the balance but staying the child's — savings moved
        into a wish. They come back through ``restore_lots`` with their dates.
        Call it before lowering the balance, so the lots still match it; the
        reconcile then sees the balance and the lots fall together. [] when
        expiry is off.
        """
        if not self.points_expiry_enabled() or amount <= 0:
            return []
        lots = self._reconcile_lots(child)
        taken: list[dict[str, Any]] = []
        owed = amount
        while owed > 0 and lots:
            take = min(owed, int(lots[0]["n"]))
            taken.append({"d": lots[0]["d"], "n": take})
            lots[0]["n"] = int(lots[0]["n"]) - take
            owed -= take
            if lots[0]["n"] <= 0:
                lots.pop(0)
        return taken

    def restore_lots(self, child, lots: list[dict[str, Any]]) -> None:
        """Put lots from ``take_lots`` back, dated as they were.

        Call it before raising the balance, for the same reason as above.
        """
        if not self.points_expiry_enabled() or not lots:
            return
        current = self._reconcile_lots(child)
        for lot in lots:
            day = str(lot.get("d", ""))
            n = int(lot.get("n", 0) or 0)
            if not day or n <= 0:
                continue
            match = next((c for c in current if c.get("d") == day), None)
            if match is not None:
                match["n"] = int(match["n"]) + n
            else:
                current.append({"d": day, "n": n})
        current.sort(key=lambda lot: str(lot.get("d", "")))
        self._expiry_record(child.id)["lots"] = current

    def reconcile_points_lots(self) -> None:
        """Run on every refresh. Cheap: one pass per child, no save of its own."""
        if not self.points_expiry_enabled():
            section = self.storage.get_section(_SECTION, dict)
            if section:
                section.clear()
            return
        for child in self.storage.get_children():
            self._reconcile_lots(child)

    def _lot_expires_on(self, lot: dict[str, Any]) -> date | None:
        try:
            return date.fromisoformat(str(lot.get("d", ""))) + timedelta(days=self.points_expiry_days())
        except ValueError:
            return None

    # ── the tick ─────────────────────────────────────────────────────────

    async def async_check_points_expiry(self) -> int:
        """Expire old lots and warn about the next ones. Returns points expired."""
        self.reconcile_points_lots()
        if not self.points_expiry_enabled():
            return 0
        today = dt_util.as_local(dt_util.now()).date()
        now = dt_util.now()
        expired_total = 0
        changed = False
        for child in self.storage.get_children():
            lots = self._reconcile_lots(child)
            gone = [lot for lot in lots if (exp := self._lot_expires_on(lot)) is not None and exp <= today]
            amount = min(self._lot_total(gone), max(0, int(child.points or 0)))
            if gone:
                self._expiry_record(child.id)["lots"] = [lot for lot in lots if lot not in gone]
                changed = True
            if amount > 0:
                child.points -= amount
                self.storage.update_child(child)
                self.storage.add_points_transaction(
                    PointsTransaction(child_id=child.id, points=-amount, reason=POINTS_EXPIRED_REASON, created_at=now)
                )
                self.hass.bus.async_fire(
                    "taskmate_points_expired",
                    {
                        "child_id": child.id,
                        "child_name": child.name,
                        "points": amount,
                        "timestamp": now.isoformat(),
                    },
                )
                expired_total += amount
            changed = await self._warn_points_expiring(child) or changed
        if changed:
            await self.storage.async_save()
        if expired_total:
            await self.async_refresh()
        # The strip appears as a day enters the warning window with no data change.
        shown = tuple(sorted((c.id, str(self.points_expiry_summary(c.id))) for c in self.storage.get_children()))
        if shown != getattr(self, "_points_expiry_shown", shown):
            self.external_state_version += 1
            self.async_update_listeners()
        self._points_expiry_shown = shown
        return expired_total

    async def _warn_points_expiring(self, child) -> bool:
        """Push the opt-in warning once per expiry date. True if the record changed."""
        upcoming = self.points_expiry_summary(child.id)
        if not upcoming:
            return False
        record = self._expiry_record(child.id)
        if record.get("warned") == upcoming["date"]:
            return False
        record["warned"] = upcoming["date"]
        self.hass.bus.async_fire(
            "taskmate_points_expiring",
            {
                "child_id": child.id,
                "child_name": child.name,
                "points": upcoming["points"],
                "date": upcoming["date"],
                "timestamp": dt_util.now().isoformat(),
            },
        )
        if getattr(self, "notifications", None):
            from . import notify_strings

            try:
                await self.notifications.fire(
                    NOTIF_TYPE_POINTS_EXPIRING,
                    {
                        "child_id": child.id,
                        "child_name": child.name,
                        "points": upcoming["points"],
                        "points_name": self.storage.get_points_name(),
                        "date": notify_strings.short_date(self.hass, date.fromisoformat(upcoming["date"])),
                    },
                    only_recipients={f"child:{child.id}"},
                )
            except Exception:  # noqa: BLE001 - a push must never stop the expiry
                _LOGGER.exception("TaskMate: points-expiry notification failed")
        return True

    # ── state for the sensor and the panel ───────────────────────────────

    def points_expiry_summary(self, child_id: str) -> dict[str, Any] | None:
        """``{"points", "date"}`` for the next expiry inside the warning window, else None."""
        if not self.points_expiry_enabled():
            return None
        warn = self.points_expiry_warn_days()
        if warn <= 0:
            return None
        record = self.storage.get_section(_SECTION, dict).get(child_id)
        if not isinstance(record, dict):
            return None
        today = dt_util.as_local(dt_util.now()).date()
        by_day: dict[date, int] = {}
        for lot in record.get("lots") or []:
            if not isinstance(lot, dict):
                continue
            exp = self._lot_expires_on(lot)
            if exp is not None and today < exp <= today + timedelta(days=warn):
                by_day[exp] = by_day.get(exp, 0) + int(lot.get("n", 0) or 0)
        if not by_day:
            return None
        first = min(by_day)
        return {"points": by_day[first], "date": first.isoformat()} if by_day[first] > 0 else None
