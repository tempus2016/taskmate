"""Quests (chore chains) mixin for TaskMateCoordinator.

A quest is an ordered list of chores. Each child works through the chain one
step at a time: completing (and getting approval for) the chore at their
current step advances them. Finishing the final step awards the quest's bonus
points, fires a ``taskmate_quest_completed`` event + celebration, and either
resets progress (repeatable quests) or marks the quest complete for that child.
"""
from __future__ import annotations

import logging

from homeassistant.util import dt as dt_util

from .models import PointsTransaction, Quest

_LOGGER = logging.getLogger(__name__)


class QuestsMixin:
    """Mixin providing quest CRUD and chore-chain progression."""

    # ── CRUD ─────────────────────────────────────────────────────────────
    async def async_create_quest(self, **fields) -> str:
        quest = Quest.from_dict(fields)
        if not quest.name.strip():
            raise ValueError("Quest name is required")
        if not quest.steps:
            raise ValueError("A quest needs at least one step")
        self.storage.add_quest(quest)
        await self.storage.async_save()
        await self.async_refresh()
        return quest.id

    async def async_update_quest(self, quest_id: str, **fields) -> None:
        existing = self.storage.get_quest(quest_id)
        if not existing:
            raise ValueError(f"Quest {quest_id} not found")
        data = existing.to_dict()
        data.update(fields)
        data["id"] = quest_id
        updated = Quest.from_dict(data)
        if not updated.steps:
            raise ValueError("A quest needs at least one step")
        self.storage.update_quest(updated)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_delete_quest(self, quest_id: str) -> None:
        if not self.storage.get_quest(quest_id):
            raise ValueError(f"Quest {quest_id} not found")
        self.storage.remove_quest(quest_id)
        await self.storage.async_save()
        await self.async_refresh()

    # ── Progress helpers ─────────────────────────────────────────────────
    def _quest_applies_to(self, quest: Quest, child_id: str) -> bool:
        return not quest.assigned_to or child_id in quest.assigned_to

    def quest_progress_for_child(self, child_id: str) -> list[dict]:
        """Snapshot of every active quest assigned to ``child_id``.

        Returned shape (for sensors / cards):
        ``{quest_id, name, icon, total_steps, step, done, times_completed,
        bonus_points, next_chore_id}``.
        """
        out: list[dict] = []
        for quest in self.storage.get_quests():
            if not quest.active or not self._quest_applies_to(quest, child_id):
                continue
            prog = self.storage.get_quest_child_progress(quest.id, child_id)
            step = int(prog.get("step", 0))
            total = len(quest.steps)
            done = step >= total
            out.append({
                "quest_id": quest.id,
                "name": quest.name,
                "icon": quest.icon,
                "total_steps": total,
                "step": min(step, total),
                "done": done,
                "times_completed": int(prog.get("completed_count", 0)),
                "bonus_points": quest.bonus_points,
                "next_chore_id": quest.steps[step] if not done and step < total else "",
            })
        return out

    # ── Progression ──────────────────────────────────────────────────────
    async def _async_advance_quests(self, child_id: str, chore_id: str) -> None:
        """Advance any active quest whose current step is ``chore_id``.

        Called after a (non-bonus) chore completion is approved. Persists and
        refreshes only if a quest actually advanced.
        """
        child = self.get_child(child_id)
        if not child:
            return
        changed = False
        for quest in self.storage.get_quests():
            if not quest.active or not quest.steps:
                continue
            if not self._quest_applies_to(quest, child_id):
                continue
            prog = dict(self.storage.get_quest_child_progress(quest.id, child_id))
            step = int(prog.get("step", 0))
            if step >= len(quest.steps):
                continue  # already finished (non-repeatable)
            if quest.steps[step] != chore_id:
                continue  # this completion isn't the next step
            step += 1
            prog["step"] = step
            self.storage.set_quest_child_progress(quest.id, child_id, prog)
            changed = True

            if step >= len(quest.steps):
                await self._complete_quest(quest, child, prog)

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    async def _complete_quest(self, quest: Quest, child, prog: dict) -> None:
        """Award the quest bonus and reset/finalise progress."""
        prog["completed_count"] = int(prog.get("completed_count", 0)) + 1
        prog["last_completed"] = dt_util.now().isoformat()

        bonus = int(quest.bonus_points or 0)
        if bonus > 0:
            child.points += bonus
            child.total_points_earned += bonus
            child.career_score = child.total_points_earned - child.total_penalties_received
            self.storage.add_points_transaction(PointsTransaction(
                child_id=child.id, points=bonus,
                reason=f"Quest complete: {quest.name}", created_at=dt_util.now(),
            ))
            if hasattr(self, "_maybe_level_up"):
                await self._maybe_level_up(child)
            self.storage.update_child(child)

        self.hass.bus.async_fire("taskmate_quest_completed", {
            "child_id": child.id, "child_name": child.name,
            "quest_id": quest.id, "quest_name": quest.name,
            "bonus": bonus, "timestamp": dt_util.now().isoformat(),
        })
        if hasattr(self, "_celebrate"):
            await self._celebrate(
                child, "quest_completed",
                f"{child.name} completed the quest '{quest.name}'!",
                tier=3, extra={"quest_id": quest.id, "bonus": bonus},
            )

        # Repeatable quests start over; one-shot quests stay complete.
        if quest.repeatable:
            prog["step"] = 0
        self.storage.set_quest_child_progress(quest.id, child.id, prog)
        _LOGGER.info("Quest '%s' completed by %s (+%d)", quest.name, child.name, bonus)
