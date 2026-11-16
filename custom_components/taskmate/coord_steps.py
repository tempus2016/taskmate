"""Multipart chores (#1253) mixin for TaskMateCoordinator.

A chore with ``steps`` is a checklist of required steps ("Tidy bedroom":
clothes away, toys in the box, make the bed). The child ticks the steps off
one at a time; ticking earns nothing. The chore itself is completed through
the ordinary ``async_complete_chore`` path, which refuses a child's
completion while a step is still open, so approvals, points, streaks,
photos and celebrations all work exactly as for any other chore.

Which steps a child has ticked lives in ``storage["chore_steps"]``, dated,
so it resets on its own at midnight. Each entry also carries the "round":
how many times the child had already completed the chore today. A chore
done more than once a day therefore starts every go with a clean
checklist, and undoing a completion brings the ticked steps back.
"""

from __future__ import annotations

import logging

from homeassistant.util import dt as dt_util

from .errors import TaskMateError

_LOGGER = logging.getLogger(__name__)


def chore_has_steps(chore) -> bool:
    steps = getattr(chore, "steps", None)
    return isinstance(steps, list) and bool(steps)


class StepsMixin:
    """Per-child, per-day step ticks for multipart chores."""

    def _steps_round(self, chore, child_id: str, day) -> int:
        """How many of the child's own completions of ``chore`` landed on ``day``.

        Bonus sub-tasks and completions an inspection sent back to redo
        don't count, the same as for the daily limit.
        """
        redo = self.inspection_redo_completion_ids() if hasattr(self, "inspection_redo_completion_ids") else set()
        count = 0
        for comp in self.storage.get_completions():
            if comp.chore_id != chore.id or comp.child_id != child_id or comp.id in redo:
                continue
            if getattr(comp, "bonus_subtask_id", ""):
                continue
            try:
                if dt_util.as_local(comp.completed_at).date() == day:
                    count += 1
            except (AttributeError, TypeError, ValueError):
                continue
        return count

    def chore_steps_done(self, chore, child_id: str, now=None) -> list[str]:
        """Ids of the steps ``child_id`` has ticked on ``chore`` for the current go, in step order."""
        if not chore_has_steps(chore):
            return []
        today = dt_util.as_local(now or dt_util.now()).date()
        entry = self.storage.get_step_progress(chore.id, child_id, today.isoformat())
        if not entry or entry.get("round", 0) != self._steps_round(chore, child_id, today):
            return []
        ticked = set(entry.get("done", []))
        return [step.id for step in chore.steps if step.id in ticked]

    def chore_steps_outstanding(self, chore, child_id: str, now=None) -> bool:
        """True while at least one of the chore's steps is still open for the child."""
        if not chore_has_steps(chore):
            return False
        return len(self.chore_steps_done(chore, child_id, now)) < len(chore.steps)

    async def async_set_chore_step(self, chore_id: str, child_id: str, step_id: str, done: bool = True) -> list[str]:
        """Tick (or untick) one step of a multipart chore for today.

        Returns the step ids now ticked. Ticking earns nothing: the card
        completes the chore through ``complete_chore`` once every step is
        ticked. Only unknown ids raise.
        """
        chore = self.get_chore(chore_id)
        if not chore:
            raise TaskMateError("chore_not_found", chore_id=chore_id)
        if not self.get_child(child_id):
            raise TaskMateError("child_not_found", child_id=child_id)
        if not chore_has_steps(chore):
            raise TaskMateError("chore_steps_none", name=chore.name)
        if not any(step.id == step_id for step in chore.steps):
            raise TaskMateError("chore_step_not_found", step_id=step_id, name=chore.name)

        now = dt_util.now()
        today = dt_util.as_local(now).date()
        ticked = set(self.chore_steps_done(chore, child_id, now))
        if done:
            ticked.add(step_id)
        else:
            ticked.discard(step_id)
        ordered = [step.id for step in chore.steps if step.id in ticked]
        self.storage.set_step_progress(
            chore.id, child_id, today.isoformat(), self._steps_round(chore, child_id, today), ordered
        )
        await self.storage.async_save()
        await self.async_refresh()
        return ordered
