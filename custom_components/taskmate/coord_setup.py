"""Setup wizard (#980): create a family's children, chores and rewards in one go.

The wizard in the admin panel collects everything first and sends it here in a
single call. Each item goes through the ordinary add path (``async_add_child``,
``async_apply_template``, ``async_add_reward``) with its refresh deferred, and
the coordinator refreshes once at the end — one refresh per item would freeze
the panel for seconds on a 30-chore setup (see #794).

Everything is checked before anything is written, so a bad birthday or an
unknown child leaves the family exactly as it was. The wizard only ever adds:
a chore or reward whose name the family already has is skipped, a child whose
name already exists is reused, and an existing child's birthday or age group is
only filled in when it is still empty.
"""

from __future__ import annotations

import logging
from typing import Any

from .const import AGE_GROUPS
from .coord_birthdays import normalize_birthday

_LOGGER = logging.getLogger(__name__)

# Chore definition keys passed straight through to async_apply_template.
_CHORE_KEYS = (
    "name",
    "points",
    "description",
    "icon",
    "requires_approval",
    "time_category",
    "daily_limit",
    "schedule_mode",
    "due_days",
    "recurrence",
    "recurrence_day",
    "assignment_mode",
)


def _fold(name: str) -> str:
    return (name or "").strip().casefold()


def _age_group(value: Any) -> str:
    value = value or ""
    if value and value not in AGE_GROUPS:
        raise ValueError(f"Unknown age group {value!r}")
    return value


class SetupWizardMixin:
    """Mixin providing the setup wizard's one-call create."""

    async def async_apply_setup_wizard(
        self,
        children: list[dict] | None = None,
        child_updates: list[dict] | None = None,
        chores: list[dict] | None = None,
        rewards: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Add the wizard's children, chores and rewards with a single refresh.

        ``children`` carry a ``ref`` the chores' ``assigned_to`` can point at
        before the child has an id. Returns the ref → id map and what was
        created or skipped.
        """
        children = list(children or [])
        child_updates = list(child_updates or [])
        chores = list(chores or [])
        rewards = list(rewards or [])

        existing_children = self.storage.get_children()
        by_name = {_fold(c.name): c for c in existing_children}
        known_ids = {c.id for c in existing_children}

        # --- validate everything before writing anything --------------------
        new_children: list[dict] = []
        ref_to_id: dict[str, str] = {}
        seen_refs: set[str] = set()
        for spec in children:
            ref = str(spec.get("ref") or "")
            name = (spec.get("name") or "").strip()
            if not ref or ref in seen_refs:
                raise ValueError("Every new child needs its own ref")
            if not name:
                raise ValueError("A child needs a name")
            seen_refs.add(ref)
            twin = by_name.get(_fold(name))
            if twin is not None:
                # Already in the family (or sent twice): reuse, never duplicate.
                ref_to_id[ref] = twin.id
                continue
            new_children.append(
                {
                    "ref": ref,
                    "name": name,
                    "avatar": spec.get("avatar") or "mdi:account-circle",
                    "birthday": normalize_birthday(spec.get("birthday", "")),
                    "age_group": _age_group(spec.get("age_group")),
                }
            )

        updates: list[tuple[Any, str, str]] = []
        for spec in child_updates:
            child = self.storage.get_child(spec.get("child_id", ""))
            if child is None:
                raise ValueError(f"Child {spec.get('child_id')} not found")
            birthday = normalize_birthday(spec.get("birthday", ""))
            age_group = _age_group(spec.get("age_group"))
            # Add-only: fill in what is missing, never overwrite.
            birthday = birthday if birthday and not child.birthday else ""
            age_group = age_group if age_group and not child.age_group else ""
            if birthday or age_group:
                updates.append((child, birthday, age_group))

        pending_refs = {c["ref"] for c in new_children}

        def resolve(who: str) -> str:
            if who in ref_to_id:
                return ref_to_id[who]
            if who in pending_refs or who in known_ids:
                return who
            raise ValueError(f"Chore assigned to an unknown child {who!r}")

        have_chores = {_fold(c.name) for c in self.storage.get_chores()}
        chore_defs: list[dict] = []
        skipped_chores = 0
        for spec in chores:
            name = (spec.get("name") or "").strip()
            if not name:
                raise ValueError("A chore needs a name")
            assigned = [resolve(str(w)) for w in spec.get("assigned_to") or []]
            if _fold(name) in have_chores:
                skipped_chores += 1
                continue
            chore_def = {k: spec[k] for k in _CHORE_KEYS if k in spec}
            chore_def["name"] = name
            chore_def["assigned_to"] = assigned
            chore_defs.append(chore_def)

        have_rewards = {_fold(r.name) for r in self.storage.get_rewards()}
        reward_specs: list[dict] = []
        skipped_rewards = 0
        for spec in rewards:
            name = (spec.get("name") or "").strip()
            if not name:
                raise ValueError("A reward needs a name")
            if _fold(name) in have_rewards:
                skipped_rewards += 1
                continue
            have_rewards.add(_fold(name))
            reward_specs.append(spec)

        # --- write, deferring every refresh to the end -----------------------
        for spec in new_children:
            child = await self.async_add_child(
                name=spec["name"],
                avatar=spec["avatar"],
                birthday=spec["birthday"],
                age_group=spec["age_group"],
                refresh=False,
            )
            ref_to_id[spec["ref"]] = child.id
        for child, birthday, age_group in updates:
            if birthday:
                child.birthday = birthday
            if age_group:
                child.age_group = age_group
            await self.async_update_child(child, refresh=False)

        for chore_def in chore_defs:
            chore_def["assigned_to"] = [ref_to_id.get(w, w) for w in chore_def["assigned_to"]]
        chore_ids = await self.async_apply_template(chore_defs, refresh=False) if chore_defs else []

        for spec in reward_specs:
            await self.async_add_reward(
                name=(spec.get("name") or "").strip(),
                cost=int(spec.get("cost", 0)),
                description=spec.get("description", ""),
                icon=spec.get("icon") or "mdi:gift",
                refresh=False,
            )

        await self.async_refresh()
        _LOGGER.info(
            "Setup wizard added %d children, %d chores and %d rewards",
            len(new_children),
            len(chore_ids),
            len(reward_specs),
        )
        return {
            "children": ref_to_id,
            "children_added": len(new_children),
            "chores_added": len(chore_ids),
            "rewards_added": len(reward_specs),
            "chores_skipped": skipped_chores,
            "rewards_skipped": skipped_rewards,
        }
