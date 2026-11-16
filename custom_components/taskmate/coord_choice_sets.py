"""Choice sets (#1259): "do at least N of these chores", the child picks which.

A choice set groups ordinary chores. The child owes the set, never a single
member: doing any ``min_required`` different members on a day fulfils it.

* Progress is counted from the day's completions, never stored. A pending
  completion counts (a child shouldn't fail because a parent is slow), a
  rejected one is deleted and so frees the slot, and a chore done twice
  counts once.
* The effective minimum is ``min(min_required, members open to the child
  that day)``, so a set whose chores are mostly off today can't be missed
  for chores that weren't there. Nothing open means nothing owed.
* An unmet set leaves ONE review item at the end of the day: a
  ``MandatoryMiss`` with ``set_id`` (``chore_id`` empty). The parent applies
  the penalty, postpones or dismisses it, exactly like a mandatory miss;
  nothing is ever deducted automatically.
* Member chores can't use rotation, first-come or the planner pool, can't be
  mandatory, and belong to one set at most.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from homeassistant.util import dt as dt_util

from .coord_set_times import mandatory_miss_key
from .errors import TaskMateError
from .models import ChoiceSet, MandatoryMiss

_LOGGER = logging.getLogger(__name__)

# Highest "pick at least" a set accepts, and the most chores in one set.
CHOICE_SET_MAX_MIN = 50
CHOICE_SET_MAX_CHORES = 100
CHOICE_SET_MAX_PENALTY = 100000
CHOICE_SET_NAME_MAX = 120

# Assignment modes a member chore may use: every assigned child owes it.
_MEMBER_MODES = {"", "everyone"}

# Where missed sets AND missed mandatory chores are reviewed: the approvals
# card (as before), the admin panel's Today page, or both.
MISS_REVIEW_LOCATIONS = ("card", "panel", "both")
MISS_REVIEW_SETTING = "miss_review_location"


def _before(created: str, day: date) -> bool:
    """True when ``day`` is earlier than the ISO date ``created`` (unknown = False)."""
    try:
        return bool(created) and day < date.fromisoformat(str(created)[:10])
    except ValueError:
        return False


def choice_set_miss_key(set_id: str, child_id: str, due_date: str) -> str:
    """The handled-miss key for a set: its own namespace, never a chore's."""
    return mandatory_miss_key(f"set:{set_id}", child_id, due_date)


class ChoiceSetsMixin:
    """CRUD, progress and end-of-day misses for choice sets."""

    def miss_review_location(self) -> str:
        """``card`` (default), ``panel`` or ``both``."""
        value = self.storage.get_setting(MISS_REVIEW_SETTING, "card")
        return value if value in MISS_REVIEW_LOCATIONS else "card"

    # ── validation ───────────────────────────────────────────────────────
    def _choice_set_member_problem(self, chore) -> str | None:
        """The error key that keeps ``chore`` out of a set, or None."""
        if getattr(chore, "mandatory", False):
            return "choice_set_mandatory_member"
        mode = getattr(chore, "assignment_mode", "everyone") or ""
        if mode == "first_come":
            return "choice_set_first_come_member"
        if mode not in _MEMBER_MODES:
            return "choice_set_rotation_member"
        return None

    def _validate_choice_set(self, cs: ChoiceSet) -> None:
        if not cs.name.strip():
            raise TaskMateError("choice_set_name_required")
        if not cs.chore_ids:
            raise TaskMateError("choice_set_needs_chore")
        if len(cs.chore_ids) > CHOICE_SET_MAX_CHORES:
            raise TaskMateError("choice_set_too_many_chores", max=CHOICE_SET_MAX_CHORES)
        if cs.min_required > CHOICE_SET_MAX_MIN:
            raise TaskMateError("choice_set_min_too_high", max=CHOICE_SET_MAX_MIN)
        chores = {c.id: c for c in self.storage.get_chores()}
        taken = {cid: other for other in self.storage.get_choice_sets() if other.id != cs.id for cid in other.chore_ids}
        for chore_id in cs.chore_ids:
            chore = chores.get(chore_id)
            if chore is None:
                raise TaskMateError("chore_not_found", chore_id=chore_id)
            problem = self._choice_set_member_problem(chore)
            if problem:
                raise TaskMateError(problem, name=chore.name)
            if chore_id in taken:
                raise TaskMateError("choice_set_chore_in_other_set", name=chore.name, set=taken[chore_id].name)
        known = {c.id for c in self.storage.get_children()}
        for child_id in cs.assigned_to:
            if child_id not in known:
                raise TaskMateError("child_not_found", child_id=child_id)

    def _drop_stale_choice_set_refs(self, cs: ChoiceSet, before: ChoiceSet) -> None:
        """An edit keeps working after a member chore or child was deleted."""
        chores = {c.id for c in self.storage.get_chores()}
        children = {c.id for c in self.storage.get_children()}
        cs.chore_ids = [c for c in cs.chore_ids if c in chores or c not in before.chore_ids]
        cs.assigned_to = [c for c in cs.assigned_to if c in children or c not in before.assigned_to]

    # ── CRUD ─────────────────────────────────────────────────────────────
    async def async_create_choice_set(self, **fields) -> str:
        fields.pop("id", None)
        fields.pop("created_on", None)
        cs = ChoiceSet.from_dict(fields)
        cs.name = cs.name.strip()
        # The first day it can be missed is today.
        cs.created_on = dt_util.as_local(dt_util.now()).date().isoformat()
        self._validate_choice_set(cs)
        self.storage.add_choice_set(cs)
        await self.storage.async_save()
        await self.async_refresh()
        return cs.id

    async def async_update_choice_set(self, set_id: str, **fields) -> None:
        existing = self.storage.get_choice_set(set_id)
        if existing is None:
            raise TaskMateError("choice_set_not_found", set_id=set_id)
        data = existing.to_dict()
        data.update({k: v for k, v in fields.items() if v is not None and k != "created_on"})
        data["id"] = set_id
        cs = ChoiceSet.from_dict(data)
        cs.name = cs.name.strip()
        self._drop_stale_choice_set_refs(cs, existing)
        self._validate_choice_set(cs)
        self.storage.update_choice_set(cs)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_choice_set(self, set_id: str) -> None:
        if self.storage.get_choice_set(set_id) is None:
            raise TaskMateError("choice_set_not_found", set_id=set_id)
        self.storage.remove_choice_set(set_id)
        # Its open review items go with it.
        for miss in self.storage.get_mandatory_misses():
            if getattr(miss, "set_id", "") == set_id:
                self.storage.remove_mandatory_miss(miss.id)
        await self.storage.async_save()
        await self.async_refresh()

    # ── who and what ─────────────────────────────────────────────────────
    def _choice_set_applies_to(self, cs: ChoiceSet, child) -> bool:
        """Assigned children; an empty list means every child, grown-ups left out (#1061)."""
        if child is None:
            return False
        if cs.assigned_to:
            return child.id in cs.assigned_to
        return not getattr(child, "is_adult", False)

    def choice_set_member_ids(self, child_id: str | None = None) -> set[str]:
        """Chore ids inside an active set (that applies to ``child_id``, when given)."""
        child = self.storage.get_child(child_id) if child_id else None
        out: set[str] = set()
        for cs in self.storage.get_choice_sets():
            if not cs.active:
                continue
            if child_id and not self._choice_set_applies_to(cs, child):
                continue
            out.update(cs.chore_ids)
        return out

    def _choice_set_done_ids(self, cs: ChoiceSet, child_id: str, day: date) -> set[str]:
        """Distinct member chores the child did on ``day``, pending ones included."""
        members = set(cs.chore_ids)
        done: set[str] = set()
        for comp in self.storage.get_completions():
            if comp.chore_id not in members or getattr(comp, "bonus_subtask_id", ""):
                continue
            # A parent completion for one child (#1096) is that child's alone.
            owner = getattr(comp, "for_child_id", "") or comp.child_id
            if owner != child_id:
                continue
            try:
                if dt_util.as_local(comp.completed_at).date() != day:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            done.add(comp.chore_id)
        return done

    def _choice_set_open_ids(self, cs: ChoiceSet, child_id: str, day: date) -> set[str]:
        """Member chores the child could do on ``day``: enabled, theirs, scheduled, not hidden."""
        chores = {c.id: c for c in self.storage.get_chores()}
        out: set[str] = set()
        for chore_id in cs.chore_ids:
            chore = chores.get(chore_id)
            if chore is None or not getattr(chore, "enabled", True):
                continue
            assigned = getattr(chore, "assigned_to", []) or []
            if assigned and child_id not in assigned:
                continue
            if child_id in (getattr(chore, "disabled_for", []) or []):
                continue
            if _before(getattr(chore, "created_date", ""), day):
                continue  # the chore didn't exist yet that day
            if not self._is_chore_scheduled_for_date(chore, day):
                continue
            if self._chore_hidden_by_gate(chore):
                continue
            out.add(chore_id)
        return out

    def choice_set_status(self, cs: ChoiceSet, child_id: str, day: date | None = None) -> dict:
        """``{min, done, fulfilled}`` for one child and day; ``min`` is the effective minimum."""
        day = day or dt_util.as_local(dt_util.now()).date()
        done = self._choice_set_done_ids(cs, child_id, day)
        available = self._choice_set_open_ids(cs, child_id, day) | done
        effective = min(cs.min_required, len(available))
        return {"min": effective, "done": len(done), "fulfilled": len(done) >= effective}

    def choice_set_progress_for_child(self, child_id: str) -> list[dict]:
        """Today's sets for the overview sensor, kept small (16 KB cap)."""
        child = self.storage.get_child(child_id)
        out: list[dict] = []
        for cs in self.storage.get_choice_sets():
            if not cs.active or not self._choice_set_applies_to(cs, child):
                continue
            st = self.choice_set_status(cs, child_id)
            out.append(
                {
                    "set_id": cs.id,
                    "name": cs.name,
                    "icon": cs.icon,
                    "min": st["min"],
                    "done": st["done"],
                    "fulfilled": st["fulfilled"],
                    "chore_ids": list(cs.chore_ids),
                }
            )
        return out

    # ── streaks / perfect week: the set is one due item ──────────────────
    def choice_sets_due_items_met(self, child_id: str, day: date, due: set[str], done: set[str]) -> tuple[set, bool]:
        """Fold set members out of ``due`` and say whether every set is met.

        Returns ``(due_without_members, sets_met)``. A set counts as one due
        item when any member is due that day; it is met once the child did
        ``min(min_required, members due)`` different members.
        """
        child = self.storage.get_child(child_id)
        remaining = set(due)
        met = True
        for cs in self.storage.get_choice_sets():
            if not cs.active or not self._choice_set_applies_to(cs, child):
                continue
            members = set(cs.chore_ids)
            due_members = remaining & members
            remaining -= members
            effective = min(cs.min_required, len(due_members))
            if effective and len(done & members) < effective:
                met = False
        return remaining, met

    # ── end of day ───────────────────────────────────────────────────────
    async def async_detect_choice_set_misses(self, day: date) -> int:
        """One review item per unmet set, child and day. Idempotent."""
        existing = {
            (getattr(m, "set_id", ""), m.child_id, m.due_date)
            for m in self.storage.get_mandatory_misses()
            if getattr(m, "set_id", "")
        }
        handled = self.storage.get_handled_mandatory_keys()
        day_iso = day.isoformat()
        created = 0
        for cs in self.storage.get_choice_sets():
            if not cs.active or cs.min_required <= 0:
                continue
            # A set can't be missed on a day before it existed (a restart on
            # the day it was made runs the catch-up for yesterday).
            if _before(cs.created_on, day):
                continue
            for child in self.storage.get_children():
                if not self._choice_set_applies_to(cs, child):
                    continue
                if self.is_sick_day(child.id, day) or self._child_away(child.id, day):
                    continue
                # A birthday day off (#924) owes only mandatory chores.
                if self.is_birthday_day_off(child, day):
                    continue
                if (cs.id, child.id, day_iso) in existing:
                    continue
                if choice_set_miss_key(cs.id, child.id, day_iso) in handled:
                    continue
                st = self.choice_set_status(cs, child.id, day)
                if st["min"] <= 0 or st["fulfilled"]:
                    continue
                miss = MandatoryMiss(
                    chore_id="",
                    child_id=child.id,
                    due_date=day_iso,
                    period_id="anytime",
                    penalty_points=int(cs.penalty_points or 0),
                    set_id=cs.id,
                )
                self.storage.add_mandatory_miss(miss)
                created += 1
                self.hass.bus.async_fire(
                    "taskmate_choice_set_missed",
                    {
                        "miss_id": miss.id,
                        "set_id": cs.id,
                        "set_name": cs.name,
                        "child_id": child.id,
                        "child_name": child.name,
                        "done": st["done"],
                        "min": st["min"],
                        "penalty_points": miss.penalty_points,
                        "date": day_iso,
                        "timestamp": dt_util.now().isoformat(),
                    },
                )
        if created:
            await self.storage.async_save()
            await self.async_refresh()
        return created

    async def async_recheck_choice_set_miss(self, chore_id: str, child_id: str, day: date) -> int:
        """A completion stopped counting after the day ended: ask again (like mandatory misses)."""
        if chore_id not in self.choice_set_member_ids():
            return 0
        if day >= dt_util.as_local(dt_util.now()).date():
            return 0
        return await self.async_detect_choice_set_misses(day)

    async def async_catchup_choice_set_misses(self) -> None:
        """Startup: the midnight check may have run while HA was off."""
        yesterday = dt_util.as_local(dt_util.now()).date() - timedelta(days=1)
        await self.async_detect_choice_set_misses(yesterday)

    def fire_choice_set_fulfilled(self, child, chore_id: str, day: date) -> None:
        """Fire ``taskmate_choice_set_fulfilled`` when this completion met a set.

        Only the completion that brings a new member in can meet a set, so a
        second go at the same chore that day never fires it again.
        """
        if child is None or chore_id not in self.choice_set_member_ids(child.id):
            return
        for cs in self.storage.get_choice_sets():
            if not cs.active or chore_id not in cs.chore_ids or not self._choice_set_applies_to(cs, child):
                continue
            same = 0
            for comp in self.storage.get_completions():
                if comp.chore_id != chore_id or getattr(comp, "bonus_subtask_id", ""):
                    continue
                if (getattr(comp, "for_child_id", "") or comp.child_id) != child.id:
                    continue
                try:
                    if dt_util.as_local(comp.completed_at).date() == day:
                        same += 1
                except (AttributeError, TypeError, ValueError):
                    continue
            if same != 1:
                continue
            st = self.choice_set_status(cs, child.id, day)
            if st["min"] <= 0 or st["done"] != st["min"]:
                continue
            self.hass.bus.async_fire(
                "taskmate_choice_set_fulfilled",
                {
                    "set_id": cs.id,
                    "set_name": cs.name,
                    "child_id": child.id,
                    "child_name": child.name,
                    "chore_id": chore_id,
                    "done": st["done"],
                    "min": st["min"],
                    "timestamp": dt_util.now().isoformat(),
                },
            )

    async def async_prune_orphan_choice_set_misses(self) -> int:
        """Drop set misses whose set is gone or switched off."""
        sets = {c.id: c for c in self.storage.get_choice_sets()}
        removed = 0
        for m in self.storage.get_mandatory_misses():
            set_id = getattr(m, "set_id", "")
            if not set_id:
                continue
            cs = sets.get(set_id)
            if cs is None or not cs.active:
                self.storage.remove_mandatory_miss(m.id)
                removed += 1
        return removed
