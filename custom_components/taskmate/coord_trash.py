"""Recently deleted: a deleted chore, reward or quest waits 7 days before it is gone.

Deleting one of these keeps a snapshot of the item and of everything its
delete clears (a chore's completions and orderings, a reward's claims and
savings, a quest's progress). The panel lists the snapshots and offers
Restore, and straight after a delete it shows an Undo that does the same.

A restore puts the item back under its old id, so its Home Assistant entities
and their history line up again. It refuses if something already uses that id.

Things a delete settles for good are not brought back: a chore's open swap
requests and teamwork joins, and its auctions (live ones were called off and
the bidders told). A reward's savings were refunded when it went; restoring
moves them back into the jar, as far as each child's balance still allows.

A chore's picture stays on disk while its snapshot is kept, and is deleted
with the snapshot after 7 days (unless another chore shows it).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from .models import Chore, PointsTransaction, PoolAllocation, Quest, Reward

_LOGGER = logging.getLogger(__name__)

TRASH_SECTION = "recently_deleted"
TRASH_KEEP_DAYS = 7
TRASH_KINDS = ("chore", "reward", "quest")


class RecentlyDeletedMixin:
    """Snapshots of deleted chores, rewards and quests, with restore."""

    def _trash(self) -> list[dict]:
        return self.storage.get_section(TRASH_SECTION, list)

    def _trash_put(self, kind: str, item: dict, extra: dict | None = None) -> None:
        """Keep a snapshot of a deleted item (the caller saves)."""
        trash = self._trash()
        trash[:] = [e for e in trash if not (e.get("kind") == kind and e.get("id") == item.get("id"))]
        trash.append(
            {
                "kind": kind,
                "id": item.get("id", ""),
                "name": item.get("name", ""),
                "deleted_at": dt_util.now().isoformat(),
                "item": item,
                "extra": extra or {},
            }
        )

    def _trash_images(self) -> set[str]:
        """Pictures a kept chore or reward snapshot still needs."""
        return {
            (e.get("item") or {}).get(key)
            for e in self._trash()
            if isinstance(e, dict) and e.get("kind") in ("chore", "reward")
            for key in ("image_url", "reference_image_url")
        } - {None, ""}

    def recently_deleted(self) -> list[dict]:
        """What the panel lists, newest first (no payloads)."""
        out = [
            {"kind": e.get("kind"), "id": e.get("id"), "name": e.get("name", ""), "deleted_at": e.get("deleted_at")}
            for e in self._trash()
            if isinstance(e, dict) and e.get("kind") in TRASH_KINDS
        ]
        return sorted(out, key=lambda e: e.get("deleted_at") or "", reverse=True)

    # ── snapshots ────────────────────────────────────────────────────────

    def _snapshot_chore(self, chore_id: str) -> None:
        """Keep a deleted chore and what its delete clears. Call before removing."""
        data = self.storage.data
        item = next((dict(c) for c in data.get("chores", []) if c.get("id") == chore_id), None)
        if item is None:
            return
        groups = [
            {"group_id": g.get("id"), "index": g.get("chore_ids", []).index(chore_id)}
            for g in data.get("task_groups", [])
            if chore_id in g.get("chore_ids", [])
        ]
        display = data.get("chore_display_order", [])
        extra = {
            "completions": [dict(c) for c in data.get("completions", []) if c.get("chore_id") == chore_id],
            "last_completed": dict(data.get("last_completed", {}).get(chore_id, {}) or {}),
            "weekly_target_bonuses": {
                k: v for k, v in (data.get("weekly_target_bonuses") or {}).items() if k.startswith(f"{chore_id}:")
            },
            "scheduled_changes": [dict(c) for c in data.get("scheduled_changes", []) if c.get("chore_id") == chore_id],
            "task_groups": groups,
            "display_index": display.index(chore_id) if chore_id in display else None,
            "chore_order": {
                c.get("id"): c.get("chore_order", []).index(chore_id)
                for c in data.get("children", [])
                if chore_id in (c.get("chore_order") or [])
            },
        }
        self._trash_put("chore", item, extra)

    def _snapshot_reward(self, reward_id: str) -> None:
        """Keep a deleted reward with its claims and savings. Call before removing."""
        data = self.storage.data
        rewards = data.get("rewards", [])
        index = next((i for i, r in enumerate(rewards) if r.get("id") == reward_id), None)
        if index is None:
            return
        extra = {
            "index": index,
            "claims": [dict(c) for c in data.get("reward_claims", []) if c.get("reward_id") == reward_id],
            "pool_allocations": [
                dict(a)
                for a in data.get("pool_allocations", [])
                if a.get("reward_id") == reward_id and int(a.get("allocated_points", 0) or 0) > 0
            ],
        }
        self._trash_put("reward", dict(rewards[index]), extra)

    def _snapshot_quest(self, quest_id: str) -> None:
        data = self.storage.data
        item = next((dict(q) for q in data.get("quests", []) if q.get("id") == quest_id), None)
        if item is None:
            return
        progress = (data.get("quest_progress") or {}).get(quest_id) or {}
        self._trash_put("quest", item, {"progress": {k: dict(v) for k, v in progress.items()}})

    # ── restore ──────────────────────────────────────────────────────────

    async def async_restore_deleted(self, kind: str, item_id: str) -> dict:
        """Bring a deleted item back under its old id. Returns its list entry."""
        trash = self._trash()
        entry = next((e for e in trash if e.get("kind") == kind and e.get("id") == item_id), None)
        if entry is None:
            raise ValueError("Nothing to restore: it was never deleted or has been purged")
        exists = {
            "chore": self.storage.get_chore,
            "reward": self.storage.get_reward,
            "quest": self.storage.get_quest,
        }[kind]
        if exists(item_id) is not None:
            raise ValueError(f"Something with id {item_id} already exists")
        item = dict(entry.get("item") or {})
        extra = entry.get("extra") or {}
        children = {c.id: c for c in self.storage.get_children()}
        if kind == "chore":
            await self._restore_chore(item, extra, children)
        elif kind == "reward":
            self._restore_reward(item, extra, children)
        else:
            self._restore_quest(item, extra, children)
        trash.remove(entry)
        await self.storage.async_save()
        await self.async_refresh()
        return {"kind": kind, "id": item_id, "name": entry.get("name", "")}

    async def _restore_chore(self, item: dict, extra: dict, children: dict) -> None:
        data = self.storage.data
        chore = Chore.from_dict(item)
        # Its calendar events were taken down with it; publish them afresh.
        chore.publish_calendar_published_dates = []
        self.storage.add_chore(chore)
        for comp in extra.get("completions", []):
            if comp.get("child_id") in children or comp.get("child_id") == "__parent__":
                data.setdefault("completions", []).append(comp)
        last = {k: v for k, v in (extra.get("last_completed") or {}).items() if k in children}
        if last:
            data.setdefault("last_completed", {})[chore.id] = last
        bonuses = data.get("weekly_target_bonuses")
        if not isinstance(bonuses, dict):
            bonuses = data["weekly_target_bonuses"] = {}
        bonuses.update(extra.get("weekly_target_bonuses") or {})
        data.setdefault("scheduled_changes", []).extend(extra.get("scheduled_changes") or [])
        for ref in extra.get("task_groups", []):
            for g in data.get("task_groups", []):
                if g.get("id") == ref.get("group_id") and chore.id not in g.get("chore_ids", []):
                    g.setdefault("chore_ids", []).insert(int(ref.get("index") or 0), chore.id)
        if extra.get("display_index") is not None:
            order = data.setdefault("chore_display_order", [])
            if chore.id not in order:
                order.insert(int(extra["display_index"]), chore.id)
        for child_id, index in (extra.get("chore_order") or {}).items():
            child = children.get(child_id)
            if child and chore.id not in child.chore_order:
                child.chore_order.insert(int(index), chore.id)
                self.storage.update_child(child)
        if chore.publish_calendar_entities:
            try:
                await self._publish_chore_to_calendars(chore)
                self.storage.update_chore(chore)
            except Exception:  # noqa: BLE001
                _LOGGER.warning("Restored chore %s, but its calendar events could not be published", chore.id)

    def _restore_reward(self, item: dict, extra: dict, children: dict) -> None:
        data = self.storage.data
        reward = Reward.from_dict(item)
        rewards = data.setdefault("rewards", [])
        rewards.insert(min(int(extra.get("index") or 0), len(rewards)), reward.to_dict())
        for claim in extra.get("claims", []):
            if claim.get("child_id") in children:
                data.setdefault("reward_claims", []).append(claim)
        # The savings were refunded on delete: move them back, as far as the
        # child still has the points.
        for alloc in extra.get("pool_allocations", []):
            child = children.get(alloc.get("child_id"))
            if not child:
                continue
            amount = min(int(alloc.get("allocated_points", 0) or 0), max(0, child.points))
            if amount <= 0:
                continue
            child.points -= amount
            self.storage.update_child(child)
            self.storage.upsert_pool_allocation(
                PoolAllocation.from_dict(
                    {**alloc, "child_id": child.id, "reward_id": reward.id, "allocated_points": amount}
                )
            )
            self.storage.add_points_transaction(
                PointsTransaction(
                    child_id=child.id,
                    points=-amount,
                    reason=f"Allocated to pool: {reward.name}",
                    created_at=dt_util.now(),
                )
            )

    def _restore_quest(self, item: dict, extra: dict, children: dict) -> None:
        quest = Quest.from_dict(item)
        self.storage.add_quest(quest)
        progress = {k: v for k, v in (extra.get("progress") or {}).items() if k in children}
        if progress:
            self.storage.get_quest_progress()[quest.id] = progress

    # ── purge ────────────────────────────────────────────────────────────

    async def async_purge_recently_deleted(self) -> None:
        """Forget snapshots older than 7 days (a minutely step)."""
        trash = self._trash()
        if not trash:
            return
        cutoff = dt_util.now() - timedelta(days=TRASH_KEEP_DAYS)
        keep: list[dict] = []
        gone: list[dict] = []
        for entry in trash:
            try:
                when = datetime.fromisoformat(str(entry.get("deleted_at") or ""))
            except (TypeError, ValueError):
                when = None
            if when is not None and when.tzinfo is None:
                when = when.replace(tzinfo=cutoff.tzinfo)
            (gone if when is None or when <= cutoff else keep).append(entry)
        if not gone:
            return
        trash[:] = keep
        # The picture goes with the snapshot, unless a chore or another kept
        # snapshot still shows it (_async_release_image checks both).
        for entry in gone:
            if entry.get("kind") not in ("chore", "reward"):
                continue
            item = entry.get("item") or {}
            for key in ("image_url", "reference_image_url"):
                if item.get(key):
                    await self._async_release_image(item[key])
        await self.storage.async_save()
