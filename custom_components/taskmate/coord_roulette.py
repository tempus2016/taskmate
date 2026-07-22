"""Chore roulette (#677).

An opt-in nudge for the child who has stalled: spin once, get a random chore
from today's outstanding list, and earn a multiplier on it if they do it.

The pick is recorded per child per day so it survives a reload and can't be
re-rolled until the parent's daily spin allowance resets. The multiplier is
applied at completion time, next to the difficulty multiplier and the
reactive-chore speed bonus.
"""
from __future__ import annotations

import logging
import random
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_MULTIPLIER = 2.0
DEFAULT_DAILY_SPINS = 1


class RouletteMixin:
    """Mixin providing the chore-roulette spin and its multiplier."""

    # ── settings ─────────────────────────────────────────────────────────
    def roulette_enabled(self) -> bool:
        return bool(self.storage.get_setting("roulette_enabled", False))

    def roulette_multiplier(self) -> float:
        try:
            value = float(self.storage.get_setting("roulette_multiplier", DEFAULT_MULTIPLIER))
        except (TypeError, ValueError):
            return DEFAULT_MULTIPLIER
        # A multiplier below 1 would punish the child for spinning.
        return max(1.0, value)

    def roulette_daily_spins(self) -> int:
        try:
            value = int(self.storage.get_setting("roulette_daily_spins", DEFAULT_DAILY_SPINS))
        except (TypeError, ValueError):
            return DEFAULT_DAILY_SPINS
        return max(1, value)

    # ── state ────────────────────────────────────────────────────────────
    def _roulette_state(self) -> dict[str, Any]:
        state = self.storage.get_setting("roulette_state", {})
        return dict(state) if isinstance(state, dict) else {}

    def roulette_selection(self, child_id: str) -> dict[str, Any] | None:
        """Today's spin result for a child, or None. Yesterday's is ignored."""
        entry = self._roulette_state().get(str(child_id))
        if not isinstance(entry, dict):
            return None
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        if entry.get("date") != today:
            return None
        return entry

    def roulette_spins_left(self, child_id: str) -> int:
        entry = self.roulette_selection(child_id)
        used = int(entry.get("spins", 0)) if entry else 0
        return max(0, self.roulette_daily_spins() - used)

    def _roulette_candidates(self, child_id: str) -> list:
        """Outstanding chores this child could be sent to do right now.

        Uses the coordinator's own availability check, so the weather gate,
        deadlines, dependencies and rotation are all respected — roulette must
        never hand a child a chore they aren't allowed to do.
        """
        today = dt_util.as_local(dt_util.now()).date()
        done_today = {
            c.chore_id for c in self.storage.get_completions()
            if c.child_id == child_id
            and not getattr(c, "bonus_subtask_id", "")
            and dt_util.as_local(c.completed_at).date() == today
        }
        return [
            chore for chore in self.storage.get_chores()
            if chore.id not in done_today
            and self.is_chore_available_for_child(chore, child_id)
        ]

    async def async_spin_roulette(self, child_id: str) -> dict[str, Any]:
        """Spin for a child. Returns the picked chore plus the multiplier.

        Raises ValueError for every "you can't do that" case so the service
        layer can surface a clear message rather than silently doing nothing.
        """
        if not self.roulette_enabled():
            raise ValueError("Chore roulette is switched off")

        child = self.storage.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        if self.roulette_spins_left(child_id) <= 0:
            raise ValueError("No spins left today")

        candidates = self._roulette_candidates(child_id)
        if not candidates:
            raise ValueError("Nothing left to spin for")

        # Don't hand back the chore they were already given today.
        current = self.roulette_selection(child_id)
        if current and len(candidates) > 1:
            candidates = [c for c in candidates if c.id != current.get("chore_id")] or candidates

        picked = random.choice(candidates)
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        used = int(current.get("spins", 0)) if current else 0

        state = self._roulette_state()
        state[str(child_id)] = {
            "date": today,
            "chore_id": picked.id,
            "chore_name": picked.name,
            "multiplier": self.roulette_multiplier(),
            "spins": used + 1,
        }
        self.storage.set_setting("roulette_state", state)
        await self.storage.async_save()
        await self.async_refresh()

        _LOGGER.info("Roulette picked '%s' for %s", picked.name, child.name)
        self.hass.bus.async_fire(
            "taskmate_roulette_spun",
            {
                "child_id": child_id,
                "child_name": child.name,
                "chore_id": picked.id,
                "chore_name": picked.name,
                "multiplier": self.roulette_multiplier(),
                "timestamp": dt_util.now().isoformat(),
            },
        )
        return dict(state[str(child_id)])

    def _apply_roulette_multiplier(self, chore, child_id: str, base: int) -> int:
        """Scale the award when this is the child's roulette chore for today."""
        selection = self.roulette_selection(child_id)
        if not selection or selection.get("chore_id") != chore.id:
            return base
        try:
            multiplier = float(selection.get("multiplier", DEFAULT_MULTIPLIER))
        except (TypeError, ValueError):
            multiplier = DEFAULT_MULTIPLIER
        return max(0, round(base * max(1.0, multiplier)))

    async def async_prune_roulette_state(self, refresh: bool = True) -> int:
        """Drop selections from previous days. Returns how many were cleared."""
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        state = self._roulette_state()
        keep = {cid: entry for cid, entry in state.items()
                if isinstance(entry, dict) and entry.get("date") == today}
        removed = len(state) - len(keep)
        if removed:
            self.storage.set_setting("roulette_state", keep)
            await self.storage.async_save()
            if refresh:
                await self.async_refresh()
        return removed
