"""Season event packs: seasonal content that installs and retires itself.

A parent switches a season's pack on in Settings → Seasons & events. When the
season's window starts (checked at startup, at midnight and straight after the
setting is saved) the pack's items are created as ordinary chores, rewards,
quests, challenges and badges for the chosen children, grown-ups left out.
When the window ends they are hidden, never deleted, so their history stays;
next year the same items come back rather than new copies.

What a pack installed is remembered in the ``season_packs`` storage section:
``{season: {"year", "state", "installed_on", "items": [{"kind", "key", "id"}]}}``.
That record is the pack's tag on its items (chores and rewards also carry a
``season.<season>.<key>`` template id). An item the parent deleted stays in
the record with nothing behind it, so it is never made again. "Remove pack"
deletes the items through Recently deleted and forgets the record.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from . import notify_strings
from .const import SEASON_ORDER, SEASON_PACK_CHILDREN_KEY, SEASON_PACK_KEYS
from .models import Badge, Challenge, Chore, Quest, Reward
from .season_packs import PACKS, async_load_strings, name_of, pack_contents
from .seasons import current_window, next_window

_LOGGER = logging.getLogger(__name__)

SEASON_PACKS_SECTION = "season_packs"
PACK_ITEM_KINDS = ("chore", "reward", "quest", "challenge", "badge")


def _on(value: Any) -> bool:
    return value in (True, "true")


class SeasonPacksMixin:
    """Install, retire, re-enable and remove season event packs."""

    # ── helpers ──────────────────────────────────────────────────────────

    def _season_registry(self) -> dict:
        return self.storage.get_section(SEASON_PACKS_SECTION, dict)

    def _season_lock(self) -> asyncio.Lock:
        lock = getattr(self, "_season_pack_lock", None)
        if lock is None:
            lock = self._season_pack_lock = asyncio.Lock()
        return lock

    def season_pack_children(self, season: str) -> list[str]:
        """Who the pack is for: the parent's pick, else every child. Never a grown-up."""
        kids = [c for c in self.storage.get_children() if not getattr(c, "is_adult", False)]
        chosen = (self.storage.get_setting(SEASON_PACK_CHILDREN_KEY, {}) or {}).get(season)
        if isinstance(chosen, list) and chosen:
            picked = [c.id for c in kids if c.id in chosen]
            if picked:
                return picked
        return [c.id for c in kids]

    def _pack_object(self, kind: str, item_id: str):
        getter = {
            "chore": self.storage.get_chore,
            "reward": self.storage.get_reward,
            "quest": self.storage.get_quest,
            "challenge": self.storage.get_challenge,
            "badge": self.storage.get_badge,
        }[kind]
        return getter(item_id)

    def _pack_save(self, kind: str, obj) -> None:
        {
            "chore": self.storage.update_chore,
            "reward": self.storage.update_reward,
            "quest": self.storage.update_quest,
            "challenge": self.storage.update_challenge,
            "badge": self.storage.update_badge,
        }[kind](obj)

    def season_pack_item_ids(self, kind: str, *, state: str | None = None) -> set[str]:
        """Ids of ``kind`` items the packs installed (only packs in ``state`` if given)."""
        out: set[str] = set()
        for rec in self._season_registry().values():
            if not isinstance(rec, dict) or (state and rec.get("state") != state):
                continue
            out.update(i.get("id") for i in rec.get("items", []) if i.get("kind") == kind and i.get("id"))
        return out

    # ── lifecycle ────────────────────────────────────────────────────────

    async def async_sync_season_packs(self, today: date | None = None, *, refresh: bool = True) -> list[str]:
        """Install, re-enable or retire every pack for today. Returns the seasons changed.

        Idempotent: a pack already installed for this season-year is left
        alone, so a restart, a second tick or a vacation day never makes a
        second set of items.
        """
        async with self._season_lock():
            today = today or dt_util.as_local(dt_util.now()).date()
            settings = self.storage.get_settings()
            registry = self._season_registry()
            changed: list[str] = []
            strings: dict[str, str] | None = None
            for season in SEASON_ORDER:
                if season not in PACKS:
                    continue
                rec = registry.get(season) if isinstance(registry.get(season), dict) else None
                window = (
                    current_window(season, today, settings) if _on(settings.get(SEASON_PACK_KEYS[season])) else None
                )
                if window:
                    year = window[0].year
                    if rec and rec.get("state") == "active" and rec.get("year") == year:
                        continue
                    if strings is None:
                        strings = await async_load_strings(self.hass, notify_strings._language(self.hass))
                    if rec is None:
                        rec = registry[season] = {"items": [], "installed_on": today.isoformat()}
                    new_year = rec.get("year") != year
                    self._season_activate(season, rec, window, today, new_year=new_year)
                    self._season_create_missing(season, rec, window, strings)
                    rec.update({"year": year, "state": "active"})
                    if new_year:
                        rec["installed_on"] = today.isoformat()
                    changed.append(season)
                elif rec and rec.get("state") == "active":
                    self._season_retire(rec, today)
                    rec["state"] = "retired"
                    changed.append(season)
            if changed:
                await self.storage.async_save()
                if refresh:
                    await self.async_refresh()
            return changed

    def _season_create_missing(self, season: str, rec: dict, window: tuple[date, date], strings: dict) -> None:
        """Create every pack item the record doesn't know yet (the first install,
        or something a newer TaskMate added). An item the record knows but that
        is gone was deleted by a parent, and stays gone."""
        pack = PACKS[season]
        known = {(i.get("kind"), i.get("key")) for i in rec.get("items", [])}
        kids = self.season_pack_children(season)
        items = rec.setdefault("items", [])
        chore_ids: dict[str, str] = {
            i["key"]: i["id"]
            for i in items
            if i.get("kind") == "chore" and i.get("id") and self.storage.get_chore(i["id"])
        }

        def add(kind: str, key: str, obj) -> None:
            {
                "chore": self.storage.add_chore,
                "reward": self.storage.add_reward,
                "quest": self.storage.add_quest,
                "challenge": self.storage.add_challenge,
                "badge": self.storage.add_badge,
            }[kind](obj)
            items.append({"kind": kind, "key": key, "id": obj.id})

        for key, spec in pack["chores"].items():
            if ("chore", key) in known:
                continue
            if "door" in spec:
                name = name_of(strings, "door", n=spec["door"], job=name_of(strings, f"{season}.{key}"))
            elif "egg" in spec:
                name = name_of(strings, "easter.egg", n=spec["egg"])
            else:
                name = name_of(strings, f"{season}.{key}")
            chore = Chore(
                name=name,
                points=spec["points"],
                icon=spec.get("icon", ""),
                assigned_to=list(kids),
                requires_approval=bool(spec.get("requires_approval", False)),
                time_category=spec.get("time_category", "anytime"),
                schedule_mode=spec["schedule_mode"],
                due_days=list(spec.get("due_days", [])),
                recurrence=spec.get("recurrence", "weekly"),
                assignment_mode="everyone",
                daily_limit=1,
            )
            if "day" in spec:
                chore.created_date = (window[0] + timedelta(days=spec["day"])).isoformat()
            chore.template_id = f"season.{season}.{key}"
            add("chore", key, chore)
            chore_ids[key] = chore.id

        if "quest" in pack and ("quest", pack["quest"]["key"]) not in known:
            q = pack["quest"]
            steps = [chore_ids[k] for k in q["steps"] if k in chore_ids]
            if steps:
                add(
                    "quest",
                    q["key"],
                    Quest(
                        name=name_of(strings, f"{season}.{q['key']}"),
                        icon=q["icon"],
                        steps=steps,
                        bonus_points=q["bonus"],
                        assigned_to=list(kids),
                    ),
                )
        if "reward" in pack and ("reward", pack["reward"]["key"]) not in known:
            r = pack["reward"]
            reward = Reward(
                name=name_of(strings, f"{season}.{r['key']}"),
                cost=r["cost"],
                icon=r["icon"],
                assigned_to=list(kids),
                expires_at=(window[1] + timedelta(days=1)).isoformat(),
            )
            reward.template_id = f"season.{season}.{r['key']}"
            add("reward", r["key"], reward)
        if "challenge" in pack and ("challenge", pack["challenge"]["key"]) not in known:
            c = pack["challenge"]
            add(
                "challenge",
                c["key"],
                Challenge(
                    name=name_of(strings, f"{season}.{c['key']}"),
                    description=name_of(strings, f"{season}.{c['key']}_desc"),
                    icon=c["icon"],
                    scope=c["scope"],
                    metric=c["metric"],
                    target=c["target"],
                    bonus_points=c["bonus"],
                    assigned_to=list(kids),
                ),
            )
        if "badge" in pack and ("badge", pack["badge"]["key"]) not in known:
            b = pack["badge"]
            # No criteria: the pack's own rule (jobs done in the window) awards
            # it, in _async_check_season_pack_badges.
            add(
                "badge",
                b["key"],
                Badge(
                    name=name_of(strings, f"{season}.{b['key']}"),
                    description=name_of(strings, f"{season}.{b['key']}_desc", count=b["goal"]),
                    icon=b["icon"],
                    tier=b["tier"],
                    point_bonus=b["bonus"],
                    assigned_to=list(kids),
                ),
            )

    def _season_activate(
        self, season: str, rec: dict, window: tuple[date, date], today: date, *, new_year: bool
    ) -> None:
        """Bring a retired pack's items back for this window (no new copies)."""
        pack = PACKS[season]
        kids = self.season_pack_children(season) if new_year else None
        for item in rec.get("items", []):
            kind, key, item_id = item.get("kind"), item.get("key"), item.get("id")
            if kind not in PACK_ITEM_KINDS or not item_id:
                continue
            obj = self._pack_object(kind, item_id)
            if obj is None:
                continue  # deleted by a parent: stays deleted
            if kids is not None and hasattr(obj, "assigned_to"):
                obj.assigned_to = list(kids)
            if kind == "chore":
                obj.enabled = True
                obj.disabled_for = []
                spec = pack["chores"].get(key) or {}
                if "day" in spec:
                    obj.created_date = (window[0] + timedelta(days=spec["day"])).isoformat()
            elif kind == "reward":
                obj.expires_at = (window[1] + timedelta(days=1)).isoformat()
            elif kind in ("quest", "challenge"):
                obj.active = True
                if kind == "quest" and new_year:
                    # A new season: everyone starts the quest again.
                    self.storage.get_quest_progress().pop(obj.id, None)
            elif kind == "badge":
                obj.enabled = True
            self._pack_save(kind, obj)

    def _season_retire(self, rec: dict, today: date) -> None:
        """Hide a pack's items until its next window. Nothing is deleted."""
        for item in rec.get("items", []):
            kind, item_id = item.get("kind"), item.get("id")
            if kind not in PACK_ITEM_KINDS or not item_id:
                continue
            obj = self._pack_object(kind, item_id)
            if obj is None:
                continue
            if kind == "chore":
                obj.enabled = False
            elif kind == "reward":
                # Expired from today: it can't be claimed, and the cards hide
                # it (sensor.py) while the pack is retired.
                obj.expires_at = today.isoformat()
            elif kind in ("quest", "challenge"):
                obj.active = False
            else:
                # A badge stays enabled so children keep the ones they earned;
                # the badges sensor hides it from those who haven't.
                continue
            self._pack_save(kind, obj)

    async def async_set_season_pack_children(self, season: str) -> None:
        """Re-assign an active pack's items after the parent changed who it is for."""
        rec = self._season_registry().get(season)
        if not isinstance(rec, dict) or rec.get("state") != "active":
            return
        kids = self.season_pack_children(season)
        for item in rec.get("items", []):
            obj = (
                self._pack_object(item.get("kind"), item.get("id") or "")
                if item.get("kind") in PACK_ITEM_KINDS
                else None
            )
            if obj is not None and hasattr(obj, "assigned_to"):
                obj.assigned_to = list(kids)
                self._pack_save(item["kind"], obj)

    async def async_remove_season_pack(self, season: str) -> int:
        """Delete everything the pack installed and switch the pack off.

        Chores, rewards and quests go to Recently deleted (7 days to restore);
        the challenge, which has no Recently deleted, is removed. The badge is
        removed only if nobody has earned it: a child never loses a badge they
        earned. An earned one is kept, assigned to just the children who have
        it, so it stays on their cards and is offered to nobody else (it has no
        criteria, so nothing awards it again).
        """
        if season not in PACKS:
            raise ValueError(f"Unknown season pack: {season}")
        async with self._season_lock():
            registry = self._season_registry()
            rec = registry.pop(season, None)
            removed = 0
            for item in (rec or {}).get("items", []):
                kind, item_id = item.get("kind"), item.get("id")
                if kind not in PACK_ITEM_KINDS or not item_id or self._pack_object(kind, item_id) is None:
                    continue
                if kind == "chore":
                    await self.async_remove_chore(item_id, refresh=False)
                elif kind == "reward":
                    await self.async_remove_reward(item_id, refresh=False)
                elif kind == "quest":
                    self._snapshot_quest(item_id)
                    self.storage.remove_quest(item_id)
                elif kind == "challenge":
                    self.storage.remove_challenge(item_id)
                else:
                    earners = sorted({a.child_id for a in self.storage.get_awarded_badges() if a.badge_id == item_id})
                    if earners:
                        badge = self.storage.get_badge(item_id)
                        badge.assigned_to = earners
                        self.storage.update_badge(badge)
                        continue
                    self.storage.remove_badge(item_id)
                removed += 1
            # Off, or the next tick would install it all again.
            self.storage.set_setting(SEASON_PACK_KEYS[season], False)
            await self.storage.async_save()
        await self.async_refresh()
        return removed

    # ── badges ───────────────────────────────────────────────────────────

    async def _async_check_season_pack_badges(self, child_id: str) -> None:
        """Award an active pack's badge once the child has done enough of its jobs."""
        badges = getattr(self, "badges", None)
        if badges is None:
            return
        registry = self._season_registry()
        today = dt_util.as_local(dt_util.now()).date()
        settings = self.storage.get_settings()
        for season, rec in registry.items():
            spec = (PACKS.get(season) or {}).get("badge")
            if not spec or not isinstance(rec, dict) or rec.get("state") != "active":
                continue
            window = current_window(season, today, settings)
            items = rec.get("items", [])
            badge_id = next((i.get("id") for i in items if i.get("kind") == "badge"), None)
            if not window or not badge_id or self.storage.has_awarded(child_id, badge_id):
                continue
            badge = self.storage.get_badge(badge_id)
            if badge is None or (badge.assigned_to and child_id not in badge.assigned_to):
                continue
            counted = {
                i.get("id")
                for i in items
                if i.get("kind") == "chore"
                and (spec.get("counts") != "advent" or str(i.get("key", "")).startswith("advent_"))
            }
            done = sum(
                1
                for comp in self.storage.get_completions()
                if comp.child_id == child_id
                and comp.approved
                and not comp.bonus_subtask_id
                and comp.chore_id in counted
                and window[0] <= dt_util.as_local(comp.completed_at).date() <= window[1]
            )
            if done >= int(spec["goal"]):
                await badges.award_manually(child_id, badge_id, manual=False)

    # ── what the cards and the panel see ─────────────────────────────────

    def season_pack_advent(self, today: date | None = None) -> dict | None:
        """The advent calendar while the Christmas pack is on and in its window.

        ``{"chore": today's door chore id or "", "door": its number or 0,
        "goal": doors for the badge, "badge": its name, "children": {child id:
        24 letters}}``. One letter per door: o opened, p waiting for a parent,
        m missed, t today, l locked (still to come), - not this child's door.
        """
        rec = self._season_registry().get("christmas")
        if not isinstance(rec, dict) or rec.get("state") != "active":
            return None
        today = today or dt_util.as_local(dt_util.now()).date()
        window = current_window("christmas", today, self.storage.get_settings())
        if not window:
            return None
        doors: list[tuple[int, Chore]] = []
        for item in rec.get("items", []):
            key = str(item.get("key", ""))
            if item.get("kind") != "chore" or not key.startswith("advent_"):
                continue
            chore = self.storage.get_chore(item.get("id") or "")
            if chore is not None:
                doors.append((int(key.split("_", 1)[1]), chore))
        if not doors:
            return None
        ids = {chore.id: n for n, chore in doors}
        states: dict[tuple[str, int], str] = {}
        for comp in self.storage.get_completions():
            n = ids.get(comp.chore_id)
            if n is None or comp.bonus_subtask_id:
                continue
            key = (comp.child_id, n)
            if comp.approved:
                states[key] = "o"
            else:
                states.setdefault(key, "p")
        kids = [c.id for c in self.storage.get_children() if not getattr(c, "is_adult", False)]
        by_door = dict(doors)
        children: dict[str, str] = {}
        today_door = 0
        for n, chore in doors:
            try:
                if date.fromisoformat(chore.created_date) == today:
                    today_door = n
            except (TypeError, ValueError):
                pass
        for cid in kids:
            letters = []
            mine = False
            for n in range(1, 25):
                chore = by_door.get(n)
                if chore is None or (chore.assigned_to and cid not in chore.assigned_to):
                    letters.append("-")
                    continue
                mine = True
                if (cid, n) in states:
                    letters.append(states[(cid, n)])
                    continue
                try:
                    day = date.fromisoformat(chore.created_date)
                except (TypeError, ValueError):
                    day = window[0] + timedelta(days=n - 1)
                letters.append("m" if day < today else "t" if day == today else "l")
            if mine:
                children[cid] = "".join(letters)
        if not children:
            return None
        badge_spec = PACKS["christmas"]["badge"]
        badge_id = next((i.get("id") for i in rec.get("items", []) if i.get("kind") == "badge"), "")
        badge = self.storage.get_badge(badge_id) if badge_id else None
        today_chore = by_door.get(today_door)
        return {
            "chore": today_chore.id if today_chore is not None and today_chore.enabled else "",
            "door": today_door,
            **({"goal": badge_spec["goal"], "badge": badge.name} if badge is not None else {}),
            "children": children,
        }

    def season_packs_state(self, today: date | None = None) -> list[dict]:
        """One row per pack for Settings → Seasons & events."""
        today = today or dt_util.as_local(dt_util.now()).date()
        settings = self.storage.get_settings()
        registry = self._season_registry()
        names = {c.id: c.name for c in self.storage.get_children()}
        out = []
        for season in SEASON_ORDER:
            if season not in PACKS:
                continue
            rec = registry.get(season) if isinstance(registry.get(season), dict) else {}
            window = next_window(season, today, settings)
            on = _on(settings.get(SEASON_PACK_KEYS[season]))
            if on and rec.get("state") == "active":
                state = "installed"
            elif on and window:
                state = "scheduled"
            elif on:
                state = "needs_date"
            else:
                state = "off"
            items = [i for i in rec.get("items", []) if i.get("kind") in PACK_ITEM_KINDS]
            live = [i for i in items if self._pack_object(i["kind"], i.get("id") or "") is not None]
            chosen = (settings.get(SEASON_PACK_CHILDREN_KEY) or {}).get(season) or []
            out.append(
                {
                    "season": season,
                    "emoji": PACKS[season]["emoji"],
                    "state": state,
                    **({"window": [window[0].isoformat(), window[1].isoformat()]} if window else {}),
                    **(
                        {"installed_on": rec["installed_on"]}
                        if state == "installed" and rec.get("installed_on")
                        else {}
                    ),
                    "items": len(live),
                    "children": [cid for cid in chosen if cid in names],
                    "contents": pack_contents(season),
                }
            )
        return out
