"""Virtual pets: a creature that grows as its child does chores.

A gentler motivator than a streak for young children. Once pets are switched
on, a child adopts one (picks a species and a name). It hatches and grows with
every chore the child finishes from then on, is happy on days they do one,
gets sleepy after a missed day or two, and wears accessories the child unlocks
by levelling up. Nothing is ever lost: a sleepy pet perks up with the next
chore.

Growth: every chore since adoption is worth ``pet_xp_per_chore`` and, unless
a parent turns it off, every point earned since adoption counts too, so a big
job grows it faster than a quick one. Spending points never shrinks it —
growth uses points *earned*, not the balance. Parents set the growth each
stage needs.

After fully grown, four things can keep it going, each switched on and tuned
by a parent: its home fills up with a new item every so often, it turns
legendary, it lays an egg the child hatches into the next pet (the old ones
join the pet family), and it gains pet levels.

Nothing reached is ever taken back: an undo, or a parent raising a number,
leaves the pet where it got to. The store keeps the peaks (stage, legendary,
home items, level, egg); everything else is derived on read from the child's
own counters, so pets need no hooks into completion, approval or undo. The
minutely tick records new peaks and announces them.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.util import dt as dt_util

from . import notify_strings
from .const import NOTIF_TYPE_PET_EVOLVED

PET_SPECIES = ("dragon", "cat", "dog", "bunny", "dino", "unicorn")
PET_NAME_MAX = 24
PET_STAGE_NAMES = ("egg", "baby", "kid", "teen", "grown")
# Default growth each stage needs (baby, kid, teen, grown). With 10 per chore
# plus its points, a 5-point chore is worth 15: a pet hatches after 2 chores,
# is big after about 40 and fully grown after about 100.
PET_STAGE_DEFAULTS = (30, 200, 600, 1500)
PET_STAGE_KEYS = ("pet_stage_baby", "pet_stage_kid", "pet_stage_teen", "pet_stage_grown")
PET_GROWTH_MAX = 1_000_000
PET_HOME_ITEMS = 10
PET_FAMILY_LIMIT = 12
# Accessories by the child's level.
PET_ACCESSORIES = (("bow", 3), ("top_hat", 8), ("scarf", 15), ("crown", 25))

# Parent settings: key -> (default, low, high). Booleans are listed apart.
PET_INT_SETTINGS: dict[str, tuple[int, int, int]] = {
    "pet_xp_per_chore": (10, 0, 1000),
    "pet_stage_baby": (PET_STAGE_DEFAULTS[0], 1, PET_GROWTH_MAX),
    "pet_stage_kid": (PET_STAGE_DEFAULTS[1], 1, PET_GROWTH_MAX),
    "pet_stage_teen": (PET_STAGE_DEFAULTS[2], 1, PET_GROWTH_MAX),
    "pet_stage_grown": (PET_STAGE_DEFAULTS[3], 1, PET_GROWTH_MAX),
    "pet_home_every": (300, 1, PET_GROWTH_MAX),
    "pet_legendary_at": (3000, 1, PET_GROWTH_MAX),
    "pet_egg_at": (3000, 1, PET_GROWTH_MAX),
    "pet_family_max": (6, 2, PET_FAMILY_LIMIT),
    "pet_level_every": (300, 1, PET_GROWTH_MAX),
}
PET_BOOL_SETTINGS: dict[str, bool] = {
    "pet_points_count": True,
    "pet_home_enabled": True,
    "pet_legendary_enabled": True,
    "pet_eggs_enabled": True,
    "pet_levels_enabled": False,
}


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).lower() == "true"


class PetsMixin:
    """Per-child virtual pets."""

    def pets_enabled(self) -> bool:
        return _as_bool(self.storage.get_setting("pets_enabled", False), False)

    def _pets(self) -> dict[str, dict[str, Any]]:
        return self.storage.get_section("pets", dict)

    # ── parent settings ────────────────────────────────────────────────

    def _pet_int(self, key: str) -> int:
        default, low, high = PET_INT_SETTINGS[key]
        try:
            value = int(self.storage.get_setting(key, default))
        except (TypeError, ValueError):
            value = default
        return min(high, max(low, value))

    def _pet_on(self, key: str) -> bool:
        return _as_bool(self.storage.get_setting(key, PET_BOOL_SETTINGS[key]), PET_BOOL_SETTINGS[key])

    def pet_stage_thresholds(self) -> tuple[int, ...]:
        """Growth for (egg, baby, kid, teen, grown), always strictly rising."""
        out = [0]
        for key in PET_STAGE_KEYS:
            out.append(max(self._pet_int(key), out[-1] + 1))
        return tuple(out)

    def _pet_after_grown(self, key: str) -> int:
        """A post-grown milestone, never at or below fully grown."""
        return max(self._pet_int(key), self.pet_stage_thresholds()[-1] + 1)

    # ── adoption and hatching ──────────────────────────────────────────

    async def async_adopt_pet(self, child_id: str, species: str, name: str, hatch_egg: bool = False) -> dict[str, Any]:
        """Adopt (or rename) the child's pet; with ``hatch_egg``, hatch the egg it laid."""
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
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        fresh = {
            "species": species,
            "name": name,
            "adopted": today,
            "base": int(child.total_chores_completed or 0),
            "base_points": int(child.total_points_earned or 0),
        }
        if hatch_egg:
            if not existing or not self._pet_view(child, existing)["egg_ready"]:
                raise ValueError("There's no egg to hatch yet.")
            view = self._pet_view(child, existing)
            family = list(existing.get("family") or [])
            family.append(
                {
                    "species": existing.get("species", PET_SPECIES[0]),
                    "name": existing.get("name", ""),
                    "adopted": existing.get("adopted", ""),
                    "until": today,
                    "legendary": bool(view["legendary"]),
                }
            )
            pets[child_id] = {**fresh, "family": family}
        elif existing:
            # Renaming or re-choosing keeps the growth: it's still the same friend.
            existing.update({"species": species, "name": name})
        else:
            pets[child_id] = fresh
        await self.storage.async_save()
        await self.async_refresh()
        return pets[child_id]

    # ── growth ─────────────────────────────────────────────────────────

    def _pet_growth(self, child, pet: dict[str, Any]) -> tuple[int, int]:
        """(chores since adoption, growth)."""
        chores = max(0, int(child.total_chores_completed or 0) - int(pet.get("base", 0) or 0))
        points = 0
        # Pets adopted before growth counted points have no points baseline;
        # they grow on chores alone rather than jumping on every point ever earned.
        if "base_points" in pet and self._pet_on("pet_points_count"):
            points = max(0, int(child.total_points_earned or 0) - int(pet.get("base_points", 0) or 0))
        return chores, chores * self._pet_int("pet_xp_per_chore") + points

    def _pet_view(self, child, pet: dict[str, Any]) -> dict[str, Any]:
        """Everything derived about one pet: stage, extras and the next goal."""
        chores, xp = self._pet_growth(child, pet)
        steps = self.pet_stage_thresholds()
        computed = max(i for i, at in enumerate(steps) if xp >= at)
        reached = pet.get("stage_reached")
        peak = PET_STAGE_NAMES.index(reached) if reached in PET_STAGE_NAMES else 0
        index = max(peak, computed)
        grown = index == len(PET_STAGE_NAMES) - 1
        grown_at = steps[-1]
        post = max(0, xp - grown_at) if grown else 0

        home = None
        if self._pet_on("pet_home_enabled"):
            every = self._pet_int("pet_home_every")
            home = min(PET_HOME_ITEMS, max(post // every if grown else 0, int(pet.get("home_peak", 0) or 0)))

        legendary_on = self._pet_on("pet_legendary_enabled")
        legendary = legendary_on and (
            bool(pet.get("legendary")) or (grown and xp >= self._pet_after_grown("pet_legendary_at"))
        )

        level = None
        if self._pet_on("pet_levels_enabled") and grown:
            every = self._pet_int("pet_level_every")
            level = max(1 + post // every, int(pet.get("level_peak", 0) or 0))

        family = list(pet.get("family") or [])
        room = len(family) + 1 < self._pet_int("pet_family_max")
        egg_ready = False
        if self._pet_on("pet_eggs_enabled") and room:
            if pet.get("egg_laid"):
                egg_ready = True
            elif grown:
                egg_ready = legendary if legendary_on else xp >= self._pet_after_grown("pet_egg_at")

        # The next thing to look forward to, for the progress bar.
        goal = None
        if not grown:
            goal = {"kind": "stage", "from": steps[index], "at": steps[index + 1]}
        else:
            options = []
            if home is not None and home < PET_HOME_ITEMS:
                every = self._pet_int("pet_home_every")
                options.append(("home", grown_at + home * every, grown_at + (home + 1) * every))
            if level is not None:
                every = self._pet_int("pet_level_every")
                options.append(("level", grown_at + (level - 1) * every, grown_at + level * every))
            if legendary_on and not legendary:
                options.append(("legendary", grown_at, self._pet_after_grown("pet_legendary_at")))
            elif not legendary_on and self._pet_on("pet_eggs_enabled") and room and not egg_ready:
                options.append(("egg", grown_at, self._pet_after_grown("pet_egg_at")))
            options = [o for o in options if o[2] > xp]
            if options:
                kind, start, at = min(options, key=lambda o: o[2])
                goal = {"kind": kind, "from": min(start, xp), "at": at}

        return {
            "chores": chores,
            "xp": xp,
            "stage": PET_STAGE_NAMES[index],
            "legendary": legendary,
            "home": home,
            "level": level,
            "egg_ready": egg_ready,
            "family": family,
            "goal": goal,
        }

    def pet_state(self, child) -> dict[str, Any] | None:
        """What a card needs to draw the child's pet; None while pets are off."""
        if not self.pets_enabled():
            return None
        pet = self._pets().get(child.id)
        if not pet:
            return {"adopted": False}
        view = self._pet_view(child, pet)
        level = int(getattr(child, "level", 1) or 1)
        state: dict[str, Any] = {
            "adopted": True,
            "name": pet.get("name", ""),
            "species": pet.get("species", PET_SPECIES[0]),
            "stage": view["stage"],
            "chores": view["chores"],
            "xp": view["xp"],
            "mood": self._pet_mood(child),
            "accessories": [acc for acc, at in PET_ACCESSORIES if level >= at],
        }
        # Only what's switched on and reached goes out, to keep the attribute small.
        if view["goal"]:
            state["goal"] = view["goal"]
        if view["legendary"]:
            state["legendary"] = True
        if view["home"]:
            state["home"] = view["home"]
        if view["level"] is not None:
            state["pet_level"] = view["level"]
        if view["egg_ready"]:
            state["egg_ready"] = True
        if view["family"]:
            state["family"] = [
                {
                    "species": f.get("species", PET_SPECIES[0]),
                    "name": f.get("name", ""),
                    "legendary": bool(f.get("legendary")),
                }
                for f in view["family"]
            ]
        return state

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

    async def async_check_pet_growth(self, refresh: bool = True) -> int:
        """Record every pet's new peaks and announce them. Idempotent.

        The first look at a pet only records where it is — no fanfare for a
        pet that was already big when this started counting.
        """
        if not self.pets_enabled():
            return 0
        news_count = 0
        for child_id, pet in list(self._pets().items()):
            child = self.get_child(child_id)
            if child is None:
                continue
            view = self._pet_view(child, pet)
            first_look = pet.get("stage_reached") is None
            news: list[tuple[str, dict[str, Any]]] = []
            changed = False
            old_stage = PET_STAGE_NAMES.index(pet["stage_reached"]) if not first_look else 0
            new_stage = PET_STAGE_NAMES.index(view["stage"])
            if first_look or new_stage > old_stage:
                pet["stage_reached"] = view["stage"]
                changed = True
                if not first_look:
                    news.append(("stage", {"stage": view["stage"]}))
            if view["legendary"] and not pet.get("legendary"):
                pet["legendary"] = True
                changed = True
                news.append(("legendary", {}))
            if view["home"] and view["home"] > int(pet.get("home_peak", 0) or 0):
                pet["home_peak"] = view["home"]
                changed = True
            if view["level"] is not None and view["level"] > int(pet.get("level_peak", 0) or 0):
                had = int(pet.get("level_peak", 0) or 0)
                pet["level_peak"] = view["level"]
                changed = True
                if had and not first_look:
                    news.append(("level", {"pet_level": view["level"]}))
            if view["egg_ready"] and not pet.get("egg_laid"):
                pet["egg_laid"] = True
                changed = True
                news.append(("egg", {}))
            if not changed:
                continue
            await self.storage.async_save()
            if first_look:
                continue
            for kind, extra in news:
                news_count += 1
                context = {
                    "child_id": child_id,
                    "child_name": child.name,
                    "pet_name": pet.get("name", ""),
                    "species": pet.get("species", PET_SPECIES[0]),
                    "kind": kind,
                    **extra,
                }
                context["news"] = notify_strings.render(getattr(self, "hass", None), f"pet_news_{kind}", context)
                await self.notifications.fire(NOTIF_TYPE_PET_EVOLVED, context)
        if news_count and refresh:
            await self.async_refresh()
        return news_count
