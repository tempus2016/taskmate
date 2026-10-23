"""Screen-time bank: rewards that buy minutes, spent while the child's devices are on.

A reward with ``screen_minutes`` set adds that many minutes to the child's
balance when a parent approves it. A parent can also top a balance up or take
minutes away (``adjust_screen_time``).

Each child can have devices: a TV switch, a console's smart plug, a media
player. While any of them is on, the minutely tick spends one minute. When
the balance drops to the warning level the child (and parents) hear about it
once; at zero a ``taskmate_screen_time_out`` event fires and, if the parent
switched on "Turn devices off at zero", TaskMate turns those devices off —
and keeps turning them off while the balance stays at zero.

Daily allowance: a parent can also hand out free minutes each day — one
amount on school days, another at weekends and holidays. A holiday is any
day inside a family vacation period, or while the family vacation calendar
has an event on. The balance is two buckets: today's allowance and the
"bank" (minutes bought with rewards, top-ups, carried-over allowance and an
opened jar). Watching spends the allowance first. At the start of each day
what is left of yesterday's allowance either expires (the default) or moves
into the bank; bought minutes always carry over.

Weekend jar: with the jar on, a child can save minutes they have not used
(today's allowance first, as it would otherwise expire, then banked minutes)
into a jar, up to its cap. Saved minutes are locked until the opening time
(Saturday 08:00 by default), when the whole jar empties into the bank.

Only ``homeassistant.turn_off`` is ever called, and only on entities a parent
listed for that child in Settings.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import NOTIF_TYPE_SCREEN_TIME_JAR_OPENED, NOTIF_TYPE_SCREEN_TIME_LOW, NOTIF_TYPE_SCREEN_TIME_OUT

_LOGGER = logging.getLogger(__name__)

SCREEN_TIME_MAX_MINUTES = 24 * 60 * 7  # a week of telly is plenty of bank
SCREEN_TIME_MAX_REWARD = 24 * 60
SCREEN_TIME_MAX_DEVICES = 10
DEFAULT_SCREEN_TIME_WARN = 10
SCREEN_TIME_LOG_KEEP = 20
# Device states that count as "watching". A paused film is still screen time;
# idle/standby/off are not.
_ACTIVE_STATES = frozenset({"on", "playing", "paused", "buffering"})
# Domains a device may come from. Turning off is only offered where it means
# something; a binary_sensor can be watched but never switched.
SCREEN_TIME_DOMAINS = ("switch", "media_player", "input_boolean", "binary_sensor", "remote", "light")
_SWITCHABLE = frozenset({"switch", "media_player", "input_boolean", "remote", "light"})
SCREEN_TIME_MAX_ALLOWANCE = 24 * 60
SCREEN_TIME_UNUSED_MODES = ("expire", "carry")
DEFAULT_JAR_CAP = 120
DEFAULT_JAR_OPEN_DAY = 5  # Saturday (Monday is 0)
DEFAULT_JAR_OPEN_TIME = "08:00"


def _hhmm(value: Any, default: str) -> time:
    try:
        hour, minute = str(value or default).split(":")
        return time(int(hour), int(minute))
    except (TypeError, ValueError):
        hour, minute = default.split(":")
        return time(int(hour), int(minute))


class ScreenTimeMixin:
    """Per-child screen-time balances, the burn-down and the stop at zero."""

    # ── settings ─────────────────────────────────────────────────────────

    def screen_time_enabled(self) -> bool:
        return bool(self.storage.get_setting("screen_time_enabled", False))

    def screen_time_warn_minutes(self) -> int:
        try:
            return max(0, min(120, int(self.storage.get_setting("screen_time_warn_minutes", DEFAULT_SCREEN_TIME_WARN))))
        except (TypeError, ValueError):
            return DEFAULT_SCREEN_TIME_WARN

    def screen_time_stop_at_zero(self) -> bool:
        return bool(self.storage.get_setting("screen_time_stop_at_zero", False))

    def screen_time_devices(self, child_id: str) -> list[str]:
        raw = self.storage.get_setting("screen_time_devices", {})
        if not isinstance(raw, dict):
            return []
        devices = raw.get(child_id)
        if not isinstance(devices, list):
            return []
        return [d for d in devices if isinstance(d, str) and d.split(".", 1)[0] in SCREEN_TIME_DOMAINS]

    def _screen_time_int(self, key: str, default: int, top: int) -> int:
        try:
            return max(0, min(top, int(self.storage.get_setting(key, default))))
        except (TypeError, ValueError):
            return default

    def screen_time_allowance_carries(self) -> bool:
        return self.storage.get_setting("screen_time_allowance_unused", "expire") == "carry"

    def screen_time_is_holiday(self, day: date) -> bool:
        """A weekend or holiday day: Saturday, Sunday, a vacation period, or the vacation calendar on now."""
        if day.weekday() >= 5 or self.is_vacation_day(day):
            return True
        # The calendar is read live, so it only speaks for today.
        return day == dt_util.now().date() and self._vacation_calendar_active()

    def screen_time_allowance_for(self, day: date) -> int:
        """Free minutes a child gets on ``day`` (0 = no allowance)."""
        if self.screen_time_is_holiday(day):
            return self._screen_time_int("screen_time_allowance_weekend", 0, SCREEN_TIME_MAX_ALLOWANCE)
        return self._screen_time_int("screen_time_allowance_school", 0, SCREEN_TIME_MAX_ALLOWANCE)

    def screen_time_jar_enabled(self) -> bool:
        return bool(self.storage.get_setting("screen_time_jar_enabled", False))

    def screen_time_jar_cap(self) -> int:
        return max(1, self._screen_time_int("screen_time_jar_cap", DEFAULT_JAR_CAP, SCREEN_TIME_MAX_MINUTES))

    def screen_time_jar_opening(self) -> tuple[int, str]:
        """``(weekday, "HH:MM")`` the jar opens at; Monday is 0."""
        day = self._screen_time_int("screen_time_jar_open_day", DEFAULT_JAR_OPEN_DAY, 6)
        at = _hhmm(self.storage.get_setting("screen_time_jar_open_time"), DEFAULT_JAR_OPEN_TIME)
        return day, at.strftime("%H:%M")

    def _screen_time_last_opening(self, now: datetime) -> datetime:
        """The most recent jar opening at or before ``now``."""
        weekday, at = self.screen_time_jar_opening()
        local = dt_util.as_local(now)
        opening = local.replace(hour=int(at[:2]), minute=int(at[3:]), second=0, microsecond=0)
        opening -= timedelta(days=(local.weekday() - weekday) % 7)
        if opening > local:
            opening -= timedelta(days=7)
        return opening

    # ── balances ─────────────────────────────────────────────────────────

    def _screen_time_record(self, child_id: str) -> dict[str, Any]:
        section = self.storage.get_section("screen_time", dict)
        record = section.get(child_id)
        if not isinstance(record, dict):
            # "minutes" is the bank (bought, topped up, carried over); it was the
            # whole balance before the daily allowance came, so old data reads as banked.
            record = {"minutes": 0, "allowance": 0, "jar": 0, "warned": False, "out": False, "log": []}
            section[child_id] = record
        return record

    def _screen_time_bucket(self, child_id: str, key: str) -> int:
        record = self.storage.get_section("screen_time", dict).get(child_id)
        if not isinstance(record, dict):
            return 0
        try:
            return max(0, int(record.get(key, 0) or 0))
        except (TypeError, ValueError):
            return 0

    def screen_time_balance(self, child_id: str) -> int:
        """What the child can watch now: today's allowance plus the bank."""
        return self._screen_time_bucket(child_id, "allowance") + self._screen_time_bucket(child_id, "minutes")

    def screen_time_allowance_left(self, child_id: str) -> int:
        return self._screen_time_bucket(child_id, "allowance")

    def screen_time_jar(self, child_id: str) -> int:
        return self._screen_time_bucket(child_id, "jar")

    def _screen_time_log(self, record: dict[str, Any], delta: int, reason: str) -> None:
        log = record.setdefault("log", [])
        log.append({"at": dt_util.now().isoformat(), "delta": delta, "reason": reason})
        del log[:-SCREEN_TIME_LOG_KEEP]

    def _screen_time_rearm(self, record: dict[str, Any], balance: int) -> None:
        if balance > self.screen_time_warn_minutes():
            record["warned"] = False
        if balance > 0:
            record["out"] = False

    def _screen_time_change(self, child_id: str, delta: int, reason: str, log: bool = True) -> int:
        """Add to the bank, or spend (allowance first). Returns the new balance."""
        record = self._screen_time_record(child_id)
        allowance = self.screen_time_allowance_left(child_id)
        bank = self._screen_time_bucket(child_id, "minutes")
        before = allowance + bank
        if delta >= 0:
            bank = min(SCREEN_TIME_MAX_MINUTES, bank + int(delta))
        else:
            spend = -int(delta)
            from_allowance = min(allowance, spend)
            allowance -= from_allowance
            bank = max(0, bank - (spend - from_allowance))
        record["allowance"] = allowance
        record["minutes"] = bank
        after = allowance + bank
        self._screen_time_rearm(record, after)
        if log and after != before:
            self._screen_time_log(record, after - before, reason)
        return after

    async def async_adjust_screen_time(self, child_id: str, minutes: int, reason: str = "") -> int:
        """Add (or, negative, take away) minutes. Returns the new balance."""
        child = self.storage.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        try:
            delta = int(minutes)
        except (TypeError, ValueError) as err:
            raise ValueError("Minutes must be a whole number") from err
        if delta == 0:
            return self.screen_time_balance(child_id)
        if abs(delta) > SCREEN_TIME_MAX_MINUTES:
            raise ValueError(f"Minutes cannot exceed {SCREEN_TIME_MAX_MINUTES}")
        balance = self._screen_time_change(child_id, delta, (reason or "adjusted").strip()[:60])
        await self.storage.async_save()
        self.hass.bus.async_fire(
            "taskmate_screen_time_changed",
            {
                "child_id": child.id,
                "child_name": child.name,
                "delta": delta,
                "minutes": balance,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        await self.async_refresh()
        return balance

    def _grant_screen_time(self, child, reward) -> None:
        """Called by the reward approval path; the caller saves and refreshes."""
        minutes = int(getattr(reward, "screen_minutes", 0) or 0)
        if minutes <= 0:
            return
        balance = self._screen_time_change(child.id, minutes, reward.name[:60])
        self.hass.bus.async_fire(
            "taskmate_screen_time_changed",
            {
                "child_id": child.id,
                "child_name": child.name,
                "delta": minutes,
                "minutes": balance,
                "reward_id": reward.id,
                "timestamp": dt_util.now().isoformat(),
            },
        )

    # ── the tick ─────────────────────────────────────────────────────────

    def screen_time_active(self, child_id: str) -> bool:
        """True when any of the child's devices is on right now."""
        for entity_id in self.screen_time_devices(child_id):
            state = self.hass.states.get(entity_id)
            if state is not None and str(state.state).lower() in _ACTIVE_STATES:
                return True
        return False

    async def async_check_screen_time(self) -> int:
        """Spend a minute for every child watching; warn, stop at zero.

        Returns how many children were charged. Runs from the minutely tick.
        """
        if not self.screen_time_enabled():
            return 0
        charged = 0
        changed = self._screen_time_new_day()
        changed = await self._async_screen_time_open_jars() or changed
        warn_at = self.screen_time_warn_minutes()
        watching = frozenset(
            c.id
            for c in self.storage.get_children()
            if self.screen_time_devices(c.id) and self.screen_time_active(c.id)
        )
        # A screen going off spends nothing, but the card's "on now" still has to clear.
        shown_changed = watching != getattr(self, "_screen_time_watching", frozenset())
        self._screen_time_watching = watching
        for child in self.storage.get_children():
            if child.id not in watching:
                continue
            record = self._screen_time_record(child.id)
            balance = self.screen_time_balance(child.id)
            if balance > 0:
                # One "watched -1" row a minute would bury the log; keep it out.
                balance = self._screen_time_change(child.id, -1, "watched", log=False)
                charged += 1
                changed = True
                if 0 < balance <= warn_at and not record.get("warned"):
                    record["warned"] = True
                    await self._announce_screen_time(child, NOTIF_TYPE_SCREEN_TIME_LOW, balance)
            if balance == 0:
                if not record.get("out"):
                    record["out"] = True
                    record["warned"] = True
                    changed = True
                    await self._announce_screen_time(child, NOTIF_TYPE_SCREEN_TIME_OUT, 0)
                if self.screen_time_stop_at_zero():
                    await self._async_screen_time_stop(child.id)
        if changed:
            await self.storage.async_save()
        if changed or shown_changed:
            # Once a minute at most: while somebody is watching, or as a screen goes on or off.
            await self.async_refresh()
        return charged

    def _screen_time_new_day(self) -> bool:
        """Once a day per child: roll yesterday's allowance over or let it go, then grant today's."""
        today = dt_util.now().date()
        carry = self.screen_time_allowance_carries()
        grant = self.screen_time_allowance_for(today)
        changed = False
        for child in self.storage.get_children():
            if getattr(child, "is_adult", False):
                continue
            record = self._screen_time_record(child.id)
            if record.get("allowance_day") == today.isoformat():
                continue
            left = self.screen_time_allowance_left(child.id)
            if left:
                record["allowance"] = 0
                if carry:
                    record["minutes"] = min(
                        SCREEN_TIME_MAX_MINUTES, self._screen_time_bucket(child.id, "minutes") + left
                    )
                else:
                    self._screen_time_log(record, -left, "allowance expired")
            record["allowance"] = grant
            record["allowance_day"] = today.isoformat()
            if grant:
                self._screen_time_log(record, grant, "allowance")
            self._screen_time_rearm(record, self.screen_time_balance(child.id))
            changed = True
        return changed

    async def _async_screen_time_open_jars(self) -> bool:
        """Empty every jar saved before the latest opening time into its bank."""
        if not self.screen_time_jar_enabled():
            return False
        opening = self._screen_time_last_opening(dt_util.now())
        changed = False
        for child in self.storage.get_children():
            jar = self.screen_time_jar(child.id)
            if not jar:
                continue
            record = self._screen_time_record(child.id)
            try:
                saved_at = datetime.fromisoformat(str(record.get("jar_saved_at") or ""))
            except ValueError:
                saved_at = None
            if saved_at is not None and saved_at >= opening:
                continue
            await self._async_screen_time_release_jar(child, record)
            changed = True
        return changed

    async def _async_screen_time_release_jar(self, child, record: dict[str, Any]) -> int:
        jar = self.screen_time_jar(child.id)
        record["jar"] = 0
        record.pop("jar_saved_at", None)
        balance = self._screen_time_change(child.id, jar, "jar opened")
        self.hass.bus.async_fire(
            f"taskmate_{NOTIF_TYPE_SCREEN_TIME_JAR_OPENED}",
            {
                "child_id": child.id,
                "child_name": child.name,
                "minutes": jar,
                "balance": balance,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        await self._notify_screen_time(child, NOTIF_TYPE_SCREEN_TIME_JAR_OPENED, jar)
        return jar

    async def async_save_screen_time(self, child_id: str, minutes: int | None = None) -> dict[str, int]:
        """Move unused minutes into the weekend jar (all that fits when ``minutes`` is None).

        Today's allowance goes in first, then banked minutes.
        """
        child = self.storage.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        if not self.screen_time_enabled() or not self.screen_time_jar_enabled():
            raise ValueError("The screen-time jar is switched off")
        jar = self.screen_time_jar(child_id)
        room = max(0, self.screen_time_jar_cap() - jar)
        available = self.screen_time_balance(child_id)
        wanted = available if minutes is None else int(minutes)
        amount = min(wanted, available, room)
        if amount <= 0:
            raise ValueError("The jar is full" if room <= 0 else "No minutes to save")
        record = self._screen_time_record(child_id)
        balance = self._screen_time_change(child_id, -amount, "saved in the jar")
        if not jar:
            record["jar_saved_at"] = dt_util.now().isoformat()
        record["jar"] = jar + amount
        await self.storage.async_save()
        self.hass.bus.async_fire(
            "taskmate_screen_time_saved",
            {
                "child_id": child.id,
                "child_name": child.name,
                "minutes": amount,
                "jar": jar + amount,
                "balance": balance,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        await self.async_refresh()
        return {"saved": amount, "jar": jar + amount, "minutes": balance}

    async def async_open_screen_time_jar(self, child_id: str) -> int:
        """A parent opens a child's jar early. Returns the minutes released."""
        child = self.storage.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        if not self.screen_time_jar(child_id):
            return 0
        released = await self._async_screen_time_release_jar(child, self._screen_time_record(child_id))
        await self.storage.async_save()
        await self.async_refresh()
        return released

    async def _announce_screen_time(self, child, type_id: str, minutes: int) -> None:
        self.hass.bus.async_fire(
            f"taskmate_{type_id}",
            {
                "child_id": child.id,
                "child_name": child.name,
                "minutes": minutes,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        await self._notify_screen_time(child, type_id, minutes)

    async def _notify_screen_time(self, child, type_id: str, minutes: int) -> None:
        if getattr(self, "notifications", None):
            try:
                await self.notifications.fire(
                    type_id,
                    {"child_id": child.id, "child_name": child.name, "minutes": minutes},
                    # This child and the parents, not every child routed.
                    only_recipients={f"child:{child.id}"} | {p.id for p in self.storage.get_parent_recipients()},
                )
            except Exception:  # noqa: BLE001 - a push must never stop the burn-down
                _LOGGER.exception("TaskMate: screen-time notification failed")

    async def _async_screen_time_stop(self, child_id: str) -> None:
        for entity_id in self.screen_time_devices(child_id):
            if entity_id.split(".", 1)[0] not in _SWITCHABLE:
                continue
            state = self.hass.states.get(entity_id)
            if state is None or str(state.state).lower() not in _ACTIVE_STATES:
                continue
            try:
                await self.hass.services.async_call(
                    "homeassistant", "turn_off", {"entity_id": entity_id}, blocking=False
                )
            except Exception:  # noqa: BLE001
                _LOGGER.warning("TaskMate: could not turn off %s at the end of screen time", entity_id)

    # ── state for the sensor and the panel ───────────────────────────────

    def screen_time_summary(self, child_id: str) -> dict[str, Any] | None:
        """Compact per-child block; None when the feature is off."""
        if not self.screen_time_enabled():
            return None
        out: dict[str, Any] = {
            "minutes": self.screen_time_balance(child_id),
            "active": bool(self.screen_time_devices(child_id)) and self.screen_time_active(child_id),
            "low": 0 < self.screen_time_balance(child_id) <= self.screen_time_warn_minutes(),
        }
        # Only when set: the overview attributes have a size cap.
        if allowance := self.screen_time_allowance_left(child_id):
            out["allowance"] = allowance
        if self.screen_time_jar_enabled():
            day, at = self.screen_time_jar_opening()
            out["jar"] = {
                "minutes": self.screen_time_jar(child_id),
                "cap": self.screen_time_jar_cap(),
                "day": day,
                "at": at,
            }
        return out

    def screen_time_state(self) -> dict[str, Any]:
        """Everything the panel's Settings section shows."""
        out: dict[str, Any] = {}
        for child in self.storage.get_children():
            record = self.storage.get_section("screen_time", dict).get(child.id) or {}
            out[child.id] = {
                "minutes": self.screen_time_balance(child.id),
                "allowance": self.screen_time_allowance_left(child.id),
                "jar": self.screen_time_jar(child.id),
                "devices": self.screen_time_devices(child.id),
                "active": self.screen_time_active(child.id),
                "log": list(record.get("log", []))[-5:] if isinstance(record, dict) else [],
            }
        return out
