"""Per-child stage (#1262).

A child's stage is the stored ``Child.age_group`` (#980), relabelled "Stage"
in the panel. Each stage carries a few suggestions:

* card behaviour, which the child card reads from the child's stage whenever
  the card's own YAML leaves the option unset (nothing is written for these);
* chore changes, which are only offered when the family-wide ``stage_scope``
  setting is "all", and are applied once, when a parent confirms, to the
  chores assigned to that child alone. Chores shared with other children are
  never touched; they come back in ``skipped_shared``.
* ideas that don't map onto a chore field, shown as tips and never applied.

Nothing here runs on its own: a stage change only applies anything through
``async_apply_child_stage`` with ``apply=True``.
"""

from __future__ import annotations

from typing import Any

from .const import AGE_GROUPS, STAGE_SCOPE_SETTING, STAGE_SCOPES
from .errors import TaskMateError

# What the child card does by default at each stage (when its YAML is unset).
# Mirrored by STAGE_CARD_DEFAULTS in taskmate-child-card.js.
STAGE_CARD_ITEMS: dict[str, tuple[str, ...]] = {
    "3_5": ("pre_reader_on",),
    "6_8": ("pre_reader_off", "descriptions_on"),
    "9_12": ("pre_reader_off",),
    "13_plus": ("pre_reader_off", "fewer_game_bits"),
}
# Chore changes a stage may apply (stage_scope "all" only).
STAGE_CHORE_ITEMS: dict[str, tuple[str, ...]] = {
    "3_5": ("no_deadlines",),
    "6_8": (),
    "9_12": (),
    "13_plus": (),
}
# Ideas with no clean chore field behind them: shown, never applied.
STAGE_TIPS: dict[str, tuple[str, ...]] = {
    "3_5": ("few_chores",),
    "6_8": ("rotation",),
    "9_12": ("open_ended", "weekly_targets"),
    "13_plus": ("savings_goals",),
}

# "No deadlines or deductions": the fields that make a missed or late chore
# cost points, and the value each one goes back to.
_NO_DEADLINE_FIELDS: tuple[tuple[str, Any], ...] = (
    ("mandatory", False),
    ("mandatory_penalty_points", 0),
    ("late_penalty", 0),
)


def _no_deadline_changes(chore) -> dict[str, list[Any]]:
    """{field: [old, new]} for the deadline/deduction fields set on ``chore``."""
    out: dict[str, list[Any]] = {}
    for key, off in _NO_DEADLINE_FIELDS:
        cur = getattr(chore, key, off)
        if cur != off and cur:
            out[key] = [cur, off]
    return out


class StagesMixin:
    """Per-child stage suggestions and the once-only apply."""

    def stage_scope(self) -> str:
        value = self.storage.get_setting(STAGE_SCOPE_SETTING, "cards")
        return value if value in STAGE_SCOPES else "cards"

    def stage_plan(self, child_id: str, stage: str) -> dict[str, Any]:
        """What moving ``child_id`` to ``stage`` would suggest and change.

        Pure: nothing is written. ``chores`` lists the changes the apply would
        make (only when ``stage_scope`` is "all"); ``skipped_shared`` the
        shared chores it leaves alone though they'd otherwise qualify.
        """
        child = self.storage.get_child(child_id)
        if child is None:
            raise TaskMateError("child_not_found", child_id=child_id)
        scope = self.stage_scope()
        plan: dict[str, Any] = {
            "child_id": child_id,
            "stage": stage,
            "previous": child.age_group,
            "scope": scope,
            "card": list(STAGE_CARD_ITEMS.get(stage, ())),
            "chore_items": [],
            "tips": list(STAGE_TIPS.get(stage, ())),
            "chores": [],
            "skipped_shared": [],
        }
        if stage not in AGE_GROUPS or scope != "all":
            return plan
        items = STAGE_CHORE_ITEMS.get(stage, ())
        plan["chore_items"] = list(items)
        if "no_deadlines" not in items:
            return plan
        for chore in self.storage.get_chores():
            assigned = list(chore.assigned_to or [])
            # Empty assigned_to means everyone, so it counts as shared.
            if child_id not in assigned and assigned:
                continue
            changes = _no_deadline_changes(chore)
            if not changes:
                continue
            if assigned != [child_id]:
                plan["skipped_shared"].append({"chore_id": chore.id, "name": chore.name})
                continue
            plan["chores"].append({"chore_id": chore.id, "name": chore.name, "changes": changes})
        return plan

    async def async_apply_child_stage(self, child_id: str, stage: str, *, apply: bool) -> dict[str, Any]:
        """Set the child's stage; with ``apply`` also make the chore changes once.

        Returns the plan with ``applied`` saying whether any chore changed.
        """
        plan = self.stage_plan(child_id, stage)
        child = self.storage.get_child(child_id)
        child.age_group = stage
        self.storage.update_child(child)
        mandatory_changed = False
        changed: list[dict[str, Any]] = []
        if apply:
            for item in plan["chores"]:
                chore = self.storage.get_chore(item["chore_id"])
                if chore is None:
                    continue
                for key, (_old, new) in item["changes"].items():
                    setattr(chore, key, new)
                mandatory_changed = mandatory_changed or "mandatory" in item["changes"]
                self.storage.update_chore(chore)
                changed.append(item)
        plan["chores"] = changed
        plan["applied"] = bool(changed)
        await self.storage.async_save()
        if mandatory_changed:
            await self.async_rearm_mandatory_schedules()
        await self.async_refresh()
        return plan

    def chore_stage_cleanup(self, chore_id: str) -> None:
        """Drop a deleted chore from every child's chore_stage map."""
        for child in self.storage.get_children():
            if chore_id in (child.chore_stage or {}):
                child.chore_stage.pop(chore_id, None)
                self.storage.update_child(child)
