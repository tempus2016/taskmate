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

from . import notify_strings
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
        # Kept for 7 days so it can be restored with everyone's progress.
        self._snapshot_quest(quest_id)
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
            out.append(
                {
                    "quest_id": quest.id,
                    "name": quest.name,
                    "icon": quest.icon,
                    "total_steps": total,
                    "step": min(step, total),
                    "done": done,
                    "times_completed": int(prog.get("completed_count", 0)),
                    "bonus_points": quest.bonus_points,
                    "next_chore_id": quest.steps[step] if not done and step < total else "",
                }
            )
        return out

    # ── Progression ──────────────────────────────────────────────────────
    async def _async_advance_quests(self, child_id: str, chore_id: str, completion_id: str = "") -> None:
        """Advance any active quest whose current step is ``chore_id``.

        Called after a (non-bonus) chore completion is approved. Persists and
        refreshes only if a quest actually advanced. ``completion_id`` is
        remembered against the step it moved, so only that completion's
        reversal can move the quest back (a second occurrence of the same
        chore, or a sibling occurrence, never rewinds a step it didn't earn).
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
            advanced_by = [str(x) for x in (prog.get("advanced_by") or [])]
            advanced_by.append(completion_id or "")
            prog["advanced_by"] = advanced_by
            self.storage.set_quest_child_progress(quest.id, child_id, prog)
            changed = True

            if step >= len(quest.steps):
                await self._complete_quest(quest, child, prog)

        if changed:
            await self.storage.async_save()
            await self.async_refresh()

    def _quest_rewind_plan(self, child_id: str, chore_id: str, completion_id: str = "") -> list[tuple]:
        """Which quests a reversal of ``chore_id`` would move back, and how.

        Returns ``(quest, new_progress, was_finished)`` per affected quest.
        When the step remembers which completion advanced it, only that
        completion's reversal counts; a legacy record (no ``advanced_by``)
        keeps the chore-keyed behaviour.
        """
        plan: list[tuple] = []
        for quest in self.storage.get_quests():
            if not quest.active or not quest.steps:
                continue
            if not self._quest_applies_to(quest, child_id):
                continue
            prog = dict(self.storage.get_quest_child_progress(quest.id, child_id))
            step = int(prog.get("step", 0))
            completed = int(prog.get("completed_count", 0))
            advanced_by = [str(x) for x in (prog.get("advanced_by") or [])]
            prev_advanced_by = [str(x) for x in (prog.get("prev_advanced_by") or [])]
            was_finished = False

            if step > 0 and quest.steps[step - 1] == chore_id:
                # Ordinary mid-quest step, or the final step of a one-shot
                # quest (whose step stays at len(steps) once finished).
                if not self._completion_owns_step(advanced_by, completion_id):
                    continue
                was_finished = step >= len(quest.steps)
                prog["step"] = step - 1
                prog["advanced_by"] = advanced_by[:-1]
            elif step == 0 and completed > 0 and quest.steps[-1] == chore_id:
                # A repeatable quest wrapped back to the start on this very
                # completion: step back into its final step.
                if not self._completion_owns_step(prev_advanced_by, completion_id):
                    continue
                was_finished = True
                prog["step"] = len(quest.steps) - 1
                prog["advanced_by"] = prev_advanced_by[:-1]
                prog.pop("prev_advanced_by", None)
            else:
                continue

            if was_finished:
                prog["completed_count"] = max(0, completed - 1)
            plan.append((quest, prog, was_finished))
        return plan

    @staticmethod
    def _completion_owns_step(advanced_by: list[str], completion_id: str) -> bool:
        """Whether the completion being reversed is the one that earned the last step."""
        if not advanced_by:
            return True  # legacy progress: nothing recorded, keep chore-keyed behaviour
        owner = advanced_by[-1]
        if not owner or not completion_id:
            return True
        return owner == completion_id

    def _quest_refund_owed(self, child_id: str, chore_id: str, completion_id: str = "") -> int:
        """Quest bonus a reversal of ``chore_id`` would take back, without doing it."""
        return sum(
            int(quest.bonus_points or 0)
            for quest, _prog, was_finished in self._quest_rewind_plan(child_id, chore_id, completion_id)
            if was_finished
        )

    async def _async_rewind_quests(self, child_id: str, chore_id: str, completion_id: str = "") -> None:
        """Undo a quest step that a now-reversed completion had advanced.

        Progress used to be one-way: rejecting or un-approving a completion left
        the quest sitting on the step it unlocked, so re-approving the same
        completion advanced it again — and on a repeatable quest that meant
        paying the completion bonus a second time for one piece of work.
        """
        child = self.get_child(child_id)
        if not child:
            return
        changed = False
        for quest, prog, was_finished in self._quest_rewind_plan(child_id, chore_id, completion_id):
            if was_finished:
                self._refund_quest_bonus(quest, child)
            self.storage.set_quest_child_progress(quest.id, child_id, prog)
            changed = True

        if changed:
            self.storage.update_child(child)
            await self.storage.async_save()
            await self.async_refresh()

    def _refund_quest_bonus(self, quest: Quest, child) -> None:
        """Take back a quest completion bonus, logging the reversal."""
        bonus = int(quest.bonus_points or 0)
        if bonus <= 0:
            return
        child.points = max(0, child.points - bonus)
        child.total_points_earned = max(0, child.total_points_earned - bonus)
        child.career_score = child.total_points_earned - child.total_penalties_received
        self.storage.add_points_transaction(
            PointsTransaction(
                child_id=child.id,
                points=-bonus,
                reason=f"Quest reversed: {quest.name}",
                created_at=dt_util.now(),
            ),
            reverses_season=True,
        )

    async def _complete_quest(self, quest: Quest, child, prog: dict) -> None:
        """Award the quest bonus and reset/finalise progress."""
        prog["completed_count"] = int(prog.get("completed_count", 0)) + 1
        prog["last_completed"] = dt_util.now().isoformat()

        bonus = int(quest.bonus_points or 0)
        if bonus > 0:
            child.points += bonus
            child.total_points_earned += bonus
            child.career_score = child.total_points_earned - child.total_penalties_received
            self.storage.add_points_transaction(
                PointsTransaction(
                    child_id=child.id,
                    points=bonus,
                    reason=f"Quest complete: {quest.name}",
                    created_at=dt_util.now(),
                )
            )
            if hasattr(self, "_maybe_level_up"):
                await self._maybe_level_up(child)
            self.storage.update_child(child)

        self.hass.bus.async_fire(
            "taskmate_quest_completed",
            {
                "child_id": child.id,
                "child_name": child.name,
                "quest_id": quest.id,
                "quest_name": quest.name,
                "bonus": bonus,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        if hasattr(self, "_celebrate"):
            await self._celebrate(
                child,
                "quest_completed",
                notify_strings.render(
                    self.hass,
                    "celebrate_quest_completed",
                    {"child_name": child.name, "quest_name": quest.name},
                ),
                tier=3,
                extra={"quest_id": quest.id, "bonus": bonus},
            )

        # Repeatable quests start over; one-shot quests stay complete. The
        # finished cycle's completion ids are kept so reversing the one that
        # closed it can step back into the final step.
        if quest.repeatable:
            prog["step"] = 0
            prog["prev_advanced_by"] = list(prog.get("advanced_by") or [])
            prog["advanced_by"] = []
        self.storage.set_quest_child_progress(quest.id, child.id, prog)
        _LOGGER.info("Quest '%s' completed by %s (+%d)", quest.name, child.name, bonus)
