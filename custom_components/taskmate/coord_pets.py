"""Virtual pets: a creature that grows as its child does chores.

A gentler motivator than a streak for young children. Once pets are switched
on, a child adopts one (picks a species and a name). It hatches and grows with
every chore the child finishes from then on, is happy on days they do one,
gets sleepy after a missed day or two, and wears accessories the child unlocks
by levelling up. Nothing is ever lost: a sleepy pet perks up with the next
chore.

Almost everything is derived on read from the child's own counters, so the
pet needs no hooks into completion, approval or undo: the store only keeps
the species, the name and the chore count at adoption.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.util import dt as dt_util

PET_SPECIES = ("dragon", "cat", "dog", "bunny", "dino", "unicorn")
PET_NAME_MAX = 24
# Chores since adoption needed to reach each stage.
PET_STAGES = (("egg", 0), ("baby", 3), ("kid", 15), ("teen", 40), ("grown", 100))
# Accessories by the child's level.
PET_ACCESSORIES = (("bow", 3), ("top_hat", 8), ("scarf", 15), ("crown", 25))


class PetsMixin:
    """Per-child virtual pets."""

    def pets_enabled(self) -> bool:
        v = self.storage.get_setting("pets_enabled", False)
        return v is True or str(v).lower() == "true"

    def _pets(self) -> dict[str, dict[str, Any]]:
        return self.storage.get_section("pets", dict)

    async def async_adopt_pet(self, child_id: str, species: str, name: str) -> dict[str, Any]:
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        if not self.pets_enabled():
            raise ValueError("Pets are switched off.")
        if species not in PET_SPECIES:
            raise ValueError(f"Unknown pet {species!r}")
        name = (name or "").strip()[:PET_NAME_MAX]
        if not name:
            raise ValueError("Give your pet a name.")
        pets = self._pets()
        existing = pets.get(child_id)
        if existing:
            # Renaming or re-choosing keeps the growth: it's still the same friend.
            existing.update({"species": species, "name": name})
        else:
            pets[child_id] = {
                "species": species,
                "name": name,
                "adopted": dt_util.as_local(dt_util.now()).date().isoformat(),
                "base": int(child.total_chores_completed or 0),
            }
        await self.storage.async_save()
        await self.async_refresh()
        return pets[child_id]

    def pet_state(self, child) -> dict[str, Any] | None:
        """What a card needs to draw the child's pet; None while pets are off."""
        if not self.pets_enabled():
            return None
        pet = self._pets().get(child.id)
        if not pet:
            return {"adopted": False}
        grown = max(0, int(child.total_chores_completed or 0) - int(pet.get("base", 0) or 0))
        stage, stage_at, next_at = PET_STAGES[0][0], 0, None
        for i, (name, needed) in enumerate(PET_STAGES):
            if grown >= needed:
                stage, stage_at = name, needed
                next_at = PET_STAGES[i + 1][1] if i + 1 < len(PET_STAGES) else None
        level = int(getattr(child, "level", 1) or 1)
        return {
            "adopted": True,
            "name": pet.get("name", ""),
            "species": pet.get("species", PET_SPECIES[0]),
            "stage": stage,
            "chores": grown,
            "stage_at": stage_at,
            **({"next_at": next_at} if next_at is not None else {}),
            "mood": self._pet_mood(child),
            "accessories": [acc for acc, at in PET_ACCESSORIES if level >= at],
        }

    def _pet_mood(self, child) -> str:
        """happy (did a chore today), content (yesterday), sleepy (longer).

        A long streak makes a happy pet "proud". Away days (vacation, sick)
        don't make it sleepy — the child was meant to rest.
        """
        today = dt_util.as_local(dt_util.now()).date()
        last = getattr(child, "last_completion_date", None)
        try:
            last_day = date.fromisoformat(last) if last else None
        except (TypeError, ValueError):
            last_day = None
        if last_day == today:
            return "proud" if int(child.current_streak or 0) >= 7 else "happy"
        if self._is_child_on_vacation(child, today):
            return "content"
        if last_day is not None and (today - last_day).days == 1:
            return "content"
        return "sleepy"
