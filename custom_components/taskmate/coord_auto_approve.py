"""Auto-approve chores nobody reviewed in time.

A parent on a 12-hour shift can't approve "Make bed" before the child checks
whether it counted. With ``auto_approve_hours`` set, a chore completion still
waiting after that many hours approves itself at the price the child was
promised, exactly as if a parent had tapped Approve. 0 (the default) is off.

Open-ended chores (#832) are left alone: the child only suggested a price, so
a parent has to set it. Bounty work is left alone too — a bounty pays from its
own posted reward and has its own claim rules.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

AUTO_APPROVE_MAX_HOURS = 168


class AutoApproveMixin:
    """Approves completions that have waited longer than the setting allows."""

    def auto_approve_hours(self) -> int:
        try:
            hours = int(self.storage.get_setting("auto_approve_hours", 0) or 0)
        except (TypeError, ValueError):
            return 0
        return max(0, min(AUTO_APPROVE_MAX_HOURS, hours))

    def overdue_completions(self) -> list:
        """Pending completions old enough to approve themselves now."""
        hours = self.auto_approve_hours()
        if not hours:
            return []
        cutoff = dt_util.now() - timedelta(hours=hours)
        chores = {c.id: c for c in self.storage.get_chores()}
        due = []
        for comp in self.storage.get_completions():
            if comp.approved or getattr(comp, "bounty_id", ""):
                continue
            chore = chores.get(comp.chore_id)
            if chore is None or getattr(chore, "open_ended", False):
                continue
            if comp.completed_at <= cutoff:
                due.append(comp)
        return due

    async def async_auto_approve_overdue(self, refresh: bool = True) -> int:
        """Approve everything past the timeout. Returns how many were approved."""
        overdue = self.overdue_completions()
        count = 0
        for comp in overdue:
            try:
                await self.async_approve_chore(comp.id, refresh=False)
            except ValueError as err:
                _LOGGER.debug("auto-approve skipped %s: %s", comp.id, err)
                continue
            stored = next((c for c in self.storage.get_completions() if c.id == comp.id), None)
            if stored is None or not stored.approved:
                continue
            stored.auto_approved = True
            self.storage.update_completion(stored)
            count += 1
            child = self.storage.get_child(stored.child_id)
            chore = self.storage.get_chore(stored.chore_id)
            self.hass.bus.async_fire(
                "taskmate_chore_auto_approved",
                {
                    "child_id": stored.child_id,
                    "child_name": child.name if child else "",
                    "chore_id": stored.chore_id,
                    "chore_name": chore.name if chore else "",
                    "points": stored.points_awarded,
                    "hours": self.auto_approve_hours(),
                    "timestamp": dt_util.now().isoformat(),
                },
            )
        if count:
            _LOGGER.info("Auto-approved %d chore(s) nobody reviewed in time", count)
            await self.storage.async_save()
            if refresh:
                await self.async_refresh()
        return count
