"""Boost windows: a timed multiplier on chosen chores the children can see coming.

A parent opens a boost on the spot ("the next hour, bins and dishes pay
double"), schedules one for later the same way, or sets a recurring rule in
Settings ("Saturdays 09:00-11:00, garden jobs ×2"). Automations can do the
same through the ``start_boost`` / ``end_boost`` services.

A chore *completed* inside the window is priced with the multiplier, so
approving it after the window has closed still pays what the child saw.
When two boosts cover the same chore the bigger one applies.

On special days (the weekend multiplier, a birthday) ``boost_stacking``
decides: "highest" (default) pays the bigger of the boost and the special-day
multiplier, "stack" multiplies both.

When a boost begins TaskMate can wake wall tablets: a Fully Kiosk Browser
screen switch is turned on (with its screensaver turned off and the browser
brought to the front), and a Companion-app device is sent
``command_screen_on``. Only those two kinds of target are ever called.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, time, timedelta
from typing import Any

from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import notify_strings
from .const import NOTIF_TYPE_BOOST_STARTED
from .models import generate_id

_LOGGER = logging.getLogger(__name__)

BOOST_MIN_MULTIPLIER = 1.1
BOOST_MAX_MULTIPLIER = 5.0
BOOST_MAX_MINUTES = 24 * 60
BOOST_NAME_MAX = 60
BOOST_KEEP = 20
BOOST_MAX_RULES = 20
BOOST_STACKING_MODES = ("highest", "stack")
# A boost can be scheduled up to a week ahead.
BOOST_MAX_LEAD = timedelta(days=7)
# How far in the past a start time may be (clock skew on a quick tap).
_PAST_GRACE = timedelta(minutes=5)

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_MOBILE_APP_RE = re.compile(r"^mobile_app_[a-z0-9_]+$")
_FKB_SCREEN_SUFFIX = "-screenOn"


def _parse_time(value: Any) -> time:
    m = _TIME_RE.match(str(value or ""))
    if not m:
        raise ValueError(f"'{value}' is not a time like 09:30.")
    return time(int(m.group(1)), int(m.group(2)))


def _fmt_multiplier(value: float) -> str:
    return f"{value:g}"


class BoostsMixin:
    """Boost windows, recurring boost rules and the tablet wake-up."""

    # ── settings ─────────────────────────────────────────────────────────

    def boost_stacking(self) -> str:
        mode = str(self.storage.get_setting("boost_stacking", "highest") or "highest")
        return mode if mode in BOOST_STACKING_MODES else "highest"

    def _boost_list_setting(self, key: str) -> list[str]:
        raw = self.storage.get_setting(key, [])
        return [str(v) for v in raw if isinstance(v, str)] if isinstance(raw, list) else []

    # ── storage ──────────────────────────────────────────────────────────

    def _boosts(self) -> list[dict[str, Any]]:
        return self.storage.get_section("boosts", list)

    def boost_rules(self) -> list[dict[str, Any]]:
        return self.storage.get_section("boost_rules", list)

    @staticmethod
    def _boost_times(boost: dict[str, Any]) -> tuple[datetime, datetime] | None:
        try:
            return datetime.fromisoformat(boost["starts_at"]), datetime.fromisoformat(boost["ends_at"])
        except (KeyError, TypeError, ValueError):
            return None

    def _boost_status(self, boost: dict[str, Any], now: datetime) -> str:
        if boost.get("ended_early"):
            return "ended"
        times = self._boost_times(boost)
        if times is None:
            return "ended"
        start, end = times
        if now < start:
            return "upcoming"
        if now < end:
            return "active"
        return "ended"

    # ── validation ───────────────────────────────────────────────────────

    def _check_boost_fields(self, multiplier, chore_ids, child_ids) -> tuple[float, list[str], list[str]]:
        try:
            mult = round(float(multiplier), 2)
        except (TypeError, ValueError):
            raise ValueError("The multiplier must be a number.") from None
        if not BOOST_MIN_MULTIPLIER <= mult <= BOOST_MAX_MULTIPLIER:
            raise ValueError(f"Pick a multiplier from ×{BOOST_MIN_MULTIPLIER:g} to ×{BOOST_MAX_MULTIPLIER:g}.")
        chores = list(dict.fromkeys(str(c) for c in (chore_ids or [])))
        for cid in chores:
            if self.get_chore(cid) is None:
                raise ValueError(f"Chore {cid} not found.")
        kids = list(dict.fromkeys(str(c) for c in (child_ids or [])))
        for cid in kids:
            if self.get_child(cid) is None:
                raise ValueError(f"Child {cid} not found.")
        return mult, chores, kids

    # ── start / end ──────────────────────────────────────────────────────

    async def async_start_boost(
        self,
        multiplier: float,
        minutes: int,
        chore_ids: list[str] | None = None,
        child_ids: list[str] | None = None,
        starts_at: datetime | None = None,
        name: str = "",
        notify: bool = True,
        rule_id: str = "",
        rule_day: str = "",
        ends_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Open a boost now, or schedule one. Empty chore/child lists mean all of them."""
        mult, chores, kids = self._check_boost_fields(multiplier, chore_ids, child_ids)
        now = dt_util.now()
        start = starts_at or now
        if start.tzinfo is None:
            start = dt_util.as_local(start) if hasattr(dt_util, "as_local") else start
        # A recurring rule's window can already be under way when the tick
        # (or a rule saved mid-window) picks it up; it runs for what's left.
        if start < now - _PAST_GRACE and not rule_id:
            raise ValueError("A boost can't start in the past.")
        if start > now + BOOST_MAX_LEAD:
            raise ValueError("A boost can be scheduled up to a week ahead.")
        if ends_at is None:
            try:
                minutes = int(minutes)
            except (TypeError, ValueError):
                raise ValueError("The minutes must be a whole number.") from None
            if not 1 <= minutes <= BOOST_MAX_MINUTES:
                raise ValueError(f"Pick from 1 to {BOOST_MAX_MINUTES} minutes.")
            end = start + timedelta(minutes=minutes)
        else:
            end = ends_at
            minutes = max(1, int((end - start).total_seconds() // 60))
        boost = {
            "id": generate_id(),
            "name": str(name or "").strip()[:BOOST_NAME_MAX],
            "multiplier": mult,
            "chore_ids": chores,
            "child_ids": kids,
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
            "minutes": minutes,
            "notify": bool(notify),
            "announced": False,
            "ended": False,
            "ended_early": False,
            "created_at": now.isoformat(),
        }
        if rule_id:
            boost["rule_id"] = rule_id
            boost["rule_day"] = rule_day
        self._boosts().append(boost)
        await self.storage.async_save()
        if start <= now:
            await self._async_announce_boost(boost)
        await self.async_refresh()
        return {**self._boost_payload(boost), "status": self._boost_status(boost, dt_util.now())}

    async def async_end_boost(self, boost_id: str) -> None:
        """End a boost early, or call off one that hasn't started.

        A recurring rule's boost for today has the id ``rule:<rule id>:<day>``
        until it begins; ending that one skips the rule for the day.
        """
        now = dt_util.now()
        if boost_id.startswith("rule:"):
            row = next((b for s, b in self._boost_rows(now) if b.get("id") == boost_id), None)
            if row is None:
                raise ValueError("That boost has already ended.")
            day = boost_id.rsplit(":", 1)[-1]
            self._boosts().append(
                {
                    **{
                        k: row[k]
                        for k in ("name", "multiplier", "chore_ids", "child_ids", "starts_at", "ends_at", "minutes")
                    },
                    "id": generate_id(),
                    "rule_id": row["rule_id"],
                    "rule_day": day,
                    "notify": False,
                    "announced": False,
                    "ended": True,
                    "ended_early": True,
                    "ended_at": now.isoformat(),
                    "created_at": now.isoformat(),
                }
            )
            await self.storage.async_save()
            await self.async_refresh()
            return
        boost = next((b for b in self._boosts() if b.get("id") == boost_id), None)
        if boost is None or self._boost_status(boost, now) == "ended":
            raise ValueError("That boost has already ended.")
        was_active = self._boost_status(boost, now) == "active"
        boost["ended_early"] = True
        boost["ended"] = True
        boost["ended_at"] = now.isoformat()
        await self.storage.async_save()
        if was_active or boost.get("announced"):
            self._fire_boost_ended(boost, early=True)
        await self.async_refresh()

    def _boost_payload(self, boost: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": boost["id"],
            "name": boost.get("name", ""),
            "multiplier": boost["multiplier"],
            "chore_ids": list(boost.get("chore_ids") or []),
            "child_ids": list(boost.get("child_ids") or []),
            "starts_at": boost["starts_at"],
            "ends_at": boost["ends_at"],
            "minutes": boost.get("minutes", 0),
            **({"rule_id": boost["rule_id"]} if boost.get("rule_id") else {}),
        }

    def _fire_boost_ended(self, boost: dict[str, Any], early: bool) -> None:
        self.hass.bus.async_fire(
            "taskmate_boost_ended",
            {**self._boost_payload(boost), "ended_early": early, "timestamp": dt_util.now().isoformat()},
        )

    async def _async_announce_boost(self, boost: dict[str, Any]) -> None:
        """The moment a boost goes live: event, push, wake the tablets. Once."""
        if boost.get("announced"):
            return
        boost["announced"] = True
        await self.storage.async_save()
        payload = self._boost_payload(boost)
        self.hass.bus.async_fire("taskmate_boost_started", {**payload, "timestamp": dt_util.now().isoformat()})
        if boost.get("notify", True) and getattr(self, "notifications", None):
            chore_names = [c.name for cid in payload["chore_ids"] if (c := self.get_chore(cid))]
            kids = payload["child_ids"] or [c.id for c in self.storage.get_children()]
            try:
                await self.notifications.fire(
                    NOTIF_TYPE_BOOST_STARTED,
                    {
                        "boost_id": boost["id"],
                        "name": payload["name"],
                        "multiplier": _fmt_multiplier(payload["multiplier"]),
                        "minutes": payload["minutes"],
                        "chores_text": ", ".join(chore_names) or notify_strings.text(self.hass, "boost_all_chores"),
                        "points_name": self.storage.get_points_name(),
                    },
                    only_recipients={f"child:{cid}" for cid in kids},
                )
            except Exception:  # noqa: BLE001 - a push must never stop the boost
                _LOGGER.exception("TaskMate: boost notification failed")
        await self.async_wake_boost_screens()

    # ── the tick ─────────────────────────────────────────────────────────

    async def async_check_boosts(self, refresh: bool = True) -> int:
        """Start rule boosts, announce scheduled ones that began, close finished ones.

        Returns how many boosts changed state. Runs from the minutely tick.
        """
        now = dt_util.now()
        changed = 0
        changed += await self._async_fire_rules(now)
        for boost in list(self._boosts()):
            status = self._boost_status(boost, now)
            if status == "active" and not boost.get("announced"):
                await self._async_announce_boost(boost)
                changed += 1
            elif status == "ended" and not boost.get("ended"):
                boost["ended"] = True
                if boost.get("announced"):
                    self._fire_boost_ended(boost, early=False)
                changed += 1
        if changed:
            self._prune_boosts()
            await self.storage.async_save()
            if refresh:
                await self.async_refresh()
        return changed

    def _prune_boosts(self) -> None:
        boosts = self._boosts()
        done = [b for b in boosts if b.get("ended")]
        extra = len(done) - BOOST_KEEP
        if extra > 0:
            drop = {id(b) for b in sorted(done, key=lambda b: b.get("ends_at", ""))[:extra]}
            boosts[:] = [b for b in boosts if id(b) not in drop]

    # ── recurring rules ──────────────────────────────────────────────────

    def _rule_window(self, rule: dict[str, Any], day) -> tuple[datetime, datetime]:
        tz = dt_util.now().tzinfo
        start = datetime.combine(day, _parse_time(rule["start"]), tzinfo=tz)
        end = datetime.combine(day, _parse_time(rule["end"]), tzinfo=tz)
        return start, end

    def _rule_ran(self, rule_id: str, day_iso: str) -> bool:
        return any(b.get("rule_id") == rule_id and b.get("rule_day") == day_iso for b in self._boosts())

    async def _async_fire_rules(self, now: datetime) -> int:
        started = 0
        today = now.date()
        for rule in self.boost_rules():
            if not rule.get("enabled", True) or today.weekday() not in (rule.get("days") or []):
                continue
            try:
                start, end = self._rule_window(rule, today)
            except ValueError:
                continue
            if not start <= now < end or self._rule_ran(rule["id"], today.isoformat()):
                continue
            try:
                await self.async_start_boost(
                    multiplier=rule["multiplier"],
                    minutes=0,
                    chore_ids=[c for c in rule.get("chore_ids") or [] if self.get_chore(c)],
                    child_ids=[c for c in rule.get("child_ids") or [] if self.get_child(c)],
                    starts_at=start,
                    ends_at=end,
                    name=rule.get("name", ""),
                    notify=rule.get("notify", True),
                    rule_id=rule["id"],
                    rule_day=today.isoformat(),
                )
                started += 1
            except ValueError as err:
                _LOGGER.warning("TaskMate: boost rule '%s' could not start: %s", rule.get("name"), err)
        return started

    async def async_save_boost_rule(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Add or replace a recurring boost rule (matched on ``id``)."""
        days = sorted({int(d) for d in (rule.get("days") or []) if str(d).lstrip("-").isdigit() and 0 <= int(d) <= 6})
        if not days:
            raise ValueError("Pick at least one day.")
        start, end = _parse_time(rule.get("start")), _parse_time(rule.get("end"))
        if end <= start:
            raise ValueError("The end time must be after the start time.")
        mult, chores, kids = self._check_boost_fields(
            rule.get("multiplier"), rule.get("chore_ids"), rule.get("child_ids")
        )
        rules = self.boost_rules()
        rule_id = str(rule.get("id") or "")
        existing = next((r for r in rules if r.get("id") == rule_id), None) if rule_id else None
        if existing is None and len(rules) >= BOOST_MAX_RULES:
            raise ValueError(f"Up to {BOOST_MAX_RULES} recurring boosts.")
        clean = {
            "id": rule_id if existing else generate_id(),
            "name": str(rule.get("name") or "").strip()[:BOOST_NAME_MAX],
            "days": days,
            "start": start.strftime("%H:%M"),
            "end": end.strftime("%H:%M"),
            "multiplier": mult,
            "chore_ids": chores,
            "child_ids": kids,
            "notify": bool(rule.get("notify", True)),
            "enabled": bool(rule.get("enabled", True)),
        }
        if existing is not None:
            existing.clear()
            existing.update(clean)
        else:
            rules.append(clean)
        await self.storage.async_save()
        await self.async_refresh()
        return dict(clean)

    async def async_delete_boost_rule(self, rule_id: str) -> None:
        rules = self.boost_rules()
        if not any(r.get("id") == rule_id for r in rules):
            raise ValueError("That recurring boost no longer exists.")
        rules[:] = [r for r in rules if r.get("id") != rule_id]
        await self.storage.async_save()
        await self.async_refresh()

    # ── what applies to a completion ─────────────────────────────────────

    def _boost_rows(self, now: datetime) -> list[tuple[str, dict[str, Any]]]:
        """Every live boost plus today's enabled rules that haven't produced one yet."""
        rows = [(self._boost_status(b, now), b) for b in self._boosts()]
        rows = [(s, b) for s, b in rows if s != "ended"]
        today = now.date()
        for rule in self.boost_rules():
            if not rule.get("enabled", True) or today.weekday() not in (rule.get("days") or []):
                continue
            if self._rule_ran(rule["id"], today.isoformat()):
                continue
            try:
                start, end = self._rule_window(rule, today)
            except ValueError:
                continue
            if now >= end:
                continue
            rows.append(
                (
                    "upcoming" if now < start else "active",
                    {
                        "id": f"rule:{rule['id']}:{today.isoformat()}",
                        "name": rule.get("name", ""),
                        "multiplier": rule["multiplier"],
                        "chore_ids": rule.get("chore_ids") or [],
                        "child_ids": rule.get("child_ids") or [],
                        "starts_at": start.isoformat(),
                        "ends_at": end.isoformat(),
                        "minutes": int((end - start).total_seconds() // 60),
                        "rule_id": rule["id"],
                    },
                )
            )
        return rows

    def boost_multiplier_for(self, chore_id: str, child_id: str, when: datetime | None = None) -> float:
        """The biggest active boost covering this chore for this child, or 0."""
        now = when or dt_util.now()
        best = 0.0
        for status, boost in self._boost_rows(now):
            if status != "active":
                continue
            if boost.get("chore_ids") and chore_id not in boost["chore_ids"]:
                continue
            if boost.get("child_ids") and child_id not in boost["child_ids"]:
                continue
            best = max(best, float(boost.get("multiplier") or 0))
        return best

    def special_day_multiplier(self, child, day) -> float:
        """What the weekend and birthday bonuses together would multiply a chore by."""
        mult = 1.0
        if day.weekday() in (5, 6):
            try:
                weekend = float(self.storage.get_setting("weekend_multiplier", "2.0"))
            except (ValueError, TypeError):
                weekend = 2.0
            if weekend > 1.0:
                mult *= weekend
        if hasattr(self, "is_birthday") and self.is_birthday(child, day):
            mult *= self.birthday_multiplier()
        return mult

    def apply_boost(self, chore, child, points: int, when: datetime) -> tuple[int, float, bool]:
        """Price a completion made at ``when``. Returns (points, multiplier used or 0, stacked)."""
        if points <= 0:
            return points, 0.0, False
        mult = self.boost_multiplier_for(chore.id, child.id, when)
        if mult <= 1.0:
            return points, 0.0, False
        if self.boost_stacking() == "stack":
            return round(points * mult), mult, True
        special = self.special_day_multiplier(child, dt_util.as_local(when).date())
        if mult <= special:
            # Highest wins and the special day already pays more.
            return points, 0.0, False
        return round(points * mult), mult, False

    # ── what the cards and panel see ─────────────────────────────────────

    def boosts_state(self) -> list[dict[str, Any]]:
        """Active and upcoming boosts, active first, then by start time."""
        now = dt_util.now()
        out = []
        for status, boost in self._boost_rows(now):
            row = self._boost_payload(boost)
            row["status"] = status
            row["chore_names"] = [c.name for cid in row["chore_ids"] if (c := self.get_chore(cid))]
            out.append(row)
        out.sort(key=lambda r: (r["status"] != "active", r["starts_at"]))
        return out

    # ── waking the wall tablets ──────────────────────────────────────────

    def _fkb_targets(self) -> list[tuple[str, str, str]]:
        """(domain, service, entity_id) calls for each chosen Fully Kiosk screen."""
        wanted = self._boost_list_setting("boost_wake_screens")
        if not wanted:
            return []
        registry = er.async_get(self.hass)
        entities = getattr(registry, "entities", {}) or {}
        calls: list[tuple[str, str, str]] = []
        for entity_id in wanted:
            entry = registry.async_get(entity_id) if hasattr(registry, "async_get") else entities.get(entity_id)
            if entry is None or getattr(entry, "platform", "") != "fully_kiosk":
                continue
            unique_id = str(getattr(entry, "unique_id", "") or "")
            if not entity_id.startswith("switch.") or not unique_id.endswith(_FKB_SCREEN_SUFFIX):
                continue
            device_prefix = unique_id[: -len(_FKB_SCREEN_SUFFIX)]
            calls.append(("switch", "turn_on", entity_id))
            for other in entities.values() if isinstance(entities, dict) else []:
                if getattr(other, "platform", "") != "fully_kiosk":
                    continue
                other_uid = str(getattr(other, "unique_id", "") or "")
                if other_uid == f"{device_prefix}-screensaver" and other.entity_id.startswith("switch."):
                    calls.append(("switch", "turn_off", other.entity_id))
                elif other_uid == f"{device_prefix}-toForeground" and other.entity_id.startswith("button."):
                    calls.append(("button", "press", other.entity_id))
        return calls

    def _companion_targets(self) -> list[str]:
        return [s for s in self._boost_list_setting("boost_wake_devices") if _MOBILE_APP_RE.match(s)]

    async def async_wake_boost_screens(self) -> int:
        """Turn the chosen tablets' screens on. Failures are logged, never raised."""
        sent = 0
        try:
            calls = self._fkb_targets()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("TaskMate: could not read the Fully Kiosk screens to wake")
            calls = []
        for domain, service, entity_id in calls:
            try:
                await self.hass.services.async_call(domain, service, {"entity_id": entity_id}, blocking=False)
                sent += 1
            except Exception:  # noqa: BLE001
                _LOGGER.warning("TaskMate: could not wake %s", entity_id, exc_info=True)
        for notify_service in self._companion_targets():
            if not self.hass.services.has_service("notify", notify_service):
                continue
            try:
                await self.hass.services.async_call(
                    "notify", notify_service, {"message": "command_screen_on"}, blocking=False
                )
                sent += 1
            except Exception:  # noqa: BLE001
                _LOGGER.warning("TaskMate: could not wake %s", notify_service, exc_info=True)
        return sent

    def boost_wake_candidates(self) -> dict[str, list[dict[str, str]]]:
        """Fully Kiosk screen switches and Companion-app devices a parent can pick."""
        screens: list[dict[str, str]] = []
        try:
            registry = er.async_get(self.hass)
            for entry in (getattr(registry, "entities", {}) or {}).values():
                if getattr(entry, "platform", "") != "fully_kiosk" or not entry.entity_id.startswith("switch."):
                    continue
                if not str(getattr(entry, "unique_id", "") or "").endswith(_FKB_SCREEN_SUFFIX):
                    continue
                state = self.hass.states.get(entry.entity_id)
                name = (state.attributes.get("friendly_name") if state else None) or entry.entity_id
                screens.append({"entity_id": entry.entity_id, "name": str(name)})
        except Exception:  # noqa: BLE001
            _LOGGER.debug("TaskMate: no entity registry for wake candidates", exc_info=True)
        devices: list[dict[str, str]] = []
        try:
            services = self.hass.services.async_services().get("notify", {})
            for name in services:
                if _MOBILE_APP_RE.match(name):
                    devices.append({"service": name, "name": name[len("mobile_app_") :].replace("_", " ").title()})
        except Exception:  # noqa: BLE001
            _LOGGER.debug("TaskMate: could not list notify services", exc_info=True)
        screens.sort(key=lambda s: s["name"].lower())
        devices.sort(key=lambda d: d["name"].lower())
        return {"screens": screens, "devices": devices}
