"""Sibling checks: an older child checks a younger one's chore.

A parent decides who may check whom (``sibling_check_pairs``: checker id →
the children they check) and a small bonus per check. The checker's card
lists their siblings' completions waiting for approval with two buttons:

* **Looks done** approves it through the normal approval path, marked as a
  sibling check (``checked_by``), and pays the checker the bonus.
* **Not yet** leaves it waiting for a parent, with the checker's note on it.

Parents keep the last word: a sibling-approved chore can still be rejected or
its approval undone, and the bonus is an ordinary transaction they can undo.
Each check is logged for the activity feed.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.util import dt as dt_util

from .models import PRAISE_NOTE_MAX, clean_label, generate_id

_LOGGER = logging.getLogger(__name__)

SIBLING_CHECK_VERDICTS = ("done", "not_yet")
SIBLING_CHECK_MAX_BONUS = 50
# At most this many waiting checks on a checker's card (16 KB cap).
SIBLING_CHECK_CARD_MAX = 5
SIBLING_CHECK_LOG_KEEP = 30


class SiblingChecksMixin:
    """Who may check whom, the checker's queue and the check itself."""

    def sibling_checks_enabled(self) -> bool:
        return bool(self.storage.get_setting("sibling_check_enabled", False))

    def sibling_check_bonus(self) -> int:
        try:
            return max(0, min(SIBLING_CHECK_MAX_BONUS, int(self.storage.get_setting("sibling_check_bonus", 1))))
        except (TypeError, ValueError):
            return 1

    def sibling_checkees(self, checker_id: str) -> list[str]:
        """The children ``checker_id`` may check (never themselves)."""
        pairs = self.storage.get_setting("sibling_check_pairs", {})
        if not isinstance(pairs, dict):
            return []
        ids = pairs.get(checker_id)
        if not isinstance(ids, list):
            return []
        return [c for c in ids if isinstance(c, str) and c != checker_id]

    def _sibling_checkable(self, completion, chore) -> bool:
        """A waiting, ordinary chore completion no one has checked yet."""
        if completion.approved or completion.bonus_subtask_id or getattr(completion, "checked_by", ""):
            return False
        if chore is None or getattr(chore, "open_ended", False):
            return False  # a parent prices open-ended work
        return not getattr(completion, "bounty_id", "")

    def sibling_checks_for_child(self, checker_id: str, pending=None, chore_lookup=None) -> list[dict[str, Any]]:
        """The completions this child is asked to check, oldest first."""
        if not self.sibling_checks_enabled():
            return []
        checkees = set(self.sibling_checkees(checker_id))
        if not checkees:
            return []
        if pending is None:
            pending = [c for c in self.storage.get_completions() if not c.approved]
        if chore_lookup is None:
            chore_lookup = {c.id: c for c in self.storage.get_chores()}
        names = {c.id: c.name for c in self.storage.get_children()}
        out = []
        for comp in sorted(pending, key=lambda c: c.completed_at):
            chore = chore_lookup.get(comp.chore_id)
            if comp.child_id not in checkees or not self._sibling_checkable(comp, chore):
                continue
            out.append(
                {
                    "completion_id": comp.id,
                    "child_id": comp.child_id,
                    "child_name": names.get(comp.child_id, ""),
                    "chore_name": chore.name,
                    "completed_at": comp.completed_at.isoformat(),
                    **({"photo": True} if getattr(comp, "photo_url", "") else {}),
                }
            )
            if len(out) >= SIBLING_CHECK_CARD_MAX:
                break
        return out

    async def async_sibling_check(self, checker_id: str, completion_id: str, verdict: str, note: str = "") -> None:
        """Record a sibling's verdict; "done" approves, "not_yet" leaves it waiting."""
        if not self.sibling_checks_enabled():
            raise ValueError("Sibling checks are turned off")
        if verdict not in SIBLING_CHECK_VERDICTS:
            raise ValueError(f"Unknown verdict {verdict}")
        checker = self.get_child(checker_id)
        if checker is None:
            raise ValueError(f"Child {checker_id} not found")
        completion = next((c for c in self.storage.get_completions() if c.id == completion_id), None)
        if completion is None:
            raise ValueError("That chore has already been checked. Refresh the card.")
        if completion.child_id == checker_id:
            raise ValueError("You can't check your own chore")
        if completion.child_id not in self.sibling_checkees(checker_id):
            raise ValueError(f"{checker.name} can't check this child's chores")
        chore = self.get_chore(completion.chore_id)
        if not self._sibling_checkable(completion, chore):
            raise ValueError("That chore has already been checked. Refresh the card.")
        note = clean_label(note, PRAISE_NOTE_MAX)
        completion.checked_by = checker_id
        completion.check_note = note if verdict == "not_yet" else ""
        self.storage.update_completion(completion)
        bonus = self.sibling_check_bonus() if verdict == "done" else 0
        self._log_sibling_check(checker_id, completion, chore.name, verdict, note, bonus)
        if verdict == "done":
            await self.async_approve_chore(completion_id, refresh=False)
        if bonus:
            # Saves and refreshes, so the approval above lands with it.
            await self.async_add_points(checker_id, bonus, reason=f"Sibling check: {chore.name}")
        else:
            await self.storage.async_save()
            await self.async_refresh()
        checkee = self.get_child(completion.child_id)
        self.hass.bus.async_fire(
            "taskmate_sibling_check",
            {
                "child_id": checker_id,
                "child_name": checker.name,
                "checked_child_id": completion.child_id,
                "checked_child_name": getattr(checkee, "name", ""),
                "chore_id": completion.chore_id,
                "chore_name": chore.name,
                "completion_id": completion_id,
                "verdict": verdict,
                "bonus": bonus,
                **({"note": note} if note and verdict == "not_yet" else {}),
                "timestamp": dt_util.now().isoformat(),
            },
        )

    def _log_sibling_check(self, checker_id: str, completion, chore_name: str, verdict: str, note: str, bonus: int):
        log = self.storage.get_section("sibling_checks", list)
        log.append(
            {
                "id": generate_id(),
                "checker_id": checker_id,
                "child_id": completion.child_id,
                "chore_id": completion.chore_id,
                "chore_name": chore_name,
                "verdict": verdict,
                **({"note": note} if note and verdict == "not_yet" else {}),
                **({"bonus": bonus} if bonus else {}),
                "at": dt_util.now().isoformat(),
            }
        )
        del log[:-SIBLING_CHECK_LOG_KEEP]

    def recent_sibling_checks(self) -> list[dict[str, Any]]:
        """Sibling checks for the activity feed, oldest first."""
        out = []
        for row in self.storage.get_section("sibling_checks", list):
            if not isinstance(row, dict):
                continue
            out.append(
                {
                    "id": row.get("id", ""),
                    "type": "sibling_check",
                    "child_id": row.get("checker_id", ""),
                    "checked_child_id": row.get("child_id", ""),
                    "chore_id": row.get("chore_id", ""),
                    "chore_name": row.get("chore_name", ""),
                    "verdict": row.get("verdict", ""),
                    **({"note": row["note"]} if row.get("note") else {}),
                    "created_at": str(row.get("at", "")),
                }
            )
        return out
