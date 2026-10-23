"""Shopping-list jobs: a tagged to-do item becomes a chore.

Add "#tm fetch logs from the shed" to Home Assistant's shopping list (or
say it to Assist) and, within a couple of minutes, the children see
"🛒 Fetch logs from the shed". The tag (``#tm`` by default) only counts at
the start of the item.

Each item is turned into a chore once, keyed by the to-do item's uid. When
the chore is done (and approved, if it needs approval) TaskMate ticks the
item off the list. If the item is ticked off or deleted first, the chore
goes too — unless a child has already done it, in which case it stays for
the parent to approve.

The chore is a one-off: either the first child to do it gets the points,
or the jobs go round the chosen children in turn. A one-off normally only
lasts its own day, so while the item is still on the list and nobody has
done it, TaskMate carries the chore over to the next day.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

SHOPPING_JOB_MODES = ("first_come", "rotate")
SHOPPING_JOB_MAX_POINTS = 1000
DEFAULT_SHOPPING_ENTITY = "todo.shopping_list"
DEFAULT_SHOPPING_TAG = "#tm"
# How often the list is read. The tick runs every minute; a to-do read
# every other minute is plenty for "a job appears".
_POLL_EVERY = timedelta(minutes=2)
_NAME_MAX = 90


def shopping_job_name(summary: str, tag: str) -> str:
    """The chore name for a tagged item, or "" when it isn't one of ours."""
    text = (summary or "").strip()
    tag = (tag or "").strip()
    if not tag or not text.lower().startswith(tag.lower()):
        return ""
    rest = text[len(tag) :]
    # "#tm fetch" yes, "#tmp fetch" no.
    if rest and not rest[0].isspace() and rest[0] not in ":-":
        return ""
    rest = rest.lstrip(" \t:-").strip()
    if not rest:
        return ""
    return f"🛒 {rest[0].upper()}{rest[1:]}"[:_NAME_MAX]


class ShoppingJobsMixin:
    """Chores raised from tagged items on a to-do list."""

    # ── settings ─────────────────────────────────────────────────────────

    def shopping_jobs_enabled(self) -> bool:
        return bool(self.storage.get_setting("shopping_jobs_enabled", False))

    def shopping_jobs_entity(self) -> str:
        entity = str(self.storage.get_setting("shopping_jobs_entity", "") or "").strip()
        return entity if entity.startswith("todo.") else DEFAULT_SHOPPING_ENTITY

    def shopping_jobs_tag(self) -> str:
        return str(self.storage.get_setting("shopping_jobs_tag", "") or "").strip() or DEFAULT_SHOPPING_TAG

    def shopping_jobs_mode(self) -> str:
        mode = str(self.storage.get_setting("shopping_jobs_mode", "first_come") or "first_come")
        return mode if mode in SHOPPING_JOB_MODES else "first_come"

    def shopping_jobs_points(self) -> int:
        try:
            return max(0, min(SHOPPING_JOB_MAX_POINTS, int(self.storage.get_setting("shopping_jobs_points", 5))))
        except (TypeError, ValueError):
            return 5

    def shopping_jobs_children(self) -> list[str]:
        """The chosen children, else every child who isn't an adult."""
        children = self.storage.get_children()
        chosen = self.storage.get_setting("shopping_jobs_children", [])
        known = {c.id for c in children}
        if isinstance(chosen, list):
            picked = [cid for cid in chosen if cid in known]
            if picked:
                return picked
        return [c.id for c in children if not getattr(c, "is_adult", False)]

    # ── the list ─────────────────────────────────────────────────────────

    def _shopping_state(self) -> dict[str, Any]:
        state = self.storage.get_section("shopping_jobs", dict)
        if not isinstance(state.get("items"), dict):
            state["items"] = {}
        return state

    async def _async_shopping_items(self, entity_id: str) -> dict[str, str] | None:
        """``{uid: chore name}`` for every open tagged item; None when the list can't be read."""
        try:
            response = await self.hass.services.async_call(
                "todo",
                "get_items",
                {"entity_id": entity_id, "status": ["needs_action"]},
                blocking=True,
                return_response=True,
            )
        except Exception as err:  # noqa: BLE001 - a missing list must not stop the tick
            _LOGGER.debug("TaskMate: could not read %s: %s", entity_id, err)
            return None
        if not isinstance(response, dict):
            return None
        bucket = response.get(entity_id, response)
        items = bucket.get("items", []) if isinstance(bucket, dict) else []
        tag = self.shopping_jobs_tag()
        out: dict[str, str] = {}
        for item in items or []:
            if not isinstance(item, dict) or item.get("status", "needs_action") != "needs_action":
                continue
            uid = str(item.get("uid") or "")
            name = shopping_job_name(str(item.get("summary") or ""), tag)
            if uid and name:
                out[uid] = name
        return out

    async def _async_tick_off(self, entity_id: str, uid: str) -> None:
        try:
            await self.hass.services.async_call(
                "todo",
                "update_item",
                {"entity_id": entity_id, "item": uid, "status": "completed"},
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("TaskMate: could not tick %s off %s: %s", uid, entity_id, err)

    # ── the tick ─────────────────────────────────────────────────────────

    async def async_check_shopping_jobs(self) -> int:
        """Sync the list with its chores. Returns how many chores were raised."""
        if not self.shopping_jobs_enabled():
            return 0
        now = dt_util.now()
        last = getattr(self, "_shopping_last_poll", None)
        if last is not None and now - last < _POLL_EVERY:
            return 0
        self._shopping_last_poll = now
        entity_id = self.shopping_jobs_entity()
        open_items = await self._async_shopping_items(entity_id)
        if open_items is None:
            # Unreadable is not the same as empty: never remove chores on a failed read.
            return 0
        state = self._shopping_state()
        tracked: dict[str, dict[str, Any]] = state["items"]
        today = dt_util.as_local(now).date().isoformat()
        completions = self.storage.get_completions()
        changed = False
        created = 0

        for uid, record in list(tracked.items()):
            if record.get("done"):
                # Remembered until the item leaves the list, so a tick-off that
                # failed never turns the same item into a second chore.
                if uid not in open_items:
                    del tracked[uid]
                    changed = True
                continue
            chore = self.storage.get_chore(record.get("chore_id", ""))
            if chore is None:
                # A parent deleted the chore; the item stays on the list.
                del tracked[uid]
                changed = True
                continue
            done = [c for c in completions if c.chore_id == chore.id]
            if any(c.approved for c in done):
                if uid in open_items:
                    await self._async_tick_off(entity_id, uid)
                chore.enabled = False
                self.storage.update_chore(chore)
                record["done"] = True
                changed = True
                self._fire_shopping_job("done", chore, uid)
                continue
            if uid not in open_items:
                if not done:
                    del tracked[uid]
                    self._fire_shopping_job("removed", chore, uid)
                    await self.async_remove_chore(chore.id, keep_deleted=False)
                # Done but waiting for approval: it stays for the parent.
                continue
            # Still wanted and nobody has done it: carry the one-off over to today.
            if not done and (not chore.enabled or chore.created_date != today):
                chore.enabled = True
                chore.created_date = today
                chore.disabled_for = []
                self.storage.update_chore(chore)
                changed = True

        for uid, name in open_items.items():
            if uid in tracked:
                continue
            chore = await self._async_raise_shopping_chore(name)
            if chore is None:
                continue
            tracked[uid] = {"chore_id": chore.id, "added": now.isoformat()}
            created += 1
            changed = True
            self._fire_shopping_job("added", chore, uid)

        if changed:
            await self.storage.async_save()
            await self.async_refresh()
        return created

    async def _async_raise_shopping_chore(self, name: str):
        pool = self.shopping_jobs_children()
        if not pool:
            return None
        state = self._shopping_state()
        if self.shopping_jobs_mode() == "rotate":
            turn = int(state.get("rotation", 0) or 0)
            assigned = [pool[turn % len(pool)]]
            state["rotation"] = turn + 1
            assignment_mode = "everyone"
        else:
            assigned = pool
            assignment_mode = "first_come" if len(pool) > 1 else "everyone"
        return await self.async_add_chore(
            name=name,
            points=self.shopping_jobs_points(),
            assigned_to=assigned,
            schedule_mode="one_shot",
            time_category="anytime",
            assignment_mode=assignment_mode,
        )

    def _fire_shopping_job(self, kind: str, chore, uid: str) -> None:
        self.hass.bus.async_fire(
            "taskmate_shopping_job",
            {
                "kind": kind,
                "chore_id": chore.id,
                "chore_name": chore.name,
                "item_uid": uid,
                "child_ids": list(chore.assigned_to),
                "timestamp": dt_util.now().isoformat(),
            },
        )
